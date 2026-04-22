from __future__ import annotations

from pydantic import BaseModel

CONFIG_SCHEMA_VERSION = 1


class AppConfigModel(BaseModel):
    schema_version: int = CONFIG_SCHEMA_VERSION
    catalog_url: str = ""
    catalog_max_age_seconds: int = 86400
    theme: str = "dark"
    density: str = "full"
    motion: str = "standard"
    automation_level: str = "observe"
    telemetry_enabled: bool = False
    health_scan_interval: str = "30m"
