# Mission: M6 — Activity Log, Operator Mode, Demo Hardening

**Status:** COMPLETED
**Started:** 2026-04-21
**Branch:** feat/m6-activity-operator-demo
**Owner:** orchestrator

## Objective

Capture and display a structured activity feed. Wire `--operator` debug panel. Define and seed
three concrete demo scenarios. Wire event emission from `InstallerEngine` and `AuthService`.

## Spec Reference

`docs/milestones/m6-activity-operator-demo.md`

---

## UX Decisions

All decisions locked before implementation begins.

1. **Navigation shortcut for ActivityScreen** — Use `Ctrl+L` (not chord `g l`) to navigate to
   ActivityScreen. This is consistent with the existing `Ctrl+*` pattern already in the app
   (`Ctrl+T`, `Ctrl+H`, `Ctrl+A`, `Ctrl+,`). Chord shortcuts are explicitly called out in
   `app.py` comments as unsupported in Textual.

2. **Operator panel widget type** — Implemented as a Textual `ModalScreen` overlay (`Screen[None]`
   subclass with `BINDINGS = [Binding("escape", "app.pop_screen", "Close")]`). Dismissed with
   `Esc` or by clicking outside. Same pattern as any future modals.

3. **Event emission strategy** — `ActivityLog` is injected into `InstallerEngine` and
   `AuthService` constructors as an optional parameter `activity_log: ActivityLog | None = None`.
   When `None`, emission is silently skipped. No global singleton. Existing callers that
   construct these services without an `ActivityLog` continue to work unchanged.

4. **`--demo` default scenario** — `--demo` without `--operator` continues to seed Scenario 1
   (`seed_scenario_partially_onboarded`) by default. Existing behaviour is preserved.

5. **ActivityScreen row structure** — Each `ActivityEvent` renders as a single `Static` row.
   Day headers (`Today`, `Yesterday`, `YYYY-MM-DD`) are non-selectable separator rows.
   `j`/`k` skip separator rows when navigating. `Enter` on the selected row toggles an
   inline detail expansion. Scroll container wraps all rows.

6. **HomeScreen recent activity** — The existing `#activity-placeholder` `Static` widget is
   replaced with a `Vertical(id="recent-activity")` container holding up to 5 compact rows
   (one `Static` per event) plus a `Button("View all →", id="btn-view-activity")`. When there
   are no events, a single `Static("No recent activity.", id="activity-empty")` is shown and
   the view-all button is hidden.

7. **Operator panel guard** — `IgnitionApp` receives a new `operator_mode: bool = False`
   constructor parameter. The `Ctrl+D` binding is registered unconditionally in `BINDINGS`
   but the `action_operator_panel` handler checks `self._operator_mode` and does nothing
   (no push, no notification) if `False`. No affordance is shown in normal mode.

8. **`CatalogService.force_refresh()`** — The operator panel calls
   `CatalogService.force_refresh()` which is a thin alias for the existing
   `refresh_from_remote()`. Added as a new method name so the spec's button label matches
   the call without renaming the existing method.

9. **`health_scan` event emission** — `HealthEngine.run_scan()` accepts an optional
   `activity_log: ActivityLog | None = None` parameter. At the end of a scan, if provided,
   it emits a single `health_scan` event with `summary` = "Health scan: N issues found".
   Marked as lower priority per spec; implemented but not wired from UI workers.

10. **`last_activity_event_id` field** — Added to `AppStateModel` as
    `last_activity_event_id: str | None = None`. Updated by `ActivityLog.append()` after
    each write. Used by `HomeScreen` to detect when the recent-activity panel needs refresh
    (future use; in M6 the home screen reads directly from the log object).

11. **`ActivityLog` path function** — Add `activity_file() -> Path` to `core/paths.py`
    returning `state_dir() / "activity.json"`. Follows the same pattern as `state_file()`.
    `conftest.py` `isolated_paths` fixture gets a corresponding monkeypatch for the new
    path function.

12. **`EventType` enum scope** — Only the event types that are actually emitted in M6 are
    included in the `EventType` enum: `tool_install`, `tool_install_failed`, `auth_sign_in`,
    `auth_sign_out`, `auth_expired`, `health_scan`. Future types (`tool_update`,
    `health_fix`, `onboarding_complete`) are defined as enum members with a comment but are
    not wired yet, consistent with the spec table.

---

## Plan

### Layer 1 — Schema

- [x] S1: Create `src/ignition/schemas/activity.py` — `EventType` enum, `Outcome` enum,
      `ActivityEvent` Pydantic model (id, timestamp, event_type, tool_key, outcome, summary,
      detail). `schema_version = 1`. All fields validated. Run `/schema-guardian`.
- [x] S2: Update `src/ignition/schemas/state.py` — add
      `last_activity_event_id: str | None = None` to `AppStateModel`; bump
      `STATE_SCHEMA_VERSION` 6 → 7; add v6→v7 migration shim in `core/state.py`.
      Run `/schema-guardian`.

