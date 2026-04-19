from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ignition.core.health import HealthEngine
from ignition.schemas.health import CheckResult, FixType, HealthState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine() -> HealthEngine:
    return HealthEngine()


# ---------------------------------------------------------------------------
# Tools category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tools_healthy_when_binary_present(isolated_paths: Path) -> None:
    """All tools show HEALTHY when which succeeds and health_check succeeds."""
    engine = _make_engine()

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "which":
            return (0, f"/usr/bin/{args[1]}", "")
        # health_check invocation
        return (0, f"{args[0]} version 1.0.0", "")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        results = await engine.run_scan(categories=["tools"])

    assert results, "Expected at least one tool result"
    for r in results:
        assert r.state == HealthState.HEALTHY, f"{r.check_id} should be HEALTHY, got {r.state}"
        assert r.category == "tools"


@pytest.mark.asyncio
async def test_tools_needs_attention_when_managed_binary_absent(isolated_paths: Path) -> None:
    """A managed tool with absent binary reports NEEDS_ATTENTION."""
    engine = _make_engine()

    # Mock catalog to return a single managed tool
    mock_tool = MagicMock()
    mock_tool.key = "kubectl"
    mock_tool.name = "kubectl"
    mock_tool.managed = True
    mock_tool.health_check = "kubectl version --client"
    engine._catalog = MagicMock()
    engine._catalog.get_all_tools.return_value = [mock_tool]

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "which":
            return (1, "", "not found")
        return (0, "v1.28.0", "")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        results = await engine.run_scan(categories=["tools"])

    assert len(results) == 1
    assert results[0].state == HealthState.NEEDS_ATTENTION
    assert results[0].fix_type == FixType.NONE


@pytest.mark.asyncio
async def test_tools_recommended_when_unmanaged_binary_absent(isolated_paths: Path) -> None:
    """An unmanaged tool with absent binary reports RECOMMENDED."""
    engine = _make_engine()

    mock_tool = MagicMock()
    mock_tool.key = "trivy"
    mock_tool.name = "Trivy"
    mock_tool.managed = False
    mock_tool.health_check = "trivy --version"
    engine._catalog = MagicMock()
    engine._catalog.get_all_tools.return_value = [mock_tool]

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "which":
            return (1, "", "not found")
        return (0, "", "")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        results = await engine.run_scan(categories=["tools"])

    assert len(results) == 1
    assert results[0].state == HealthState.RECOMMENDED
    assert results[0].fix_type == FixType.NONE


@pytest.mark.asyncio
async def test_tools_recommended_when_health_check_fails(isolated_paths: Path) -> None:
    """A tool whose health_check command fails reports RECOMMENDED."""
    engine = _make_engine()

    mock_tool = MagicMock()
    mock_tool.key = "docker"
    mock_tool.name = "Docker"
    mock_tool.managed = True
    mock_tool.health_check = "docker --version"
    engine._catalog = MagicMock()
    engine._catalog.get_all_tools.return_value = [mock_tool]

    call_count = 0

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        nonlocal call_count
        call_count += 1
        if args[0] == "which":
            return (0, "/usr/local/bin/docker", "")
        # health_check fails
        return (1, "", "Cannot connect to the Docker daemon")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        results = await engine.run_scan(categories=["tools"])

    assert len(results) == 1
    assert results[0].state == HealthState.RECOMMENDED


@pytest.mark.asyncio
async def test_tools_exception_caught_as_needs_attention(isolated_paths: Path) -> None:
    """An exception in a tool check is caught and reported as NEEDS_ATTENTION."""
    engine = _make_engine()

    mock_tool = MagicMock()
    mock_tool.key = "git"
    mock_tool.name = "Git"
    mock_tool.managed = False
    mock_tool.health_check = "git --version"
    engine._catalog = MagicMock()
    engine._catalog.get_all_tools.return_value = [mock_tool]

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        raise RuntimeError("unexpected subprocess error")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        results = await engine.run_scan(categories=["tools"])

    # Exception should be caught and surfaced, not re-raised
    assert len(results) == 1
    assert results[0].state == HealthState.NEEDS_ATTENTION


# ---------------------------------------------------------------------------
# Configs category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_configs_healthy_when_marker_present(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HEALTHY when shell config contains '# ignition' marker."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    zshrc = fake_home / ".zshrc"
    zshrc.write_text("export PATH=$PATH\n# ignition\n", encoding="utf-8")

    monkeypatch.setenv("SHELL", "/bin/zsh")

    engine = _make_engine()
    engine._catalog = MagicMock()
    engine._catalog.get_all_tools.return_value = []

    with patch("ignition.core.health.Path") as mock_path_cls:
        mock_path_cls.home.return_value = fake_home
        # Passthrough for other Path() uses
        mock_path_cls.side_effect = lambda *a, **kw: Path(*a, **kw)
        mock_path_cls.home = MagicMock(return_value=fake_home)

        results = await engine.run_scan(categories=["configs"])

    marker_results = [r for r in results if r.check_id == "config_ignition_marker"]
    assert marker_results, "Expected config_ignition_marker result"
    assert marker_results[0].state == HealthState.HEALTHY


