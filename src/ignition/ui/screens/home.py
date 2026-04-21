from __future__ import annotations

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from ignition.core.activity import ActivityLog
from ignition.core.recommendations import RecommendationsEngine, Suggestion, SuggestionType
from ignition.schemas.activity import Outcome
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.catalog import ToolCatalogScreen

_OUTCOME_ICON: dict[Outcome, str] = {
    Outcome.SUCCESS: "✓",
    Outcome.FAILURE: "✗",
    Outcome.PENDING: "…",
    Outcome.CANCELLED: "-",
}

_SUGGESTION_ICON: dict[SuggestionType, str] = {
    SuggestionType.AUTH: "⚠",
    SuggestionType.HEALTH: "⚠",
    SuggestionType.INSTALL: "↑",
    SuggestionType.UPDATE: "↑",
    SuggestionType.ONBOARDING: "✓",
}

_SUGGESTION_BTN_LABEL: dict[SuggestionType, str] = {
    SuggestionType.AUTH: "Configure",
    SuggestionType.HEALTH: "Fix",
    SuggestionType.INSTALL: "Install",
    SuggestionType.UPDATE: "Update",
    SuggestionType.ONBOARDING: "Continue",
}


class HomeScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "app.quit", "Quit"),
        Binding("ctrl+u", "goto_updates", "Updates"),
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

    #recommendations-panel {
        margin-top: 2;
        margin-bottom: 2;
        height: auto;
        border: round $accent;
        padding: 1 2;
    }

    #recommendations-panel.hidden {
        display: none;
    }

    #recommendations-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .suggestion-row {
        height: auto;
        margin-bottom: 1;
        align: left middle;
    }

    .suggestion-icon {
        width: 3;
        color: $warning;
    }

    .suggestion-icon.stype-auth {
        color: $error;
    }

    .suggestion-icon.stype-health {
        color: $error;
    }

    .suggestion-icon.stype-install {
        color: $primary;
    }

    .suggestion-icon.stype-update {
        color: $warning;
    }

    .suggestion-icon.stype-onboarding {
        color: $success;
    }

    .suggestion-text {
        width: 1fr;
    }

    .suggestion-title {
        text-style: bold;
    }

    .suggestion-subtitle {
        color: $text-secondary;
    }

    .suggestion-btn {
        width: auto;
        margin-left: 2;
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

    #update-badge {
        color: $warning;
        text-style: bold;
        margin-right: 2;
        padding: 0 1;
    }

    #update-badge.hidden {
        display: none;
    }

    #btn-update-all {
        margin-right: 2;
    }

    #btn-update-all.hidden {
        display: none;
    }
    """

    def __init__(self, state: AppStateModel, activity_log: ActivityLog | None = None) -> None:
        super().__init__()
        self._state = state
        self._activity_log = activity_log or ActivityLog()
        self._recommendations_engine = RecommendationsEngine()

    def _readiness_status(self) -> tuple[str, str]:
        if not self._state.onboarding_complete:
            return ("NEEDS ATTENTION", "status--warn")
        return ("READY", "status--ok")

    def _update_count(self) -> int:
        return len(self._state.available_updates)

    def _get_suggestions(self) -> list[Suggestion]:
        from ignition.core.catalog import CatalogService

        catalog = CatalogService()
        return self._recommendations_engine.get_suggestions(
            self._state,
            catalog.get_all_tools(),
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        label_text, css_class = self._readiness_status()
        demo_suffix = " (Demo data)" if self._state.demo_mode else ""
        status_display = f"{label_text}{demo_suffix}"

        if self._state.onboarding_complete:
            onboarding_line = "Core systems nominal."
        else:
            onboarding_line = "Subsystem variance detected. Onboarding incomplete."

        suggestions = self._get_suggestions()

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
                    n = self._update_count()
                    badge_classes = "hidden" if n == 0 else ""
                    yield Static(
                        f"{n} tool{'s' if n != 1 else ''} have updates",
                        id="update-badge",
                        classes=badge_classes,
                    )
                    update_all_classes = "hidden" if n == 0 else ""
                    yield Button(
                        "Update All Tools",
                        id="btn-update-all",
                        variant="warning",
                        classes=update_all_classes,
                        tooltip="Update all tools that have newer managed versions available.",
                    )

            # Recommendations panel — hidden when no suggestions
            reco_classes = "" if suggestions else "hidden"
            with Vertical(id="recommendations-panel", classes=reco_classes):
                yield Static("Recommended for you", id="recommendations-title")
                for idx, suggestion in enumerate(suggestions):
                    icon = _SUGGESTION_ICON.get(suggestion.type, "•")
                    icon_class = f"suggestion-icon stype-{suggestion.type.value}"
                    btn_label = _SUGGESTION_BTN_LABEL.get(suggestion.type, "View")
                    with Horizontal(classes="suggestion-row", id=f"suggestion-row-{idx}"):
                        yield Static(icon, classes=icon_class)
                        with Vertical(classes="suggestion-text"):
                            yield Static(suggestion.title, classes="suggestion-title")
                            yield Static(suggestion.subtitle, classes="suggestion-subtitle")
                        yield Button(
                            btn_label,
                            id=f"btn-suggestion-{idx}",
                            variant="default",
                            classes="suggestion-btn",
                            tooltip=suggestion.title,
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
        from ignition.ui.screens.updates import UpdatesScreen

        if event.button.id == "btn-catalog":
            self.app.push_screen(ToolCatalogScreen(self._state))
            return
        if event.button.id == "btn-diagnostics":
            self.app.push_screen(HealthScreen(self._state))
            return
        if event.button.id == "btn-view-activity":
            self.app.push_screen(ActivityScreen(self._state, self._activity_log))
            return
        if event.button.id == "update-badge":
            # Retargeted: badge now goes to UpdatesScreen exclusively
            self.app.push_screen(UpdatesScreen(self._state, self._activity_log))
            return
        if event.button.id == "btn-update-all":
            self._run_update_all()
            return
        # Suggestion action buttons
        if event.button.id and event.button.id.startswith("btn-suggestion-"):
            idx_str = event.button.id[len("btn-suggestion-") :]
            try:
                idx = int(idx_str)
            except ValueError:
                return
            suggestions = self._get_suggestions()
            if 0 <= idx < len(suggestions):
                self._handle_suggestion(suggestions[idx])
            return
        self.notify("Coming in a future release.", title="Not yet available")

    def _handle_suggestion(self, suggestion: Suggestion) -> None:
        """Navigate to the appropriate screen for the given suggestion."""
        from ignition.ui.screens.auth import AuthScreen
        from ignition.ui.screens.health import HealthScreen
        from ignition.ui.screens.onboarding import OnboardingScreen
        from ignition.ui.screens.updates import UpdatesScreen

        if suggestion.type == SuggestionType.AUTH:
            self.app.push_screen(AuthScreen(self._state))
        elif suggestion.type == SuggestionType.HEALTH:
            self.app.push_screen(HealthScreen(self._state))
        elif suggestion.type == SuggestionType.INSTALL:
            self.app.push_screen(ToolCatalogScreen(self._state))
        elif suggestion.type == SuggestionType.UPDATE:
            self.app.push_screen(UpdatesScreen(self._state, self._activity_log))
        elif suggestion.type == SuggestionType.ONBOARDING:
            self.app.push_screen(OnboardingScreen(self._state))

    def action_goto_updates(self) -> None:
        """Navigate to UpdatesScreen via Ctrl+U."""
        from ignition.ui.screens.updates import UpdatesScreen

        self.app.push_screen(UpdatesScreen(self._state, self._activity_log))

    @work(exclusive=True)
    async def _run_update_all(self) -> None:
        """Update all outdated tools sequentially in a background worker."""
        from ignition.core.catalog import CatalogService
        from ignition.core.installer import InstallerEngine
        from ignition.core.updater import UpdateEngine

        catalog = CatalogService()
        installer = InstallerEngine(self._state, self._activity_log)
        engine = UpdateEngine(
            catalog=catalog,
            installer=installer,
            activity_log=self._activity_log,
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
        # Refresh the state reference so available_updates reflects the new state
        from ignition.core.state import save_state

        self._state.available_updates = []
        save_state(self._state)
        # Hide badge and button now that update is done
        try:
            self.query_one("#update-badge").add_class("hidden")
            self.query_one("#btn-update-all").add_class("hidden")
        except Exception:
            pass
