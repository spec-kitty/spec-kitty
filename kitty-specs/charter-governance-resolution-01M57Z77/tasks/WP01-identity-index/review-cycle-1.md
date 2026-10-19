---
affected_files: []
cycle_number: 1
mission_slug: charter-governance-resolution-01M57Z77
reproduction_command:
reviewed_at: '2026-10-18T19:24:09Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback (reviewer-renata), cycle 1

Verified good: snapshot 941964531 regenerates identically on the merge-base src (the test passes there, and pytest imports the base `src/`). Red commit ec6eaf400 fails on base src (collection ImportError, plus `test_resolve_artifact_urn_accepts_declared_id_for_non_directive_kind`). The API covers declared_id, selection_id, stem, knows, source_layer, resolve_many and activation_id. Precedence, collision and anti_pattern behave as specified. The scan probe runs through the module attribute and asserts more than 0 scans. `identity_index.py` does not import resolver or profile_resolution, directly or transitively. The api re-export gate is updated. ruff, format and `mypy --strict` are clean, and C901 is within 15. tests/charter/: 3890 passed. Both hotpath reds also fail on base src, so they are pre-existing.

## Issue 1 (blocking): not every activatable kind is tested
The done criteria say the index is unit-tested for **every activatable kind**. The Review Guidance says to "parametrise over `ArtifactKind` members with `activatable == True`, skipping file-less kinds explicitly". `tests/charter/activation/test_identity_index.py:21-30` (`_STEM_NE_ID`) hardcodes 7 kinds and silently omits `mission_step_contract`, `glossary_pack` and `skill`. All three are activatable and have glob patterns. A manual probe shows they resolve correctly today, so only the tests need to change:
- Derive the kind list from `[k for k in ArtifactKind if k.activatable]`.
- Add stem ≠ id fixtures (org and project layers) for the three missing kinds.
- Skip `anti_pattern` explicitly with a reason (it is covered by the passthrough test).
- Add a guard assertion that the parametrised set equals the activatable set minus the explicit skips, so that a future kind cannot be silently uncovered.

## Issue 2 (needs a disposition): T005 asked for a declared-id activation test
T005 asks to "confirm `charter activate tactic <declared-id>` writes the **stem** (add a test)". `tests/specify_cli/cli/commands/charter/test_activate_declared_id_writes_stem.py` instead tests activation **by stem**. Despite its name, it never activates by declared id. The implementer reports that declared-id activation is still rejected, and no later WP (WP02, WP03, WP06 or WP10) owns it. Pick one:
- (a) Pin the gap with a strict `xfail` test that names a tracker issue, and file that issue.
- (b) Record an explicit hand-off note in the WP history naming the owning WP.

Also rename the file or test so the name matches what it asserts.
