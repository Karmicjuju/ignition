# Ignition

A terminal-native developer onboarding and workspace command centre for the Reactor ecosystem. Replaces ad-hoc setup scripts with a guided, role-aware TUI experience.

## Status

**Ideation phase.** Specifications exist but opinions are subject to change. No code yet.

## Planned Stack

- **Language:** Python 3.14
- **TUI:** Textual (reactive attributes + posted messages; `App` / `Screen` / `Widget`)
- **CLI:** Typer (arg parsing for `--demo`, `--operator`, future subcommands)
- **Package manager:** uv (`pyproject.toml` + `uv.lock`)
- **Project layout:** `src/` layout at `src/ignition/`
- **Schemas:** Pydantic v2 (every schema includes `schema_version: int`)
- **YAML:** ruamel.yaml (round-trip preserves comments)
- **Logging:** structlog → JSON
- **XDG paths:** platformdirs
- **Async:** Textual `@work` (asyncio); subprocesses via `asyncio.create_subprocess_exec`
- **Lint/format:** ruff — **Type checker:** ty (Astral's type checker, focused on `src/ignition/core/`)
- **Tests:** pytest + pytest-asyncio + Textual `Pilot`
- **Config:** YAML manifests (tools, personas, policies)
- **State persistence:** JSON at `$XDG_STATE_HOME/ignition/` (resolved via platformdirs)
- **Supported platforms (v0.1):** macOS + Linux (Ubuntu/Debian). No Windows. No other distros.
- **Distribution (testers):** `pipx install` from TestPyPI, later PyPI.

## What It Does

- Guided onboarding wizard (role-aware: backend, frontend, devops, security, contractor)
- Status dashboard with health diagnostics and repair workflows
- Tool catalog with manifest-driven install/version management
- AWS auth centre (SSO, credential management)
- Activity logs, telemetry, settings
- Demo mode (seeded state, no real changes) and Operator mode (privileged debug)

## Docs

| Document | Path |
|---|---|
| Product Requirements (PRD) | `docs/product/prd.md` |
| Design System | `docs/design/design-system.md` |
| UX Specification | `docs/design/ux-spec.md` |
| Technical Architecture | `docs/engineering/technical-architecture.md` |
| Operations & Governance | `docs/operations/governance.md` |
| Demonstration Strategy | `docs/strategy/demo-strategy.md` |

## Key Concepts

- **Personas:** roles that drive which tools are recommended/required
- **Manifests:** YAML-driven tool/persona/policy definitions in a separate repo
- **Version governance:** Managed / Recommended / Flexible / Deprecated / Experimental tiers
- **Release channels:** Stable / Beta / Experimental with staged rollout support
- **Density modes:** Full (new users) and Compact (power users)

## Notes

Working ideation notes live in `notes/`.
