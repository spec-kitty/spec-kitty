---
work_package_id: WP01
title: Planning-only fingerprint for the analysis material closure
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7106-analysis-freshness-claim-fields
merge_target_branch: issue-7106-analysis-freshness-claim-fields
branch_strategy: Planning artifacts for this mission were generated on issue-7106-analysis-freshness-claim-fields. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7106-analysis-freshness-claim-fields unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-analysis-freshness-claim-fields-01M6G9PP
base_commit: ca57af5154500f856b822c2f89aa39884e27a7e3
created_at: '2026-11-03T08:57:25.070249+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Implementation
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/analysis_inputs.py
create_intent:
- tests/integration/test_analysis_freshness_claim_7106.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/analysis_inputs.py
- src/specify_cli/frontmatter.py
- src/specify_cli/lanes/implement_support.py
- tests/specify_cli/test_analysis_inputs.py
- tests/integration/test_analysis_freshness_claim_7106.py
- docs/changelog/unreleased/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Planning-only fingerprint for the analysis material closure

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (python implementer), and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Close spec-kitty/spec-kitty#7106: claiming a work package must not stale the mission's recorded
analysis, and a real planning edit must still stale it.

Definition of done:

- `tests/specify_cli/test_analysis_inputs.py` proves the material key for a WP prompt ignores
  `base_branch` / `base_commit` / `created_at`, and that the key for `meta.json` ignores
  `vcs` / `vcs_locked_at`.
- The same file proves each of `subtasks`, `dependencies`, `requirement_refs`, `owned_files`, the
  prompt body and an added WP file still changes the key.
- `tests/integration/test_analysis_freshness_claim_7106.py` drives the real CLI: `record-analysis
  --report-only`, `agent action implement WP01` (real lane worktree), `agent action implement WP02`
  → exit 0, no `analysis_report_required`; then edits WP01's `subtasks` and asserts the next claim
  is refused.
- Both new tests were **red on the pre-fix tree**; the PR records that output.
- `ruff check`, `ruff format --check` and the blast-radius suites are green.

## Context & Constraints

- Read first: `kitty-specs/analysis-freshness-claim-fields-01M6G9PP/spec.md` (FR-001…FR-005,
  NFR-001…NFR-003, C-001…C-003), `.../plan.md` (D-1…D-3) and `.../research.md` (D1…D4).
- The failing path today: `src/specify_cli/analysis_inputs.py::collect_material_inputs` →
  `_entry()`. For `tasks/WP*.md` it hashes `metadata` minus
  `specify_cli.migration.strip_frontmatter.MUTABLE_FIELDS`; `base_branch`, `base_commit` and
  `created_at` are in `STATIC_FIELDS`, so they are hashed. `meta.json` is hashed whole, so the
  `vcs` / `vcs_locked_at` lock the first claim writes stales it too.
- These two writers are the claim path, not planning: `lanes/implement_support.py`
  (`create_lane_workspace` stamps the provenance triple; `ensure_vcs_locked` writes the lock).
  Do not change them.
- The gate that refuses is `cli/commands/agent/workflow.py::_require_current_analysis_report`
  → `analysis_report.py::check_analysis_report_current`, which only consults the material closure
  when the report carries `material_manifest_version` (the `record-analysis --report-only` path).
  Do not change the gate's requirements.

## Branch Strategy

- **Strategy**: `{{branch_strategy}}`
- **Planning base branch**: `issue-7106-analysis-freshness-claim-fields`
- **Merge target branch**: `issue-7106-analysis-freshness-claim-fields`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### T001 – Red-first unit fixtures

- **Purpose**: pin the defect at the seam that computes the fingerprint.
- **Steps**: in `tests/specify_cli/test_analysis_inputs.py`, extend the existing
  `test_wp_runtime_fields_do_not_change_definition_hash` pattern (it currently only covers `lane`,
  which was already in `MUTABLE_FIELDS`) with a case that adds the claim's provenance triple to a
  WP prompt and asserts the material key is unchanged; add the `meta.json` sibling (add
  `vcs`/`vcs_locked_at`, assert the key is unchanged). Also assert the *keys* are present
  (`material:<slug>/meta.json`, `material:<slug>/tasks/WP01-*.md`) so the assertion cannot pass
  vacuously on a missing entry.
- **Files**: `tests/specify_cli/test_analysis_inputs.py`
- **Notes**: run these against the unmodified `src/` first and paste the failure into the PR body.

### T002 – Red-first end-to-end reproduction

- **Purpose**: prove the user-visible contract, not just the hash.
- **Steps**: new `tests/integration/test_analysis_freshness_claim_7106.py`. Follow the fixture
  shape of `tests/integration/test_6715_consolidate_lane_evidence.py::setup_mission` (real git
  repo, isolated `HOME`/XDG env, `init --ai claude --non-interactive`,
  `agent mission create … --topology lanes`, two non-dependent WPs, `finalize-tasks`,
  `agent mission record-analysis --input-file <carrier> --report-only`), then claim WP01 and WP02
  with `agent action implement`. Assert the second claim's `returncode == 0`, that its combined
  output contains no `analysis_report_required`, **and** that WP02 actually reached `in_progress`
  (reduced lane from `spec-kitty agent tasks status --mission <slug> --json`) — an exit-0 path that
  never claimed WP02 must fail the test. Mark the module
  `[pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]` and carry
  `@pytest.mark.p0_repro(issue=7106)` while the issue is open.
