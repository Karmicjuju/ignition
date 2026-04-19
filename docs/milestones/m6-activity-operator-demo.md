# Milestone 6 — Activity Log, Operator Mode, Demo Hardening

## Goal

Capture and display a structured activity feed. Wire the `--operator` debug panel. Define and seed three concrete demo scenarios.

## Depends On

M4 (Installer Engine) — install events are the first activity log entries.
M5 (Auth Centre) — auth events are the second major event source.

---

## Scope

### In Scope

- `ActivityScreen` (chronological feed, expandable rows)
- `ActivityLog` core service (append, persist, cap at 500)
- Activity events emitted from InstallerEngine and AuthService
- Operator debug panel (`Ctrl+D`, only visible with `--operator` flag)
- Three defined demo scenarios, selectable from operator panel
- `ActivityLog` entry on HomeScreen showing last 5 events ("Recent activity")

### Out of Scope

- Activity log filtering or search (deferred post-M6)
- Export / copy activity log (deferred)
- Proactive notifications or banners based on activity (deferred to M7)

---

## Activity Log

### Event Structure

```python
class ActivityEvent:
    id: str               # UUID
    timestamp: datetime
    event_type: EventType
    tool_key: str | None  # for install/update events
    outcome: Outcome      # success | failure | pending | cancelled
    summary: str          # one-line human-readable description
    detail: str           # full log output or extended description
```

### Event Types

| EventType | Emitted by | Example summary |
|---|---|---|
| `tool_install` | InstallerEngine | "Installed kubectl 1.30" |
| `tool_install_failed` | InstallerEngine | "Failed to install kubectl" |
| `tool_update` | InstallerEngine (M7) | "Updated terraform 1.8 → 1.9" |
| `auth_sign_in` | AuthService | "Signed in to AWS (reactor-dev)" |
| `auth_sign_out` | AuthService | "Signed out of AWS" |
| `auth_expired` | AuthService | "AWS session expired" |
| `health_scan` | HealthEngine | "Health scan: 3 issues found" |
| `health_fix` | HealthEngine | "Fixed: SSH key permissions" |
| `onboarding_complete` | OnboardingService | "Onboarding completed (backend, devops)" |

### Persistence

- Stored as JSON array in `{XDG_STATE_HOME}/ignition/activity.json`
- Capped at 500 entries (oldest removed when cap exceeded)
- Loaded at app start; appended on each event

### ActivityLog Service

Location: `src/ignition/core/activity.py`

```python
class ActivityLog:
    def append(self, event: ActivityEvent) -> None: ...
    def get_recent(self, n: int = 50) -> list[ActivityEvent]: ...
    def get_all(self) -> list[ActivityEvent]: ...
```

`append` writes to disk immediately (no batching). File is always a valid JSON array.

---

## ActivityScreen

```
┌───────────────────────────────────────────────────────┐
│  Activity Log                                    [?]  │
├───────────────────────────────────────────────────────┤
│  Today                                                │
│  ✓ 14:32  Installed kubectl 1.30              install │
│  ✓ 14:28  Signed in to AWS (reactor-dev)       auth  │
│  ✗ 14:20  Failed to install postgresql-client  install│
│    → [expand for detail]                             │
│                                                       │
│  Yesterday                                            │
│  ✓ 11:04  Onboarding completed (backend)   onboard   │
└───────────────────────────────────────────────────────┘
```

- Grouped by day (Today / Yesterday / date)
- Selecting a row expands it inline to show `detail` (full log output, scrollable)
- Keyboard: `j`/`k` navigate rows, `Enter` expands/collapses, `Esc` returns
- Navigation shortcut: `g l` → ActivityScreen

### HomeScreen Recent Activity

Replace "No recent activity." placeholder with last 5 `ActivityEvent` entries rendered as compact one-line rows. "View all →" link navigates to ActivityScreen.

---

## Operator Mode

Activated by `--operator` CLI flag. Panel accessible via `Ctrl+D` from any screen.

### Operator Panel Contents

```
┌─────────────────────────────────────────────┐
│  Operator Panel                        [✕]  │
├─────────────────────────────────────────────┤
│  App state                                  │
│  [View raw state JSON]                      │
│                                             │
│  Catalog                                    │
│  [Force reload] (wipes ETag cache)          │
│                                             │
│  Demo scenarios                             │
│  [Seed: Partially onboarded backend]        │
│  [Seed: Healthy devops]                     │
│  [Seed: Needs attention]                    │
│                                             │
│  Version: 0.1.0   Mode: OPERATOR            │
└─────────────────────────────────────────────┘
```

- **View raw state JSON**: opens a read-only scrollable overlay showing `AppStateModel` serialised to indented JSON
- **Force reload**: calls `CatalogService.force_refresh()` which clears the cached ETag and re-fetches
- **Seed scenarios**: calls `demo.seed_*` functions then restarts the screen stack to reflect new state

Operator panel is not accessible unless `--operator` was passed. Attempting `Ctrl+D` in normal mode does nothing (no affordance shown).

---

## Demo Scenarios

Three concrete scenarios replace the current single `seed_demo_state` function.

### Scenario 1: "Partially onboarded backend dev"

- Personas: `backend`
- Onboarding: incomplete (progress halted after persona selection)
- Tools: git, python, docker installed; kubectl, helm, terraform not installed
- AWS: not configured
- Health: 1 "Recommended fix" (kubectl absent)
- Activity log: 3 install events (git, python, docker)

### Scenario 2: "Healthy devops setup"

- Personas: `backend`, `devops`
- Onboarding: complete
- Tools: all 8 devops bundle tools installed
- AWS: active session (expires 4h from seed time), profile `reactor-dev`
- Health: all Healthy
- Activity log: 8 install events, 1 onboarding complete, 1 auth sign-in

### Scenario 3: "Needs attention"

- Personas: `backend`, `devops`
- Onboarding: complete
- Tools: git, python, docker installed; kubectl outdated (version lower than `managed_version`); terraform not installed
- AWS: expired session
- Health: 2 "Needs attention" (kubectl outdated, session expired), 1 "Recommended fix" (terraform absent)
- Activity log: 5 install events, 1 auth expiry event

Each scenario is a named function in `src/ignition/core/demo.py`. The operator panel calls them by name. `--demo` without operator still seeds Scenario 1 by default.

---

## Schema Changes

Add `ActivityEvent` to schemas: `src/ignition/schemas/activity.py` (new file, `schema_version = 1`).

Extend `AppStateModel` (add `last_activity_event_id: str | None = None` for HomeScreen badge update — optional, not blocking).

---

## Verification

1. `pytest tests/test_activity*.py` — unit tests for append, cap enforcement, persistence round-trip
2. `pytest tests/test_activity_screen.py` — Pilot tests for row display, expand/collapse, day grouping
3. `pytest tests/test_demo.py` — extend to cover all three scenarios: persona state, tool counts, health summary
4. `/quality-gate` before commit
5. `/core-module-review` on `activity.py`
6. `/screen-reviewer` on `ActivityScreen` and operator panel overlay
7. `/schema-guardian` on `schemas/activity.py`
8. Manual: run `ignition --operator`, open panel, seed each scenario, verify HomeScreen updates
