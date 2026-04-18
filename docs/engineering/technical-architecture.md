# Technical Architecture

## Page 1

Ignition: Technical Architecture
This document describes the high‑level technical architecture for Ignition, including the chosen frameworks,
internal modules, data storage, telemetry pipeline and special modes. It is intended for engineering teams
responsible for building and maintaining Ignition.
1. Frameworks and Libraries
Textual
Textual is the primary TUI framework powering Ignition. It provides a reactive component model,
keyboard/mouse event handling and view rendering. The architecture is event‑driven: actions trigger
messages, which update the application state, which automatically triggers view re‑renders. Textual’s
built‑in support for reactive data binding and async methods enables background tasks such as
installations and telemetry without explicit command systems.
Forms and Wizards
Textual provides composable widget systems for building forms, input validation and multi‑step wizards.
The application uses a custom form builder built on Textual widgets for onboarding flows, persona
selection, and settings pages. It supports input validation, accessible navigation and progress indicators.
YAML / JSON Parsing
Tool and persona definitions are loaded from YAML or JSON manifests. The application uses a manifest
loader that watches these files and converts them into internal data structures at runtime. Validations
ensure that unknown keys or invalid version specifications are flagged.
2. Core Modules
Ignition is composed of several internal modules organised around responsibilities:
Module Responsibilities
Maintains the current application state (user preferences, active personas, installed
State tools, onboarding progress, health flags). Persists to
Manager ~/.local/state/ignition/ as JSON. Provides reconciliation between stored
state and live system inspection on startup.
Handles tool installation, update and removal. It resolves the best installation
Installer
method (apt, direct binary, language manager) based on platform policy. It runs
Engine
tasks asynchronously, emits progress messages and writes logs.
1

---

### Table 1 (Page 1)

| Module Responsibilities |
|---|
| Maintains the current application state (user preferences, active personas, installed
State tools, onboarding progress, health flags). Persists to
Manager ~/.local/state/ignition/ as JSON. Provides reconciliation between stored
state and live system inspection on startup. |
| Handles tool installation, update and removal. It resolves the best installation
Installer
method (apt, direct binary, language manager) based on platform policy. It runs
Engine
tasks asynchronously, emits progress messages and writes logs. |

## Page 2

Module Responsibilities
Tool Catalog Loads tool manifests from the maintainer repository. Merges with persona files and
Service policies to produce recommended bundles. Exposes search APIs for the UI.
Interfaces with AWS CLI, SSO providers and underlying credential stores. Provides
Auth
status checks, refresh logic and switching. Handles config file generation and
Integrations
merges.
Defines health checks for subsystems (tools, configs, shell integration, permissions).
Health Engine Runs scans in the background or on demand. Categorises results (Healthy,
Recommended fix, Needs attention, Manual).
Maps health issues to repair tasks. Supports tiered fix actions: safe auto‑fix,
Repair Engine confirmation required and manual guidance. Tracks repair history and informs the
state manager.
Determines when new versions of tools or Ignition itself are available. Applies policy
Update
rules (managed vs optional) and orchestrates update flows. Supports later
Engine
auto‑update modes.
Captures UI and workflow events. Implements two transport modes: push for critical
Telemetry
errors and batch for usage metrics. Uses an anonymous install ID. Queues events
Engine
locally when offline and uploads on schedule or shutdown.
Settings Stores and exposes user preferences (appearance, density, motion, automation).
Module Persists to ~/.config/ignition/ and informs other modules.
Provides debug commands and internal inspection views for platform maintainers.
Operator
Enables state inspection, manifest viewing, workflow control and verbose logging.
Mode
Only accessible via privileged launch flag.
Seeds fake states and metrics for presentation and testing. Displays a banner
Demo Mode
indicating simulation.
3. Data Storage
Configuration Files ( ~/.config/ignition/ )
• config.json – Appearance, density, motion and automation preferences.
• personas.json – Currently selected personas.
• includes.sh – Shell integration script to be sourced by the user’s shell (if enabled). The user’s
~/.bashrc or ~/.zshrc should include a line sourcing this file.
State Files ( ~/.local/state/ignition/ )
• state.json – Current state of installations, health flags, onboarding progress, last scan times and
cached tool catalog.
• telemetry/ – Queued telemetry events awaiting upload.
• logs/ – Per‑operation logs for installs, updates, repairs and auth flows.
2

