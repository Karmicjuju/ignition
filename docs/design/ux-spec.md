# Ux Spec

## Page 1

Ignition: UX Specification
This document outlines the user experience architecture for Ignition. It defines the primary screens,
navigation patterns, interactions and guidance paradigms. It is meant for product, design and engineering
teams to align on the desired user journey.
1. High‑Level Principles
• Keyboard‑first, mouse‑optional – All interactions must be navigable via keyboard; mouse support is
a convenience, not a requirement.
• Clarity before flavour – Themed language adds energy, but core actions and states must remain
clear and unambiguous.
• Progressive guidance – Users enjoy a fast path by default but can open detailed explanations or
assistance when needed.
• Adaptive layouts – Screen density adapts to terminal size; large terminals show more panels, small
terminals prioritise key information.
2. Primary Screens
Home Dashboard
The landing screen after onboarding and on subsequent launches. It includes:
Panel Description
A hero panel summarising environment readiness (AWS auth, tool status,
Unified Reactor
updates, health). Shows “Ready”, “Needs attention”, “Blocked” etc. Contains quick
Status
actions to remediate.
Lightweight indicators for various subsystems: tools, configs, shell integration,
Health Summary
permissions. Clicking opens the Health centre.
Buttons or hotkeys for common operations (refresh auth, run health scan, install
Quick Actions
recommended tools, update all).
Recommended Personalised suggestions based on active personas (e.g. “Install Docker”, “Switch
Actions to Node 22 LTS”).
A list of recent actions with timestamps and outcomes. Clicking opens the
Recent Activity
Activity log for details.
Shows how many managed and optional updates are available. Links into the
Updates
Updates screen.
1

---

### Table 1 (Page 1)

| Panel Description |
|---|
| A hero panel summarising environment readiness (AWS auth, tool status,
Unified Reactor
updates, health). Shows “Ready”, “Needs attention”, “Blocked” etc. Contains quick
Status
actions to remediate. |
| Lightweight indicators for various subsystems: tools, configs, shell integration,
Health Summary
permissions. Clicking opens the Health centre. |
| Buttons or hotkeys for common operations (refresh auth, run health scan, install
Quick Actions
recommended tools, update all). |
| Recommended Personalised suggestions based on active personas (e.g. “Install Docker”, “Switch
Actions to Node 22 LTS”). |
| A list of recent actions with timestamps and outcomes. Clicking opens the
Recent Activity
Activity log for details. |
| Shows how many managed and optional updates are available. Links into the
Updates
Updates screen. |

## Page 2

Onboarding
When the user launches Ignition for the first time (or chooses to rerun setup), they see a path selection:
1. Quick Launch – Applies recommended defaults for selected personas. Minimal prompts, fastest
completion.
2. Custom Launch – Allows users to choose personas, select tools, set version preferences and
automation levels.
3. Explore Workspace – Skips setup; enters dashboard directly with no changes.
The onboarding flow is broken into phases, displayed in a side navigation:
1. Identity Calibration
2. Toolchain Provisioning
3. Access Systems (AWS auth)
4. Shell Integration
5. Configuration Sync
6. Readiness Validation
7. Launch Sequence
Each phase shows a progress indicator (pending, active, complete) and can be expanded for details. During
each step the main panel displays progress bars and status messages; a contextual help panel can be
opened with ? for explanations.
Tools Catalog
The catalog allows browsing and searching for tools. It supports two discovery modes:
• Browse – Organised by categories (Core Development, Cloud, Containers, Languages, Frontend,
Security, Utilities). Shows cards with tool names, descriptions, labels (Installed, Managed,
Recommended, Optional) and install buttons.
• Search – Activated via / or Ctrl+K . Users type to filter tools quickly. Results appear in a list;
pressing Enter installs a simple tool or opens a details view for complex tools.
When a tool requires additional decisions (e.g. version choice, dependencies, sudo), the install button leads
to a details page. Otherwise tools install in one click.
Auth Centre
This dedicated screen displays AWS authentication status and actions:
• Session status – Signed in / signed out, active profile, assumed role, token expiry timer.
• Actions – Sign in, refresh session, switch profile, switch role, repair config files.
• Details – Expandable section showing underlying config files and environment variables.
• Issues – Surface and explain common auth errors; provide fix actions.
2

---

## Page 3

Health Centre
The Health centre provides deep diagnostics. It shows categories (Tools, Configs, Shell, Permissions,
Network, State). Each category lists specific checks with statuses (Healthy, Recommended fix, Needs
attention, Manual). Users can run a full scan, auto‑fix safe issues and view detailed logs.
Updates
This screen lists available updates by tool and category, distinguishing between Managed
(platform‑controlled) and Optional (user‑controlled) updates. Users can update individually or in batches.
Critical updates highlight security or compliance issues.
Activity Log
An audit trail showing what Ignition has done recently. Each entry includes the action, result, timestamp
and context. Users can expand entries to see exact commands and logs.
Settings
A configuration screen where users can adjust:
• Appearance – Dark or light mode.
• Density – Compact or full layout.
• Motion – Standard or reduced animations.
• Automation Level – Observe (default), Assist or Autopilot.
Help & Guidance
Help is accessible via ? anywhere. Ignition supports multiple help modalities:
• Inline hints – Small ? icons next to form elements reveal short explanations on click or keypress.
• Side panel – Pressing ? opens a contextual help drawer on the right with deeper guidance relevant
to the current screen and selection.
• Command palette – Searching for “help” or pressing Ctrl+K and typing queries like “how to
install Docker” surfaces targeted documentation links.
3. Navigation Patterns
Ignition uses a hybrid navigation model:
• Sidebar or top bar – Primary navigation for modules (Home, Tools, Auth, Health, Updates, Configs,
Personas, Logs, Settings).
• Keyboard shortcuts – g h (Home), g t (Tools), g a (Auth), g u (Updates), g r (Repair/
Health), / (Search), Ctrl+K (Command palette), ? (Help), Esc (Back/Close).
• Command palette – Quick fuzzy finder for actions, tools and navigation. Opens with Ctrl+K .
3

---

### Table 1 (Page 3)

| ? | None |
|---|---|
|  | ? |

### Table 2 (Page 3)

| g a |
|---|
| ? |

## Page 4

4. States and Flows
• Not started – First launch: show startup ceremony and path selection.
• Onboarding in progress – Show progress bar with phases; main panel displays active step details;
allow pause/resume.
• Ready – Dashboard shows green status and quick actions; no blocking issues.
• Drift detected – Dashboard shows yellow warnings; Health centre lists issues; Repair actions
available.
• Blocked – Dashboard shows red state; requires immediate action (auth expired, missing critical tool);
clicking takes user to guided fix flow.
5. Visual Guidance and Feedback
Ignition leverages Reactor‑themed language to add personality while keeping clarity. For example:
• Installing tools → “Charging runtime modules…”.
• Success → “Core systems online.”
• Errors → “Access systems offline.”
• Progress → progress bars with both percentage and textual status.
Transitions and animations should be subtle (fade or slide) and respect the user’s motion settings. Use
consistent spacing, margins and typography from the design system (see separate design system
document).
6. Accessibility Considerations
• Provide tooltip labels for all interactive elements to support keyboard-only navigation.
• Ensure high contrast in both dark and light modes.
• Support reduced motion preferences.
• All keyboard shortcuts must be discoverable via a ? menu.
7. Future Extensions
The UX architecture is designed to support future modules such as repository bootstrapping, workspace
templates, remote profile sync and plugin extensions. New screens can be added to the navigation with
minimal rework as long as they follow the established patterns.
4

---
