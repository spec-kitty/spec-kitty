---
affected_files: []
cycle_number: 1
mission_slug: org-drg-fragment-pack-root-01M66YJG
reproduction_command:
reviewed_at: '2026-10-30T18:23:19Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review — org-drg-fragment-pack-root-01M66YJG

Reviewed head: 2003b6f394 (WP01 only).

## Anti-pattern checklist

1. Dead code — **PASS**: `find_body_path_escapes` / `find_asset_path_escapes` /
   `OrgPackRootUnavailableError` each have a live non-test caller
   (`src/charter/activation/drg_activation.py` wrappers, via `charter.drg`).
2. Synthetic-fixture test — **PASS**: the new tests call `load_org_pack` and the real
   predicates (no literal fragment dicts), and each has a same-fixture positive control.
3. Silent empty return — **PASS**: the only new failure path raises
   `OrgPackRootUnavailableError`; there is no fallback root.
4. FR coverage — **PASS** for FR-001, FR-002, FR-003, FR-007, NFR-003.
5. Frozen surface — **PASS**: no `packs/` or baseline file touched.
6. Locked decision — **PASS**: fragment-only predicates, no serialized field, no protocol
   (DM `01M66YN5CCFXQF4DBWDSVNSJBG`).
7. Shared-file ownership — **PASS**: the one out-of-map edit
   (`tests/architectural/test_charter_facades_reexport_offering.py`) is a required
   identity-contract row, recorded in the WP history.
8. Production fragility — **PASS**: the new `raise` is the documented fail-loud contract
   for a fragment that cannot supply its root.

## Findings

**F1 — BLOCKING (deliverability, not a defect in the code).** WP01 is not independently
deliverable. At this head the two activation wrappers still call the old two-argument
form, so `doctor charter-packs` reports `org-layer body_path check failed:
find_body_path_escapes() takes 1 positional argument but 2 were given` for every project
with org packs, and `tests/charter_offering/drg/test_org_pack_node_inference.py::test_artifact_reaches_doctor_and_only_its_scoped_action`
fails in both parametrizations. The split between WP01 and WP02 draws the WP boundary
through a single atomic refactor.

**Required rework.** Fold WP02 into WP01: one `code_change` work package that carries the
root, collapses both predicates, deletes the activation wrappers and `_org_pack_roots_by_name`,
and re-points both doctor halves onto the `charter.drg` facade — with the registry read
counted at exactly one. Keep the existing commit (offering-layer slice) and add the
doctor/activation slice as a second commit; the two stay readable as slices of one WP.
The tasks.md `WP02` row and `tasks/WP02-doctor-single-authority.md` move into WP01
(T007–T012 keep their ids).

Everything else in this head is good and should be preserved.
