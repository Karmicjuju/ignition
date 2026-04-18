from __future__ import annotations

from datetime import UTC, datetime

from ignition.core.install_id import get_or_create_install_id
from ignition.core.paths import state_file
from ignition.schemas.state import AppStateModel


def load_state(*, demo_mode: bool = False) -> AppStateModel:
    path = state_file()
    if path.exists():
        try:
            state = AppStateModel.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            state = AppStateModel(install_id=get_or_create_install_id())
    else:
        state = AppStateModel(install_id=get_or_create_install_id())

    state.last_launched_at = datetime.now(UTC)
    state.demo_mode = demo_mode
    save_state(state)
    return state


def save_state(state: AppStateModel) -> None:
    state_file().write_text(state.model_dump_json(indent=2), encoding="utf-8")
