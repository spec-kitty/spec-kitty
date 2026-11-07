# Discovery: Terminus retrospective commit target (#7201)

## Question the issue poses

Issue #7201 asks for two changes' worth of ambiguity to be resolved first: is the *refusal*
(`safe_commit` warning `HEAD is '<topic>', expected 'main'`) the defect, or is the *missing
commit* the defect? The two answers prescribe opposite fixes, so this step settles it with
code-truth before the spec commits to a design.

## Reproduction on current `main` (b4d1e918e2)

Scratch repo, `kitty-specs/<slug>/meta.json` with `target_branch: main`, HEAD on
`topic-landing`, both terminus artifacts dirty, then the real public entry point
`run_retrospective_postcondition(mission_slug=..., repo_root=...)`:

```
WARNING ... retrospective for mission demo-mission-01ABCDEF was captured but could NOT be
committed: safe_commit: worktree /tmp/repro7201-… HEAD is 'topic-landing', expected 'main'.
Run `git -C /tmp/repro7201-… checkout main` first.. These files have uncommitted changes:
…/retrospective.yaml …/status.events.jsonl. … re-run `spec-kitty mission close --mission
demo-mission-01ABCDEF` to commit them.
returned sha: None
HEAD branch: topic-landing
porcelain: '?? kitty-specs/…/retrospective.yaml\n?? kitty-specs/…/status.events.jsonl'
topic-landing log: 1ab04f1 init        (no bookkeeping commit)
main log:          1ab04f1 init        (untouched)
```

Matches the issue's report exactly, including that the suggested recovery (`mission close`) is
the same code path.

## Which side is wrong (decision)

Neither the refusal nor the leftover commit is the defect.

- **The refusal is correct.** `safe_commit` asserts `worktree HEAD == destination_ref` before
  staging (`src/specify_cli/git/commit_helpers.py`, validation step 4 →
  `SafeCommitHeadMismatch`). The destination it was handed was `main`; HEAD was not `main`.
  Committing anyway would advance a ref the checkout is not on and, for a protected `main`,
  would be an unauthorized protected-branch write. Relaxing this would re-open the class of
  defect "committed onto a branch the operator never declared".
- **The leftover is not a defect either.** The terminus is fail-open *by contract*
  (`src/specify_cli/post_merge/retrospective_terminus.py` module docstring; FR-016): a
  retrospective failure must never abort a merge or a close. The warning + uncommitted files
  is that policy reporting an unresolved refusal.
- **The defect is the destination the terminus asked for.** The terminus re-derives its
  destination through the placement port, which reads `meta.json`'s `target_branch`
  (`main`). For a consolidate run with `--target <topic>` that value is stale: the run
  resolved the real landing branch once (`lanes_manifest.target_branch`, from `--target` >
  persisted `ConsolidationState.target_branch` > meta, per `core/paths.py::
  resolve_merge_target_branch`, FR-007 "single persisted merge target"). The caller never
  hands that resolved value to the terminus.

## Prior art in-tree (the mechanism already exists)

- `commit_merge_bookkeeping(destination_ref_override=...)` exists precisely for this:
  `src/specify_cli/git/bookkeeping_commit.py` documents it as "the RESOLVED merge target,
  threaded by the merge executor (terminus-merge-integrity C-1 / #4985/#4991)", and the
  architectural ratchet `tests/architectural/test_no_write_side_rederivation.py` sanctions the
  `CommitTarget(ref=destination_ref_override)` construction as NOT checkout-derived.
- Existing users already thread it: `consolidation/phase_bookkeeping.py:751`,
  `phase_teardown.py:338` and `:959`, `mission_number/bake.py:497`. The terminus's two call
  sites are the gap.
- `tests/consolidation/test_merge_state_authority.py:315` pins the non-default-target merge
  case for the merge executor — the same shape this mission needs for the terminus.

## Call sites to thread (from a full reader trace)

1. `cli/commands/consolidate.py:918` — post-merge `run_retrospective_postcondition`, has
   `resolved_target_branch` in hand.
2. `consolidation/phase_teardown.py::_teardown_coord_worktree` →
   `teardown_coordination_topology(...)` (the persist leg that runs *before* the coordination
   worktree is destroyed) — has `run.lanes_manifest.target_branch`.
3. `coordination/teardown.py::_persist_retrospective` / `teardown_coordination_topology` — the
   seam that must accept and forward it.
4. `cli/commands/mission_type.py::close_cmd` — the recovery path named by the warning; it has
   no resolved target today, so it needs `--target` to be aimable.

## Decisions

- **D1** Do not touch `safe_commit`, `commit_guard`, or the fail-open policy. The only change
  is what destination the terminus asks for.
- **D2** Reuse `destination_ref_override` rather than adding a second resolution authority.
  New keyword-only parameter, `None` default, so today's behaviour is the fallback.
- **D3** `mission close` gets an optional `--target`, and the refusal warning prints it when
  the terminus was given one — otherwise the documented recovery keeps the identical defect.
  Rationale for a flag rather than magic: after a *successful* consolidate,
  `clear_state()` (`consolidation/phase_finalize.py:102`) removes `state.json`, and the
  `--target` override is never written back to `lanes.json`/`meta.json`, so no durable record
  of the resolved target survives for `mission close` to read. An explicit operator value is
  the only honest source; a HEAD read is forbidden (NFR-002 / the write-side rederivation
  ratchet).
- **D4** Doc surface: the new option changes `docs/api/cli-commands.md`'s `mission close`
  section; regenerate that page and verify with `check_docs_freshness --ci`.

## Evidence consulted

- `src/specify_cli/git/commit_helpers.py` (`safe_commit` validation order, `SafeCommitHeadMismatch`).
- `src/specify_cli/git/bookkeeping_commit.py` (the single sanctioned protected-flow seam).
- `src/specify_cli/post_merge/retrospective_terminus.py` (fail-open contract, recovery guidance).
- `src/specify_cli/coordination/teardown.py` (persist-before-destroy seam).
- `src/specify_cli/consolidation/{executor,phase_teardown,phase_bookkeeping,phase_finalize}.py`.
- `src/specify_cli/core/paths.py::resolve_merge_target_branch` (FR-007 resolution order).
- `tests/architectural/test_no_write_side_rederivation.py` (destination_ref_override sanction).
- `tests/consolidation/test_merge_state_authority.py` (the merge-executor precedent).
- ADR-era context: #4985/#4991 (terminus merge integrity), #3716 (mission close --discard
  commit boundary), #5570 (teardown anchor), #2280 (idempotency-heal).
- Grounding sweep: `gh search issues/prs` for a prior fix — none; `git log -S
  destination_ref_override` shows no terminus-side threading.

## Open questions

- None blocking. Deferred (not fixed here): the resolved target is never *persisted* for a
  later bare `mission close`/`consolidate --resume` to find once `state.json` is cleared. The
  explicit `--target` flag covers the operator path; a durable record would be a separate
  change to what `consolidate` writes, out of this issue's scope.
