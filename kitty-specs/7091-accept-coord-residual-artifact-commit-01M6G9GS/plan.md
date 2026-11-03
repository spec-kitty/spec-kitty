# Implementation Plan: coord-topology `accept` commits its own coordination-worktree residual

**Branch**: `issue-7091-accept-coord-residual-artifact-commit` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/7091-accept-coord-residual-artifact-commit-01M6G9GS/spec.md`
**Input**: Mission specification from `kitty-specs/7091-accept-coord-residual-artifact-commit-01M6G9GS/spec.md`

## Summary

`accept`'s residual artifact commit hands the commit router one absolute-path batch built
from BOTH checkouts (primary dirt + coordination-worktree dirt). The router groups the
batch by partition through the single file→kind authority. `mission-events.jsonl` has no
entry in `mission_runtime.artifacts._MISSION_FILE_KIND_BY_BASENAME` — deliberately, per
#5669 — so it classifies `None`, `None` is never coordination residue, and the
coordination worktree's copy is routed to the PRIMARY surface — where `safe_commit`
correctly refuses any path under `.worktrees/`, so `accept` exits 1 after readiness has
already passed.

Review cycle 1 rejected the first approach (adding a COORD-partition kind for the log):
classifying it flips `is_coord_residue_churn`, silently exempts the dirty-gate rows #5669
exists to protect, and fails the pinned C-002 guard
(`tests/review/test_mission_events_dirty_survivor_5669.py`).

The accepted fix is a scoped survivor at the seam that failed, matching issue #7091's own
expected outcome (b): a coordination-leg residual path whose classifier verdict is `None`
is not a mission artifact, so no surface owns it. `_run_residual_acceptance_commit` excludes
those paths from the batch, and `_note_deferred_residuals` reports them on the acceptance
result. Classified artifacts keep committing exactly as before, and a PRIMARY-classified
path stranded in the coordination worktree still resolves PRIMARY and still refuses loudly.
No classifier, partition, readiness or gate change.

Verified during grounding with a real coordination-topology fixture: before the change
`_run_residual_acceptance_commit` raised `ResidualCommitError` with the issued
`safe_commit: refusing to stage path under .worktrees/` text; after the change it returns a
result with no refused surface, commits the coordination-owned matrix on the coordination
branch, adds no commit to the primary branch, and leaves the keep-local log where it lives.

## Technical Context

**Language/Version**: Python 3.11 (repo `pyproject.toml` / `.python-version`)
**Primary Dependencies**: typer CLI, pytest, the in-repo `mission_runtime` package
(the artifact-kind/partition authority) and `specify_cli.coordination.commit_router`
**Storage**: git worktrees; JSON/JSONL mission artifacts under `kitty-specs/<mission>/`
**Testing**: pytest (`tests/mission_runtime`, `tests/specify_cli/cli/commands`,
`tests/architectural`); real-git fixtures, no mocked worktrees
**Target Platform**: POSIX developer/CI hosts with git
**Project Type**: single Python package (`src/specify_cli`, `src/mission_runtime`)
**Performance Goals**: the change is one dict entry and one enum member — no new I/O,
no extra git call, no new import on the residual path
**Constraints**: one classification authority (no accept-local classifier); no gate
weakening; narrow `is_status_state_path` must not widen
**Scale/Scope**: ~10 lines of production change across one module; 3 test files touched
(one new regression test set, one classifier pin, one partition pin)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — satisfied: the partition verdict stays on
  `mission_runtime.kind_for_mission_file` / `is_coord_residue_churn`; the fix ADDS the
  missing entry to that authority instead of forking a classifier at the accept seam.
- **`change-apply-smallest-viable-diff` / `DIRECTIVE_024` locality of change** —
  satisfied: the production diff is one exclusion + one reporting helper in `accept.py`;
  no change to the classifier, `commit_router.py` or `safe_commit`.
- **ATDD-first / `DIRECTIVE_034` test-first-bug-fixing** — satisfied: the regression
  test drives the pre-existing seam (`_run_residual_acceptance_commit`) and is authored
  and run RED before the classifier entry lands.
- **`NO_FULL_HEAVY_SUITES_IN_MISSION`** — satisfied: run the targeted accept residual,
  partition-mapping and write-surface-placement modules, not the full suite.
- **Gate integrity** — satisfied: no marker, skip, xfail or refusal relaxation is added.

No violations; `## Complexity Tracking` is not used.

