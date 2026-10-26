# Research: Terminality gate judges every issue-matrix row

Discovery findings, evidence and the live reproduction are in
`kitty-specs/issue-matrix-terminality-research-01M5X1X0/research.md` (F-1..F-4, D-1..D-5).
This file records the planning decisions that resolve its open questions.

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
