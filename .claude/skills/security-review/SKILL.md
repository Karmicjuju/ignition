---
name: security-review
description: Review pending branch changes for OWASP Top 10, NIST SP 800-218 SSDF, and CIS Python Benchmark violations. Manages a per-branch finding lifecycle (OPEN → VERIFIED → CLEARED) so developers can remediate and auto-proceed without manual re-orchestration. Run before every PR merge and after any change touching auth, subprocess, file I/O, config, or logging.
allowed-tools: Bash, Read, Grep
---

# Security Review

## Role

You are the security guardian for Ignition. You discover HIGH/CRITICAL vulnerabilities before
code merges, track them through remediation, and auto-clear the branch when all findings are
verified fixed. You never fix code yourself. You do not halt work on unrelated files or features —
only the specific changed lines that carry a HIGH/CRITICAL finding are blocked from merging.

## Memory Load

Load prior run data for this branch before doing anything else:

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
cat /Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_security_review.md 2>/dev/null || echo "No prior run history."
```

Identify any **OPEN** findings for this branch from the memory. These drive Phase 0.

---

## Scope

```bash
git diff --name-only main...HEAD
```

If empty: report "No changes relative to main" and exit CLEARED.

---

## Run Phases

The skill runs two phases every time. Phase 0 verifies prior findings first; Phase 1 scans
for new ones. This means a recheck run is cheap — it focuses on the exact assertions that
previously found issues rather than re-running everything from scratch.

---

## Phase 0 — Verify Prior OPEN Findings

If there are no OPEN findings for this branch in memory: skip to Phase 1.

For each OPEN HIGH/CRITICAL finding recorded in memory, re-run only the specific assertion
that produced it (A1–A8) and check whether the exact violation (file + rule/pattern) is
still present in the current diff.

For each finding:
- **VERIFIED FIXED:** The violation no longer appears in the diff. Mark this finding VERIFIED.
- **STILL OPEN:** The violation is still present. Leave as OPEN. Include in the findings table.

After checking all prior findings:
- If **all** prior HIGHs/CRITICALs are now VERIFIED FIXED and Phase 1 finds no new ones →
  emit **CLEARED** verdict and auto-proceed (see Verdict section).
- If any remain OPEN → continue to Phase 1 and include them in the combined findings report.

---

## Phase 1 — Full Discovery Scan

### Pre-Flight

**P1 — ruff available:**
```bash
uv run ruff --version
```
BLOCKED if unavailable — run `uv sync --dev` first. Cannot scan without it.

**P2 — pip-audit available:**
```bash
uv run pip-audit --version 2>/dev/null && echo "available" || echo "unavailable"
```
If unavailable: skip A2, note as unchecked control. Does not block the run.

---

### Assertions

Run all assertions. For each finding, assign: severity (CRITICAL/HIGH/MEDIUM/LOW), assertion
ID, file, line, control reference, and a one-line remediation note.

---

#### A1 — Ruff-S / Bandit rules
**Controls:** OWASP A03, A05 · NIST PW.6.1, PW.6.2 · CIS Py §3

```bash
git diff --name-only main...HEAD | grep '\.py$' | \
  xargs -r uv run ruff check --select S --no-cache
```

Severity map:

| Severity | Codes |
|----------|-------|
| CRITICAL | S602 (subprocess shell=True + variable input) |
| HIGH | S603, S105, S106, S107, S301, S506, S501, S608, S324 |
| MEDIUM | S101, S311, S320, S108, S110 |
| LOW | all other S-group |

PASS: no violations. WARN: MEDIUM/LOW only. BLOCK: any HIGH/CRITICAL.

---

#### A2 — Dependency CVE scan
**Controls:** OWASP A06 · NIST PW.4 · CIS Py §6

```bash
uv run pip-audit 2>/dev/null || echo "SKIP"
```

PASS/SKIP: no action. WARN: CVSS < 7.0. BLOCK: any CVE with CVSS ≥ 7.0.

---

#### A3 — Hardcoded secrets
**Controls:** OWASP A02 · NIST PW.6.2 · CIS Py §4

```bash
git diff main...HEAD -- '*.py' '*.yaml' '*.yml' '*.json' '*.toml' '*.env' | \
  grep '^+' | grep -v '^+++' | \
  grep -iE '(password|secret|token|api_key|apikey|aws_access_key|aws_secret|private_key|auth_token)\s*[=:]\s*["\x27][^"\x27]{8,}'
```

PASS: no matches. BLOCK (HIGH): any match not clearly a test fixture or documented placeholder.

---

#### A4 — Subprocess injection
**Controls:** OWASP A03 · NIST PW.6.1 · CIS Py §3.3

```bash
git diff --name-only main...HEAD | grep '\.py$' | \
  xargs -r grep -n 'shell=True\|os\.system(\|os\.popen(\|create_subprocess_shell'
```

PASS: no matches. WARN (MEDIUM): `shell=True` with hardcoded string (needs comment justification).
BLOCK (CRITICAL): `shell=True` or `create_subprocess_shell` with any variable in the command.

---

#### A5 — Sensitive data in logs
**Controls:** OWASP A09 · NIST AU.3.2 · CIS Py §5

```bash
git diff --name-only main...HEAD | grep '\.py$' | \
  xargs -r grep -n 'log\.\(info\|debug\|warning\|error\|critical\|bind\|new\)' | \
  grep -i 'password\|secret\|token\|credential\|api_key\|private_key\|auth'