- **Files**: `tests/integration/test_analysis_freshness_claim_7106.py`
- **Notes**: the carrier body must be a valid `analysis-findings/v1` block with zero findings
  (`verdict: ready`), otherwise `record-analysis` records `verdict: unknown`. Keep the write to a
  path outside the repo checkout (the recoder refuses a dirty worktree).

### T003 – WP-prompt planning projection

- **Purpose**: remove runtime provenance from the WP-prompt fingerprint at its root.
- **Steps**: in `analysis_inputs.py`, replace the WP-file branch of `_entry()` with a helper
  (`_wp_prompt_fingerprint(path, relative)`), which reads with `FrontmatterManager` exactly as
  today (a `FrontmatterError` still raises `MaterialInputError("Invalid WP definition: …")`) and
  hashes `json.dumps({k: metadata[k] for k in WP_STATIC_PROJECTION_FIELDS if k in metadata},
  sort_keys=True, default=str) + "\n" + body`. Import `WP_STATIC_PROJECTION_FIELDS` from
  `specify_cli.dossier.hasher` lazily inside the branch. Do not touch `MUTABLE_FIELDS`.
- **Files**: `src/specify_cli/analysis_inputs.py`
- **Notes**: the allow-list is deliberate — it closes the class (a future runtime writer of a new
  key cannot re-open it). Keep the docstring honest: the module docstring says
  "Runtime/status/cache outputs are deliberately not inputs"; cite the projection there.

### T004 – `meta.json` projection

- **Purpose**: the first claim's VCS lock must not count as planning input.
- **Steps**: add `_meta_fingerprint(path, relative)` and dispatch on
  `path == feature_dir / "meta.json"` in `_entry()`. Load with the existing `_mapping()` helper
  (so malformed JSON/YAML keeps the existing fail-closed `MaterialInputError`), drop
  `VCS_LOCK_META_FIELDS` (import from `kernel.vcs_lock`), hash
  `json.dumps(projected, sort_keys=True, default=str)`.
- **Files**: `src/specify_cli/analysis_inputs.py`
- **Notes**: every other key — `target_branch`, `topology`, `mission_id`, `status_phase` — must
  keep staling the report. `VCS_LOCK_META_FIELDS`'s docstring forbids an inline duplicate tuple.

### T005 – Positive controls (parallel with T003/T004)

- **Purpose**: prove the narrowed fingerprint still guards the mission.
- **Steps**: unit level — for each of `subtasks`, `dependencies`, `requirement_refs`,
  `owned_files`, a body change and an added `tasks/WP02-*.md`, assert the material key changes;
  for `meta.json`, assert changing `target_branch` changes the key while the VCS lock does not.
  End-to-end — on the T002 fixture, edit WP01's `subtasks` after the analysis, then assert the
  next `agent action implement` is refused with `analysis_report_required`. Same fixture, both
  directions (half-by-half proof per the non-vacuity tactic).
- **Files**: both test modules
- **Notes**: these are the tests that must fail if the fix over-reaches.

### T006 – Mutation check and blast radius

- **Purpose**: prove the new tests are not tautological, and keep the diff clean.
- **Steps**: (a) temporarily put `created_at` back into the projection **and** revert the
  `meta.json` branch, confirm T001/T002 go red, then restore; paste both the red and the
  restored-green output into the PR's `## Tests run` / `Self-review:` block.
  (b) `uv run ruff check src/specify_cli/analysis_inputs.py tests/specify_cli/test_analysis_inputs.py tests/integration/test_analysis_freshness_claim_7106.py`,
  `uv run ruff format --check --force-exclude <the same files>`, `uv run mypy src/specify_cli/analysis_inputs.py` (project config).
  (c) run `tests/specify_cli/test_analysis_inputs.py`, `tests/git/test_report_transaction.py`,
  `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py`,
  `tests/integration/test_owned_analysis_currency.py`,
  `tests/integration/test_owned_analysis_recording.py`, `tests/dossier/`, and `make test-fast`.
- **Files**: none (verification only)
- **Notes**: do not run `make test-full`; CI owns the full sweep.

## Test Strategy

- New tests live beside the code they cover (`tests/specify_cli/`) plus one integration module.
- Commands:
  - `uv run pytest tests/specify_cli/test_analysis_inputs.py -q`
  - `uv run pytest tests/integration/test_analysis_freshness_claim_7106.py -q`
- Typed sources: `uv run mypy src/specify_cli/analysis_inputs.py` must pass with the project config.

## Risks & Mitigations

- **Over-narrowing**: a planning field silently dropped from the fingerprint would let a stale
  report pass. Mitigation: the field set is the repository's existing authored-content
  classification (exhaustive over `WPMetadata` by test), and T005 asserts the refusals.
- **New refusals for legacy prompts**: mitigated by keeping the tolerant read and projecting the
  raw mapping (never `WPMetadata` with `extra="forbid"`).
- **`meta.json` divergence**: only the two VCS-lock keys are dropped; T005 asserts another
  `meta.json` change still stales.

## Review Guidance

- Confirm the projection reuses the canonical declarations and does not mint a second field list.
- Confirm `MUTABLE_FIELDS`, `analysis_report.py` and the claim writers are untouched.
- Confirm the end-to-end test genuinely claims through `agent action implement` (a real lane
  worktree, real claim commit) rather than simulating the stamp.
- Confirm both mutation directions were exercised and that the positive controls are on the same
  fixture as the regression.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
