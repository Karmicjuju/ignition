from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

CATALOG_SCHEMA_VERSION = 1


class InstallStatus(StrEnum):
    INSTALLED = "installed"
    OUTDATED = "outdated"
    MISSING = "missing"
    UNMANAGED = "unmanaged"
    FAILED = "failed"


class InstallMethod(StrEnum):
    BREW = "brew"
    APT = "apt"
    BINARY = "binary"
    COPY_PASTE = "copy_paste"


class InstallStep(BaseModel):
    # str keeps forward-compat with manifest extensions beyond InstallMethod enum values
    method: str
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
    release_channel: str = "stable"
    install_status: InstallStatus = InstallStatus.MISSING
    version: str | None = None
    managed_version: str | None = None
