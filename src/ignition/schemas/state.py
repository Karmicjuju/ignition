from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

STATE_SCHEMA_VERSION = 1


class AppStateModel(BaseModel):
    schema_version: int = STATE_SCHEMA_VERSION
    install_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_launched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    demo_mode: bool = False