---

### Table 1 (Page 2)

| Module Responsibilities |
|---|
| Tool Catalog Loads tool manifests from the maintainer repository. Merges with persona files and
Service policies to produce recommended bundles. Exposes search APIs for the UI. |
| Interfaces with AWS CLI, SSO providers and underlying credential stores. Provides
Auth
status checks, refresh logic and switching. Handles config file generation and
Integrations
merges. |
| Defines health checks for subsystems (tools, configs, shell integration, permissions).
Health Engine Runs scans in the background or on demand. Categorises results (Healthy,
Recommended fix, Needs attention, Manual). |
| Maps health issues to repair tasks. Supports tiered fix actions: safe auto‑fix,
Repair Engine confirmation required and manual guidance. Tracks repair history and informs the
state manager. |
| Determines when new versions of tools or Ignition itself are available. Applies policy
Update
rules (managed vs optional) and orchestrates update flows. Supports later
Engine
auto‑update modes. |
| Captures UI and workflow events. Implements two transport modes: push for critical
Telemetry
errors and batch for usage metrics. Uses an anonymous install ID. Queues events
Engine
locally when offline and uploads on schedule or shutdown. |
| Settings Stores and exposes user preferences (appearance, density, motion, automation).
Module Persists to ~/.config/ignition/ and informs other modules. |
| Provides debug commands and internal inspection views for platform maintainers.
Operator
Enables state inspection, manifest viewing, workflow control and verbose logging.
Mode
Only accessible via privileged launch flag. |
| Seeds fake states and metrics for presentation and testing. Displays a banner
Demo Mode
indicating simulation. |

### Table 2 (Page 2)

| config.json |
|---|
| personas.json |
| includes.sh |
| ~/.bashrc |

### Table 3 (Page 2)

| telemetry/ |
|---|
| logs/ |

## Page 3

Manifests Repository
Ignition reads tool and persona definitions from a repository controlled by the platform team. The
recommended structure is:
ignition-catalog/
tools/
terraform.yaml
kubectl.yaml
node.yaml
personas/
backend.yaml
frontend.yaml
platform.yaml
security.yaml
policies/
versions.yaml
restrictions.yaml
releases.yaml
Each tool manifest defines: name, description, categories, version policy (managed/recommended/flexible),
install method(s), dependencies, health check commands and persona recommendations.
Personas list recommended and optional tools per role. Policies define allowed versions, deprecations and
release channels.
4. Telemetry Architecture
Ignition uses a dual telemetry model:
• Push channel – For critical operational events such as crashes, fatal installer failures, repeated auth
failures or corrupted state files. These events are sent immediately (if network available) or queued
for next connection.
• Batch channel – For behavioural metrics such as onboarding funnel performance, screen time,
feature usage and repeated flows. Events are stored locally and uploaded on a schedule or when
Ignition exits gracefully. The upload destination will be configured later (e.g. internal API,
observability platform).
All events include an anonymous install_id to allow session correlation without storing personal
identity.
3

---

## Page 4

5. Special Modes
Demo Mode
Activated via a launch flag or internal toggle. Demo mode simulates states, seeded metrics and
deterministic flows for leadership presentations and UX testing. It displays a “DEMO MODE” banner to avoid
confusion. Demo mode does not modify the real system and uses randomised or prebuilt telemetry.
Operator Mode
Activated via a privileged flag or secret key combination. Operator mode exposes hidden menus and
commands that allow maintainers to inspect state, reload manifests, dry‑run workflows, view telemetry
queues and enable verbose logging. It should never be enabled for ordinary users.
6. Update Strategy
Ignition itself can be updated via future channels such as an internal apt repository or self‑replace
mechanism. The Update engine should abstract the delivery mechanism; for MVP we focus on detection,
user notification and version metadata display. Updates must be signed and validated before installation.
Users can choose to update immediately or defer. Future automation modes may allow autopilot upgrades
of Ignition, subject to policy.
7. Extensibility Considerations
Although no public plugin system is planned for the MVP, the codebase should be modular. Each module
should define clear interfaces so that adding repository bootstrap flows, remote sync or plugin extensions
in later phases does not require rewriting the core system.
4

---
