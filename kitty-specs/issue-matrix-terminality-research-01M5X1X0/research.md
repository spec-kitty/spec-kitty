# Research: issue-matrix terminality gate judges every row (#6653)

Base: `origin/main` @ adf7b7a6 (the issue cites 1a0c8b467; the operator re-confirmed on 9b21b75c).

## Evidence: live reproduction

`research/probe_6653.py` drives `evaluate_merge_gates` in block mode through the fixtures of
`tests/policy/test_merge_gates_issue_matrix.py` (run with `PYTHONPATH=. uv run --frozen pytest -s <probe>`).
On adf7b7a6 all three variants from the issue PASS:

```text
UNCITED:  pass  No unresolved (in-mission/unknown) issue-matrix rows        (#1234 cited+fixed, #5678 uncited in-mission)
ZERO:     pass  No gating issue references discovered — nothing to enforce (no refs, #5678 in-mission)
ONEDIGIT: pass  No gating issue references discovered — nothing to enforce (#8 cited, in-mission)
```

## Findings (root cause, confirmed against the code)

F-1. Row filter. `src/specify_cli/tasks/issue_matrix_approval.py::_issue_matrix_in_mission_rows`
keeps a row only when `row.issue in referenced_issues`, the gating set discovered from
PRIMARY artifacts. An `in-mission` row for an issue that discovery does not report as
gating (not cited, cited only as context, a one-digit ref the detector skips, or a row
recorded with `agent issue-verdict` alone) is dropped before the `target_lane == DONE`
check. Only the DONE leg uses this list: at `approved` the caller resets
`unresolved_in_mission = []`.

F-2. Zero-refs short-circuit, twice.
- `_issue_matrix_approval_blocker` returns `None` when `gating_refs` is empty, before it
  reads the matrix (approval AND done).
- `policy/merge_gates.py::_evaluate_issue_matrix_verdict_terminality_gate` returns PASS
  ("No gating issue references discovered — nothing to enforce") before it resolves the
  matrix partition. That early return is #5222 leg 1 (FR-001): a coord mission with zero
  gating refs and no matrix must not reach the coord probe, because
  `read_issue_matrix_ref_content` raises `IssueMatrixRefReadError` when no matrix exists.

F-3. Overclaiming PASS. `merge_gates.py` reports
"No unresolved (in-mission/unknown) issue-matrix rows" after judging only the gating rows.

F-4. `move-task --to done` reaches the same blocker
(`tasks_move_task.py:1278-1290`, through `st.feature_dir`, the topology-resolved COORD
surface), so the same gap applies there.

## Blast radius

- Callers of `_issue_matrix_approval_blocker`: `move-task` (approved + done) and the
  terminality merge gate (done). Re-exported through `tasks_parsing_validation.py` and
  `tasks.py` as frozen compat symbols (names must not change).
- `_issue_matrix_evaluation` / `_issue_matrix_in_mission_rows`: only the blocker uses
  them; they are re-exported too (compat).
- Tests: `tests/policy/test_merge_gates_issue_matrix.py` (TestTerminalVerdictEnforcement
  :340, TestZeroGatingReferencesNeverProbesCoordination :440, legacy-md coord ref :477),
  the move-task done-gate tests (grep `issue_matrix` under `tests/specify_cli/cli/commands/agent`
  and `tests/tasks`).

## Decisions

D-1 (operator ruling, 2026-10-26). At `done` every `in-mission` row in the matrix blocks,
cited or not. Classification still decides which rows are REQUIRED (completeness); the
verdict decides whether an existing row is RESOLVED. This matches the contract text in
`review/_issue_matrix.py:54-59` and `docs/development/reference/issue-matrix-verdicts.md:33-41`.

D-2. `approved` is unchanged. An `in-mission` row is acceptable there, and a mission
with zero gating refs still never needs a matrix to be approved (FR-012/FR-013 of #3469).

D-3. Zero gating refs at `done`: read the matrix when one exists; a missing matrix is
nothing to enforce. "Missing" must be told apart from "probe failed":
- coord-less topology: a dir-based presence check (`issue_matrix_artifact_present`).
- coord topology, coord worktree materialized: the same dir-based check on the coord dir.
- coord topology, post-consolidation ref read: the object is genuinely absent at a VALID
  ref (both `issue-matrix.json` and `issue-matrix.md`) -> nothing to enforce. A deleted
  ref, an unreadable object or a git failure stays fail closed (FAIL with the probe
  message), as it already is for a mission with gating refs. Today the ref reader folds
  "path never committed" into `ISSUE_MATRIX_PROBE_ERROR`, so the presence leg needs the
  two-step discipline of `mission_runtime.lifecycle_phase._git_object_present`
  (valid-rev check, then path check).
  This preserves #5222 F1: a coord mission with no matrix never FAILs.

D-4. PASS text says what was judged: the number of rows checked, e.g.
"No unresolved (in-mission/unknown) rows among N issue-matrix row(s)", or
"No issue-matrix authored and no gating issue references — nothing to enforce".

D-5. Accepted behaviour change (operator): a mission that passes today can be refused in
block mode (and warned in warn mode), including `move-task --to done`.

## Red-first tests to write

T-1. Gate, lanes mission, `#1234` cited + fixed, `#5678` uncited + in-mission -> FAIL
     naming `#5678` (block) / warning (warn). Control: the existing cited case.
T-2. Gate, zero gating refs, matrix with one `in-mission` row -> FAIL (today PASS).
T-3. Gate, one-digit cited ref `#8` with an `in-mission` row -> FAIL.
T-4. Gate, coord mission, zero refs, coord worktree materialized with an in-mission row -> FAIL.
T-5. Gate, coord mission, zero refs, post-consolidation, matrix at coord ref with an
     in-mission row -> FAIL; no matrix at the ref -> PASS (F1 preserved).
T-6. Existing `TestZeroGatingReferencesNeverProbesCoordination` stays green unchanged.
T-7. `move-task --to done` with an uncited in-mission row -> refused; `--to approved` with
     the same matrix -> allowed (D-2).
T-8. PASS detail text names the judged row count (no "No unresolved ... rows" over rows
     not judged).

## Open questions for specify / plan

Q-1. At `done` with zero gating refs and a present matrix, do validator diagnostics
     (malformed rows, `unknown` verdicts) also block? Proposed: yes. The gate judges
     the whole matrix it reads, and the PASS text already claims "unknown" rows were
     checked.
Q-2. Where does the presence probe live: a new `mission_runtime` function next to
     `read_issue_matrix_ref_content` (proposed `issue_matrix_present`), or a typed
     `ISSUE_MATRIX_ABSENT` code on the existing reader? Proposed: a new code on the
     reader, raised only when the ref is valid and both objects are absent, so one
     authority stays.
Q-3. Decision record: an ADR amendment versus an update to the reference doc
     `docs/development/reference/issue-matrix-verdicts.md`. Proposed: a short ADR in
     `docs/adr/4.x/` plus the reference-doc section "What `done` enforces".
