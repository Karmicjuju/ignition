"""Unit tests for InstallerEngine.

All subprocess calls are mocked. No real install operations are performed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ignition.core.installer import InstallerEngine, InstallResult
from ignition.schemas.catalog import (
    InstallMethod,
    InstallStep,
    PlatformInstallMethods,
    ToolInfo,
)
from ignition.schemas.state import AppStateModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(isolated_paths: Path) -> AppStateModel:
    return AppStateModel(install_id="test-install-id")


def _make_tool(
    key: str = "mytool",
    health_check: str = "",
    requires_sudo: bool = False,
    macos_steps: list[InstallStep] | None = None,
    linux_steps: list[InstallStep] | None = None,
) -> ToolInfo:
    return ToolInfo(
        key=key,
        name=key.capitalize(),
        description=f"Test tool {key}",
        categories=["testing"],
        persona_tags=["backend"],
        managed=True,
        health_check=health_check,
        requires_sudo=requires_sudo,
        install_methods=PlatformInstallMethods(
            macos=macos_steps or [],
            linux=linux_steps or [],
        ),
    )


def _brew_step(formula: str = "mytool", cask: bool = False) -> InstallStep:
    return InstallStep(method=InstallMethod.BREW, package=formula, cask=cask)


def _apt_step(package: str = "mytool") -> InstallStep:
    return InstallStep(method=InstallMethod.APT, package=package)


def _binary_step(
    url: str = "https://example.com/mytool",
    binary_name: str = "mytool",
) -> InstallStep:
    return InstallStep(method=InstallMethod.BINARY, url=url, binary_name=binary_name)


# ---------------------------------------------------------------------------
# resolve_method — macOS
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only resolve tests")
def test_resolve_method_brew_when_brew_available(isolated_paths: Path) -> None:
    """On macOS with brew present and a brew step, BREW is returned."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = True

    tool = _make_tool(macos_steps=[_brew_step()])
    assert engine.resolve_method(tool) == InstallMethod.BREW


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only resolve tests")
def test_resolve_method_binary_when_brew_absent(isolated_paths: Path) -> None:
    """On macOS without brew, falls back to BINARY if a binary step is present."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = False

    tool = _make_tool(macos_steps=[_brew_step(), _binary_step()])
    assert engine.resolve_method(tool) == InstallMethod.BINARY


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only resolve tests")
def test_resolve_method_copy_paste_when_no_method_macos(isolated_paths: Path) -> None:
    """On macOS with no suitable step, falls back to COPY_PASTE."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = False

    tool = _make_tool(macos_steps=[])
    assert engine.resolve_method(tool) == InstallMethod.COPY_PASTE


# ---------------------------------------------------------------------------
# resolve_method — Linux
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only resolve tests")
def test_resolve_method_apt_on_linux(isolated_paths: Path) -> None:
    """On Linux with apt step and no requires_sudo, APT is returned."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    tool = _make_tool(linux_steps=[_apt_step()])
    assert engine.resolve_method(tool) == InstallMethod.APT


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only resolve tests")
def test_resolve_method_copy_paste_when_requires_sudo_linux(isolated_paths: Path) -> None:
    """On Linux with requires_sudo=True, APT step → COPY_PASTE."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    tool = _make_tool(linux_steps=[_apt_step()], requires_sudo=True)
    assert engine.resolve_method(tool) == InstallMethod.COPY_PASTE


# ---------------------------------------------------------------------------
# resolve_method — cross-platform (mock sys.platform)
# ---------------------------------------------------------------------------


