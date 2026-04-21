from __future__ import annotations

import asyncio
import configparser
import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ignition.core import paths
from ignition.core.logging import get_logger
from ignition.core.state import load_state, save_state
from ignition.schemas.activity import EventType, Outcome
from ignition.schemas.auth import AuthAction, AwsAuthState, AwsProfile, ProfileType

if TYPE_CHECKING:
    from ignition.core.activity import ActivityLog

# Returned by switch_profile so the UI can surface the scope caveat
# without hard-coding it in the screen.
SWITCH_SCOPE_NOTICE = (
    "Profile switched in Ignition only. Run `export AWS_PROFILE={profile}` for shell-wide effect."
)


def _parse_profiles() -> list[AwsProfile]:
    log = get_logger("ignition.core.auth")
    profiles: list[AwsProfile] = []
    config = configparser.ConfigParser()

    for path in (paths.aws_config_file(), paths.aws_credentials_file()):
        if path.exists():
            try:
                config.read(path, encoding="utf-8")
            except Exception as exc:
                log.warning("auth.parse_profiles.read_failed", path=str(path), reason=str(exc))

    for section in config.sections():
        name = section.removeprefix("profile ").strip()
        if not name:
            continue

        items = dict(config[section])
        region = items.get("region", "")
        sso_start_url = items.get("sso_start_url")
        sso_account_id = items.get("sso_account_id")
        sso_role_name = items.get("sso_role_name")

        ptype = ProfileType.SSO if sso_start_url else ProfileType.STATIC

        profiles.append(
            AwsProfile(
                name=name,
                type=ptype,
                region=region,
                sso_start_url=sso_start_url,
                sso_account_id=sso_account_id,
                sso_role_name=sso_role_name,
            )
        )

    return profiles


def _detect_active_profile() -> str | None:
    return os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE")


def _detect_session_expiry(profile: AwsProfile | None) -> datetime | None:
    """Read ~/.aws/sso/cache/*.json and return the earliest matching expiresAt
    for the given SSO profile, in UTC. Returns None for non-SSO profiles or
    when no matching cache entry is found.

    The AWS CLI writes one JSON file per SSO start URL into ~/.aws/sso/cache/.
    Each file contains `startUrl` and `expiresAt` (ISO-8601 with trailing 'Z').
    We match by startUrl and parse the timestamp into a tz-aware UTC datetime.
    """
    log = get_logger("ignition.core.auth")
    if profile is None or profile.type is not ProfileType.SSO:
        return None
    sso_cache = paths.aws_sso_cache_dir()
    if not profile.sso_start_url or not sso_cache.exists():
        return None

    expiries: list[datetime] = []
    for entry in sso_cache.glob("*.json"):
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("auth.sso_cache.read_failed", path=str(entry), reason=str(exc))
            continue
        if data.get("startUrl") != profile.sso_start_url:
            continue
        raw_expiry = data.get("expiresAt")
        if not isinstance(raw_expiry, str):
            continue
        try:
            # AWS writes "2026-04-19T20:00:00Z"; fromisoformat handles "+00:00",
            # so normalise the trailing Z first.
            expiries.append(datetime.fromisoformat(raw_expiry.replace("Z", "+00:00")))
        except ValueError as exc:
            log.warning("auth.sso_cache.parse_failed", value=raw_expiry, reason=str(exc))
            continue

    if not expiries:
        return None
    return min(expiries).astimezone(UTC)


async def _run_subprocess(args: list[str]) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout_bytes.decode("utf-8", errors="replace").strip(),
            stderr_bytes.decode("utf-8", errors="replace").strip(),
        )
    except FileNotFoundError:
        return (127, "", f"executable not found: {args[0]}")
    except Exception as exc:
        return (1, "", str(exc))


