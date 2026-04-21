from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

ACTIVITY_SCHEMA_VERSION = 1


class EventType(StrEnum):
    # Emitted in M6
    TOOL_INSTALL = "tool_install"
    TOOL_INSTALL_FAILED = "tool_install_failed"
    AUTH_SIGN_IN = "auth_sign_in"
    AUTH_SIGN_OUT = "auth_sign_out"
    AUTH_EXPIRED = "auth_expired"
    HEALTH_SCAN = "health_scan"

    # Defined for future milestones — not yet wired
    TOOL_UPDATE = "tool_update"  # M7
    HEALTH_FIX = "health_fix"  # M7
    ONBOARDING_COMPLETE = "onboarding_complete"  # future


class Outcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    CANCELLED = "cancelled"


class ActivityEvent(BaseModel):
    """A single entry in the structured activity feed."""

    schema_version: int = ACTIVITY_SCHEMA_VERSION
    id: str  # UUID string
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: EventType
    tool_key: str | None = None
    outcome: Outcome
    summary: str  # one-line human-readable description
    detail: str = ""  # full log output or extended description
