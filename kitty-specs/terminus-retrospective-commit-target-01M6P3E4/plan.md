# Implementation Plan: Terminus retrospective commit target (#7201)

**Branch**: `issue-7201-terminus-retrospective-target` | **Date**: 2026-11-05 | **Spec**: `kitty-specs/terminus-retrospective-commit-target-01M6P3E4/spec.md`
**Input**: Mission specification from `kitty-specs/terminus-retrospective-commit-target-01M6P3E4/spec.md`

## Summary

The terminus retrospective bookkeeping commit resolves its destination from `meta.json`'s
`target_branch` through the placement port. After `spec-kitty consolidate --target <branch>`
that value is stale, so `safe_commit` correctly refuses (`SafeCommitHeadMismatch`) and the
fail-open terminus leaves `retrospective.yaml` + `status.events.jsonl` uncommitted. The
technical approach is to hand the terminus the consolidate run's already-resolved merge
target through the existing, sanctioned `commit_merge_bookkeeping(destination_ref_override=)`
seam — at the teardown persist leg (where the commit actually happens) and at the post-merge
call site — and to let the recovery command the warning prints (`spec-kitty mission close`)
be aimed at that branch with a new optional `--target`. `safe_commit`, `commit_guard` and the
fail-open policy are untouched.

## Technical Context

**Language/Version**: Python 3.11+ (repo standard)
**Primary Dependencies**: `typer`, `rich`, `kernel.git`, `mission_runtime` (placement port); no new dependency
**Storage**: git refs + `kitty-specs/<slug>/{retrospective.yaml,status.events.jsonl,meta.json}`; no database
**Testing**: `pytest` — real-git fixtures for the terminus commit, `typer.testing.CliRunner` for the `mission close` option, plus the two named architectural ratchets
**Target Platform**: CLI (Linux/macOS developer + CI)
**Project Type**: single Python package (`src/specify_cli` with the `src/mission_runtime` / `src/kernel` boundaries)
**Performance Goals**: no new subprocess on the healthy path beyond the one bookkeeping commit already made; `mission close` adds no git call when `--target` is absent
**Constraints**: additive keyword-only parameter with a `None` default; no new guard-capability call site; no HEAD-derived destination; no gate weakening
**Scale/Scope**: 4 production modules + 1 CLI command signature, ~1 new test module + 1 CLI test addition, 1 regenerated doc page, 1 changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|------|---------|
| Single canonical authority (DIRECTIVE_044) | PASS — the resolved target keeps ONE owner (`lanes_manifest.target_branch`, FR-007); the fix forwards a value, it does not add a resolution rule. The one *new* input is `mission close --target`, mirroring the `--target` that `consolidate` already exposes. |
| Architectural alignment (DIRECTIVE_001) | PASS — routes through the existing `commit_merge_bookkeeping` seam; no second `GuardCapability` call site (NFR-001). |
| No write-side rederivation | PASS — every new destination is caller-supplied; no `get_current_branch` read added (NFR-002). |
| ATDD-first / red-first (C-011, DIRECTIVE_034) | PASS — the red test drives the public terminus entry point on a real git fixture before the fix. |
| Campsite rule / smallest viable diff (DIRECTIVE_024/025, RECONCILE_CHANGE_SCOPE_TENSIONS) | PASS — file set is exactly the four call sites + the seam signatures; no opportunistic refactor of the terminus or teardown. |
| No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION) | PASS — targeted files + the two named architectural gate files + owning-module fast tier. |
| Fail-open contract (FR-016) | PASS — preserved; the new destination only changes which ref is asked for. |
| Terminology canon | PASS — "target branch"/"resolved merge target"; no `feature` vocabulary introduced. |

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/terminus-retrospective-commit-target-01M6P3E4/
├── plan.md              # This file
├── research.md          # Phase 0 output (the refusal-vs-missing-commit determination)
├── spec.md              # Mission specification
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── traces/              # tooling-friction, approach, design-decisions
```

### Source Code (repository root)

```
src/specify_cli/
├── post_merge/retrospective_terminus.py     # terminus entry point + commit + recovery guidance
├── coordination/teardown.py                 # persist-before-destroy seam (_persist_retrospective)
├── consolidation/phase_teardown.py          # teardown call site (has run.lanes_manifest.target_branch)
└── cli/commands/
    ├── consolidate.py                       # post-merge terminus call site
    └── mission_type.py                      # `mission close` (new --target)

tests/
├── specify_cli/post_merge/test_retrospective_commit_target.py   # new: red-first real-git proof
├── specify_cli/cli/commands/test_mission_close_target.py         # new: close --target wiring
├── specify_cli/post_merge/test_retrospective_triggering.py       # existing: must stay green
├── specify_cli/coordination/test_teardown_seam_persist_before_destroy.py  # existing: seam contract
├── consolidation/test_merge_state_authority.py                   # existing: the precedent shape
└── architectural/{test_no_write_side_rederivation,test_guard_capability_call_sites}.py  # named ratchets
```

**Structure Decision**: the change is confined to the four modules that make up the
terminus commit path plus the one CLI command that prints/executes the recovery. Test files
mirror the source tree (`post_merge/`, `cli/commands/`), matching the existing layout.

## Phases

### Phase 0 — Research (complete)

`research.md` records the reproduction on `main` (b4d1e918e2), the determination that the
refusal is correct and the withheld destination is the defect, the in-tree precedent
(`destination_ref_override`), and the call sites to thread.

### Phase 1 — Design

**The change, in one sentence:** every caller that already knows the run's resolved landing
branch passes it down to the terminus, which forwards it to `commit_merge_bookkeeping` as
`destination_ref_override`; when nobody passes one, resolution is exactly as today.

Data flow (consolidate):

```
lane advance lands on <target>
  → phase_teardown._teardown_coord_worktree(run)
      → teardown_coordination_topology(..., destination_ref=run.lanes_manifest.target_branch)
          → _persist_retrospective(..., destination_ref=...)
              → run_retrospective_postcondition(..., destination_ref=...)
                  → _commit_captured_retrospective(..., destination_ref=...)
                      → commit_merge_bookkeeping(destination_ref_override=..., branch=<degrade ref>)
                          → safe_commit(target=CommitTarget(ref=<target>))   # HEAD matches → lands
