from __future__ import annotations

from pathlib import Path

from ignition.core.catalog import CatalogService
from ignition.core.catalog_loader import load_bundled, load_local_override, load_remote
from ignition.schemas.catalog import InstallStatus, ToolInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service(isolated_paths: Path) -> CatalogService:
    """Instantiate a fresh CatalogService (isolated_paths passed for fixture hygiene)."""
    return CatalogService()


# ---------------------------------------------------------------------------
# test_get_all_tools_returns_tools
# ---------------------------------------------------------------------------


def test_get_all_tools_returns_tools(isolated_paths: Path) -> None:
    """The bundled catalogue must return at least one tool.

    We also confirm the count equals the number of YAML files in the bundled
    data directory (currently 12).
    """
    import importlib.resources

    svc = _service(isolated_paths)
    tools = svc.get_all_tools()
    assert len(tools) >= 1

    # Count YAML files in the bundled package data to cross-check.
    package_ref = importlib.resources.files("ignition.data.catalog.tools")
    yaml_count = sum(
        1
        for r in package_ref.iterdir()
        if r.name.endswith(".yaml")  # type: ignore[attr-defined]
    )
    assert len(tools) == yaml_count, (
        f"Expected {yaml_count} tools (one per YAML file), got {len(tools)}"
    )


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
# test_simulate_install_does_not_exist
# ---------------------------------------------------------------------------


def test_simulate_install_does_not_exist(isolated_paths: Path) -> None:
    """CatalogService must NOT expose simulate_install (removed in M4)."""
    svc = _service(isolated_paths)
    assert not hasattr(svc, "simulate_install"), (
        "simulate_install must be removed from CatalogService"
    )


# ---------------------------------------------------------------------------
# test_mark_installed_mutates_status
# ---------------------------------------------------------------------------


def test_mark_installed_mutates_status(isolated_paths: Path) -> None:
    """mark_installed must flip the in-memory status to INSTALLED."""
    svc = _service(isolated_paths)
    before = next(t for t in svc.get_all_tools() if t.key == "python")
    assert before.install_status == InstallStatus.MISSING

    updated = svc.mark_installed("python")

    assert updated is not None
    assert updated.install_status == InstallStatus.INSTALLED
    # The in-memory cache must also reflect the change
    cached = next(t for t in svc.get_all_tools() if t.key == "python")
    assert cached.install_status == InstallStatus.INSTALLED


# ---------------------------------------------------------------------------
# test_mark_installed_records_version
# ---------------------------------------------------------------------------


def test_mark_installed_records_version(isolated_paths: Path) -> None:
    """mark_installed with a version argument must update tool.version."""
    svc = _service(isolated_paths)
    updated = svc.mark_installed("python", version="3.12.0")
    assert updated is not None
    assert updated.install_status == InstallStatus.INSTALLED
    assert updated.version == "3.12.0"


# ---------------------------------------------------------------------------
# test_mark_installed_unknown_key_returns_none
# ---------------------------------------------------------------------------


def test_mark_installed_unknown_key_returns_none(isolated_paths: Path) -> None:
    """mark_installed with an unknown key must return None without raising."""
    svc = _service(isolated_paths)
    result = svc.mark_installed("no_such_tool_xyz")
    assert result is None


# ---------------------------------------------------------------------------
# test_mark_failed_mutates_status
# ---------------------------------------------------------------------------


def test_mark_failed_mutates_status(isolated_paths: Path) -> None:
    """mark_failed must flip the in-memory status to FAILED."""
    svc = _service(isolated_paths)
    before = next(t for t in svc.get_all_tools() if t.key == "python")
    assert before.install_status == InstallStatus.MISSING

    updated = svc.mark_failed("python")

    assert updated is not None
    assert updated.install_status == InstallStatus.FAILED
    # The in-memory cache must also reflect the change
    cached = next(t for t in svc.get_all_tools() if t.key == "python")
    assert cached.install_status == InstallStatus.FAILED


# ---------------------------------------------------------------------------
# test_mark_failed_unknown_key_returns_none
# ---------------------------------------------------------------------------