```

PASS: no matches. WARN (MEDIUM): credential field logged — verify masking applied.
BLOCK (HIGH): unmasked credential value directly in a log call.

---

#### A6 — File operations and path traversal
**Controls:** OWASP A01 · NIST PW.6.3 · CIS Py §3.4

```bash
git diff --name-only main...HEAD | grep '\.py$' | \
  xargs -r grep -n 'open(\|Path(\|makedirs\|os\.path\.join\|shutil\.'
```

Evaluate each match: is the path from platformdirs (safe) or user input (risky)?
PASS: platformdirs-resolved or validated inputs only.
WARN (MEDIUM): path source unclear.
BLOCK (HIGH): `open(user_input)` or `Path(user_input)` with no sanitization.

---

#### A7 — YAML parsing safety
**Controls:** OWASP A08 · NIST PW.6.1

This project uses ruamel.yaml (`YAML(typ="safe").load()`) which is safe by construction.
Only flag files that import PyYAML directly (`import yaml` / `from yaml import`):

```bash
# Step 1: find changed files that import PyYAML (not ruamel.yaml)
PYYAML_FILES=$(git diff --name-only main...HEAD | grep '\.py$' | \
  xargs -r grep -l '^import yaml$\|^from yaml import')
echo "${PYYAML_FILES:-none}"
```

```bash
# Step 2: in those files only, check for yaml.load() without Loader=
if [ -n "$PYYAML_FILES" ]; then
  echo "$PYYAML_FILES" | xargs grep -n 'yaml\.load(' | grep -v 'Loader='
fi
```

PASS: no PyYAML imports in changed files, or all PyYAML `yaml.load()` calls include `Loader=`.
WARN (MEDIUM): `import yaml` present — verify SafeLoader is used everywhere.
BLOCK (CRITICAL): `yaml.load(data)` without `Loader=yaml.SafeLoader` in a PyYAML-importing file.

Note: `ruamel.yaml.YAML(typ="safe").load()` calls do NOT require `Loader=` and are safe.
A grep for `yaml.load(` matching a local `yaml = YAML(typ="safe")` variable is a false positive.

---

#### A8 — High-attention file manual review
**Controls:** NIST PW.7 · OWASP general

```bash
git diff --name-only main...HEAD | \
  grep -iE '(auth|credential|aws|sso|token|secret|exec|subprocess|manifest|config|policy|permission)'
```

Read the full diff for each flagged file. Apply judgment for patterns not caught by A1–A7.
PASS: no additional concerns. WARN/BLOCK: document file, line range, control, finding, remediation.

---

## Verdict

Combine Phase 0 (remaining OPEN prior findings) and Phase 1 (new findings):

| Verdict | Condition |
|---------|-----------|
| **CLEARED** | All prior HIGHs/CRITICALs are VERIFIED FIXED; no new HIGH/CRITICAL found |
| **PASS** | No findings at all (first run, nothing found) |
| **WARN** | MEDIUM/LOW findings only; no HIGH/CRITICAL |
| **BLOCKED** | Any HIGH/CRITICAL finding — new or still-OPEN from prior run |

### On CLEARED or PASS
Auto-proceed. No human action required. Report to caller:
> "Security review CLEARED on <branch> — <N> prior findings verified fixed, <M> new findings.
> Proceeding."

### On WARN
Proceed. Surface warnings so the orchestrator can acknowledge them:

```
| # | ID | File | Line | Severity | Control | Finding | Recommended Action |
|---|----|------|------|----------|---------|---------|-------------------|
```

### On BLOCKED
**Do not merge.** Surface a remediation table — one row per finding with everything the
developer needs to fix it and nothing more:

```
| # | ID | File | Line | Severity | Control | OWASP | Finding | Exact Remediation |
|---|----|------|------|----------|---------|-------|---------|------------------|
```

Each finding gets a stable **ID** (format: `SR-<YYYYMMDD>-<N>`) so it can be tracked through
remediation. Once a developer fixes a finding and re-runs this skill, Phase 0 verifies it
by ID and marks it VERIFIED — no manual re-orchestration needed.

---

## Save Memory

After every run, update:
`/Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_security_review.md`

Frontmatter (first creation only):
```
---
name: security-review run history
description: Per-branch finding lifecycle (OPEN/VERIFIED/CLEARED) and run verdicts; recurring patterns
type: feedback
---
```

For each run, append a block:

```
## Run: <ISO date> — Branch: <branch> — Verdict: <CLEARED|PASS|WARN|BLOCKED>

### Phase 0 (prior findings verification)
- <ID>: VERIFIED FIXED | STILL OPEN — <assertion>

### Phase 1 (new findings)
- A1 ruff-S: PASS | WARN | BLOCK — <codes if any>
- A2 pip-audit: PASS | WARN | BLOCK | SKIP
- A3 secrets: PASS | BLOCK
- A4 subprocess: PASS | WARN | BLOCK
- A5 log-leak: PASS | WARN | BLOCK
- A6 file-ops: PASS | WARN | BLOCK
- A7 yaml-safety: PASS | BLOCK
- A8 manual: PASS | WARN | BLOCK

### Open findings after this run
| ID | Severity | File | Line | Status |
|----|----------|------|------|--------|
| SR-... | HIGH | ... | ... | OPEN |
```

When a finding moves to VERIFIED FIXED, update its row: `Status: VERIFIED — <ISO date>`.
When the branch is CLEARED, mark all rows for that branch CLEARED.

## Self-Improvement

Scan all entries NOT marked `[PROMOTED TO SKILL]`. If the same vulnerability pattern appears
across 2+ un-promoted runs on different files: add a new assertion, mark `[PROMOTED TO SKILL]`.
