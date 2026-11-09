---
affected_files: []
cycle_number: 1
mission_slug: docsite-shared-build-01M70V33
reproduction_command:
reviewed_at: '2026-11-09T19:43:21Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP01
---

# WP01 review (reviewer-renata, claude-reviewer)

The implementation is correct. No blocking defects in the workflows:
- The 6 build steps in `docs-site-build.yml` `build` equal the old inline `docs-site` steps; the only changes are the `if:` on `Upload the built site` and the new Pages upload. `runs-on` and `timeout-minutes` are unchanged.
- `docs-pages.yml` and `scripts/ci/router_gate.py` are untouched. `ADVISORY_JOB_NAMES` is empty, `router-gate.needs` still lists `docs-site`, and there is no `continue-on-error`.
- `upload-pages-artifact@fc324d35…` equals `refs/tags/v5.0.0` (git ls-remote). The caller workflow's `permissions: contents: read` is inherited, and the called workflow declares the same.
- Red to green is verified: 776896b14 gives 10 failed / 33 passed; HEAD gives 200 passed across the four target modules.

The rejection is for one required change: test trimming (operator decision, issue #7484).

**Issue 1 (required): remove the tests that only restate the workflow YAML; keep the tests that guard a lasting invariant.** In `tests/ci/test_docs_site_job.py`:

KEEP:
- The `.github/workflows/docs-site-build.yml` case in `test_a_docs_or_site_change_selects_the_job`. It runs `gate_selection`, so editing the shared build must trigger the gate.
- The re-pointed `test_every_action_is_pinned_by_commit` / `test_a_tag_pinned_action_is_caught`, `test_the_job_uses_no_credential` / `test_a_token_in_the_job_is_caught`, `test_no_step_swallows_a_failure`, `test_the_job_installs_frozen_and_checks_the_contract` and the astro-config scan of the shared file. These are supply-chain and no-swallow invariants, and each has a mutant.
- `test_the_called_build_row_blocks_the_gate`. It runs `scripts/ci/router_gate.py` on the real `<caller> / <callee>` row name.
- The security half of `test_the_shared_definition_is_only_callable`: the trigger set is `{workflow_call}` only, there is no `secrets`, and `permissions == {contents: read}`. These prevent a fork or secret exposure and widened token scope. Keep `permissions` asserted in one place only; it is now asserted both here and in `test_the_job_uses_no_credential`.
- From `test_the_router_job_only_calls_the_shared_definition`, keep only `job["uses"] == SHARED_REF`, folded into a helper or the credential test. It is the anchor that keeps the re-pointed step checks non-vacuous: they must read the file the router actually calls.

DROP:
- The `pages-artifact` input `type`/`default`/name assertions in `test_the_shared_definition_is_only_callable`. They restate the YAML.
- `"steps" not in job` and `PAGES_INPUT not in with` in `test_the_router_job_only_calls_the_shared_definition`. Once `uses:` is pinned these restate the YAML: Actions rejects `uses` alongside `steps`.
- `test_the_build_job_carries_the_build`. `name`/`runs-on`/`timeout` restate the YAML. The command and non-vacuity checks are duplicates: `test_the_job_installs_frozen_and_checks_the_contract` already asserts the same three commands, and `test_no_step_swallows_a_failure` asserts that `steps` is non-empty.
- `test_the_deploy_can_reuse_the_build_with_a_pages_artifact`. It restates the two `if:` strings for a caller that does not exist yet. #6938's deploy is the real proof.
- `test_a_green_called_build_row_does_not_mask_another_failure`. It duplicates `test_a_green_docs_site_row_passes_beside_another_failure_row`: router_gate blocks the `ruff` failure regardless of the docs row's name.

After trimming, re-run `tests/ci/test_docs_site_job.py` and the other three target modules, and record the counts with `add-history`.

**Issue 2 (advisory, low): actionlint was not available in the review container.** The YAML parses and the row-name assumption is consistent with GitHub's `<caller> / <callee>` naming. The PR's real CI run is the end-to-end proof that the row appears and is classified, so confirm it in the PR's Tests run section.
