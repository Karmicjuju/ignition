from __future__ import annotations

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from ignition.core.catalog import CatalogService
from ignition.core.health import HealthEngine
from ignition.core.installer import InstallerEngine, InstallResult
from ignition.core.state import save_state
from ignition.schemas.catalog import InstallStatus, ToolInfo
from ignition.schemas.state import AppStateModel

# g t chord is not natively supported in Textual; using ctrl+t instead.
# Vim-style g t chord is deferred to a future vim-mode layer.
_STATUS_CLASS: dict[InstallStatus, str] = {
    InstallStatus.INSTALLED: "status-installed",
    InstallStatus.OUTDATED: "status-outdated",
    InstallStatus.MISSING: "status-missing",
    InstallStatus.UNMANAGED: "status-unmanaged",
    InstallStatus.FAILED: "status-failed",
}

_STATUS_LABEL: dict[InstallStatus, str] = {
    InstallStatus.INSTALLED: "Installed",
    InstallStatus.OUTDATED: "Outdated",
    InstallStatus.MISSING: "Missing",
    InstallStatus.UNMANAGED: "Unmanaged",
    InstallStatus.FAILED: "Failed",
}


class ToolCatalogScreen(Screen[None]):
    """Tool catalog browser with category sidebar, tool list, and detail panel.

    Allows browsing, searching, and installing tools. Install operations run in
    a background worker and report progress via a Static widget in the detail panel.
    """

    class CatalogRefreshed(Message):
        """Posted when the background remote fetch succeeds and new tool data is available."""

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

    .status-failed {
        color: $error;
        text-style: bold;
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

    #install-progress {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #install-progress.hidden {
        display: none;
    }

    #btn-install {
        margin-top: 1;
    }

    #btn-update-tool {
        margin-top: 1;
        margin-left: 1;
    }

    #btn-update-all {
        margin-left: 2;
    }

    #btn-update-all.hidden {
        display: none;
    }

    #update-available-tag {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }

    #update-available-tag.hidden {
        display: none;
    }

    #conflict-note {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #conflict-note.hidden {
        display: none;
    }
    """

    filter_outdated: reactive[bool] = reactive(False)

    def __init__(self, state: AppStateModel, filter_outdated: bool = False) -> None:
        super().__init__()
        self._state = state
        self._catalog = CatalogService()
        self._installer = InstallerEngine(state)
        self._health = HealthEngine()
        self._selected_tool_key: str | None = None
        self._active_category: str = "All"
        self._search_active: bool = False
        self._install_in_progress: bool = False
        self.filter_outdated = filter_outdated

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
                has_updates = bool(self._state.available_updates) or self.filter_outdated
                update_all_classes = "" if has_updates else "hidden"
                yield Button(
                    "Update All",
                    id="btn-update-all",
                    variant="warning",
                    classes=update_all_classes,
                    tooltip="Update all tools that have newer managed versions available.",
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
                yield Static("", id="update-available-tag", classes="hidden")
                yield Static("", id="conflict-note", classes="hidden")
                yield Static("", id="install-progress", classes="hidden")
                with Horizontal():
                    yield Button(
                        "Install",
                        id="btn-install",
                        variant="primary",
                        tooltip="Install this tool on the current system.",
                    )
                    yield Button(
                        "Update",
                        id="btn-update-tool",
                        variant="warning",
                        tooltip="Update this tool to the latest managed version.",
                        disabled=False,
                    )
        yield Footer()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate category list and tool list after mount, then refresh from remote."""
        self._refresh_category_list()
        if self.filter_outdated:
            outdated = self._get_outdated_tools()
            self._populate_tool_list(outdated)
        else:
            self._populate_tool_list(self._catalog.get_all_tools())
        self._background_refresh()
        # Hide the per-tool update button until a tool is selected
        import contextlib

        with contextlib.suppress(Exception):
            self.query_one("#btn-update-tool", Button).display = False

    # ------------------------------------------------------------------
    # background remote refresh
    # ------------------------------------------------------------------

    @work(thread=True)
    def _background_refresh(self) -> None:
        """Attempt a remote catalog fetch in a background thread.

        Posts CatalogRefreshed if new data was returned so the UI can
        repopulate without blocking the event loop.
        """
        refreshed = self._catalog.refresh_from_remote()
        if refreshed:
            self.post_message(self.CatalogRefreshed())

    def on_catalog_refreshed(self, event: CatalogRefreshed) -> None:
        """Repopulate the screen when the background refresh delivers new data."""
        self._refresh_category_list()
        if self.filter_outdated:
            self._populate_tool_list(self._get_outdated_tools())
        else:
            self._populate_tool_list(self._catalog.get_all_tools())
        self.notify("Catalog updated from remote.")

    # ------------------------------------------------------------------
    # outdated helpers
    # ------------------------------------------------------------------

    def _get_outdated_tools(self) -> list[ToolInfo]:
        """Return tools with install_status == OUTDATED or with a newer managed_version."""
        from packaging.version import Version

        result: list[ToolInfo] = []
        for tool in self._catalog.get_all_tools():
            if tool.install_status == InstallStatus.OUTDATED:
                result.append(tool)
                continue
            if tool.version_policy == "flexible":
                continue
            if tool.install_status != InstallStatus.INSTALLED:
                continue
            if tool.version is None or tool.managed_version is None:
                continue
            try:
                if Version(tool.version) < Version(tool.managed_version):
                    result.append(tool)
            except Exception:
                pass
        return result

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
            status_class = _STATUS_CLASS.get(tool.install_status, "status-missing")
            status_text = _STATUS_LABEL.get(tool.install_status, "Unknown")
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
        from packaging.version import Version

        status_text = _STATUS_LABEL.get(tool.install_status, "Unknown")
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

        # Update available tag
        update_tag = self.query_one("#update-available-tag", Static)
        is_outdated = False
        if (
            tool.version_policy != "flexible"
            and tool.version is not None
            and tool.managed_version is not None
        ):
            try:
                is_outdated = Version(tool.version) < Version(tool.managed_version)
            except Exception:
                is_outdated = False
        if is_outdated and tool.managed_version:
            update_tag.update(f"Update available: {tool.version} -> {tool.managed_version}")
            update_tag.remove_class("hidden")
        else:
            update_tag.update("")
            update_tag.add_class("hidden")

        # Conflict resolution note — shown when multiple active personas tag this tool
        conflict_note = self.query_one("#conflict-note", Static)
        active_personas = self._state.selected_personas
        tagging_personas = [p for p in tool.persona_tags if p in active_personas]
        if len(tagging_personas) > 1 and tool.managed_version:
            conflict_note.update(
                f"Version governed by: {tagging_personas[0]} persona ({tool.managed_version})"
            )
            conflict_note.remove_class("hidden")
        else:
            conflict_note.update("")
            conflict_note.add_class("hidden")

        # Configure install button based on current status
        btn = self.query_one("#btn-install", Button)
        if tool.install_status == InstallStatus.INSTALLED:
            btn.label = "Installed"
            btn.disabled = True
            btn.display = False
        elif tool.install_status == InstallStatus.FAILED:
            btn.label = "Failed — Retry"
            btn.disabled = False
            btn.display = True
        else:
            btn.label = "Install"
            btn.disabled = False
            btn.display = True

        # Configure per-tool update button
        update_btn = self.query_one("#btn-update-tool", Button)
        if is_outdated and tool.install_status == InstallStatus.INSTALLED:
            update_btn.display = True
            update_btn.disabled = False
        else:
            update_btn.display = False

        # Hide progress widget when showing a new tool
        progress = self.query_one("#install-progress", Static)
        progress.add_class("hidden")
        progress.update("")

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
    # install
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-update-all":
            self._run_update_all()
            return
        if event.button.id == "btn-update-tool":
            if self._selected_tool_key is not None:
                self._run_update_tool(self._selected_tool_key)
            return
        if event.button.id != "btn-install":
            return
        if self._selected_tool_key is None:
            return
        if self._install_in_progress:
            return
        tool = self._find_tool(self._selected_tool_key)
        if tool is None:
            return
        self._run_install(tool)

    @work(exclusive=True)
    async def _run_update_all(self) -> None:
        """Update all outdated tools via UpdateEngine."""
        from ignition.core.updater import UpdateEngine

        engine = UpdateEngine(
            catalog=self._catalog,
            installer=self._installer,
        )
        self.notify("Updating all tools…", title="Updates")
        results = await engine.update_all()
        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        if failed == 0:
            self.notify(f"All {succeeded} tool(s) updated.", title="Updates")
        else:
            self.notify(
                f"{succeeded} updated, {failed} failed.",
                severity="warning",
                title="Updates",
            )
        self._repopulate_current_view()
        # Hide "Update All" button if no more updates
        if not self._get_outdated_tools():
            import contextlib

            with contextlib.suppress(Exception):
                self.query_one("#btn-update-all", Button).add_class("hidden")

    @work(exclusive=False)
    async def _run_update_tool(self, tool_key: str) -> None:
        """Update a single tool via UpdateEngine."""
        from ignition.core.updater import UpdateEngine

        engine = UpdateEngine(
            catalog=self._catalog,
            installer=self._installer,
        )
        result = await engine.update_tool(tool_key)
        if result.success:
            tool = self._find_tool(tool_key)
            if tool and result.detected_version:
                self._catalog.mark_installed(tool_key, version=result.detected_version)
            from ignition.core.state import save_state

            save_state(self._state)
            self.notify(f"{tool_key} updated successfully.", title="Update")
        else:
            self.notify(
                f"{tool_key}: {result.error or 'Update failed.'}",
                severity="error",
                title="Update",
            )
        self._repopulate_current_view()

    @work(exclusive=False)
    async def _run_install(self, tool: ToolInfo) -> None:
        """Run the installer in an async worker and update UI on completion."""
        self._install_in_progress = True
        btn = self.query_one("#btn-install", Button)
        btn.label = "Installing…"
        btn.disabled = True

        progress = self.query_one("#install-progress", Static)
        progress.remove_class("hidden")

        def _on_progress(msg: str) -> None:
            self.call_from_thread(progress.update, msg)

        result: InstallResult = await self._installer.install(tool, progress_cb=_on_progress)

        if result.success:
            self._catalog.mark_installed(tool.key, version=result.detected_version)
            save_state(self._state)
            btn.label = "Installed"
            btn.disabled = True
            btn.display = False
            self.notify(f"{tool.name} installed successfully.")
        else:
            self._catalog.mark_failed(tool.key)
            save_state(self._state)
            btn.label = "Failed — Retry"
            btn.disabled = False
            error_msg = result.error or "Installation failed."
            self.notify(f"{tool.name}: {error_msg}", severity="error")

        self._install_in_progress = False

        # Refresh tool list so status badge updates
        self._repopulate_current_view()

        # Trigger post-install health re-check in background
        self._post_install_health_check()

    @work(thread=True)
    def _post_install_health_check(self) -> None:
        """Re-run the tools health scan after an install completes."""
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._health.run_scan(categories=["tools"]))
        finally:
            loop.close()
        self._repopulate_current_view()

    def _repopulate_current_view(self) -> None:
        """Refresh tool list using the current active filter."""
        if self._search_active:
            query = self.query_one("#search-input", Input).value
            self._populate_tool_list(self._catalog.search_tools(query))
        elif self.filter_outdated:
            self._populate_tool_list(self._get_outdated_tools())
        elif self._active_category == "All":
            self._populate_tool_list(self._catalog.get_all_tools())
        else:
            filtered = [
                t for t in self._catalog.get_all_tools() if self._active_category in t.categories
            ]
            self._populate_tool_list(filtered)
