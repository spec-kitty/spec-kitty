---
work_package_id: WP01
title: Shared docs-site build workflow
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
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6937-docs-site-shared-build
merge_target_branch: issue-6937-docs-site-shared-build
branch_strategy: Planning artifacts for this mission were generated on issue-6937-docs-site-shared-build. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6937-docs-site-shared-build unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Extraction and deploy reuse
history:
- at: '2026-11-09T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent:
- .github/workflows/docs-site-build.yml
- docs/changelog/unreleased/6937-docs-site-shared-build.internal.md
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/docs-site-build.yml
- .github/workflows/ci-router.yml
- tests/ci/test_docs_site_job.py
- tests/release/ci_retirement_scrub.json
- docs/changelog/unreleased/6937-docs-site-shared-build.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared docs-site build workflow

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- `.github/workflows/docs-site-build.yml` exists, triggers only on `workflow_call`, and holds the build: contract check, pnpm/node setup, frozen install, build, upload (FR-001).
- The router's `docs-site` job has no `steps`; it is `uses: ./.github/workflows/docs-site-build.yml` with the same key, display name `docs site (doc-kitty build)`, `needs: [changes]`, `if:` and a place in `router-gate.needs` (FR-002, FR-003).
- Input `pages-artifact` (boolean, default `false`) swaps the plain upload for `actions/upload-pages-artifact` of `site/dist` (FR-005); the router call does not set it.
- Every step-level check in `tests/ci/test_docs_site_job.py` reads the called job, keeps its mutant, and the module asserts the called job really carries the build steps (FR-004, SC-003).
- The new workflow is in the `docs_site` path group and its scrub copy (FR-006).
- NFR-001 (no credential, `contents: read`), NFR-002 (commit pins), NFR-003 (timeout ≤ 20 min).

## Context & Constraints