## Project Structure

### Documentation (this mission)

```
kitty-specs/7091-accept-coord-residual-artifact-commit-01M6G9GS/
├── spec.md              # Mission specification
├── plan.md              # This file
├── contracts/
│   └── accept-residual-routing.contract.md   # The rule this mission implements
├── tasks.md             # Work-package planning output
└── tasks/               # Work-package prompts
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
└── accept.py                        # The fix: defer non-artifact coordination residuals,
                                     # report them on the acceptance result

src/specify_cli/coordination/
└── commit_router.py                 # UNCHANGED — partition grouping and staging

src/specify_cli/git/safe_commit*     # UNCHANGED — the .worktrees/ refusal stays loud
src/mission_runtime/artifacts.py     # UNCHANGED — no kind, no partition move (#5669)

tests/specify_cli/cli/commands/
└── test_accept_residual_partition.py    # red-first survivor + narrowness + flat control
                                         # + note reporting

tests/review/
└── test_mission_events_dirty_survivor_5669.py  # UNCHANGED — the C-002 guard that proves
                                                # the keep-local ruling was respected
```

**Structure Decision**: single-package repository; the change lands in the accept seam that
produced the failure and is proven through that seam. No new module.

## Design Decisions

### DD-01 — A scoped survivor in the residual committer, not a kind

Cycle 1 tried `MissionArtifactKind.MISSION_EVENT_LOG` in the COORD partition. Rejected in
review: `mission-events.jsonl` is deliberately NOT a kind (#5669 — keep-local, must stay
real dirt for the destructive gates), and classifying it flips `is_coord_residue_churn` so
those gates would silently discard its rows. The pinned C-002 guard
(`is_toolchain_generated_churn(...) is False`) fails under that approach. The accepted
design leaves the taxonomy alone and scopes the exception to the seam that needs it — the
same per-gate survivor pattern #5669 used for the review-handoff gate.

### DD-02 — The survivor is classifier-derived, not a filename literal

`_nonartifact_residual_paths` defers a coordination-leg path iff `kind_for_mission_file`
returns `None`. That keeps the one classification authority authoritative (C-001), adds no
second filename list, and retires itself automatically if the log ever gains a kind. It is
also why a future unrelated unclassified artifact is deferred-and-reported rather than
silently dropped.

### DD-03 — The deferral is reported, never silent

Leaving the log uncommitted is only acceptable if the operator can see it. The acceptance
result gains one note naming every deferred path and the #5669 rationale; both output lanes
(text and `--json`) render it. The residual commit's own surface outcome still reports the
commit it did make.

### DD-04 — Classified dirt keeps its existing verdicts

