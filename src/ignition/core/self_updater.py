from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING
from urllib.request import Request, urlopen

from packaging.version import Version

from ignition.core.logging import get_logger
from ignition.schemas.activity import EventType, Outcome

if TYPE_CHECKING:
    from ignition.core.activity import ActivityLog

PYPI_URL = "https://pypi.org/pypi/ignition/json"


@dataclass
class SelfUpdateInfo:
    """Describes an available self-update for the Ignition package itself."""

    current_version: str
    available_version: str


class SelfUpdater:
    """Checks PyPI for a newer version of Ignition and applies upgrades via pipx.

    Args:
        activity_log: Optional ActivityLog for recording check/upgrade events.
    """

    def __init__(self, activity_log: ActivityLog | None = None) -> None:
        self._activity_log = activity_log
        self._log = get_logger("ignition.core.self_updater")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check(self) -> SelfUpdateInfo | None:
        """Check PyPI for a newer version of the Ignition package.

        Resolves the currently installed version via ``importlib.metadata``,
        fetches the latest version from PyPI (with a 5-second timeout), and
        compares using ``packaging.version.Version``.

        Returns:
            A ``SelfUpdateInfo`` when a newer version is available on PyPI,
            or ``None`` when already up-to-date, the package is not installed,
            or any network/parse error occurs.
        """
        try:
            current_str = version("ignition")
        except PackageNotFoundError:
            self._log.warning("self_updater.check.package_not_found")
            return None

        try:
            available_str = await asyncio.wait_for(
                asyncio.to_thread(_fetch_pypi_version, PYPI_URL),
                timeout=5.0,
            )
        except Exception as exc:
            self._log.warning("self_updater.check.fetch_failed", reason=str(exc))
            return None

        if self._activity_log is not None:
            self._activity_log.append(
                EventType.TOOL_UPDATE,
                Outcome.SUCCESS,
                f"Self-update check: current={current_str} available={available_str}",
                detail="Checked PyPI for Ignition updates",
            )

        try:
            current_v = Version(current_str)
            available_v = Version(available_str)
        except Exception as exc:
            self._log.warning(
                "self_updater.check.version_parse_failed",
                reason=str(exc),
            )
            return None

        if available_v > current_v:
            self._log.info(
                "self_updater.check.update_available",
                current=current_str,
                available=available_str,
            )
            return SelfUpdateInfo(
                current_version=current_str,
                available_version=available_str,
            )

        self._log.info(
            "self_updater.check.up_to_date",
            current=current_str,
            available=available_str,
        )
        return None

    async def upgrade(self) -> tuple[bool, str]:
        """Upgrade Ignition via ``pipx upgrade ignition``.

        Runs pipx as a subprocess (never via shell=True). Captures stdout
        and stderr separately and returns the relevant output string.

        Returns:
            ``(True, stdout)`` when pipx exits with returncode 0.
            ``(False, stderr)`` when pipx exits with a non-zero returncode.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "pipx",
                "upgrade",
                "ignition",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
        except Exception as exc:
            self._log.warning("self_updater.upgrade.subprocess_failed", reason=str(exc))
            return (False, str(exc))

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        returncode = proc.returncode or 0

        if returncode == 0:
            if self._activity_log is not None:
                self._activity_log.append(
                    EventType.TOOL_UPDATE,
                    Outcome.SUCCESS,
                    "Self-update applied via pipx upgrade ignition",
                    detail=stdout,
                )
            self._log.info("self_updater.upgrade.success")
            return (True, stdout)

        self._log.warning(
            "self_updater.upgrade.failed",
            returncode=returncode,
            stderr=stderr,
        )
        return (False, stderr)


# ------------------------------------------------------------------
# Module-level helpers (not part of public API)
# ------------------------------------------------------------------


def _fetch_pypi_version(url: str) -> str:
    """Blocking HTTP fetch of the latest version from PyPI JSON API.

    Intended to be called inside ``asyncio.to_thread``.

    Args:
        url: The full PyPI JSON API URL.

    Returns:
        The latest version string from ``data["info"]["version"]``.

    Raises:
        Exception: On any HTTP or JSON parse failure.
    """
    req = Request(url, headers={"User-Agent": "ignition-self-updater/1"})
    with urlopen(req, timeout=5) as resp:
        data: dict[str, object] = json.loads(resp.read().decode("utf-8"))
    info = data["info"]
    assert isinstance(info, dict)
    latest: object = info["version"]
    assert isinstance(latest, str)
    return latest
