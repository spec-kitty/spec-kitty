---
work_package_id: WP01
title: Deploy the doc-kitty build with a post-deploy smoketest
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-002
- C-004
planning_base_branch: issue-6938-docsite-cutover
merge_target_branch: issue-6938-docsite-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6938-docsite-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6938-docsite-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Cutover
history:
- at: '2026-11-11T16:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/docs-pages.yml
- .github/workflows/docs-site-build.yml
- .github/workflows/ci-router.yml
- tests/release/test_release_ci_ownership.py
- tests/ci/test_nightly_tooling_cache.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Deploy the doc-kitty build with a post-deploy smoketest

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- A push to `main` of the core repository runs `pages` → `build` (the shared `docs-site-build.yml`, `pages-artifact: true`) → `deploy` → `smoketest`, all succeeding (SC-001).
- A failed `build` skips `deploy` and `smoketest`; a failed `deploy` or `smoketest` leaves the run red (SC-002).
- No `deploy` or `smoketest` on a fork or off `main` (SC-003).
- The canary jobs and the `canary` dispatch input are gone (FR-006).
- Workflow default `contents: read`; `pages: read` on `pages`; `contents: read` on `build` and `smoketest`; `pages: write` + `id-token: write` on `deploy` only (NFR-001). New action references SHA-pinned (NFR-002). `smoketest` `timeout-minutes` ≤ 60 (NFR-004).

## Context & Constraints

- Spec: `kitty-specs/docsite-cutover-01M75N3E/spec.md`; plan: `plan.md` (Design section: job graph, decisions); data model: `data-model.md`.
- ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-11, D-12, D-13 and Amendment 2026-11-11.
- #7484: behaviour is tested by evaluating the real `if:` conditions (`tests/ci/_gh_expr.py`) inside the `_schedule` job model in `tests/release/test_release_ci_ownership.py`; never restate YAML text for behaviour. Shape facts (pins, permissions, the probe command) may be read from the parsed YAML.
- C-002: never dispatch a workflow or deploy. C-004: keep the fork guard (`tests/ci/test_fork_guard.py` must stay green unchanged) and update the ownership test without loosening it.
- Do NOT delete DocFX sources (`docs/docfx.json`, `toc.yml`, template, `scripts/docs/*` DocFX scripts); the revert of this PR is the rollback.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-6938-docsite-cutover
- **Merge target branch**: issue-6938-docsite-cutover

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first job-graph tests

- **Purpose**: pin the cutover's behaviour before changing the workflow.
- **Steps**: in `tests/release/test_release_ci_ownership.py`, replace the canary section and the DocFX-era asserts of `test_docs_pages_deploys_only_from_promotion_repo_and_fails_transient_setup_errors` with:
  - the pages probe asserts kept verbatim (probe-then-configure, 200/404/other semantics);
  - `_schedule` without the `canary` input (an `inputs.*` reference must now be an assertion failure: drop it from the context);
  - push and plain dispatch on `main`: `pages`, `build`, `deploy`, `smoketest` all succeed, and `smoketest` has `deploy` and `build` as ancestors, `deploy` has `build`;
  - `build` fails → `deploy` and `smoketest` skipped;
  - `deploy` fails → `smoketest` skipped and the run has a failure; `smoketest` fails → the run has a failure (nothing swallows it);
  - fork (`push` and `workflow_dispatch`) and a topic ref: `deploy` and `smoketest` skipped; a fork `push` also skips `pages`;
  - `build` calls `./.github/workflows/docs-site-build.yml` with `{pages-artifact: true}` and no other name (default `github-pages`), and `deploy` uses the pinned `actions/deploy-pages` with no `artifact_name` override;
  - permissions as in the objectives, and the workflow default is `{contents: read}`;
  - the smoketest runs `python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai` after a pinned checkout (`persist-credentials: false`), with no `|| true` / `continue-on-error`, `timeout-minutes` ≤ 60;
  - no job named `canary-*` and no `workflow_dispatch` inputs;
  - the push path filter covers every path of the `docs_site` group in `ci-router.yml` except `ci-router.yml` itself, plus `docs-pages.yml` (read the group from the parsed router YAML, do not restate it).
