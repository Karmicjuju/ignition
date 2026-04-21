"""Tests for Phase 2b — Custom Tool Selection onboarding path.

Covers:
- "Customise" button visible in Phase 2a
- Phase 2b shows all recommended tools pre-checked
- Unchecking a recommended tool excludes it from the accepted list
- Checking an additional tool includes it
- btn-custom-accept triggers OnboardingComplete with onboarding_complete=True
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, ListView

from ignition.app import IgnitionApp
from ignition.core.catalog import CatalogService
from ignition.schemas.onboarding import PERSONAS
from ignition.ui.screens.onboarding import OnboardingComplete, OnboardingScreen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _reach_phase_2a(pilot: object, app: IgnitionApp) -> OnboardingScreen:  # type: ignore[type-arg]
    """Select the first persona and advance to Phase 2a via direct method call.

    Uses screen._advance_to_phase_2() directly to avoid OutOfBounds from
    pilot.click() on docked buttons (known pattern from prior test runs).
    """
    await pilot.pause()  # type: ignore[attr-defined]
    first_persona_id = PERSONAS[0].id
    screen: OnboardingScreen = app.screen  # type: ignore[assignment]
    checkbox = screen.query_one(f"#persona-{first_persona_id}", Checkbox)
    checkbox.toggle()
    await pilot.pause()  # type: ignore[attr-defined]
    # Direct call avoids pilot.click() OutOfBounds on docked Next button
    screen._advance_to_phase_2()
    await pilot.pause()  # type: ignore[attr-defined]
    return screen


async def _reach_phase_2b(pilot: object, app: IgnitionApp) -> OnboardingScreen:  # type: ignore[type-arg]
    """Advance from Phase 1 → Phase 2a → Phase 2b via direct method calls."""
    screen = await _reach_phase_2a(pilot, app)
    screen._advance_to_phase_2b()
    await pilot.pause()  # type: ignore[attr-defined]
    return screen


# ---------------------------------------------------------------------------
# test_customise_button_visible_in_phase_2a
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_customise_button_visible_in_phase_2a(isolated_paths: Path) -> None:
    """After advancing to Phase 2a, the Customise button must be visible."""
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        screen = await _reach_phase_2a(pilot, app)
        customise_btn = screen.query_one("#customise-btn", Button)
        assert customise_btn.display is True


# ---------------------------------------------------------------------------
# test_phase_2b_shows_all_catalog_tools_as_checkboxes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_2b_shows_all_catalog_tools_as_checkboxes(isolated_paths: Path) -> None:
    """Phase 2b must render one checkbox per tool in the catalog."""
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        screen = await _reach_phase_2b(pilot, app)

        # custom-tool-list must be visible
        custom_list = screen.query_one("#custom-tool-list", ListView)
        assert custom_list.display is True

        svc = CatalogService()
        all_tools = svc.get_all_tools()
        # Each tool should have a checkbox with id custom-tool-<key>
        for tool in all_tools:
            cb = screen.query_one(f"#custom-tool-{tool.key}", Checkbox)
            assert cb is not None, f"Missing checkbox for tool {tool.key}"


# ---------------------------------------------------------------------------
# test_phase_2b_recommended_tools_pre_checked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_2b_recommended_tools_pre_checked(isolated_paths: Path) -> None:
    """All recommended tools for the selected persona must be pre-checked in Phase 2b."""
    from ignition.core.onboarding import OnboardingService

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        screen = await _reach_phase_2b(pilot, app)

        first_persona_id = PERSONAS[0].id
        service = OnboardingService()
        recommended = set(service.get_recommended_tools([first_persona_id]))

        for tool_key in recommended:
            try:
                cb = screen.query_one(f"#custom-tool-{tool_key}", Checkbox)
                assert cb.value is True, (
                    f"Recommended tool '{tool_key}' should be pre-checked in Phase 2b"
                )
            except Exception:
                pytest.fail(f"Checkbox not found for recommended tool: {tool_key}")


# ---------------------------------------------------------------------------
# test_phase_2b_uncheck_excludes_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_2b_uncheck_excludes_tool(isolated_paths: Path) -> None:
    """Unchecking a recommended tool in Phase 2b must result in onboarding completing.

    We verify the OnboardingComplete message is posted when _complete_onboarding_custom
    is called, and that the resulting state has onboarding_complete=True.
    """
    first_recommended = PERSONAS[0].recommended_tools[0]

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        screen = await _reach_phase_2b(pilot, app)

        # Uncheck the first recommended tool
        cb = screen.query_one(f"#custom-tool-{first_recommended}", Checkbox)
        assert cb.value is True, "Recommended tool should be pre-checked"
        cb.toggle()
        await pilot.pause()  # type: ignore[attr-defined]
        assert cb.value is False, "Checkbox should now be unchecked"

        # Capture the OnboardingComplete message
        complete_messages: list[OnboardingComplete] = []
        original_post = screen.post_message

        def _capture(msg: object) -> None:
            if isinstance(msg, OnboardingComplete):
                complete_messages.append(msg)
            original_post(msg)

        screen.post_message = _capture  # type: ignore[method-assign]

        # Direct call to avoid OutOfBounds on docked btn-custom-accept
        screen._complete_onboarding_custom()
        await pilot.pause()  # type: ignore[attr-defined]

    # Verify a complete message was posted
    assert len(complete_messages) >= 1, "Expected OnboardingComplete to be posted"
    final_state = complete_messages[-1].state
    assert final_state.onboarding_complete is True

    # The unchecked tool should not be in the custom selection
    assert screen._custom_tool_keys is not None
    assert first_recommended not in screen._custom_tool_keys, (
        f"Unchecked tool '{first_recommended}' should not be in custom_tool_keys"
    )


# ---------------------------------------------------------------------------
# test_phase_2b_check_additional_tool_included
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_2b_check_additional_tool_included(isolated_paths: Path) -> None:
    """Checking a non-recommended tool in Phase 2b means it appears in the custom selection."""
    from ignition.core.onboarding import OnboardingService

    first_persona_id = PERSONAS[0].id

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        screen = await _reach_phase_2b(pilot, app)

        service = OnboardingService()
        recommended = set(service.get_recommended_tools([first_persona_id]))
        svc = CatalogService()
        all_tools = svc.get_all_tools()

        # Find a tool that is NOT recommended
        non_recommended = next(
            (t for t in all_tools if t.key not in recommended),
            None,
        )
        if non_recommended is None:
            pytest.skip("No non-recommended tools available in catalog")

        cb = screen.query_one(f"#custom-tool-{non_recommended.key}", Checkbox)
        assert cb.value is False, "Non-recommended tool should start unchecked"
        cb.toggle()
        await pilot.pause()  # type: ignore[attr-defined]
        assert cb.value is True, f"Checkbox for {non_recommended.key} should be checked"

        # Accept the custom selection via direct call
        screen._complete_onboarding_custom()
        await pilot.pause()  # type: ignore[attr-defined]

    # custom_tool_keys should include the extra tool
    assert screen._custom_tool_keys is not None
    assert non_recommended.key in screen._custom_tool_keys, (
        f"Newly-checked tool '{non_recommended.key}' should be in custom_tool_keys"
    )


# ---------------------------------------------------------------------------
# test_btn_custom_accept_triggers_onboarding_complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_btn_custom_accept_triggers_onboarding_complete(isolated_paths: Path) -> None:
    """_complete_onboarding_custom posts OnboardingComplete with onboarding_complete=True."""
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        screen = await _reach_phase_2b(pilot, app)

        complete_messages: list[OnboardingComplete] = []
        original_post = screen.post_message

        def _capture(msg: object) -> None:
            if isinstance(msg, OnboardingComplete):
                complete_messages.append(msg)
            original_post(msg)

        screen.post_message = _capture  # type: ignore[method-assign]

        # Direct call to avoid OutOfBounds on docked btn-custom-accept
        screen._complete_onboarding_custom()
        await pilot.pause()  # type: ignore[attr-defined]

    assert len(complete_messages) >= 1
    final_state = complete_messages[-1].state
    assert final_state.onboarding_complete is True
    assert final_state.selected_personas == [PERSONAS[0].id]
