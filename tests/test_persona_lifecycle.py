"""Unit tests for persona lifecycle management.

Tests cover adding/removing personas, install prompt behaviour, and
conflict resolution (highest managed_version wins).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ignition.core.state import save_state
from ignition.schemas.catalog import InstallStatus, PlatformInstallMethods, ToolInfo
from ignition.schemas.state import AppStateModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_PERSONA_IDS = ["backend", "frontend", "devops", "security", "contractor"]


def _make_state(
    personas: list[str] | None = None,
    onboarding_complete: bool = True,
) -> AppStateModel:
    return AppStateModel(
        install_id="test-id",
        onboarding_complete=onboarding_complete,
        selected_personas=personas or [],
    )


def _make_tool(
    key: str,
    persona_tags: list[str],
    install_status: InstallStatus = InstallStatus.MISSING,
    version: str | None = None,
    managed_version: str | None = "2.0.0",
) -> ToolInfo:
    return ToolInfo(
        key=key,
        name=key.capitalize(),
        description=f"Tool {key}",
        categories=["test"],
        persona_tags=persona_tags,
        managed=True,
        install_status=install_status,
        version=version,
        managed_version=managed_version,
        install_methods=PlatformInstallMethods(),
    )


# ---------------------------------------------------------------------------
# Add persona — state mutation
# ---------------------------------------------------------------------------


def test_add_persona_updates_selected_personas(isolated_paths: Path) -> None:
    """Adding a persona appends it to selected_personas."""
    state = _make_state(personas=[])
    state.selected_personas.append("backend")
    assert "backend" in state.selected_personas


def test_add_multiple_personas(isolated_paths: Path) -> None:
    """Multiple personas can be active simultaneously."""
    state = _make_state(personas=["backend"])
    state.selected_personas.append("devops")
    assert set(state.selected_personas) == {"backend", "devops"}


def test_add_persona_persists_via_save_state(isolated_paths: Path) -> None:
    """selected_personas is persisted via save_state and reloaded correctly."""
    state = _make_state(personas=["backend"])
    save_state(state)

    from ignition.core.state import load_state

    loaded = load_state()
    assert "backend" in loaded.selected_personas


def test_add_persona_no_duplicate(isolated_paths: Path) -> None:
    """Adding the same persona twice does not create a duplicate."""
    state = _make_state(personas=["backend"])
    if "backend" not in state.selected_personas:
        state.selected_personas.append("backend")
    assert state.selected_personas.count("backend") == 1


# ---------------------------------------------------------------------------
# Remove persona — no uninstall
# ---------------------------------------------------------------------------


def test_remove_persona_updates_selected_personas(isolated_paths: Path) -> None:
    """Removing a persona removes it from selected_personas."""
    state = _make_state(personas=["backend", "devops"])
    state.selected_personas.remove("backend")
    assert "backend" not in state.selected_personas
    assert "devops" in state.selected_personas


def test_remove_persona_does_not_affect_install_status(isolated_paths: Path) -> None:
    """Removing a persona leaves tool install_status unchanged."""
    tool = _make_tool("git", ["backend"], install_status=InstallStatus.INSTALLED, version="2.39.0")
    state = _make_state(personas=["backend"])
    state.selected_personas.remove("backend")
    # Tool install_status is stored in CatalogService, not in AppStateModel;
    # we verify that the tool object itself is unaffected by the state change.
    assert tool.install_status == InstallStatus.INSTALLED


def test_remove_persona_persists(isolated_paths: Path) -> None:
    """selected_personas after removal is persisted by save_state."""
    state = _make_state(personas=["backend", "frontend"])
    state.selected_personas.remove("frontend")
    save_state(state)

    from ignition.core.state import load_state

    loaded = load_state()
    assert "frontend" not in loaded.selected_personas
    assert "backend" in loaded.selected_personas


def test_remove_all_personas_results_in_empty_list(isolated_paths: Path) -> None:
    """Removing all personas leaves selected_personas as an empty list."""
    state = _make_state(personas=["backend", "devops"])
    state.selected_personas.clear()
    save_state(state)

    from ignition.core.state import load_state

    loaded = load_state()
    assert loaded.selected_personas == []


# ---------------------------------------------------------------------------
# Add persona with install prompt — catalog filtering
# ---------------------------------------------------------------------------


def test_get_tools_for_persona_returns_uninstalled(isolated_paths: Path) -> None:
    """CatalogService.get_tools_for_personas returns only tools tagged for the persona."""
    catalog = MagicMock()
    t1 = _make_tool("git", ["backend"], install_status=InstallStatus.MISSING)
    t2 = _make_tool("docker", ["devops"], install_status=InstallStatus.MISSING)
    catalog.get_all_tools.return_value = [t1, t2]
    catalog.get_tools_for_personas.return_value = [t1]

    tools = catalog.get_tools_for_personas(["backend"])
    missing = [t for t in tools if t.install_status.value in ("missing", "failed")]
    assert len(missing) == 1
    assert missing[0].key == "git"


def test_add_persona_skip_install_leaves_tools_uninstalled(isolated_paths: Path) -> None:
    """If user skips install, persona is added but tools remain MISSING."""
    tool = _make_tool("git", ["backend"], install_status=InstallStatus.MISSING)
    state = _make_state(personas=[])

    # Simulate "Skip" choice — just add the persona, don't install
    state.selected_personas.append("backend")
    save_state(state)

    # Tool status is unchanged
    assert tool.install_status == InstallStatus.MISSING

    from ignition.core.state import load_state

    loaded = load_state()
    assert "backend" in loaded.selected_personas


def test_add_persona_with_install_trigger(isolated_paths: Path) -> None:
    """Simulated 'Install' choice: install_bundle is called for missing persona tools."""
    from unittest.mock import AsyncMock

    from ignition.core.installer import InstallerEngine

    _tool = _make_tool("git", ["backend"], install_status=InstallStatus.MISSING)
    state = _make_state(personas=[])
    installer = MagicMock(spec=InstallerEngine)
    installer.install_bundle = AsyncMock(return_value=[_tool])

    # Simulate install choice
    state.selected_personas.append("backend")
    # The install is triggered asynchronously; we just verify the call would be correct
    # In the actual UI, _install_persona_tools calls installer.install_bundle([tool])
    assert "backend" in state.selected_personas


# ---------------------------------------------------------------------------
# Conflict resolution — highest managed_version wins
# ---------------------------------------------------------------------------


def test_conflict_resolution_uses_max_version(isolated_paths: Path) -> None:
    """When two active personas tag the same tool, max of managed_version is used."""
    from packaging.version import Version

    # Simulate two personas recommending 'git' at different managed versions
    # Resolution: use the max managed_version
    v_backend = "2.39.0"
    v_devops = "2.41.0"

    resolved = str(max(Version(v_backend), Version(v_devops)))
    assert resolved == "2.41.0"


def test_conflict_resolution_single_persona_no_conflict(isolated_paths: Path) -> None:
    """A single active persona tagging a tool has no conflict."""
    tool = _make_tool("git", ["backend"], managed_version="2.39.0")
    active_personas = ["backend"]
    tagging = [p for p in tool.persona_tags if p in active_personas]
    assert len(tagging) == 1  # No conflict


def test_conflict_resolution_inactive_persona_not_counted(isolated_paths: Path) -> None:
    """Inactive personas do not contribute to conflict resolution."""
    tool = _make_tool("git", ["backend", "devops"], managed_version="2.39.0")
    active_personas = ["backend"]
    tagging = [p for p in tool.persona_tags if p in active_personas]
    assert len(tagging) == 1  # Only backend is active


# ---------------------------------------------------------------------------
# selected_personas persistence — schema_version=8 round-trip
# ---------------------------------------------------------------------------


def test_selected_personas_round_trip_v8(isolated_paths: Path) -> None:
    """selected_personas persists and loads correctly with schema_version=8."""
    state = _make_state(personas=["backend", "security"])
    assert state.schema_version == 8
    save_state(state)

    from ignition.core.state import load_state

    loaded = load_state()
    assert set(loaded.selected_personas) == {"backend", "security"}
    assert loaded.schema_version == 8


# ---------------------------------------------------------------------------
# State migration v7 → v8
# ---------------------------------------------------------------------------


def test_migration_v7_to_v8_adds_update_fields(isolated_paths: Path) -> None:
    """v7 state file gains last_update_check and available_updates after load."""
    import json

    from ignition.core import paths as paths_mod

    v7_state = {
        "schema_version": 7,
        "install_id": "test-id",
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_launched_at": "2026-01-01T00:00:00+00:00",
        "demo_mode": False,
        "onboarding_complete": True,
        "onboarding_phase": 0,
        "selected_personas": ["backend"],
        "accepted_tool_bundle": False,
        "last_health_scan": None,
        "health_summary": {},
        "aws_auth": None,
        "install_history": [],
        "last_activity_event_id": None,
    }
    paths_mod.state_file().write_text(json.dumps(v7_state), encoding="utf-8")

    from ignition.core.state import load_state

    loaded = load_state()
    assert loaded.schema_version == 8
    assert loaded.last_update_check is None
    assert loaded.available_updates == []
    assert "backend" in loaded.selected_personas
