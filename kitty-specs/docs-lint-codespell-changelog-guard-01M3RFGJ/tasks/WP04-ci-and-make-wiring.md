---
work_package_id: WP04
title: CI and local wiring
dependencies:
- WP01
- WP02
requirement_refs:
- FR-013
- FR-014
- SC-003
- C-005
- C-008
planning_base_branch: issue-5426-docs-lint
merge_target_branch: issue-5426-docs-lint
branch_strategy: Planning artifacts for this mission were generated on issue-5426-docs-lint. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5426-docs-lint unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-docs-lint-codespell-changelog-guard-01M3RFGJ
base_commit: dbd847a67acfeae366b4d11797d59f78a7bc01bc
created_at: '2026-09-30T08:27:17.927513+00:00'
subtasks:
- T021
- T022
- T023
- T024
- T025
phase: Phase 3 - Wiring and docs
history:
- at: '2026-09-30T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_docs_lint_job.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-router.yml
- tests/ci/test_ci_module_wiring.py
- tests/ci/test_docs_lint_job.py
- tests/architectural/_ci_integrity_oracle.py
- Makefile
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – CI and local wiring

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Load it through the CLI (`spec-kitty agent profile show python-pedro`); do not just adopt the persona name.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log and the Activity Log. Address every item.

---

## Objectives & Success Criteria

Make both checks block every PR, and give contributors one local command (FR-013, FR-014, SC-003, C-005). It is done when:

1. `.github/workflows/ci-router.yml` has an always-on job `docs-lint`: no `if:`, no filter group, no `|| true`. It runs:
   ```yaml
   - run: |
       uv sync --frozen
       uv run --frozen python -m scripts.docs.check_spelling
       uv run --frozen python -m scripts.docs.check_changelog_style
   ```
   It never runs pytest or `make`.
2. `docs-lint` is listed in the `router-gate` job's `needs`, and in `_ALWAYS_ON_JOB_NAMES` in `tests/ci/test_ci_module_wiring.py`.
3. A `docs-lint` Makefile target runs the same two commands (no pytest) and is listed in `.PHONY`.
4. A new CI-shape test, `tests/ci/test_docs_lint_job.py`, asserts the job's contract. The named gate files are green.

## Context & Constraints

- Read: `research.md` R-6 (why always-on, and why not widen the `docs` path group), `plan.md` IC-04, `contracts/check-cli.md`.
- Existing shapes to mirror:
  - the `terminology` job (`ci-router.yml` ~:464–475): checkout, then setup-uv with `python-version: '3.12'`, then `uv sync --frozen --all-extras` and a run. Copy the SHA-pinned action refs **exactly** from that job; do not bump or invent SHAs.
  - The `markdownlint` job (~:411–417) is the neighbor.
- Gates this WP must keep green:
  - `tests/architectural/test_dual_mode_contract.py` (~:304–312): `router-gate.needs` must equal the set of non-gate jobs exactly.
  - `tests/architectural/test_no_duplicate_suite_execution.py`: a new job must not reach pytest, whether directly, via `make` or via a script. `make docs-lint` must not run pytest either (the test reads the Makefile).
  - `tests/ci/test_workflow_script_import_guard.py`: `python -m scripts.docs.…` imports `scripts.release.validate_release`. Check whether this guard needs the invocation form, or a `sys.path` bootstrap in the scripts, and satisfy it.
  - `tests/ci/test_ci_module_wiring.py` (`_ALWAYS_ON_JOB_NAMES` ~:319; unconditional assertion ~:395).
  - Also re-run `tests/architectural/test_gate_selection_authority.py`, `tests/architectural/test_ci_router_transcription_guards.py`, `tests/architectural/test_ci_quality_path_filters.py` and `tests/ci/test_prose_only.py`.
- **Do NOT** add `pyproject.toml`, `README.md` or `packs/**` to the `docs` filter group. It feeds the prose-only globs (~:367) and would let code shards be skipped.
- `gate_selection.py` derives always-on jobs from the absence of `if:`, so no change is expected there. Verify with its tests.

## Branch Strategy

- **Planning base branch**: `issue-5426-docs-lint` · **Merge target branch**: `issue-5426-docs-lint`
- Run `spec-kitty implement WP04` and work in the lane workspace it prints. The lane contains WP01 and WP02 (the scripts); it may not yet contain WP03's content fixes. The job's red/green on the live tree is therefore not this WP's assertion; the shape is.

## Subtasks & Detailed Guidance

### Subtask T021 – The `docs-lint` job

