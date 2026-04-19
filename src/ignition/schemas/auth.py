from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

AUTH_SCHEMA_VERSION = 1


class ProfileType(StrEnum):
    SSO = "sso"
    STATIC = "static"
    INSTANCE = "instance"


class AuthAction(StrEnum):
    LOGIN = "login"
    REFRESH = "refresh"
    SWITCH_PROFILE = "switch_profile"
    REPAIR_CONFIG = "repair_config"


class AwsProfile(BaseModel):
    name: str
    type: ProfileType
    region: str = ""
    sso_start_url: str | None = None
    sso_account_id: str | None = None
    sso_role_name: str | None = None
    is_active: bool = False


class AwsAuthState(BaseModel):
    schema_version: int = AUTH_SCHEMA_VERSION
    profiles: list[AwsProfile] = Field(default_factory=list)
    active_profile: str | None = None
    session_expiry: datetime | None = None
    last_checked: datetime | None = None
