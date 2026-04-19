from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox

from ignition.app import IgnitionApp
from ignition.core.onboarding import OnboardingService
from ignition.schemas.onboarding import PERSONAS
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.onboarding import OnboardingScreen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(*, onboarding_complete: bool = False) -> AppStateModel:
    """Build a minimal AppStateModel for unit tests."""
    return AppStateModel(install_id="test-install-id", onboarding_complete=onboarding_complete)


# ---------------------------------------------------------------------------
# Group 1 — OnboardingService unit tests (sync)
# ---------------------------------------------------------------------------


def test_get_personas_returns_all_five(isolated_paths: Path) -> None:
    service = OnboardingService()
    personas = service.get_personas()
    assert len(personas) == 5
    for persona in personas:
        assert persona.id, f"Persona {persona!r} has an empty id"
        assert persona.name, f"Persona {persona!r} has an empty name"
        assert persona.description, f"Persona {persona!r} has an empty description"
        assert persona.recommended_tools, f"Persona {persona!r} has no recommended_tools"


def test_get_recommended_tools_deduplicates(isolated_paths: Path) -> None:
    service = OnboardingService()
    tools = service.get_recommended_tools(["backend", "devops"])
    assert tools.count("git") == 1, "'git' should appear exactly once"
    assert tools.count("awscli") == 1, "'awscli' should appear exactly once"


def test_get_recommended_tools_unknown_id_ignored(isolated_paths: Path) -> None:
    service = OnboardingService()
    backend_tools = service.get_recommended_tools(["backend"])
    combined_tools = service.get_recommended_tools(["backend", "unknown_persona"])
    # Should not raise; result must equal pure backend tools
    assert combined_tools == backend_tools


def test_is_first_launch_true_when_incomplete(isolated_paths: Path) -> None:
    service = OnboardingService()
    state = _make_state(onboarding_complete=False)
    assert service.is_first_launch(state) is True


def test_is_first_launch_false_when_complete(isolated_paths: Path) -> None:
    service = OnboardingService()
    state = _make_state(onboarding_complete=True)
    assert service.is_first_launch(state) is False


def test_complete_quick_path_sets_all_fields(isolated_paths: Path) -> None:
    service = OnboardingService()
    state = _make_state(onboarding_complete=False)
    result = service.complete_quick_path(state, ["backend"])
    assert result.selected_personas == ["backend"]
    assert result.onboarding_phase == 3
    assert result.onboarding_complete is True
    assert result.accepted_tool_bundle is True


# ---------------------------------------------------------------------------
# Group 2 — OnboardingScreen async Textual pilot tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_screen_boots(isolated_paths: Path) -> None:
    """App with onboarding_complete=False should route to OnboardingScreen."""
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, OnboardingScreen)


@pytest.mark.asyncio
async def test_persona_next_button_disabled_initially(isolated_paths: Path) -> None:
    """Next → button should be disabled before any persona is selected."""
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        next_btn = app.screen.query_one("#next-btn", Button)
        assert next_btn.disabled is True


@pytest.mark.asyncio
async def test_persona_selection_enables_next(isolated_paths: Path) -> None:
    """Toggling a persona Checkbox should enable the Next → button."""
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Toggle the first persona checkbox directly via the widget API.
        first_persona_id = PERSONAS[0].id
        checkbox = app.screen.query_one(f"#persona-{first_persona_id}", Checkbox)
        checkbox.toggle()
        await pilot.pause()
        next_btn = app.screen.query_one("#next-btn", Button)
        assert next_btn.disabled is False
