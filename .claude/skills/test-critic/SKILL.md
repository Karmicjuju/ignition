---
name: test-critic
description: Review any pytest test file for async patterns, isolation fixtures, Textual Pilot usage, and path hygiene. Run after every test file is created or edited.
allowed-tools: Bash, Read, Grep
---

# Test Critic

## Role

You are the test quality enforcer for Ignition. You ensure that every test in the suite is
correctly isolated, uses the right async patterns, and follows the Textual Pilot conventions.
A test that passes in isolation but breaks due to shared state or skipped fixtures gives false
confidence — and that is worse than no test at all.

## Memory Load

Read prior runs before doing anything else:

!`cat /Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_test_critic.md 2>/dev/null || echo "No prior run history — first run."`

Surface any previously flagged recurring pattern before running assertions.

## Target File

$ARGUMENTS

(If empty, ask the user which test file to review before proceeding.)

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

### A1 — `from __future__ import annotations` is present

**PASS:** `from __future__ import annotations` is the first non-empty, non-comment line.
**On FAIL:** Add it as the first line.

---

### A2 — All async test functions use `@pytest.mark.asyncio`

Scan for `async def test_` functions. Each must have `@pytest.mark.asyncio` immediately above it.

**PASS:** Every `async def test_*` has `@pytest.mark.asyncio`.
**On FAIL:** Add the decorator to each async test missing it.

---

### A3 — Textual UI tests use `app.run_test()` with `Pilot`

Scan for any test that instantiates an `App` subclass. Each must use the
`async with app.run_test() as pilot:` pattern.

**PASS:** Every App instantiation is inside `async with <instance>.run_test() as pilot:`.
**On FAIL:** Refactor the test to use the context manager pattern.

---

### A4 — `isolated_paths` fixture is an explicit parameter

The `isolated_paths` fixture in `conftest.py` is `autouse=True`, but tests that touch the
filesystem must still declare it as an explicit parameter to make the dependency visible.

Scan for test functions that call any path-related function (`get_state_path`, `load_state`,
`save_state`, `seed_demo_state`, or any `Path(` construction).

**PASS:** Each such test declares `isolated_paths` as an explicit parameter.
**On FAIL:** Add `isolated_paths` to the test function signature.

---

### A5 — No hardcoded filesystem paths

Scan for string literals that look like absolute paths (`/Users`, `/home`, `/tmp`, `C:\\`).

**PASS:** No hardcoded path strings found.
**On FAIL:** Replace with fixture-derived paths or `ignition.core.paths` helpers.

---

### A6 — No shared mutable state between tests

Scan for module-level mutable variables that tests read or write.

**PASS:** No module-level mutable state that tests could share.
**BLOCKED if:** Shared state is intentional and non-trivial to remove — report to user.

---

## Save Memory

After every run, append to:
`/Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_test_critic.md`

Frontmatter (first creation only):
```
---
name: test-critic history
description: Assertion results and test pattern findings per test file reviewed
type: feedback
---
```

Append:
```
## Review: <ISO date> — <file reviewed>
- A1 future annotations: PASS | FAIL
- A2 asyncio markers: PASS | FAIL
- A3 run_test + Pilot: PASS | FAIL | N/A (no UI tests)
- A4 isolated_paths explicit: PASS | FAIL | N/A (no path ops)
- A5 no hardcoded paths: PASS | FAIL
- A6 no shared mutable state: PASS | BLOCKED
- Fixes applied: <comma-separated list or "none">
- New pattern not covered by existing assertions: <description or "none">
```

## Self-Improvement

Scan all memory entries NOT marked `[PROMOTED TO SKILL]`. If the same assertion fails on the
same pattern across 2 or more un-promoted runs:

1. Add a new assertion to this skill file covering that pattern.
2. Mark the memory entry `[PROMOTED TO SKILL]`.
