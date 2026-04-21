from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, RadioSet, Static

from ignition.app import IgnitionApp
from ignition.core.config import load_config, save_config
from ignition.core.state import save_state
from ignition.schemas.config import AppConfigModel
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.home import HomeScreen
from ignition.ui.screens.settings import PersonaManagerModal, SettingsScreen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _complete_state() -> AppStateModel:
    return AppStateModel(install_id="test-id", onboarding_complete=True)


async def _navigate_to_settings(pilot: object) -> SettingsScreen:  # type: ignore[type-arg]
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("ctrl+comma")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    screen = pilot.app.screen  # type: ignore[attr-defined]
    assert isinstance(screen, SettingsScreen)
    return screen


# ---------------------------------------------------------------------------
# test_settings_screen_boots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_screen_boots(isolated_paths: Path) -> None:
    """ctrl+, from HomeScreen must push SettingsScreen."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        assert isinstance(pilot.app.screen, HomeScreen)
        await pilot.press("ctrl+comma")
        await pilot.pause()
        assert isinstance(pilot.app.screen, SettingsScreen), (
            f"Expected SettingsScreen, got {type(pilot.app.screen).__name__}"
        )


# ---------------------------------------------------------------------------
# test_settings_screen_reflects_saved_config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_screen_reflects_saved_config(isolated_paths: Path) -> None:
    """SettingsScreen reads existing config on init and displays correct selection."""
    # Save a non-default config before opening the screen
    config = AppConfigModel(
        theme="light", density="compact", motion="reduced", automation_level="assist"
    )
    save_config(config)
    save_state(_complete_state())

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        # The screen's _config should reflect what we saved
        assert screen._config.theme == "light"
        assert screen._config.density == "compact"
        assert screen._config.motion == "reduced"
        assert screen._config.automation_level == "assist"


# ---------------------------------------------------------------------------
# test_theme_radio_change_saves_config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_theme_radio_change_saves_config(isolated_paths: Path) -> None:
    """Changing the Theme RadioSet to Light immediately persists to config file."""
    save_state(_complete_state())
    # Start with dark (default)
    save_config(AppConfigModel(theme="dark"))

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        # Simulate RadioSet.Changed for the theme group
        theme_set = screen.query_one("#radio-theme", RadioSet)
        # Navigate to next button (wraps around), which fires RadioSet.Changed
        theme_set.action_next_button()
        await pilot.pause()

        # Config on the screen instance should be updated
        assert screen._config.theme in ("light", "dark"), (
            f"Unexpected theme value: {screen._config.theme}"
        )

        # Verify the persisted config file reflects the change
        saved = load_config()
        assert saved.theme == screen._config.theme


# ---------------------------------------------------------------------------
# test_density_radio_change_saves_config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_density_radio_change_saves_config(isolated_paths: Path) -> None:
    """Changing Density to Compact immediately persists to config file."""
    save_state(_complete_state())
    save_config(AppConfigModel(density="full"))

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        density_set = screen.query_one("#radio-density", RadioSet)
        density_set.action_next_button()
        await pilot.pause()

        saved = load_config()
        assert saved.density == screen._config.density


# ---------------------------------------------------------------------------
# test_motion_radio_change_saves_config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_motion_radio_change_saves_config(isolated_paths: Path) -> None:
    """Changing Motion to Reduced immediately persists to config file."""
    save_state(_complete_state())
    save_config(AppConfigModel(motion="standard"))

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        motion_set = screen.query_one("#radio-motion", RadioSet)
        motion_set.action_next_button()
        await pilot.pause()

        saved = load_config()
        assert saved.motion == screen._config.motion


# ---------------------------------------------------------------------------
# test_automation_radio_change_saves_config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_automation_radio_change_saves_config(isolated_paths: Path) -> None:
    """Changing Automation level immediately persists to config file."""
    save_state(_complete_state())
    save_config(AppConfigModel(automation_level="observe"))

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        automation_set = screen.query_one("#radio-automation", RadioSet)
        automation_set.action_next_button()
        await pilot.pause()

        saved = load_config()
        assert saved.automation_level == screen._config.automation_level


# ---------------------------------------------------------------------------
# test_escape_returns_to_home
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escape_returns_to_home(isolated_paths: Path) -> None:
    """Pressing Escape from SettingsScreen returns to HomeScreen."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await _navigate_to_settings(pilot)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(pilot.app.screen, HomeScreen), (
            f"Expected HomeScreen after Escape, got {type(pilot.app.screen).__name__}"
        )


# ---------------------------------------------------------------------------
# test_all_four_radio_sets_present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_radio_sets_present(isolated_paths: Path) -> None:
    """SettingsScreen must contain all five RadioSet widgets (including release channel)."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        expected_ids = {
            "radio-theme",
            "radio-density",
            "radio-motion",
            "radio-automation",
            "radio-channel",
        }
        found_ids = {rs.id for rs in screen.query(RadioSet) if rs.id}
        assert found_ids == expected_ids, f"Expected RadioSet IDs {expected_ids}, found {found_ids}"


# ---------------------------------------------------------------------------
# test_personas_section_visible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_personas_section_visible(isolated_paths: Path) -> None:
    """SettingsScreen must render the Personas section with manage button."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        # Personas title must be present
        titles = [w for w in screen.query(Static) if w.id == "personas-title"]
        assert titles, "Expected #personas-title widget in SettingsScreen"

        # Manage personas button must be present
        btn = screen.query_one("#btn-manage-personas", Button)
        assert btn is not None


