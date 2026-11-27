---
affected_files: []
cycle_number: 6
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T12:52:35Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review 6 (reviewer-renata): changes requested

The cycle-5 fold is mostly right. The ancestry-path window drops the reviewer's merge shape. The R1 remedies are true for the three canceled cases the implementer drove end to end. The note is wired through the claim and the forecast. Ruling R1 (any non-approved planning WP voids the lane, and no attestation lifts that) and ruling R2 (each approved WP is credited from its own claim, for its own owned_files) are implemented as ruled. The two-literal-segment breadth rule moved unchanged.

Four findings remain. Two are should-fix, and they are one R2 leak and one remedy that cannot be run as printed. Two are small. Nits follow.

## Issue 1 (should fix, R2 leak): a merge that resolves a conflict in an owned path is credited, and it can carry pre-claim content

`reconciliation_authorship._scoped_commits` and `_lane_final_walk` read a merge commit's paths through `changed_paths_of`. That is `git show --name-only`, a combined diff, and it is empty only for a clean merge. A merge that resolved a conflict lists the resolved path. `--ancestry-path <claim>..<coord base>` keeps that merge, because it descends from the claim. So when the path is owned, the merge enters `claim.shas` and its blob enters `claim.blobs`.

I reproduced this with a scratch probe, which is not committed and was removed afterwards:
- the side branch holds the claim commit C, then an owned change `S = 1` to `curation/pkg/x.py`;
- the Mission branch commits `E = 1  # pre-claim` to the same file before it merges the side branch;
- the merge conflicts and is resolved to keep both lines.

With WP02 owning `curation/pkg/**`, starting at C, the result was:
- `MERGE_IN_SHAS True`;
- `EARLY_IN_SHAS False`;
- the merged blob, which holds E's pre-claim line, is in `claim.blobs` (`MERGED_BLOB_CREDITED True`).

So E's change, made before the claim reached the Mission branch, lands through the resolution as approved authorship. This is the shape ruling R2 excludes.

The docs say the opposite. "The merge commit itself credits nothing" or "A merge commit changes no path of its own on the walk, so it credits nothing" appears in:
- the module docstring;
- `docs/migrations/planning-lane-write-branch.md`;
- `adr-wording-c5.md`;
- the docstring of `test_a_change_the_claim_does_not_reach_across_a_merge_is_not_credited`.

**Fix:** let no merge commit credit anything on the planning walk. Make `_PlanningScope.owns` / `at` (or `_scoped_commits` and the `keep` predicate) return False for a merge commit (`is_merge_commit`). A resolved path then reads as seen and is recorded nowhere, so the gate fails closed. As an alternative, judge it the way the verifier does (`merge_own_changed_paths`), but crediting the whole resolution is the leak itself. Add a test with this conflict-resolution shape next to the ancestry-path test. If you choose a residual instead of a fix, the operator must agree to it, and you must state it in all four places.

## Issue 2 (should fix, remedy cannot be run as printed): "claim commit cannot be found" tells the operator to run `implement` on an approved WP

