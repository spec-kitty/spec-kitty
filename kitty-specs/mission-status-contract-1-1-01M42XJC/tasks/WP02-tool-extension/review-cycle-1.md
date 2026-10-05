---
affected_files: []
cycle_number: 1
mission_slug: mission-status-contract-1-1-01M42XJC
reproduction_command:
reviewed_at: '2026-10-04T13:14:05Z'
reviewer_agent: claude
wp_id: WP02
---

VERDICT: rejected

F1 (severity 3): OD-4 weakens leak detection through an embedded newline in an artifact-path value.
Plant (temp, removed): `path: |-` block scalar, or `path: "a\n<real home path>/x"`; likewise `path: "a\n<address>"`.
Result: leak_scan reports nothing. The text pass masks the whole scalar span, and malformed_artifact_path has no newline/control-character reason.
Before WP02 this was reported as HOST_PATH/EMAIL. Fix: reject any control char/newline in malformed_artifact_path
(or mask only single-line scalars / scan multi-line values unmasked), plus a red-first test.

Checked OK:
- Home path and email in a non-path field, in a path field's neighbour, in x-source/x-derived path, in a trailing comment: all reported.
- Credential inside a path value: SECRET reported (text and structured).
- Home path at path start: ARTIFACT_PATH_MALFORMED (absolute).
- Legit `@`, space, accent, `home/<x>/` segment inside a path value: pass.
- Mask covers only the scalar span of path/artifactPath, not under x-source/x-derived. leak_scan --root contracts exits 0.
- Seven reverts, all red in pytest, all restored:
  - swap trailing_slash/empty_segment
  - mask ignoring x-source
  - secrets read from the masked line
  - credential check dropped
  - old-kind output changed (digest pin red)
  - legit `@` name dropped
  - artifactPath key dropped
- Note: the swap-order revert is caught only by pytest; the manifest cannot see reason order (all report one code). Acceptable.
- run_negative_cases: 126 cases; 93 ran, 33 skipped (jvm/vacuum/oasdiff tags, all pre-existing); all 25 new cases ran, plant and control passed.
- Diff aef7cc967..HEAD touches exactly the six owned files; ruff format --check . clean (3103 files), nothing else reformatted.
- Gates: four targeted modules 205 passed; corpus "corpus and not windows_ci" 3423 passed; ruff check (TID251 included) clean; mypy --strict contracts/tools/*.py clean; cutover_guard(base_ref=aef7cc967) passes.
Lane clean (git status empty).
