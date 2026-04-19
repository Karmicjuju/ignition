# Mission: M2 — Tool Catalog

**Status:** COMPLETED  
**Branch:** feat/m2-tool-catalog  
**Created:** 2026-04-19  
**Last updated:** 2026-04-19

---

## Milestone Summary

### What ships in M2
- `ToolInfo` Pydantic v2 schema with `InstallStatus` enum; `AppStateModel` extended with `tool_catalog_cache`
- `CatalogService` in `src/ignition/core/catalog.py` — hardcoded stub catalogue of 12 tools covering all 5 personas; clean `_load_tools()` seam for M3 manifest loading
- `ToolCatalogScreen` at `src/ignition/ui/screens/catalog.py` — left sidebar category filter, right scrollable tool list, bottom inline detail panel, `/`-activated search
- Navigation wiring: `g t` global keybind in `IgnitionApp`; "Tool Catalog" button added to `HomeScreen` quick-actions
- Unit tests for `CatalogService`; Textual Pilot integration test for `ToolCatalogScreen`

### What is deferred to M3
- Loading tools from a real external manifest YAML repo
- Actual install/uninstall execution (subprocesses, version checks)
- Per-tool repair workflows
- Version governance tiers (Managed / Recommended / Flexible / Deprecated / Experimental) beyond the `managed: bool` flag
- AWS-specific tool auth flows

---

## UX Decisions

All decisions below fill gaps in the UX spec and are authoritative for M2 implementation.

### D1 — Detail panel placement: bottom split, not modal, not right split

**Decision:** When the user presses Enter on a tool row the screen splits horizontally: the tool list occupies the upper ~65% and a detail panel occupies the lower ~35%. A second Enter (or Escape) collapses the panel.

**Justification:**
- A right split would compress the tool list and category sidebar into a very narrow strip on typical 80-column terminals, making labels illegible.
- A modal blocks the list entirely, breaking the browse-while-reading mental model.
- A bottom split is the Textual/tmux convention for "inspector" panels; it lets the user keep scanning the list without closing the detail view. The 65/35 ratio is borrowed from Textual's own developer console split.

**Detail panel fields (top-to-bottom):**
1. Tool name (bold) + install status badge on the same line
2. Full description (wrapped)
3. Version (or "unversioned" if absent)
4. Categories (comma-separated)
5. Persona tags (comma-separated)
6. Managed flag: "Yes — version pinned by Reactor ops" / "No — self-managed"
7. "Simulate Install" button (only shown when `install_status != INSTALLED`)

### D2 — Search vs category filter interaction: search overrides, category resets

**Decision:** When the user activates search (`/`), any active category filter is temporarily suspended. The search results span all categories. The category sidebar visually dims (opacity: 50%) to signal it is inactive. Pressing Escape exits search, restores the last category filter selection, and re-brightens the sidebar.

**Justification:**
- Stacking search AND category filter is the right long-term UX, but with only 12 stub tools the intersection frequently returns zero results, which would confuse evaluators. "Override" mode is simpler, always returns something, and is correct for the M2 scope.
- A clear visual dim signal prevents confusion about why category selections have no effect during search.

### D3 — Stub tool list (12 tools, all 5 personas covered)

| Tool key          | Display name          | Personas                       | Managed | Categories                   |
|-------------------|-----------------------|--------------------------------|---------|------------------------------|
| `git`             | Git                   | all                            | No      | vcs, core                   |
| `python`          | Python 3              | backend, contractor            | Yes     | language, core              |
| `docker`          | Docker                | backend, devops                | Yes     | container, infra            |
| `node`            | Node.js               | frontend                       | Yes     | language, core              |
| `pnpm`            | pnpm                  | frontend                       | No      | package-manager             |
| `awscli`          | AWS CLI v2            | all                            | Yes     | cloud, auth                 |
| `terraform`       | Terraform             | devops                         | Yes     | infra, iac                  |
| `kubectl`         | kubectl               | devops                         | Yes     | container, orchestration    |
| `helm`            | Helm                  | devops                         | No      | container, orchestration    |
| `trivy`           | Trivy                 | security                       | Yes     | security, scanning          |
| `vault`           | HashiCorp Vault CLI   | security                       | Yes     | security, secrets           |
| `postgresql-client` | psql (PostgreSQL)   | backend                        | No      | database, core              |

