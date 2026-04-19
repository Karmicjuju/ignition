from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from ignition.core import paths
from ignition.core.auth import (
    SWITCH_SCOPE_NOTICE,
    AuthService,
    _detect_session_expiry,
    _parse_profiles,
)
from ignition.schemas.auth import AwsProfile, ProfileType


def _write_aws_config(content: str) -> Path:
    """Write AWS config to the conftest-redirected aws_config_file()."""
    cfg = paths.aws_config_file()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(content, encoding="utf-8")
    return cfg


def _write_sso_cache_entry(start_url: str, expires_at: datetime) -> Path:
    """Write a single AWS SSO cache JSON entry under the conftest-redirected dir."""
    cache_dir = paths.aws_sso_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    # AWS writes the timestamp as an ISO string ending in "Z".
    expires_iso = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = cache_dir / "abc123.json"
    entry.write_text(
        json.dumps(
            {
                "startUrl": start_url,
                "region": "us-east-1",
                "accessToken": "redacted",
                "expiresAt": expires_iso,
            }
        ),
        encoding="utf-8",
    )
    return entry


# ---------------------------------------------------------------------------
# load_auth_state / _parse_profiles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_auth_state_no_aws_config(isolated_paths: Path) -> None:
    service = AuthService()
    auth = await service.load_auth_state()
    assert auth.profiles == []
    assert auth.last_checked is not None


@pytest.mark.asyncio
async def test_parse_profiles_sso(isolated_paths: Path) -> None:
    _write_aws_config(
        """\
[profile sso-dev]
region = us-east-1
sso_start_url = https://example.awsapps.com/start
sso_account_id = 123456789012
sso_role_name = DevAccess
"""
    )
    profiles = _parse_profiles()
    assert len(profiles) == 1
    p = profiles[0]
    assert p.name == "sso-dev"
    assert p.type == ProfileType.SSO
    assert p.region == "us-east-1"
    assert p.sso_start_url == "https://example.awsapps.com/start"


@pytest.mark.asyncio
async def test_parse_profiles_static(isolated_paths: Path) -> None:
    _write_aws_config(
        """\
[profile static-prod]
region = us-west-2
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
"""
    )
    profiles = _parse_profiles()
    assert len(profiles) == 1
    assert profiles[0].type == ProfileType.STATIC
    assert profiles[0].region == "us-west-2"


