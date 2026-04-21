from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from ignition.schemas.auth import AwsAuthState
from ignition.schemas.catalog import InstallMethod

STATE_SCHEMA_VERSION = 7
INSTALL_HISTORY_MAX = 100


class InstallEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool_key: str
    method: InstallMethod
    success: bool
    version: str | None = None


class AppStateModel(BaseModel):
    schema_version: int = STATE_SCHEMA_VERSION
    install_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_launched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    demo_mode: bool = False
    onboarding_complete: bool = False
    onboarding_phase: int = 0
    selected_personas: list[str] = Field(default_factory=list)
    accepted_tool_bundle: bool = False
    last_health_scan: datetime | None = None
    health_summary: dict[str, str] = Field(default_factory=dict)
    aws_auth: AwsAuthState | None = None
    install_history: list[InstallEvent] = Field(default_factory=list)
    last_activity_event_id: str | None = None

    @field_validator("install_history", mode="before")
    @classmethod
    def _cap_install_history(cls, v: object) -> object:
        if isinstance(v, list) and len(v) > INSTALL_HISTORY_MAX:
            return v[-INSTALL_HISTORY_MAX:]
        return v
