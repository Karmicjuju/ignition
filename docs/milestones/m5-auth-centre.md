# Milestone 5 — Auth Centre

## Goal

Replace the "Sync Access" stub on HomeScreen with a working AWS SSO auth centre: session status, sign-in/out, refresh, and config health.

## Depends On

M3 (Health Engine) — config and permission checks are reused for auth config health items.

---

## Scope

### In Scope

- `AuthScreen` showing AWS session status and controls
- AWS CLI SSO sign-in / sign-out / refresh via subprocess
- Session expiry detection
- Config health surface (Healthy / Needs attention items, same UX as HealthScreen)
- `~/.aws/config` backup-before-repair strategy
- Single AWS account / single SSO profile (first configured profile used)

### Out of Scope

- Inline `~/.aws/config` editing (no in-TUI editor in M5)
- Multi-account / multi-profile switching (deferred post-M5)
- Non-AWS auth: GitHub, Vault, etc. (deferred post-MVP)
- Credential rotation or key generation

---

## Session States

| State | Condition | Display |
|---|---|---|
| Not configured | No `[profile ...]` with `sso_start_url` in `~/.aws/config` | "AWS not configured" + setup guide |
| Configured, not signed in | Config present; no valid cached token | "Signed out" |
| Active | Valid cached token, not expired | "Active — expires in Xh Xm" |
| Expired | Token exists but past expiry | "Session expired" |
| Error | AWS CLI returned non-zero or is absent | "Auth error — [details]" |

Expiry is detected by parsing the cached SSO token JSON in `~/.aws/sso/cache/`. Token files are JSON with an `expiresAt` ISO 8601 field.

---

## AWS CLI Operations

All operations use `asyncio.create_subprocess_exec` with `aws` on PATH. No sudo required.

| Action | Command |
|---|---|
| Sign in | `aws sso login --profile <profile>` (opens browser) |
| Sign out | `aws sso logout` |
| Refresh / re-auth | `aws sso login --profile <profile>` (re-login flow) |
| Check identity | `aws sts get-caller-identity --profile <profile>` |
| List profiles | Parse `~/.aws/config` with `configparser` |

`aws sso login` opens the system browser. Ignition shows a "Waiting for browser authentication…" banner with a cancel button (sends SIGTERM to the subprocess).

### AWS CLI Minimum Version

Require `aws --version` output to be `aws-cli/2.x.x` or higher (`2.0.0` minimum). If AWS CLI v1 is detected, show an upgrade notice instead of attempting SSO operations.

---

## Config Repair Strategy

When Ignition detects a broken or missing `~/.aws/config`:

1. If `~/.aws/config` exists: copy to `~/.aws/config.ignition.bak` (if `.bak` already exists, append ISO timestamp suffix: `.bak.20260419T120000`)
2. Write corrected config
3. Show diff-style summary of what changed (old → new), not a raw file diff — human-readable: "Added `sso_start_url`", "Fixed `region` from `us-east-1` to `ap-southeast-2`"

**Fields Ignition owns** (will write/repair):
- `sso_start_url`
- `sso_region`
- `sso_account_id`
- `sso_role_name`
- `region`

**Fields Ignition treats as user-managed** (never overwrites):
- `output`
- `cli_pager`
- Any field not in the owned list

If an owned field is already set correctly, Ignition leaves it unchanged. No backup is created for read-only config inspections.

---

## Screen Layout

```
┌──────────────────────────────────────────────────────┐
│  Auth Centre                              [Refresh]  │
├──────────────────────────────────────────────────────┤
│  AWS Session                                         │
│  ● Active                  Profile: reactor-dev      │
│    Account: 123456789012   Expires in: 3h 42m        │
│                                                      │
│  [Sign out]                                          │
│                                                      │
│  Config health                                       │
│  ✓ ~/.aws/config           Healthy                   │
│  ✓ Credentials file        Healthy                   │
│  ✓ AWS CLI version         2.15.4 ✓                  │
└──────────────────────────────────────────────────────┘
```

Expired / not-signed-in state:
```
│  ✖ Session expired                                   │
│    Last active: 4 hours ago                          │
│  [Sign in]                                           │
```

Not-configured state:
```
│  AWS is not configured.                              │
│  Contact your platform team for your SSO URL, or    │
│  [Set up manually]  (opens guided config flow)       │
```

"Set up manually" is a simple prompt sequence for `sso_start_url`, `sso_region`, `sso_account_id`, `sso_role_name`, written to `~/.aws/config` after confirmation.

---

## Core Module: `AuthService`

Location: `src/ignition/core/auth.py`

```python
class SessionStatus:
    state: AuthState  # not_configured | signed_out | active | expired | error
    profile: str | None
    account_id: str | None
    expires_at: datetime | None
    error_detail: str | None

class AuthService:
    async def get_status(self) -> SessionStatus: ...
    async def sign_in(self, profile: str) -> bool: ...
    async def sign_out(self) -> bool: ...
    async def get_active_profile(self) -> str | None: ...
    async def repair_config(self, fields: dict[str, str]) -> bool: ...
    def get_config_health(self) -> list[CheckResult]: ...  # reuses HealthEngine types
```

`get_config_health()` returns the same `CheckResult` type from M3's `health.py` so the auth screen can display items using the same health row widget.

---

## AppStateModel Changes

Add (bump `schema_version` to 5 if M3 and M4 consumed 3 and 4):
```python
aws_profile: str | None = None
aws_session_expires_at: datetime | None = None
aws_last_sign_in: datetime | None = None
```

---

## Navigation

- HomeScreen "Sync Access" button → `AuthScreen`
- Keyboard shortcut: `g a` → `AuthScreen`

---

## Open Questions Deferred to Implementation

- SSO token cache path: standard at `~/.aws/sso/cache/`; confirm no variation across AWS CLI 2.x minor versions
- Which profile to use when multiple are configured: use the first profile with `sso_start_url`, or read from `AppStateModel.aws_profile` preference field

---

## Verification

1. `pytest tests/test_auth*.py` — unit tests with mocked `~/.aws/` directory; test state detection, token expiry parsing, config repair backup strategy
2. `pytest tests/test_auth_screen.py` — Pilot tests for session state display, sign-in/out button visibility
3. `/quality-gate` before commit
4. `/core-module-review` on `auth.py`
5. `/screen-reviewer` on `AuthScreen`
6. Manual: expire or delete the SSO cache token; confirm "Session expired" state; confirm sign-in opens browser flow
