# Research memo — rc5 consolidate regressions

**Audience:** spec-kitty maintainers (software-engineer persona). **Date:** 2026-10-03.
**Base:** `skupstream/main` @ `c11d043e5`. All `file:line` below are on that tree.
**Sources:** grounding squad (debugger-debbie ×4, paula-patterns, researcher-robbie),
tickets #5569 #5570 #5571 #5572, PRs #5012 (`c830944174`), #5020 (`8b769edeec`),
#5031 (`9eae015382`), #5359/#5046 (`5ae9a41887`), changelog note #5587 (`4bf748a795`).
Codegraph was available (index of the sibling primary checkout); line numbers were
re-verified in this tree with `rg`/`sed`.

## Verdict: four separate predicates → one WP per issue

| Pair | Verdict | Why |
|---|---|---|
| #5570 ↔ #5572 | separate | Same family (act on the coord ref from a stale capture), but #5570 is check-then-`branch -D`, #5572 is heal-time recomputation of the strand set. Different code, different fix. |
| #5569 ↔ #5571 | separate | #5569 is claim authorship in reconciliation; #5571 is the resume preflight remedy for the coord worktree. |
| all others | separate | No shared missing predicate. |

Shared-file risk: `consolidation/executor.py` is touched by #5570 (teardown triple) and
#5572 (marker writer + heal caller) and #5571 (pre-mutation preflight). The touched
functions are disjoint; WPs keep disjoint function ownership.

## #5569 (P0) — canceled dependency-lane content on an approved lane's first-parent spine

- `lanes/worktree_allocator.py:1613-1625`: dependency merge without `--no-ff`; a fresh
  dependent lane fast-forwards, so WP01's commit sits on lane-b's first-parent spine.
- `consolidation/reconciliation.py:1732` `_collect_authored` (spine walk 1782-1789) claims it
  as approved authorship; `:1592` `_collect_excluded` (`lane_tip_shas - authored_shas`)
  drops it from the excluded set; `:1224` `_mixed_lanes` never selects a lane holding
  only a canceled WP; `:1372-1378` `_closed_world_anchors` exempts dependency-lane tips.
- **Missing predicate:** a commit reachable from a fully-canceled lane's tip (after its
  base) is canceled content and must never count as authorship of another lane.
- **rc5 miss:** the #4977 exclusion assumed smuggled commits arrive behind a merge's second
  parent; `plant_canceled_commit` (`tests/terminus/conftest.py:1170-1225`) always builds a
  true merge, so the test went green.
- **Residual link:** this is the predicate pinned by residual 7,
  `test_fully_canceled_dependency_lane_content_ideally_does_not_ship`
  (`tests/consolidation/test_canceled_content_residuals.py`, strict xfail, #5330). #5569 is
  its non-mixed variant. The fix flips residual 7 to a regular test instead of adding a
  parallel unit pin; the entry-point test covers the non-mixed shape.
- **Fix:** subtract the fully-canceled lanes' commits from the authored claim (SHAs,
  patch-ids, blobs) and stop using a fully-canceled dependency lane tip as a closed-world
  anchor. One claim correction covers squash and `--strategy merge`. Allocator `--no-ff`
  is rejected (prevents new cases only) and refusing the cancel is a policy change.

## #5571 (P0) — resume gives "Commit" advice for a lagging coordination worktree

- `consolidation/executor.py:3368-3369` (`_pre_mutation_safety_preflight`,
  `assert_worktree_clean(coord_worktree)`) raises `MERGE_UNSAFE_WORKTREE_DIRTY` with the
  generic remedy at `git/destructive_guard.py:206`.
- The behind-own-HEAD advice (`executor.py:3784-3795`) and in-place recovery
  `_recover_behind_head_primary_on_resume` (`:3819-3880`, gate at `:3848`) apply only to
  `MERGE_UNSAFE_PRIMARY_DIRTY`. `classify_resume_dirty_remedy` / `is_pure_behind_head_lag`
  (`consolidation/preflight.py:778-838`, `:840+`) are never applied to the coord worktree.
- **Missing predicate:** the coord-worktree refusal on `--resume` is not classified as a
  pure behind-own-HEAD lag (base `state.pre_mutation_coord_sha`).
- **rc5 miss:** the fix assumed only the repository root checkout can lag; `test_repro_4982.py:82`
  merges inside the coord worktree, which leaves it clean.
- **Fix:** reuse the same classifier + in-place refresh for the coord worktree on `--resume`
  when the lag is provably pure; otherwise print the "Do NOT stage or record" advice. The
  ancestry-only "already integrated" skip stays as designed.

## #5570 (P1) — coord teardown deletes a branch that moved after the CAS check

- `coordination/teardown.py:185-207` `_enforce_projection_teardown_gate` (one `rev-parse`,
  `:198`); teardown then writes the retrospective (`:354`) and removes the worktree (`:362`).
- `consolidation/executor.py:2863-2897` `_delete_mission_branch` runs an unconditional
  `git branch -D` (`:2888`); expected tip comes from `coord_tip_after_projection` (`:1619`).
- **Missing predicate:** the delete is not compare-and-delete against the gated tip.
- **rc5 miss:** `test_teardown_aborts_when_coord_tip_moved_since_checkpoint` moves the tip
  before the gate; nothing commits inside the window.
- **Fix:** `git update-ref -d refs/heads/<b> <expected_sha>`; on mismatch raise, keep the
  branch, non-zero exit. Smaller than holding `feature_status_lock`, and also covers raw git
  commits. Same flaw noted at `orchestrator_api/commands.py:990` (follow-up candidate,
  assessed in plan).

## #5572 (P1) — doctor `--fix` reverts a reviewer's later reopen

- Marker writer `consolidation/executor.py:1075-1110` (schema `:1102-1109`) stores no
  commit SHAs. `coordination/coherence.py:546-580` `_recorded_strand_shas` re-derives
  "recorded" as every status-log commit in `captured_sha..HEAD`; `repair_coord_strand`
  (`:613`) reverts them; guard `_head_shape_is_expected` (`:471-503`).
- **Missing predicate:** the strand's own commits are not recorded at write time.
- **rc5 miss:** `test_repro_4973.py:84-87` uses a non-status-log third-party commit.
- **Fix:** persist `strand_shas` when the marker is written (every write site runs after the
  done bake); heal reverts only those; refuse (no revert, no "Healed", non-zero) when the
  range holds any other status-log commit or the marker predates the field. The `--resume`
  caller shares the primitive.

## Changelog contradiction map (rc5 `### Fixed`)

| Issue | Parent | rc5 entry contradicted (CHANGELOG.md, this tree) |
|---|---|---|
| #5569 | #4977 | L182-184 |
| #5571 | #4982 | L183, L192 |
| #5570 | #4981 | L186 |
| #5572 | #4973 (doctor leg) | L191 |

The #5587 Upgrade Notes entry is at L23-29 under `[Unreleased] - 4.0.0rc6`; new Fixed
entries go under `### Fixed` (L35).

## Escalation check

None of the three operator-escalation triggers fire: no fix weakens CAS or the closed
world (#5569 tightens the anchor set), residual 7 is fixed in-mission rather than deferred,
and no fix relies on `--attest-canceled-superseded`.
