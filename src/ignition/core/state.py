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

            # Migration: v3 → v4 — add last_health_scan and health_summary
            if raw.get("schema_version") == 3:
                raw.setdefault("last_health_scan", None)
                raw.setdefault("health_summary", {})
                raw["schema_version"] = 4
                log.info("state.migrated", from_version=3, to_version=4)

            # Migration: v4 → v5 — add aws_auth (optional, defaults to None).
            # Pydantic fills the default on validate; we only need to bump the
            # version key so the re-save below stamps schema_version=5 and so
            # cascading migrations from older versions land on a valid v5 dict.
            if raw.get("schema_version") == 4:
                raw.setdefault("aws_auth", None)
                raw["schema_version"] = 5
                log.info("state.migrated", from_version=4, to_version=5)

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