- Place it after `terminology` in the always-on block, with a comment in the style of the surrounding comments:
  ```yaml
  # Docs prose lint (#5426): codespell (typos + scoped US spelling) and the
  # changelog [Unreleased] style guard. Always-on because its inputs span
  # docs/**, README.md, packs/built-in/**/*.md, pyproject.toml and uv.lock,
  # which no single path group covers. Runs no pytest (duplicate-suite ledger).
  docs-lint:
    name: docs lint (spelling + changelog style, always-on)
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@<same SHA as terminology> # v5.0.0
      - uses: astral-sh/setup-uv@<same SHA as terminology> # v5.4.2
        with:
          python-version: '3.12'
      - run: |
          uv sync --frozen
          uv run --frozen python -m scripts.docs.check_spelling
          uv run --frozen python -m scripts.docs.check_changelog_style
  ```
- `uv sync --frozen` installs the default `dev` group, which holds codespell. Confirm the `dev` group is a default group (check `[tool.uv]` `default-groups`, or uv's default behavior) and note the result.

### Subtask T022 – Router gate and always-on list

- Also add `docs-lint` to `MUST_RUN_ALWAYS_ON_GATES` in `tests/architectural/_ci_integrity_oracle.py:75`, and run `tests/architectural/test_ci_integrity_oracle_nonvacuous.py`.

- Add `docs-lint` to `router-gate.needs` (~:712–729), keeping the existing ordering convention.
- Add `"docs-lint"` to `_ALWAYS_ON_JOB_NAMES` in `tests/ci/test_ci_module_wiring.py`.
- Verified: the router-gate verdict step reads the jobs API via `scripts/ci/router_gate.py` and has no per-job list, so no change is needed there. Re-read it to confirm.

### Subtask T023 – Make target

```make
docs-lint: ## Spell-check docs (typos + scoped US spelling) and check the changelog [Unreleased] style
	uv run --frozen python -m scripts.docs.check_spelling
	uv run --frozen python -m scripts.docs.check_changelog_style
```

Add it next to `lint` / `format-check` (Makefile ~:13–21) and to `.PHONY` (~:3). Match the file's existing help-comment convention, if any.

### Subtask T024 – CI-shape test

Create `tests/ci/test_docs_lint_job.py` (fast/unit markers matching `tests/ci/` conventions). Load `ci-router.yml` with the same YAML loader the sibling tests use. Assert:

1. the `docs-lint` job exists and has no `if:` key;
2. its run steps contain both `python -m scripts.docs.check_spelling` and `python -m scripts.docs.check_changelog_style`;
3. no run step contains `|| true`, `pytest` or `make `; neither the job nor any step has a `continue-on-error` **key**; no step has an `if:` key; no step overrides `shell:`;
4. `docs-lint` is in `router-gate.needs`;
5. the Makefile `docs-lint` recipe contains both module commands and no `pytest`.

**Red first**: commit `tests/ci/test_docs_lint_job.py` (and the `_ALWAYS_ON_JOB_NAMES` edit) **before** the workflow/Makefile commit, and confirm it is red. The reviewer checks the commit order.

**Non-vacuity**: for each assertion, write a companion test that feeds a mutated in-memory copy of the job dict or Makefile text through the same checker helper and expects failure: (a) with `|| true` appended; (b) with a job-level `if:` added; (c) with one command removed; (d) with job-level `continue-on-error: true`; (e) with a step-level `continue-on-error: true`; (f) with a step-level `if: false`; (g) with `pytest` added to the Makefile recipe. Structure the assertions as small helper functions that take the parsed data, so the mutants reuse them.

### Subtask T025 – Named gate files

```bash
.venv/bin/python -m pytest \
  tests/ci/test_docs_lint_job.py tests/ci/test_ci_module_wiring.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_prose_only.py \
  tests/architectural/test_dual_mode_contract.py tests/architectural/test_no_duplicate_suite_execution.py \
  tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_router_transcription_guards.py \
  tests/architectural/test_ci_quality_path_filters.py tests/architectural/test_ci_integrity_oracle_nonvacuous.py -q
```

Do **not** run the whole `tests/architectural/` directory (NO_FULL_HEAVY_SUITES_IN_MISSION). If a named file is red, check it on the WP base (`git stash`, or a clean checkout) to classify it as yours or pre-existing, and record the classification.

Also validate the workflow's YAML syntax, e.g. with `actionlint` if available, or at least with `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci-router.yml'))"`.

## Risks & Mitigations

- **Set-equality on router-gate needs**: T022 plus the dual-mode test.
- **A job that silently passes**: the T024 mutants.
- **Action SHA drift**: copy the SHAs from the existing job verbatim.

## Review Guidance

- Diff `ci-router.yml`: only the new job, its comment and the `needs` entry change.
- Confirm there is no path-filter change.
- Confirm that every named gate file ran and passed, with counts in the Activity Log.

## Activity Log

- 2026-09-30T08:10:00Z – system – Prompt created.
