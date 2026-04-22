from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.timer import Timer
from textual.widgets import Static

from ignition.core.activity import ActivityLog
from ignition.core.catalog import CatalogService
from ignition.core.config import load_config
from ignition.core.demo import seed_demo_state
from ignition.core.health import HealthEngine
from ignition.core.installer import InstallerEngine
from ignition.core.logging import get_logger
from ignition.core.onboarding import OnboardingService
from ignition.core.state import load_state, save_state
from ignition.core.updater import UpdateEngine
from ignition.schemas.health import HealthState
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.auth import AuthScreen
from ignition.ui.screens.catalog import ToolCatalogScreen
from ignition.ui.screens.health import HealthScreen
from ignition.ui.screens.home import HomeScreen
from ignition.ui.screens.onboarding import OnboardingComplete, OnboardingScreen
from ignition.ui.screens.settings import ScanIntervalChanged, SettingsScreen

_SCAN_INTERVAL_SECONDS: dict[str, int] = {
    "15m": 900,
    "30m": 1800,
    "60m": 3600,
}


class IgnitionApp(App[None]):
    TITLE = "Ignition"
    SUB_TITLE = "Reactor command centre"

    # NOTE: Textual does not natively support two-key chords (g t, g h, g s).
    # Using ctrl+* single bindings instead. The g-motion style belongs to a
    # future vim-mode layer.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+t", "goto_catalog", "Catalog"),
        Binding("ctrl+h", "goto_health", "Health"),
        Binding("ctrl+a", "goto_auth", "Auth"),
        Binding("ctrl+comma", "goto_settings", "Settings"),
        Binding("ctrl+l", "goto_activity", "Activity"),
        Binding("ctrl+u", "goto_updates", "Updates"),
        # Ctrl+D is registered unconditionally; action_operator_panel guards
        # against non-operator invocations at runtime.
        Binding("ctrl+d", "operator_panel", "Operator", show=False),
    ]

    DEFAULT_CSS = """
    #demo-banner {
        background: $accent;
        color: $background;
        text-align: center;
        width: 1fr;
        height: 1;
    }
    """

    def __init__(self, *, demo_mode: bool = False, operator_mode: bool = False) -> None:
        super().__init__()
        self._demo_mode = demo_mode
        self._operator_mode = operator_mode
        self._log = get_logger("ignition.app")
        self._current_state: AppStateModel | None = None
        self._activity_log = ActivityLog()
        self._scan_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        if self._demo_mode:
            yield Static(
                "⚡ DEMO MODE — no real system changes will be made",
                id="demo-banner",
            )

    def on_mount(self) -> None:
        state = load_state(demo_mode=self._demo_mode)
        if self._demo_mode:
            state = seed_demo_state(state)
            save_state(state)
        self._current_state = state
        self._log.info("app.mounted", install_id=state.install_id, demo_mode=state.demo_mode)
        if OnboardingService().is_first_launch(state):
            self.push_screen(OnboardingScreen(state))
        else:
            self.push_screen(HomeScreen(state, self._activity_log))
            self._check_updates_on_launch()

        # Start scheduled health scan timer based on config
        config = load_config()
        interval = config.health_scan_interval or "30m"
        seconds = _SCAN_INTERVAL_SECONDS.get(interval)
        if seconds is not None:
            self._scan_timer = self.set_interval(seconds, self._scheduled_health_scan)

    @work(thread=True)
    def _check_updates_on_launch(self) -> None:
        """Check for tool updates in the background after HomeScreen is shown.

        Constructs UpdateEngine, runs check_updates(), and stores the result in
        AppStateModel.available_updates and last_update_check. Saves state via
        call_from_thread to avoid touching the event loop from the worker thread.
        """
        if self._current_state is None:
            return
        try:
            catalog = CatalogService()
            installer = InstallerEngine(self._current_state, self._activity_log)
            engine = UpdateEngine(
                catalog=catalog,
                installer=installer,
                activity_log=self._activity_log,
            )
            updates = engine.check_updates()
            self._current_state.available_updates = [u.tool_key for u in updates]
            self._current_state.last_update_check = datetime.now(UTC)
            self._log.info(
                "app.update_check.complete",
                available_updates=len(updates),
            )
            self.call_from_thread(save_state, self._current_state)
        except Exception as exc:
            self._log.warning("app.update_check.failed", reason=str(exc))

    def on_onboarding_complete(self, message: OnboardingComplete) -> None:
        save_state(message.state)
        self._current_state = message.state
        self.push_screen(HomeScreen(message.state, self._activity_log))

    def action_goto_catalog(self) -> None:
        """Push the Tool Catalog screen (ctrl+t global binding)."""
        if self._current_state is None:
            return
        self.push_screen(ToolCatalogScreen(self._current_state))

    def action_goto_health(self) -> None:
        """Push the Health & Diagnostics screen (ctrl+h global binding)."""
        if self._current_state is None:
            return
        self.push_screen(HealthScreen(self._current_state))

    def action_goto_auth(self) -> None:
        """Push the AWS Auth Centre screen (ctrl+a global binding)."""
        if self._current_state is None:
            return
        self.push_screen(AuthScreen(self._current_state))

    def action_goto_settings(self) -> None:
        """Push the Settings screen (ctrl+, global binding)."""
        if self._current_state is None:
            return
        self.push_screen(SettingsScreen(self._current_state))

    def action_goto_activity(self) -> None:
        """Push the Activity Log screen (ctrl+l global binding)."""
        if self._current_state is None:
            return
        from ignition.ui.screens.activity import ActivityScreen

        self.push_screen(ActivityScreen(self._current_state, self._activity_log))

    def action_goto_updates(self) -> None:
        """Push the Updates screen (ctrl+u global binding)."""
        if self._current_state is None:
            return
        from ignition.ui.screens.updates import UpdatesScreen

        self.push_screen(UpdatesScreen(self._current_state, self._activity_log))

    def action_operator_panel(self) -> None:
        """Push the Operator Panel (ctrl+d) — only when operator_mode is active."""
        if not self._operator_mode:
            return
        if self._current_state is None:
            return
        from ignition.ui.screens.operator import OperatorPanel

        self.push_screen(OperatorPanel(self._current_state))

    @work(exclusive=False)
    async def _scheduled_health_scan(self) -> None:
        """Perform a background health scan and notify on new issues."""
        if self._current_state is None:
            return

        previous_summary = dict(self._current_state.health_summary)
        engine = HealthEngine()
        await engine.run_scan(
            previous_summary=previous_summary,
            activity_log=self._activity_log,
        )

        # Reload state to pick up changes the engine saved
        self._current_state = load_state()

        if engine.last_new_issues:
            n = len(engine.last_new_issues)
            new_values = {
                self._current_state.health_summary.get(issue.split("_")[0], "")
                for issue in engine.last_new_issues
            }
            has_manual = HealthState.MANUAL.value in new_values
            severity = "error" if has_manual else "warning"
            self.notify(
                f"{n} new health issue{'s' if n != 1 else ''} detected."
                " Open Health Centre to review.",
                title="Health Scan",
                severity=severity,
                timeout=8,
            )

        # Ask HomeScreen to refresh its badge (it will re-read state on resume)
        import contextlib

        for screen in self.screen_stack:
            if hasattr(screen, "on_screen_resume"):
                with contextlib.suppress(Exception):
                    screen.on_screen_resume()  # type: ignore[attr-defined]
                break

    def on_scan_interval_changed(self, message: ScanIntervalChanged) -> None:
        """Handle a change to the health scan interval from SettingsScreen."""
        if self._scan_timer is not None:
            self._scan_timer.stop()
            self._scan_timer = None

        seconds = _SCAN_INTERVAL_SECONDS.get(message.interval)
        if seconds is not None:
            self._scan_timer = self.set_interval(seconds, self._scheduled_health_scan)
            self._log.info(
                "app.scan_timer.restarted",
                interval=message.interval,
                seconds=seconds,
            )
        else:
            self._log.info("app.scan_timer.disabled", interval=message.interval)

    def on_unmount(self) -> None:
        self._log.info("app.unmounted")
        if self._scan_timer is not None:
            self._scan_timer.stop()