Versions are pinned stub strings (e.g. "2.15.1") — no real detection in M2.

### D4 — InstallStatus enum values

```python
class InstallStatus(str, enum.Enum):
    INSTALLED   = "installed"     # detected on PATH at expected version
    OUTDATED    = "outdated"      # detected but wrong version
    MISSING     = "missing"       # not found on PATH
    UNMANAGED   = "unmanaged"     # present but not version-managed by Ignition
```

In stub mode all tools default to `MISSING` except `git` and `awscli` which default to `INSTALLED` (reasonable for a developer machine).

### D5 — "Simulate Install" behaviour

**Decision:** Pressing "Simulate Install":
1. Logs a structured no-op via structlog (`catalog.simulate_install`, tool name, timestamp).
2. Mutates `install_status` to `INSTALLED` on the in-memory `ToolInfo` object held by `CatalogService` (not persisted to `AppStateModel.tool_catalog_cache` in M2 — persistence is M3 scope).
3. The detail panel refreshes to show `INSTALLED` badge and hides the button.
4. A Textual `notify()` toast confirms: "Simulated install of <tool name>."

**Justification:** Updating in-memory state makes the demo feel alive without touching disk or running real subprocesses. Excluding persistence from M2 keeps the scope clean — M3 will wire `tool_catalog_cache` properly once manifest loading exists.

### D6 — Category sidebar behaviour

- Categories are derived dynamically from the loaded tool list (no hardcoded list in the widget).
- "All" is always the first entry and is selected by default.
- Selecting a category filters the right panel immediately (reactive, no confirm needed).
- Categories sort alphabetically after "All".
- A tool may appear in multiple categories; it appears once in the filtered list if any of its categories match.

### D7 — Keyboard navigation model

| Key        | Action                                          |
|------------|-------------------------------------------------|
| `/`        | Activate search input (focus moves to search bar at top of main panel) |
| `Escape`   | Exit search / close detail panel / return to home |
| `Up/Down`  | Navigate tool list rows                         |
| `Enter`    | Open/close detail panel for focused tool        |
| `g t`      | (global, in IgnitionApp) Push ToolCatalogScreen |
| `q`        | Quit (existing global binding)                  |

---

## Layered Task Plan

### Layer 1 — Schema (schema-architect)

- [x] **S1** — Create `src/ignition/schemas/catalog.py`
  - Owner: schema-architect
  - Inputs: D3 (stub tool list), D4 (InstallStatus enum), UX decisions D1–D7
  - Outputs:
    - `InstallStatus` enum (`str`, `enum.Enum`, four values per D4)
    - `ToolInfo` Pydantic v2 model: `schema_version: int = CATALOG_SCHEMA_VERSION`, `key: str`, `name: str`, `description: str`, `version: str`, `categories: list[str]`, `persona_tags: list[str]`, `managed: bool`, `install_status: InstallStatus`
    - All fields annotated; no mutable defaults (use `Field(default_factory=...)` for lists)
    - `CATALOG_SCHEMA_VERSION = 1` module-level constant
  - Done criteria: file exists, no bare `list[...]` or `dict[...]` defaults, `schema_version` field present, `InstallStatus` has exactly four members

- [x] **S2** — Extend `src/ignition/schemas/state.py`
  - Owner: schema-architect
  - Inputs: S1 (ToolInfo model), existing `AppStateModel`
  - Outputs: `tool_catalog_cache: list[ToolInfo] = Field(default_factory=list)` added to `AppStateModel`; `STATE_SCHEMA_VERSION` bumped to `2`
  - Done criteria: field present, default is a factory (not `[]`), version constant incremented, existing fields unchanged

### Layer 2 — Core (core-engineer)