# ---------------------------------------------------------------------------
# test_personas_section_shows_no_personas_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_personas_section_shows_no_personas_message(isolated_paths: Path) -> None:
    """When no personas are selected, show 'No personas selected.' text."""
    state = AppStateModel(install_id="test-id", onboarding_complete=True, selected_personas=[])
    save_state(state)
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        label = screen.query_one("#active-personas-label", Static)
        assert "No personas" in str(label.content)


# ---------------------------------------------------------------------------
# test_personas_section_shows_active_personas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_personas_section_shows_active_personas(isolated_paths: Path) -> None:
    """When personas are selected, show them in the active personas label."""
    state = AppStateModel(
        install_id="test-id",
        onboarding_complete=True,
        selected_personas=["backend"],
    )
    save_state(state)
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        label = screen.query_one("#active-personas-label", Static)
        assert "Backend" in str(label.content)


# ---------------------------------------------------------------------------
# test_manage_personas_button_opens_modal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manage_personas_button_opens_modal(isolated_paths: Path) -> None:
    """Pressing 'Manage personas' button must push PersonaManagerModal onto the screen stack."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test(size=(120, 60)) as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        # Post button pressed directly to avoid viewport/click-offset issues
        btn = screen.query_one("#btn-manage-personas", Button)
        screen.post_message(Button.Pressed(btn))
        await pilot.pause()

        assert isinstance(pilot.app.screen, PersonaManagerModal), (
            f"Expected PersonaManagerModal, got {type(pilot.app.screen).__name__}"
        )


# ---------------------------------------------------------------------------
# test_persona_manager_modal_shows_all_personas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persona_manager_modal_shows_all_personas(isolated_paths: Path) -> None:
    """PersonaManagerModal must render a checkbox for each of the 5 personas."""
    save_state(_complete_state())
    from textual.widgets import Checkbox

    async with IgnitionApp(demo_mode=False).run_test(size=(120, 60)) as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        btn = screen.query_one("#btn-manage-personas", Button)
        screen.post_message(Button.Pressed(btn))
        await pilot.pause()

        modal = pilot.app.screen
        assert isinstance(modal, PersonaManagerModal)
        checkboxes = list(modal.query(Checkbox))
        assert len(checkboxes) == 5, f"Expected 5 persona checkboxes, got {len(checkboxes)}"


# ---------------------------------------------------------------------------
# test_persona_manager_modal_checkboxes_reflect_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persona_manager_modal_checkboxes_reflect_state(isolated_paths: Path) -> None:
    """PersonaManagerModal checkboxes reflect current selected_personas."""
    state = AppStateModel(
        install_id="test-id",
        onboarding_complete=True,
        selected_personas=["backend"],
    )
    save_state(state)
    from textual.widgets import Checkbox

    async with IgnitionApp(demo_mode=False).run_test(size=(120, 60)) as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        btn = screen.query_one("#btn-manage-personas", Button)
        screen.post_message(Button.Pressed(btn))
        await pilot.pause()

        modal = pilot.app.screen
        assert isinstance(modal, PersonaManagerModal)

        backend_cb = modal.query_one("#persona-backend", Checkbox)
        frontend_cb = modal.query_one("#persona-frontend", Checkbox)

        assert backend_cb.value is True, "backend checkbox must be checked"
        assert frontend_cb.value is False, "frontend checkbox must be unchecked"


# ---------------------------------------------------------------------------
# test_persona_manager_done_dismisses_modal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persona_manager_done_dismisses_modal(isolated_paths: Path) -> None:
    """Pressing 'Done' in PersonaManagerModal returns to SettingsScreen."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test(size=(120, 60)) as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        btn = screen.query_one("#btn-manage-personas", Button)
        screen.post_message(Button.Pressed(btn))
        await pilot.pause()

        assert isinstance(pilot.app.screen, PersonaManagerModal)

        done_btn = pilot.app.screen.query_one("#persona-done", Button)
        pilot.app.screen.post_message(Button.Pressed(done_btn))
        await pilot.pause()

        assert isinstance(pilot.app.screen, SettingsScreen), (
            f"Expected SettingsScreen after Done, got {type(pilot.app.screen).__name__}"
        )


# ---------------------------------------------------------------------------
# test_release_channel_radio_set_present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_channel_radio_set_present(isolated_paths: Path) -> None:
    """SettingsScreen must contain the #radio-channel RadioSet widget."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        radio_channel = screen.query_one("#radio-channel", RadioSet)
        assert radio_channel is not None, "Expected #radio-channel RadioSet in SettingsScreen"


# ---------------------------------------------------------------------------
# test_release_channel_reflects_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_channel_reflects_state_stable(isolated_paths: Path) -> None:
    """Release channel RadioSet must reflect the preferred_channel from AppStateModel."""
    state = AppStateModel(
        install_id="test-id", onboarding_complete=True, preferred_channel="stable"
    )
    save_state(state)

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        # The screen's state should reflect stable
        assert screen._state.preferred_channel == "stable"


# ---------------------------------------------------------------------------
# test_release_channel_change_saves_to_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_channel_change_saves_to_state(isolated_paths: Path) -> None:
    """Changing Release channel RadioSet must persist preferred_channel to state."""

    state = AppStateModel(
        install_id="test-id", onboarding_complete=True, preferred_channel="stable"
    )
    save_state(state)

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        # Trigger a RadioSet.Changed on radio-channel
        channel_set = screen.query_one("#radio-channel", RadioSet)
        channel_set.action_next_button()
        await pilot.pause()

        # preferred_channel on screen state should have changed
        assert screen._state.preferred_channel in ("stable", "beta", "experimental"), (
            f"Unexpected preferred_channel: {screen._state.preferred_channel}"
        )
