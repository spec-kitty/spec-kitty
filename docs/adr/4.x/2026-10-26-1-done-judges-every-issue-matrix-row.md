---
title: 'ADR: at done, every issue-matrix row is judged, cited or not'
description: 'At done the verdict decides resolution for every issue-matrix row; a present matrix is judged whole even with zero gating references, and a missing one is nothing to enforce.'
status: Accepted
date: '2026-10-26'
---

# At `done`, every issue-matrix row is judged, cited or not

**Status:** Accepted (2026-10-26). Operator rulings of 2026-10-26, recorded on #6653.

**Date:** 2026-10-26

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #6653 (an uncited `in-mission` row lands with exit 0).
- #4943 and PR #5222 (the `issue_matrix_verdict_terminality` merge gate, and its zero-reference early return, #5222 F1).
- Mission `issue-matrix-terminality-all-rows-01M5X1ZJ`; research in `kitty-specs/issue-matrix-terminality-all-rows-01M5X1ZJ/research.md`.
- Decisions `01M5X206M989YE99MA0KHRFTNP` (judge the whole matrix) and `01M5X498X3ATTAB12KQWMDPZRV` (a typed `ISSUE_MATRIX_NOT_AUTHORED` code on the existing reader).
- It refines [ADR 2026-09-20-1](../3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md): classification still decides which rows are required.

## Context and Problem Statement

The issue-matrix has two levers. **Classification** decides whether a row is required. **Verdict** decides whether an existing row is resolved. The `done` check mixed them up in two places:

1. `_issue_matrix_in_mission_rows` kept an `in-mission` row only when its issue was a discovered gating reference. A row whose issue was not cited, was cited only as context (`see #12`), was a one-digit reference the detector skips, or was recorded with `agent issue-verdict` alone, was dropped before the `done` check.
2. With zero gating references, both the blocker and the terminality gate returned before reading the matrix at all ("No gating issue references discovered — nothing to enforce").

So a Mission whose own matrix said it still owed a fix could be consolidated, or moved to `done`, with exit 0. The gate's PASS line, "No unresolved (in-mission/unknown) issue-matrix rows", described rows it never looked at.

The zero-reference early return existed for a reason (#5222 F1): a coordination Mission that never authored a matrix must not fail on a coordination probe for a file that was never written. Before this decision, the post-consolidation ref read could not tell "no matrix at a valid ref" from "the probe failed".

## Decision

### 1. At `done`, the verdict decides resolution for every existing row

Every `in-mission` row blocks at `done` in `block` mode and warns in `warn` mode, whether or not its issue is cited. This applies to `spec-kitty consolidate` (the terminality gate) and to `move-task --to done`, which call the same blocker. Classification still decides which rows are **required**: the completeness gate and the "missing rows" list are unchanged.

### 2. A present matrix is judged whole, even with zero gating references

With zero gating references, a matrix that exists is still judged at `done`: row diagnostics (malformed rows, unknown verdicts) and `in-mission` rows both count as unresolved. Judging only `in-mission` rows would keep a PASS that claims rows nobody checked.

### 3. A missing matrix is still nothing to enforce

A Mission with zero gating references and no matrix passes, so #5222 F1 holds. "Missing" is a positive fact, never an inferred one:

- for a coord-less Mission, or a materialized coordination worktree, the matrix file is absent from that directory;
- after consolidation, the coordination ref is valid and neither `issue-matrix.json` nor `issue-matrix.md` is in its tree. The reader reports this with its own code, `ISSUE_MATRIX_NOT_AUTHORED`.

### 4. `ISSUE_MATRIX_NOT_AUTHORED` means "nothing to enforce" only without gating references

The terminality gate accepts `ISSUE_MATRIX_NOT_AUTHORED` as a PASS only when the Mission has zero gating references. With gating references it stays a FAIL, as before. Every other read error (`ISSUE_MATRIX_REF_ABSENT`, `ISSUE_MATRIX_PROBE_ERROR`, `ISSUE_MATRIX_EMPTY_CONTENT`) fails closed on every path.

This now includes a Mission with zero gating references. One case reaches it in practice: running `consolidate` again after a finished run tore the coordination branch down. The read ref is then the deleted coordination branch, so the gate reports `ISSUE_MATRIX_REF_ABSENT` and FAILs, where the old early return passed. That is an accepted FAIL. The gate runs before any mutation, so an ordinary run never reaches it, and a Mission with gating references already failed the same way.

### 5. A PASS says what it judged

The PASS detail names the number of rows judged ("No unresolved (in-mission/unknown) rows among N issue-matrix row(s)"), or says "No issue-matrix authored and no gating issue references — nothing to enforce".

### 6. `approved` is unchanged

An `in-mission` row is still accepted at `approved`, and a Mission with zero gating references still never needs a matrix to be approved.

## Consequences

### Positive

- A Mission cannot land while its own matrix says it still owes a fix.
- `consolidate` and `move-task --to done` enforce one rule through one blocker.
- The gate output no longer overclaims.

### Negative

- **Accepted behaviour change (C-005).** A Mission that passes today can be refused in `block` mode, or warned in `warn` mode, at consolidation and at `move-task --to done`. The remedy is to record a terminal verdict for the row with `spec-kitty agent issue-verdict`.
- A zero-reference coordination Mission now reads its coordination ref at the terminality gate. A deleted ref, an unreadable object, an empty matrix or any other resolution error there now FAILs where the old early return passed. That is the fail-closed rule of NFR-002.

### Neutral

- The completeness gate keeps its zero-reference early return.
- The compat names `_issue_matrix_approval_blocker`, `_issue_matrix_evaluation` and `_issue_matrix_in_mission_rows` keep their names and signatures.

## Alternatives Considered

- **Judge only `in-mission` rows with zero references, with a narrower PASS text.** Rejected by the operator (Decision `01M5X206M989YE99MA0KHRFTNP`): the PASS would still have to describe which rows it did not check, and a malformed row would land unseen.
- **A separate `issue_matrix_present()` probe in `mission_runtime`.** Rejected (Decision `01M5X498X3ATTAB12KQWMDPZRV`): it is a second entry point that repeats the ref and lifecycle-phase resolution. The typed code on the one reader keeps a single read authority.

## References

- [Issue-Matrix Verdict Reference: What `done` enforces](../../development/reference/issue-matrix-verdicts.md#what-done-enforces)
- `src/specify_cli/tasks/issue_matrix_approval.py` (`_issue_matrix_approval_blocker`, `issue_matrix_judged_row_count`)
- `src/specify_cli/policy/merge_gates.py` (`_evaluate_issue_matrix_verdict_terminality_gate`)
- `src/mission_runtime/resolution.py` (`read_issue_matrix_ref_content`, `ISSUE_MATRIX_NOT_AUTHORED`)
