# Implementation Plan: Squash Merge Target Safety

## Architectural intent

Keep one branch-integration authority in `src/specify_cli/lanes/merge.py` and
make the isolated squash operation reusable in two modes:

```text
merge --dry-run ─┐
                 ├─> isolated squash simulation ─> conflict result
real merge ──────┘              │
                                ├─ custom drivers for governed artifacts
                                └─ planning-recency resolver for eligible paths

real merge + clean result  ─> commit temporary tree ─> advance target ref
dry-run or conflict        ─> discard temporary tree ─> refs unchanged
```

The simulation uses normal `git merge --squash <mission>` semantics. It never
passes a global favour-mission option. A failed Git merge is inspected for
unmerged paths. Only paths explicitly owned by the existing target-newer
planning policy may be reconciled; every remaining path becomes a blocker.

## Components

### 1. Squash simulation and conflict result

**Owner:** `src/specify_cli/lanes/merge.py`

- Extract the squash command and conflict inspection from
  `_merge_branch_into` into a narrow helper that runs inside the existing
  temporary worktree and ephemeral merge-driver activation.
- Add a typed, immutable result carrying sorted unresolved paths and a concise
  diagnostic. Do not expose temporary paths.
- Resolve eligible target-newer planning conflicts with the existing
  `target_newer_primary_artifacts` and three-way target-favouring helper.
- On unresolved conflict, abort/discard the temporary merge and raise/return
  before commit and `advance_branch_ref`.
- Preserve no-op squash and retry behavior.

### 2. Read-only forecast seam

**Owners:** `src/specify_cli/lanes/merge.py`,
`src/specify_cli/merge/forecast.py`

- Add a public forecast helper that runs the same isolated squash primitive in
  preview mode and always discards the worktree.
- Invoke it from `run_dry_run_forecast` only when strategy is squash and both
  local refs exist. The existing missing-mission-branch preview remains
  compatible.
- On conflict, emit a stable `TARGET_BRANCH_CONTENT_CONFLICT` blocked payload
  and exit 1. Human output names branches, paths, and rebase/manual-resolution
  remediation.
- Leave the clean payload key set unchanged.

### 3. Regression coverage

**Owners:** `tests/lanes/test_merge.py`, `tests/merge/test_forecast_seam.py`, and
one CLI-level regression module if the public CLI assertions need a fuller
fixture.

ATDD order:

1. Add a same-hunk source-conflict test that currently fails because target
   content is silently replaced.
2. Add a dry-run conflict test that currently returns a ready payload.
3. Add disjoint same-file and target-byte/ref invariants.
4. Re-run existing merge-driver, #3942 planning-recency, no-op/resume, golden
   payload, and non-squash strategy tests.

### 4. Operator documentation

**Owners:** `docs/guides/how-to/recovery/troubleshoot-merge.md`,
`docs/changelog/CHANGELOG.md`

- Explain the fail-closed default squash behavior and remediation.
- Record the RC5 bug fix and reference #4892.

## Data flow

1. Resolve persisted mission and target branches from `lanes.json`.
2. Create a detached temporary worktree at the target tip.
3. Activate registered merge drivers for that operation.
4. Run normal squash integration of the mission ref.
5. If Git reports conflicts, enumerate unmerged repo-relative paths.
6. Reconcile only target-newer planning paths; inspect unmerged paths again.
7. If any remain, return a deterministic blocker and discard the worktree.
8. In preview mode, discard even a clean simulation and report readiness.
9. In execute mode, commit the staged squash result and atomically advance the
   target ref through the existing `advance_branch_ref` seam.

## Error and recovery contract

- Diagnostic code: `TARGET_BRANCH_CONTENT_CONFLICT`.
- State preserved: source ref, target ref, primary checkout, WP lifecycle,
  branches, worktrees, and retention state.
- Suggested recovery: update/rebase the mission against the current target,
  resolve the named files, re-run dry-run, then run merge.
- No automatic ordinary-source side selection is offered.

## Validation matrix

| Surface | Required evidence |
|---|---|
| Same-hunk ordinary source | Failure; target SHA and bytes unchanged |
| Disjoint same-file edits | Success; both edits present |
| Dry-run conflict | Exit 1; deterministic JSON/human blocker; refs unchanged |
| Dry-run clean | Existing exact success keys and exit 0 |
| Custom-driver artifact | Existing reconciliation tests green |
| Target-newer planning | Existing #3942 tests green |
| Merge/rebase strategies | Existing behavior green |
| Quality | Focused pytest, Ruff, mypy, project fast and architectural gates |

## Risks and mitigations

- **Planning conflict becomes a regression:** resolve only paths selected by the
  current history-aware planning authority and retain its regression suite.
- **Preview drifts from execution:** both modes call the same simulation helper.
- **Temporary activation leaks:** retain the existing `ExitStack` teardown and
  information-attributes leak tests.
- **Error details become unstable:** sort and normalize conflict paths; avoid raw
  temporary-directory paths in public diagnostics.
- **Preview becomes expensive:** it performs one local isolated merge only for
  squash when both refs exist; correctness takes precedence at this destructive
  boundary.

## Rollback

The implementation is localized to the merge simulation and forecast call site.
If rollback is required, revert the mission commit; no data migration, schema
change, or persisted-state transformation is introduced.
