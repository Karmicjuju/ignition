from __future__ import annotations

from textual.app import App

from ignition.core.logging import get_logger
from ignition.core.state import load_state
from ignition.ui.screens.home import HomeScreen


class IgnitionApp(App[None]):
    TITLE = "Ignition"
    SUB_TITLE = "Reactor command centre"

    def __init__(self, *, demo_mode: bool = False) -> None:
        super().__init__()
        self._demo_mode = demo_mode
        self._log = get_logger("ignition.app")

    def on_mount(self) -> None:
        state = load_state(demo_mode=self._demo_mode)
        self._log.info("app.mounted", install_id=state.install_id, demo_mode=state.demo_mode)
        self.push_screen(HomeScreen(state))

    def on_unmount(self) -> None:
        self._log.info("app.unmounted")
