from __future__ import annotations

import contextlib
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from ignition.core.auth import AuthService
from ignition.schemas.auth import AwsAuthState, ProfileType
from ignition.schemas.state import AppStateModel

_TYPE_LABEL: dict[ProfileType, str] = {
    ProfileType.SSO: "SSO",
    ProfileType.STATIC: "Static",
    ProfileType.INSTANCE: "Instance",
}


class AuthScreen(Screen[None]):
    """AWS Auth Centre screen.

    Displays detected AWS profiles, session status, and action buttons
    for Login, Refresh, Switch Profile, and Repair Config.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh_status", "Refresh"),
    ]

    DEFAULT_CSS = """
    AuthScreen {
        background: $background;
    }

    #status-bar {
        height: 3;
        padding: 0 1;
        background: $surface;
        border-bottom: tall $border;
    }

    #status-label {
        width: 1fr;
        content-align: left middle;
    }

    #session-badge {
        width: auto;
        padding: 0 2;
        content-align: center middle;
    }

    .badge-active {
        color: $success;
        text-style: bold;
    }

    .badge-unknown {
        color: $text-muted;
    }

    #profiles-container {
        height: 1fr;
        padding: 1;
    }

    #profiles-label {
        padding: 0 1 1 1;
        color: $text-secondary;
    }

    #action-bar {
        height: auto;
        padding: 1;
        align: left middle;
    }

    #action-bar Button {
        margin-right: 1;
    }

    #loading-msg {
        color: $text-secondary;
        padding: 1;
    }
    """

    _BUSY_BUTTON_IDS: ClassVar[tuple[str, ...]] = (
        "btn-login",
        "btn-refresh",
        "btn-switch",
        "btn-repair",
    )
    _BUTTON_LABELS: ClassVar[dict[str, str]] = {
        "btn-login": "Login",
        "btn-refresh": "Refresh",
        "btn-switch": "Switch Profile",
        "btn-repair": "Repair Config",
    }

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state
        self._service = AuthService()
        self._auth_state: AwsAuthState | None = None
        self._busy: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="status-bar"):
            yield Static("AWS Auth Centre", id="status-label")
            yield Static("● Unknown", id="session-badge", classes="badge-unknown")
        with Vertical(id="profiles-container"):
            yield Label("Detected profiles", id="profiles-label")
            yield Static("Loading profiles…", id="loading-msg")
            tbl: DataTable[str] = DataTable(id="profiles-table", show_cursor=True)
            tbl.display = False
            yield tbl
        with Horizontal(id="action-bar"):
            yield Button(
                "Login",
                id="btn-login",
                variant="primary",
                tooltip="Run aws sso login for the selected profile.",
            )
            yield Button(
                "Refresh",
                id="btn-refresh",
                tooltip="Refresh credentials for the selected profile.",
            )
            yield Button(
                "Switch Profile",
                id="btn-switch",
                tooltip="Set AWS_PROFILE to the selected row.",
            )
            yield Button(
                "Repair Config",
                id="btn-repair",
                variant="warning",
                tooltip="Fix ~/.aws directory permissions.",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._load_auth()

    @work
    async def _load_auth(self) -> None:
        try:
            auth_state = await self._service.load_auth_state()
            self._auth_state = auth_state
            self._render_profiles(auth_state)
            self._update_badge(auth_state)
        except Exception as exc:
            self._set_loading(f"Error loading profiles: {exc}")

    def _set_loading(self, msg: str) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#loading-msg", Static).update(msg)

    def _render_profiles(self, auth_state: AwsAuthState) -> None:
        tbl = self.query_one("#profiles-table", DataTable)
        loading = self.query_one("#loading-msg", Static)

        tbl.clear(columns=True)
        tbl.add_columns("Profile", "Type", "Region", "SSO URL")

        for profile in auth_state.profiles:
            marker = "▶ " if profile.is_active else "  "
            tbl.add_row(
                f"{marker}{profile.name}",
                _TYPE_LABEL.get(profile.type, profile.type.value),
                profile.region or "—",
                profile.sso_start_url or "—",
                key=profile.name,
            )

        if not auth_state.profiles:
            # Empty state: surface a Repair Config CTA inline rather than
            # leaving the user at a dead-end label. The action-bar Repair
            # button stays available too; this just makes the recovery
            # path obvious.
            loading.update(
                "No AWS profiles found in ~/.aws/config.\n"
                "Press the Repair Config button below to create the directory "
                "with safe permissions, then run `aws configure` to add a profile."
            )
            loading.display = True
            tbl.display = False
        else:
            loading.display = False
            tbl.display = True

    def _update_badge(self, auth_state: AwsAuthState) -> None:
        badge = self.query_one("#session-badge", Static)
        if auth_state.active_profile:
            badge.update(f"● Active — {auth_state.active_profile}")
            badge.set_classes("badge-active")
        else:
            badge.update("● No active profile")
            badge.set_classes("badge-unknown")

    def _selected_profile(self) -> str | None:
        if self._auth_state is None:
            return None
        tbl = self.query_one("#profiles-table", DataTable)
        row_key = tbl.cursor_row
        if row_key is None:
            return None
        try:
            cell = tbl.get_cell_at((row_key, 0))
            return str(cell).strip().lstrip("▶ ").strip() or None
        except Exception:
            return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        # Drop clicks while another @work is running. Without this, a user
        # can spam-queue subprocesses (aws sso login, aws configure, etc.)
        # because Textual's @work does not implicitly serialise calls.
        if self._busy:
            return
        if btn_id == "btn-login":
            self._action_login()
        elif btn_id == "btn-refresh":
            self._action_refresh()
        elif btn_id == "btn-switch":
            self._action_switch()
        elif btn_id == "btn-repair":
            self._action_repair()

    def _set_busy(self, active_id: str | None) -> None:
        """Disable all four action buttons and append "…" to the active one.
        Call with `active_id=None` to release the busy state and restore
        every button's original label.
        """
        self._busy = active_id is not None
        for btn_id in self._BUSY_BUTTON_IDS:
            try:
                btn = self.query_one(f"#{btn_id}", Button)
            except Exception:
                continue
            btn.disabled = self._busy
            base_label = self._BUTTON_LABELS[btn_id]
            btn.label = f"{base_label}…" if btn_id == active_id else base_label

    @work
    async def _action_login(self) -> None:
        profile = self._selected_profile() or (
            self._auth_state.active_profile if self._auth_state else None
        )
        if not profile:
            self.notify("Select a profile first.", severity="warning")
            return
        self._set_busy("btn-login")
        try:
            self.notify(f"Starting SSO login for {profile}…")
            success, msg = await self._service.trigger_login(profile)
            severity = "information" if success else "error"
            self.notify(msg, severity=severity)
            if success:
                await self._reload()
        finally:
            self._set_busy(None)

    @work
    async def _action_refresh(self) -> None:
        profile = self._selected_profile() or (
            self._auth_state.active_profile if self._auth_state else None
        )
        if not profile:
            self.notify("Select a profile first.", severity="warning")
            return
        self._set_busy("btn-refresh")
        try:
            self.notify(f"Refreshing credentials for {profile}…")
            success, msg = await self._service.trigger_refresh(profile)
            severity = "information" if success else "error"
            self.notify(msg, severity=severity)
            if success:
                await self._reload()
        finally:
            self._set_busy(None)

    @work
    async def _action_switch(self) -> None:
        profile = self._selected_profile()
        if not profile:
            self.notify("Select a profile row first.", severity="warning")
            return
        self._set_busy("btn-switch")
        try:
            auth_state, scope_notice = await self._service.switch_profile(profile)
            self._auth_state = auth_state
            self._render_profiles(auth_state)
            self._update_badge(auth_state)
            # `scope_notice` carries the Ignition-only caveat from core.
            # Rendered as `warning` severity so the user reads it as
            # actionable rather than informational chrome.
            self.notify(
                f"Switched to profile: {profile}\n{scope_notice}",
                severity="warning",
            )
        finally:
            self._set_busy(None)

    @work
    async def _action_repair(self) -> None:
        self._set_busy("btn-repair")
        try:
            success, msg = await self._service.repair_config()
            severity = "information" if success else "error"
            self.notify(msg, severity=severity)
        finally:
            self._set_busy(None)

    async def _reload(self) -> None:
        auth_state = await self._service.load_auth_state()
        self._auth_state = auth_state
        self._render_profiles(auth_state)
        self._update_badge(auth_state)

    def action_refresh_status(self) -> None:
        self._load_auth()
