---
affected_files: []
cycle_number: 5
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T11:21:24Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review 5 (reviewer-renata): changes requested

R1, the per-WP window and the `keep` walk are implemented as claimed. The blast list is green: 6744 passed, 4 skipped, 11 xfailed, 0 failed. ruff, `ruff format --check --force-exclude`, mypy and C901 are clean, and no suppressions were added. Every mutation I made turned a test red (listed at the end). Two findings remain, both about R2 and the remedy. A third item is a nit.

## Issue 1 (should fix, R2 gap): window membership credits commits that do not descend from the claim

`src/specify_cli/consolidation/reconciliation_authorship.py`, `_planning_scope`: `frozenset(commits_in_range(repo_root, starts[wp], coord_base_ref))`, which is `git rev-list <claim>..<coord base>`.

That range holds every commit the claim cannot reach, not only the commits made after the claim. The Mission branch can bring in the claim commit through a merge, for example a `git pull` in a second clone. When it does, the spine commits on the other side of that merge are in the window, although they do not descend from the claim.

I reproduced this with a scratch probe that is not committed:
- the Mission branch forks at P;
- the side branch holds the claim commit C;
- the Mission branch commits E, which changes `curation/pkg/early.py`, then merges the side branch (M), then commits L.

With WP02 owning `curation/pkg/**` and its start at C, E is in `claim.shas`, and `curation/pkg/early.py` is in `claim.blobs`. Ruling R2 says the credit runs from the WP's own claim point.

**Fix:** use `git rev-list --ancestry-path <claim>..<coord base>`, which keeps only descendants of the claim (E is dropped; M and L stay). As an alternative, fail closed when the claim commit is not on the walk's first-parent spine. Add an integration test of this merge shape next to `test_an_owned_change_made_before_the_claim_is_not_credited_one_after_it_is`. If you choose a residual instead of a fix, the operator must agree to it, and you must record it in the module docstring, the migration doc and the ADR wording.

## Issue 2 (should fix, remedy text is not true for a common case)

The remedy in `docs/migrations/planning-lane-write-branch.md`, `docs/changelog/unreleased/7860.fixed.md`, the module docstring and `adr-wording-c4.md` reads: "take every planning work package to `approved` (a canceled one leaves `canceled` only with `--force`)". I drove it end to end through the real CLI. I used a scratch copy of the shape-B fixture, with WP04 as a second planning WP that is canceled. Results:

- **Canceled WP04 that was never claimed** (a dropped WP, the common case). The first `consolidate` fails with "file 'curation/apply_curation.py' ... belongs to NO approved WP", and the branches roll back cleanly. Next I ran `move-task WP04 --to approved --force`. `accept` then refuses `EVIDENCE_WINDOW_UNCOMPUTABLE` ("no window-opening (claim) status event is recorded for WP04"). `consolidate --attest-no-implementation WP04` refuses with "lifts IMPLEMENTATION_MISSING only ... (EVIDENCE_WINDOW_UNCOMPUTABLE) ... Nothing was recorded." **The documented remedy does not work.** This path has to go through `--force` to `planned`, a claim through `spec-kitty agent action implement` (whose claim commit lands on the Mission branch), `for_review`, an independent review and approval, and then `--attest-no-implementation` if WP04 owes no work. I did not run that longer path. Please verify it before you document it.
- **Canceled WP04 that was claimed first.** The first `consolidate` refuses at claim time on the mixed-lane rule (the `--attest-canceled-superseded` recovery). Next I ran `move-task WP04 --to approved --force`. `accept` then refuses `IMPLEMENTATION_MISSING`, and `consolidate --attest-no-implementation WP04 --attest-reason ...` **lands** (exit 0, the reconciliation is verified). The remedy works here, but it also needs `--attest-no-implementation`, which the text does not mention.

**Fix:** state both cases truthfully in the four places. For a never-claimed WP: claim it through `implement`, get it reviewed and approved, and attest no implementation if it owes none. For a claimed WP: force it to approved, then `--attest-no-implementation` when it owes no work. The phrase "commit the missing claim on the Mission branch" in the migration doc should instead name the command that makes that commit (`spec-kitty agent action implement`), as `PLANNING_WINDOW_RECOVERY` does.

For the operator (a report, not a design request): under R1, a Mission whose planning lane holds a dropped, never-claimed WP cannot consolidate until that WP goes through a full claim and review cycle. The refusal the operator sees is the generic un-attributable FAIL, which suggests `--dependency-ref` and names neither the planning lane nor the canceled WP. Only the docs explain the cause.

## Issue 3 (nit): no fast test pins the claim's event-reader wiring

Removing `events=event_log.read` from `reconciliation_claim._build_claim` leaves `test_planning_lane_authorship_7860.py` and `test_planning_evidence_callers_7860.py` green. Only the slow shape-B end-to-end test fails (because the autouse fixture stubs `_planning_window_starts`). Add a fast test that `build_approved_wp_set` hands `_collect_authored` a non-`None` reader, or one that runs the real `_planning_window_starts` with real claim events.

## Checked and fine

- R1 reads `_is_approved_wp` on the claim's own `materialize_snapshot` map, the same fold the claim uses. No attestation is read. The no-status-row case is covered.
- The event reader is the claim's single `_ClaimEventLog`, cached and shared with `evaluate_evidence`. The window start is the same `planning_evidence_window` decision the evidence axis uses. A rejection back to `planned` keeps the original opener (`window_opener_events(cycle=True)`), so a re-claimed WP keeps its first claim as the start, consistent with the evidence axis.
- `keep` is checked after `seen_paths.add`, so an older credited commit never stands in for a rejected newer one. Probe: a commit before WP03's claim, then WP03's credited change, then a mixed commit in both windows. The result is correct.
- Rename out of scope (probe): the rename commit is not whole, the owned deletion is credited, and the new path is left un-attributable. Fail closed.
- The unkeyed `_final_authored_walk` calls in `_collect_authored` run for code lanes only. The planning lane reuses the keyed `full_blobs`.
- The dead code removal preserves behaviour (the guards only concerned non-approved WPs, which R1 now excludes entirely). `test_no_dead_symbols` is green. `globs_overlap` is still used.
- The 1200-line trim touched only the planning hunks. I found no unrelated docstring cut.
- The ADR wording cases 1-5 match the code (normalisation, the two-segment rule, all-empty, an unprovable start or an unreadable window).

## Mutations (each temporary and reverted, tree clean)

- R1 `all` over the first WP only: red.
- `keep` before `seen_paths.add`: red.
- `whole` ignoring credit: red.
- Window from the pin instead of the claim: red.
- Unreadable ownership tolerated: red.
- `events=` dropped from the claim: red only in the slow end-to-end test (issue 3).
