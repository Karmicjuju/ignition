# Mission: M7 — Update Engine + Persona Lifecycle

**Status:** COMPLETED
**Started:** 2026-04-21
**Branch:** feat/m7-updates-personas
**Owner:** orchestrator

## Objective

Detect and apply available tool updates. Allow users to manage their personas after
onboarding. UpdateEngine reuses InstallerEngine — no new subprocesses. Telemetry deferred.

## Spec Reference

`docs/milestones/m7-updates-personas.md`

---

## UX Decisions

All decisions locked before implementation begins.

1. **`packaging` dependency** — Add `packaging>=24.0` as a runtime dependency in
   `pyproject.toml`. Cleaner than rolling our own semver; avoids edge cases with pre-release
   and build metadata strings. No alternative considered.

2. **ToolCatalogScreen outdated filter** — Add `filter_outdated: reactive[bool] =
   reactive(False)` as a class-level reactive attribute on `ToolCatalogScreen`. When True,
   the tool list shows only tools with `install_status == InstallStatus.OUTDATED`.
   Toggled to True when HomeScreen navigates to catalog via the update badge.
   Constructor gains `filter_outdated: bool = False` parameter.

3. **Persona management modal** — `PersonaManagerModal` is a `ModalScreen[None]` subclass.
   Uses `BINDINGS = [Binding("escape", "app.pop_screen", "Close")]`. Same pattern as
   `OperatorPanel`. Checkboxes implemented as Textual `Checkbox` widgets, one per persona,
   inside a `Vertical` with a title and a "Done" button. Posted messages propagate changes
   back to `SettingsScreen` which updates `AppStateModel.selected_personas` and saves state.

4. **"Update all" button placement** — HomeScreen: a "Update All Tools" button added to the
   `#quick-actions` `Horizontal`, shown only when `AppStateModel.available_updates` is
   non-empty. ToolCatalogScreen: an "Update All" button added to the `#toolbar` row, shown
   only when `filter_outdated` is True or `available_updates` is non-empty.

5. **On-launch update check** — `IgnitionApp.on_mount()` gains a `@work(thread=True)` worker
   `_check_updates_on_launch()` that constructs `UpdateEngine` and calls `check_updates()`.
   Results are stored in `AppStateModel.available_updates` (list of tool_keys) and
   `AppStateModel.last_update_check` (datetime). Worker runs after state is loaded and home
   screen is pushed. Uses `call_from_thread` to save state after update.

6. **"Add persona" install prompt** — After user checks a new persona in `PersonaManagerModal`,
   a second modal (`PersonaInstallPromptModal`) is pushed immediately showing the list of
   uninstalled recommended tools and two buttons: "Install" and "Skip". If Install is pressed
   the modal dismisses and `SettingsScreen` runs the install bundle via a `@work` worker.
   If Skip is pressed the persona is added with no install. This second modal is a lightweight
   `ModalScreen[bool]` that returns True (Install) or False (Skip).

7. **Conflict resolution display** — When two active personas recommend the same tool at
   different version tiers, the `_show_detail()` panel in `ToolCatalogScreen` appends a line
   "Version governed by: {persona} persona ({version})" when more than one active persona
   tags the tool. Resolved silently using max of managed_version; displayed in detail only.

8. **"Removing a persona" note** — Shown as a `self.notify()` call in `SettingsScreen` after
   `AppStateModel.selected_personas` is updated: "Tools from this persona remain installed.
   They will no longer appear in health checks for this role."

9. **`AppStateModel.selected_personas` vs `active_personas`** — The spec calls the field
   `active_personas` but the existing schema uses `selected_personas`. Use `selected_personas`
   throughout M7 to avoid introducing a new field. No schema rename needed.

10. **`installed_tools` field** — The spec references `AppStateModel.installed_tools[key]
    .installed_version`. This field does not exist in the current schema (v7). Instead,
    `InstallerEngine` stores version in `CatalogService` in-memory and in `install_history`.
    For M7, `UpdateEngine.check_updates()` will use `CatalogService.get_all_tools()` to
    find tools with `install_status == INSTALLED` and compare `tool.version` (installed
    version, set by `mark_installed`) vs `tool.managed_version` (added to `ToolInfo`).
    `ToolInfo` gains a `managed_version: str | None = None` field (catalog schema change).
    `version_policy` field already exists — `"flexible"` tier tools are excluded.

11. **`managed_version` field on ToolInfo** — Add `managed_version: str | None = None` to
    `ToolInfo` in `src/ignition/schemas/catalog.py`. This is the authoritative upgrade target.
    For bundled catalog tools, `managed_version` defaults to the same as `version` if set.
    For flexible-tier tools, `managed_version` is always None in the manifest.

---

## Plan

### Layer 1 — Schema

- [x] S1: Update `src/ignition/schemas/state.py` — add `last_update_check: datetime | None = None`
      and `available_updates: list[str] = Field(default_factory=list)` to `AppStateModel`;
      bump `STATE_SCHEMA_VERSION` 7 → 8. Run `/schema-guardian`.
- [x] S2: Update `src/ignition/schemas/catalog.py` — add `managed_version: str | None = None`
      to `ToolInfo`. No schema_version bump needed (catalog schema stays at 1; field is additive
      with None default). Run `/schema-guardian`.

