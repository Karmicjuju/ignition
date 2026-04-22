# Mission: Sprint 2 — Telemetry, Self-Update, Scheduled Health Scans

**Status:** SECURITY_GATE_PENDING — all layers complete, quality gate passed (295/2), awaiting /security-review before upload pipeline can be added

---

## Context

Sprint 1 post-MVP (PR #12) shipped Updates Screen, Recommended Actions, and Release Channels
onto main. The codebase now has 264 tests passing with schema_version=9.

Sprint 2 delivers three capabilities that together close the observability, maintainability,
and proactive-health gaps in the product:

- **Feature A — Telemetry / Analytics (FR#10):** Anonymous local event buffer with a consent
  gate. No upload pipeline ships until /security-review clears it.
- **Feature B — Ignition Self-Update:** In-app detection and one-command upgrade of the
  Ignition application itself via pipx, distinct from tool updates.
- **Feature C — Scheduled Health Scans + Proactive Notifications:** Periodic background scan
  within the running Textual process lifecycle using @work, badge on Health Centre nav, and
  toast notifications for new issues.

A single schema bump (v9 → v10) covers all new state fields from Features A, B, and C.

---

## PO Decision

**Verdict:** APPROVE with caveats
**Date:** 2026-04-22
All caveats resolved by orchestrator. See UX Decisions below.

---

## Architectural Boundaries (hard constraints from PO)

**Feature C — No background process outside Ignition lifecycle:**
Scheduled health scans MUST be implemented exclusively using Textual's `@work` decorator
and `asyncio`-native scheduling (e.g., `asyncio.sleep` inside a `@work` loop, or
`set_interval` on a Textual widget). No LaunchAgent, no systemd unit, no cron entry, no
subprocess that outlives the Ignition process. If Ignition is not running, no scan occurs.
This is not a limitation to work around — it is the intended design.

**Feature A — No upload code without security clearance:**
The telemetry buffer (local JSON file) may be implemented in full. The upload pipeline
(HTTP POST to any remote endpoint) MUST NOT be written until /security-review runs on the
branch containing the buffer implementation and returns PASS or CLEARED. A placeholder
comment in the code is acceptable; working upload code is not. Flag this gate explicitly
after Layer 2 completes.

---

## UX Decisions

### Feature A — Telemetry / Analytics

**Decision A1 — Consent gate: settings-only opt-in (not first-run modal)**
The existing SettingsScreen already has the radio-button rows pattern. Telemetry consent
is an opt-in toggle in SettingsScreen (off by default). There is no first-run modal.
Rationale: a first-run modal adds friction for a capability that starts disabled. Users who
want telemetry can enable it in Settings; those who don't never see a prompt. This matches
the automation_level = "observe" default philosophy — Ignition observes and does not act
without explicit user choice.

**Decision A2 — Event taxonomy (exhaustive list for v1 buffer):**
The following events are captured. All are written to the local buffer only:
  1. `app_launch` — on every Ignition startup (captures install_id, schema_version, demo_mode, platform)
  2. `screen_view` — when any Screen is pushed onto the Textual stack (captures screen_name)
  3. `tool_install` — mirrors existing ActivityLog TOOL_INSTALL (captures tool_key, outcome, method)
  4. `tool_update` — mirrors existing ActivityLog TOOL_UPDATE (captures tool_key, outcome)
  5. `health_fix` — when apply_fix() succeeds (captures check_id, fix_type)
  6. `health_scan` — on each scan completion (captures issue_count, categories)
  7. `auth_action` — on auth sign-in, sign-out, or expired (captures action_type, outcome)
  8. `self_update_check` — when Ignition self-update check runs (captures channel, current_version)
  9. `self_update_applied` — when pipx upgrade succeeds (captures previous_version, new_version)
  10. `onboarding_complete` — when onboarding wizard finishes (captures selected_personas)

Events are written as NDJSON lines to `$XDG_STATE_HOME/ignition/telemetry_buffer.ndjson`.
Buffer is capped at 1000 events (oldest dropped). Each event has: `event_id` (uuid4),
`timestamp` (ISO-8601 UTC), `install_id` (from install_id.py), `event_name`, `properties`
(dict). No PII. No filesystem paths. No usernames.

**Decision A3 — Operator queue viewer: defer**
The operator queue viewer for the telemetry buffer is deferred. OperatorScreen already
shows activity log and demo data. A dedicated telemetry queue view adds complexity without
developer value in this sprint. It can be added in Sprint 3 once the buffer has shipped
and its shape is confirmed. Operator mode can already inspect the raw NDJSON file.

**Decision A4 — New schema: src/ignition/schemas/telemetry.py**
A new standalone schema file is created (separate from state.py) to hold:
  - `TELEMETRY_SCHEMA_VERSION = 1`
  - `TelemetryEvent` Pydantic model (event_id, timestamp, install_id, event_name, properties)
  - `TelemetryConfig` Pydantic model (enabled: bool = False, buffer_max: int = 1000)

TelemetryConfig fields are added to AppConfigModel in schemas/config.py (not state.py,
since consent is a config preference, not session state).

### Feature B — Ignition Self-Update

**Decision B1 — Placement: UpdatesScreen dedicated row, plus HomeScreen banner**
Self-update gets a dedicated section at the top of UpdatesScreen (above the tool-update
rows). The section shows: current Ignition version, available version (if newer), and an
"Upgrade Ignition" button. HomeScreen gets a minimal banner (one Static line) in the
reactor-status-panel only when an Ignition update is available, linking to UpdatesScreen.
Rationale: UpdatesScreen is the established home for all update activity. HomeScreen
already has an update badge for tools; a second badge for Ignition itself would clutter
the panel. A single-line banner inside the status panel (visible only when relevant) is
low-noise.

**Decision B2 — Post-upgrade restart messaging**
After the user clicks "Upgrade Ignition" and pipx upgrade completes:
  - Success: notify() toast: "Ignition upgraded to {version}. Restart to apply changes."
  - The Ignition process does NOT auto-restart (would be disorienting in a TUI).
  - The "Upgrade Ignition" button is replaced with a Static: "Restart required — quit and
    relaunch Ignition to use the new version."
  - This message persists for the session (not dismissed on navigate-away).
  - Failure: notify() toast: "Upgrade failed: {error}. Try: pipx upgrade ignition"

**Decision B3 — PyPI version check endpoint**
Use the official PyPI JSON API: `https://pypi.org/pypi/ignition/json`
Rationale: the app is distributed via PyPI (pipx install from PyPI). TestPyPI is only for
pre-release testing. The check reads `.info.version` from the JSON response.
HTTP call is non-blocking via `@work` with a 5-second timeout. If the check fails (network
error, timeout, 404), the self-update row shows "Update check unavailable" and logs a
warning — it does not crash or show an error modal.
`last_ignition_update_check` and `ignition_available_version` are stored in AppStateModel
(new fields in v10 schema).

**Decision B4 — New core module: src/ignition/core/self_updater.py**
`SelfUpdater` dataclass (mirrors UpdateEngine pattern):
  - `check()` → `SelfUpdateInfo | None` (None = no update available or check failed)
  - `upgrade()` → `bool` (True = succeeded; runs `pipx upgrade ignition` via asyncio subprocess)
  - activity_log: ActivityLog | None injected

### Feature C — Scheduled Health Scans + Proactive Notifications

**Decision C1 — Scan intervals and SettingsScreen placement**
Scan interval options: Off / 15 min / 30 min / 60 min (default: 30 min).
Placement: new "Health scan interval" row in SettingsScreen using the existing RadioSet
pattern. Value persisted to AppConfigModel (new field: `health_scan_interval: str = "30m"`).
Valid values: "off", "15m", "30m", "60m".

**Decision C2 — Scan scheduling mechanism**
The scheduler runs inside IgnitionApp using Textual's `set_interval()` method (fires a
callback on the Textual event loop). On startup, `app.py` reads `config.health_scan_interval`
and calls `self.set_interval(seconds, self._scheduled_health_scan)` if not "off".
`_scheduled_health_scan` is a `@work` coroutine that instantiates HealthEngine and calls
`run_scan()`. If the interval setting changes in SettingsScreen, SettingsScreen posts a
custom message `ScanIntervalChanged` to the app, which cancels the old timer and creates
a new one (or stops it if "off").

**Decision C3 — Toast notification format**
When a scheduled scan finds new issues (issues not present in the previous scan summary):
  notify() call with:
  - message: "{n} new health issue(s) detected. Open Health Centre to review."
  - title: "Health Scan"
  - severity: "warning" (for NEEDS_ATTENTION) or "error" (for MANUAL)
  - timeout: 8 (seconds)
"New" is defined as: a check_id that is in the new results with state NEEDS_ATTENTION or
MANUAL that was not in the previous scan's results at the same severity or worse.

**Decision C4 — Nav sidebar badge on Health Centre**
The HomeScreen "Run Diagnostics" button gains an issue-count badge (a Static appended
inline in the button row) that shows the count of NEEDS_ATTENTION + MANUAL issues from
`state.health_summary`. Badge is hidden when count is 0. This is a read from persisted
state (no live scan needed to display it). Badge updates after every scan completion.

**Decision C5 — Scan result accumulation: replace strategy**
Each scan fully replaces the previous scan result in `state.health_summary`. There is no
merge. Rationale: the health summary is a snapshot of current system state, not a
changelog. Accumulation would make stale issues invisible and inflate the badge count.
The scheduler stores the previous scan's check_ids at NEEDS_ATTENTION/MANUAL in memory
(not persisted) to compute the "new issues" delta for toast notifications.

---

## Schema v9 → v10 (combined migration)

Single migration shim in core/state.py. New fields in AppStateModel:
  - `telemetry_consent: bool = False` (Feature A)
  - `last_ignition_update_check: datetime | None = None` (Feature B)
  - `ignition_available_version: str | None = None` (Feature B)

New field in AppConfigModel (schemas/config.py, no version bump needed for config):
  - `telemetry_enabled: bool = False` (Feature A — consent flag lives in config)
  - `health_scan_interval: str = "30m"` (Feature C)

New standalone schema file:
  - `src/ignition/schemas/telemetry.py` — TelemetryEvent, TelemetryConfig

---

## Plan

### Layer 1 — Schema (schema-architect)

- [ ] S1: schemas/state.py — bump STATE_SCHEMA_VERSION 9→10; add `last_ignition_update_check: datetime | None = None` and `ignition_available_version: str | None = None` to AppStateModel
- [ ] S2: core/state.py — add v9→v10 migration shim: setdefault last_ignition_update_check=None, ignition_available_version=None; bump schema_version to 10
- [ ] S3: schemas/config.py — add `telemetry_enabled: bool = False` and `health_scan_interval: str = "30m"` to AppConfigModel (CONFIG_SCHEMA_VERSION stays 1; these are additive with Pydantic defaults)
- [ ] S4: schemas/telemetry.py — new file: TELEMETRY_SCHEMA_VERSION=1; TelemetryEvent model (event_id: str, timestamp: datetime, install_id: str, event_name: str, properties: dict[str, object]); no upload config in this file

### Layer 2 — Core (core-engineer)

- [ ] C1: core/telemetry.py — new TelemetryBuffer class: `record(event_name, properties)` writes NDJSON to `$XDG_STATE_HOME/ignition/telemetry_buffer.ndjson`; buffer_max=1000 cap enforced on write; `flush_pending()` → list[TelemetryEvent] reads and returns all buffered events (for future upload); `clear()` truncates buffer; TelemetryBuffer checks AppConfigModel.telemetry_enabled before writing (no-op if disabled); inject install_id automatically from install_id.py; all file I/O synchronous (buffer writes are fast, not async)
- [ ] C2: core/self_updater.py — new SelfUpdater dataclass: `async check() → SelfUpdateInfo | None` (fetches https://pypi.org/pypi/ignition/json via asyncio subprocess curl or urllib with 5s timeout, compares to current version from importlib.metadata); `async upgrade() → tuple[bool, str]` (runs `pipx upgrade ignition` via asyncio.create_subprocess_exec, returns success + output); `SelfUpdateInfo` dataclass (current_version, available_version); activity_log: ActivityLog | None; emits self_update_check and self_update_applied to activity log; reads current version via `importlib.metadata.version("ignition")`
- [ ] C3: core/health.py — extend run_scan() to accept optional `previous_summary: dict[str, str] | None` parameter; after scan completes, compute `new_issues: list[str]` (check_ids that are newly NEEDS_ATTENTION or MANUAL vs previous_summary); return value stays `list[CheckResult]` (new_issues accessible via attribute on HealthEngine: `self.last_new_issues: list[str]`)

### Layer 3 — UI (ui-builder)

All UI tasks can begin after Layer 2 is complete.

- [ ] U1: ui/screens/updates.py — add Ignition self-update section at top of UpdatesScreen (above #tool-rows): shows current version, available version (or "Checking…"), "Upgrade Ignition" button; mounts a `@work` call to SelfUpdater.check() on mount; on upgrade success replace button with "Restart required" Static; wire activity log; also add HomeScreen banner integration (read state.ignition_available_version to show/hide a one-line banner in HomeScreen reactor-status-panel)
- [ ] U2: ui/screens/settings.py — add "Health scan interval" RadioSet row (Off / 15 min / 30 min / 60 min) with immediate-apply to AppConfigModel.health_scan_interval; add "Analytics" section with a Checkbox for telemetry_enabled (off by default); Checkbox change saves AppConfigModel immediately; post ScanIntervalChanged message to app when interval changes; add explanatory Static under Analytics checkbox: "Anonymous usage data helps improve Ignition. No personal information is collected."
- [ ] U3: ui/screens/home.py — add issue-count badge after "Run Diagnostics" button (reads state.health_summary; shows count of NEEDS_ATTENTION + MANUAL issues; hidden if 0); add Ignition update banner (one Static line, hidden if state.ignition_available_version is None, shown above the quick-actions row)
- [ ] U4: app.py — on startup: read config.health_scan_interval; call set_interval() to schedule _scheduled_health_scan @work if not "off"; implement on_scan_interval_changed() message handler; _scheduled_health_scan worker instantiates HealthEngine, calls run_scan(), compares to previous summary, calls self.notify() for new issues, updates HomeScreen badge via app message or direct query

### Layer 4 — Tests (test-writer)

All test tasks can run in parallel after Layer 2 core is complete (no need to wait for Layer 3).

- [x] T1: tests/test_telemetry.py — unit tests: TelemetryBuffer.record() writes NDJSON when enabled; no-op when disabled; buffer_max cap enforced; flush_pending() returns correct events; clear() empties buffer; install_id injected correctly; event schema matches TelemetryEvent
- [x] T2: tests/test_self_updater.py — unit tests: SelfUpdateInfo fields; check() returns None when current==available; check() returns SelfUpdateInfo when update available; check() handles network failure gracefully (returns None, no exception); upgrade() calls correct subprocess args; activity_log receives events
- [x] T3: tests/test_health_scheduled.py — unit tests: run_scan() new_issues computation correct (new NEEDS_ATTENTION vs same-state previous); HealthEngine.last_new_issues populated; no regression on existing scan tests
- [ ] T4: tests/test_settings_screen.py — extend: health scan interval RadioSet present and all 4 options renderable; Analytics checkbox present and defaults off; Checkbox change saves config
- [ ] T5: tests/test_updates_screen.py — extend: Ignition self-update section present in UpdatesScreen; "Upgrade Ignition" button present; "Checking…" shown on mount; after mock check returns None, appropriate "Up to date" state shown
- [ ] T6: tests/test_schema_telemetry.py — schema-guardian style: TelemetryEvent validates correctly; required fields; properties is dict; schema_version present

### Layer 5 — QA

- [ ] SEC-GATE: /security-review must run on the feature branch after Layer 2 (C1 telemetry buffer) is merged. Upload pipeline MUST NOT be written until this returns PASS or CLEARED. Flag to user.
- [ ] QA: /quality-gate — all four CI checks pass (ruff lint, ruff format, ty, pytest)

---

## Verification

Sprint is complete when all of the following are true:

1. `pytest` runs 290+ tests (264 baseline + ~26 new), 0 failures
2. `ruff check src/ tests/` exits 0
3. `ruff format --check src/ tests/` exits 0
4. `ty check src/ignition/core/` exits 0 (covers C1, C2, C3 new modules)
5. `STATE_SCHEMA_VERSION == 10` in schemas/state.py
6. TelemetryBuffer writes to NDJSON only when telemetry_enabled is True
7. SelfUpdater.check() fetches PyPI JSON API without shell=True
8. HealthEngine.last_new_issues is populated after each scan
9. UpdatesScreen shows Ignition self-update section
10. SettingsScreen has both "Health scan interval" and "Analytics" sections
11. HomeScreen shows issue-count badge and Ignition update banner (when applicable)
12. /security-review flagged to user before any upload pipeline code is written

---

## Blockers

None at start.

---

## Resume

If resuming: read this file, check Status. If IN_PROGRESS, find first `[ ]` task in Plan.
All source paths are absolute under `/Users/colt/Documents/Source/Ignition`.

Key file paths:
- Branch: feat/sprint-2
- Schemas: src/ignition/schemas/state.py (v10), src/ignition/schemas/config.py, src/ignition/schemas/telemetry.py (new)
- Core: src/ignition/core/telemetry.py (new), src/ignition/core/self_updater.py (new), src/ignition/core/health.py (extended)
- Screens: src/ignition/ui/screens/updates.py (extended), src/ignition/ui/screens/settings.py (extended), src/ignition/ui/screens/home.py (extended)
- App: src/ignition/app.py (extended)
- Tests: tests/test_telemetry.py (new), tests/test_self_updater.py (new), tests/test_health_scheduled.py (new), tests/test_settings_screen.py (extended), tests/test_updates_screen.py (extended), tests/test_schema_telemetry.py (new)
