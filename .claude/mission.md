# Mission: M5 — Real Installer Engine + Full Onboarding Custom Path

**Status:** IN_PROGRESS
**Started:** 2026-04-21
**Branch:** feat/m4-installer-engine
**Owner:** orchestrator

## Objective

Replace the `CatalogService.simulate_install` stub with a real platform-aware `InstallerEngine`.
Wire it into the Tool Catalog screen and the Onboarding wizard. Add the full custom onboarding
path (Phase 2b: manual tool selection checklist). Persist install history in `AppStateModel`.
Bump `AppStateModel.schema_version` from 5 to 6.

## Spec Reference

`docs/milestones/m4-installer-engine.md`

---

## UX Decisions

All decisions are locked before implementation begins.

1. **binary_url format** — Single URL per platform entry. Runtime architecture selection is done
   via `platform.machine()` at the download point (not encoded in the URL). If `binary_url` is
   absent from the manifest and the primary method fails, the tool is marked
   `InstallStatus.FAILED` immediately (no further fallback).

2. **apt-get update caching** — `apt-get update` is run once per `InstallerEngine` instance
   (i.e., once per session). The result is cached on the instance as `_apt_updated: bool`.
   Subsequent `apt-get install` calls within the same session skip the update step.

3. **PATH banner after binary install** — After writing a binary to `~/.local/bin`, inspect
   `os.environ["PATH"]` at install time. If `~/.local/bin` is NOT present, show a
   `severity="warning"` notify: "Restart your terminal or run `source ~/.zshrc` to add
   ~/.local/bin to your PATH." If it IS already on PATH, suppress the banner entirely.

4. **sudo / apt privilege model** — Ignition never invokes `sudo` directly. For commands
   requiring privilege (`apt-get install`, binary to `/usr/local/bin`), it builds the exact
   command string, shows it in a copy-paste block, and polls for the binary on PATH every
   5 seconds for up to 2 minutes. Once binary is detected, it marks install complete.

5. **Bundle install sequencing** — Tools in a bundle install sequentially (not concurrently)
   to avoid conflicting package manager locks. If a tool fails, mark it FAILED and continue
   with remaining tools. Summary at end: "N installed, M failed — [Retry failed]".

6. **InstallStatus.FAILED** — Added to the `InstallStatus` StrEnum. The existing Install
   button in the detail panel shows "Failed — Retry" when status is FAILED and is enabled.
   For INSTALLED it stays disabled. For MISSING/FAILED, it is enabled.

7. **Phase 2b UI** — Phase 2b is a scrollable `ListView` of `Checkbox` items. All recommended
   tools are pre-checked. The user may uncheck recommended tools or check additional tools from
   the full catalog. A `[Accept custom selection]` button advances to install. No search/filter
   required in M4. The "Customise" button lives on the Phase 2a review screen next to "Accept".

8. **Install button label transitions** — In `ToolCatalogScreen`, the install button ID changes
   to `btn-install` (replacing `btn-simulate-install`). Label states:
   - "Install" — MISSING or FAILED (button enabled)
   - "Installing…" — in-progress (button disabled)
   - "Installed" — INSTALLED (button disabled)
   - "Failed — Retry" — FAILED after a failed attempt (button enabled)
   Button is hidden when tool status is INSTALLED and install has not been attempted this session
   (consistent with existing show/hide logic, but now backed by real state).

9. **Post-install health re-check** — After `InstallerEngine.install()` completes (success or
   failure), `ToolCatalogScreen` triggers `HealthEngine.run_scan(categories=["tools"])` in a
   background worker and refreshes the tool list on completion. No separate UI affordance needed.

10. **InstallEvent / install_history** — `install_history: list[InstallEvent] = []` on
    `AppStateModel`, capped at 100 entries (oldest dropped). `InstallEvent` fields:
    `timestamp`, `tool_key`, `method`, `success`, `version`. Defined in `schemas/state.py`
    alongside `AppStateModel` (no separate install.py schema file).

11. **Schema version bump** — `AppStateModel.schema_version` bumps 5 → 6. The v5 → v6
    migration shim in `core/state.py` adds `install_history: []` to raw state dicts that
    don't have it, then sets `schema_version = 6`. No other field changes at this version.

12. **InstallMethod enum** — `InstallMethod` is defined in `schemas/catalog.py` as a StrEnum
    with values: `BREW`, `APT`, `BINARY`, `COPY_PASTE` (copy-paste block for sudo commands).
    `InstallerEngine.resolve_method()` returns an `InstallMethod` value.

13. **Homebrew detection** — `resolve_method()` caches the result of `which brew` on the
    instance as `_brew_available: bool | None`. On first call it runs the subprocess check;
    subsequent calls use the cached value. If Homebrew is absent on macOS, immediately falls
    back to BINARY method.

14. **Progress widget** — `ToolCatalogScreen` progress is a `Static` widget placed above the
    install button in the detail panel. It shows streaming status messages as text (not a
    real progress bar). Cleared on completion. Hidden when no install is in progress.

