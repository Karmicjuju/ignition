from __future__ import annotations

from pathlib import Path

import pytest

from ignition.app import IgnitionApp
from ignition.core.paths import install_id_file, state_file
from ignition.schemas.state import STATE_SCHEMA_VERSION, AppStateModel


@pytest.mark.asyncio
async def test_app_boots_writes_state_and_quits(isolated_paths: Path) -> None:
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")

    assert state_file().exists(), "state.json should be written on launch"
    assert install_id_file().exists(), "install_id should be written on first launch"

    state = AppStateModel.model_validate_json(state_file().read_text())
    assert state.schema_version == STATE_SCHEMA_VERSION
    assert state.install_id == install_id_file().read_text().strip()
    assert state.demo_mode is False


@pytest.mark.asyncio
async def test_demo_mode_flag_persists_to_state(isolated_paths: Path) -> None:
    app = IgnitionApp(demo_mode=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")

    state = AppStateModel.model_validate_json(state_file().read_text())
    assert state.demo_mode is True


def test_install_id_is_stable_across_runs(isolated_paths: Path) -> None:
    from ignition.core.install_id import get_or_create_install_id

    first = get_or_create_install_id()
    second = get_or_create_install_id()
    assert first == second
