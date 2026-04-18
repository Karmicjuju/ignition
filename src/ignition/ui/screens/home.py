from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ignition.schemas.state import AppStateModel


class HomeScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [("q", "app.quit", "Quit")]

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        demo_tag = " [DEMO MODE]" if self._state.demo_mode else ""
        with Middle(), Center():
            yield Static(
                f"Welcome to Ignition{demo_tag}\n\n"
                f"install_id: {self._state.install_id}\n"
                f"last launched: {self._state.last_launched_at.isoformat()}\n\n"
                "Press q to quit.",
                id="welcome",
            )
        yield Footer()
