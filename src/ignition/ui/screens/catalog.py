from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from ignition.core.catalog import CatalogService
from ignition.schemas.catalog import InstallStatus, ToolInfo
from ignition.schemas.state import AppStateModel

# g t chord is not natively supported in Textual; using ctrl+t instead.
# Vim-style g t chord is deferred to a future vim-mode layer.
_STATUS_CLASS: dict[InstallStatus, str] = {
    InstallStatus.INSTALLED: "status-installed",
    InstallStatus.OUTDATED: "status-outdated",
    InstallStatus.MISSING: "status-missing",
    InstallStatus.UNMANAGED: "status-unmanaged",
}

_STATUS_LABEL: dict[InstallStatus, str] = {
    InstallStatus.INSTALLED: "Installed",
    InstallStatus.OUTDATED: "Outdated",
    InstallStatus.MISSING: "Missing",
    InstallStatus.UNMANAGED: "Unmanaged",
}


class ToolCatalogScreen(Screen[None]):
    """Tool catalog browser with category sidebar, tool list, and detail panel.

    Allows browsing, searching, and simulating tool installs without touching
    real system state. All mutations are in-memory only (M2 scope).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("/", "focus_search", "Search"),
    ]

    DEFAULT_CSS = """
    ToolCatalogScreen {
        background: $background;
    }

    #toolbar {
        height: auto;
        padding: 0 1;
    }

    #search-input {
        width: 1fr;
    }

    #search-input.hidden {
        display: none;
    }

    #body {
        height: 1fr;
    }

    #sidebar {
        width: 20%;
        border-right: tall $surface;
    }

    #sidebar.search-active {
        opacity: 50%;
    }

    #sidebar-header {
        text-style: bold;
        color: $primary;
        padding: 0 1;
        height: 1;
    }

    #category-list {
        height: 1fr;
    }

    #main {
        width: 80%;
    }

    #tool-list {
        height: 1fr;
    }

    .tool-row {
        height: 1;
        padding: 0 1;
    }

    .tool-name {
        text-style: bold;
        width: 20;
    }

    .tool-description {
        color: $text-secondary;
        width: 1fr;
    }

    .tool-status {
        width: 12;
        text-align: right;
    }

    .status-installed {
        color: $success;
    }

    .status-missing {
        color: $error;
    }

    .status-outdated {
        color: $warning;
    }

    .status-unmanaged {
        color: $text-secondary;
    }

    #detail-panel {
        height: 35%;
        border-top: tall $accent;
        padding: 1 2;
    }

    #detail-panel.hidden {
        display: none;
    }

    #detail-name {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #detail-description {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #detail-meta {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #btn-simulate-install {
        margin-top: 1;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state
        self._catalog = CatalogService()
        self._selected_tool_key: str | None = None
        self._active_category: str = "All"
        self._search_active: bool = False

    # ------------------------------------------------------------------
    # compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            with Horizontal(id="toolbar"):
                yield Input(
                    placeholder="Search tools…",
                    id="search-input",
                    classes="hidden",
                    tooltip="Filter tools by name, description, or category.",
                )
            with Horizontal(id="body"):
                with Vertical(id="sidebar"):
                    yield Label("Categories", id="sidebar-header")
                    yield ListView(id="category-list")
                with Vertical(id="main"):
                    yield ListView(id="tool-list")
            with Vertical(id="detail-panel", classes="hidden"):
                yield Static("", id="detail-name")
                yield Static("", id="detail-description")
                yield Static("", id="detail-meta")
                yield Button(
                    "Simulate Install",
                    id="btn-simulate-install",
                    variant="primary",
                    tooltip="Simulate tool installation (no real changes — demo only).",
                )
        yield Footer()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate category list and tool list after mount."""
        self._refresh_category_list()
        self._populate_tool_list(self._catalog.get_all_tools())

    # ------------------------------------------------------------------
    # population helpers
    # ------------------------------------------------------------------

    def _refresh_category_list(self) -> None:
        """Build the category sidebar from the live tool catalogue."""
        all_tools = self._catalog.get_all_tools()
        categories: set[str] = set()
        for tool in all_tools:
            categories.update(tool.categories)
        sorted_cats = ["All", *sorted(categories)]

        category_list = self.query_one("#category-list", ListView)
        category_list.clear()
        for cat in sorted_cats:
            item = ListItem(Label(cat))
            item._category = cat  # type: ignore[attr-defined]
            category_list.append(item)

    def _populate_tool_list(self, tools: list[ToolInfo]) -> None:
        """Clear and repopulate #tool-list with the given tool set."""
        tool_list = self.query_one("#tool-list", ListView)
        tool_list.clear()
        for tool in tools:
            status_class = _STATUS_CLASS[tool.install_status]
            status_text = _STATUS_LABEL[tool.install_status]
            name_static = Static(tool.name, classes="tool-name")
            desc_static = Static(tool.description, classes="tool-description")
            status_static = Static(status_text, classes=f"tool-status {status_class}")
            item = ListItem(Horizontal(name_static, desc_static, status_static, classes="tool-row"))
            item._tool_key = tool.key  # type: ignore[attr-defined]
            tool_list.append(item)

    # ------------------------------------------------------------------
    # category selection
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Route selection events from category list and tool list."""
        if event.list_view.id == "category-list":
            self._on_category_selected(event)
        elif event.list_view.id == "tool-list":
            self._on_tool_selected(event)

    def _on_category_selected(self, event: ListView.Selected) -> None:
        if self._search_active:
            return
        category = getattr(event.item, "_category", "All")
        self._active_category = category
        if category == "All":
            self._populate_tool_list(self._catalog.get_all_tools())
        else:
            filtered = [t for t in self._catalog.get_all_tools() if category in t.categories]
            self._populate_tool_list(filtered)

    # ------------------------------------------------------------------
    # tool selection — detail panel
    # ------------------------------------------------------------------

    def _on_tool_selected(self, event: ListView.Selected) -> None:
        tool_key = getattr(event.item, "_tool_key", None)
        if tool_key is None:
            return
        tool = self._find_tool(tool_key)
        if tool is None:
            return
        self._selected_tool_key = tool_key
        self._show_detail(tool)

    def _find_tool(self, key: str) -> ToolInfo | None:
        for t in self._catalog.get_all_tools():
            if t.key == key:
                return t
        return None

    def _show_detail(self, tool: ToolInfo) -> None:
        """Populate and reveal the bottom detail panel for the given tool."""
        status_text = _STATUS_LABEL[tool.install_status]
        managed_text = (
            "Yes — version pinned by Reactor ops" if tool.managed else "No — self-managed"
        )
        self.query_one("#detail-name", Static).update(f"[bold]{tool.name}[/bold]  {status_text}")
        self.query_one("#detail-description", Static).update(tool.description)
        version_text = tool.version if tool.version else "unversioned"
        meta_lines = [
            f"Version: {version_text}",
            f"Categories: {', '.join(tool.categories)}",
            f"Personas: {', '.join(tool.persona_tags)}",
            f"Managed: {managed_text}",
        ]
        self.query_one("#detail-meta", Static).update("\n".join(meta_lines))
        # Show/hide simulate-install button based on current status
        btn = self.query_one("#btn-simulate-install", Button)
        btn.display = tool.install_status != InstallStatus.INSTALLED
        # Reveal panel
        self.query_one("#detail-panel").remove_class("hidden")

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def action_focus_search(self) -> None:
        """Activate the search input bar."""
        search_input = self.query_one("#search-input", Input)
        search_input.remove_class("hidden")
        search_input.focus()
        self._search_active = True
        self.query_one("#sidebar").add_class("search-active")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-input":
            return
        query = event.value
        results = self._catalog.search_tools(query) if query else self._catalog.get_all_tools()
        self._populate_tool_list(results)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search-input":
            return
        self._exit_search()

    def _exit_search(self) -> None:
        """Close search bar and restore category filter."""
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        search_input.add_class("hidden")
        self._search_active = False
        self.query_one("#sidebar").remove_class("search-active")
        # Restore category filter
        if self._active_category == "All":
            self._populate_tool_list(self._catalog.get_all_tools())
        else:
            filtered = [
                t for t in self._catalog.get_all_tools() if self._active_category in t.categories
            ]
            self._populate_tool_list(filtered)

    # ------------------------------------------------------------------
    # simulate install
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-simulate-install":
            return
        if self._selected_tool_key is None:
            return
        updated = self._catalog.simulate_install(self._selected_tool_key)
        if updated is None:
            return
        # Refresh the detail panel to reflect INSTALLED status
        self._show_detail(updated)
        # Repopulate the tool list so the status badge updates
        self._repopulate_current_view()
        self.notify(f"Simulated install of {updated.name}.")

    def _repopulate_current_view(self) -> None:
        """Refresh tool list using the current active filter."""
        if self._search_active:
            query = self.query_one("#search-input", Input).value
            self._populate_tool_list(self._catalog.search_tools(query))
        elif self._active_category == "All":
            self._populate_tool_list(self._catalog.get_all_tools())
        else:
            filtered = [
                t for t in self._catalog.get_all_tools() if self._active_category in t.categories
            ]
            self._populate_tool_list(filtered)
