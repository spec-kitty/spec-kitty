---
affected_files: []
cycle_number: 1
mission_slug: approved-claim-bound-01M444QR
reproduction_command:
reviewed_at: '2026-10-04T23:48:09Z'
reviewer_agent: claude-reviewer
wp_id: WP06
---

# WP06 review feedback 1

Verdict: changes requested. One required consequence is missing and four statements are imprecise against the final code in lane-g. Everything else in the three documents was checked sentence by sentence against lane-g and is true. Gates are green. Code references are lane-g paths under `src/specify_cli/`.

## Required

1. **Missing: a commit reachable from another lane's approval stamp, or from a dependency-lane tip, is not refused on this lane.** (ADR "The lane check"; `AGENTS.md` paragraph.)
   The ADR lists "every bounded lane's approval stamps" as anchors and stops there. The consequence is not stated anywhere.
   Code: `consolidation/reconciliation.py:1773-1776` (`approval_stamp_anchors` collects the stamps of ALL bounded lanes), `:1803` and `:1822` (they are passed as anchors to every lane), `consolidation/approved_bound.py:267-268` (every commit in `claim_base..anchor` is exempt). Dependency-lane anchors are live branch names: `reconciliation.py:1946-1949`.
   Add to the ADR, after the anchor list, wording such as:
   > Because every bounded lane's approval stamps are anchors, a commit that review approved as part of another lane is not refused on the lane it was first made on. Example: a commit is added to lane A after WP01 was approved. Lane B merges lane A. WP02 on lane B is sent back, reworked and approved again, so its new approval stamp reaches that commit. Lane A is then no longer refused: the commit is inside what review approved for lane B. The dependency-lane tip anchor has the same property for a lane that depends on lane A; lane A itself is still checked against its own stamps in the same run. This is deliberate. It also means a fresh run can give a different verdict than the first implementation of this rule did.
   Add one sentence with the same fact to the `AGENTS.md` paragraph, after the anchor list.

2. **Imprecise: where the claim-time check runs.** (`AGENTS.md`: "It runs at claim time through `reconciliation.approved_bound_refusal`".)
   `consolidate` does not call `approved_bound_refusal`. The claim builder `build_approved_wp_set` calls `_approved_bound_verdict` (`reconciliation.py:1473-1486`), after the mixed-lane resolution, and the refusal exits through `claim_integrity_refusal` in `phase_claim.py:497-500`, before the snapshot at `:504`. `approved_bound_refusal` (`reconciliation.py:1834`) is the public entry that only `orchestrator-api consolidate-mission` calls (`orchestrator_api/consolidation.py:457`).
   Corrected: "It runs at claim time inside `reconciliation.build_approved_wp_set` (`_approved_bound_verdict`, after the mixed-lane resolution, before the snapshot, so nothing is rolled back); ... and in `orchestrator-api consolidate-mission` (`_refuse_post_approval_lane_content`, which calls `reconciliation.approved_bound_refusal` before its first lane is consolidated)".

3. **Imprecise: "The hollow-review warning is unaffected by it".** (ADR Attestation, last bullet; `AGENTS.md` same sentence.)
   Two different things are true. The attestation is never read as the approving review: `consolidation/preflight.py:535-536` skips it when looking for the approving actor. But the attestation is a forced transition (`approved_attestation.py:240`), it raises the work package's forced-transition count, that count is the warning's input with a threshold of 2 (`preflight.py:630-635`), and the attestation is not among the discounted forced transitions (`preflight.py:566-597`). So an attestation can make the warning appear.
   Corrected: "It is not a review. The hollow-review warning never reads it as the approving review, and each attestation adds one to the work package's forced-transition count, which that warning counts."

4. **Imprecise: "Nothing has moved, so there is nothing to roll back."** (ADR "Where it runs" table, row 1.)
   True for branches and worktrees. A requested attestation is recorded in the status log before the claim is built (`executor.py:305-314`), and the refusal text says so (`phase_claim.py:542-546`).
   Corrected: "No branch or worktree has moved, so there is nothing to roll back. An attestation requested on the same command is already recorded in the status log."

5. **Imprecise: when an attestation is accepted.** (ADR Attestation, second bullet; `AGENTS.md` "accepted only for a WP in the approved claim whose newest approval carries no stamp".)
   The request is refused only when the newest approval is a REVIEW approval that carries a stamp (`approved_attestation.py:95-105`). A newest approval that is an earlier attestation passes this test, stamped or not, and then falls under the repeat rule (`:177`). As written, the second bullet contradicts the fourth.
   Corrected: "It is accepted only for a work package in the approved claim whose newest approval is not a stamped review approval: an approval with no stamp, or an earlier attestation (see the repeat rule below)."

## Optional (accuracy, not blocking on their own)

6. ADR "The claim base is the target branch's tip as it was before the run mutated anything": when that SHA does not resolve, the base falls back to the coordination base reference (`reconciliation.py:1754-1762`). One clause is enough.
7. ADR gate row: the SHAs the re-check excludes are the validated lane tips plus the mission branch, the target and the coordination base as resolved at claim time (`phase_claim.py:507-524`). Naming them makes "The live mission branch is not a reference" exact: its claim-time SHA is one, its live name is not.

## Checked and correct (no change)

The three codes and the printed recovery command; which event supplies the stamp, `approved -> done` never read, migration events skipped; covered points including the canceled work package's newest STAMPED event; merge and bookkeeping-only commits dropped; full range, not first-parent; the anchor list; the empty-lane exemption and its FR-005 note; orchestrator-api `PREFLIGHT_FAILED` + `data.preflight_error_code`, contract 1.10.0, no gate re-check; what the gate re-check adds (the plain case is not claimed as closed); attestation never lifts a post-approval-commit refusal; the repeat rule; mixed-lane precedence; both reversed decisions and the forward-only 3.x note; every residual (the resume/mission-branch hole is described as fixed, not as a residual); the 4.0.0rc5 boundary; both changelog entries.

## Gates (lane-f)

- `check_docs_freshness.py --ci`: errors=0 (4 pre-existing HELP-DRIFT warnings, not from this WP).
- `tests/docs/test_changelog_style.py tests/docs/test_sync_changelog.py tests/architectural/test_docs_cli_reference_parity.py`: 155 passed.
- `docs_index.py --strict`: drift=False; working tree clean.
- `test_no_legacy_terminology.py`: 1 failed, names only `src/specify_cli/orchestrator_api/consolidation.py:76,430` (already reworded in lane-g). No docs file.
- Hygiene: 7 files, all docs, `AGENTS.md` and the two generated indexes; trailers correct; no em dashes or filler in added lines.