- Spec: `kitty-specs/docsite-shared-build-01M70V33/spec.md`; plan, research, data model, quickstart beside it; grounding in `research/code-grounding.md`.
- ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-11, D-12.
- Charter `.kittify/charter/charter.md`: ATDD/red-first, non-vacuous gates (SO#5), no new gates or allowlists.
- Do NOT edit `.github/workflows/docs-pages.yml` (C-002). Do NOT add any gate of #6932–#6936 (C-004).
- Precedent for reusable workflows: `.github/workflows/module-tests.yml`, called from `ci-modules.yml:429`.
- `scripts/ci/router_gate.py:111-127` classifies every jobs-API row of the run by display name; a called job's row is `<caller name> / <callee name>`.

## Branch Strategy

- **Strategy**: set by finalize-tasks
- **Planning base branch**: `issue-6937-docs-site-shared-build`
- **Merge target branch**: `issue-6937-docs-site-shared-build`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement with: `spec-kitty agent action implement WP01 --agent claude --mission docsite-shared-build-01M70V33`

## Subtasks & Detailed Guidance

### Subtask T001 – Commit the failing acceptance tests (red)

- **Purpose**: ATDD red-first: prove the tests fail on the base for the right reason, on their own commit.
- **Steps** (in `tests/ci/test_docs_site_job.py`):
  1. Add `SHARED = ROOT / ".github" / "workflows" / "docs-site-build.yml"` and helpers `_shared()` (parsed YAML) and `_build_job()` (its single job, key `build`).
  2. `test_the_router_job_only_calls_the_shared_definition`: `_job()` has no `steps` and `_job()["uses"] == "./.github/workflows/docs-site-build.yml"`; `with` is absent or does not set `pages-artifact`.
  3. `test_the_shared_definition_is_only_callable`: the triggers (YAML `on`/`True` key) are exactly `{"workflow_call"}`; inputs are exactly `{"pages-artifact"}`, `type: boolean`, `default: false`; no `secrets` declared; top-level `permissions == {"contents": "read"}`.
  4. `test_the_build_job_carries_the_build`: `_build_job()` has `runs-on`, `timeout-minutes <= 20`, and its `run` text holds `site_contract --check`, `pnpm install --frozen-lockfile`, `pnpm run build`.
  5. `test_the_deploy_can_reuse_the_build_with_a_pages_artifact` (deploy reuse, SC-004): exactly two upload steps; the `actions/upload-artifact@<sha>` step has `if: ${{ !inputs.pages-artifact }}` (or the equivalent `!inputs.pages-artifact`) and `path: site/dist`; the `actions/upload-pages-artifact@<sha>` step has `if: ${{ inputs.pages-artifact }}` and `path: site/dist`. Evaluate the `if`s with `tests/ci/_gh_if.eval_gh_if` if it supports `inputs.*`, otherwise compare the normalized expression strings.
  6. `test_the_called_job_row_blocks_the_gate` (parametrize failure/timed_out/cancelled/""): row name `f"{_job()['name']} / {_build_job()['name']}"` → `router_gate.main()` blocks; plus a green row beside a red `ruff` row still blocks.
  7. Add the path to the routing test's parametrize list: `.github/workflows/docs-site-build.yml` selects `docs-site`.
  8. Run `uv run --frozen pytest tests/ci/test_docs_site_job.py` and record the red result (expected: the new tests fail because the file does not exist / the job has steps). Commit only the test file: `test(ci): pin the shared docs-site build definition (red)`.
- **Files**: `tests/ci/test_docs_site_job.py`.

### Subtask T002 – Create the reusable workflow

- **Steps**: create `.github/workflows/docs-site-build.yml`:
  - header comment: #6937, ADR D-11, callers (router `docs-site` now, Pages deploy at #6938), "pinned by tests/ci/test_docs_site_job.py".
  - `name: docs site build (shared)`; `on: workflow_call: inputs: pages-artifact: {description, type: boolean, default: false, required: false}`.
  - `permissions: contents: read`.
  - `jobs: build: name: build, runs-on: ubuntu-24.04, timeout-minutes: 20, steps:` — move the six existing steps verbatim (same SHAs, same comments), then two uploads:
    - `Upload the built site` (`actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1`), `if: ${{ !inputs.pages-artifact }}`, same `with:` as today.
    - `Upload the built site as the Pages artifact` (`actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0`), `if: ${{ inputs.pages-artifact }}`, `with: path: site/dist`.
- **Notes**: no `concurrency`, no secrets, no `services` (that is #6936).

### Subtask T003 – Router call and path group

- **Steps** in `.github/workflows/ci-router.yml`:
  - Replace the job body (`runs-on`, `timeout-minutes`, `steps`) with `permissions: contents: read` (optional; workflow default already is) and `uses: ./.github/workflows/docs-site-build.yml`. Keep `name`, `needs`, `if`.
  - Update the header comment: the build lives in `docs-site-build.yml`; its row reads `docs site (doc-kitty build) / build`; the deploy will call it at #6938.
  - Add `'.github/workflows/docs-site-build.yml'` to the `docs_site` filter (`:455-460`) and update its comment.
- **Validation**: `uv run --frozen python -c "import yaml;yaml.safe_load(open('.github/workflows/ci-router.yml'))"`; `actionlint` if available.

### Subtask T004 – Re-point the step checks

- **Steps**: in the existing tests, replace `_job()` with `_build_job()` wherever steps are read: `test_every_action_is_pinned_by_commit`, `test_a_tag_pinned_action_is_caught`, `test_the_job_uses_no_credential` (check both the caller and the called job, and the called workflow's top-level `permissions`), `test_a_token_in_the_job_is_caught`, `test_the_job_installs_frozen_and_checks_the_contract`, `test_no_step_swallows_a_failure`. Keep each mutant, now built from `_build_job()`. `test_every_dockitty_call_passes_the_astro_config` also scans the shared workflow's text. Update the module docstring.
- **Notes**: `_job()['name']` stays the caller's display name for the router-row tests; the T001 row test covers the called row.

### Subtask T005 – Scrub copy, changelog, blast radius

- **Steps**:
  - Add the path to the `docs_site` row in `tests/release/ci_retirement_scrub.json` and mention the shared build in its note.
  - Changelog fragment `docs/changelog/unreleased/6937-docs-site-shared-build.internal.md`, one line (internal entries are one line); check with `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
  - Run: `uv run --frozen pytest tests/ci/ -n auto --dist loadfile`, `tests/release/test_release_ci_ownership.py`, `tests/architectural/test_dual_mode_contract.py`, `tests/ci/test_fork_guard.py`, `tests/architectural/test_no_legacy_terminology.py`, `make test-fast`. Record counts with `add-history`.

## Test Strategy

- Red: T001 commit alone fails the new tests (record the failure list).
- Green: after T002–T005 the whole module passes; mutants still catch a tag pin, a token, a step-level `continue-on-error`.
- Non-vacuity: `test_the_build_job_carries_the_build` fails if the steps are removed from the called job.
- No typed Python sources beyond the test module; `ruff check` and `ruff format --check --force-exclude` on it.

## Risks & Mitigations

- **Vacuous checks**: mitigated by `_build_job()` + the carries-the-build assertion.
- **Row name**: GitHub's `<caller> / <callee>` naming; the gate classifies every row, so no allowlist is needed. The PR's real run is the end-to-end proof.
- **Hot file**: rebase `ci-router.yml` edits just before push.

## Review Guidance

- Confirm `docs-pages.yml` is untouched and the D-12 pins pass unchanged.
- Confirm no step disappeared or changed between the old job and the new build job (diff them).
- Confirm the T001 commit is red on its own.
- Confirm `router-gate.needs` still lists `docs-site` and `ADVISORY_JOB_NAMES` is empty.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`
