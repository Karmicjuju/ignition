# Governance

## Page 1

Ignition: Operations and Governance Model
This document outlines how Ignition is managed by the platform team. It describes the maintainer
responsibilities, manifest format, governance policies, release channels, feedback mechanisms, analytics
and internal modes.
1. Ownership Model
Ignition is maintained by a small platform engineering team. They are responsible for:
• Curating the tool catalog and personas.
• Defining and enforcing version policies and governance rules.
• Monitoring telemetry and improving the product.
• Responding to bug reports and user feedback.
• Demonstrating Ignition to leadership and stakeholders.
2. Manifest‑Driven Configuration
All tools, personas and policies are defined as code in a Git repository (see the Technical Architecture for
directory structure). Maintainers add, modify and retire tools by submitting pull requests to this repository.
Version control provides audit trails and peer review.
Tool Manifest Keys
• name – Human‑readable name.
• categories – List of categories (e.g. Cloud, Containers).
• description – Short description displayed in the catalog.
• install_method – One or more installation strategies (apt, direct binary, language package
manager).
• version_policy – Managed (locked by platform), Recommended (default but flexible) or Flexible
(user chooses).
• allowed_versions – Semver ranges allowed by policy.
• requires_sudo – Whether installation needs elevated privileges.
• health_check – Command or script to verify installation health.
• recommended_for – List of personas that should see this tool by default.
• dependencies – Other tools that must be installed first.
Persona Manifest Keys
• persona – Identifier (e.g. backend, frontend).
• recommended – List of tools that will be selected in quick launch.
• optional – Tools suggested to the persona but not selected by default.
• description – Used in the UI to describe the persona.
1

---

### Table 1 (Page 1)

| name |
|---|
| categories |
| description |
| install_method |

### Table 2 (Page 1)

| allowed_versions |
|---|
| requires_sudo |
| health_check |
| recommended_for |
| dependencies |

### Table 3 (Page 1)

| recommended |
|---|
| optional |
| description |

## Page 2

Policy Files
• versions.yaml – Defines organisation‑wide version rules (e.g. enforce Terraform ≥ 1.8.x and
< 2.0).
• restrictions.yaml – Lists forbidden tools or versions, deprecations and compliance notes.
• releases.yaml – Describes release channels for Ignition itself (stable, beta, experimental) and
staged roll‑outs.
3. Governance Layers
Ignition supports multiple governance labels applied to tools:
• Managed – Versions and installation methods are controlled by the platform team. Users cannot
select alternate versions. Used for critical tools like Terraform or internal CLIs.
• Recommended – A default version is suggested, but users may choose from a list of supported
versions.
• Flexible – Users may pick any version; Ignition presents a default based on current best practice.
• Deprecated – Tools that should not be used going forward; appear with warnings and are hidden
from quick browse.
• Experimental – Early access tools. Only shown when explicitly enabled.
These labels are defined in tool manifests and enforced by the installer engine.
4. Release Channels
Ignition itself and tool updates can be distributed via release channels:
• Stable – Default channel for all users. Only thoroughly tested and approved versions.
• Beta – Pre‑release channel for platform team members and early adopters. Used to validate new
features and tool definitions.
• Experimental – Feature flags and prototypes. Enabled manually via settings or operator mode.
Release channels are defined in releases.yaml and can include staged roll‑out percentages for large
deployments.
5. Feedback and Issue Intake
Ignition does not implement its own ticket system. Instead, users are directed to the organisation’s existing
issue tracker (e.g. Jira). Within the UI, actions like “Request a new tool” or “Report a bug” open a link or
template in the tracker with pre‑filled context (Ignition version, OS, active personas, recent logs). This
ensures feedback is processed through standard channels and associated with sprints and backlogs.
2

---

### Table 1 (Page 2)

| restrictions.yaml |
|---|
| releases.yaml |

## Page 3

6. Analytics and Reporting
The telemetry engine collects anonymised events and critical errors (see Technical Architecture).
Maintainers can run reports to understand:
• Onboarding funnel completion rates and durations.
• Most commonly installed tools and personas.
• Frequent repair actions and health issues.
• Where users request help or open guidance panels.
• Adoption of optional features (reconfigure, operator mode).
Operational events (crashes, installer failures) are pushed immediately, while usage metrics are uploaded in
batches. Telemetry does not store personal user identity; it only tags events by anonymous install_id .
7. Special Modes
• Demo Mode – Allows the platform team to simulate states and metrics for leadership presentations.
Configurable via launch flags. Does not perform real installs or collect real telemetry. Always displays
a banner to indicate simulation.
• Operator Mode – Provides privileged functions for debugging and operations. Access controlled via
launch flag or secret key. Capabilities include viewing internal state, reloading manifests, running dry
runs, examining logs and adjusting environment variables. Operator mode should never be enabled
for ordinary users.
8. Maintenance Tasks
Maintainers are expected to:
• Review tool manifest changes (PRs) and merge them after testing.
• Update persona recommendations when organisational standards change.
• Monitor telemetry dashboards and address recurring issues.
• Curate the governance labels and deprecate tools that no longer meet standards.
• Communicate with security and compliance teams about policy updates.
• Coordinate staged roll‑outs of Ignition updates via release channels.
9. Risks and Considerations
• Manifest errors – Invalid YAML could break the catalog; include schema validation and CI checks.
• Shadow installs – Users could manually install tools outside Ignition; the reconciliation logic must
detect and respect these installs.
• Over‑politicised governance – Ensure that restrictions are justified and transparent to avoid user
frustration.
• Telemetry sensitivity – Provide clear privacy statements and allow users to opt out if necessary.
3

---