`planning_lane_scope._why_unscoped` reaches its "cannot be proven" branch only after R1 passed, so every WP of the lane is approved there. It then prints `PLANNING_WINDOW_RECOVERY[EVIDENCE_WINDOW_UNCOMPUTABLE]`, which says to claim the WP through `spec-kitty agent action implement`. But `implement` refuses an approved WP (#7754). `lanes/stale_check._reopen_step` exists for exactly this reason at `consolidate`: it reopens the WP first with `move-task --to planned --review-feedback-file`, which costs a re-review.

The same unrunnable step is in:
- the migration doc ("a claim commit that cannot be found: claim the work package through `spec-kitty agent action implement <WP>`");
- `7860.fixed.md` ("a claim commit that cannot be found is made with `spec-kitty agent action implement <WP>`");
- `adr-wording-c5.md`, line 17.

The fold says every remedy was driven end to end. This one was not: `r6probe/out/` covers only the canceled cases.

There is a second doubt. Review 5 confirmed that a rejection back to `planned` keeps the original window opener (`window_opener_events(cycle=True)`). After a reopen, the new `implement` claim may therefore not become the window start, and the start would stay unprovable.

**Fix:** drive this case end to end. An approved planning WP whose claim event is not committed on the Mission branch is enough, for example a WP claimed before the upgrade. Then print and document the sequence that actually lands, including the reopen step and its re-review cost. If no CLI sequence lands, say so and name the escalation. Do not print `implement` alone.

## Issue 3 (should fix, small): a note can name the planning lane on a FAIL that the planning lane did not cause

`planning_lane_notes` is keyed only on "this planning lane's scope is empty". `_with_attribution_hint` prints every note on every un-attributable FAIL, whichever lane the un-attributable commits or paths come from.

Take a Mission whose dropped planning WP owns nothing that was committed, and whose other planning commits are all bookkeeping. If a code lane then fails on un-attributable content, the FAIL tells the operator that the planning lane credits nothing, and it prints the forced claim, forced approve and attestation recipe. That recipe does not touch the actual cause. It also records three forced operator acts for nothing.

The fold says "a note never disagrees with the verdict". It agrees only with the lane's scope decision, not with the cause of the FAIL.

**Fix:** print a planning lane's note only when an un-attributable commit is on that lane's Mission-branch walk, or when an un-attributable path matches one of the lane's owned_files or the lane's write_scope. As an alternative, word it as a possible cause ("The planning lane ... also credits nothing ...") and leave the remedy out unless it applies. Add a test where a code lane's stray content fails while the planning lane is empty, and assert what is printed.

## Issue 4 (should fix, small): new test file is not mypy-clean on its own

`mypy tests/consolidation/test_planning_lane_notes_7860.py` reports:

```
tests/consolidation/test_planning_lane_notes_7860.py:78: error: Returning Any from function declared to return "tuple[str, ...]"  [no-any-return]
```

The fold report says mypy is clean on new and changed code. This file is new in `dd49b424`. Fix it with a typed local, as `reconciliation_verifier` does for `patch_id_of`. Do not suppress it.

## Nits

- **N1.** The note's remedy commands use a `<WP>` placeholder and carry no `--mission`, although the note already knows the WP ids and the Mission slug. The approved-bound and stale-lane recovery blocks print commands that run as written, with the slug. Substitute the canceled WP ids and `--mission <slug>`.
- **N2.** The remedy for a dropped WP does not say that `--to claimed --force` and `--to approved --force` are forced operator transitions recorded in the status log, and that the attestation records why the WP owes no work. The ADR wording says this (line 19), but the printed note and the migration doc do not. One clause is enough.
- **N3.** In the note, "no attestation lifts this" is followed by a remedy that uses `--attest-no-implementation`. Say which check the attestation answers ("the evidence check's `IMPLEMENTATION_MISSING`"), so the two sentences do not read as contradicting each other.
- **N4 (campsite, optional).** `tests/consolidation/test_git_probes_seam.py:100` (`_FakeConsole` passed as `Console`) is pre-existing. It also fails at `dd49b424^` in a multi-file mypy run. This fold edited the file, so a one-line `cast`, or typing the helper to a `Protocol`, would clear it. The other mypy error, the Any return in `reconciliation_verifier.py`, is pre-existing at `dd49b424^` (two errors there, lines 531 and 901) and is not WP05's.

## Checked and fine

- `commits_on_ancestry_path` raises `GitProbeError` on a git error. `_planning_scope` turns that into "no scope" (fail closed). The ancestry path excludes the claim commit itself, as the old range did.
- When the claim is not an ancestor of the coordination base, `--ancestry-path` returns nothing, so the WP is credited nothing (fail closed). The start comes from the commit that introduced the claim on the Mission branch, so in practice it is an ancestor.
- A criss-cross merge needs nothing new beyond issue 1: ancestry is a plain DAG property.
- `ApprovedWpCommitSet.planning_lane_notes` is appended last with a default, so positional constructions are unchanged. It is not added to the `--dry-run --json` keys or to the orchestrator-api envelope. It changes only the hint text of an un-attributable FAIL (and the forecast message that embeds it). With a declared `--dependency-ref` and no notes, the hint stays `None`, as before.
- The note's reason order matches `_planning_scope`'s decision order: R1, then unreadable, then broad, then unprovable start, then all-empty, then unreadable window.
- The forced claim, approve and attest path credits only the WP's own owned_files, after its own claim commit. It never credits content the WP did not own. Planning lanes have no approval stamp, so a forced approval is the documented residual, unchanged.
- The three canceled remedies match `r6probe/out/` (claimed, then canceled: exit 0; never claimed, without implement and with implement: exit 0; `--to planned` refused for `canceled`).

## Tests and mutations (reviewer)

- Blast list (WP05 test files, `tests/integration/test_7860_*.py`, consolidation, terminus, lanes, ownership, mission_runtime, orchestrator_api, the move-task 7860 test, and four architectural gates): **7146 passed, 4 skipped, 11 xfailed, 0 failed**.
- ruff, `ruff format --check --force-exclude` and C901 are clean on the 11 changed files. No suppressions were added.
- mypy: see issue 4 and N4.
- Mutations, each temporary and reverted, tree clean afterwards:
  - the unreadable-ownership reason of the note skipped: red;
  - the `--ancestry-path` flag dropped: red.
