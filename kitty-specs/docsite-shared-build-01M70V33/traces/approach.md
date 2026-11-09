# Approach trace: docsite-shared-build-01M70V33

Append-only, newest last.

- 2026-11-09 — Initial: extract the `docs-site` job's steps into a reusable workflow before #6932–#6936 add gates (resliced plan, operator-approved), red-first acceptance tests then the extraction, one WP.
- 2026-11-09 — **Changed after the operator's #7484 ruling:** the red-first acceptance tests that only restated the workflow YAML (no-inline-steps, input type/default, carries-the-build, deploy-reuse shape, a duplicate green-row test) were dropped in review cycle 1. Kept: the call target the step checks follow, the security surface, the called-row-blocks-router-gate test, the routing case and the re-pointed hygiene checks with their mutants. The PR's real CI run, and #6938's first deploy, are the evidence for the rest.