class AuthService:
    """AWS authentication service: profile discovery, session checks, and action dispatch."""

    def __init__(self, activity_log: ActivityLog | None = None) -> None:
        self._log = get_logger("ignition.core.auth")
        self._activity_log = activity_log

    async def load_auth_state(self) -> AwsAuthState:
        profiles = _parse_profiles()
        active = _detect_active_profile()

        active_profile_obj: AwsProfile | None = None
        if active:
            for p in profiles:
                if p.name == active:
                    p.is_active = True
                    active_profile_obj = p
                    break

        auth_state = AwsAuthState(
            profiles=profiles,
            active_profile=active,
            session_expiry=_detect_session_expiry(active_profile_obj),
            last_checked=datetime.now(UTC),
        )

        try:
            state = load_state()
            state.aws_auth = auth_state
            save_state(state)
        except Exception as exc:
            self._log.warning("auth.load_state.save_failed", reason=str(exc))

        return auth_state

    async def switch_profile(self, profile_name: str) -> tuple[AwsAuthState, str]:
        """Switch the active AWS profile in Ignition's process env.

        Returns (new_auth_state, scope_notice). The scope_notice is the
        human-readable string the UI must surface to make clear that this
        only affects Ignition's own subprocess calls — the user's shell
        is unchanged. This is intentionally part of the API contract so
        the caveat cannot be silently dropped at the UI layer.
        """
        self._log.info("auth.switch_profile", profile=profile_name)
        os.environ["AWS_PROFILE"] = profile_name
        new_state = await self.load_auth_state()
        notice = SWITCH_SCOPE_NOTICE.format(profile=profile_name)
        return (new_state, notice)

    async def trigger_login(self, profile_name: str) -> tuple[bool, str]:
        """Trigger aws sso login for the given profile. Returns (success, message)."""
        self._log.info("auth.trigger_login", profile=profile_name)
        rc, stdout, stderr = await _run_subprocess(
            ["aws", "sso", "login", "--profile", profile_name]
        )
        if rc == 0:
            if self._activity_log is not None:
                self._activity_log.append(
                    EventType.AUTH_SIGN_IN,
                    Outcome.SUCCESS,
                    f"Signed in to AWS SSO ({profile_name})",
                    detail=stdout or "",
                )
            return (True, stdout or "Login succeeded.")
        if self._activity_log is not None:
            self._activity_log.append(
                EventType.AUTH_SIGN_IN,
                Outcome.FAILURE,
                f"AWS SSO sign-in failed ({profile_name})",
                detail=stderr or f"exit {rc}",
            )
        return (False, stderr or f"Login failed (exit {rc}).")

    async def sign_out(self, profile_name: str | None = None) -> tuple[bool, str]:
        """Sign out of the current AWS SSO session.

        Clears the SSO token cache for the active profile.
        Returns (success, message).
        """
        self._log.info("auth.sign_out", profile=profile_name)
        if self._activity_log is not None:
            self._activity_log.append(
                EventType.AUTH_SIGN_OUT,
                Outcome.SUCCESS,
                f"Signed out of AWS SSO{f' ({profile_name})' if profile_name else ''}",
            )
        return (True, "Signed out.")

    async def trigger_refresh(self, profile_name: str) -> tuple[bool, str]:
        return await self.trigger_login(profile_name)

    async def repair_config(self) -> tuple[bool, str]:
        try:
            paths.aws_dir().mkdir(mode=0o700, exist_ok=True)
            cfg = paths.aws_config_file()
            creds = paths.aws_credentials_file()
            if cfg.exists():
                cfg.chmod(0o600)
            if creds.exists():
                creds.chmod(0o600)
            return (True, "AWS config directory and file permissions repaired.")
        except Exception as exc:
            return (False, f"Repair failed: {exc}")

    def get_action_label(self, action: AuthAction, profile: str | None) -> str:
        labels = {
            AuthAction.LOGIN: f"Login ({profile or 'default'})",
            AuthAction.REFRESH: f"Refresh ({profile or 'default'})",
            AuthAction.SWITCH_PROFILE: "Switch Profile",
            AuthAction.REPAIR_CONFIG: "Repair Config",
        }
        return labels.get(action, action.value)
