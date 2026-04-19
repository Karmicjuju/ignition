# Milestone 3 — Health & Diagnostics Engine

## Goal

Replace the "Run Diagnostics" stub on HomeScreen with a working health scan engine and results screen. Add a Settings screen backed by the existing `AppConfigModel`.

## Depends On

M2 (Tool Catalog) — health checks reference installed tool state from `AppStateModel`.

---

## Scope

### In Scope

- `HealthScreen` with scan results grouped by category
- `SettingsScreen` with immediate-apply preferences
- `HealthEngine` core service that runs categorised checks
- Four health categories: **Tools**, **Configs**, **Shell integration**, **Permissions**
- Four result states: **Healthy**, **Recommended fix**, **Needs attention**, **Manual**
- Auto-fix for safe issues (no privilege required)
- Copy-paste command surface for privileged fixes
- Re-scan after successful auto-fix
- Navigation: `g h` → HealthScreen, `g s` → SettingsScreen (consistent with existing `g t` → Catalog)

### Out of Scope

- Background / scheduled scans (deferred to M7)
- Network and State health categories (deferred)
- Repair Engine orchestration (deferred to M4)
- Links to internal documentation (deferred)

---

## Health Categories & Checks

### Tools

For each tool tracked in `AppStateModel.installed_tools`:
- Is the tool binary present on PATH? (`which <tool>`)
- Does the installed version match the catalog's `managed_version`? (`<tool> --version`)

Result mapping:
- Binary absent + tool is managed → **Needs attention**
- Binary absent + tool is optional → **Recommended fix**
- Version mismatch (managed) → **Recommended fix**
- Version mismatch (flexible) → **Healthy** (noted, not flagged)

### Configs

Shell config files to check (in order): `~/.zshrc`, `~/.bashrc`, `~/.profile`, `~/.bash_profile`.

Checks:
- Does `~/.aws/config` exist if AWS is in the user's tool bundle?
- Does the active shell config source the Ignition `includes.sh` block? (Checked by looking for `# ignition` marker)
- Are known required environment variables (`AWS_DEFAULT_REGION`, etc.) resolvable?

Result mapping:
- Missing file that Ignition owns → **Needs attention**
- Missing env var (non-critical) → **Recommended fix**
- Ignition block absent → **Recommended fix**

### Shell Integration

Checks:
- Is `~/.local/bin` on `$PATH`?
- Is the Ignition `includes.sh` block present and syntactically valid?

Auto-fix: Add `~/.local/bin` to PATH by appending to the detected shell config (with user confirmation prompt in TUI before writing — this is the one shell-file write Ignition performs, with user consent).

**Ignition never silently edits shell config files.** It always shows the line it will append and requires an explicit "Apply" action.

Result mapping:
- `~/.local/bin` absent from PATH → **Recommended fix** (with apply button)
- `includes.sh` block absent → **Recommended fix**
- `includes.sh` parse error → **Needs attention**

### Permissions

Checks:
- SSH keys in `~/.ssh/` have mode `0600` (private) and `0644` (public)
- `~/.aws/credentials` has mode `0600` if it exists
- `~/.local/bin` is writable by the current user

Privilege model: `chmod` requires no sudo for user-owned files. Ignition runs `chmod` directly for files the user owns.

For system-owned files or directories: surface a copy-paste `sudo chmod` command. User runs it in their terminal; Ignition detects success on manual re-scan ("Re-check" button).

Result mapping:
- Overly permissive key → **Needs attention** (auto-fixable with direct chmod)
- Non-writable `~/.local/bin` → **Needs attention** (may need sudo)

---

## Result States

| State | Colour | Meaning |
|---|---|---|
| Healthy | Green | Check passed, no action needed |
| Recommended fix | Yellow | Non-blocking issue; auto-fix available |
| Needs attention | Orange | Blocking or degraded state; fix available |
| Manual | Red | Fix requires steps Ignition cannot perform; shown command or guidance |

---

## Privilege Model

| Fix type | Ignition action |
|---|---|
| No privilege needed | Run directly (chmod on owned file, write to XDG state dir, etc.) |
| Requires sudo | Show formatted copy-paste block; poll for success on re-check |
| Requires manual steps | Show numbered instructions; user marks complete or triggers re-scan |

Ignition never invokes `sudo`. It surfaces the exact command in a styled code block with a copy button.

---

## Screens

### HealthScreen

```
┌─────────────────────────────────────────────────────┐
│  Health & Diagnostics            [Scan] [?]          │
├─────────────────────────────────────────────────────┤
│  ● Tools (4 checks)          3 Healthy  1 ⚠ Attn    │
│    ✓ git 2.44                              Healthy   │
│    ✓ docker 25.0                           Healthy   │
│    ✓ python 3.14                           Healthy   │
│    ⚠ kubectl — not found                  Needs attn │
│      [Install via Catalog]                           │
│                                                      │
│  ● Configs (2 checks)        2 Healthy               │
│  ● Shell integration (2 checks)  1 Rec. fix          │
│    → ~/.local/bin not on PATH    [Apply fix]         │
│  ● Permissions (3 checks)    3 Healthy               │
└─────────────────────────────────────────────────────┘
```

- Categories are collapsible
- Each issue row shows: icon, description, result state, action button (if fixable)
- "Scan" re-runs all checks; individual "Re-check" available per issue after manual fix

### SettingsScreen

```
┌──────────────────────────────────────────────────┐
│  Settings                                   [?]  │
├──────────────────────────────────────────────────┤
│  Theme           ● Dark  ○ Light                 │
│  Density         ● Full  ○ Compact               │
│  Motion          ● Standard  ○ Reduced           │
│  Automation      ● Observe  ○ Assist  ○ Autopilot│
└──────────────────────────────────────────────────┘
```

- All settings apply immediately on selection (no Save button)
- Backed by `AppConfigModel` in `src/ignition/core/config.py`
- Navigation: Esc returns to previous screen

---

## Core Module: `HealthEngine`

Location: `src/ignition/core/health.py`

```python
class CheckResult:
    category: str
    check_id: str
    label: str
    state: HealthState  # healthy | recommended | needs_attention | manual
    detail: str
    fix_type: FixType   # none | auto | copy_paste | manual_steps
    fix_command: str | None
    fix_steps: list[str]

class HealthEngine:
    async def run_scan(self, categories: list[str] | None = None) -> list[CheckResult]: ...
    async def apply_fix(self, check_id: str) -> bool: ...  # True = success
```

Each category is a module of check functions. Checks run concurrently via `asyncio.gather`. Individual check failures (exceptions) are caught and reported as `needs_attention` rather than crashing the scan.

---

## Schema Changes

Add to `AppStateModel` (bump `schema_version` to 4):
```python
last_health_scan: datetime | None = None
health_summary: dict[str, HealthState] = {}  # category → worst state
```

---

## Open Questions Deferred to Implementation

- Which shell config file takes priority if multiple exist? (Proposed: detect active shell from `$SHELL`, use its rc file)
- Should "Apply fix" for PATH update restart the shell prompt or just inform the user to restart? (Proposed: show instruction banner, no restart attempt)

---

## Verification

1. `pytest tests/test_health*.py` — unit tests for each check function with mocked filesystem
2. `pytest tests/test_health_screen.py` — Pilot tests for scan trigger, result display, apply-fix button
3. `/quality-gate` before commit
4. `/screen-reviewer` on HealthScreen and SettingsScreen
5. `/core-module-review` on `health.py`
6. Manual: run `ignition` with a tool binary removed from PATH; confirm "Needs attention" appears
