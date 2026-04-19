from __future__ import annotations

from pathlib import Path

import pytest

from ignition.app import IgnitionApp
from ignition.core.demo import DEMO_TOOL_LIST, seed_demo_state
from ignition.schemas.state import AppStateModel

# ---------------------------------------------------------------------------
# Group 1 — seed_demo_state unit tests (sync)
# ---------------------------------------------------------------------------


def test_seed_demo_state_sets_personas(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="test-id")
    seed_demo_state(state)
    assert state.selected_personas == ["backend", "devops"]


def test_seed_demo_state_completes_onboarding(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="test-id")
    seed_demo_state(state)
    assert state.onboarding_complete is True
    assert state.onboarding_phase == 3
    assert state.accepted_tool_bundle is True


def test_seed_demo_state_does_not_mutate_install_id(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="test-id")
    seed_demo_state(state)
    assert state.install_id == "test-id"


def test_seed_demo_state_does_not_mutate_demo_mode(isolated_paths: Path) -> None:
    state_true = AppStateModel(install_id="test-id", demo_mode=True)
    seed_demo_state(state_true)
    assert state_true.demo_mode is True

    state_false = AppStateModel(install_id="test-id", demo_mode=False)
    seed_demo_state(state_false)
    assert state_false.demo_mode is False


def test_demo_tool_list_is_nonempty(isolated_paths: Path) -> None:
    assert len(DEMO_TOOL_LIST) > 0
    assert all(isinstance(entry, str) and entry for entry in DEMO_TOOL_LIST)


# ---------------------------------------------------------------------------
# Group 2 — Demo banner async Textual pilot tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_demo_banner_visible_in_demo_mode(isolated_paths: Path) -> None:
    async with IgnitionApp(demo_mode=True).run_test() as pilot:
        await pilot.pause()
        results = pilot.app.query("#demo-banner")
        assert len(results) > 0
        widget = results.first()
        assert widget.display is True


@pytest.mark.asyncio
async def test_demo_banner_absent_in_normal_mode(isolated_paths: Path) -> None:
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        results = pilot.app.query("#demo-banner")
        assert len(results) == 0
