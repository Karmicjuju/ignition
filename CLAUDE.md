# Ignition

A terminal-native developer onboarding and workspace command centre for the Reactor ecosystem. Replaces ad-hoc setup scripts with a guided, role-aware TUI experience.

## Status

**Ideation phase.** Specifications exist but opinions are subject to change. No code yet.

## Planned Stack

- **Language:** Python
- **TUI:** Textual (event-driven reactive framework)
- **Config:** YAML manifests (tools, personas, policies)
- **State persistence:** JSON at `~/.local/state/ignition/`

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
