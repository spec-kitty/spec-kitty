---
affected_files: []
cycle_number: 1
mission_slug: approval-honesty-01M78J9S
reproduction_command:
reviewed_at: '2026-11-13T07:47:46Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review (reviewer-renata) — changes requested

## Blocking

### B1. `has_unaccounted_verdict` is broader than the ambiguity it addresses (#7571 / FR-008 / FR-014 regress on post-fix logs)

`find_adoptable_review_cycle` returns `none` whenever **any** verdict anywhere in the
work package's history names no review cycle. After this WP, a **forced approval writes no cycle
by design** (FR-006) and records `force-override`. `has_unaccounted_verdict` counts that event
as unaccounted. As a result, every work package that has ever had a forced approval loses
adoption and the `REVIEW_CYCLE_NOT_ADOPTABLE` refusal for the rest of its life.

Reproduction (pure, tip `08ee8918`). The events are: claim; forced approval
(`review_ref`/`review_result.reference` = `force-override`); a rejection referencing
`review-cycle://m/WP01-core/review-cycle-1.md`; a new claim. Files: `review-cycle-1.md` and
`review-cycle-2.md`, both by the reviewer of record.
- `has_unaccounted_verdict` returns `True`, and the probe returns `none`. The approval then
  writes `review-cycle-3.md`: one review, two cycles (#7571 again). A non-adoptable cycle 2
  would also be silently doubled instead of refused (FR-014).
- Control (the same log without the forced approval): the probe returns `adopt`.

This affects orchestrated Missions, which force-approve routinely. The `adoption_rule` decision
has no legacy carve-out at all, so the carve-out must be as narrow as the ambiguity.

**Required fix (small).** Cycle numbers are allocated `max(existing) + 1`
(`ReviewCycleArtifact.next_cycle_number`). Any cycle that an unaccounted verdict wrote **before**
an event that references a higher-numbered cycle is therefore numbered at or below the floor, so it
is never a candidate. Only an unaccounted verdict **after** the last cycle-referencing event can
leave an unreferenced cycle above the floor. Restrict `has_unaccounted_verdict` (or the probe's use
of it) to verdict events after the newest event that references a cycle (equivalently, after the
event that sets the floor).

Tests to add:
- unit: a forced approval, then a rejection with a pointer, then a claim; an own post-claim cycle is
  adopted, and an other-identity cycle refuses `REVIEW_CYCLE_NOT_ADOPTABLE`;
- unit: the existing legacy cases (an unaccounted verdict as the latest verdict) still adopt and
  refuse nothing;
- a self-mutation check: moving the unaccounted verdict before or after the floor event flips the
  answer.

## Non-blocking (route to WP04 or a follow-up; no change required here)

- **N1 (item 3a). Legacy logs and the FR-010 pre-claim leg.** The citation verifier does not use
  the legacy carve-out: `--note "cycle 4 APPROVE"` with no cycle 4 still refuses on a legacy log
  (probed). Good. However, on a legacy log an old cycle that is unreferenced and predates the claim
  (`cycle 1`, another identity) **is accepted** as a citation. Its age is judged only by
  references, which the legacy approval never recorded. The approval then writes cycle 2, and the
  note cites cycle 1. This is an inherent limit (no timestamps, per R5). WP04 should document it as a
  residual.
- **N2 (item 5). JSON `code` field.** A non-owned `ActionContextError` renders `{"error": "<CODE>: ..."}`
  with no `code` field. That is true for `REVIEW_NOT_INDEPENDENT`, `APPROVER_NOT_CLAIMANT` and
  `REVIEW_SLOT_DAMAGED` alike, and the shape is pinned exactly by
  `test_owned_checkout_move_task.py::test_context_error_envelope_is_opt_in`. The new codes are
  consistent with that. Ruling: WP04 corrects the wording of `contracts/move-task-approval.md`
  ("leads the `error` text; a `code` field only under `--owned-checkout`"). Do not change the
  handler in WP03.
- **N3 (item 6). Stale docstring.** `src/kernel/__init__.py:19` still lists `format_stamp`. Fold
  the one-word docstring fix into WP04, which already carries the changelog fragment, rather than
  bumping the version for prose here.

## Verified OK

- Red-first: `8cb857b4` is test-only, and its tree is base plus tests: 74 failed, 5 passed. At the
  tip: 158 passed (new tests plus WP01/WP02).
- Real-CLI probes (subprocess) all pass:
  - adoption (cycle 1, no cycle 2, pointer reference);
  - none: one cycle;
  - missing citation via note, pointer and ref-text: refused, byte-identical;
  - not-adoptable, raw and other-identity: refused, naming the file and the route;
  - feedback file;
  - forced approved and done: no cycle, `force-override`, JSON and event agree;
  - `--agent codex --profile reviewer-renata`: body, `reviewer_agent` and repro command all name
    `codex::reviewer-renata`, with no `approval:` token.
- `excluded_cycle_numbers`: removing the filter turns `test_stale_cycle_is_not_adopted` red.
  Correct and tested.
- `format_stamp` removal is behaviour-identical (its body was `value.strftime(fmt)`). The
  synthetic mints are deleted; the prefixes and classifiers are kept.
- Re-pins are stale under FR-006 and the honest body; none is weakened. The xfail removal is
  correct.
- Citations are found by listing (glob) the read-candidate dirs, with no user-text path join.
  `test_untrusted_path_containment` is green.
- ruff, format and mypy are clean; C901 is OK; `_do_move_task` is untouched; no forbidden files;
  leeway is recorded in the commits.
