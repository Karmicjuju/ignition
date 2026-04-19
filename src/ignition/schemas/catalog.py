from __future__ import annotations

import enum

from pydantic import BaseModel, Field

CATALOG_SCHEMA_VERSION = 1


class InstallStatus(enum.StrEnum):
    INSTALLED = "installed"
    OUTDATED = "outdated"
    MISSING = "missing"
    UNMANAGED = "unmanaged"


class InstallStep(BaseModel):
    method: str  # brew | apt | binary | npm | pip | script
    package: str = ""
    cask: bool = False
    repo: str = ""
    repo_key_url: str = ""
    url: str = ""
    archive_type: str = "raw"  # tgz | zip | raw
    binary_name: str = ""
    install_path: str = ""
    global_install: bool = False  # npm --global (avoid 'global' as field name — reserved)


class PlatformInstallMethods(BaseModel):
    macos: list[InstallStep] = Field(default_factory=list)
    linux: list[InstallStep] = Field(default_factory=list)


class ToolInfo(BaseModel):
    schema_version: int = CATALOG_SCHEMA_VERSION
    key: str
    name: str
    description: str
    categories: list[str] = Field(default_factory=list)
    persona_tags: list[str] = Field(default_factory=list)
    managed: bool
    version_policy: str = "flexible"
    requires_sudo: bool = False
    health_check: str = ""
    dependencies: list[str] = Field(default_factory=list)
    install_methods: PlatformInstallMethods = Field(default_factory=PlatformInstallMethods)
    install_status: InstallStatus = InstallStatus.MISSING
    version: str | None = None
