# Research: Terminality gate judges every issue-matrix row

Pre-spec discovery findings (F-1..F-4) and rulings (D-1..D-5) are recorded in the
"Pre-spec research" section at the end of this file. The decisions below resolve its
open questions.

## Decision: judge the whole matrix at done (resolves Q-1)

- **Decision**: at `done`, when a matrix exists, row diagnostics (malformed rows, unknown
  verdicts) and `in-mission` rows both count as unresolved, with or without gating refs.
- **Rationale**: the PASS text already claims "no unresolved (in-mission/unknown) rows".
  Judging only `in-mission` would keep a PASS that describes rows nobody checked.
- **Alternatives considered**: in-mission only, with narrower PASS text. Rejected by the
  operator (Decision `01M5X206M989YE99MA0KHRFTNP`).

## Decision: typed NOT_AUTHORED code on the existing reader (resolves Q-2)

- **Decision**: `read_issue_matrix_ref_content` raises `IssueMatrixRefReadError` with a new
  code, `ISSUE_MATRIX_NOT_AUTHORED`, when the read ref resolves and neither
  `issue-matrix.json` nor `issue-matrix.md` exists there (an object-presence check with the
  `lifecycle_phase` valid-rev-then-path discipline). A timeout, an OSError, an unreadable
  object or any failed presence check keeps `ISSUE_MATRIX_PROBE_ERROR`. A deleted ref keeps
  `ISSUE_MATRIX_REF_ABSENT`.
- **Rationale**: one read authority (C-004). Every caller that catches the error type keeps
  failing closed unless it opts in to the new code. The gate opts in only when there are
  zero gating refs.
- **Alternatives considered**: a separate `issue_matrix_present()` function. Rejected: it
  is a second entry point and repeats ref/phase resolution (Decision
  `01M5X498X3ATTAB12KQWMDPZRV`).

## Decision: decision record location (resolves Q-3)

- **Decision**: a short ADR, `docs/adr/4.x/2026-10-26-1-done-judges-every-issue-matrix-row.md`,
  plus a "What `done` enforces" section in `docs/development/reference/issue-matrix-verdicts.md`.
- **Rationale**: the operator asked for a decision record (or a reference-doc update), and
  the behaviour change (C-005) is worth an ADR people can cite.

## Supply chain

No dependency is added, upgraded or removed, so DIRECTIVE_051 does not apply.

## Pre-spec research

Base `origin/main` @ adf7b7a6 (issue #6653 cites 1a0c8b467). A live reproduction through
`evaluate_merge_gates` in block mode PASSed all three variants from the issue: an uncited
`in-mission` row, zero gating refs with an `in-mission` row, and a one-digit ref `#8`.

### Findings (root cause)

- **F-1 Row filter.** `issue_matrix_approval._issue_matrix_in_mission_rows` kept a row only
  when its issue was in the gating set discovered from PRIMARY artifacts. A row for an issue
  not reported as gating (uncited, context-only, a one-digit ref the detector skips, or
  recorded with `agent issue-verdict` alone) was dropped before the `done` check.
- **F-2 Zero-refs short-circuit, twice.** The blocker returned `None` on empty gating refs
  before reading the matrix, and the terminality gate returned PASS before resolving the
  matrix partition. The gate's early return is #5222 leg 1 (FR-001): a coord mission with
  zero refs and no matrix must not reach the coord probe, which raises when no matrix exists.
- **F-3 Overclaiming PASS.** The gate said "No unresolved (in-mission/unknown) issue-matrix
  rows" after judging only the gating rows.
- **F-4** `move-task --to done` reaches the same blocker through `st.feature_dir`, so the
  same gap applied there.

### Rulings

- **D-1 (operator, 2026-10-26).** At `done` every `in-mission` row blocks, cited or not.
  Classification decides which rows are REQUIRED; the verdict decides whether a row is RESOLVED.
- **D-2** `approved` is unchanged; a mission with zero gating refs never needs a matrix to
  be approved (FR-012/FR-013 of #3469).
- **D-3** Zero gating refs at `done`: read the matrix when one exists; a missing matrix is
  nothing to enforce. "Missing" is told apart from "probe failed" per topology (dir presence
  check; coord worktree dir; post-consolidation ref with valid-rev-then-path presence).
  Deleted ref, unreadable object or git failure stays fail closed (preserves #5222 F1).
- **D-4** The PASS text says what was judged (row count, or "no issue-matrix authored").
- **D-5** Accepted behaviour change: a mission that passes today can be refused at `done`.
