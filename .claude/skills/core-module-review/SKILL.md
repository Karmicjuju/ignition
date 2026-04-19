---
name: core-module-review
description: Review any module in src/ignition/core/ for type correctness, logging conventions, and path hygiene — the only directory ty enforces. Run after every core/ file is created or edited.
allowed-tools: Bash, Read, Grep
---

# Core Module Review

## Role

You are the core/ module steward for Ignition. The `src/ignition/core/` directory is the only
one the type checker (ty) enforces, and it is the foundation everything else depends on. Your
job is to ensure every module here is fully typed, logs correctly, and never reaches outside its
boundaries for paths. A type error or a rogue `print()` in core/ is a systemic issue — it means
CI will fail for everyone touching this module.

## Memory Load

Read prior runs before doing anything else:

!`cat /Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_core_module_review.md 2>/dev/null || echo "No prior run history — first run."`

Surface any previously flagged recurring pattern before running assertions.

## Target File

$ARGUMENTS

(If empty, ask the user which core/ module to review before proceeding.)

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

### A2 — All public functions have full type annotations (excluding `self`)

Scan for `def ` declarations that are not prefixed with `_`. Each must have type annotations
on all parameters (except `self`) and a return type annotation.

**PASS:** Every public function has complete annotations.
**On FAIL:** Add the missing annotations. Never annotate `self` — ty does not require it.

---

### A3 — Logger is obtained inside class or function scope, not at module level

Scan for `get_logger(` at module scope (i.e., not inside a `class` or `def` body).

**PASS:** No module-level logger assignment found. All `get_logger(` calls are inside a class
body or function body.
**On FAIL:** Move the `get_logger()` call inside the class `__init__` or the function body.

---

### A4 — All paths obtained via `ignition.core.paths` helpers

Scan for `Path(` constructions that are not inside a `paths.py` file itself.

**PASS:** No direct `Path(` construction for application directories. All paths use helpers
from `ignition.core.paths`.
**On FAIL:** Replace `Path(...)` with the appropriate helper call.
**Exception:** `Path(__file__)` for relative module paths is acceptable.

---

### A5 — No `print()` statements

Scan for `print(` in the file.

**PASS:** No `print(` calls found.
**On FAIL:** Replace each `print(...)` with the appropriate `structlog` call (`log.info(...)`,
`log.debug(...)`, etc.).

---

### A6 — No `os.path` usage

Scan for `os.path.` in the file.

**PASS:** No `os.path.` usage found.
**On FAIL:** Replace each `os.path.*` call with the `pathlib.Path` equivalent.

---

## Save Memory

After every run, append to:
`/Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_core_module_review.md`

Frontmatter (first creation only):
```
---
name: core-module-review history
description: Assertion results and type-hygiene findings per core/ module reviewed
type: feedback
---
```

Append:
```
## Review: <ISO date> — <file reviewed>
- A1 future annotations: PASS | FAIL
- A2 public functions typed: PASS | FAIL — <function(s) if FAIL>
- A3 logger inside scope: PASS | FAIL
- A4 paths via helpers: PASS | FAIL
- A5 no print(): PASS | FAIL
- A6 no os.path: PASS | FAIL
- Fixes applied: <comma-separated list or "none">
- New pattern not covered by existing assertions: <description or "none">
```

## Self-Improvement

Scan all memory entries NOT marked `[PROMOTED TO SKILL]`. If the same assertion fails on the
same pattern across 2 or more un-promoted runs:

1. Add a new assertion to this skill file covering that pattern.
2. Mark the memory entry `[PROMOTED TO SKILL]`.
