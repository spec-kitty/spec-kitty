# Design decisions

Append-only notes for mission `approved-claim-bound-01M444QR`.

- 2026-10-04 (plan): refuse rather than drop the later commit (research.md R-1).
- 2026-10-04 (plan): the attestation is read by the same function as a real approval, so no voiding rule exists (R-6).
- 2026-10-04 (plan): on a mixed lane a canceled work package's latest stamp is a covered point, so existing closed-world verdicts are unchanged (R-4).
- 2026-10-04 (WP02): about thirty existing tests moved a lane after the fixture approved it; they were fixed with one restamp helper, not by weakening the rule.
- 2026-10-05 (WP04): a repeat attestation re-records only while the lane has not moved past the earlier one; the hollow-review check skips attestation events.
- 2026-10-05 (WP07): the check measures from the pre-mutation target tip, and other lanes' approval stamps are anchors; the mission branch is no longer a reference. Consequence: a commit inside another lane's approval stamp is not refused on its own lane.
- 2026-10-05 (WP07): orchestrator-api contract 1.10.0 for `data.preflight_error_code`.
