from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ignition.core.install_id import get_or_create_install_id
from ignition.core.logging import get_logger
from ignition.core.paths import state_file
from ignition.schemas.state import AppStateModel


def load_state(*, demo_mode: bool = False) -> AppStateModel:
    log = get_logger("ignition.core.state")
    path = state_file()
    if path.exists():
        try:
            raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

            # Migration: v2 → v3 — drop tool_catalog_cache (moved to file cache)
            if raw.get("schema_version") == 2:
                raw.pop("tool_catalog_cache", None)
                log.info("state.migrated", from_version=2, to_version=3)

            state = AppStateModel.model_validate(raw)
        except Exception as exc:
            log.warning("state.load_failed", reason=str(exc))
            state = AppStateModel(install_id=get_or_create_install_id())
    else:
        state = AppStateModel(install_id=get_or_create_install_id())

    state.last_launched_at = datetime.now(UTC)
    state.demo_mode = demo_mode
    save_state(state)
    return state


def save_state(state: AppStateModel) -> None:
    state_file().write_text(state.model_dump_json(indent=2), encoding="utf-8")
