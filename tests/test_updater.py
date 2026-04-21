"""Unit tests for UpdateEngine.

All installer calls are mocked. No real subprocesses are executed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ignition.core.updater import UpdateEngine, UpdateInfo
from ignition.schemas.catalog import (
    InstallMethod,
    InstallStatus,
    PlatformInstallMethods,
    ToolInfo,
)
from ignition.schemas.state import AppStateModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state() -> AppStateModel:
    return AppStateModel(install_id="test-id")


def _make_tool(
    key: str = "mytool",
    install_status: InstallStatus = InstallStatus.INSTALLED,
    version: str | None = "1.0.0",
    managed_version: str | None = "2.0.0",
    version_policy: str = "managed",
) -> ToolInfo:
    return ToolInfo(
        key=key,
        name=key.capitalize(),
        description=f"Test tool {key}",
        categories=["test"],
        persona_tags=["backend"],
        managed=True,
        install_status=install_status,
        version=version,
        managed_version=managed_version,
        version_policy=version_policy,
        install_methods=PlatformInstallMethods(),
    )


def _make_engine(
    tools: list[ToolInfo],
    install_side_effect: object = None,
) -> tuple[UpdateEngine, MagicMock]:
    catalog = MagicMock()
    catalog.get_all_tools.return_value = tools
    installer = MagicMock()
    from ignition.core.installer import InstallResult

    if install_side_effect is not None:
        installer.install = install_side_effect
    else:
        installer.install = AsyncMock(
            return_value=InstallResult(
                tool_key="mytool",
                success=True,
                method_used=InstallMethod.BREW,
                detected_version="2.0.0",
            )
        )
    engine = UpdateEngine(catalog=catalog, installer=installer)
    return engine, catalog


# ---------------------------------------------------------------------------
# check_updates — version comparison
# ---------------------------------------------------------------------------


def test_check_updates_detects_outdated(isolated_paths: Path) -> None:
    """check_updates returns UpdateInfo when installed < managed."""
    tool = _make_tool(version="1.0.0", managed_version="2.0.0")
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert len(updates) == 1
    assert updates[0].tool_key == "mytool"
    assert updates[0].installed_version == "1.0.0"
    assert updates[0].available_version == "2.0.0"


def test_check_updates_no_update_when_equal(isolated_paths: Path) -> None:
    """check_updates returns empty list when installed == managed."""
    tool = _make_tool(version="2.0.0", managed_version="2.0.0")
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert updates == []


def test_check_updates_no_update_when_newer(isolated_paths: Path) -> None:
    """check_updates returns empty list when installed > managed (downgrade not triggered)."""
    tool = _make_tool(version="3.0.0", managed_version="2.0.0")
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert updates == []


def test_check_updates_semver_minor_bump(isolated_paths: Path) -> None:
    """check_updates handles minor version bump correctly."""
    tool = _make_tool(version="1.2.3", managed_version="1.3.0")
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert len(updates) == 1


def test_check_updates_semver_patch_bump(isolated_paths: Path) -> None:
    """check_updates handles patch version bump correctly."""
    tool = _make_tool(version="1.2.3", managed_version="1.2.4")
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert len(updates) == 1


# ---------------------------------------------------------------------------
# check_updates — exclusion rules
# ---------------------------------------------------------------------------


def test_check_updates_excludes_flexible_tier(isolated_paths: Path) -> None:
    """Flexible-tier tools are never included in update list."""
    tool = _make_tool(version="1.0.0", managed_version="2.0.0", version_policy="flexible")
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert updates == []


def test_check_updates_excludes_not_installed(isolated_paths: Path) -> None:
    """Tools with MISSING status are excluded from update check."""
    tool = _make_tool(
        install_status=InstallStatus.MISSING,
        version=None,
        managed_version="2.0.0",
    )
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert updates == []


def test_check_updates_excludes_when_no_version(isolated_paths: Path) -> None:
    """Tools with no installed version string are excluded."""
    tool = _make_tool(version=None, managed_version="2.0.0")
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert updates == []


def test_check_updates_excludes_when_no_managed_version(isolated_paths: Path) -> None:
    """Tools with no managed_version are excluded."""
    tool = _make_tool(version="1.0.0", managed_version=None)
    engine, _ = _make_engine([tool])
    updates = engine.check_updates()
    assert updates == []


def test_check_updates_multiple_tools(isolated_paths: Path) -> None:
    """check_updates returns one UpdateInfo per outdated tool."""
    t1 = _make_tool(key="tool1", version="1.0.0", managed_version="2.0.0")
    t2 = _make_tool(key="tool2", version="3.0.0", managed_version="3.0.0")
    t3 = _make_tool(key="tool3", version="1.0.0", managed_version="1.5.0")
    engine, _ = _make_engine([t1, t2, t3])
    updates = engine.check_updates()
    assert len(updates) == 2
    keys = {u.tool_key for u in updates}
    assert keys == {"tool1", "tool3"}


# ---------------------------------------------------------------------------
# check_updates — invalid version strings
# ---------------------------------------------------------------------------


def test_check_updates_skips_invalid_version_string(isolated_paths: Path) -> None:
    """Tools with unparseable version strings are skipped without raising."""
    tool = _make_tool(version="not-a-version", managed_version="2.0.0")
    engine, _ = _make_engine([tool])
    # Should not raise
    updates = engine.check_updates()
    assert updates == []


# ---------------------------------------------------------------------------
# update_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tool_calls_installer(isolated_paths: Path) -> None:
    """update_tool delegates to InstallerEngine.install."""
    from ignition.core.installer import InstallResult

    tool = _make_tool()
    catalog = MagicMock()
    catalog.get_all_tools.return_value = [tool]
    installer = MagicMock()
    install_result = InstallResult(
        tool_key="mytool", success=True, method_used=InstallMethod.BREW, detected_version="2.0.0"
    )
    installer.install = AsyncMock(return_value=install_result)
    engine = UpdateEngine(catalog=catalog, installer=installer)

    result = await engine.update_tool("mytool")

    installer.install.assert_awaited_once_with(tool)
    assert result.success is True


@pytest.mark.asyncio
async def test_update_tool_unknown_key_returns_failure(isolated_paths: Path) -> None:
    """update_tool returns failure result when tool_key is not in catalog."""
    engine, _ = _make_engine([])
    result = await engine.update_tool("nonexistent")
    assert result.success is False
    assert result.tool_key == "nonexistent"
    assert "not found" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_update_tool_emits_activity_event_on_success(isolated_paths: Path) -> None:
    """update_tool emits TOOL_UPDATE SUCCESS event via ActivityLog."""
    from ignition.core.installer import InstallResult

    tool = _make_tool()
    catalog = MagicMock()
    catalog.get_all_tools.return_value = [tool]
    installer = MagicMock()
    installer.install = AsyncMock(
        return_value=InstallResult(
            tool_key="mytool",
            success=True,
            method_used=InstallMethod.BREW,
            detected_version="2.0.0",
        )
    )
    activity_log = MagicMock()
    engine = UpdateEngine(catalog=catalog, installer=installer, activity_log=activity_log)

    await engine.update_tool("mytool")

    activity_log.append.assert_called_once()
    args, _kwargs = activity_log.append.call_args
    from ignition.schemas.activity import EventType, Outcome

    assert args[0] == EventType.TOOL_UPDATE
    assert args[1] == Outcome.SUCCESS


@pytest.mark.asyncio
async def test_update_tool_emits_activity_event_on_failure(isolated_paths: Path) -> None:
    """update_tool emits TOOL_UPDATE FAILURE event via ActivityLog."""
    from ignition.core.installer import InstallResult

    tool = _make_tool()
    catalog = MagicMock()
    catalog.get_all_tools.return_value = [tool]
    installer = MagicMock()
    installer.install = AsyncMock(
        return_value=InstallResult(
            tool_key="mytool",
            success=False,
            method_used=InstallMethod.BREW,
            error="Network error",
        )
    )
    activity_log = MagicMock()
    engine = UpdateEngine(catalog=catalog, installer=installer, activity_log=activity_log)

    await engine.update_tool("mytool")

    from ignition.schemas.activity import EventType, Outcome

    args, _ = activity_log.append.call_args
    assert args[0] == EventType.TOOL_UPDATE
    assert args[1] == Outcome.FAILURE


# ---------------------------------------------------------------------------
# update_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_all_sequential_flow(isolated_paths: Path) -> None:
    """update_all processes all outdated tools in sequence and returns results."""
    from ignition.core.installer import InstallResult

    t1 = _make_tool(key="tool1", version="1.0.0", managed_version="2.0.0")
    t2 = _make_tool(key="tool2", version="1.0.0", managed_version="2.0.0")
    catalog = MagicMock()
    catalog.get_all_tools.return_value = [t1, t2]
    installer = MagicMock()

    call_order: list[str] = []

    async def mock_install(tool: ToolInfo) -> InstallResult:
        call_order.append(tool.key)
        return InstallResult(tool_key=tool.key, success=True, method_used=InstallMethod.BREW)

    installer.install = mock_install
    engine = UpdateEngine(catalog=catalog, installer=installer)

    results = await engine.update_all()

    assert len(results) == 2
    assert all(r.success for r in results)
    # Sequential — tool1 before tool2
    assert call_order == ["tool1", "tool2"]


@pytest.mark.asyncio
async def test_update_all_progress_cb_called(isolated_paths: Path) -> None:
    """update_all invokes progress_cb after each tool update."""
    from ignition.core.installer import InstallResult

    tool = _make_tool()
    catalog = MagicMock()
    catalog.get_all_tools.return_value = [tool]
    installer = MagicMock()
    installer.install = AsyncMock(
        return_value=InstallResult(tool_key="mytool", success=True, method_used=InstallMethod.BREW)
    )
    engine = UpdateEngine(catalog=catalog, installer=installer)

    progress_calls: list[tuple[str, str]] = []
    await engine.update_all(progress_cb=lambda k, s: progress_calls.append((k, s)))

    assert len(progress_calls) == 1
    assert progress_calls[0][0] == "mytool"
    assert progress_calls[0][1] == "updated"


@pytest.mark.asyncio
async def test_update_all_empty_when_no_updates(isolated_paths: Path) -> None:
    """update_all returns empty list when check_updates finds nothing."""
    # All tools up to date
    tool = _make_tool(version="2.0.0", managed_version="2.0.0")
    engine, _ = _make_engine([tool])
    results = await engine.update_all()
    assert results == []


@pytest.mark.asyncio
async def test_update_all_continues_after_failure(isolated_paths: Path) -> None:
    """update_all does not abort when one update fails."""
    from ignition.core.installer import InstallResult

    t1 = _make_tool(key="tool1", version="1.0.0", managed_version="2.0.0")
    t2 = _make_tool(key="tool2", version="1.0.0", managed_version="2.0.0")
    catalog = MagicMock()
    catalog.get_all_tools.return_value = [t1, t2]
    installer = MagicMock()

    async def mock_install(tool: ToolInfo) -> InstallResult:
        if tool.key == "tool1":
            return InstallResult(
                tool_key="tool1", success=False, method_used=InstallMethod.BREW, error="fail"
            )
        return InstallResult(tool_key="tool2", success=True, method_used=InstallMethod.BREW)

    installer.install = mock_install
    engine = UpdateEngine(catalog=catalog, installer=installer)

    results = await engine.update_all()

    assert len(results) == 2
    assert results[0].success is False
    assert results[1].success is True


# ---------------------------------------------------------------------------
# UpdateInfo dataclass
# ---------------------------------------------------------------------------


def test_update_info_fields() -> None:
    """UpdateInfo stores all expected fields."""
    info = UpdateInfo(tool_key="mytool", installed_version="1.0.0", available_version="2.0.0")
    assert info.tool_key == "mytool"
    assert info.installed_version == "1.0.0"
    assert info.available_version == "2.0.0"
