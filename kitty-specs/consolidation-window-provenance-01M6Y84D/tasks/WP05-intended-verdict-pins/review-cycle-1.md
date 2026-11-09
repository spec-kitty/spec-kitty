---
affected_files: []
cycle_number: 1
mission_slug: consolidation-window-provenance-01M6Y84D
reproduction_command:
reviewed_at: '2026-11-09T02:27:19Z'
reviewer_agent: claude:claude-opus-5-5:reviewer-renata
wp_id: WP05
---

# WP05 review, cycle 1 (reviewer-renata, claude-opus-5-5)

Verdict: **changes requested** (one blocking pin-soundness defect, one small docstring addition). Everything else verified sound; see "Verified" below so the next cycle does not redo it.

## Issue 1 (blocking): pin (b) cannot fail on the cell's distinguishing claim

`test_window_refusal_names_commit_and_preceding_wp` asserts `_assert_refused_naming(result, stray[:7], "WP01")`. Cell (b) (NFR-002, FR-007) is the refusal text naming the commit **and the work package approved before it**. The lanes renderer (`approved_bound._moved_finding`) prints every work package of the lane: `branch '…' (lane-a carries WP01, WP02) holds content committed after …`. So a WP19 that reuses `check_lane`'s whole-lane `wp_ids` for the window refusal (the most likely mis-implementation) satisfies the `"WP01"` needle and XPASS-flips (b) without naming the preceding work package. Today the pin also fails only for (a)'s reason (exit 0), so (b) adds nothing beyond (a) plus the short SHA.

Fix: make the work-package needle discriminate. Assert that the refusal attributes X to WP01 and does **not** attribute it to WP02, for example: take the output line (finding) that contains `stray[:7]`, assert `WP01` is in it and `WP02` is not. Do not couple to wording beyond what FR-007 fixes. Re-check with `--runxfail` that it still fails today on an `AssertionError` (it will: exit 0), and that it would hold under the intended render (`write_branch_bound._preceding_wp` yields `wp_ids=(preceding,)`, i.e. `(lane-a carries WP01)` on the finding line; the recovery block's per-WP commands sit on other lines).

## Issue 2 (please do in this cycle, small): (g) docstring covers only one of the two routes

The (g) docstring argues unreachability for the route "the fully-canceled lane C itself advances (D on C), and a carrier merges D". It does not cover the second route the WP02 reviewer raised and WP18 T094 plans: **C's own approved dependency lane A advances after the kill and reaches C's commits** (A merges C's tip). That is the only place a frozen anchor touches C at all: `_fully_canceled_lane_own_commits` computes C's own commits via `lane_own_commits(…, _closed_world_anchors(C))`, whose anchors are A's **live branch name** plus the target base. Add one paragraph with the reason from the (g) ruling below, so the pin's docstring is the complete record WP18 converts.

## (g) ruling (binding for WP18 T094 / T096; orchestrator adjudication requested in the review brief)

**Record unreachable; do not reshape (g) into an xfail.** Read from the code (no prototyping):

- C is never an anchor (`_closed_world_anchors` drops fully-canceled dependency lanes) and has no frozen tip (`_capture_pre_interrupt_lane_tips` skips fully-canceled lanes). The one frozen read that can change C's judgement is A's tip as C's own anchor.
- WP02-reviewer shape (advance A with D, then merge C's tip into A): C's commits and D reach A **after A's approval stamp**. A fully-canceled lane contributes no approval-stamp anchor and no closed-world anchor, so `check_lane` on A refuses them (`LANE_MOVED_AFTER_APPROVAL`, claim time) with live and frozen anchors alike: A's own anchors (its dependencies, target base, stamps) did not move. That refusal stops the claim before the gate-time `CANCELED_REACHABLE_VIA_DEPENDENCY` content axis, which is the only consumer of C's own-commit set that a frozen anchor would change. With the merge commit (A advanced first), C's commits are not on A's first-parent spine, so A is not even a carrier (`_carrier_spines`). With a fast-forward variant (merge C first, then D), A is a carrier, but the claim-time canceled-dependency refusals (unstamped / unattributable) do not fire on a stamped modern Mission. Either way the verdict (exit 1, `LANE_MOVED_AFTER_APPROVAL` on A naming C's commits and D) is identical before and after FR-015. No flip.
- The only verdict-level flip needs A **re-approved over C's merged commits** after the kill. Then the live read empties C's own commits (A reaches them), so the canceled content is carried by A unchecked, and a **fresh run on the same final state does the same**. Pinning the frozen resume as stricter than a fresh run on identical state encodes no intended verdict. It points at a pre-existing fresh-run gap outside FR-015: a fully-canceled lane merged into its approved dependency lane, then re-approved, hides its commits from `lane_own_commits`. Recommended follow-up: file an issue (needs confirmation by a red test). Do not pin it in this Mission.
- WP18: T094 takes the documented unreachable branch: `test_resume_fully_canceled_lane_flip_is_unreachable` asserts the reachable consequence for the T094 shape (resume refuses `LANE_MOVED_AFTER_APPROVAL` on A naming C's commit(s) and D, identical before and after the fix), with the reason above in its docstring and the tracer. Keep WP05's consequence test.
- Spec: NFR-002 (g) already allows "a cell recording that the flip is unreachable, with the reason", so **no wording change is required**. Optional for WP21: "a dependency-lane advance" is ambiguous between "C as a dependency lane" and "C's own dependency lane"; naming both routes would remove the ambiguity.

## Verified (no action)

- `-rxX`: 11 XFAIL, 0 XPASS, 2 passed (control, (g)).
- `--runxfail`: every pin fails on its verdict assertion, none on a fixture: (a), (a mixed), (b), (c)×2, WW-6 `the run must refuse, it exited 0`; (d) at the claim-probe message (today the walk records `src/pkg/wp01.py` as a deletion, the gate FAILs it unattributable and rolls back); (e)/(f) `lane-b carries WP0x` missing (today only lane-a is refused); (h1) the forecast lacks `canceled WP02 cannot be attributed`; (h2) the forecast passed `kitty/mission-terminus-01M6Y2S1`, not a SHA.
- Precondition rule: on a throwaway copy, breaking a `require` in a fixture gives ERROR at setup and in a body gives FAILED, never XFAIL (copy deleted, tree clean).
- (d) fake is scoped to `(touch_sha, P)`: the gate reads `blob_id_at(target_ref, P)` (line 1370; never touch_sha) and `blob_id_at(contribution.lane_commit, P)` (line 1596, only for two-lane `multi_lane_paths`, and `wp01.py` is lane-a's alone). Today's failure is the unattributable-blob FAIL, not a probe REFUSE, which proves the fake fired only in `_final_authored_walk`.
- (e)/(f) flip together: both consumers read `_closed_world_anchors` (live dependency-lane names), as the (e) docstring says.
- (h) fixtures are sound: (h1) an unstamped canceled WP gives a fresh-run claim-time refusal the dry-run reports once it gets the excluded set (#6771 claim build); (h2) observes `coord_base_ref` through the family patch (phase_claim/forecast bindings included), the documented fallback when no visible verdict difference exists.
- Gates: ruff, ruff format, mypy clean; characterization + single-rollback-authority 31 passed; `make test-fast` 2921 passed, 6 skipped. No production code changed (single file).
- Shared-file note: WP18 (T09x) moves the (e)/(f)/(g) fixture builders out of this file into `resume_frozen_anchors_support.py`; WP16/17/19/20 remove markers here.
