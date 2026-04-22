from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

TELEMETRY_SCHEMA_VERSION = 1


class TelemetryEvent(BaseModel):
    """A single anonymous telemetry event for local buffering."""

    schema_version: int = TELEMETRY_SCHEMA_VERSION
    event_id: str  # UUID string
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    install_id: str
    event_name: str
    properties: dict[str, object] = Field(default_factory=dict)
