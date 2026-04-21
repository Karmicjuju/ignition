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

            # Migration: v5 → v6 — add install_history (empty list default).
            # Pydantic fills the default on validate; bumping the version key
            # ensures the re-save stamps schema_version=6 and cascading
            # migrations from older versions land on a valid v6 dict.
            if raw.get("schema_version") == 5:
                raw.setdefault("install_history", [])
                raw["schema_version"] = 6
                log.info("state.migrated", from_version=5, to_version=6)

            # Migration: v6 → v7 — add last_activity_event_id (None default).
            # Pydantic fills the default on validate; bumping the version key
            # ensures the re-save stamps schema_version=7.
            if raw.get("schema_version") == 6:
                raw.setdefault("last_activity_event_id", None)
                raw["schema_version"] = 7
                log.info("state.migrated", from_version=6, to_version=7)

            # Migration: v7 → v8 — add last_update_check and available_updates.
            # Pydantic fills the defaults on validate; bumping the version key
            # ensures the re-save stamps schema_version=8.
            if raw.get("schema_version") == 7:
                raw.setdefault("last_update_check", None)
                raw.setdefault("available_updates", [])
                raw["schema_version"] = 8
                log.info("state.migrated", from_version=7, to_version=8)

            # Migration: v8 → v9 — add preferred_channel (release channel preference).
            # Pydantic fills the default on validate; bumping the version key
            # ensures the re-save stamps schema_version=9.
            if raw.get("schema_version") == 8:
                raw.setdefault("preferred_channel", "stable")
                raw["schema_version"] = 9
                log.info("state.migrated", from_version=8, to_version=9)

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
