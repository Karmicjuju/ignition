from __future__ import annotations

from ignition.core.logging import get_logger
from ignition.schemas.onboarding import PERSONAS, PersonaInfo
from ignition.schemas.state import AppStateModel


class OnboardingService:
    def __init__(self) -> None:
        self._log = get_logger("ignition.core.onboarding")

    def is_first_launch(self, state: AppStateModel) -> bool:
        """Returns True if onboarding has not been completed."""
        return not state.onboarding_complete

    def get_personas(self) -> list[PersonaInfo]:
        """Returns the full list of available personas."""
        return PERSONAS

    def get_recommended_tools(self, persona_ids: list[str]) -> list[str]:
        """Returns a deduplicated union of recommended tools for the given persona ids.

        Preserves order (first occurrence wins). Unknown persona ids are skipped.
        """
        persona_map = {p.id: p for p in PERSONAS}
        seen: set[str] = set()
        tools: list[str] = []
        for pid in persona_ids:
            persona = persona_map.get(pid)
            if persona is None:
                self._log.warning("unknown_persona_id", persona_id=pid)
                continue
            for tool in persona.recommended_tools:
                if tool not in seen:
                    seen.add(tool)
                    tools.append(tool)
        return tools

    def complete_quick_path(self, state: AppStateModel, persona_ids: list[str]) -> AppStateModel:
        """Marks onboarding complete via the quick path.

        Sets selected_personas, advances onboarding_phase to 3, marks
        onboarding_complete and accepted_tool_bundle. The caller is responsible
        for persisting the returned state via save_state().
        """
        state.selected_personas = persona_ids
        state.onboarding_phase = 3
        state.onboarding_complete = True
        state.accepted_tool_bundle = True
        self._log.info(
            "onboarding_quick_path_complete",
            personas=persona_ids,
            phase=state.onboarding_phase,
        )
        return state
