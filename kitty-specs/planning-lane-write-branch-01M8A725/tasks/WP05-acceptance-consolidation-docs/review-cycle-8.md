---
affected_files: []
cycle_number: 8
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T16:30:14Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review cycle 8 (reviewer-renata, runner claude::reviewer-renata)

**Verdict: changes requested.**

What holds:
- Fold claims 1 to 4 behave as stated.
- The every-change rule still credits an approved work package that touches one path in two credited commits. I probed this: the blob is credited and the squash check passes.
- A rename between two of the work package's own files is credited.
- A clean merge on the spine leaves the path un-attributed. The new test pins this.
- `opener_recorded` reaches no envelope or JSON. `move-task` and the evidence scan read only `code` and `detail`.

Three findings follow. The first one turns CI red.

## Issue 1 (blocker, red per-PR test): the skill edit was not followed by a digest regeneration

The edit to `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md` turns this test red:

```
tests/specify_cli/skills/test_historical_renders.py::test_every_current_render_is_listed
AssertionError: Shipped skill renders missing from the historical list; run
`uv run --frozen python -m scripts.skills.build_historical_skill_digests` and commit the result:
['spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md']
```

- **Attribution:** the test is green at `cee07ae2^` (16 passed, 1 skipped) and red at HEAD. The fold caused it.
- **Why it matters:** this is the gate that #7788 and #7790 moved into the per-PR `cli` shard (`tests/ci/test_skill_source_routing.py`), so the PR goes red.
- **Why it was missed:** the fold report lists the skill-pinning tests it ran, but not this one.
- **Fix:**
  1. Run `uv run --frozen python -m scripts.skills.build_historical_skill_digests`.
  2. Review the diff and commit `src/specify_cli/skills/data/historical_skill_renders.json`. That file is outside WP05's owned_files, so record the leeway.
  3. Re-run `tests/specify_cli/skills/` and `tests/ci/test_skill_source_routing.py`.

## Issue 2 (should fix, R2 leak by rename): a file made before the claim lands under a new name through a credited rename

`_scoped_final_walk` checks each path on its own, and git reads every commit with `--no-renames`. A rename therefore starts a fresh history under the new path. Pre-claim content then lands at exit 0 as follows:

1. A commit before the claim creates `curation/pkg/pre.py` with content nobody reviewed.
2. A credited `feat(WP02)` commit runs `git mv curation/pkg/pre.py curation/pkg/moved.py`.
3. The only change to `moved.py` on the spine is that credited commit, so `(moved.py, <pre-claim blob>)` is credited.
4. On the target, `pre.py` never existed, so there is no deletion to refuse.
5. `MergeOutcomeVerifier._verify_squash_content` returns **PASS**.

Probe, never committed: `/tmp/claude-0/-home-user-spec-kitty/241acd7b-8c3e-5505-b70e-8c22ad244fdf/scratchpad/r8probe2/test_r8_probe.py::test_rename_of_a_pre_claim_file_carries_pre_claim_content`. It uses the helpers `_same_file_mission` and `_wp02_claim` from `tests/consolidation/test_planning_lane_authorship_7860.py`. Its output: `CREDITED {'curation/pkg/moved.py', 'curation/pkg/other.py'} ... STATUS VerifyStatus.PASS`.

This is the same class as review 7 issue 1. It is arguably worse: git's default diff shows the rename as `similarity index 100%` with no content, so the reviewer never saw the moved lines. An explicit copy differs, because it shows up in the diff as added lines and so counts as reviewed work.

The fix makes these texts untrue:
- the module docstring ("So an owned-path change made before the claim is never its work");
- `adr-wording-c7.md` ("So an owned-path change made before the claim never lands as that work package's work");
- `docs/migrations/planning-lane-write-branch.md`;
- `7860.fixed.md` ("so an owned-file change made before the claim never lands as approved work through a later credited commit").

Fix options (an operator call if in doubt):

- **(a) Fail closed, consistent with R2.**
  - Read each spine commit's renames and copies with `git diff -M -C --name-status <sha>^1 <sha>`, through a new `git_probes` helper.
  - When a commit creates a path as a rename or copy of a source path, the new path inherits the source path's taint: an uncredited change to the source anywhere on the walk leaves the new path un-attributed.
  - Add a red-first test with the shape above, at both claim level and squash-verifier level.
  - Add a control in which the work package renames its own credited file. That control must still pass. It does today: `test_rename_of_own_file_credits_both` in the probe file.
- **(b) Residual.** Record it as residual (c) in the ADR wording and the migration doc, with an operator ruling. The text would say: "a file created before the claim and renamed by a credited commit lands under its new name". Then correct the texts above.

Note: `reconciliation_authorship.py` is at 1199 lines. Option (a) will push it over the limit. Move the planning-only walk pieces (`_PlanningScope`, `_scoped_commits`, `_scoped_final_walk`) into a module of their own rather than packing lines.

## Issue 3 (nit): `opener_recorded` defaults to True for causes that say nothing about the opener

`PlanningWindowUnresolved.__init__` defaults `opener_recorded=True`. That default also covers the three `IMPLEMENTATION_UNREADABLE` raises:
- the status log is unreadable (`wp_evidence.py:291`);
- the write branch cannot be decided (`:273`);
- `git_unavailable` (`_unresolved_start`).

For those, `planning_lane_scope._opener_recorded` returns True, and the note prints the "a claim event is recorded but no single commit introduced it, start a second window" steps. That advice is wrong when the log simply cannot be read.

The consolidate flow probably cannot reach this case, because the evidence axis refuses `IMPLEMENTATION_UNREADABLE` first. Even so, the field says something false.

Fix:
1. Make the field `bool | None`, defaulting to `None`. Set True only in `_unresolved_start`'s `EVIDENCE_WINDOW_UNCOMPUTABLE` branch and False in the no-opener raise.
2. Have `_opener_recorded` pass the value through, so that `None` prints the shared text.
3. Add one unit test for an unreadable-log raise.

## Not findings (for the record)

- **Bookkeeping commits.** They change no owned path, unless `owned_files` lists a path under `kitty-specs/<slug>/`, and the gate ignores those paths anyway (`_is_bookkeeping`). So they cannot block a path.
- **Second-parent changes.** A change on a second parent that reaches the spine by a merge is read through the merge's first-parent diff. The merge is in no window, so the path is uncredited and blocked. This is confirmed by `test_a_clean_merge_of_a_pre_claim_change_taints_the_path`.
- **Readability.** It is acceptable. The new function is short and its docstring matches the code. See the size note under issue 2.
- **ADR wording c7.** It matches the code, apart from the rename gap in issue 2.
