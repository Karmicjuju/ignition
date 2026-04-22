from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ignition.core.health import HealthEngine
from ignition.schemas.health import CheckResult, FixType, HealthState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    check_id: str,
    category: str,
    state: HealthState,
) -> CheckResult:
    return CheckResult(
        category=category,
        check_id=check_id,
        label=check_id,
        state=state,
        detail="stub",
        fix_type=FixType.NONE,
    )


def _patch_all_scans(engine: HealthEngine, results: list[CheckResult]) -> None:
    """Replace every _scan_* method with an AsyncMock returning the given results."""
    categories = ["tools", "configs", "shell_integration", "permissions"]
    for cat in categories:
        method = f"_scan_{cat}"
        # Return only results for this category from the provided list
        cat_results = [r for r in results if r.category == cat]
        setattr(engine, method, AsyncMock(return_value=cat_results))


# ---------------------------------------------------------------------------
# T3-1: last_new_issues is empty when no previous_summary supplied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_new_issues_empty_without_previous_summary(isolated_paths: Path) -> None:
    engine = HealthEngine()
    _patch_all_scans(
        engine,
        [
            _make_result("tool_git", "tools", HealthState.NEEDS_ATTENTION),
            _make_result("config_aws_config", "configs", HealthState.NEEDS_ATTENTION),
        ],
    )

    await engine.run_scan()

    assert engine.last_new_issues == []


# ---------------------------------------------------------------------------
# T3-2: last_new_issues populated when category transitions from healthy to bad
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_new_issues_populated_for_new_bad_checks(isolated_paths: Path) -> None:
    engine = HealthEngine()
    _patch_all_scans(
        engine,
        [
            _make_result("tool_git", "tools", HealthState.NEEDS_ATTENTION),
            _make_result("config_aws_config", "configs", HealthState.HEALTHY),
        ],
    )

    # Previous summary says "tools" was healthy — so tool_git is newly bad
    previous_summary = {"tools": "healthy", "configs": "healthy"}

    await engine.run_scan(previous_summary=previous_summary)

    assert "tool_git" in engine.last_new_issues


# ---------------------------------------------------------------------------
# T3-3: checks already bad in previous_summary are NOT in last_new_issues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_new_issues_empty_when_already_bad(isolated_paths: Path) -> None:
    engine = HealthEngine()
    _patch_all_scans(
        engine,
        [
            _make_result("tool_git", "tools", HealthState.NEEDS_ATTENTION),
        ],
    )

    # Previous summary says "tools" was already needs_attention
    previous_summary = {"tools": "needs_attention"}

    await engine.run_scan(previous_summary=previous_summary)

    assert "tool_git" not in engine.last_new_issues
    assert engine.last_new_issues == []


# ---------------------------------------------------------------------------
# T3-4: second scan without previous_summary clears last_new_issues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_new_issues_cleared_on_next_scan_without_previous_summary(
    isolated_paths: Path,
) -> None:
    engine = HealthEngine()
    _patch_all_scans(
        engine,
        [
            _make_result("tool_git", "tools", HealthState.NEEDS_ATTENTION),
        ],
    )

    # First scan: with previous_summary so last_new_issues gets populated
    await engine.run_scan(previous_summary={"tools": "healthy"})
    assert "tool_git" in engine.last_new_issues

    # Second scan: no previous_summary, so last_new_issues must be cleared
    await engine.run_scan()
    assert engine.last_new_issues == []


# ---------------------------------------------------------------------------
# T3-5: RECOMMENDED state checks are NOT included in last_new_issues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_new_issues_only_includes_needs_attention_and_manual(
    isolated_paths: Path,
) -> None:
    engine = HealthEngine()
    _patch_all_scans(
        engine,
        [
            _make_result("tool_optional", "tools", HealthState.RECOMMENDED),
            _make_result("config_aws_config", "configs", HealthState.MANUAL),
        ],
    )

    # Both categories were previously healthy
    previous_summary = {"tools": "healthy", "configs": "healthy"}

    await engine.run_scan(previous_summary=previous_summary)

    # RECOMMENDED should NOT appear
    assert "tool_optional" not in engine.last_new_issues
    # MANUAL should appear (it is in the "bad" set)
    assert "config_aws_config" in engine.last_new_issues
