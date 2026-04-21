from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from packaging.version import Version

from ignition.core.catalog import CatalogService
from ignition.core.logging import get_logger
from ignition.schemas.activity import EventType, Outcome
from ignition.schemas.catalog import InstallStatus

if TYPE_CHECKING:
    from ignition.core.activity import ActivityLog
    from ignition.core.installer import InstallerEngine, InstallResult


@dataclass
class UpdateInfo:
    """Describes an available update for an installed tool."""

    tool_key: str
    installed_version: str
    available_version: str


@dataclass
class UpdateEngine:
    """Detects and applies tool updates.

    Wraps InstallerEngine.install(force=True) for individual and bulk updates.
    Flexible-tier tools are always excluded from update checks.

    Attributes:
        catalog: CatalogService instance to query tool metadata.
        installer: InstallerEngine instance used to apply updates.
        activity_log: Optional ActivityLog for TOOL_UPDATE events.
    """

    catalog: CatalogService
    installer: InstallerEngine
    activity_log: ActivityLog | None = field(default=None)

    def __post_init__(self) -> None:
        self._log = get_logger("ignition.core.updater")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_updates(self) -> list[UpdateInfo]:
        """Compare installed tool versions against managed_version in the catalog.

        Flexible-tier tools (``version_policy == "flexible"``) are excluded.
        A tool qualifies as outdated when:
          - Its install_status is INSTALLED.
          - It has a non-None ``version`` (installed version string).
          - It has a non-None ``managed_version`` (target version string).
          - ``packaging.version.Version(version) < Version(managed_version)``.

        Returns:
            A list of UpdateInfo for all tools with available updates.
        """
        updates: list[UpdateInfo] = []
        for tool in self.catalog.get_all_tools():
            if tool.version_policy == "flexible":
                continue
            if tool.install_status != InstallStatus.INSTALLED:
                continue
            if tool.version is None or tool.managed_version is None:
                continue
            try:
                installed_v = Version(tool.version)
                managed_v = Version(tool.managed_version)
            except Exception as exc:
                self._log.warning(
                    "updater.version_parse_failed",
                    tool_key=tool.key,
                    reason=str(exc),
                )
                continue
            if installed_v < managed_v:
                updates.append(
                    UpdateInfo(
                        tool_key=tool.key,
                        installed_version=tool.version,
                        available_version=tool.managed_version,
                    )
                )
                self._log.info(
                    "updater.update_available",
                    tool_key=tool.key,
                    installed=tool.version,
                    available=tool.managed_version,
                )
        return updates

    async def update_tool(self, tool_key: str) -> InstallResult:
        """Update a single tool by re-installing it (force=True).

        Emits a TOOL_UPDATE ActivityEvent on success or failure.

        Args:
            tool_key: The catalog key of the tool to update.

        Returns:
            An InstallResult describing the outcome.
        """
        tool = next(
            (t for t in self.catalog.get_all_tools() if t.key == tool_key),
            None,
        )
        if tool is None:
            from ignition.core.installer import InstallMethod, InstallResult

            self._log.warning("updater.tool_not_found", tool_key=tool_key)
            return InstallResult(
                tool_key=tool_key,
                success=False,
                method_used=InstallMethod.COPY_PASTE,
                error=f"Tool '{tool_key}' not found in catalog",
            )

        result = await self.installer.install(tool)

        if self.activity_log is not None:
            if result.success:
                version_suffix = f" ({result.detected_version})" if result.detected_version else ""
                self.activity_log.append(
                    EventType.TOOL_UPDATE,
                    Outcome.SUCCESS,
                    f"Updated {tool.name}{version_suffix}",
                    tool_key=tool_key,
                    detail=f"Method: {result.method_used.value}",
                )
            else:
                self.activity_log.append(
                    EventType.TOOL_UPDATE,
                    Outcome.FAILURE,
                    f"Failed to update {tool.name}",
                    tool_key=tool_key,
                    detail=result.error or "",
                )

        self._log.info(
            "updater.update_tool.complete",
            tool_key=tool_key,
            success=result.success,
        )
        return result

    async def update_all(
        self,
        progress_cb: Callable[[str, str], None] | None = None,
    ) -> list[InstallResult]:
        """Update all tools with available updates sequentially.

        Fetches the update list via ``check_updates()`` then calls
        ``update_tool()`` for each in order.

        Args:
            progress_cb: Optional callback invoked with ``(tool_key, message)``
                         after each tool completes.

        Returns:
            A list of InstallResult in the order tools were processed.
        """
        updates = self.check_updates()
        results: list[InstallResult] = []
        for update_info in updates:
            result = await self.update_tool(update_info.tool_key)
            results.append(result)
            if progress_cb:
                status = "updated" if result.success else "failed"
                progress_cb(update_info.tool_key, status)

        self._log.info(
            "updater.update_all.complete",
            total=len(updates),
            succeeded=sum(1 for r in results if r.success),
            failed=sum(1 for r in results if not r.success),
            timestamp=datetime.now(UTC).isoformat(),
        )
        return results
