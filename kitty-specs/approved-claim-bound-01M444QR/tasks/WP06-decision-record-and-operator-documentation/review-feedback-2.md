# WP06 review feedback 2

Verdict: changes requested. One clause in the `AGENTS.md` paragraph states the dependency-lane tip anchor wrongly and contradicts the corrected ADR. The ADR rework is accepted in full: all seven cycle-1 items are true against lane-g. Gates are green. Code references are lane-g paths under `src/specify_cli/`.

## Required

1. **`AGENTS.md`: "and a dependency-lane tip anchor behaves the same way" is false as written.**
   The sentence it closes says that lane A no longer refuses. A dependency-lane tip is an anchor only for the lane that DEPENDS on it: `_closed_world_anchors(lanes_manifest, lane, ...)` returns the tips of `lane`'s own dependencies (`consolidation/reconciliation.py:1946-1949`), and `_approved_bound_verdict` builds that list per lane (`:1822`). Lane A's tip is therefore an anchor in lane B's check, never in lane A's check. With only that anchor, the post-approval commit is exempt on lane B and lane A still refuses (`consolidation/approved_bound.py:267-270`). Only the approval-stamp anchors are shared by every lane (`reconciliation.py:1773-1776`, `:1803`). The ADR says this correctly ("for a lane that depends on lane A; lane A itself is still checked against its own stamps in the same run"), so the two documents now disagree.
   Replace
   > ..., lane A no longer refuses, and a dependency-lane tip anchor behaves the same way; this is deliberate and changed one verdict compared with the first implementation.

   with
   > ..., lane A no longer refuses. A dependency-lane tip anchor exempts that commit only on the lane that depends on lane A; lane A itself is still checked against its own stamps. This is deliberate (content inside an approval stamp was in a reviewed tip), and a fresh run can give a different verdict than the first implementation of this rule did.

   The replacement also drops "changed one verdict", which names a count the reader cannot check.

## LOW (closeout, not blocking)

- `AGENTS.md`: "It is accepted only for a WP in the approved claim unless its newest approval is a review approval that carries a stamp" is true but "only ... unless" reads badly. The ADR's form is clearer: "accepted only for a WP in the approved claim whose newest approval is not a stamped review approval".
- `reconciliation.py:1845` docstring names "the resume path" as a caller of `approved_bound_refusal`; only `orchestrator_api/consolidation.py:457` calls it. Code comment, outside this WP.

## Cycle-1 items, checked against lane-g

1. ADR example: TRUE. `approval_stamp_anchors` (`reconciliation.py:1773-1776`) feeds every lane's `anchors` (`:1822`); `check_lane` exempts `claim_base..anchor` (`approved_bound.py:267-268`, `wp_attribution.py:591-594`). `AGENTS.md`: see Required 1.
2. Claim-time location: TRUE. `build_approved_wp_set` calls `_approved_bound_verdict`; exit at `phase_claim.py:497-499` before the snapshot at `:503`; `approved_bound_refusal` called only at `orchestrator_api/consolidation.py:457`.
3. Hollow-review wording: TRUE. `preflight.py:535-536` skips the attestation; threshold 2 at `:635`; attestation not discounted (`:586`).
4. Claim-time row: TRUE. `executor.py:303-314`, `phase_claim.py:542-546`.
5. Attestation acceptance: TRUE. `approved_attestation.py:95-105`, repeat rule `:177`.
6. Claim-base fallback: TRUE. `reconciliation.py:1754-1762`.
7. Gate references: TRUE. `phase_claim.py:507-524`, `reconciliation.py:1899-1900`.

Changelog entries: still consistent with the corrected ADR. ADR is one Divio type, `updated: '2026-10-05'`. No em dashes or filler in the added lines.

## Gates (lane-f)

- `check_docs_freshness.py --ci`: errors=0 (16 warnings, link health and help drift, not from this WP).
- `docs_index.py --strict`: drift=False.
- pytest (4 files): 250 passed, 1 failed; the failure names only `src/specify_cli/orchestrator_api/consolidation.py:76,430`. No docs file.
- Hygiene: rework touches only `AGENTS.md` and the ADR; trailers correct; working tree clean.
