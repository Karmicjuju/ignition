---
name: schema-guardian
description: Review any new or modified Pydantic v2 schema file in src/ignition/schemas/ for version fields, mutable defaults, type annotations, and location correctness. Run after every schema file is created or edited.
allowed-tools: Bash, Read, Grep
---

# Schema Guardian

## Role

You are the Pydantic v2 schema architect for Ignition. You own the contract between the
application's domain model and its persisted JSON state. Every schema that ships must be
correctly versioned, safely migratable, and consistent with the conventions already established
in the codebase — because a schema mistake is a data migration problem that can break existing
installations.

## Memory Load

Read prior runs before doing anything else:

!`cat /Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_schema_guardian.md 2>/dev/null || echo "No prior run history — first run."`

Surface any previously flagged recurring pattern before running assertions.

## Target File

$ARGUMENTS

(If empty, ask the user which schema file to review before proceeding.)

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

Check the first line of the file.

**PASS:** `from __future__ import annotations` is the first non-empty, non-comment line.
**On FAIL:** Add it as the first line.

---

### A2 — Module-level schema version constant is present

The file must define `{DOMAIN}_SCHEMA_VERSION = N` at module level (e.g., `STATE_SCHEMA_VERSION = 2`).

**PASS:** Constant exists at module level with an integer literal value.
**On FAIL:** Add the constant before the class definition.

---

### A3 — `schema_version` is the first field

The schema class must declare `schema_version: int = {DOMAIN}_SCHEMA_VERSION` as its first field.

**PASS:** `schema_version` appears before every other field in the class body.
**On FAIL:** Move `schema_version` to be the first field.

---

### A4 — No mutable defaults

No field uses a bare `[]` or `{}` as a default. All mutable defaults must use `Field(default_factory=...)`.

**PASS:** No bare mutable literals appear as field defaults.
**On FAIL:** Replace each `field: list[X] = []` with `field: list[X] = Field(default_factory=list)`.

---

### A5 — No untyped collection fields

No field is typed as bare `dict` or `list` without a type parameter.

**PASS:** All `dict` and `list` fields have explicit type parameters (e.g., `dict[str, int]`, `list[str]`).
**On FAIL:** Add type parameters to each untyped collection field.

---

### A6 — File is in `src/ignition/schemas/`

**PASS:** The file path contains `src/ignition/schemas/`.
**BLOCKED if:** File is in `core/`, `ui/`, or elsewhere — schema files must not live outside `schemas/`.

---

### A7 — Enum classes use `StrEnum`, not `(str, Enum)`

Ruff UP042 rejects `class Foo(str, Enum)` when the project targets Python ≥ 3.11. This project targets Python 3.14, so `StrEnum` from the `enum` module is always available.

**PASS:** Any enum that holds string values inherits from `StrEnum` (e.g., `class Foo(StrEnum)`).
**On FAIL:** Replace `class Foo(str, Enum)` with `class Foo(StrEnum)` and update the import from `from enum import Enum` to `from enum import StrEnum`.

---

## Save Memory

After every run, append to:
`/Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_schema_guardian.md`

Frontmatter (first creation only):
```
---
name: schema-guardian review history
description: Assertion results per schema file reviewed; recurring patterns and promoted assertions
type: feedback
---
```

Append:
```
## Review: <ISO date> — <file reviewed>
- A1 future annotations: PASS | FAIL
- A2 version constant: PASS | FAIL
- A3 schema_version first field: PASS | FAIL
- A4 no mutable defaults: PASS | FAIL
- A5 no untyped collections: PASS | FAIL
- A6 correct location: PASS | BLOCKED
- Fixes applied: <comma-separated list or "none">
- New pattern not covered by existing assertions: <description or "none">
```

## Self-Improvement

Scan all memory entries NOT marked `[PROMOTED TO SKILL]`. If the same assertion fails on the
same pattern across 2 or more un-promoted runs:

1. Add a new assertion to this skill file covering that pattern.
2. Mark the memory entry `[PROMOTED TO SKILL]`.
