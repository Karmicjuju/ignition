from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ignition.core.self_updater as self_updater_mod
from ignition.core.self_updater import SelfUpdateInfo, SelfUpdater

# ---------------------------------------------------------------------------
# SelfUpdateInfo dataclass
# ---------------------------------------------------------------------------


def test_self_update_info_fields() -> None:
    info = SelfUpdateInfo(current_version="0.1.0", available_version="0.2.0")
    assert info.current_version == "0.1.0"
    assert info.available_version == "0.2.0"


# ---------------------------------------------------------------------------
# check() — up-to-date
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_returns_none_when_up_to_date(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from importlib.metadata import version as real_version

    try:
        current = real_version("ignition")
    except PackageNotFoundError:
        current = "0.1.0"
        monkeypatch.setattr(
            "ignition.core.self_updater.version",
            lambda _name: current,
        )

    monkeypatch.setattr(self_updater_mod, "_fetch_pypi_version", lambda url: current)

    updater = SelfUpdater()
    result = await updater.check()
    assert result is None


# ---------------------------------------------------------------------------
# check() — update available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_returns_info_when_update_available(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(self_updater_mod, "_fetch_pypi_version", lambda url: "99.0.0")

    updater = SelfUpdater()
    result = await updater.check()
    assert result is not None
    assert result.available_version == "99.0.0"


# ---------------------------------------------------------------------------
# check() — network failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_returns_none_on_network_failure(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(url: str) -> str:
        raise Exception("timeout")

    monkeypatch.setattr(self_updater_mod, "_fetch_pypi_version", _raise)

    updater = SelfUpdater()
    result = await updater.check()
    assert result is None


# ---------------------------------------------------------------------------
# check() — package not installed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_returns_none_when_package_not_found(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(_name: str) -> str:
        raise PackageNotFoundError("ignition")

    monkeypatch.setattr(self_updater_mod, "version", _raise)

    updater = SelfUpdater()
    result = await updater.check()
    assert result is None


# ---------------------------------------------------------------------------
# upgrade() — subprocess args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upgrade_calls_correct_subprocess(
    isolated_paths: Path,
) -> None:
    captured_args: list[str] = []

    async def _fake_exec(*args: str, **kwargs: object) -> object:
        captured_args.extend(args)
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"upgraded", b""))
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        updater = SelfUpdater()
        await updater.upgrade()

    assert "pipx" in captured_args
    assert "upgrade" in captured_args
    assert "ignition" in captured_args


# ---------------------------------------------------------------------------
# upgrade() — success / failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upgrade_returns_true_on_success(isolated_paths: Path) -> None:
    async def _fake_exec(*args: str, **kwargs: object) -> object:
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"already up-to-date", b""))
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        updater = SelfUpdater()
        success, output = await updater.upgrade()

    assert success is True
    assert isinstance(output, str)


@pytest.mark.asyncio
async def test_upgrade_returns_false_on_failure(isolated_paths: Path) -> None:
    async def _fake_exec(*args: str, **kwargs: object) -> object:
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(return_value=(b"", b"pipx error: something went wrong"))
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        updater = SelfUpdater()
        success, _output = await updater.upgrade()

    assert success is False


# ---------------------------------------------------------------------------
# check() — activity_log receives event when update available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_log_receives_check_event(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(self_updater_mod, "_fetch_pypi_version", lambda url: "99.0.0")

    activity_log = MagicMock()
    updater = SelfUpdater(activity_log=activity_log)
    result = await updater.check()

    assert result is not None
    activity_log.append.assert_called_once()
