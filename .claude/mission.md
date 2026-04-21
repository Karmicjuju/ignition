# Mission: Post-MVP Sprint 1 — Updates Screen, Recommended Actions, Release Channels

**Status:** COMPLETED

## Request

Three features bundled as one post-MVP sprint:

**Feature A: Dedicated Updates Screen**
- New UpdatesScreen (`src/ignition/ui/screens/updates.py`) grouped by governance tier
- Per-tool update rows with version delta (current → available), one-click update button
- "Update all managed" action at top
- Navigation: `Ctrl+U` shortcut or HomeScreen badge click
- Fills the UX spec "Updates" screen gap; UpdateEngine already exists from M7

**Feature B: HomeScreen Recommended Actions panel**
- "Recommended for you" panel on HomeScreen driven by active personas + install state
- Shows up to 4 actionable suggestions; clicking navigates to relevant screen/action
- Logic lives in a new RecommendationsEngine core service

**Feature C: Release Channels in Catalog**
- Add `release_channel: str = "stable"` to ToolInfo (default "stable")
- Add `preferred_channel: str = "stable"` to AppStateModel (requires schema v8→v9 bump)
- CatalogService filters tools by channel
- SettingsScreen gains a "Release channel" preference row

---

## PO Decision

**Verdict:** APPROVE with caveats
**Date:** 2026-04-21

All caveats resolved by orchestrator — see UX Decisions section.

---

## UX Decisions

**Decision 1 — HomeScreen badge navigation retarget (Caveat 1)**
The HomeScreen update badge click is retargeted exclusively to UpdatesScreen.
ToolCatalogScreen retains its `filter_outdated` reactive for direct keyboard nav
(ctrl+t then filter) but HomeScreen no longer drives it via badge click.
Rationale: having two dedicated entry points for the same action creates confusion.
UpdatesScreen is purpose-built; the badge should take users there.

**Decision 2 — UpdatesScreen row layout (Caveat 2)**
- Row fields: tool name + version delta text (`installed → available`) + governance tier badge
  (badge text "Managed" or "Optional") + per-tool "Update" button
- "Update all managed" button sits in a top toolbar above the list (not a sticky group header)
- Progress feedback: inline progress row (a Static widget) replaces the Update button during
  an active update — same pattern used in ToolCatalogScreen for installs
- Empty state: full-screen centred message "All tools are up to date ✓" with last-checked
  timestamp displayed below the message

**Decision 3 — RecommendationsEngine suggestion card layout (Caveat 3)**
- Panel placement: inserted between Quick Actions and Recent Activity on HomeScreen
  (after reactor-status-panel content, before recent-activity Vertical)
