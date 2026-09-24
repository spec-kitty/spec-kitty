# Mission Retrospective — terminus-integrity-followups (Epic #5001)

## Outcome
Follow-up to PR #5012 (the reconciliation-gate spine). **8 of 9 in-scope children genuinely closed** — #5013 (P0 default-squash content axis), #4945/#4977/#4981 (default flow, integrity-gate level), #4970 (surface-write), #4985/#4991 (resume target authority), #4982 (resume lane-tip SHA preservation). **PR #5020** (stacked on #5012). Honest residuals: **#4997** (staged-deletion/`LOCAL_CHANGES` behind-HEAD window — a distinct window from #4982, strict xfail) and **#5021** (new: mid-teardown false-FAIL, fails-closed + 3-way merge-resolution attribution). Epic #5001 stays open. No green-washing: the honest 8/9 (+ 1 strict xfail) is the mission's integrity, not a fake 9/9.

## Approach (what worked)
- **Research/grounding squad first** (3 lenses, file:line) corrected TWO brief premises against the live base before any code: the vacuous-manifest hoist and `pre_mutation_target_sha` persistence had already landed in #5012, narrowing the work honestly.
- **Four adversarial squad passes each earned their tokens.** Post-plan caught real decomposition leaks (strategy-persist WP04↔WP05 coupling; test-file ownership) AND the fail-open corners F1/F2/F7 + the F5 superseded-blob false-PASS + the F3/F9 resume re-poison — all BEFORE code. Post-tasks caught the red-isolation gap + the marker-removal ownership self-contradiction. Pre-merge (mandatory) confirmed the load-bearing **deviation-3** (does the squash axis ATTRIBUTE in production, or defer like the harness?) resolves to ATTRIBUTE via two real tests, cleared WP02's shared-helper widening as strictly-more-correct, and found the two hygiene folds (mypy-strict + honest squash message). None visible to single-pass review.
- **Conflict-safe WP decomposition**: `executor.py` single-owned (WP05); the 4 parallel WPs were file-disjoint and ran clean. WP05's dependency lanes auto-consolidated cleanly on 4.0.0rc5.
- **Red-first, mock-free, honest xfail throughout.** #4982's green was proven real (pre-interrupt commit objects are ancestors of target — a squash would mint new SHAs); #4997 stays RED as the discrimination proof.

## Tooling friction (tracer — HIGH SIGNAL)
Milder than #5012 (the terminus/lane machinery this epic hardens fought the operator less on 4.0.0rc5), but recurring points:
1. **CLI-on-PATH sibling-checkout staleness.** `spec-kitty` on PATH ran from a sibling WIP checkout without the #5012 spine; mitigated by driving EVERYTHING through `.venv/bin/spec-kitty` + `.venv/bin/python -m pytest` (this tree's code). This must be re-checked every session.
2. **Review-cycle-artifact commits block the next transition.** Each `move-task` review write drops an untracked `kitty-specs/.../tasks/WP##-.../review-cycle-N.md` that the NEXT approval gate refuses as "uncommitted owned file" — a per-transition commit dance. Also a leftover from the PRIOR mission blocked `record-analysis` (dirty-worktree guard).
3. **Cross-WP test-signature drift caught only at integration.** WP01 changed `plant_canceled_commit` to a 3-tuple; WP05's test (developed in a lane without WP01's change) unpacked 2 → `ValueError` surfaced ONLY in the combined blast-radius run, not any per-lane run. The lesson: shared-harness signature changes need a contract or the harness WP integrated first.
4. **`make test-fast` unusable offline.** Its `uv run --frozen` env-sync step times out against the private artifactory; the identical pytest run against the built `.venv` is the honest equivalent. Every make target that syncs is blocked in this network-restricted environment.
5. **`spec-kitty merge` avoided** for consolidation (per #5012's lesson); manual soft-reset-to-fork + regroup into 6 per-area commits, byte-identical-guarded, worked cleanly again.

## Design decisions (tracer)
- WS1: blob-attribution against the **FINAL** first-parent authored blob per (lane, path) — union-of-all admits superseded intermediate blobs (F5). NOT patch-id-of-squash (opaque aggregate) or lane-tip replay (carrier tip contains smuggled content).
- WS2: mirror the C-1 target-authority precedence for strategy; persist coord base symmetrically to `pre_mutation_target_sha` (read-persisted-first, F3/F9); per-lane tip as a CAS expectation that ACCEPTS behind-HEAD (the #4982 window) and refuses only true divergence; H4 gated on `completed_wps` (a consolidated-but-baseless state is impossible post-fix, persist-before-mutate).
- WS3: committed-content probe via placement authority / `git ls-tree` (path-drift safe); NO blanket `terminus_write` flip; the `_mission_meta_exists`→`read_primary_meta` widening is a latent-bug fix (meta.json is PRIMARY-only).
- Fail-closed everywhere: probe error / None base / unreadable git / absent anchor ⇒ REFUSE, never vacuous PASS.

## If done again
- Land + integrate the shared test-harness WP (WP01) BEFORE the WPs that reuse its fixtures write their own tests, or pin a harness-signature contract — the WP01→WP05 `plant_canceled_commit` drift would have been caught earlier.
- The review-cycle-artifact commit dance is worth a DX fix (auto-commit the review artifact as part of `move-task`, or exempt it from the next gate's cleanliness check).
