from __future__ import annotations

from pathlib import Path

import pytest

from ignition.app import IgnitionApp
from ignition.core.paths import state_file
from ignition.core.state import save_state
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.home import HomeScreen
from ignition.ui.screens.onboarding import OnboardingScreen


@pytest.mark.asyncio
async def test_app_boots_and_quits(isolated_paths: Path) -> None:
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")


@pytest.mark.asyncio
async def test_demo_mode_flag(isolated_paths: Path) -> None:
    """Demo mode seeds Scenario 1 (partially onboarded, onboarding_complete=False)
    and routes to OnboardingScreen. The seeded state is marked demo_mode=True.
    """
    async with IgnitionApp(demo_mode=True).run_test() as pilot:
        await pilot.pause()
        # Scenario 1 leaves onboarding incomplete → OnboardingScreen
        assert isinstance(pilot.app.screen, OnboardingScreen)

    state = AppStateModel.model_validate_json(state_file().read_text())
    assert state.demo_mode is True


@pytest.mark.asyncio
async def test_first_launch_shows_onboarding_screen(isolated_paths: Path) -> None:
    """Fresh state (onboarding_complete=False by default) routes to OnboardingScreen."""
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        assert isinstance(pilot.app.screen, OnboardingScreen)


@pytest.mark.asyncio
async def test_returning_user_shows_home_screen(isolated_paths: Path) -> None:
    """A state file with onboarding_complete=True routes directly to HomeScreen."""
    save_state(AppStateModel(install_id="test-id", onboarding_complete=True))

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        assert isinstance(pilot.app.screen, HomeScreen)


def test_install_id_is_stable_across_runs(isolated_paths: Path) -> None:
    from ignition.core.install_id import get_or_create_install_id

    first = get_or_create_install_id()
    second = get_or_create_install_id()
    assert first == second
