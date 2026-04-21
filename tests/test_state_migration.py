from __future__ import annotations

import json
from pathlib import Path

from ignition.core.paths import state_file
from ignition.core.state import load_state
from ignition.schemas.state import STATE_SCHEMA_VERSION


def _write_state(raw: dict[str, object]) -> Path:
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_v4_state_loads_cleanly_with_aws_auth_none(isolated_paths: Path) -> None:
    """Without the v4→v5 shim, an existing v4 file would fail validation
    (no aws_auth key, schema_version mismatch), fall through the except,
    and silently destroy install_id and onboarding progress.

    This test guards against that regression.
    """
    _write_state(
        {
            "schema_version": 4,
            "install_id": "tester-install-abc",
            "created_at": "2026-04-01T00:00:00+00:00",
            "last_launched_at": "2026-04-15T00:00:00+00:00",
            "demo_mode": False,
            "onboarding_complete": True,
            "onboarding_phase": 3,
            "selected_personas": ["backend"],
            "accepted_tool_bundle": True,
            "last_health_scan": None,
            "health_summary": {},
        }
    )

    state = load_state()

    # Critical: install_id and onboarding must be preserved.
    assert state.install_id == "tester-install-abc"
    assert state.onboarding_complete is True
    assert state.onboarding_phase == 3
    assert state.selected_personas == ["backend"]
    # aws_auth filled with the v5 default.
    assert state.aws_auth is None
    # install_history filled with the v6 default.
    assert state.install_history == []
    # And the file must be re-stamped at the new version on save.
    assert state.schema_version == STATE_SCHEMA_VERSION == 6


def test_v3_state_cascades_through_v4_to_v6(isolated_paths: Path) -> None:
    """Cascade test: a v3 file must walk through v3→v4→v5→v6 in a single
    load_state call. Without the explicit `raw["schema_version"] = N` reassignment
    in each shim, the cascade would short-circuit and the file would land
    at an intermediate version — failing the v6 model validate.
    """
    _write_state(
        {
            "schema_version": 3,
            "install_id": "v3-install-xyz",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_launched_at": "2026-04-01T00:00:00+00:00",
            "demo_mode": False,
            "onboarding_complete": False,
            "onboarding_phase": 0,
            "selected_personas": [],
            "accepted_tool_bundle": False,
        }
    )

    state = load_state()

    assert state.install_id == "v3-install-xyz"
    assert state.schema_version == 6
    assert state.aws_auth is None
    assert state.install_history == []
    # Re-load the persisted file to confirm save_state stamped v6.
    persisted = json.loads(state_file().read_text(encoding="utf-8"))
    assert persisted["schema_version"] == 6


def test_v5_state_migrates_to_v6(isolated_paths: Path) -> None:
    """A native v5 file must be migrated to v6 on load, gaining install_history."""
    _write_state(
        {
            "schema_version": 5,
            "install_id": "native-v5",
            "created_at": "2026-04-19T00:00:00+00:00",
            "last_launched_at": "2026-04-19T00:00:00+00:00",
            "demo_mode": False,
            "onboarding_complete": True,
            "onboarding_phase": 3,
            "selected_personas": ["devops"],
            "accepted_tool_bundle": True,
            "last_health_scan": None,
            "health_summary": {},
            "aws_auth": None,
        }
    )

    state = load_state()
    assert state.install_id == "native-v5"
    assert state.schema_version == 6
    assert state.aws_auth is None
    assert state.install_history == []


def test_v6_state_loads_without_migration(isolated_paths: Path) -> None:
    """A native v6 file with install_history must round-trip unchanged."""
    _write_state(
        {
            "schema_version": 6,
            "install_id": "native-v6",
            "created_at": "2026-04-21T00:00:00+00:00",
            "last_launched_at": "2026-04-21T00:00:00+00:00",
            "demo_mode": False,
            "onboarding_complete": True,
            "onboarding_phase": 3,
            "selected_personas": ["devops"],
            "accepted_tool_bundle": True,
            "last_health_scan": None,
            "health_summary": {},
            "aws_auth": None,
            "install_history": [],
        }
    )

    state = load_state()
    assert state.install_id == "native-v6"
    assert state.schema_version == 6
    assert state.aws_auth is None
    assert state.install_history == []
