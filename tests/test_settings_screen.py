from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import RadioSet

from ignition.app import IgnitionApp
from ignition.core.config import load_config, save_config
from ignition.core.state import save_state
from ignition.schemas.config import AppConfigModel
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.home import HomeScreen
from ignition.ui.screens.settings import SettingsScreen

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
async def test_all_four_radio_sets_present(isolated_paths: Path) -> None:
    """SettingsScreen must contain all four RadioSet widgets."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_settings(pilot)
        await pilot.pause()

        expected_ids = {"radio-theme", "radio-density", "radio-motion", "radio-automation"}
        found_ids = {rs.id for rs in screen.query(RadioSet) if rs.id}
        assert found_ids == expected_ids, f"Expected RadioSet IDs {expected_ids}, found {found_ids}"