- [x] **C1** — Create `src/ignition/core/catalog.py`
  - Owner: core-engineer
  - Inputs: S1 (ToolInfo, InstallStatus), S2 (AppStateModel), D3 (12 stub tools), D5 (simulate install)
  - Outputs: `CatalogService` class with:
    - `__init__`: initialises structlog logger `ignition.core.catalog`
    - `_load_tools() -> list[ToolInfo]`: private; returns hardcoded stub list (12 tools per D3); docstring notes "replace with manifest YAML load in M3"
    - `get_all_tools() -> list[ToolInfo]`: returns `_load_tools()` result (or cached copy on second call — simple instance-level cache via `self._tools`)
    - `get_tools_for_personas(persona_ids: list[str]) -> list[ToolInfo]`: filters by `persona_tags` intersection; unknown ids silently skipped; logs `catalog.filter_by_persona`
    - `search_tools(query: str) -> list[ToolInfo]`: case-insensitive substring match on `name`, `description`, and `categories`; logs `catalog.search`
    - `simulate_install(tool_key: str) -> ToolInfo | None`: mutates `install_status` to `INSTALLED` on in-memory tool; logs `catalog.simulate_install`; returns updated `ToolInfo` or `None` if key not found
  - Done criteria: all five public/private methods present with correct return types; no `list[ToolInfo]` as bare default; structlog used for every mutation/query event; `_load_tools` docstring references M3

### Layer 3 — UI (ui-builder)

- [x] **U1** — Create `src/ignition/ui/screens/catalog.py`
  - Owner: ui-builder
  - Inputs: C1 (CatalogService), S1 (ToolInfo, InstallStatus), D1–D7 (all UX decisions), existing screen patterns from `home.py` and `onboarding.py`
  - Outputs: `ToolCatalogScreen(Screen[None])` with:
    - `BINDINGS`: `("escape", "app.pop_screen", "Back")`, `("/", "focus_search", "Search")`
    - Layout: `Horizontal` root → `Vertical#sidebar` (category list, `ListView`) + `Vertical#main` (search `Input` + `ListView#tool-list`)
    - Bottom detail panel: `Vertical#detail-panel` hidden by default; shown via CSS `display: block` when a tool is selected; contains `Static#detail-name`, `Static#detail-description`, `Static#detail-meta`, `Button#btn-simulate-install`
    - Category sidebar populated from `CatalogService.get_all_tools()` categories; "All" first
    - Tool list rows: `ListItem` containing a `Horizontal` with tool name `Static`, description `Static`, and status badge `Label`
    - On `ListView.Selected` in tool list: populate and show detail panel
    - On `Button.Pressed` for `#btn-simulate-install`: call `catalog_service.simulate_install(key)`, refresh detail panel, call `self.notify(...)`
    - On `Input.Changed` for search: call `catalog_service.search_tools(query)`, repopulate tool list; dim sidebar via `add_class("search-active")` on sidebar
    - CSS included inline via `DEFAULT_CSS`; follows design system (`$surface`, `$background`, `$accent`, `$success`, `$error`, `$text-secondary`)
    - `__init__` accepts `state: AppStateModel`; instantiates `CatalogService` internally
  - Done criteria: screen composes without error; sidebar, tool list, and detail panel are distinct DOM regions; all keybinds declared in `BINDINGS`; no hardcoded colour hex values

- [x] **U2** — Wire navigation in `src/ignition/app.py` and `src/ignition/ui/screens/home.py`
  - Owner: ui-builder
  - Inputs: U1 (ToolCatalogScreen), existing `IgnitionApp`, `HomeScreen`
  - Outputs:
    - `IgnitionApp.BINDINGS` extended with `Binding("g", "noop", show=False)` + `("t", "goto_catalog", "Tool Catalog")` using Textual chord pattern, OR a single `Binding("ctrl+t", "goto_catalog", "Catalog")` if chord is not supported cleanly — see note below
    - `action_goto_catalog(self)`: pushes `ToolCatalogScreen(self._current_state)` — requires `IgnitionApp` to hold a `_current_state` reference (add it if not already there)
    - `HomeScreen` quick-actions: add `Button("Tool Catalog", id="btn-catalog")` and handle its `Button.Pressed` to post a message or call `app.push_screen(ToolCatalogScreen(state))`
  - Note on `g t` chord: Textual does not natively support two-key chords. Implement as a single binding `ctrl+t` for keyboard shortcut (label it "Catalog" in footer) and document the deviation from the spec in a code comment. The `g t` motion style belongs to a future vim-mode layer.
  - Done criteria: pressing the keyboard shortcut from `HomeScreen` navigates to `ToolCatalogScreen`; "Tool Catalog" button on home screen works; back-navigation (Escape) returns to home screen

