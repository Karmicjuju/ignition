from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from ignition.core.activity import ActivityLog
from ignition.core.catalog import CatalogService
from ignition.core.self_updater import SelfUpdateInfo, SelfUpdater
from ignition.core.state import save_state
from ignition.core.updater import UpdateEngine
from ignition.schemas.catalog import ToolInfo
from ignition.schemas.state import AppStateModel


class UpdatesScreen(Screen[None]):
    """Dedicated update management screen.

    Shows all tools that have updates available, grouped with name, version delta,
    governance tier badge, and per-tool Update button. Inline progress feedback
    replaces the Update button during an active update.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+u", "app.pop_screen", "Updates", show=False),
    ]

    DEFAULT_CSS = """
    UpdatesScreen {
        background: $background;
    }

    #updates-container {
        padding: 1 2;
        height: 1fr;
    }

    #updates-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        padding-bottom: 1;
        border-bottom: solid $surface;
    }

    #ignition-section {
        height: auto;
        margin-bottom: 2;
        border: round $surface;
        padding: 1 2;
    }

    #ignition-section-header {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #ignition-version-row {
        height: auto;
        align: left middle;
        margin-bottom: 1;
    }

    #ignition-version-status {
        color: $text-secondary;
        width: 1fr;
    }

    #btn-self-upgrade {
        width: auto;
    }

    #self-upgrade-done {
        color: $success;
    }

    #toolbar {
        height: auto;
        margin-bottom: 1;
        align: left middle;
    }

    #btn-update-all-managed {
        margin-right: 2;
    }

    #last-checked {
        color: $text-secondary;
    }

    #tool-rows {
        height: 1fr;
    }

    .update-row {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: round $surface;
        align: left middle;
    }

    .update-tool-name {
        text-style: bold;
        width: 18;
    }

    .update-version-delta {
        color: $warning;
        width: 24;
    }

    .update-tier-badge {
        width: 12;
    }

    .tier-managed {
        color: $success;
        text-style: bold;
    }

    .tier-optional {
        color: $text-secondary;
    }

    .update-progress {
        color: $text-secondary;
        width: 1fr;
    }

    .update-progress.hidden {
        display: none;
    }

    .btn-update-tool {
        width: auto;
    }

    #empty-state {
        align: center middle;
        height: 1fr;
    }

    #empty-message {
        text-align: center;
        color: $success;
        text-style: bold;
    }

    #empty-timestamp {
        text-align: center;
        color: $text-secondary;
        margin-top: 1;
    }
    """

    available_updates: reactive[list[ToolInfo]] = reactive(list, always_update=True)

    def __init__(
        self,
        state: AppStateModel,
        activity_log: ActivityLog | None = None,
    ) -> None:
        super().__init__()
        self._state = state
        self._activity_log = activity_log or ActivityLog()
        self._catalog = CatalogService()
        self._installer: object | None = None  # lazily created to avoid import at module level
        self._updating: set[str] = set()  # tool keys currently being updated

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="updates-container"):
            yield Static("Updates", id="updates-title")

            # --- Ignition self-update section ---
            with Vertical(id="ignition-section"):
                yield Static("Ignition", id="ignition-section-header")
                with Horizontal(id="ignition-version-row"):
                    yield Static(
                        "Checking for updates…",
                        id="ignition-version-status",
                    )
                    yield Button(
                        "Upgrade Ignition",
                        id="btn-self-upgrade",
                        variant="warning",
                        tooltip="Upgrade Ignition to the latest version via pipx.",
                    )

            with Horizontal(id="toolbar"):
                yield Button(
                    "Update all managed",
                    id="btn-update-all-managed",
                    variant="warning",
                    tooltip="Update all tools governed by the managed version policy.",
                )
                last_check = self._state.last_update_check
                if last_check is not None:
                    ts = last_check.strftime("%Y-%m-%d %H:%M")
                    checked_text = f"Last checked: {ts}"
                else:
                    checked_text = "Not yet checked"
                yield Static(checked_text, id="last-checked")
            with Vertical(id="tool-rows"):
                pass  # populated in on_mount
            with Vertical(id="empty-state"):
                yield Static("All tools are up to date ✓", id="empty-message")
                last_check2 = self._state.last_update_check
                if last_check2 is not None:
                    ts2 = last_check2.strftime("%Y-%m-%d %H:%M")
                    ts_text = f"Last checked: {ts2}"
                else:
                    ts_text = "Run a check to see update status."
                yield Static(ts_text, id="empty-timestamp")
        yield Footer()

    def on_mount(self) -> None:
        """Populate tool rows and set update-all button state after mount."""
        # Hide the upgrade button until the check resolves
        with contextlib.suppress(Exception):
            self.query_one("#btn-self-upgrade", Button).display = False
        self._refresh_view()
        self._check_self_update()

    # ------------------------------------------------------------------
    # view population
    # ------------------------------------------------------------------

    def _refresh_view(self) -> None:
        """Rebuild tool rows from the current catalog state."""
        from packaging.version import Version

        rows_container = self.query_one("#tool-rows", Vertical)
        rows_container.remove_children()

        outdated: list[ToolInfo] = []
        for tool in self._catalog.get_all_tools():
            if tool.version_policy == "flexible":
                continue
            if tool.version is None or tool.managed_version is None:
                continue
            try:
                if Version(tool.version) < Version(tool.managed_version):
                    outdated.append(tool)
            except Exception:
                continue

        if outdated:
            for tool in outdated:
                rows_container.mount(self._make_tool_row(tool))
            self.query_one("#empty-state").display = False
            self.query_one("#tool-rows").display = True
        else:
            self.query_one("#empty-state").display = True
            self.query_one("#tool-rows").display = False

        # Enable/disable update-all button based on managed outdated tools
        has_managed = any(t for t in outdated if t.version_policy != "flexible" and t.managed)
        btn = self.query_one("#btn-update-all-managed", Button)
        btn.disabled = not has_managed

    def _make_tool_row(self, tool: ToolInfo) -> Horizontal:
        """Build a single update row widget for the given tool."""
        installed = tool.version or "?"
        available = tool.managed_version or "?"
        version_delta = f"{installed} → {available}"

        tier_label = "Managed" if tool.managed else "Optional"
        tier_class = "tier-managed" if tool.managed else "tier-optional"

        row = Horizontal(
            Static(tool.name, classes="update-tool-name"),
            Static(version_delta, classes="update-version-delta"),
            Static(tier_label, classes=f"update-tier-badge {tier_class}"),
            Static("", classes="update-progress hidden", id=f"progress-{tool.key}"),
            Button(
                "Update",
                id=f"btn-update-{tool.key}",
                variant="warning",
                classes="btn-update-tool",
                tooltip=f"Update {tool.name} from {installed} to {available}.",
            ),
            classes="update-row",
            id=f"row-{tool.key}",
        )
        return row

    # ------------------------------------------------------------------
    # button handler
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "btn-self-upgrade":
            self._run_self_upgrade()
            return
        if btn_id == "btn-update-all-managed":
            self._run_update_all()
            return
        if btn_id.startswith("btn-update-"):
            tool_key = btn_id[len("btn-update-") :]
            if tool_key not in self._updating:
                self._run_update_tool(tool_key)

    # ------------------------------------------------------------------
    # update workers
    # ------------------------------------------------------------------

    @work(exclusive=True)
    async def _run_update_all(self) -> None:
        """Update all managed outdated tools sequentially."""
        from ignition.core.installer import InstallerEngine

        catalog = self._catalog
        installer = InstallerEngine(self._state, self._activity_log)
        engine = UpdateEngine(
            catalog=catalog,
            installer=installer,
            activity_log=self._activity_log,
        )
        # Disable update-all button during run
        with contextlib.suppress(Exception):
            self.query_one("#btn-update-all-managed", Button).disabled = True

        self.notify("Updating all managed tools…", title="Updates")

        def _progress(tool_key: str, status: str) -> None:
            self.call_from_thread(self._on_tool_progress, tool_key, status)

        results = await engine.update_all(progress_cb=_progress)
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

        from ignition.core.state import save_state

        self._state.available_updates = []
        save_state(self._state)
        self._refresh_view()

    @work(exclusive=False)
    async def _run_update_tool(self, tool_key: str) -> None:
        """Update a single tool with inline progress feedback."""
        from ignition.core.installer import InstallerEngine

        self._updating.add(tool_key)

        # Switch button for progress widget
        try:
            self.query_one(f"#btn-update-{tool_key}", Button).display = False
            progress = self.query_one(f"#progress-{tool_key}", Static)
            progress.remove_class("hidden")
            progress.update("Updating…")
        except Exception:
            pass

        installer = InstallerEngine(self._state, self._activity_log)
        engine = UpdateEngine(
            catalog=self._catalog,
            installer=installer,
            activity_log=self._activity_log,
        )
        result = await engine.update_tool(tool_key)

        if result.success:
            self.notify(f"{tool_key} updated.", title="Update")
        else:
            self.notify(
                f"{tool_key}: {result.error or 'Update failed.'}",
                severity="error",
                title="Update",
            )

        from ignition.core.state import save_state

        # Update available_updates list
        if tool_key in self._state.available_updates:
            self._state.available_updates.remove(tool_key)
        save_state(self._state)

        self._updating.discard(tool_key)
        self._refresh_view()

    def _on_tool_progress(self, tool_key: str, status: str) -> None:
        """Update inline progress text for a tool row."""
        try:
            progress = self.query_one(f"#progress-{tool_key}", Static)
            progress.update(f"{status}…")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # self-update workers
    # ------------------------------------------------------------------

    @work(exclusive=False)
    async def _check_self_update(self) -> None:
        """Check PyPI for a newer version of Ignition and update the UI."""
        updater = SelfUpdater(self._activity_log)
        info: SelfUpdateInfo | None = await updater.check()

        # Persist check result to state
        self._state.last_ignition_update_check = datetime.now(UTC)
        self._state.ignition_available_version = info.available_version if info else None
        save_state(self._state)

        with contextlib.suppress(Exception):
            status_widget = self.query_one("#ignition-version-status", Static)
            btn = self.query_one("#btn-self-upgrade", Button)
            if info is None:
                status_widget.update("Ignition is up to date")
                btn.display = False
            else:
                status_widget.update(
                    f"Version {info.available_version} available (current: {info.current_version})"
                )
                btn.display = True

    @work(exclusive=True)
    async def _run_self_upgrade(self) -> None:
        """Run pipx upgrade ignition and report the result."""
        # Disable the button while upgrading
        with contextlib.suppress(Exception):
            self.query_one("#btn-self-upgrade", Button).disabled = True
        with contextlib.suppress(Exception):
            self.query_one("#ignition-version-status", Static).update("Upgrading Ignition…")

        updater = SelfUpdater(self._activity_log)
        success, output = await updater.upgrade()

        if success:
            # Replace button with a done message
            with contextlib.suppress(Exception):
                btn = self.query_one("#btn-self-upgrade", Button)
                btn.display = False
            with contextlib.suppress(Exception):
                self.query_one("#ignition-version-status", Static).update(
                    "Restart required — quit and relaunch Ignition to use the new version."
                )
            self.app.notify(
                "Ignition upgraded. Restart to apply changes.",
                title="Ignition Updated",
            )
        else:
            with contextlib.suppress(Exception):
                self.query_one("#btn-self-upgrade", Button).disabled = False
            self.app.notify(
                f"Upgrade failed: {output[:100]}. Try: pipx upgrade ignition",
                severity="error",
                title="Ignition Upgrade Failed",
            )
