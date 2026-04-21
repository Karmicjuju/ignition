from __future__ import annotations

from ignition.core.catalog_loader import load_bundled, load_local_override, load_remote
from ignition.core.logging import get_logger
from ignition.core.paths import catalog_cache_dir, catalog_override_dir, config_file
from ignition.schemas.catalog import InstallStatus, ToolInfo


class CatalogService:
    def __init__(self) -> None:
        self._log = get_logger("ignition.core.catalog")
        self._tools: list[ToolInfo] | None = None

    def _load_tools(self) -> list[ToolInfo]:
        """Load tools via the three-layer priority chain: override → remote → bundled."""
        from ignition.schemas.config import AppConfigModel

        # Layer 1: local override
        override = load_local_override(catalog_override_dir())
        if override is not None:
            self._log.info("catalog.source", layer="override", count=len(override))
            return override

        # Layer 2: remote fetch — read config for URL and max_age
        config_path = config_file()
        if config_path.exists():
            try:
                app_config = AppConfigModel.model_validate_json(
                    config_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                self._log.warning("catalog.config_load_failed", reason=str(exc))
                app_config = AppConfigModel()
        else:
            app_config = AppConfigModel()

        if app_config.catalog_url:
            remote = load_remote(
                app_config.catalog_url,
                catalog_cache_dir(),
                app_config.catalog_max_age_seconds,
            )
            if remote is not None:
                self._log.info("catalog.source", layer="remote", count=len(remote))
                return remote

        # Layer 3: bundled fallback (never None — raises on corrupt package)
        bundled = load_bundled()
        self._log.info("catalog.source", layer="bundled", count=len(bundled))
        return bundled

    def get_all_tools(self) -> list[ToolInfo]:
        """Return the full tool catalogue, loading and caching on first call."""
        if self._tools is None:
            self._tools = self._load_tools()
        self._log.info("catalog.get_all", count=len(self._tools))
        return self._tools

    def get_tools_for_personas(self, persona_ids: list[str]) -> list[ToolInfo]:
        """Return tools whose persona_tags overlap with any of the given persona ids.

        Unknown persona ids are silently skipped. Results are deduplicated by key.
        """
        persona_set = set(persona_ids)
        seen: set[str] = set()
        result: list[ToolInfo] = []
        for tool in self.get_all_tools():
            if tool.key not in seen and bool(set(tool.persona_tags) & persona_set):
                seen.add(tool.key)
                result.append(tool)
        self._log.info(
            "catalog.filter_by_persona",
            persona_ids=persona_ids,
            count=len(result),
        )
        return result

    def search_tools(self, query: str) -> list[ToolInfo]:
        """Return tools whose name, description, or categories contain query (case-insensitive)."""
        needle = query.lower()
        result: list[ToolInfo] = [
            tool
            for tool in self.get_all_tools()
            if needle in tool.name.lower()
            or needle in tool.description.lower()
            or any(needle in cat.lower() for cat in tool.categories)
        ]
        self._log.info("catalog.search", query=query, count=len(result))
        return result

    def refresh_from_remote(self) -> bool:
        """Attempt a remote catalog fetch and replace in-memory tools if successful.

        Returns True when remote data was fetched, False otherwise.
        This method is intentionally synchronous so it can be called from a
        Textual @work(thread=True) worker without requiring an async executor.
        """
        from ignition.schemas.config import AppConfigModel

        config_path = config_file()
        if config_path.exists():
            try:
                app_config = AppConfigModel.model_validate_json(
                    config_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                self._log.warning("catalog.refresh.config_load_failed", reason=str(exc))
                return False
        else:
            app_config = AppConfigModel()

        if not app_config.catalog_url:
            self._log.info("catalog.refresh.skipped", reason="no catalog_url configured")
            return False

        remote = load_remote(
            app_config.catalog_url,
            catalog_cache_dir(),
            # Force a fresh fetch by setting max_age to 0.
            0,
        )
        if remote is None:
            self._log.info("catalog.refresh.no_data")
            return False

        self._tools = remote
        self._log.info("catalog.refresh.updated", count=len(self._tools))
        return True

    def mark_installed(self, tool_key: str, version: str | None = None) -> ToolInfo | None:
        """Mutate the in-memory status of the named tool to INSTALLED.

        Optionally records the detected version string. Returns the updated
        ToolInfo, or None if the key is not found.
        """
        for tool in self.get_all_tools():
            if tool.key == tool_key:
                tool.install_status = InstallStatus.INSTALLED
                if version is not None:
                    tool.version = version
                self._log.info("catalog.mark_installed", tool_key=tool_key, version=version)
                return tool
        self._log.warning("catalog.mark_installed.not_found", tool_key=tool_key)
        return None

    def mark_failed(self, tool_key: str) -> ToolInfo | None:
        """Mutate the in-memory status of the named tool to FAILED.

        Returns the updated ToolInfo, or None if the key is not found.
        """
        for tool in self.get_all_tools():
            if tool.key == tool_key:
                tool.install_status = InstallStatus.FAILED
                self._log.info("catalog.mark_failed", tool_key=tool_key)
                return tool
        self._log.warning("catalog.mark_failed.not_found", tool_key=tool_key)
        return None
