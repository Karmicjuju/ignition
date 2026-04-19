# Mission: M3 — Health & Diagnostics Engine

**Status:** COMPLETED

## Request

Replace the "Run Diagnostics" stub on HomeScreen with a working health scan engine and results
screen. Add a SettingsScreen backed by the existing AppConfigModel. Implement HealthEngine as a
new core service with four check categories (Tools, Configs, Shell integration, Permissions),
four result states (Healthy / Recommended fix / Needs attention / Manual), auto-fix for
safe issues, copy-paste command surface for privileged fixes, re-scan after successful auto-fix,
and a schema bump to add `last_health_scan` and `health_summary` to AppStateModel (version 3 → 4).

## PO Decision

**Verdict:** APPROVE with caveats

**Caveats:**
1. **Chord shortcuts must be replaced.** The M3 spec proposes `g h` → HealthScreen and `g s` →
   SettingsScreen. Textual does not support two-key chords natively. The orchestrator must assign
   `ctrl+*` equivalents (following M2's `ctrl+t` precedent) and document them in the UX Decisions
   section below before any UI work begins.

2. **Collapsible category widget choice.** The spec says "Categories are collapsible" but does not
   specify the Textual widget pattern. The orchestrator must decide between `CollapsibleContent`,
   a custom toggle-Vertical, or `TabbedContent` and document the decision before the UI layer
   begins.

3. **Per-issue Re-check UX.** The spec mentions both a full "Scan" button and per-issue "Re-check"
   after manual fix, but does not wireframe the per-issue re-check placement or label. The
   orchestrator must define this interaction before the UI layer begins.

4. **Schema migration shim (inherited from M2).** M2 deferred the migration shim for
   `schema_version` 2 → 3 to M3 scope. M3 must implement this shim alongside the 3 → 4 bump
   so that existing developer machines with state.json at version 2 do not crash on load.

**Reasoning:** All M3 features are explicitly named in the PRD MVP scope (FR#5 Health centre,
FR#6 Repair system, FR#9 Settings) and the architecture doc names both `Health Engine` and
`Repair Engine` as first-class core modules with matching interfaces. The UX spec describes the
Health Centre and Settings screen at sufficient intent level; the M3 milestone spec fills in the
detail with wireframes and check definitions. The four caveats are resolvable by the orchestrator
without human review.

## UX Decisions

### D1 — Keyboard shortcuts (chord replacement)

Following M2 precedent (ctrl+t for Tool Catalog), two-key chord bindings (g h, g s) are not
supported by Textual natively. Replacements:

- `ctrl+h` → HealthScreen (mnemonic: h for Health)
- `ctrl+,` → SettingsScreen (mnemonic: conventional settings shortcut on macOS)

Both bindings are registered on `IgnitionApp` at the app level, same pattern as `ctrl+t` for
the catalog.

### D2 — Collapsible category widget pattern

Use Textual's built-in `Collapsible` widget (available since Textual 0.46). Rationale:
- No custom widget code required — reduces implementation risk and test surface.
- Collapsible handles keyboard toggle (Enter/Space), title bar, and expand/collapse state
  natively.
- `TabbedContent` is excluded because it hides categories rather than stacking them — the
  wireframe shows all category summaries visible at once.
- A custom toggle-Vertical is excluded because Collapsible already exists in the stdlib.

Each health category is wrapped in a `Collapsible(title="Tools (4 checks) …")` with issue rows
as children. The Collapsible title line is updated after a scan to reflect counts.

### D3 — Per-issue Re-check interaction

An inline "Re-check" button appears on each issue row that has `fix_type != none`. It is
positioned to the far right of the row (same row as the issue description and state badge).
Label: "Re-check". Clicking it re-runs only the single check for that `check_id` via
`HealthEngine.run_scan(categories=[check.category])` filtered to that check_id, then updates
only that row's display. This keeps the full-page "Scan" button separate from per-issue
verification after a manual fix.

### D4 — Schema migration shim (v2 → v3 already implemented; add v3 → v4)

Inspection of `src/ignition/core/state.py` shows the v2 → v3 migration shim is ALREADY
implemented (drops `tool_catalog_cache` key). The M2 deferred item was completed during M2
implementation. M3 only needs to add the v3 → v4 migration shim in `core/state.py` alongside
the `AppStateModel` bump in `schemas/state.py`. No additional v2 → v3 work is needed.

## Plan

### Layer 1 — Schema

- [x] S1: `src/ignition/schemas/health.py` — define `HealthState` (enum), `FixType` (enum), `CheckResult` (Pydantic BaseModel), `InstallEvent` stub
- [x] S1b: `src/ignition/schemas/state.py` — bump STATE_SCHEMA_VERSION to 4, add `last_health_scan: datetime | None` and `health_summary: dict[str, str]` fields, confirm v2→v3 shim exists, add v3→v4 migration shim in `core/state.py`

### Layer 2 — Core

- [x] C1: `src/ignition/core/health.py` — `HealthEngine` with `run_scan()` and `apply_fix()`, all four check categories (Tools, Configs, Shell integration, Permissions), concurrent execution via `asyncio.gather`, individual check failures caught as `needs_attention`

### Layer 3 — UI

- [x] U1: `src/ignition/ui/screens/health.py` — `HealthScreen` with Collapsible categories, issue rows with inline Re-check buttons, full Scan button, result state badges
- [x] U2: `src/ignition/ui/screens/settings.py` — `SettingsScreen` with immediate-apply radio groups for Theme/Density/Motion/Automation backed by `AppConfigModel`
- [x] U3: `src/ignition/ui/screens/home.py` — wire "Run Diagnostics" → HealthScreen, add Recent Activity stub, register `ctrl+h` and `ctrl+,` bindings in `app.py`

### Layer 4 — Tests

- [x] T1: `tests/test_health_engine.py` — HealthEngine unit tests with mocked filesystem (asyncio, all four categories, apply_fix happy path, exception-tolerance)
- [x] T2: `tests/test_health_screen.py` — Pilot tests for HealthScreen (boots, scan trigger, result rows appear, re-check button, apply-fix flow)
- [x] T3: `tests/test_settings_screen.py` — Pilot tests for SettingsScreen (boots, radio group changes persist to config)

### Layer 5 — QA

- [x] QA: `/quality-gate` — ruff lint + format + ty type check + pytest all pass

## Progress

All layers complete. 76 tests passing. ruff lint, ruff format, ty type check all pass.

## Blockers

None.

## Resume

If this session is interrupted:
1. Status is IN_PROGRESS — check which layer tasks are incomplete (look for `[ ]` checkboxes).
2. Schema files: `src/ignition/schemas/health.py` (new), `src/ignition/schemas/state.py` (v4 bump).
3. Migration shim: `src/ignition/core/state.py` — v3→v4 shim needed alongside existing v2→v3 shim.
4. Core: `src/ignition/core/health.py` — HealthEngine with asyncio.gather over four categories.
5. UI screens: `health.py` (new), `settings.py` (new), `home.py` (update btn-diagnostics + bindings).
6. App-level bindings: `app.py` — add ctrl+h (health) and ctrl+, (settings) alongside ctrl+t.
7. Tests: `test_health_engine.py`, `test_health_screen.py`, `test_settings_screen.py`.
8. Run `/quality-gate` before declaring done.

Key reference files:
- Milestone spec: `docs/milestones/m3-health-diagnostics.md`
- State schema (v3, to be bumped to v4): `src/ignition/schemas/state.py`
- Config schema (v1, no change): `src/ignition/schemas/config.py`
- Config core (load/save pattern): `src/ignition/core/config.py`
- State core (migration shim pattern): `src/ignition/core/state.py`
- App (navigation/bindings pattern): `src/ignition/app.py`
- HomeScreen (button wiring pattern): `src/ignition/ui/screens/home.py`
- CatalogScreen (full screen pattern): `src/ignition/ui/screens/catalog.py`
- Conftest (isolated_paths fixture): `tests/conftest.py`
- Catalog screen tests (Pilot pattern): `tests/test_catalog_screen.py`
