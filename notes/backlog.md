# Ignition Backlog

Items not yet in a sprint, ordered roughly by priority.

---

## AWS CodeArtifact Integration

**What:** Add CodeArtifact auth and config to the onboarding flow so engineers can pull internal packages after setup.

**Why:** Without it, a completed onboarding still leaves the engineer unable to install packages from the private Reactor registry.

**Scope (when triaged):**
- Onboarding Phase 3 (Access Systems): run `aws codeartifact get-authorization-token`, write `pip.conf` / `.npmrc` for the relevant domains
- Health check: verify CodeArtifact token is valid and not expired
- Auth Centre: surface token expiry + "Refresh CodeArtifact" action alongside SSO session
- PRD: add to FR#4 or as new FR before writing code

**Gate:** Needs PO triage. CodeArtifact domain/repo names are Reactor-specific config — must be confirmed before implementation.

---

## Telemetry Upload Pipeline

**What:** HTTP POST upload of buffered `telemetry_buffer.ndjson` events to the configured endpoint.

**Why:** The local buffer (Sprint 2) is complete. Upload pipeline is the natural next step.

**Gate:** `/security-review` must pass on the Sprint 2 branch before any upload code is written. Endpoint config goes in `AppConfigModel.catalog_url` or a new `telemetry_endpoint` field.