def test_resolve_method_brew_returns_brew(isolated_paths: Path) -> None:
    """resolve_method returns BREW on mocked macOS with brew available + brew step."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = True

    tool = _make_tool(macos_steps=[_brew_step()])
    with patch("ignition.core.installer.sys") as mock_sys:
        mock_sys.platform = "darwin"
        result = engine.resolve_method(tool)
    assert result == InstallMethod.BREW


def test_resolve_method_apt_returns_apt(isolated_paths: Path) -> None:
    """resolve_method returns APT on mocked Linux with apt step, no sudo."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    tool = _make_tool(linux_steps=[_apt_step()])
    with patch("ignition.core.installer.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = engine.resolve_method(tool)
    assert result == InstallMethod.APT


def test_resolve_method_binary_fallback_linux(isolated_paths: Path) -> None:
    """On Linux without apt step, binary step → BINARY."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    tool = _make_tool(linux_steps=[_binary_step()])
    with patch("ignition.core.installer.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = engine.resolve_method(tool)
    assert result == InstallMethod.BINARY


# ---------------------------------------------------------------------------
# Brew cache (_brew_available)
# ---------------------------------------------------------------------------


def test_brew_available_caches_result(isolated_paths: Path) -> None:
    """_is_brew_available() calls shutil.which exactly once regardless of call count."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    with patch("shutil.which", return_value="/usr/local/bin/brew") as mock_which:
        first = engine._is_brew_available()
        second = engine._is_brew_available()

    assert first is True
    assert second is True
    # shutil.which should only be called once (cached after first call)
    mock_which.assert_called_once_with("brew")


# ---------------------------------------------------------------------------
# install — brew success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_brew_success(isolated_paths: Path) -> None:
    """Brew install success: result.success is True, event recorded in state."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = True

    tool = _make_tool(
        macos_steps=[_brew_step("mytool")],
        health_check="mytool --version",
    )

    async def mock_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[:2] == ["brew", "install"]:
            return (0, "Installed mytool", "")
        if args[0] == "mytool":
            return (0, "mytool 1.2.3", "")
        return (0, "", "")

    with (
        patch("ignition.core.installer.sys") as mock_sys,
        patch("ignition.core.installer._run_subprocess", side_effect=mock_subprocess),
    ):
        mock_sys.platform = "darwin"
        result = await engine.install(tool)

    assert result.success is True
    assert result.method_used == InstallMethod.BREW
    assert result.detected_version == "mytool 1.2.3"
    assert len(state.install_history) == 1
    assert state.install_history[0].tool_key == "mytool"
    assert state.install_history[0].success is True


# ---------------------------------------------------------------------------
# install — brew failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_brew_failure(isolated_paths: Path) -> None:
    """Brew install failure: result.success is False, error is set."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = True

    tool = _make_tool(macos_steps=[_brew_step("mytool")])

    async def mock_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[:2] == ["brew", "install"]:
            return (1, "", "Error: formula not found")
        return (0, "", "")

    with (
        patch("ignition.core.installer.sys") as mock_sys,
        patch("ignition.core.installer._run_subprocess", side_effect=mock_subprocess),
    ):
        mock_sys.platform = "darwin"
        result = await engine.install(tool)

    assert result.success is False
    assert "not found" in (result.error or "")
    assert len(state.install_history) == 1
    assert state.install_history[0].success is False


# ---------------------------------------------------------------------------
# install — binary no URL → FAILED immediately
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_binary_no_url_fails(isolated_paths: Path) -> None:
    """Binary install with no URL in manifest returns success=False immediately."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    # Binary step with no URL
    step = InstallStep(method=InstallMethod.BINARY, url="", binary_name="mytool")
    tool = _make_tool(linux_steps=[step])

    with patch("ignition.core.installer.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = await engine.install(tool)

    assert result.success is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# install — binary success path with PATH warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_binary_success_path_warning(isolated_paths: Path, tmp_path: Path) -> None:
    """Binary install emits PATH warning when ~/.local/bin is not on PATH."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    dest_dir = tmp_path / ".local" / "bin"
    tool = _make_tool(linux_steps=[_binary_step(url="https://example.com/mytool")])
    messages: list[str] = []

    async def mock_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "curl":
            # Simulate download by touching the dest file
            dest = Path(args[args.index("-o") + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("#!/bin/sh\necho mytool 1.0\n")
            return (0, "", "")
        return (0, "", "")

    import os

    with (
        patch("ignition.core.installer.sys") as mock_sys,
        patch("ignition.core.installer._run_subprocess", side_effect=mock_subprocess),
        patch("ignition.core.installer._LOCAL_BIN", dest_dir),
        patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}, clear=False),
    ):
        mock_sys.platform = "linux"
        result = await engine.install(tool, progress_cb=messages.append)

    assert result.success is True
    assert any("PATH" in m for m in messages), "Expected PATH warning in progress messages"


# ---------------------------------------------------------------------------
# apt_updated cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apt_updated_runs_only_once(isolated_paths: Path) -> None:
    """apt-get update is invoked exactly once across two sequential installs."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)

    tool_a = _make_tool(key="toola", linux_steps=[_apt_step("toola")])
    tool_b = _make_tool(key="toolb", linux_steps=[_apt_step("toolb")])

    calls: list[list[str]] = []

    async def mock_subprocess(args: list[str]) -> tuple[int, str, str]:
        calls.append(args)
        return (0, "ok", "")

    with (
        patch("ignition.core.installer.sys") as mock_sys,
        patch("ignition.core.installer._run_subprocess", side_effect=mock_subprocess),
    ):
        mock_sys.platform = "linux"
        await engine.install(tool_a)
        await engine.install(tool_b)

    update_calls = [c for c in calls if c[:2] == ["apt-get", "update"]]
    assert len(update_calls) == 1, f"Expected exactly 1 apt-get update, got {len(update_calls)}"


# ---------------------------------------------------------------------------
# install_bundle — sequential + partial failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_bundle_sequential_partial_failure(isolated_paths: Path) -> None:
    """install_bundle continues after a failure and returns all results."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = True

    tool_ok = _make_tool(key="goodtool", macos_steps=[_brew_step("goodtool")])
    tool_fail = _make_tool(key="badtool", macos_steps=[_brew_step("badtool")])

    async def mock_subprocess(args: list[str]) -> tuple[int, str, str]:
        if "goodtool" in str(args):
            return (0, "Installed goodtool", "")
        if "badtool" in str(args):
            return (1, "", "Error: badtool not found")
        return (0, "", "")

    with (
        patch("ignition.core.installer.sys") as mock_sys,
        patch("ignition.core.installer._run_subprocess", side_effect=mock_subprocess),
    ):
        mock_sys.platform = "darwin"
        results = await engine.install_bundle([tool_ok, tool_fail])

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False
    # State records both events
    assert len(state.install_history) == 2


# ---------------------------------------------------------------------------
# install_history capped at 100
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_history_capped_at_100(isolated_paths: Path) -> None:
    """install_history is capped at 100 entries; oldest entries are dropped."""
    state = _make_state(isolated_paths)
    engine = InstallerEngine(state)
    engine._brew_available = True

    tool = _make_tool(macos_steps=[_brew_step()])

    async def mock_subprocess(args: list[str]) -> tuple[int, str, str]:
        return (0, "ok", "")

    with (
        patch("ignition.core.installer.sys") as mock_sys,
        patch("ignition.core.installer._run_subprocess", side_effect=mock_subprocess),
    ):
        mock_sys.platform = "darwin"
        for _ in range(105):
            await engine.install(tool)

    assert len(state.install_history) <= 100


# ---------------------------------------------------------------------------
# InstallResult dataclass fields
# ---------------------------------------------------------------------------


def test_install_result_fields() -> None:
    """InstallResult stores all expected fields with correct defaults."""
    r = InstallResult(
        tool_key="mytool",
        success=True,
        method_used=InstallMethod.BREW,
    )
    assert r.tool_key == "mytool"
    assert r.success is True
    assert r.method_used == InstallMethod.BREW
    assert r.error is None
    assert r.detected_version is None
