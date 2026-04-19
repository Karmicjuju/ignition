from __future__ import annotations

import enum

from pydantic import BaseModel, Field

CATALOG_SCHEMA_VERSION = 1


class InstallStatus(enum.StrEnum):
    INSTALLED = "installed"
    OUTDATED = "outdated"
    MISSING = "missing"
    UNMANAGED = "unmanaged"


class ToolInfo(BaseModel):
    schema_version: int = CATALOG_SCHEMA_VERSION
    key: str
    name: str
    description: str
    version: str
    categories: list[str] = Field(default_factory=list)
    persona_tags: list[str] = Field(default_factory=list)
    managed: bool
    install_status: InstallStatus = InstallStatus.MISSING