```

Recovery flow: the terminus's warning names `spec-kitty mission close --mission <slug>
--target <target>`; `mission close --target` forwards the same `destination_ref`.

**Key types / signatures (contracts):**

```python
# post_merge/retrospective_terminus.py
def run_retrospective_postcondition(*, mission_slug: str, repo_root: Path,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
    destination_ref: str | None = None) -> str | None: ...

# coordination/teardown.py
def teardown_coordination_topology(repo_root: Path, mission_slug: str, mid8: str, *,
    ..., destination_ref: str | None = None) -> bool: ...

# cli/commands/mission_type.py
def close_cmd(..., target: Annotated[str | None, typer.Option("--target", ...)] = None) -> None: ...
```

**Design decisions carried from research:** D1 guard untouched; D2 reuse
`destination_ref_override`, additive and `None`-defaulted; D3 `--target` on `mission close`
(the resolved target is not durable after `clear_state`, and a HEAD read is forbidden); D4
regenerate the `mission close` section of `docs/api/cli-commands.md`.

**Rejected alternatives:**

- *Loosen `safe_commit` to commit onto the current HEAD when the destination mismatches.*
  Rejected: re-opens the wrong-branch-commit class, and moves a ref the operator is not on.
- *Make the terminus re-read `ConsolidationState` itself.* Rejected: it would put a second
  merge-target resolution authority inside the terminus, and `state.json` is cleared on
  success — the value is only reliably available to the run that holds it.
- *Commit the retrospective with a raw `git commit` / `--no-verify`.* Rejected: bypasses the
  single sanctioned protected-flow bookkeeping seam (NFR-001).
- *Persist the resolved target into `meta.json`/`lanes.json` at consolidate time.* Rejected
  for this mission: it changes what consolidate writes and contradicts the #3311
  never-rewrite guard on `lanes.json`; recorded as the deferred durable-record follow-up.

### Phase 2 — Tasks

One work package: the threading is a single coherent behaviour change whose parts are
individually meaningless ("thread a parameter" is not shippable alone), and its red-first
test covers both halves (consolidate path + recovery path). Tasks below.

## Implementation Concern Map

### IC-01 — Thread the resolved destination through the terminus commit path

- **Purpose**: make the terminus bookkeeping commit land on the branch the consolidate run
  actually merged into, instead of the stale `meta.json` target.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-006, FR-007, NFR-001, NFR-002, C-001, C-002
- **Affected surfaces**: `src/specify_cli/post_merge/retrospective_terminus.py`,
  `src/specify_cli/coordination/teardown.py`, `src/specify_cli/consolidation/phase_teardown.py`,
  `src/specify_cli/cli/commands/consolidate.py`
- **Sequencing/depends-on**: none
- **Risks**: the teardown seam is shared by merge cleanup, `mission close` and `--abort`;
  every caller must keep the `None` default so no unrelated leg changes behaviour. The
  `--abort` caller passes `persist=False`, so it never reaches the commit.

### IC-02 — Aim the recovery command

- **Purpose**: make the recovery the warning prints actually work for a Mission consolidated
  onto a topic branch — the population that hit #7201 before this fix.
- **Relevant requirements**: FR-004, FR-005, FR-007
- **Affected surfaces**: `src/specify_cli/cli/commands/mission_type.py`
  (`close_cmd` + `_teardown_coordination_worktree`), `retrospective_terminus.py`
  (`_rerun_command` / `_recovery_guidance`), `docs/api/cli-commands.md`
- **Sequencing/depends-on**: IC-01 (shares the `destination_ref` parameter on the seam)
- **Risks**: an added CLI option is a public surface — the help text must say what it is for
  and the option must default to today's behaviour; `--discard` also runs the persist leg, so
  it must forward the same value without changing its `runtime_abandoned` provenance.

## Verification plan

| Check | Command |
|-------|---------|
| New red-first module | `uv run pytest tests/specify_cli/post_merge/test_retrospective_commit_target.py -q` |
| Terminus existing contract | `uv run pytest tests/specify_cli/post_merge/test_retrospective_triggering.py -q` |
| Teardown seam contract | `uv run pytest tests/specify_cli/coordination/test_teardown_seam_persist_before_destroy.py -q` |
| Merge-target precedent shape | `uv run pytest tests/consolidation/test_merge_state_authority.py -q` |
| `mission close` CLI | `uv run pytest tests/specify_cli/cli/commands/test_mission_close_target.py tests/specify_cli/cli/commands/test_mission_close_guard.py -q` |
| Owning module fast tier | `uv run pytest tests/specify_cli/post_merge tests/consolidation tests/coordination -q -m "fast or unit"` |
| Named architectural ratchets | `uv run pytest tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_guard_capability_call_sites.py -q` |
| Lint / format / types | `uv run ruff check <files>`, `uv run ruff format --check --force-exclude <files>`, `uv run mypy <files>` |
| CLI reference freshness | `uv run python -m scripts.docs.build_cli_reference` then `uv run python -m scripts.docs.check_docs_freshness --ci` |
| Terminology guard | `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` |

## Complexity Tracking

No charter violations — table intentionally empty.
