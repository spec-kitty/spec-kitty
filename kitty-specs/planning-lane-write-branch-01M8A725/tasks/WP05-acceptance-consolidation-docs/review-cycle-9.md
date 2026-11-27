---
affected_files: []
cycle_number: 9
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T18:11:58Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review cycle 9 (reviewer-renata, runner claude::reviewer-renata)

**Verdict: changes requested.** One R2 leak remains, plus two nits.

## What holds

- **Fold claim 1.** The digest is regenerated. `test_historical_renders.py` and `test_skill_source_routing.py` pass; counts are in the report.
- **Fold claim 2.** Rename and copy taint works for every shape that starts after the planning pin. I probed each of these:
  - a rename chain across three commits (pre-claim, then `a.py`, then `b.py`, then an edit): FAIL, correct;
  - a pre-claim file in a non-owned path renamed into an owned path by a credited commit: FAIL, correct;
  - a credited rename of an owned file to an out-of-scope path: FAIL, correct;
  - delete then re-add of a pre-claim path: FAIL. The taint is permanent, which is over-strict but fails closed;
  - the own-file rename control: PASS.
- **Kernel.** `changed_entries(copies=False)` emits exactly the old flags (`_rename_flag`). The other callers (`bulk_edit/gate.py`, `lanes/auto_rebase.py`, `lanes/planning_base.py`, `review/_dead_code.py`, `line_attribution.py`, `mission_base.py`, and `git_probes.py:726`) never pass `copies`. `tests/kernel/test_git_listing.py::test_changed_entries_with_copies` pins the argv.
- **Fold claim 3.** Verified: `False` is set at `wp_evidence.py:297`, `True` at `:324`, and the default is `None`.
- **Mutations.** Each was temporary and reverted; none was committed.
  - The lineage probe was switched to `-M` without copies: 2 tests went red.
  - The kernel `copies` flag was switched to `-M`: 3 tests went red.
  - The `dropped` taint was removed: 1 test went red.
- **Static checks.** ruff, ruff format and mypy are clean on all 11 changed files. There are no suppressions. C901 is clean.

## Issue 1 (should fix, R2 leak): changes made before the planning pin are never walked

`_scoped_final_walk` walks `first_parent`, which is `_lane_first_parent_spine(pin, coord_base)`. That range leaves out:
- every Mission-branch commit between the Mission base and the planning pin;
- the pin commit itself.

The squash axis, however, diffs from the target base (`claim_inputs.py:424`, `excluded_window_base=inputs.target_base`). So content committed to the Mission branch before `finalize-tasks` is in the landing, but no taint walk ever sees it. Probes, never committed, using `excluded_window_base` set to the `main` tip as in production:

| Shape | Credited | Squash verdict |
|---|---|---|
| Before the pin, `curation/pkg/same.py` is created with 20 unreviewed lines. After the claim, a credited `feat(WP02)` commit appends `L = 1`. | `same.py` | **PASS**. The review diff shows only `+L = 1`. |
| Before the pin, `curation/pkg/pre.py` is created. A credited commit runs `git mv` to `moved.py`. | `moved.py` | **PASS**. The diff is a 100% rename with no content. |
| Before the pin, non-owned `elsewhere/x.py` is created. A credited commit runs `git mv` into `curation/pkg/x.py`. | `x.py` | **PASS** |

Before WP05 all three FAILed, because the planning lane authored nothing. This is the review 7 and review 8 class again, one boundary earlier. These texts are therefore untrue:
- the module docstring ("So an owned-path change made before the claim is never its work");
- the c8 ADR wording ("So an owned-path change made before the claim never lands as that work package's work");
- `7860.fixed.md` ("an owned-file change made before the claim never lands as approved work through a later credited commit");
- the migration doc.

Probe file: `/tmp/claude-0/-home-user-spec-kitty/241acd7b-8c3e-5505-b70e-8c22ad244fdf/scratchpad/r9probe/test_r9_probe.py`. The tests are `test_pre_pin_file_modified_by_credited_commit`, `test_pre_pin_file_renamed_by_credited_commit` and `test_pre_pin_nonowned_file_renamed_into_scope`.

**Fix (fail closed, consistent with R2):**
- Start the final-state taint walk at the Mission base, not at the pin. Credit windows stay as they are.
  - Use `consolidation/mission_base.py::resolve_mission_base`, or the merge-base of the target base and the coordination base.
  - Every commit in `<Mission base>..pin`, and the pin commit itself, is then an uncredited change that taints the paths it touches.
  - A Mission base that cannot be resolved means the lane authors nothing.
- Keep `_scoped_commits` (SHA and patch-id entry) on the windows as today.
- Add red-first tests for the three shapes above, at claim level and squash-verifier level, with the window base set to the target tip (not the pin, as `_commit_set` does now).
- Add a control: a Mission whose pre-pin commits are bookkeeping only (`kitty-specs/<slug>/...`) still PASSes.
- Update the four texts, and the c8 ADR wording's "`<planning pin>..<coordination base>`".

If you would rather record this as a residual, it needs an operator ruling, and the four texts must say so. I recommend the fix: it is a range change, not a design change.

## Issue 2 (nit): document the below-threshold rename beside residual (c)

Probe `test_heavy_edit_rename_below_threshold`:
- a pre-claim `pre.py` (20 lines) is removed;
- a credited commit adds `moved.py`, keeping 6 of those lines and adding 30 new ones;
- git reads this as D plus A, so `moved.py` is credited and the squash axis passes.

This is safe in the same sense as residual (c): the review diff shows the whole file as added lines. But the residual text names only copies. Add one clause to the docstring, the migration doc and ADR residual (c): "a rename below git's similarity threshold reads as a delete and an add, likewise shown in full."

## Issue 3 (nit): stray punctuation in the ADR wording

In `adr-wording-c8.md`, residual (b) ends "changes the scope.;". Drop the `;`.

## Residual (c), judged

The claim is accurate. With plain `-C`, a copy of a source the same commit left unchanged reads as an added file. The probe `test_copy_then_delete_source` shows the full shape:
- a credited commit copies an untouched pre-claim `pre.py` to `copy.py`;
- a later credited commit deletes `pre.py`;
- `copy.py` is credited, and the squash axis passes.

If `pre.py` stays on the branch, the squash FAILs on `pre.py` itself, so the copy alone carries nothing.

The content is visible to review. Neither the credited commit's own diff nor the WP review range (`git log -- <owned pathspecs>`, no `-C`) uses `--find-copies-harder`, so both show the copy as added lines. For a reviewer this is the same as the work package writing those lines fresh. So I accept it as a residual, not a leak of unreviewed content.

`--find-copies-harder` would close it:
- **Cost.** It treats every unmodified tree file as a copy source for each spine commit. Exact copies are found by hash and are cheap. Inexact detection is bounded by `diff.renameLimit` and is silently skipped above it.
- **Side effects.** It over-refuses only copies of tainted files, which is in R2's spirit.

**Recommendation:** keep it as residual (c), as worded. Optionally, add `--find-copies-harder` as a cheap tightening. It is not required for approval. Once issue 1 is fixed, pre-pin files become taint sources too, and the same residual then covers copies of them.
