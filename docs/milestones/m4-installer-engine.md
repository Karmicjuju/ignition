# Milestone 4 — Real Installer Engine + Full Onboarding Custom Path

## Goal

Make `simulate_install` real. Wire the Tool Catalog "Install" button and the Onboarding wizard to an actual platform-aware install engine. Add the full onboarding custom path (manual tool selection before accepting).

## Depends On

M3 (Health Engine) — installer reuses health check logic to verify installs succeeded.

---

## Scope

### In Scope

- `InstallerEngine` core service that dispatches to the right install method per platform
- Real install execution replacing `CatalogService.simulate_install`
- Per-tool progress UI in `ToolCatalogScreen`
- Full onboarding custom path (Phase 2b: manual tool selection)
- Post-install health re-check to confirm success
- `InstallStatus.FAILED` state with retry affordance

### Out of Scope

- Uninstall / remove tools (deferred)
- Version pinning (always installs latest governed version in M4)
- Cancel mid-install (button disabled during active install; retry after failure)
- Update existing installations (deferred to M7)

---

## Platform Dispatch

| Platform | Primary method | Fallback |
|---|---|---|
| macOS | Homebrew (`brew install <formula>`) | Direct binary download to `~/.local/bin` |
| Linux | apt (`apt-get install -y <package>`) | Direct binary download to `~/.local/bin` |

Detection: `sys.platform == "darwin"` → macOS path; `sys.platform == "linux"` → Linux path.

Homebrew absent on macOS: fall back to direct binary immediately (do not install Homebrew automatically).

### Privilege Model

| Method | Privilege needed | Ignition action |
|---|---|---|
| `brew install` | None (user-level) | Run directly via `asyncio.create_subprocess_exec` |
| `apt-get install` | sudo | Surface copy-paste command block; poll for completion |
| Direct binary to `~/.local/bin` | None | Run directly |
| Direct binary to `/usr/local/bin` | sudo | Surface copy-paste command block |

For `apt` commands: Ignition shows the exact command (`sudo apt-get install -y <package>`), copies to clipboard on click, and polls the binary PATH every 5 seconds for up to 2 minutes. Once detected, marks install complete.

### Tool Manifest Extensions

Each tool YAML gains an `install_methods` block (already partially defined in `ToolInfo` schema):

```yaml
install_methods:
  macos:
    brew: "awscli"          # brew formula name
    binary_url: "https://..."  # fallback direct download URL
  linux:
    apt: "awscli"           # apt package name
    binary_url: "https://..."  # fallback direct download URL
  post_install_check: "aws --version"  # command to verify success
```

`binary_url` is optional. If absent and primary method fails, tool is marked `InstallStatus.FAILED`.

---

## Install Flow

```
User clicks Install
        ↓
Resolve install method for platform
        ↓
If method requires sudo → show copy-paste block, poll for binary
If method is direct    → spawn subprocess, stream stdout/stderr to progress widget
        ↓
Run post_install_check command
        ↓
Success: update AppStateModel (status=INSTALLED, installed_version=<detected>)
Failure: update AppStateModel (status=FAILED), show retry button
        ↓
Trigger health re-check for this tool (reuses HealthEngine.apply_fix logic)
```

### Bundle Install (Onboarding)

Tools in a bundle install sequentially (not concurrently) to avoid conflicting package manager locks. Each tool shows its own progress row. If one fails:
- Mark it FAILED
- Continue with remaining tools
- Show summary at end: "4 installed, 1 failed — [Retry failed]"

No rollback: already-installed tools remain installed.

---

## Progress UI

`ToolCatalogScreen` install button becomes a progress indicator during install:

```
[Installing...]  ██████░░░░  Downloading awscli 2.15...
```

After completion:
- Success: button label → "Installed ✓", disabled
- Failure: button label → "Failed — Retry", enabled

---

## Full Onboarding Custom Path

Current `OnboardingScreen` has two phases: persona selection → accept bundle.

Add **Phase 2b** between them, triggered by a "Customise" button on the bundle review screen:

```
Phase 1: Select personas (checkboxes)
        ↓
Phase 2a: Review recommended bundle (current)
  [Accept]  [Customise]
        ↓ (Customise)
Phase 2b: Manual tool selection
  - All recommended tools pre-checked
  - User can uncheck tools to skip
  - User can check additional tools from full catalog list
  - [Accept custom selection]
        ↓
Phase 3: Install (same as current quick path accept, but with custom list)
```

Phase 2b is a scrollable checklist widget. Search/filter within the list is not required in M4.

---

## Core Module: `InstallerEngine`

Location: `src/ignition/core/installer.py`

```python
class InstallResult:
    tool_key: str
    success: bool
    method_used: str
    error: str | None
    detected_version: str | None

class InstallerEngine:
    async def install(self, tool: ToolInfo) -> InstallResult: ...
    async def install_bundle(
        self,
        tools: list[ToolInfo],
        progress_cb: Callable[[str, str], None],  # (tool_key, status_msg)
    ) -> list[InstallResult]: ...
    def resolve_method(self, tool: ToolInfo) -> InstallMethod: ...
```

`resolve_method` returns the best available method for the current platform. It checks for Homebrew presence by running `which brew`. Result is cached per session.

---

## Schema Changes

Tool manifest YAML already defines `InstallStep` and `PlatformInstallMethods` in `schemas/catalog.py` — verify these match the extended YAML format above. Update if needed (bump `schema_version` if `ToolInfo` fields change).

`AppStateModel` gains:
```python
install_history: list[InstallEvent] = []  # capped at 100 entries
```

```python
class InstallEvent:
    timestamp: datetime
    tool_key: str
    method: str
    success: bool
    version: str | None
```

---

## Open Questions Deferred to Implementation

- `binary_url` format: plain download URL or a JSON manifest listing per-arch URLs? (Proposed: single URL pointing to a platform-arch-specific binary; architecture from `platform.machine()`)
- Should `apt-get update` run before `apt-get install`? (Proposed: yes, once per session, cached)
- PATH refresh after binary install: show "restart your terminal or run `source ~/.zshrc`" instruction banner

---

## Verification

1. `pytest tests/test_installer*.py` — unit tests with mocked subprocess; test method resolution, success/failure state mutation
2. `pytest tests/test_onboarding_custom.py` — Pilot tests for Phase 2b checklist, accept custom selection
3. `/quality-gate` before commit
4. `/core-module-review` on `installer.py`
5. `/screen-reviewer` on updated `OnboardingScreen`
6. Manual: install a real tool (e.g. `trivy`) via catalog on macOS; confirm binary present, state updated, health check passes
