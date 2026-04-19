from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static

from ignition.core.demo import seed_demo_state
from ignition.core.logging import get_logger
from ignition.core.onboarding import OnboardingService
from ignition.core.state import load_state, save_state
from ignition.ui.screens.home import HomeScreen
from ignition.ui.screens.onboarding import OnboardingComplete, OnboardingScreen


class IgnitionApp(App[None]):
    TITLE = "Ignition"
    SUB_TITLE = "Reactor command centre"

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
        self._log.info("app.mounted", install_id=state.install_id, demo_mode=state.demo_mode)
        if OnboardingService().is_first_launch(state):
            self.push_screen(OnboardingScreen(state))
        else:
            self.push_screen(HomeScreen(state))

    def on_onboarding_complete(self, message: OnboardingComplete) -> None:
        save_state(message.state)
        self.push_screen(HomeScreen(message.state))

    def on_unmount(self) -> None:
        self._log.info("app.unmounted")
