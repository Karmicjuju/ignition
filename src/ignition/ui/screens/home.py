from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from ignition.schemas.state import AppStateModel


class HomeScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [("q", "app.quit", "Quit")]

    DEFAULT_CSS = """
    HomeScreen {
        background: $background;
    }

    #main-content {
        padding: 1 2;
    }

    #reactor-status-panel {
        border: round $surface;
        padding: 1 2;
        height: auto;
        margin-bottom: 2;
    }

    #status-label {
        text-style: bold;
        margin-bottom: 1;
    }

    #status-label.status--ok {
        color: $success;
    }

    #status-label.status--warn {
        color: $warning;
    }

    #status-label.status--blocked {
        color: $error;
    }

    #onboarding-status {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #quick-actions {
        height: auto;
        margin-top: 1;
    }

    #quick-actions Button {
        margin-right: 2;
    }

    #activity-placeholder {
        color: $text-secondary;
        margin-top: 2;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state

    def _readiness_status(self) -> tuple[str, str]:
        if not self._state.onboarding_complete:
            return ("NEEDS ATTENTION", "status--warn")
        return ("READY", "status--ok")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        label_text, css_class = self._readiness_status()
        demo_suffix = " (Demo data)" if self._state.demo_mode else ""
        status_display = f"{label_text}{demo_suffix}"

        if self._state.onboarding_complete:
            onboarding_line = "Core systems nominal."
        else:
            onboarding_line = "Subsystem variance detected. Onboarding incomplete."

        with Vertical(id="main-content"):
            with Vertical(id="reactor-status-panel"):
                yield Static(
                    status_display,
                    id="status-label",
                    classes=css_class,
                )
                yield Static(
                    onboarding_line,
                    id="onboarding-status",
                )
                with Horizontal(id="quick-actions"):
                    yield Button(
                        "Run Diagnostics",
                        id="btn-diagnostics",
                        tooltip="Scan all subsystems for issues and report health status.",
                    )
                    yield Button(
                        "Sync Access",
                        id="btn-sync-access",
                        tooltip="Refresh AWS SSO credentials and access tokens.",
                    )
            yield Static(
                "No recent activity.",
                id="activity-placeholder",
            )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.notify("Coming in a future release.", title="Not yet available")