# ---------------------------------------------------------------------------
# switch_profile — now returns (AwsAuthState, scope_notice)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_switch_profile_sets_env_and_returns_notice(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """switch_profile must set AWS_PROFILE in process env AND return the
    Ignition-only scope notice so the UI cannot silently drop it."""
    service = AuthService()
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_PROFILE", raising=False)

    auth, notice = await service.switch_profile("my-profile")

    assert os.environ.get("AWS_PROFILE") == "my-profile"
    assert auth.active_profile == "my-profile"
    # Notice must mention both that it is Ignition-only and the export command.
    assert "Ignition only" in notice
    assert "export AWS_PROFILE=my-profile" in notice
    # And it must be the templated form of the module constant — protects
    # against a refactor that drops the placeholder substitution.
    assert notice == SWITCH_SCOPE_NOTICE.format(profile="my-profile")


# ---------------------------------------------------------------------------
# trigger_login — unchanged contract, retain coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_login_success(isolated_paths: Path) -> None:
    service = AuthService()

    async def mock_run(*args: object, **kwargs: object) -> tuple[int, str, str]:
        return (0, "Successfully logged in.", "")

    with patch("ignition.core.auth._run_subprocess", side_effect=mock_run):
        success, msg = await service.trigger_login("sso-dev")

    assert success is True
    assert "logged in" in msg.lower() or msg


@pytest.mark.asyncio
async def test_trigger_login_failure(isolated_paths: Path) -> None:
    service = AuthService()

    async def mock_run(*args: object, **kwargs: object) -> tuple[int, str, str]:
        return (1, "", "Error: SSO token expired")

    with patch("ignition.core.auth._run_subprocess", side_effect=mock_run):
        success, msg = await service.trigger_login("sso-dev")

    assert success is False
    assert "expired" in msg.lower() or msg


# ---------------------------------------------------------------------------
# repair_config — now uses aws_dir() helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repair_config_creates_dir(isolated_paths: Path) -> None:
    service = AuthService()
    success, _msg = await service.repair_config()
    assert success is True
    assert (isolated_paths / ".aws").exists()


# ---------------------------------------------------------------------------
# _detect_session_expiry — new helper
# ---------------------------------------------------------------------------


def test_detect_session_expiry_returns_none_for_none_profile(isolated_paths: Path) -> None:
    assert _detect_session_expiry(None) is None


def test_detect_session_expiry_returns_none_for_static_profile(isolated_paths: Path) -> None:
    static = AwsProfile(name="static-prod", type=ProfileType.STATIC, region="us-east-1")
    assert _detect_session_expiry(static) is None


def test_detect_session_expiry_returns_none_when_cache_dir_missing(
    isolated_paths: Path,
) -> None:
    sso = AwsProfile(
        name="sso-dev",
        type=ProfileType.SSO,
        sso_start_url="https://example.awsapps.com/start",
    )
    # Cache dir is not created — must return None, not raise.
    assert not paths.aws_sso_cache_dir().exists()
    assert _detect_session_expiry(sso) is None


def test_detect_session_expiry_returns_none_for_unmatched_start_url(
    isolated_paths: Path,
) -> None:
    expires = datetime.now(UTC) + timedelta(hours=8)
    _write_sso_cache_entry(start_url="https://OTHER.awsapps.com/start", expires_at=expires)
    sso = AwsProfile(
        name="sso-dev",
        type=ProfileType.SSO,
        sso_start_url="https://example.awsapps.com/start",
    )
    assert _detect_session_expiry(sso) is None


def test_detect_session_expiry_parses_z_suffix(isolated_paths: Path) -> None:
    expires = datetime(2099, 1, 2, 3, 4, 5, tzinfo=UTC)
    _write_sso_cache_entry(start_url="https://example.awsapps.com/start", expires_at=expires)
    sso = AwsProfile(
        name="sso-dev",
        type=ProfileType.SSO,
        sso_start_url="https://example.awsapps.com/start",
    )
    detected = _detect_session_expiry(sso)
    assert detected is not None
    assert detected == expires
    # Must be tz-aware UTC, not naive — preserves badge-state correctness.
    assert detected.tzinfo is not None


def test_detect_session_expiry_skips_malformed_json(isolated_paths: Path) -> None:
    cache = paths.aws_sso_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "broken.json").write_text("{not valid json", encoding="utf-8")
    # A valid entry alongside the broken one should still be picked up.
    expires = datetime(2099, 6, 1, 0, 0, 0, tzinfo=UTC)
    _write_sso_cache_entry(start_url="https://example.awsapps.com/start", expires_at=expires)
    sso = AwsProfile(
        name="sso-dev",
        type=ProfileType.SSO,
        sso_start_url="https://example.awsapps.com/start",
    )
    assert _detect_session_expiry(sso) == expires


@pytest.mark.asyncio
async def test_load_auth_state_populates_session_expiry_when_active_sso(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: an active SSO profile with a matching cache entry must
    surface the parsed expiry on AwsAuthState (not the hardcoded None)."""
    monkeypatch.setenv("AWS_PROFILE", "sso-dev")
    _write_aws_config(
        """\
[profile sso-dev]
region = us-east-1
sso_start_url = https://example.awsapps.com/start
sso_account_id = 123456789012
sso_role_name = DevAccess
"""
    )
    expires = datetime(2099, 12, 31, 23, 59, 59, tzinfo=UTC)
    _write_sso_cache_entry(start_url="https://example.awsapps.com/start", expires_at=expires)

    service = AuthService()
    auth = await service.load_auth_state()
    assert auth.active_profile == "sso-dev"
    assert auth.session_expiry == expires
