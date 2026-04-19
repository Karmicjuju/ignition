from __future__ import annotations

from pathlib import Path

from ignition.core.catalog import CatalogService
from ignition.schemas.catalog import InstallStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service(isolated_paths: Path) -> CatalogService:
    """Instantiate a fresh CatalogService (isolated_paths passed for fixture hygiene)."""
    return CatalogService()


# ---------------------------------------------------------------------------
# test_get_all_tools_returns_twelve
# ---------------------------------------------------------------------------


def test_get_all_tools_returns_twelve(isolated_paths: Path) -> None:
    """The stub catalogue must contain exactly 12 tools."""
    svc = _service(isolated_paths)
    tools = svc.get_all_tools()
    assert len(tools) == 12


# ---------------------------------------------------------------------------
# test_get_all_tools_fields_valid
# ---------------------------------------------------------------------------


def test_get_all_tools_fields_valid(isolated_paths: Path) -> None:
    """Every tool must have non-empty key, name, description, at least one
    category, and at least one persona_tag."""
    svc = _service(isolated_paths)
    for tool in svc.get_all_tools():
        assert tool.key, f"tool {tool!r} has empty key"
        assert tool.name, f"tool {tool.key!r} has empty name"
        assert tool.description, f"tool {tool.key!r} has empty description"
        assert tool.categories, f"tool {tool.key!r} has no categories"
        assert tool.persona_tags, f"tool {tool.key!r} has no persona_tags"


# ---------------------------------------------------------------------------
# test_get_tools_for_personas_backend
# ---------------------------------------------------------------------------


def test_get_tools_for_personas_backend(isolated_paths: Path) -> None:
    """Backend persona must include python, docker, and git; must exclude terraform."""
    svc = _service(isolated_paths)
    tools = svc.get_tools_for_personas(["backend"])
    keys = {t.key for t in tools}
    assert "python" in keys
    assert "docker" in keys
    assert "git" in keys
    assert "terraform" not in keys


# ---------------------------------------------------------------------------
# test_get_tools_for_personas_deduplication
# ---------------------------------------------------------------------------


def test_get_tools_for_personas_deduplication(isolated_paths: Path) -> None:
    """Two personas that share 'git' and 'awscli' must not produce duplicates."""
    svc = _service(isolated_paths)
    tools = svc.get_tools_for_personas(["backend", "frontend"])
    keys = [t.key for t in tools]
    assert keys.count("git") == 1, "'git' must appear exactly once"
    assert keys.count("awscli") == 1, "'awscli' must appear exactly once"


# ---------------------------------------------------------------------------
# test_get_tools_for_personas_unknown_id_ignored
# ---------------------------------------------------------------------------


def test_get_tools_for_personas_unknown_id_ignored(isolated_paths: Path) -> None:
    """Unknown persona ids must be silently skipped without raising."""
    svc = _service(isolated_paths)
    backend_tools = svc.get_tools_for_personas(["backend"])
    combined = svc.get_tools_for_personas(["backend", "unknown_persona_xyz"])
    assert {t.key for t in combined} == {t.key for t in backend_tools}


# ---------------------------------------------------------------------------
# test_search_tools_case_insensitive
# ---------------------------------------------------------------------------


def test_search_tools_case_insensitive(isolated_paths: Path) -> None:
    """search_tools must match regardless of query case — 'DOCKER' finds docker."""
    svc = _service(isolated_paths)
    results = svc.search_tools("DOCKER")
    keys = {t.key for t in results}
    assert "docker" in keys


# ---------------------------------------------------------------------------
# test_search_tools_matches_description
# ---------------------------------------------------------------------------


def test_search_tools_matches_description(isolated_paths: Path) -> None:
    """A substring from a tool's description must be enough to find it."""
    svc = _service(isolated_paths)
    # "Kubernetes" appears in kubectl's description ("controlling Kubernetes clusters")
    results = svc.search_tools("Kubernetes")
    keys = {t.key for t in results}
    assert "kubectl" in keys


# ---------------------------------------------------------------------------
# test_search_tools_no_match_returns_empty
# ---------------------------------------------------------------------------


def test_search_tools_no_match_returns_empty(isolated_paths: Path) -> None:
    """A query that matches nothing must return an empty list, not raise."""
    svc = _service(isolated_paths)
    results = svc.search_tools("zzznomatch")
    assert results == []


# ---------------------------------------------------------------------------
# test_simulate_install_mutates_status
# ---------------------------------------------------------------------------


def test_simulate_install_mutates_status(isolated_paths: Path) -> None:
    """simulate_install must flip the in-memory status to INSTALLED."""
    svc = _service(isolated_paths)
    # python starts as MISSING per stub catalogue
    before = next(t for t in svc.get_all_tools() if t.key == "python")
    assert before.install_status == InstallStatus.MISSING

    updated = svc.simulate_install("python")

    assert updated is not None
    assert updated.install_status == InstallStatus.INSTALLED
    # The in-memory cache must also reflect the change
    cached = next(t for t in svc.get_all_tools() if t.key == "python")
    assert cached.install_status == InstallStatus.INSTALLED


# ---------------------------------------------------------------------------
# test_simulate_install_unknown_key_returns_none
# ---------------------------------------------------------------------------


def test_simulate_install_unknown_key_returns_none(isolated_paths: Path) -> None:
    """simulate_install with an unknown key must return None without raising."""
    svc = _service(isolated_paths)
    result = svc.simulate_install("no_such_tool_xyz")
    assert result is None