### Layer 2 — Core

- [x] C1: Create `src/ignition/core/updater.py` — `UpdateInfo` dataclass, `UpdateEngine` class
      with `check_updates() -> list[UpdateInfo]`, `update_tool(tool_key) -> InstallResult`,
      `update_all(progress_cb) -> list[InstallResult]`. Inject `CatalogService`, `InstallerEngine`,
      `ActivityLog | None`. Flexible-tier tools excluded. Emit `TOOL_UPDATE` events.
      Run `/core-module-review`.
- [x] C2: Update `src/ignition/core/state.py` — add v7 → v8 migration shim: setdefault
      `last_update_check = None` and `available_updates = []`, bump schema_version to 8.
      Run `/core-module-review`.
- [x] C3: Update `src/ignition/app.py` — add `@work(thread=True)` worker `_check_updates_on_launch`
      called after HomeScreen is pushed in `on_mount`. Worker constructs `UpdateEngine`,
      calls `check_updates()`, stores results in `_current_state.available_updates` and
      `last_update_check`, calls `save_state` via `call_from_thread`. Run `/core-module-review`.
- [x] C4: Update `pyproject.toml` — add `packaging>=24.0` to `[project] dependencies`.

### Layer 3 — UI

- [x] U1: Update `src/ignition/ui/screens/home.py` — add update badge `Static` (id="update-badge")
      showing "X tools have updates" when `available_updates` is non-empty; clicking it or pressing
      the "Update All Tools" button triggers update-all via a `@work` worker. Badge navigates to
      `ToolCatalogScreen(state, filter_outdated=True)`. Add "Update All Tools" `Button` to
      `#quick-actions`. Run `/screen-reviewer`.
- [x] U2: Update `src/ignition/ui/screens/catalog.py` — add `filter_outdated: bool = False`
      constructor param, `filter_outdated` reactive attribute. Add `#btn-update-tool` Button to
      detail panel (shown only when tool is installed + outdated). Add `#btn-update-all` Button
      to `#toolbar`. Update `_show_detail` to show "Update available: X → Y" tag and conflict
      resolution note. Run `/screen-reviewer`.
- [x] U3: Update `src/ignition/ui/screens/settings.py` — add Personas section below preferences:
      readonly status display of active personas + "Manage personas" button. Create
      `PersonaManagerModal(ModalScreen[None])` in same file (or separate
      `src/ignition/ui/screens/persona_modal.py`). Modal shows checkboxes for all 5 personas;
      on check → `PersonaInstallPromptModal` for new personas; on uncheck → remove + notify.
      Run `/screen-reviewer`.

### Layer 4 — Tests

- [x] T1: Create `tests/test_updater.py` — unit tests: version comparison logic, outdated
      detection, flexible-tier exclusion, `check_updates` returns correct list, `update_tool`
      reuses InstallerEngine (mock), `update_all` sequential, `TOOL_UPDATE` event emitted.
      Run `/test-critic`.
- [x] T2: Create `tests/test_persona_lifecycle.py` — unit tests: add persona (with and without
      install), remove persona (no uninstall, selected_personas updated), conflict resolution
      (highest version wins), `selected_personas` persistence. Run `/test-critic`.
- [x] T3: Update `tests/test_settings_screen.py` (extend) or create if absent — Pilot tests:
      Personas section visible, "Manage personas" opens modal, checkbox state reflects
      `selected_personas`, persona add/remove flow. Run `/test-critic`.

### Layer 5 — QA + Security

- [x] Q1: `/quality-gate` — ruff lint, ruff format, ty type check, pytest all pass.
      225 passed, 2 skipped (Linux-only). All four checks green.
- [x] Q2: `/security-review` — WARN (MEDIUM only). S110 ×2 in UI files (silent except/pass);
      no HIGH/CRITICAL. Auto-proceeded. UpdateEngine subprocess path reuses InstallerEngine
      create_subprocess_exec exclusively; persona_id from hardcoded widget IDs (safe).

---

## Resume

If resuming: read this file, check `[x]` tasks, find the first `[ ]` task, continue from there.

All source paths are absolute under `/Users/colt/Documents/Source/Ignition`.

Layer dispatch order (strict — never skip layers):
1. S1 + S2 in parallel (schema-architect)
2. C1 + C2 + C3 + C4 in parallel (core-engineer) — only after S1 and S2 both complete
3. U1 + U2 in parallel, then U3 after both (ui-builder) — only after all C tasks complete
4. T1 + T2 + T3 in parallel (test-writer) — only after U1, U2, U3 all complete
5. Q1 quality-gate → Q2 security-review (qa-runner)

Key patterns:
- Schemas: `src/ignition/schemas/state.py` (v8 now), `src/ignition/schemas/catalog.py`
- Core: `src/ignition/core/installer.py` (InstallerEngine — reuse with force param)
- Core: `src/ignition/core/activity.py` (ActivityLog — inject for TOOL_UPDATE)
- Screens: `src/ignition/ui/screens/operator.py` (ModalScreen pattern for persona modal)
- Tests: `tests/test_installer.py` + `tests/test_activity_log.py` (patterns)
- State migration: `src/ignition/core/state.py` (shim pattern; add v7→v8)
- Branch: `feat/m7-updates-personas`