15. **OnboardingScreen phase tracking** — Phase 2b is represented internally as `_phase = 3`
    (Phase 2a stays as `_phase = 2`). The accept button in Phase 2b is `btn-custom-accept`.
    The customise button added in Phase 2a is `btn-customise`.

16. **simulate_install removal** — `CatalogService.simulate_install()` is fully removed. The
    method is not deprecated-and-kept; it is deleted. Any callers (currently only
    `ToolCatalogScreen`) are updated. Tests covering `simulate_install` are replaced with tests
    for the new `InstallerEngine.install()` integration.

---

## Plan

### Layer 1 — Schema

- [x] S1: Verify/update `src/ignition/schemas/catalog.py` — add `InstallStatus.FAILED`,
      add `InstallMethod` StrEnum, verify `PlatformInstallMethods` fields match M4 YAML spec.
      No new schema file needed; bump `CATALOG_SCHEMA_VERSION` if `ToolInfo` fields change.
- [x] S2: Update `src/ignition/schemas/state.py` — add `InstallEvent` model, add
      `install_history: list[InstallEvent] = []` to `AppStateModel`, bump
      `STATE_SCHEMA_VERSION` 5 → 6.

### Layer 2 — Core

- [ ] C1: Create `src/ignition/core/installer.py` — `InstallerEngine` with `install()`,
      `install_bundle()`, `resolve_method()`. All subprocess calls use
      `asyncio.create_subprocess_exec`. Caches `_brew_available` and `_apt_updated` per
      instance. Reads `tool.install_methods` to dispatch. Records `InstallEvent` and
      appends to state.
- [ ] C2: Update `src/ignition/core/catalog.py` — remove `simulate_install()`. Add
      `mark_installed()` method that updates in-memory status and version for a tool key
      (called by `InstallerEngine` after success). Add `mark_failed()` similarly.
- [x] C3: Update `src/ignition/core/state.py` — add v5 → v6 migration shim (adds
      `install_history: []` to old state dicts, bumps `schema_version` to 6).
      VERIFIED: shim present, 4 migration tests pass.

### Layer 3 — UI

- [ ] U1: Update `src/ignition/ui/screens/catalog.py` — replace `btn-simulate-install` with
      `btn-install`; wire `on_button_pressed` to `InstallerEngine.install()` via `@work`;
      add progress `Static` widget; add post-install health re-check worker; update
      `_STATUS_CLASS` / `_STATUS_LABEL` for `FAILED` state.
- [ ] U2: Update `src/ignition/ui/screens/onboarding.py` — add Phase 2b checklist (Phase 3
      internally); add `btn-customise` button in Phase 2a; add `btn-custom-accept` button;
      wire `_complete_onboarding` to use custom tool selection when via Phase 2b path.

### Layer 4 — Tests

- [ ] T1: Create `tests/test_installer_engine.py` — unit tests with mocked subprocess for
      `InstallerEngine`: method resolution (brew/apt/binary/copy-paste), success path,
      failure path (no fallback URL → FAILED), `_apt_updated` cache, PATH banner logic,
      `install_bundle` sequencing, `InstallResult` fields.
- [ ] T2: Create `tests/test_onboarding_custom.py` — Pilot tests for Phase 2b checklist:
      customise button visible in Phase 2a, Phase 2b shows all recommended tools pre-checked,
      uncheck a tool → excluded from accepted list, check additional tool → included,
      `btn-custom-accept` triggers `OnboardingComplete` with correct tool list.
- [ ] T3: Update `tests/test_catalog_service.py` — replace `simulate_install` tests with
      tests for `mark_installed()` / `mark_failed()`. Add assertion that `simulate_install`
      does NOT exist on `CatalogService`.

### Layer 5 — QA + Security

- [ ] Q1: `/quality-gate` — ruff lint, ruff format, ty type check, pytest all pass.
- [ ] Q2: `/security-review` — mandatory; installer touches subprocess extensively.

---

## Resume

If resuming: read this file, check `[x]` tasks, find the first `[ ]` task, continue from there.

All source paths are absolute under `/Users/colt/Documents/Source/Ignition`.

Layer dispatch order (strict — never skip layers):
1. S1 + S2 in parallel (schema-architect)
2. C1 + C2 + C3 in parallel (core-engineer) — only after S1 and S2 both complete
3. U1 + U2 in parallel (ui-builder) — only after C1, C2, C3 all complete
4. T1 + T2 + T3 in parallel (test-writer) — only after U1 and U2 both complete
5. Q1 quality-gate → Q2 security-review (qa-runner)

Key patterns:
- Schemas: `src/ignition/schemas/health.py` (StrEnum + Pydantic BaseModel pattern)
- Core: `src/ignition/core/health.py` (`_run_subprocess`, structlog, asyncio pattern)
- Screens: `src/ignition/ui/screens/catalog.py` (Screen[None], inject AppStateModel, @work)
- Tests: `tests/test_health_engine.py` + `tests/test_catalog_service.py` (isolated_paths, AsyncMock)
- State migration: `src/ignition/core/state.py` (shim pattern from v4→v5 for reference)
- Branch: `feat/m4-installer-engine`