@pytest.mark.asyncio
async def test_configs_recommended_when_marker_absent(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RECOMMENDED when no shell config contains '# ignition' marker."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    zshrc = fake_home / ".zshrc"
    zshrc.write_text("export PATH=$PATH\n", encoding="utf-8")

    monkeypatch.setenv("SHELL", "/bin/zsh")

    engine = _make_engine()
    engine._catalog = MagicMock()
    engine._catalog.get_all_tools.return_value = []

    with patch("ignition.core.health.Path") as mock_path_cls:
        mock_path_cls.home = MagicMock(return_value=fake_home)
        mock_path_cls.side_effect = lambda *a, **kw: Path(*a, **kw)

        results = await engine.run_scan(categories=["configs"])

    marker_results = [r for r in results if r.check_id == "config_ignition_marker"]
    assert marker_results
    assert marker_results[0].state == HealthState.RECOMMENDED
    assert marker_results[0].fix_type == FixType.COPY_PASTE


@pytest.mark.asyncio
async def test_configs_all_four_categories_run(isolated_paths: Path) -> None:
    """run_scan with all categories returns results from all four category buckets."""
    engine = _make_engine()

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "which":
            return (0, f"/usr/bin/{args[1]}", "")
        return (0, "version output", "")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        results = await engine.run_scan()

    categories_found = {r.category for r in results}
    assert "tools" in categories_found
    assert "configs" in categories_found
    assert "shell_integration" in categories_found
    assert "permissions" in categories_found


# ---------------------------------------------------------------------------
# Shell integration category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shell_integration_healthy_when_local_bin_on_path(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """shell_local_bin_path is HEALTHY when ~/.local/bin is on PATH."""
    fake_home = tmp_path / "home"
    local_bin = fake_home / ".local" / "bin"
    local_bin.mkdir(parents=True)

    monkeypatch.setenv("PATH", str(local_bin) + ":/usr/bin:/bin")

    engine = _make_engine()

    with patch("ignition.core.health.Path") as mock_path_cls:
        mock_path_cls.home = MagicMock(return_value=fake_home)
        mock_path_cls.side_effect = lambda *a, **kw: Path(*a, **kw)

        results = await engine.run_scan(categories=["shell_integration"])

    path_results = [r for r in results if r.check_id == "shell_local_bin_path"]
    assert path_results
    assert path_results[0].state == HealthState.HEALTHY


@pytest.mark.asyncio
async def test_shell_integration_recommended_when_local_bin_not_on_path(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """shell_local_bin_path is RECOMMENDED with COPY_PASTE fix when not on PATH."""
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True)

    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    engine = _make_engine()

    with patch("ignition.core.health.Path") as mock_path_cls:
        mock_path_cls.home = MagicMock(return_value=fake_home)
        mock_path_cls.side_effect = lambda *a, **kw: Path(*a, **kw)

        results = await engine.run_scan(categories=["shell_integration"])

    path_results = [r for r in results if r.check_id == "shell_local_bin_path"]
    assert path_results
    r = path_results[0]
    assert r.state == HealthState.RECOMMENDED
    assert r.fix_type == FixType.COPY_PASTE
    assert r.fix_command is not None
    assert "$HOME/.local/bin" in r.fix_command


# ---------------------------------------------------------------------------
# Permissions category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permissions_healthy_when_ssh_key_correct_mode(
    isolated_paths: Path, tmp_path: Path
) -> None:
    """SSH private key with mode 0o600 reports HEALTHY."""
    fake_home = tmp_path / "home"
    ssh_dir = fake_home / ".ssh"
    ssh_dir.mkdir(parents=True)
    key_file = ssh_dir / "id_rsa"
    key_file.write_text("FAKE PRIVATE KEY", encoding="utf-8")
    key_file.chmod(0o600)

    engine = _make_engine()

    with patch("ignition.core.health.Path") as mock_path_cls:
        mock_path_cls.home = MagicMock(return_value=fake_home)
        mock_path_cls.side_effect = lambda *a, **kw: Path(*a, **kw)

        results = await engine.run_scan(categories=["permissions"])

    ssh_results = [r for r in results if "id_rsa" in r.check_id]
    assert ssh_results
    assert ssh_results[0].state == HealthState.HEALTHY


