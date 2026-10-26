# Data Model: Terminality gate judges every issue-matrix row

No new persisted data. The domain facts the change relies on:

- **Issue-matrix row**: `issue` (handle such as `#5678`), `verdict`, `evidence_ref`.
  Terminal verdicts: `fixed`, `verified-already-fixed`, `deferred-with-followup`,
  `not-applicable`. Non-terminal: `in-mission`. Anything else is a diagnostic.
- **Gating reference**: an `implementation_target` citation in a PRIMARY artifact. It
  decides whether a row is REQUIRED (completeness gate), never whether a row is RESOLVED.
- **Matrix read outcome** (coordination ref read), `IssueMatrixRefReadError.code`:
  - `ISSUE_MATRIX_REF_ABSENT`: the ref is deleted. Fail closed.
  - `ISSUE_MATRIX_PROBE_ERROR`: git or IO failure, or an unreadable object. Fail closed.
  - `ISSUE_MATRIX_EMPTY_CONTENT`: the matrix is authored but empty. Fail closed.
  - `ISSUE_MATRIX_NOT_AUTHORED` (new): the ref is valid and neither file is present. Only
    the zero-gating-refs terminality gate reads it as "nothing to enforce".

## Invariants

- I-1: at `done`, any `in-mission` row or row diagnostic in a present matrix produces a
  FAIL (blocking in block mode).
- I-2: at `approved`, the outcome is identical to before the change.
- I-3: a probe error never yields a PASS.
- I-4: a PASS detail names what was judged.
