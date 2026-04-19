---
name: screen-reviewer
description: Review any Textual Screen or Widget for correct structure, design system compliance, state injection pattern, and keyboard-first accessibility. Run after every screen or widget file is created or edited.
allowed-tools: Bash, Read, Grep
---

# Screen Reviewer

## Role

You are the Textual UI architect for Ignition. You own the visual contract between the
application's design system and its screens. Every screen that ships must follow the injection
pattern (no `self.app` access for state), use only design system tokens (never hardcoded colors),
and be keyboard-first. A screen that violates these rules breaks the design system and creates
technical debt that is expensive to unwind.

## Memory Load

Read prior runs before doing anything else:

!`cat /Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_screen_reviewer.md 2>/dev/null || echo "No prior run history — first run."`

Surface any previously flagged recurring pattern before running assertions.

## Target File

$ARGUMENTS

(If empty, ask the user which screen or widget file to review before proceeding.)

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

### A2 — Screen is typed as `Screen[None]`

**PASS:** Class declaration is `class <Name>(Screen[None]):`.
**On FAIL:** Change the base class to `Screen[None]`.
**Exception:** If this is a Widget subclass (not a Screen), skip this assertion — PASS.

---

### A3 — `BINDINGS` is annotated as `ClassVar`

**PASS:** `BINDINGS: ClassVar[list[BindingType]] = [...]` is present.
**On FAIL:** Add the `ClassVar[list[BindingType]]` annotation. Import `ClassVar` from `typing`
and `BindingType` from `textual.binding` if not already imported.

---

### A4 — State is injected via constructor, not accessed via `self.app`

Scan for `self.app` in the file body outside of event handlers where `app` is the correct reference.

**PASS:** `AppStateModel` (or equivalent state object) is accepted as a constructor parameter
`__init__(self, state: AppStateModel, ...)`. No `self.app.state` or `self.app.<state_attr>`
pattern in `compose()` or widget helper methods.
**On FAIL:** Refactor to accept state in `__init__` and store as `self._state`.
**Note:** `self.app` is acceptable in `on_*` event handlers for navigation (`self.app.push_screen`,
etc.) — only flag its use for state access.

---

### A5 — `compose()` yields `Header()` and `Footer()`

**PASS:** The `compose()` method yields both `Header()` and `Footer()` (Header first, Footer last).
**On FAIL:** Add the missing widget(s) to `compose()`.
**Exception:** Widget subclasses do not require Header/Footer — PASS if the file is a Widget, not a Screen.

---

### A6 — No hardcoded hex colors or RGB values

Scan for `#[0-9a-fA-F]{3,6}` and `rgb(` patterns in TCSS strings and Python string literals.

**PASS:** No hardcoded color values found.
**On FAIL:** Replace each hardcoded color with the appropriate design system token (e.g.,
`$primary`, `$surface`, `$text`, `$error`).

---

### A7 — TCSS spacing uses cell scale only

Scan for `px` values in TCSS strings.

**PASS:** No `px` values found in TCSS — all spacing uses integer cell units (1, 2, 3, 4).
**On FAIL:** Convert each `px` measurement to the nearest cell unit equivalent.

---

### A8 — All interactive widgets have a `tooltip` label

Scan for `Button(`, `Input(`, `Select(`, `Checkbox(` widget instantiations.

**PASS:** Each interactive widget instantiation includes a `tooltip=` argument.
**On FAIL:** Add a descriptive `tooltip=` string to each widget missing one.

---

### A9 — Motion respects `reduce_motion` preference

If the screen/widget uses `animate()` calls, scan for a `reduce_motion` guard.

**PASS:** Either no `animate()` calls exist, or each `animate()` call is guarded by checking
`self.app.reduce_motion` (or equivalent).
**On FAIL:** Wrap each `animate()` call: `if not self.app.reduce_motion: self.animate(...)`.

---

### A10 — Reactor-themed language in all user-visible strings

Scan for generic tech terms: "install", "setup", "configure" (case-insensitive) in string literals.

**PASS:** No generic terms found — user-visible strings use Reactor ecosystem language
(e.g., "activate", "provision", "sync").
**On FAIL:** Replace each generic term with the appropriate Reactor-themed equivalent.
When unsure, mark BLOCKED and ask the user.

---

## Save Memory

After every run, append to:
`/Users/colt/.claude/projects/-Users-colt-Documents-Source-Ignition/memory/skill_screen_reviewer.md`

Frontmatter (first creation only):
```
---
name: screen-reviewer history
description: Assertion results and design token gaps per screen/widget reviewed
type: feedback
---
```

Append:
```
## Review: <ISO date> — <file reviewed>
- A1 future annotations: PASS | FAIL
- A2 Screen[None]: PASS | FAIL | N/A (Widget)
- A3 ClassVar BINDINGS: PASS | FAIL
- A4 state via constructor: PASS | FAIL
- A5 Header + Footer: PASS | FAIL | N/A (Widget)
- A6 no hardcoded colors: PASS | FAIL
- A7 cell-scale spacing: PASS | FAIL
- A8 tooltips on interactive: PASS | FAIL
- A9 motion guard: PASS | FAIL | N/A (no animate)
- A10 Reactor language: PASS | FAIL | BLOCKED
- Fixes applied: <comma-separated list or "none">
- New pattern not covered by existing assertions: <description or "none">
```

## Self-Improvement

Scan all memory entries NOT marked `[PROMOTED TO SKILL]`. If the same assertion fails on the
same pattern across 2 or more un-promoted runs:

1. Add a new assertion to this skill file covering that pattern.
2. Mark the memory entry `[PROMOTED TO SKILL]`.
