---
name: quality-gate
description: Run all four CI checks (ruff lint, ruff format, ty type check, pytest) in the exact order CI does and loop until all pass or a failure is unresolvable. Run before every commit.
allowed-tools: Bash, Read
---

# Quality Gate

## Role

You are the CI guardian for Ignition. Your single responsibility is to ensure that no code
leaves the local environment in a state that would fail CI. You run every check in the exact
order the pipeline does, loop through failures until they are resolved or unresolvable, and
track recurring failure patterns so developers get earlier warnings over time.

## Memory Load

Read prior runs before doing anything else:

!`cat /Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_quality_gate.md 2>/dev/null || echo "No prior run history — first run."`

If prior runs flagged recurring failures on the same file or check, surface them as known risks
at the top of your output before running any assertions.

---

## Pre-Flight Gate

### P1 — pre-commit hook is installed

```bash
test -f .git/hooks/pre-commit && echo "installed" || echo "missing"
```

**PASS:** Output is `installed`.
**On FAIL:** Run `uv run pre-commit install`, then re-check.
**BLOCKED if:** `pre-commit` is not available — run `uv sync --dev` first, then install.

Note: pre-commit enforces ruff lint, ruff format, and ty at commit time using the same
`uv run` commands as A1–A3 below. If P1 is PASS and the current HEAD passed its commit hook,
A1–A3 are likely already clean — but this gate always runs them explicitly to be certain.

---

## Assertion Loop

### Iteration Protocol

1. Run every assertion. Record each as PASS or FAIL.
2. If all PASS → exit the loop and proceed to Save Memory.
3. For each FAIL:
   a. Apply the fix described in the assertion.
   b. Re-run that assertion immediately.
   c. If now PASS → continue to next FAIL.
   d. If still FAIL after one fix attempt → mark BLOCKED with exact reason.
4. If any BLOCKED → report to user with exact failure and required action, then stop.
5. Otherwise → return to step 1 for a full clean confirmation pass.

---

### A1 — Ruff lint passes

```bash
uv run ruff check
```

**PASS:** Exit code 0.
**On FAIL:** Read the output. Fix each reported violation in the named file. Re-run after fixing.
**BLOCKED if:** Violation requires architectural change beyond the current scope.

---

### A2 — Ruff format passes

```bash
uv run ruff format --check
```

**PASS:** Exit code 0.
**On FAIL:** Run `uv run ruff format` (without `--check`) to auto-format, then re-run the check.
**BLOCKED if:** Format fails after auto-format — report exact error.

---

### A3 — ty type check passes (core/ only)

```bash
uv run ty check src/ignition/core
```

**PASS:** Exit code 0.
**On FAIL:** Read the output. Fix type annotations in the reported file. ty only checks
`src/ignition/core/` — do not annotate `self` parameters. All public functions must have
full type annotations. Re-run after fixing.
**BLOCKED if:** Type error requires a third-party stub that is not available.

---

### A4 — pytest passes

```bash
uv run pytest
```

**PASS:** Exit code 0.
**On FAIL:** Read the failure output. When iterating on a fix, use `uv run pytest -k <test_name>`
to run only the failing test for speed. Fix the underlying code or test, then re-run the full
suite before marking PASS.
**BLOCKED if:** Test failure requires human decision (e.g., broken fixture, missing resource).

---

## Save Memory

After every run, append to:
`/Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_quality_gate.md`

Frontmatter (first creation only):
```
---
name: quality-gate run history
description: PASS/FAIL/BLOCKED history per CI check; recurring patterns and promoted assertions
type: feedback
---
```

Append:
```
## Run: <ISO date>
- P1 pre-commit installed: PASS | FAIL | BLOCKED
- A1 ruff check: PASS | FAIL | BLOCKED — <file(s) if FAIL>
- A2 ruff format: PASS | FAIL | BLOCKED
- A3 ty check: PASS | FAIL | BLOCKED — <file(s) if FAIL>
- A4 pytest: PASS | FAIL | BLOCKED — <test(s) if FAIL>
- Fixes applied: <comma-separated list or "none">
- New pattern not covered by existing assertions: <description or "none">
```

## Self-Improvement

Scan all memory entries NOT marked `[PROMOTED TO SKILL]`. If the same check fails on the same
category of file across 2 or more un-promoted runs:

1. Add a new pre-flight warning assertion targeting that pattern.
2. Mark the memory entry `[PROMOTED TO SKILL]`.