### Layer 4 — Tests (test-writer)

All Layer 4 tasks are independent and may run in parallel after Layer 3 completes.

- [x] **T1** — `tests/test_catalog_service.py` — CatalogService unit tests
  - Owner: test-writer
  - Inputs: C1 (CatalogService), D3 (stub tools), D4 (InstallStatus), D5 (simulate install)
  - Outputs: pytest file with:
    - `test_get_all_tools_returns_twelve()` — asserts len == 12
    - `test_get_all_tools_fields_valid()` — asserts each tool has non-empty `key`, `name`, `description`, at least one category, at least one persona_tag
    - `test_get_tools_for_personas_backend()` — asserts `python`, `docker`, `git` in results; `terraform` not in results
    - `test_get_tools_for_personas_deduplication()` — two personas sharing `git` → `git` appears once
    - `test_get_tools_for_personas_unknown_id_ignored()` — no raise; returns same as calling with only known ids
    - `test_search_tools_case_insensitive()` — search "DOCKER" finds the docker tool
    - `test_search_tools_matches_description()` — search term from a tool's description finds that tool
    - `test_search_tools_no_match_returns_empty()` — search "zzznomatch" returns `[]`
    - `test_simulate_install_mutates_status()` — after simulate_install("python"), tool's `install_status == InstallStatus.INSTALLED`
    - `test_simulate_install_unknown_key_returns_none()` — returns `None`, does not raise
  - Done criteria: all 10 tests present; no Pilot usage; all tests use `isolated_paths` fixture; no disk I/O beyond fixture

- [x] **T2** — `tests/test_catalog_screen.py` — ToolCatalogScreen Pilot integration tests
  - Owner: test-writer
  - Inputs: U1 (ToolCatalogScreen), U2 (navigation wiring), C1 (CatalogService)
  - Outputs: pytest-asyncio file with:
    - `test_catalog_screen_boots()` — navigate to catalog via keyboard shortcut from `IgnitionApp`; assert `isinstance(app.screen, ToolCatalogScreen)`
    - `test_sidebar_shows_all_category()` — query sidebar ListView; assert "All" item is present
    - `test_tool_list_populated()` — assert tool list has ≥ 10 items after mount
    - `test_search_filters_tool_list()` — type "docker" in search input; assert list length < original; assert docker tool visible
    - `test_enter_on_tool_opens_detail_panel()` — focus tool list, press Enter; assert `#detail-panel` is visible (CSS `display` not `none`)
    - `test_simulate_install_button_fires_notify()` — open detail panel on a MISSING tool; press simulate install button; assert `notify` was called (mock or capture)
    - `test_escape_closes_detail_panel()` — open detail, press Escape; assert panel hidden
  - Done criteria: all 7 tests present; each test is `async def`; uses `app.run_test()` context manager; no `time.sleep` calls; `isolated_paths` fixture used

---

## Resume

If this session is interrupted, resume by:
1. Reading this file to find the first `[ ]` task.
2. Reading the relevant source files for that layer.
3. Spawning the appropriate specialist agent for the uncompleted task.
4. Marking `[x]` immediately when the specialist confirms completion.

**Current state:** All tasks pending. Begin with Layer 1 (S1 + S2 in parallel).

**Key file paths:**
- Schema: `src/ignition/schemas/catalog.py` (new), `src/ignition/schemas/state.py` (extend)
- Core: `src/ignition/core/catalog.py` (new)
- UI: `src/ignition/ui/screens/catalog.py` (new), `src/ignition/app.py` (extend), `src/ignition/ui/screens/home.py` (extend)
- Tests: `tests/test_catalog_service.py` (new), `tests/test_catalog_screen.py` (new)