- Card structure: priority icon + one-line action text + secondary label ("recommended for
  backend") + right-aligned action button/link. Each card is a Static/Horizontal with a
  Button whose label is contextual ("Install", "Update", "Fix", "Configure", "Continue")
- Maximum 4 suggestions shown; panel hidden entirely when suggestion list is empty
- Empty state: hide panel (zero height, display: none), no placeholder text
- Suggestion type to navigation mapping:
  - SuggestionType.INSTALL → ToolCatalogScreen (pre-filtered by tool key display)
  - SuggestionType.UPDATE → UpdatesScreen
  - SuggestionType.AUTH → AuthScreen
  - SuggestionType.HEALTH → HealthScreen
  - SuggestionType.ONBOARDING → OnboardingScreen

**Decision 4 — Schema v8→v9 migration (Caveat 4)**
- STATE_SCHEMA_VERSION bumped 8→9 in schemas/state.py
- Migration shim added in core/state.py load_state(): when raw schema_version == 8,
  call `raw.setdefault("preferred_channel", "stable")` then bump to 9
- This follows the established cascade-migration pattern

**Decision 5 — Ctrl+U binding**
- Navigation shortcut Ctrl+U registered at app level (app.py BINDINGS) as `action_goto_updates`
- HomeScreen also registers Ctrl+U locally as a pass-through to UpdatesScreen
- "g u" chord not used — no native chord support in Textual

**Decision 6 — Channel filtering semantics**
- Channel order: stable < beta < experimental
- "stable" user sees only stable tools
- "beta" user sees stable + beta tools
- "experimental" user sees stable + beta + experimental tools
- "deprecated" tools always shown regardless of preferred_channel (with DEPRECATED badge)
- Channel filtering applied in CatalogService.get_tools() (a new filtered view method)

---

## Plan

### Layer 1 — Schema (schema-architect)

- [x] S1: schemas/catalog.py — add `release_channel: str = "stable"` to ToolInfo
- [x] S2: schemas/state.py — add `preferred_channel: str = "stable"`, bump STATE_SCHEMA_VERSION 8→9
- [x] S3: core/state.py — add v8→v9 migration shim for preferred_channel

### Layer 2 — Core (core-engineer)

- [x] C1: core/recommendations.py — RecommendationsEngine with Suggestion dataclass, SuggestionType enum, get_suggestions() implementing all 5 rules
- [x] C2: core/catalog.py — add get_tools() channel-filtered method; update get_all_tools() to respect preferred_channel via optional parameter
- [x] C3: data/catalog/tools/*.yaml — add `release_channel: stable` to all 12 tool manifests

### Layer 3 — UI (ui-builder)

- [x] U1: ui/screens/updates.py — new UpdatesScreen: tool rows (name + version delta + tier badge + Update button), inline progress, "Update all managed" button, empty state, Ctrl+U binding
- [x] U2: ui/screens/settings.py — add Release channel RadioSet section (Stable/Beta/Experimental) with immediate-apply pattern saving to AppStateModel.preferred_channel
- [x] U3: ui/screens/home.py — retarget badge to UpdatesScreen; add #recommendations-panel; inject RecommendationsEngine; wire Ctrl+U
- [x] U4: app.py — register Ctrl+U → action_goto_updates binding, import UpdatesScreen

### Layer 4 — Tests (test-writer)

- [x] T1: tests/test_recommendations.py — unit tests: each suggestion rule, priority ordering, max-4 cap, empty-state
- [x] T2: tests/test_updates_screen.py — Pilot tests: row display, per-tool update button, update-all enabled/disabled, empty state
- [x] T3: tests/test_settings_screen.py — extend: release channel RadioSet present, preference persists
- [x] T4: tests/test_catalog_service.py — extend: channel filtering (stable/beta/experimental)

### Layer 5 — QA

- [x] QA: /quality-gate — all four CI checks pass
- [x] SEC: /security-review — PASS or CLEARED on all findings

---

## Progress

All layers complete. 263 tests passing (2 skipped). Quality gate clean (ruff lint, ruff format, ty, pytest all pass). Security review WARN (4 MEDIUM S110/S112 findings, no HIGH/CRITICAL). PR open: https://github.com/Karmicjuju/ignition/pull/12

---

## Blockers

None.

---

## Resume

If resuming: read this file, check Status. If IN_PROGRESS, find first `[ ]` task in Plan.
All source paths are absolute under `/Users/colt/Documents/Source/Ignition`.

Key file paths:
- Branch: feat/post-mvp-sprint-1
- Schemas: src/ignition/schemas/state.py (v9), src/ignition/schemas/catalog.py
- Core: src/ignition/core/recommendations.py (new), src/ignition/core/catalog.py, src/ignition/core/state.py
- Screens: src/ignition/ui/screens/updates.py (new), src/ignition/ui/screens/home.py, src/ignition/ui/screens/settings.py
- App: src/ignition/app.py
- YAMLs: src/ignition/data/catalog/tools/*.yaml (all 12)
- Tests: tests/test_recommendations.py (new), tests/test_updates_screen.py (new), tests/test_settings_screen.py (extended), tests/test_catalog_service.py (extended)