### Layer 2 — Core

- [x] C1: Create `src/ignition/core/activity.py` — `ActivityLog` service with `append()`,
      `get_recent(n=50)`, `get_all()`. Persist to `paths.activity_file()` as JSON array.
      Cap at 500 entries. `append()` writes full array atomically on every call.
      Add `activity_file()` to `src/ignition/core/paths.py`. Update `conftest.py` to
      monkeypatch `activity_file`. Run `/core-module-review`.
- [x] C2: Update `src/ignition/core/installer.py` — add `activity_log: ActivityLog | None = None`
      parameter to `__init__`. After `install()` succeeds, emit `tool_install` event.
      After `install()` fails, emit `tool_install_failed` event. Run `/core-module-review`.
- [x] C3: Update `src/ignition/core/auth.py` — add `activity_log: ActivityLog | None = None`
      parameter to `AuthService.__init__`. `trigger_login()` success → emit `auth_sign_in`.
      `sign_out()` (new stub method) → emit `auth_sign_out`.
      Run `/core-module-review`.
- [x] C4: Update `src/ignition/core/demo.py` — replace `seed_demo_state()` with three named
      functions: `seed_scenario_partially_onboarded()`, `seed_scenario_healthy_devops()`,
      `seed_scenario_needs_attention()`. Keep `seed_demo_state` as a backwards-compat alias
      that calls `seed_scenario_partially_onboarded`. Run `/core-module-review`.
- [x] C5: Update `src/ignition/core/health.py` — add optional `activity_log` param to
      `run_scan()`. Emit `health_scan` event with issue count summary after scan.
      Run `/core-module-review`.

### Layer 3 — UI

- [x] U1: Create `src/ignition/ui/screens/activity.py` — `ActivityScreen` with
      chronological feed, day-grouped rows, `j`/`k` navigation, `Enter` expand/collapse,
      `Esc` back. Add `Ctrl+L` binding to `IgnitionApp`. Run `/screen-reviewer`.
- [x] U2: Update `src/ignition/ui/screens/home.py` — replace `#activity-placeholder`
      `Static` with recent-activity panel (last 5 events + "View all →" button). Wire
      `btn-view-activity` to push `ActivityScreen`. Run `/screen-reviewer`.
- [x] U3: Create `src/ignition/ui/screens/operator.py` — `OperatorPanel` as `ModalScreen`.
      View raw state JSON button (opens read-only scrollable overlay), Force reload button,
      three seed-scenario buttons. Update `IgnitionApp` with `operator_mode` param and
      `Ctrl+D` handler. Run `/screen-reviewer`.

### Layer 4 — Tests

- [x] T1: Create `tests/test_activity_log.py` — unit tests: append persists, get_recent(n),
      get_all, cap enforcement at 500, file always valid JSON array, atomic write pattern,
      load from existing file. Run `/test-critic`.
- [x] T2: Create `tests/test_activity_screen.py` — Pilot tests: rows display, day grouping,
      expand/collapse with Enter, j/k navigation, Esc pops screen. Run `/test-critic`.
- [x] T3: Update `tests/test_demo.py` — extend to cover all three scenarios: persona state,
      tool counts, health summary, activity log content. Keep existing tests, add new ones.
      Run `/test-critic`.

### Layer 5 — QA + Security

- [x] Q1: `/quality-gate` — ruff lint, ruff format, ty type check, pytest all pass.
- [x] Q2: `/security-review` — mandatory; ActivityLog touches file I/O, operator panel
      touches state serialisation.

---

## Resume

If resuming: read this file, check `[x]` tasks, find the first `[ ]` task, continue from there.

All source paths are absolute under `/Users/colt/Documents/Source/Ignition`.

Layer dispatch order (strict — never skip layers):
1. S1 + S2 in parallel (schema-architect)
2. C1 + C2 + C3 + C4 + C5 in parallel (core-engineer) — only after S1 and S2 both complete
3. U1 + U2 in parallel, then U3 after both (ui-builder) — only after all C tasks complete
4. T1 + T2 + T3 in parallel (test-writer) — only after U1, U2, U3 all complete
5. Q1 quality-gate → Q2 security-review (qa-runner)

Key patterns:
- Schemas: `src/ignition/schemas/health.py` (StrEnum + Pydantic BaseModel pattern)
- Core: `src/ignition/core/health.py` (structlog, asyncio, pathlib pattern)
- Screens: `src/ignition/ui/screens/auth.py` (Screen[None], inject AppStateModel, @work)
- Tests: `tests/test_health_engine.py` + `tests/test_demo.py` (isolated_paths, AsyncMock)
- State migration: `src/ignition/core/state.py` (shim pattern from v5→v6 for reference)
- Existing app bindings: `src/ignition/app.py` (Ctrl+* pattern, operator_mode flag)
- Branch: `feat/m6-activity-operator-demo`