def test_mark_failed_unknown_key_returns_none(isolated_paths: Path) -> None:
    """mark_failed with an unknown key must return None without raising."""
    svc = _service(isolated_paths)
    result = svc.mark_failed("no_such_tool_xyz")
    assert result is None


# ===========================================================================
# Loader function tests (catalog_loader.py)
# ===========================================================================

# ---------------------------------------------------------------------------
# test_load_local_override_returns_none_when_dir_absent
# ---------------------------------------------------------------------------


def test_load_local_override_returns_none_when_dir_absent(
    isolated_paths: Path, tmp_path: Path
) -> None:
    """load_local_override returns None when given a path that does not exist."""
    nonexistent = tmp_path / "does_not_exist" / "catalog" / "overrides"
    result = load_local_override(nonexistent)
    assert result is None


# ---------------------------------------------------------------------------
# test_load_local_override_returns_tools_when_valid_yaml
# ---------------------------------------------------------------------------


def test_load_local_override_returns_tools_when_valid_yaml(
    isolated_paths: Path, tmp_path: Path
) -> None:
    """load_local_override returns a list containing the tool when a valid YAML file exists."""
    override_dir = tmp_path / "overrides"
    override_dir.mkdir(parents=True, exist_ok=True)

    tool_yaml = """\
schema_version: 1
key: mytool
name: My Tool
description: A custom override tool for testing
categories: [testing]
persona_tags: [backend]
managed: false
"""
    (override_dir / "mytool.yaml").write_text(tool_yaml, encoding="utf-8")

    result = load_local_override(override_dir)
    assert result is not None
    assert len(result) == 1
    assert result[0].key == "mytool"
    assert isinstance(result[0], ToolInfo)


# ---------------------------------------------------------------------------
# test_load_local_override_skips_invalid_yaml
# ---------------------------------------------------------------------------


def test_load_local_override_skips_invalid_yaml(isolated_paths: Path, tmp_path: Path) -> None:
    """load_local_override skips unparseable YAML files without raising.

    One valid and one invalid YAML file → result has exactly 1 tool.
    """
    override_dir = tmp_path / "overrides"
    override_dir.mkdir(parents=True, exist_ok=True)

    valid_yaml = """\
schema_version: 1
key: goodtool
name: Good Tool
description: Valid tool definition for testing
categories: [testing]
persona_tags: [backend]
managed: false
"""
    # Invalid: missing required fields (key, name, description, managed).
    invalid_yaml = """\
this_is: not a valid ToolInfo at all
random_garbage: 42
"""
    (override_dir / "goodtool.yaml").write_text(valid_yaml, encoding="utf-8")
    (override_dir / "badtool.yaml").write_text(invalid_yaml, encoding="utf-8")

    result = load_local_override(override_dir)
    assert result is not None, "Expected a non-None result since one valid tool exists"
    assert len(result) == 1, f"Expected 1 tool (the valid one), got {len(result)}"
    assert result[0].key == "goodtool"


# ---------------------------------------------------------------------------
# test_load_bundled_returns_tools
# ---------------------------------------------------------------------------


def test_load_bundled_returns_tools(isolated_paths: Path) -> None:
    """load_bundled() returns at least one ToolInfo and every item is a ToolInfo."""
    tools = load_bundled()
    assert len(tools) >= 1, "load_bundled() returned an empty list"
    for tool in tools:
        assert isinstance(tool, ToolInfo), f"Expected ToolInfo, got {type(tool)!r}"


# ---------------------------------------------------------------------------
# test_load_remote_returns_none_on_network_error
# ---------------------------------------------------------------------------


def test_load_remote_returns_none_on_network_error(isolated_paths: Path, tmp_path: Path) -> None:
    """load_remote returns None on a network failure without raising."""
    cache = tmp_path / "remote_cache"
    cache.mkdir(parents=True, exist_ok=True)

    # An invalid URL that will never resolve.
    result = load_remote(
        "http://127.0.0.1:0/catalog-index.yaml",
        cache,
        max_age_seconds=0,  # always attempt a fresh fetch
    )
    assert result is None
