---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T12:22:27Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review (cycle 1): changes requested

Reviewer: reviewer-renata. The content and the tests are otherwise approvable. One blocking item remains: a gate goes red, and the WP neither declares that red nor explains it.

## Blocking

1. **The provenance ratchet goes red because of this WP.**
   - Test: `tests/architectural/test_builtin_pack_provenance_ratchet.py::test_builtin_pack_residue_baseline_is_tight` fails in the lane:
     ```
     procedures/mission-tracer-files.procedure.yaml: provenance baseline 1, live 0
     ```
   - Cause: T019 removed the tracer procedure's styleguide `reason` text ("... authored by WP08 of mission doctrine-catfooding-2196-01KWE16N"). That text was the file's only provenance residue.
   - The ratchet requires lowering the baseline in the same change (NFR-002). WP02 did this for its own files.
   - This test is not on the `Expected-red-until-WP09` list, and it is not a regeneration artifact.
   - **Fix:** in `tests/architectural/_builtin_pack_provenance_baseline.yaml`, delete the `provenance: 1` line under `procedures/mission-tracer-files.procedure.yaml`. Keep `repo_paths: 1` if that count is still live. Re-run the ratchet file until it is green.
   - The baseline file is outside `owned_files`, so add the one-line out-of-map rationale to the Activity Log.

## Verified (no action needed)

- Red→green: at fcdb1813, 26 failed and 4 passed. At head, the owner test and the lens guard give 35 passed.
- Detectors are non-vacuous:
  - The point-cut detector flags both the fixture and the real pre-change SKILL.md.
  - The headcount detector flags `bounded (3-4)`, `3-4 distinct lenses`, `three to four` and `exactly five`.
- Casting mutations are killed:
  - Debbie moved to post-plan: killed.
  - Paula dropped from escalation: killed.
  - A `researcher-ryan` line parses but does not resolve.
- The broad doctrine `-k` run gives 1193 passed and 3 skipped.
- Everything loads through DoctrineService, and the styleguide is gone.

## Non-blocking (optional, same pass)

- **Negative control only half exercised.** `test_casting_table_negative_control_rejects_researcher_ryan` only asserts `repo.get("researcher-ryan") is None`. It never runs the parser, so it does not check that "a line casting researcher-ryan fails" (FR-004). Consider feeding a mutated casting line through `_parse_casting_block` and then the resolver.
- **Word-range pattern has no positive control.** The headcount positive control covers only digit ranges. Consider adding `"three to four"` so the word-range regex cannot rot silently.
- **Direction of the rewritten comment.** In `acceptance-criteria-non-vacuity`, the comment now reads `adversarial-squad-deployment -> brownfield-onboarding`. The actual reference edge runs brownfield → procedure. Please check the arrow direction.
- **Handoff to WP09 is missing an edge.** The handoff should name the curated edge `extractor.py:~535` (`DIRECTIVE_052 -> styleguide:adversarial-squad-cadence`, SUGGESTS) explicitly as "retarget to procedure:adversarial-squad-deployment" (FR-008). Also name `tests/doctrine/fixtures/content-manifest.json`.
- **Deferral wording is narrower than the contract copies.** The `deferred_with_rationale` wording ("an issue or umbrella ticket") is narrower than the per-mission contract copies, which also accept a Non-Goal as the tracking location. Consider "e.g. a Non-Goal or follow-up issue".
