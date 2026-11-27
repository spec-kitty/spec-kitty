---
affected_files: []
cycle_number: 7
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T14:46:12Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review cycle 7 (reviewer-renata, runner claude::reviewer-renata)

Verdict: **changes requested.** Fold claims 1 to 5 hold: merges are dropped from every window, the refusal prints the restart steps, `explains` gates the note, commands carry real ids and `--agent`, and mypy and the Console fix are in. One R2 leak of the same kind as review 6 issue 1 remains, without a merge this time. There is also one note that can never print.

## Issue 1 (should fix, R2 leak): an owned-path change made before the claim lands through a credited commit's blob

`reconciliation_authorship._lane_final_walk` / `_final_authored_walk` credits the **whole final blob** of a path whose newest change is a credited commit. That blob holds every earlier change to the file, including changes the Mission branch made **before the work package's claim**. On the default `squash` strategy, the blob axis is the only content check, so the pre-claim change lands as approved authorship at exit 0. The reviewer never saw that change: the review range starts at the window opener.

### Reproduction

Scratch file, never committed: `/tmp/claude-0/-home-user-spec-kitty/241acd7b-8c3e-5505-b70e-8c22ad244fdf/scratchpad/r7probe/test_r7_sameblob.py`. It uses the helpers of `tests/consolidation/test_planning_lane_authorship_7860.py`.

On the Mission branch, with `WP02` owning `curation/pkg/**`:
1. `E = 1  # pre-claim` is committed to `curation/pkg/same.py`.
2. The claim commit follows.
3. `feat(WP02)` appends `L = 1` to the same file.

Result:
- `early` is not in `claim.shas`, which is correct.
- `(same.py, <late blob>)` **is** in `claim.blobs`.
- `MergeOutcomeVerifier._verify_squash_content` returns **PASS**, with no divergence.

Review 6 issue 1 was the same leak through a conflict merge. The fix closed only the merge route. A plain first-parent commit before the claim, or a clean merge of a pre-claim side branch followed by a credited touch of that file, takes the same route.

### Texts this makes untrue

- The ADR wording (`adr-wording-c6.md`): "So an owned-path change made before that claim is never its work".
- `docs/migrations/planning-lane-write-branch.md:51-53`: "an owned-path change made before that claim is never its work".
- `docs/changelog/unreleased/7860.fixed.md`: "content written before the claim never counts". This sentence is about the evidence window, but readers will take it as a statement about landing.
- The module docstring of `reconciliation_authorship.py`.

### Fix: choose one, operator call if in doubt

- **(a) Fail closed, consistent with R2.** Credit a path's final blob or deletion only when no non-bookkeeping commit on the walk (`pin..coordination base`, first-parent) changed that path outside a window that owns it. A pre-claim change to a credited path then leaves the path un-attributed. For example, `keep(sha, path)` also requires that every earlier walk commit touching `path` is owned at that commit. Add a red-first test with the shape above, at both the claim and the squash-verifier level.
- **(b) Residual.** Record it as residual (c) in the ADR wording and the migration doc, with an operator ruling: the planning lane is attributed by final file content, so a change made to an owned file before the claim lands when a credited commit later touches that file. Then correct the three sentences above.

## Issue 2 (minor): the "every owned_files list is empty" note can never print

Reason 4 of `planning_lane_scope._why_unscoped` (`every planning work package's owned_files list is empty`) is printed only through `_with_attribution_hint`, and only when `PlanningLaneNote.explains` is true.

Why it is never true:
- A planning lane's `write_scope` is the union of its work packages' `owned_files` (`lanes/compute.py`, around lines 1254-1263).
- So when every list is empty, `_note_patterns` is `()`, and `_note_commits` returns `frozenset()` (`if not patterns: return frozenset()`).
- `explains` is then always False. `test_a_note_with_no_patterns_explains_no_path` pins exactly that.

The note is computed and then never shown, in the one shape it describes.

Fix: with no patterns, let `_note_commits` return the walk's non-bookkeeping commits (`pin..coordination base`), so a commit of that walk explains the note. Alternatively, drop reason 4 and say why. Add a test through `_with_attribution_hint` for a lane with empty `write_scope` and empty `owned_files`.

## Not findings (for the record)

- **Printed reopen command.** Driven from `for_review` and `in_review` (`r9probe/out/`): it succeeds without `--force`. `done` cannot be reached before landing (`Cannot move WP02 to done without verified merge ancestry`), so that word in the text is harmless.
- **"Move to planned twice".** This follows directly from FR-021: a review rejection to `planned` keeps the cycle, so an old opener whose commit cannot be proven survives it. The text explains that. See the report for a follow-up suggestion.
- **Merges in a normal default Mission.** The Mission branch of this very Mission has 0 merges on 637 first-parent commits. Planning work is committed in the coordination worktree. Lane auto-rebase merges and `implement`'s Mission-branch merges are on lane branches. So `--no-merges` does not affect a normal Mission.
- **`orchestrator-api-contract.md:364`.** It still lists only the finalize-tasks cause for `EVIDENCE_WINDOW_UNCOMPUTABLE`. It is outside WP05's owned files. Track it as a follow-up.
