# Milestone 7 — Update Engine + Persona Lifecycle

## Goal

Detect and apply available tool updates. Allow users to manage their personas after onboarding. Telemetry is explicitly deferred — no event capture or upload in this milestone.

## Depends On

M4 (Installer Engine) — update dispatch reuses the same install methods.
M6 (Activity Log) — update events are logged via ActivityLog.

---

## Scope

### In Scope

- Update detection: compare installed version vs. catalog `managed_version`
- Update badge on HomeScreen and in ToolCatalogScreen rows
- "Update all managed tools" action
- Per-tool update button in catalog detail panel
- Persona add/remove from SettingsScreen
- Conflict resolution for version mismatches across personas

### Out of Scope

- Ignition self-update (deferred post-MVP)
- Automatic/scheduled updates (deferred post-MVP)
- Downgrade / rollback to previous version (deferred)
- Telemetry event capture or upload (explicitly deferred post-MVP)

---

## Update Detection

### Version Comparison

Installed version is stored in `AppStateModel.installed_tools[key].installed_version` (set by InstallerEngine post-install).

Catalog `managed_version` is the authoritative target. Comparison uses standard semver (`packaging.version.Version`).

A tool is considered **outdated** if:
- `installed_version` is set (i.e., tool is installed)
- `managed_version` is set in the catalog
- `installed_version < managed_version`

Tools with `governance_tier = "flexible"` are never marked outdated by Ignition (user manages their own version).

### Check Frequency

On-launch only: update check runs once at app start, in a background `@work` worker. No periodic re-check during a session. Result is cached in memory for the session.

User can manually trigger a re-check via a "Check for updates" button on the HomeScreen or via the catalog refresh.

### Update Badge

HomeScreen: "X tools have updates" panel item, clickable → navigates to ToolCatalogScreen filtered to outdated tools.

ToolCatalogScreen: outdated tools show an "Update available: X.X → Y.Y" tag on the row and in the detail panel.

---

## Update Flow

Same dispatch as InstallerEngine — reuses `InstallerEngine.install()` with `force=True` flag that skips the "already installed" guard.

Progress UI: same per-tool progress indicator as install.

Post-update: re-run `post_install_check` from the tool manifest; on success, update `installed_version` in state and emit `tool_update` ActivityEvent.

### "Update All" Action

HomeScreen button and ToolCatalogScreen action. Updates all managed tools that are outdated, sequentially (same bundle approach as install). Summary shown on completion.

---

## Persona Lifecycle

### Settings Screen Addition

SettingsScreen gains a "Personas" section below preferences:

```
  Personas
  ✓ backend    (active)
  ✓ devops     (active)
  ○ frontend
  ○ security
  ○ contractor

  [Manage personas]
```

"Manage personas" opens a modal with checkboxes for all five personas.

### Adding a Persona

1. User checks a new persona in the modal
2. Ignition shows the recommended tools for that persona that are not yet installed
3. User is prompted: "Install X new tools for this persona? [Install] [Skip]"
4. If Install: triggers InstallerEngine bundle install (same flow as onboarding)
5. If Skip: persona is added without installing tools; health check will flag missing tools

### Removing a Persona

1. User unchecks a persona in the modal
2. Persona is removed from `AppStateModel.active_personas`
3. Tools are **not** uninstalled (tools are user assets; Ignition does not delete without an explicit "Uninstall" action, which is out of scope for M7)
4. A note is shown: "Tools from this persona remain installed. They will no longer appear in health checks for this role."

### Conflict Resolution

When two active personas recommend the same tool at different version tiers (e.g., `backend` wants Python 3.12, `devops` wants Python 3.14):

- **Rule:** Latest governed version wins
- **Display:** Tool detail panel shows "Version governed by: devops persona (3.14)" when both personas are active
- No user prompt required — resolved silently, noted in detail view only

---

## Core Module: `UpdateEngine`

Location: `src/ignition/core/updater.py`

```python
class UpdateInfo:
    tool_key: str
    installed_version: str
    available_version: str
    governance_tier: str

class UpdateEngine:
    async def check_updates(self) -> list[UpdateInfo]: ...
    async def update_tool(self, tool_key: str) -> InstallResult: ...  # reuses InstallerEngine
    async def update_all(
        self,
        progress_cb: Callable[[str, str], None],
    ) -> list[InstallResult]: ...
```

`check_updates` returns only managed tools with `installed_version < managed_version`. Flexible-tier tools are excluded.

---

## Schema Changes

No new schema files. `AppStateModel` additions (bump version):
```python
last_update_check: datetime | None = None
available_updates: list[str] = []  # list of tool_keys with available updates
```

---

## Telemetry Note

`install_id` already exists in `AppStateModel` for future telemetry use. No event capture, no upload pipeline, no privacy statement, and no opt-out UX are needed in M7. This remains deferred until a destination and privacy review are completed post-MVP.

---

## Open Questions Deferred to Implementation

- `packaging` library: add as a runtime dependency for semver comparison, or implement a simple `X.Y.Z` tuple comparison to avoid the dep?
- Notification UX for available updates: badge count on HomeScreen is the default; a toast on launch would be higher signal but potentially annoying — implement badge only in M7

---

## Verification

1. `pytest tests/test_updater*.py` — unit tests for version comparison, outdated detection, flexible-tier exclusion
2. `pytest tests/test_persona_lifecycle.py` — unit tests for add persona (with/without install), remove (no uninstall), conflict resolution
3. `pytest tests/test_settings_screen.py` — Pilot tests for persona modal, manage personas flow
4. `/quality-gate` before commit
5. `/core-module-review` on `updater.py`
6. `/screen-reviewer` on updated SettingsScreen
7. Manual: seed scenario 3 (demo), open catalog, confirm update badges appear, run "Update all", confirm versions updated and activity log shows events
