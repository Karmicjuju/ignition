# Demo Strategy

## Page 1

Ignition: Demonstration Strategy
This document provides guidance on demonstrating Ignition to leadership and stakeholders. It describes
how to use Demo Mode effectively to showcase the product’s value, design and impact.
1. Purpose
Demonstrations of Ignition serve to:
• Illustrate how the product radically improves developer onboarding and daily workflow.
• Showcase the organisation’s investment in internal tooling and developer experience.
• Provide concrete metrics on time saved and reliability improvements.
• Build excitement for future enhancements and support for continued investment.
2. Preparing Demo Mode
Ignition includes a dedicated demo mode activated via launch flag ( --demo ). Demo mode simulates
various environment states and uses seeded metrics instead of live system data. Steps to prepare:
1. Launch Ignition in demo mode.
2. Select a persona (e.g. backend + platform) and run through a quick launch.
3. Use seeded onboarding data to show completion times and success rates.
4. Populate the dashboard with example states: ready, drift detected, blocked.
5. Preload the tool catalog with sample tools across categories.
6. Seed update notifications and health issues to demonstrate repair flows.
Always ensure that a DEMO MODE banner is visible so observers understand this is simulated.
3. Narrative Flow
An effective demo tells a story. Suggested sequence:
1. Introduction – Describe the problem space and the Reactor ecosystem. Explain that Ignition is the
new gateway for developers.
2. Startup Ceremony – Launch demo mode and highlight the ignition sequence (brand, identity,
energy). Explain the promise: “Get ready to work fast.”
3. Onboarding – Show Quick Launch vs Custom Launch options. Emphasise role selection and how
recommended bundles appear. Use progress bars and Reactor‑themed language. Highlight the
post‑onboarding summary that assures readiness.
4. Dashboard Tour – Introduce the unified status hero panel. Show how readiness is instantly
understood. Navigate through panels: health summary, quick actions, recommendations, recent
activity and updates.
1

---

## Page 2

5. Scenario 1 – Auth Expired – Simulate an expired AWS session. Show the red state. Walk through the
Auth centre, refresh the session and watch the status turn green.
6. Scenario 2 – Drift Detected – Trigger drift (e.g. removed tool). Show the yellow state on the
dashboard. Open the Health centre, inspect the issue and run a repair. Watch the status update.
7. Scenario 3 – Updates Available – Demonstrate update notifications. Show differences between
managed and optional updates. Update a tool and watch the logs and activity feed.
8. Operator Mode (Optional) – Briefly mention operator mode for maintainers: state inspection,
manifest reload and verbose logs. Keep this high level unless leadership is technical.
9. Metrics and Impact – Present seeded metrics: average onboarding time reduced from hours to
minutes, number of tools installed, health issues fixed. Emphasise how telemetry drives continuous
improvement.
10. Future Vision – Discuss roadmap items (repo bootstrap, proactive repairs, remote sync) and how
Ignition will evolve into a complete developer environment command centre.
4. Tips for Effective Demos
• Be concise – Focus on the value delivered, not every screen. Keep the demo under 10 minutes.
• Use real‑world analogies – Compare Ignition’s hero panel to a car dashboard: instantly tells you if
you’re safe to drive.
• Balance design and substance – Highlight both the polished UX and the functional robustness (no
failures, sensible fallbacks).
• Invite interaction – Let observers suggest scenarios (e.g. “What if a tool fails to install?”) and show
how Ignition handles them.
• Quantify impact – Prepare slides or dashboards that convert telemetrics into saved hours, fewer
tickets and improved consistency.
5. Avoiding Pitfalls
• Do not rely on a live environment – Use demo mode to avoid network issues or unexpected
failures during the presentation.
• Do not mislead – Make it clear that demo mode uses simulated data. Highlight that the real product
behaves identically on actual workspaces.
• Do not oversell future features – Emphasise current capabilities and frame future work as a
roadmap, not a promise.
6. Post‑Demo Follow‑Up
After the demo, provide stakeholders with a summary document and an invitation to access Ignition in their
own test environment (if appropriate). Collect feedback via existing issue trackers and incorporate it into the
product roadmap.
2

---