The survivor is not a blanket "ignore coordination-worktree dirt": a CLASSIFIED PRIMARY
path stranded in the coordination worktree still routes PRIMARY and is still refused by
`safe_commit` (pinned by a narrowness test), and a CLASSIFIED COORD artifact still commits
on the coordination branch (pinned by the survivor's own fixture). `safe_commit`'s
`.worktrees/` refusal is untouched.

### DD-05 — Flat missions unchanged

A coord-less mission has no coordination leg, so the log lives in the primary checkout and
the residual commit keeps committing it on the mission's own branch. A paired test pins
that pre-existing behaviour so the survivor cannot quietly become a global rule.

## Risks and Mitigations

- **The survivor's breadth.** Any unclassified coordination-worktree residual is deferred,
  not just `mission-events.jsonl`. That is the principled boundary (an unclassified path is
  not a mission artifact, #5697), and it is reported; misscoped agent artifacts such as
  `reasons-canvas.md` are separately unclassified and recorded as a follow-up in the PR's
  `## Deferred` so the taxonomy gap is not lost. A CLASSIFIED stranded artifact still
  refuses.
- **The reporting note adds one `git status` per accept run.** Accept is a
  once-per-mission command and already scans the coordination worktree twice; the note scan
  is bounded and advisory (failures are swallowed, never a new failure path).
- **A keep-local log left dirty after accept.** That is the #5669 posture (the log is not
  a mission artifact and is not committed by any surface); the note makes it explicit, and
  the destructive gates keep treating it as real dirt, which is what the ruling requires.
- **Drift back to classification.** The #5669 C-002 guard plus the accept tests pin the
  boundary; a future attempt to classify the log fails CI in two places at once.

## Complexity Tracking` is not used.

## Project Structure

### Documentation (this mission)

```
kitty-specs/7091-accept-coord-residual-artifact-commit-01M6G9GS/
├── spec.md              # Mission specification
├── plan.md              # This file
├── contracts/
│   └── accept-residual-routing.contract.md   # The rule this mission implements
├── tasks.md             # Work-package planning output
└── tasks/               # Work-package prompts
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
└── accept.py                        # The fix: defer non-artifact coordination residuals,
                                     # report them on the acceptance result

src/specify_cli/coordination/
└── commit_router.py                 # UNCHANGED — partition grouping and staging

src/specify_cli/git/safe_commit*     # UNCHANGED — the .worktrees/ refusal stays loud
src/mission_runtime/artifacts.py     # UNCHANGED — no kind, no partition move (#5669)

tests/specify_cli/cli/commands/
└── test_accept_residual_partition.py    # red-first survivor + narrowness + flat control
                                         # + note reporting

tests/review/
└── test_mission_events_dirty_survivor_5669.py  # UNCHANGED — the C-002 guard that proves
                                                # the keep-local ruling was respected
```

**Structure Decision**: single-package repository; the change lands in the accept seam that
produced the failure and is proven through that seam. No new module.

## Design Decisions

### DD-01 — A scoped survivor in the residual committer, not a kind

Cycle 1 tried `MissionArtifactKind.MISSION_EVENT_LOG` in the COORD partition. Rejected in
review: `mission-events.jsonl` is deliberately NOT a kind (#5669 — keep-local, must stay
real dirt for the destructive gates), and classifying it flips `is_coord_residue_churn` so
those gates would silently discard its rows. The pinned C-002 guard
(`is_toolchain_generated_churn(...) is False`) fails under that approach. The accepted
design leaves the taxonomy alone and scopes the exception to the seam that needs it — the
same per-gate survivor pattern #5669 used for the review-handoff gate.

### DD-02 — The survivor is classifier-derived, not a filename literal

`_nonartifact_residual_paths` defers a coordination-leg path iff `kind_for_mission_file`
returns `None`. That keeps the one classification authority authoritative (C-001), adds no
second filename list, and retires itself automatically if the log ever gains a kind. It is
also why a future unrelated unclassified artifact is deferred-and-reported rather than
silently dropped.

### DD-03 — The deferral is reported, never silent

Leaving the log uncommitted is only acceptable if the operator can see it. The acceptance
result gains one note naming every deferred path and the #5669 rationale; both output lanes
(text and `--json`) render it. The residual commit's own surface outcome still reports the
commit it did make.

### DD-04 — Classified dirt keeps its existing verdicts

The survivor is not a blanket "ignore coordination-worktree dirt": a CLASSIFIED PRIMARY
path stranded in the coordination worktree still routes PRIMARY and is still refused by
`safe_commit` (pinned by a narrowness test), and a CLASSIFIED COORD artifact still commits
on the coordination branch (pinned by the survivor's own fixture). `safe_commit`'s
`.worktrees/` refusal is untouched.

### DD-05 — Flat missions unchanged

A coord-less mission has no coordination leg, so the log lives in the primary checkout and
the residual commit keeps committing it on the mission's own branch. A paired test pins
that pre-existing behaviour so the survivor cannot quietly become a global rule.

## Risks and Mitigations

- **A partition-pin test enumerates kind sets literally.**
  `tests/architectural/test_write_surface_placement_guard.py` lists COORD kinds explicitly;
  the new kind is added there in the same commit so the P-1 pin stays honest.
- **`emit_mission_next_invoked` keeps asking for `STATUS_STATE`.** Intentional and
  unaffected: it needs a placement, and STATUS_STATE's home is the coordination mission
  dir. Recorded in the code comment next to the new kind so a future reader does not
  "fix" it into the new kind and change `next`'s write path inside a bug-fix PR.
- **Over-classification.** The basename entry is exact (`mission-events.jsonl` at the
  mission root, any depth prefix, matched by the existing classifier's basename leg), so
  no other file changes kind.

## Complexity Tracking

Not used — the charter check reports no violations.
