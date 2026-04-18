# Prd

## Page 1

Ignition: Product Requirements Document (PRD)
Executive Summary
Ignition is a premium terminal‑native onboarding and workspace command centre for developers working
in the Reactor ecosystem. It replaces ad‑hoc setup scripts and scattered documentation with a cohesive,
guided product experience that gets engineers productive fast. Ignition combines a polished initial setup
wizard, a role‑aware command centre for daily operations, health and repair tools, AWS authentication
management, and update capabilities. It is designed to impress leadership with a highly professional
developer experience while remaining robust and reliable for everyday use.
Problem Statement
New engineers often lose valuable time installing toolchains, configuring AWS access, and learning
environment conventions. Existing onboarding materials are scattered and out of date, and scripts do not
handle edge cases or multiple personas well. When environments drift or break, users have no clear way to
repair them. Leadership lacks visibility into onboarding effectiveness and environment consistency.
Vision
Ignition will be the single entry point into the Reactor environment. It will enable developers to:
• Install the right tools and configurations for their role quickly.
• Gain and maintain AWS access without memorising commands.
• Keep their workspace healthy with diagnostics and repair flows.
• See at a glance whether their environment is ready to work.
• Reconfigure or rebuild their environment as requirements change.
At the same time, Ignition showcases the organisation’s investment in developer productivity and provides
maintainers with a governance and analytics model for long‑term scalability.
Users and Personas
• Backend engineers – need SDKs, databases, container tools and AWS access.
• Frontend engineers – need Node ecosystems, browsers and package managers.
• DevOps / platform engineers – need Kubernetes, Terraform, cloud CLIs and observability tools.
• Security engineers – need access tools, audit utilities and hardened defaults.
• Contractors and temporary users – need fast, scoped setups with least privilege.
Ignition supports multiple active personas per user and allows manual role selection rather than
auto‑detection.
1

---

## Page 2

Goals
User Goals
• Get ready to work as quickly as possible on a new workspace.
• Avoid reading extensive setup documentation.
• Maintain a healthy environment over time.
• Feel confident in the changes made by the tool.
Business Goals
• Reduce time‑to‑productivity for new hires.
• Improve consistency and compliance across developer environments.
• Lower support burden for environment setup and repair.
• Demonstrate innovation in internal tooling to leadership.
Scope and Non‑Goals
v0.1 Thin Slice (first shippable release)
The first release deliberately ships a narrow vertical slice to prove the stack and demo the experience:
• Onboarding wizard — Quick path only (personas + recommended tool bundle).
• Unified status dashboard — Readiness summary panel.
• Demo mode (`--demo` flag) — Seeded state for presentations and local testing.
Every other "In Scope (MVP)" item below lands in subsequent milestones. The full MVP list remains the
product target; it is simply not all in the first release.
In Scope (MVP)
• Guided onboarding flows with quick and custom options.
• Role‑aware tool recommendations and installations.
• AWS authentication centre with status, refresh and role switch.
• Health diagnostics and repair workflows with tiered fixes.
• Update management for both managed and optional tools.
• Activity log and basic settings (appearance, density, motion, automation level).
• Maintainer control via YAML manifests and GitOps processes.
• Demo mode and operator mode for presentations and support.
Out of Scope (MVP)
• Repository cloning and workspace templates.
• Multi‑machine or multi‑account context management.
• Public plugin system or third‑party extensions.
• Persistent background automation (beyond optional modes).
Functional Requirements (Summary)
1. Onboarding wizard – Provide quick and custom setup paths, show progress through phases, allow
skipping and reconfiguration.
2. Unified status dashboard – Display readiness summary (AWS auth, tools status, health, updates)
with next best actions.
3. Tool catalog – Enable browsing and searching for tools; support role bundles and one‑click installs;
require detail confirmation for complex tools.
4. Auth centre – Show AWS session status, refresh expired credentials, switch profiles/roles, repair
config files.
2

---

## Page 3

5. Health centre – Surface environment drift and broken components; run health scans; categorise
issues by severity and provide repair actions.
6. Repair system – Offer safe auto‑fixes, confirmation‑required fixes and manual guidance; respect
privilege boundaries.
7. Updates – Detect available updates; differentiate managed and optional tools; provide one‑click or
guided updates; support future auto‑update modes.
8. Activity log – Record recent actions with timestamps and outcomes; provide access to detailed logs.
9. Settings – Allow users to set dark/light mode, density (compact/full), motion (standard/reduced) and
automation level (observe/assist/autopilot).
10. Analytics – Collect anonymised usage metrics (workflow durations, feature adoption, repeated
actions) and critical events; support push model for errors and batch model for behavioural metrics.
11. Maintainer control – Load tool and persona definitions from manifest files; apply governance
policies; support release channels (stable, beta, experimental, deprecated).
Success Metrics
• Median onboarding completion time (target: under 20 minutes).
• Percentage of users ready to work without manual support (target: 80%+).
• Reduction in environment‑related support tickets.
• Adoption of daily dashboard use (weekly active users).
• Number of successful repairs executed via Ignition.
• Measured reduction in environment drift across teams.
MVP vs Future Roadmap
MVP will deliver the features listed in scope above. Post‑MVP phases could include:
• Repository bootstrap and workspace templates.
• Scheduled health scans and proactive notifications.
• Richer analytics dashboards and persona effectiveness reports.
• Remote profile syncing across machines.
• Plugin extensions for custom modules.
Risks and Mitigations
• Over‑ambition – Splitting the project into modular documents and focusing on core flows reduces
risk.
• Tool installation failures – Use deterministic install methods and explicit privilege prompts; collect
telemetry on failures for rapid iteration.
• User distrust – Provide transparency through logs, opt‑in automation and clear messaging; allow
users to view and undo changes.
• Design over substance – Prioritise functional stability alongside polished UX; use a dual pipeline for
design and engineering.
3

---
