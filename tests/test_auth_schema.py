from __future__ import annotations

from datetime import UTC, datetime

from ignition.schemas.auth import (
    AUTH_SCHEMA_VERSION,
    AuthAction,
    AwsAuthState,
    AwsProfile,
    ProfileType,
)


def test_aws_profile_defaults() -> None:
    p = AwsProfile(name="default", type=ProfileType.STATIC)
    assert p.region == ""
    assert p.sso_start_url is None
    assert p.is_active is False


def test_aws_profile_sso_fields() -> None:
    p = AwsProfile(
        name="sso-dev",
        type=ProfileType.SSO,
        region="us-east-1",
        sso_start_url="https://example.awsapps.com/start",
        sso_account_id="123456789012",
        sso_role_name="DevAccess",
    )
    assert p.type == ProfileType.SSO
    assert p.sso_start_url == "https://example.awsapps.com/start"


def test_aws_auth_state_schema_version() -> None:
    state = AwsAuthState()
    assert state.schema_version == AUTH_SCHEMA_VERSION
    assert AUTH_SCHEMA_VERSION == 1


def test_aws_auth_state_defaults() -> None:
    state = AwsAuthState()
    assert state.profiles == []
    assert state.active_profile is None
    assert state.session_expiry is None
    assert state.last_checked is None


def test_aws_auth_state_with_profiles() -> None:
    profiles = [
        AwsProfile(name="sso-dev", type=ProfileType.SSO, is_active=True),
        AwsProfile(name="static-prod", type=ProfileType.STATIC),
    ]
    state = AwsAuthState(
        profiles=profiles,
        active_profile="sso-dev",
        last_checked=datetime.now(UTC),
    )
    assert len(state.profiles) == 2
    assert state.active_profile == "sso-dev"


def test_aws_auth_state_round_trip() -> None:
    now = datetime.now(UTC)
    state = AwsAuthState(
        profiles=[AwsProfile(name="dev", type=ProfileType.SSO)],
        active_profile="dev",
        last_checked=now,
    )
    dumped = state.model_dump()
    restored = AwsAuthState.model_validate(dumped)
    assert restored.active_profile == "dev"
    assert restored.schema_version == AUTH_SCHEMA_VERSION
    assert len(restored.profiles) == 1


def test_auth_action_values() -> None:
    assert AuthAction.LOGIN == "login"
    assert AuthAction.REFRESH == "refresh"
    assert AuthAction.SWITCH_PROFILE == "switch_profile"
    assert AuthAction.REPAIR_CONFIG == "repair_config"


def test_profile_type_values() -> None:
    assert ProfileType.SSO == "sso"
    assert ProfileType.STATIC == "static"
    assert ProfileType.INSTANCE == "instance"
