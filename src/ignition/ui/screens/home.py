from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from ignition.core.activity import ActivityLog
from ignition.schemas.activity import Outcome
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.catalog import ToolCatalogScreen

_OUTCOME_ICON: dict[Outcome, str] = {
    Outcome.SUCCESS: "✓",
    Outcome.FAILURE: "✗",
    Outcome.PENDING: "…",
    Outcome.CANCELLED: "-",
}


class HomeScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "app.quit", "Quit"),
    ]

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

    #recent-activity {
        margin-top: 2;
        height: auto;
    }

    #recent-activity-label {
        color: $text-secondary;
        text-style: bold;
        margin-bottom: 1;
    }

    .activity-row {
        color: $text;
        padding: 0 1;
    }

    #activity-empty {
        color: $text-secondary;
    }

    #btn-view-activity {
        margin-top: 1;
    }
    """

    def __init__(self, state: AppStateModel, activity_log: ActivityLog | None = None) -> None:
        super().__init__()
        self._state = state
        self._activity_log = activity_log or ActivityLog()

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
                    yield Button(
                        "Tool Catalog",
                        id="btn-catalog",
                        tooltip="Browse, search, and provision tools for your Reactor workspace.",
                    )
            with Vertical(id="recent-activity"):
                yield Static("Recent activity", id="recent-activity-label")
                recent = self._activity_log.get_recent(5)
                if recent:
                    for event in reversed(recent):
                        icon = _OUTCOME_ICON.get(event.outcome, "?")
                        ts = event.timestamp.strftime("%H:%M")
                        label = event.event_type.value.replace("_", " ")
                        yield Static(
                            f"{icon} {ts}  {event.summary}  [{label}]",
                            classes="activity-row",
                        )
                    yield Button(
                        "View all →",
                        id="btn-view-activity",
                        variant="default",
                        tooltip="Open the full Activity Log.",
                    )
                else:
                    yield Static("No recent activity.", id="activity-empty")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from ignition.ui.screens.activity import ActivityScreen
        from ignition.ui.screens.health import HealthScreen

        if event.button.id == "btn-catalog":
            self.app.push_screen(ToolCatalogScreen(self._state))
            return
        if event.button.id == "btn-diagnostics":
            self.app.push_screen(HealthScreen(self._state))
            return
        if event.button.id == "btn-view-activity":
            self.app.push_screen(ActivityScreen(self._state, self._activity_log))
            return
        self.notify("Coming in a future release.", title="Not yet available")
