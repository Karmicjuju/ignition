from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, ListItem, ListView, Static

from ignition.core.catalog import CatalogService
from ignition.core.onboarding import OnboardingService
from ignition.schemas.onboarding import PERSONAS, PersonaInfo
from ignition.schemas.state import AppStateModel


class OnboardingComplete(Message):
    """Posted when the onboarding quick path is accepted and state updated."""

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self.state = state


class OnboardingScreen(Screen[None]):
    """Multi-phase onboarding wizard.

    Phase 1  — Identity Calibration: multi-select persona checkboxes.
    Phase 2a — Toolchain Provisioning: read-only tool bundle review + accept / customise.
    Phase 2b (internal _phase=3) — Custom Tool Selection: scrollable checklist; all
             recommended tools pre-checked; user may uncheck or add others.
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

    #custom-tool-list {
        border: round $surface;
        padding: 1 2;
        margin-bottom: 2;
        height: 1fr;
    }

    .custom-tool-checkbox {
        margin-bottom: 0;
    }

    #next-btn {
        dock: bottom;
        margin: 1 4;
    }

    #accept-btn {
        dock: bottom;
        margin: 1 4;
    }

    #customise-btn {
        margin-top: 1;
        margin-right: 1;
    }

    #custom-accept-btn {
        dock: bottom;
        margin: 1 4;
    }

    #phase2a-actions {
        layout: horizontal;
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state
        self._service = OnboardingService()
        self._catalog = CatalogService()
        self._phase = 1
        self._selected_persona_ids: list[str] = []
        # Tracks the tool keys selected in Phase 2b (set when 2b is accepted)
        self._custom_tool_keys: list[str] | None = None

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
            # Phase 2a widgets — hidden initially
            yield Static("", id="tool-review")
            with Vertical(id="phase2a-actions"):
                yield Button(
                    "Customise",
                    id="customise-btn",
                    variant="default",
                    tooltip="Manually select which tools to install.",
                )
                yield Button(
                    "Accept & Launch →",
                    id="accept-btn",
                    variant="primary",
                    tooltip="Accept the recommended toolchain and launch.",
                )
            # Phase 2b widgets — hidden initially
            yield ListView(id="custom-tool-list")
            yield Button(
                "Accept custom selection →",
                id="btn-custom-accept",
                variant="primary",
                tooltip="Accept your custom tool selection and launch.",
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
        elif event.button.id == "customise-btn":
            self._advance_to_phase_2b()
        elif event.button.id == "btn-custom-accept":
            self._complete_onboarding_custom()

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

    def _advance_to_phase_2b(self) -> None:
        """Transition to Phase 2b: populate the custom tool checklist."""
        recommended_keys = set(self._service.get_recommended_tools(self._selected_persona_ids))
        all_tools = self._catalog.get_all_tools()

        custom_list = self.query_one("#custom-tool-list", ListView)
        custom_list.clear()

        for tool in all_tools:
            pre_checked = tool.key in recommended_keys
            cb = Checkbox(
                tool.name,
                value=pre_checked,
                id=f"custom-tool-{tool.key}",
                classes="custom-tool-checkbox",
                tooltip=tool.description,
            )
            item = ListItem(cb)
            item._tool_key = tool.key  # type: ignore[attr-defined]
            custom_list.append(item)

        self._phase = 3
        self._show_phase(3)

    def _complete_onboarding(self) -> None:
        """Finalise state via quick path and post OnboardingComplete."""
        updated_state = self._service.complete_quick_path(self._state, self._selected_persona_ids)
        self.post_message(OnboardingComplete(updated_state))

    def _complete_onboarding_custom(self) -> None:
        """Collect custom selection and post OnboardingComplete with chosen tool keys."""
        all_tools = self._catalog.get_all_tools()
        selected_keys: list[str] = []
        for tool in all_tools:
            cb_id = f"custom-tool-{tool.key}"
            try:
                cb = self.query_one(f"#{cb_id}", Checkbox)
                if cb.value:
                    selected_keys.append(tool.key)
            except Exception as exc:
                self._log.warning("onboarding.custom_keys.error", exc_info=exc)

        self._custom_tool_keys = selected_keys
        # complete_quick_path records personas; custom tool keys go on state directly
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
        # Phase 2a widgets
        self.query_one("#tool-review", Static).display = phase == 2
        self.query_one("#phase2a-actions").display = phase == 2
        # Phase 2b widgets
        self.query_one("#custom-tool-list", ListView).display = phase == 3
        self.query_one("#btn-custom-accept", Button).display = phase == 3
        # Update header copy per phase
        phase_titles = {
            1: "Identity Calibration",
            2: "Toolchain Provisioning",
            3: "Custom Tool Selection",
        }
        phase_subtitles = {
            1: (
                "Select one or more roles that describe your work at Reactor. "
                "Ignition will calibrate your toolchain accordingly."
            ),
            2: (
                "Charging runtime modules… Review the recommended toolchain below. "
                "Accept to synchronise your control surfaces and launch."
            ),
            3: (
                "Customise your tool selection. Recommended tools are pre-checked. "
                "Uncheck any you don't need or add others from the full catalog."
            ),
        }
        self.query_one("#phase-title", Static).update(phase_titles.get(phase, ""))
        self.query_one("#phase-subtitle", Static).update(phase_subtitles.get(phase, ""))

    def _build_review_text(self, tools: list[str]) -> str:
        """Build a grouped tool-bundle summary for display in Phase 2a."""
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
