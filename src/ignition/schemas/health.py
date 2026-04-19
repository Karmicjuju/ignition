from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class HealthState(StrEnum):
    HEALTHY = "healthy"
    RECOMMENDED = "recommended"
    NEEDS_ATTENTION = "needs_attention"
    MANUAL = "manual"


class FixType(StrEnum):
    NONE = "none"
    AUTO = "auto"
    COPY_PASTE = "copy_paste"
    MANUAL_STEPS = "manual_steps"


class CheckResult(BaseModel):
    category: str
    check_id: str
    label: str
    state: HealthState
    detail: str
    fix_type: FixType = FixType.NONE
    fix_command: str | None = None
    fix_steps: list[str] = Field(default_factory=list)
