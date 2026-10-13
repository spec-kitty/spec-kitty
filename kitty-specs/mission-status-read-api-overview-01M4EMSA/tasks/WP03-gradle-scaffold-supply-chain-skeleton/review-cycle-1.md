---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T12:51:58Z'
reviewer_agent: reviewer-renata
wp_id: WP03
---

# WP03 review cycle 1: REJECT (reviewer-renata)

Full evidence: wp03-review-verdict.md in the orchestrator scratchpad. Everything checked is green except the findings below. Fix all three in this round.

| id | severity | file | problem | remedy |
|---|---|---|---|---|
| F1 | medium | tests/ci/test_mission_status_api_build.py (`_RULE`, `EXPECTED_RULES`, `jacoco_violations`, about lines 293-301) | The three minimums and patterns are pinned, but `element = "CLASS"` is not. Replacing it with `"BUNDLE"`, or deleting the line (JaCoCo's default is BUNDLE), leaves `jacoco_violations()` empty. The operator ruled on 2026-10-11 that per-class floors stay (reviews/analyze.ruling.md), so this pin is required. | Capture `element` in `_RULE`, add `"CLASS"` to each `EXPECTED_RULES` tuple, and add revert rows for "element set to BUNDLE" and "element line removed", each of which must produce a violation. |
| F2 | low | services/mission-status-api/build.gradle.kts (`openApiGenerate`, about lines 67-69) | `openApiGenerate` stays UP-TO-DATE after a referenced (non-root) schema file is edited, or after `-PcontractRoot` points elsewhere. | Declare the contract root directory as a task input (`inputs.dir(contractRoot)` or the equivalent), and show that an edit to a referenced schema re-runs the task without `--rerun-tasks`. |
| F3 | info | tests/ci/test_mission_status_api_build.py (verification-metadata pin, about lines 659-670) | The pin checks strict mode and the sha256 count only. An added md5/sha1 entry, or an artifact name with an OS/arch classifier, would pass. | Pin "sha256 only" and "no OS/arch classifier artifact names", with a revert row for each. |
