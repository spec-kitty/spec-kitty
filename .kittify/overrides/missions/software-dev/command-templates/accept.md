---
description: Validate an approved mission before merge
---
# /spec-kitty.accept - Validate Mission Readiness

**Version**: 0.12.0+

## Purpose

Validate that every work package is complete and the mission is ready to merge.
This step runs the acceptance gate, surfaces any blocking diagnostics, and only
clears the path to merge once the gate passes.

---

## 📍 WORKING DIRECTORY: Run from the repository root checkout

**IMPORTANT**: Acceptance runs from the repository root checkout, NOT
from a work-package worktree.

```bash
# If you are inside a worktree, return to the repository root checkout first:
cd $(git rev-parse --show-toplevel)
```

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Steps

### 1. Record Acceptance Evidence (Zero Hand-Edited JSON)

Before running the gate, record every acceptance-criterion verdict — and
register/execute any negative invariant — through the deterministic
`acceptance-verdict` command. **Never hand-edit `acceptance-matrix.json`.**

```bash
# Record one criterion's verdict:
spec-kitty agent mission acceptance-verdict --mission <handle> \
  --criterion <criterion-id> --result pass \
  --verification-method automated_test --actor <you> --evidence <ref>

# Register AND execute a negative invariant (something that must NOT hold),
# when the mission's acceptance-matrix.json declares one:
spec-kitty agent mission acceptance-verdict --mission <handle> \
  --negative-invariant <invariant-id> \
  --description "<what must NOT hold>" \
  --verification-method grep_absence \
  --verification-command "<pattern that must be absent>"
```

Repeat the criterion form for every row in `acceptance-matrix.json` until
each one is `pass` or `fail` (no `pending` rows left unintentionally). Each
invocation reports the recomputed `overall_verdict` — use it to confirm the
matrix is converging before moving on.

### 2. Run the Acceptance Gate

Run the acceptance command from the repository root:

```bash
spec-kitty accept --mission <handle>
```

This validates that all work packages are `approved` or `done`, checks the
readiness gates (including the acceptance matrix recorded in step 1), and
reports what (if anything) still blocks merge.

### 3. Inspect Acceptance Diagnostics

Read the command output carefully:

- If the gate **passes**, the output confirms the mission is ready to merge and
  prints the merge instructions.
- If the gate **fails**, the output lists each outstanding category (for
  example: WPs not yet approved, failing checks, or unresolved review
  feedback — including any malformed acceptance-matrix entry, named by item
  and reason). Treat every outstanding item as a blocker. Use
  `spec-kitty accept --mission <handle> --diagnose` for a read-only diagnostic
  pass that reports blockers without writing anything.

### 4. Resolve Any Gate Failures

For each blocker reported:

- Route the affected work package back through implement/review as needed.
- Re-run the relevant tests or checks until they pass.
- If a criterion or negative invariant still needs recording, go back to
  step 1 — through `acceptance-verdict`, never by hand-editing the JSON.
- Re-run `spec-kitty accept --mission <handle>` and confirm the gate is now
  clean. Do **not** force acceptance past an unresolved blocker.

### 5. Proceed to Merge

Only after the acceptance gate passes:

```bash
spec-kitty merge --mission <handle>
```

Follow the merge instructions printed by the acceptance command (and any
cleanup steps it lists).

## Output

After completing this step:

- The acceptance gate has passed for `<handle>`.
- All blocking diagnostics have been resolved (or none were present).
- Merge instructions have been surfaced to the operator.

**Next step**: `spec-kitty next --agent <name>` will advance to merge, or run
`spec-kitty merge --mission <handle>` directly.
