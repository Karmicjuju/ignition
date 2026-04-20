# Mission: M4 — AWS Auth Centre

**Status:** COMPLETED (PO triage 2026-04-19: APPROVE with caveats — all P0/P1 caveats remediated; M4.1 follow-up captured)
**Started:** 2026-04-19
**Owner:** orchestrator

## Objective

Build the AWS authentication centre for Ignition. Adds credential detection, profile management, SSO login triggering, and a dedicated Auth screen wired into app navigation and health checks.

## PO Triage Verdict (2026-04-19)

**APPROVE with caveats.** Three P0/P1 fixes required before this PR ships. P2 items deferred to a follow-up M4.1 mission.

**Bundling decision:** All P0 + P1 fixes land in this same PR. Rationale — the surface area is small (one schema file, one core module, one screen), splitting would force a second security-review pass on overlapping code, and the P1 items (session expiry, in-progress UX, switch-scope clarity) materially change the security posture that the reviewer must sign off on.

## UX Decisions

1. **Session badge** — Three states only: Active (green), Expired (red), Unknown (dim). Active = session_expiry is set and in the future. Expired = expiry is set and in the past. Unknown = no expiry on record.
2. **Profile list** — Use a DataTable with columns: Name, Type, Region, Active. Consistent with catalog screen widget usage.
3. **Action bar** — Four buttons across the status panel: Login, Refresh, Switch Profile, Repair Config. Login is always enabled; Refresh and Switch Profile require an active profile row to be selected.
4. **Status panel** — Stacked Static widgets showing: active profile name, region, session expiry (or "No active session").
5. **Demo mode profiles** — Three seeded profiles: `sso-dev` (SSO, us-east-1), `sso-staging` (SSO, us-west-2), `static-prod` (static, us-east-1). `sso-dev` is active with a future session expiry.
6. **Keyboard nav** — `ctrl+a` global binding opens auth screen. Escape pops back.
7. **Switch Profile** — Calls `AuthService.switch_profile()` which updates `AwsAuthState.active_profile`. Notifies user of result, **including the explicit scope caveat** (Ignition-only; user must `export AWS_PROFILE=…` for shell-wide effect — see UX Decision #13).
8. **Login / Refresh** — Calls `AuthService.trigger_login()` which structures the subprocess call but does not exec in tests (mocked).
9. **Repair Config** — Structures `aws configure` subprocess call. Notified on completion.
10. **Health check** — Auth health added to the existing `configs` category in HealthEngine. Reports HEALTHY (active session), NEEDS_ATTENTION (expired), or RECOMMENDED (unknown/no config).
11. **AwsAuthState in AppState** — Added as optional field `aws_auth: AwsAuthState | None = None`. Schema version bumped 4 → 5. **CORRECTION (PO triage):** the mission doc previously asserted a v4→v5 migration shim was added; it was not. `src/ignition/core/state.py` only has v2→v3 and v3→v4 migrations. A v4→v5 shim **must be added** as part of P0-1 below (no behavioural change needed beyond letting v4 state load with `aws_auth=None`, then re-stamping schema_version=5 on next save).
12. **Session expiry detection (NEW, P1-2)** — `session_expiry` will be populated by reading `~/.aws/sso/cache/*.json` and selecting the cache entry whose `startUrl` matches the active profile's `sso_start_url`. The `expiresAt` ISO-8601 string is parsed to UTC datetime. Static and instance profiles return `None`. No `aws sts` subprocess fallback in v0.1 (would block the UI on a network round-trip and require credentials we may not have).
13. **Switch-scope notification (NEW, P1-5)** — `_action_switch` notify shows a two-line message: line 1 confirms the in-app switch (`Switched Ignition to <profile>.`), line 2 explicitly tells the user that shell-wide effect requires `export AWS_PROFILE=<profile>`. Severity: `warning` (so the user sees it as actionable, not just informational).
14. **In-progress button state (NEW, P1-3)** — While any of the four `@work` actions is running, all four buttons are disabled and the active button label is suffixed with `…` (e.g. `Login…`). On completion (success or error), buttons re-enable and labels reset. Implemented via a single `_busy: reactive[bool]` on the screen that drives a `_set_buttons_busy(active_id)` helper.
15. **Empty-state CTA (NEW, P1-4)** — When `_render_profiles` finds zero profiles, the "Loading profiles…" Static is replaced with a Vertical containing the message and a `Repair Config` Button. Clicking it invokes the same `_action_repair` handler as the action-bar Repair button.

## P0/P1 Punch List (PO triage caveats)

### P0 — must fix before merge
- **P0-1**: Add v4→v5 migration shim in `src/ignition/core/state.py`. Without it, existing tester state files fail validation, fall through the `except` at `state.py:32`, and get silently replaced — destroying `install_id` and onboarding progress. Owner: core-engineer.

### P1 — must fix before declaring M4 complete
- **P1-2**: Populate `session_expiry` (UX Decision #12). Currently hardcoded `None` at `src/ignition/core/auth.py:99` and `:65`, collapsing the badge to two states. Owner: core-engineer.
- **P1-3**: Disable Login/Refresh/Switch/Repair while a `@work` runs; show "Working…" suffix (UX Decision #14). Currently buttons stay enabled at `src/ignition/ui/screens/auth.py:212` allowing subprocess spam. Owner: ui-builder.
- **P1-4**: Add Repair Config CTA on the empty-profiles state at `src/ignition/ui/screens/auth.py:171` (UX Decision #15). Currently a dead-end label. Owner: ui-builder.
- **P1-5**: Update `_action_switch` notify to surface Ignition-only scope (UX Decision #13). Currently the notify at `auth.py:251` is silent about the fact `switch_profile` only mutates Ignition's `os.environ`. Owner: ui-builder.

## P2 — Deferred to M4.1 follow-up mission
- Token-expiry timer (countdown widget on the status panel)
- Role switching distinct from profile switching
- Expandable config-files / env-vars panel
- Dedicated "Issues" surface on the Auth screen
- `ProfileType.INSTANCE` is declared in `src/ignition/schemas/auth.py:14` but never emitted by `_parse_profiles` — instance-role profiles are silently misclassified as STATIC. Add a `credential_source = Ec2InstanceMetadata` / IMDS heuristic detector.
- Help (`?`), search (`/`), palette (`Ctrl+K`) shortcuts on the Auth screen.

A new `.claude/missions/m4_1_auth_followup.md` file should be created when M4 ships, capturing these as the M4.1 backlog. Not blocking the current PR.

## Plan

### Layer 1 — Schema (original M4)
- [x] S1: Create `src/ignition/schemas/auth.py` (AwsProfile, AwsAuthState, AuthAction)
- [x] S2: Update `src/ignition/schemas/state.py` — add `aws_auth` field, bump schema_version to 5

### Layer 2 — Core (original M4)
- [x] C1: Create `src/ignition/core/auth.py` (AuthService)
- [x] C2: Update `src/ignition/core/health.py` — add AWS auth check in configs category
- [x] C3: Update `src/ignition/core/demo.py` — seed demo AwsAuthState

### Layer 3 — UI (original M4)
- [x] U1: Create `src/ignition/ui/screens/auth.py` (AwsAuthScreen)
- [x] U2: Update `src/ignition/app.py` — add `ctrl+a` binding and `action_goto_auth`
- [x] U3: Update `src/ignition/ui/screens/home.py` — wire "Sync Access" button to AuthScreen

### Layer 4 — Tests (original M4)
- [x] T1: Create `tests/test_auth_schema.py`
- [x] T2: Create `tests/test_auth_core.py`
- [x] T3: Create `tests/test_auth_screen.py`

### Layer 5 — PO Triage Punch List (NEW)
- [x] R1: schema-guardian review of `src/ignition/schemas/auth.py` and the state v5 bump (TaskList #2) — all assertions PASS, no changes required
- [x] R2: P0-1 — v4→v5 migration shim added; also fixed missing `raw["schema_version"] = 4` reassignment in v3→v4 block so cascade works correctly. core-module-review clean (TaskList #3)
- [x] R3: P1-2 — `_detect_session_expiry()` added to `core/auth.py`, reads `~/.aws/sso/cache/*.json` and matches by `startUrl`. `switch_profile` now returns `tuple[AwsAuthState, str]` with explicit `SWITCH_SCOPE_NOTICE` so the UI cannot silently drop the caveat. Side fix: AWS path constants moved to `core/paths.py` helpers (`aws_dir`, `aws_config_file`, `aws_credentials_file`, `aws_sso_cache_dir`). core-module-review clean (TaskList #4)
- [x] R4: P1-3 / P1-4 / P1-5 — `_set_busy()` helper added (disables all 4 buttons + appends "…" to active one); `on_button_pressed` drops events while `_busy`; empty-state copy now points at Repair Config button (UX Decision #15); `_action_switch` consumes `(state, scope_notice)` from core and notifies with `severity="warning"`. screen-reviewer 9/10 PASS, A10 (Reactor language) BLOCKED on literal AWS CLI command names — accepted as a known carve-out (PO-approved UX Decisions #3 + #13 cover the vocabulary) (TaskList #5)
- [x] R5: tests added/updated. tests/test_auth_core.py rewritten (drops broken `_AWS_CONFIG`/`_AWS_CREDENTIALS` patches now that paths flow through helpers; covers `_detect_session_expiry` parsing/edge cases and `switch_profile` tuple contract). tests/test_state_migration.py NEW (covers v3→v4→v5 cascade and v4→v5 shim — guards `install_id` preservation regression). tests/test_auth_screen.py NEW (empty-state CTA copy, busy-state machine including dropped-press, switch-scope notify with warning severity). conftest.py extended to monkeypatch `aws_dir` / `aws_config_file` / `aws_credentials_file` / `aws_sso_cache_dir`. test-critic 6/6 PASS on all 4 files (TaskList #6)
- [x] R6: security-review WARN verdict (no HIGH/CRITICAL). All four PO-flagged surface areas (SSO cache JSON parsing, subprocess argv invocation, os.environ scope, state-file migration) verified safe. Warnings: S101 in tests (project-standard), S112 defensive UI try/except (intentional), pip-audit not installed (recommend adding to dev deps). PR not blocked (TaskList #7)

### Layer 6 — QA
- [x] Q1: quality-gate PASS. ruff check + format clean, ty clean, 106/106 pytest. Mid-run regression caught and fixed: leaf helpers in `core/paths.py` (e.g. `aws_dir`) cannot be patched via `monkeypatch.setattr(paths_mod, ...)` if the consumer does `from ignition.core.paths import aws_dir` — the bound symbol bypasses the patch. Fixed by routing `core/auth.py` and `tests/test_auth_core.py` through `from ignition.core import paths` + `paths.aws_dir()` (TaskList #8)

## Resume

If resuming: read this file, check which R*/Q* tasks are `[x]`, find the first incomplete task, continue from there. All source paths are absolute under `/Users/colt/Documents/source/ignition`.

Punch-list dispatch order (strict):
1. R1 schema-guardian (parallel-safe with no other agent — but R2 conceptually depends on its sign-off)
2. R2 core-engineer (P0 migration shim) — the highest-risk item; do first so test-writer can reference the shim
3. R3 core-engineer (P1 expiry + switch scope)
4. R4 ui-builder (P1 UX) — depends on R3 because the UI calls into the core API surface
5. R5 test-writer
6. R6 security-review
7. Q1 quality-gate

Key patterns to follow:
- Schemas: `src/ignition/schemas/health.py` (StrEnum + Pydantic BaseModel pattern)
- Core: `src/ignition/core/health.py` (asyncio, structlog, _run_subprocess pattern)
- Screens: `src/ignition/ui/screens/health.py` (Screen[None], inject AppStateModel, @work)
- Tests: `tests/test_health_engine.py` + `tests/test_health_screen.py` (isolated_paths, AsyncMock)
- App nav: `src/ignition/app.py` (BINDINGS + action_goto_* pattern)
- State migration: `src/ignition/core/state.py` (v2→v3 and v3→v4 shims; v4→v5 to be added by R2)