- Run them against the unchanged workflow and confirm they fail (record the count).

### Subtask T002 – Switch the deploy

- **Files**: `.github/workflows/docs-pages.yml`.
- Workflow `permissions: contents: read`; keep `concurrency` (`pages`, no cancel) and its comment.
- `pages`: unchanged steps and `if:`; add job `permissions: pages: read`.
- `build`: `needs: [pages]`, same `if:` as today, `permissions: contents: read`, `uses: ./.github/workflows/docs-site-build.yml`, `with: {pages-artifact: true}`. Remove the DocFX steps.
- `deploy`: `needs: [build]`, `if: github.repository == 'spec-kitty/spec-kitty' && github.ref == 'refs/heads/main' && needs.build.result == 'success'`, `permissions: pages: write, id-token: write`, environment `github-pages`, step `actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1`.
- Push `paths`: the shared build's inputs (the router's `docs_site` group without `ci-router.yml`) plus `.github/workflows/docs-pages.yml`.
- Header comment: the cutover (#6938, D-13 step 3), the rollback (revert restores DocFX), the fork guard.

### Subtask T003 – Smoketest job

- `smoketest`: `runs-on: ubuntu-24.04`, `needs: [deploy]`, `if:` repository + `refs/heads/main` + `needs.deploy.result == 'success'`, `timeout-minutes: 60`, `permissions: contents: read`; steps: pinned checkout `08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0` with `persist-credentials: false`, then `python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai` with `PYTHONPATH: .:src`. Comment: #2361, no alert issue (operator decision), red run is the signal.

### Subtask T004 – Canary retired; comments

- Remove `canary-build`, `canary-deploy`, `canary-probe` and the `workflow_dispatch.inputs.canary` block (keep `workflow_dispatch:`).
- `docs-site-build.yml` header "Callers" and the `pages-artifact-name` description: the deploy calls it with the default name; drop canary wording. The input itself stays.
- `ci-router.yml` `docs-site` comment: the Pages deploy calls the shared build since the cutover (#6938).

### Subtask T005 – DocFX deploy-job tests

- `tests/ci/test_nightly_tooling_cache.py`: remove `test_docs_pages_pins_docfx_and_caches_the_versioned_tool` and `test_docs_pages_caches_the_checksum_verified_plantuml_jar` (their subject, the DocFX build job, is gone; the revert restores both). In `test_router_docs_tests_restore_and_save_the_plantuml_jar_before_running` replace the comparison with the deleted step by a module constant holding the key (`plantuml-jar-${{ runner.os }}-${{ hashFiles('scripts/docs/plantuml_pins.json') }}`). Keep `test_docs_pages_push_trigger_is_main_only_where_the_deploy_runs`. Update the module docstring.

### Subtask T006 – Verify

```bash
uv run --frozen pytest tests/release/test_release_ci_ownership.py tests/ci/test_fork_guard.py tests/ci/test_docs_site_job.py tests/ci/test_nightly_tooling_cache.py tests/docs/test_site_live_probe.py --tb=line -q
uv run --frozen pytest tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_retirement_scrub.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_no_legacy_terminology.py --tb=line -q
uv run --frozen ruff check <touched .py>; uv run --frozen ruff format --check --force-exclude <touched .py>
uv run --frozen mypy --strict <touched test files>
actionlint .github/workflows/docs-pages.yml .github/workflows/docs-site-build.yml .github/workflows/ci-router.yml
```

## Test Strategy

Red first (T001) against the unchanged workflow, green after T002–T004. No skip, no xfail.

## Risks & Mitigations

- `pages: read` may be insufficient for the probe (research R-5): failure mode is a red run with nothing deployed; the reviewer should weigh it.
- A path filter narrower than the build's inputs would leave the live site stale: the superset test prevents it.

## Review Guidance

- Confirm each behaviour test evaluates the real `if:` (no YAML-text restatement for behaviour).
- Confirm nothing deploys after a failed build, from a fork or off `main`, and that the smoketest cannot be swallowed.
- Confirm no DocFX source was deleted.

## Progress & Status

Progress lives in `status.events.jsonl`. Use `spec-kitty agent tasks add-history`, `move-task` and `status`.
