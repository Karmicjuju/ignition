from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Static

from ignition.core.onboarding import OnboardingService
from ignition.schemas.onboarding import PERSONAS, PersonaInfo
from ignition.schemas.state import AppStateModel


class OnboardingComplete(Message):
    """Posted when the onboarding quick path is accepted and state updated."""

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self.state = state


class OnboardingScreen(Screen[None]):
    """Two-phase quick-path onboarding wizard.

    Phase 1 — Identity Calibration: multi-select persona checkboxes.
    Phase 2 — Toolchain Provisioning: read-only tool bundle review + accept.
    """

    BINDINGS: ClassVar[list[BindingType]] = [("q", "app.quit", "Quit")]

    DEFAULT_CSS = """
    OnboardingScreen {
        background: $background;
    }

    #phase-container {
        padding: 2 4;
    }

    #phase-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 2;
    }

    #phase-subtitle {
        color: $text-secondary;
        margin-bottom: 2;
    }

    #persona-list {
        margin-bottom: 2;
        border: round $surface;
        padding: 1 2;
    }

    .persona-checkbox {
        margin-bottom: 1;
    }

    #tool-review {
        border: round $surface;
        padding: 1 2;
        margin-bottom: 2;
        color: $text-primary;
    }

    #next-btn {
        dock: bottom;
        margin: 1 4;
    }

    #accept-btn {
        dock: bottom;
        margin: 1 4;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state
        self._service = OnboardingService()
        self._phase = 1
        self._selected_persona_ids: list[str] = []

    # ------------------------------------------------------------------
    # compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="phase-container"):
            yield Static("Identity Calibration", id="phase-title")
            yield Static(
                "Select one or more roles that describe your work at Reactor. "
                "Ignition will calibrate your toolchain accordingly.",
                id="phase-subtitle",
            )
            with Vertical(id="persona-list"):
                for persona in PERSONAS:
                    yield Checkbox(
                        f"{persona.name} — {persona.description}",
                        id=f"persona-{persona.id}",
                        classes="persona-checkbox",
                        tooltip=f"Activate the {persona.name} role profile.",
                    )
            # Phase 1 action button (disabled until ≥1 persona checked)
            yield Button(
                "Next →",
                id="next-btn",
                variant="primary",
                disabled=True,
                tooltip="Advance to Toolchain Provisioning once a role is selected.",
            )
            # Phase 2 widgets — hidden initially
            yield Static("", id="tool-review")
            yield Button(
                "Accept & Launch →",
                id="accept-btn",
                variant="primary",
                tooltip="Accept the recommended toolchain and initialise your Reactor workspace.",
            )
        yield Footer()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Show only phase-1 widgets on first mount."""
        self._show_phase(1)

    # ------------------------------------------------------------------
    # event handlers
    # ------------------------------------------------------------------

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Enable/disable the Next button based on persona selection."""
        if self._phase != 1:
            return
        checked_any = any(self.query_one(f"#persona-{p.id}", Checkbox).value for p in PERSONAS)
        self.query_one("#next-btn", Button).disabled = not checked_any

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next-btn":
            self._advance_to_phase_2()
        elif event.button.id == "accept-btn":
            self._complete_onboarding()

    # ------------------------------------------------------------------
    # phase transitions
    # ------------------------------------------------------------------

    def _advance_to_phase_2(self) -> None:
        """Collect selected persona ids and render the tool-bundle review."""
        self._selected_persona_ids = [
            p.id for p in PERSONAS if self.query_one(f"#persona-{p.id}", Checkbox).value
        ]
        tools = self._service.get_recommended_tools(self._selected_persona_ids)
        review_text = self._build_review_text(tools)
        self.query_one("#tool-review", Static).update(review_text)
        self._phase = 2
        self._show_phase(2)

    def _complete_onboarding(self) -> None:
        """Finalise state and post OnboardingComplete for the app to handle."""
        updated_state = self._service.complete_quick_path(self._state, self._selected_persona_ids)
        self.post_message(OnboardingComplete(updated_state))

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _show_phase(self, phase: int) -> None:
        """Toggle visibility of phase-specific widgets."""
        # Phase 1 widgets
        for persona in PERSONAS:
            self.query_one(f"#persona-{persona.id}", Checkbox).display = phase == 1
        self.query_one("#next-btn", Button).display = phase == 1
        # Phase 2 widgets
        self.query_one("#tool-review", Static).display = phase == 2
        self.query_one("#accept-btn", Button).display = phase == 2
        # Update header copy per phase
        self.query_one("#phase-title", Static).update(
            "Identity Calibration" if phase == 1 else "Toolchain Provisioning"
        )
        self.query_one("#phase-subtitle", Static).update(
            (
                "Select one or more roles that describe your work at Reactor. "
                "Ignition will calibrate your toolchain accordingly."
            )
            if phase == 1
            else (
                "Charging runtime modules… Review the recommended toolchain below. "
                "Accept to synchronise your control surfaces and launch."
            )
        )

    def _build_review_text(self, tools: list[str]) -> str:
        """Build a grouped tool-bundle summary for display in Phase 2."""
        persona_map = {p.id: p for p in PERSONAS}
        lines: list[str] = ["[bold]Recommended Toolchain[/bold]\n"]
        for pid in self._selected_persona_ids:
            persona: PersonaInfo | None = persona_map.get(pid)
            if persona is None:
                continue
            lines.append(f"[bold]{persona.name}[/bold]")
            for tool in persona.recommended_tools:
                lines.append(f"  • {tool}")
            lines.append("")
        if not tools:
            lines.append("No tools detected — subsystem variance detected.")
        return "\n".join(lines)