@pytest.mark.asyncio
async def test_permissions_needs_attention_when_ssh_key_wrong_mode(
    isolated_paths: Path, tmp_path: Path
) -> None:
    """SSH private key with mode 0o644 (too permissive) reports NEEDS_ATTENTION."""
    fake_home = tmp_path / "home"
    ssh_dir = fake_home / ".ssh"
    ssh_dir.mkdir(parents=True)
    key_file = ssh_dir / "id_rsa"
    key_file.write_text("FAKE PRIVATE KEY", encoding="utf-8")
    key_file.chmod(0o644)  # too permissive for a private key

    engine = _make_engine()

    with patch("ignition.core.health.Path") as mock_path_cls:
        mock_path_cls.home = MagicMock(return_value=fake_home)
        mock_path_cls.side_effect = lambda *a, **kw: Path(*a, **kw)

        results = await engine.run_scan(categories=["permissions"])

    ssh_results = [r for r in results if "id_rsa" in r.check_id]
    assert ssh_results
    assert ssh_results[0].state == HealthState.NEEDS_ATTENTION


# ---------------------------------------------------------------------------
# apply_fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_fix_auto_chmod_succeeds(isolated_paths: Path, tmp_path: Path) -> None:
    """apply_fix returns True and corrects permissions for an AUTO fix on a user-owned file."""
    fake_home = tmp_path / "home"
    ssh_dir = fake_home / ".ssh"
    ssh_dir.mkdir(parents=True)
    key_file = ssh_dir / "id_rsa"
    key_file.write_text("FAKE PRIVATE KEY", encoding="utf-8")
    key_file.chmod(0o644)

    engine = _make_engine()

    with patch("ignition.core.health.Path") as mock_path_cls:
        mock_path_cls.home = MagicMock(return_value=fake_home)
        mock_path_cls.side_effect = lambda *a, **kw: Path(*a, **kw)

        await engine.run_scan(categories=["permissions"])

    # Find the check_id for the key we created
    check_id = next(
        (k for k in engine._last_results if "id_rsa" in k),
        None,
    )
    assert check_id is not None, "Expected a result for id_rsa"

    result = engine._last_results[check_id]
    if result.fix_type != FixType.AUTO:
        pytest.skip("File not user-owned in this test environment — AUTO fix not available")

    success = await engine.apply_fix(check_id)
    assert success is True

    actual_mode = stat.S_IMODE(key_file.stat().st_mode)
    assert actual_mode == 0o600, f"Expected 0o600, got {oct(actual_mode)}"


@pytest.mark.asyncio
async def test_apply_fix_returns_false_for_copy_paste(isolated_paths: Path) -> None:
    """apply_fix returns False for COPY_PASTE fix type (user must act)."""
    engine = _make_engine()

    # Manually inject a COPY_PASTE result
    from ignition.schemas.health import FixType, HealthState

    engine._last_results["shell_local_bin_path"] = CheckResult(
        category="shell_integration",
        check_id="shell_local_bin_path",
        label="~/.local/bin on PATH",
        state=HealthState.RECOMMENDED,
        detail="Not on PATH",
        fix_type=FixType.COPY_PASTE,
        fix_command='export PATH="$HOME/.local/bin:$PATH"',
    )

    success = await engine.apply_fix("shell_local_bin_path")
    assert success is False


@pytest.mark.asyncio
async def test_apply_fix_returns_false_for_unknown_check_id(isolated_paths: Path) -> None:
    """apply_fix returns False when check_id is not in last results."""
    engine = _make_engine()
    success = await engine.apply_fix("nonexistent_check_id")
    assert success is False


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_persists_last_health_scan_timestamp(isolated_paths: Path) -> None:
    """run_scan updates AppStateModel.last_health_scan after completing."""
    from ignition.core.state import load_state

    engine = _make_engine()

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "which":
            return (0, f"/usr/bin/{args[1]}", "")
        return (0, "version output", "")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        await engine.run_scan()

    state = load_state()
    assert state.last_health_scan is not None, "last_health_scan should be set after scan"


@pytest.mark.asyncio
async def test_scan_populates_health_summary(isolated_paths: Path) -> None:
    """run_scan populates health_summary with per-category worst state."""
    from ignition.core.state import load_state

    engine = _make_engine()

    mock_tool = MagicMock()
    mock_tool.key = "missing_tool"
    mock_tool.name = "Missing Tool"
    mock_tool.managed = True
    mock_tool.health_check = ""
    engine._catalog = MagicMock()
    engine._catalog.get_all_tools.return_value = [mock_tool]

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "which":
            return (1, "", "not found")
        return (0, "", "")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        await engine.run_scan(categories=["tools"])

    state = load_state()
    assert "tools" in state.health_summary
    assert state.health_summary["tools"] == HealthState.NEEDS_ATTENTION


# ---------------------------------------------------------------------------
# Concurrent execution (asyncio.gather smoke test)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_runs_all_categories_concurrently(isolated_paths: Path) -> None:
    """run_scan with no categories argument returns results for all four categories."""
    engine = _make_engine()

    async def mock_run_subprocess(args: list[str]) -> tuple[int, str, str]:
        if args[0] == "which":
            return (0, f"/usr/bin/{args[1]}", "")
        return (0, "version output", "")

    with patch("ignition.core.health._run_subprocess", side_effect=mock_run_subprocess):
        results = await engine.run_scan()

    categories = {r.category for r in results}
    assert len(categories) == 4, f"Expected 4 categories, got: {categories}"
