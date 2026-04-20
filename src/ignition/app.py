from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Static

from ignition.core.demo import seed_demo_state
from ignition.core.logging import get_logger
from ignition.core.onboarding import OnboardingService
from ignition.core.state import load_state, save_state
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.auth import AuthScreen
from ignition.ui.screens.catalog import ToolCatalogScreen
from ignition.ui.screens.health import HealthScreen
from ignition.ui.screens.home import HomeScreen
from ignition.ui.screens.onboarding import OnboardingComplete, OnboardingScreen
from ignition.ui.screens.settings import SettingsScreen


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

    def __init__(self, *, demo_mode: bool = False) -> None:
        super().__init__()
        self._demo_mode = demo_mode
        self._log = get_logger("ignition.app")
        self._current_state: AppStateModel | None = None

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
            self.push_screen(HomeScreen(state))

    def on_onboarding_complete(self, message: OnboardingComplete) -> None:
        save_state(message.state)
        self._current_state = message.state
        self.push_screen(HomeScreen(message.state))

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

    def on_unmount(self) -> None:
        self._log.info("app.unmounted")