---

## Progress

**QA gate run: 2026-04-19 — COMPLETED**

All 8 planned tasks delivered across 4 layers:
- Schema layer: `InstallStatus` StrEnum + `ToolInfo` Pydantic v2 model in `src/ignition/schemas/catalog.py`; `AppStateModel` extended with `tool_catalog_cache` and `STATE_SCHEMA_VERSION` bumped to 2 in `src/ignition/schemas/state.py`
- Core layer: `CatalogService` in `src/ignition/core/catalog.py` with all 5 methods (get_all_tools, get_tools_for_personas, search_tools, simulate_install, _load_tools); 12 stub tools covering all 5 personas
- UI layer: `ToolCatalogScreen` in `src/ignition/ui/screens/catalog.py` with sidebar, tool list, bottom detail panel, search, and simulate-install; navigation wired via `ctrl+t` global binding in `IgnitionApp` and "Tool Catalog" button on `HomeScreen`
- Tests: 10 unit tests in `tests/test_catalog_service.py`; 7 Pilot integration tests in `tests/test_catalog_screen.py`; total suite grew from 21 to 38 tests

QA fixes applied at gate time (not blocking, corrected before commit):
- UP042: `InstallStatus(str, enum.Enum)` changed to `InstallStatus(enum.StrEnum)` in `src/ignition/schemas/catalog.py`
- I001/F401/RUF100: unsorted imports and unused noqa in test files — auto-fixed via `ruff check --fix`
- Format: `src/ignition/ui/screens/catalog.py` and `tests/test_catalog_screen.py` — auto-fixed via `ruff format`

---

## Blockers

None identified at plan time.

**Potential risks (not blockers):**
- Textual chord keybinds (`g t`) are not natively supported. U2 uses `ctrl+t` as a single binding instead. This is documented in a code comment and deferred to a future vim-mode layer.
- `STATE_SCHEMA_VERSION` bump from 1 → 2 may cause `load_state()` to fail if existing persisted state files exist on a developer's machine. The `isolated_paths` fixture in tests prevents this in CI. For local dev, deleting `$XDG_STATE_HOME/ignition/state.json` is the documented workaround. Migration logic is M3 scope.

---

## Catalog Loading Strategy — Schema Tasks (plan: twinkling-bubbling-gizmo.md)

**Completed: 2026-04-19**

### Schema changes applied

- [x] **S3** — Extend `src/ignition/schemas/catalog.py`
  - Added `InstallStep` model (method, package, cask, repo, repo_key_url, url, archive_type, binary_name, install_path, global_install)
  - Added `PlatformInstallMethods` model (macos, linux — both `list[InstallStep]` with `Field(default_factory=list)`)
  - Modified `ToolInfo`: added `version_policy`, `requires_sudo`, `health_check`, `dependencies`, `install_methods` with defaults; changed `version: str` to `version: str | None = None`
  - All existing fields preserved; `schema_version` and `install_status` unchanged
  - schema-guardian: all 6 assertions PASS

- [x] **S4** — Create `src/ignition/schemas/config.py`
  - New `AppConfigModel` with `CONFIG_SCHEMA_VERSION = 1`
  - Fields: `catalog_url`, `catalog_max_age_seconds`, `theme`, `density`, `motion`, `automation_level` — all scalar, no mutable defaults
  - schema-guardian: all 6 assertions PASS

- [x] **S5** — Update `src/ignition/schemas/state.py`
  - Removed `tool_catalog_cache: list[ToolInfo]` field and `from .catalog import ToolInfo` import
  - Bumped `STATE_SCHEMA_VERSION` from 2 to 3
  - Migration strategy: at `load_state()` time, if `schema_version == 2`, drop `tool_catalog_cache` key from the parsed dict before validation and write back at version 3. Implementation is in `core/state.py` (M3 scope for this PR).
  - schema-guardian: all 6 assertions PASS
