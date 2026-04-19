from __future__ import annotations

from ignition.core.logging import get_logger
from ignition.schemas.catalog import InstallStatus, ToolInfo


class CatalogService:
    def __init__(self) -> None:
        self._log = get_logger("ignition.core.catalog")
        self._tools: list[ToolInfo] | None = None

    def _load_tools(self) -> list[ToolInfo]:
        """Return the hardcoded stub tool catalogue (12 tools, all 5 personas covered).

        # M3: replace with ruamel.yaml manifest load
        """
        return [
            ToolInfo(
                key="git",
                name="Git",
                description="Distributed version control system",
                version="2.44.0",
                categories=["vcs", "core"],
                persona_tags=["backend", "frontend", "devops", "security", "contractor"],
                managed=False,
                install_status=InstallStatus.INSTALLED,
            ),
            ToolInfo(
                key="python",
                name="Python 3",
                description="General-purpose programming language runtime",
                version="3.12.3",
                categories=["language", "core"],
                persona_tags=["backend", "contractor"],
                managed=True,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="docker",
                name="Docker",
                description="Container platform for building and running isolated environments",
                version="26.0.0",
                categories=["container", "infra"],
                persona_tags=["backend", "devops"],
                managed=True,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="node",
                name="Node.js",
                description="JavaScript runtime built on Chrome's V8 engine",
                version="22.3.0",
                categories=["language", "core"],
                persona_tags=["frontend"],
                managed=True,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="pnpm",
                name="pnpm",
                description="Fast, disk space efficient package manager for Node.js",
                version="9.1.0",
                categories=["package-manager"],
                persona_tags=["frontend"],
                managed=False,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="awscli",
                name="AWS CLI v2",
                description="Unified command line interface for Amazon Web Services",
                version="2.15.1",
                categories=["cloud", "auth"],
                persona_tags=["backend", "frontend", "devops", "security", "contractor"],
                managed=True,
                install_status=InstallStatus.INSTALLED,
            ),
            ToolInfo(
                key="terraform",
                name="Terraform",
                description="Infrastructure as code tool for provisioning cloud resources",
                version="1.8.1",
                categories=["infra", "iac"],
                persona_tags=["devops"],
                managed=True,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="kubectl",
                name="kubectl",
                description="Command line tool for controlling Kubernetes clusters",
                version="1.30.0",
                categories=["container", "orchestration"],
                persona_tags=["devops"],
                managed=True,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="helm",
                name="Helm",
                description="Package manager for Kubernetes",
                version="3.14.4",
                categories=["container", "orchestration"],
                persona_tags=["devops"],
                managed=False,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="trivy",
                name="Trivy",
                description="Vulnerability scanner for containers and other artifacts",
                version="0.51.1",
                categories=["security", "scanning"],
                persona_tags=["security"],
                managed=True,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="vault",
                name="HashiCorp Vault CLI",
                description="Secrets management and data protection tool",
                version="1.16.1",
                categories=["security", "secrets"],
                persona_tags=["security"],
                managed=True,
                install_status=InstallStatus.MISSING,
            ),
            ToolInfo(
                key="postgresql-client",
                name="psql (PostgreSQL)",
                description="Interactive terminal for PostgreSQL databases",
                version="16.2",
                categories=["database", "core"],
                persona_tags=["backend"],
                managed=False,
                install_status=InstallStatus.MISSING,
            ),
        ]

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

    def simulate_install(self, tool_key: str) -> ToolInfo | None:
        """Mutate the in-memory install_status of the named tool to INSTALLED.

        Returns the updated ToolInfo, or None if the key is not found.
        This is a no-op stub — no subprocess is invoked.
        """
        for tool in self.get_all_tools():
            if tool.key == tool_key:
                tool.install_status = InstallStatus.INSTALLED
                self._log.info("catalog.simulate_install", tool_key=tool_key)
                return tool
        self._log.warning("catalog.simulate_install.not_found", tool_key=tool_key)
        return None
