---
work_package_id: WP07
title: Integrated verification
dependencies:
- WP03
- WP04
- WP05
requirement_refs:
- FR-012
- NFR-002
- NFR-003
planning_base_branch: issue-5668-approved-claim-bound
merge_target_branch: issue-5668-approved-claim-bound
branch_strategy: Planning artifacts for this mission were generated on issue-5668-approved-claim-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5668-approved-claim-bound unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-claim-bound-01M444QR
base_commit: 1571015860025be91d106c4f550b3c6b6b1a6246
created_at: '2026-10-04T22:46:21.461366+00:00'
subtasks:
- T027
- T028
- T029
- T030
- T031
- T032
phase: Phase 4 - Integration
history:
- at: '2026-10-04T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/test_approved_bound_integration.py
execution_mode: code_change
owned_files:
- tests/terminus/test_approved_bound_integration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP07 – Integrated verification

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task.** Check the `review_ref` field in the event log (`.venv/bin/spec-kitty agent tasks status --mission approved-claim-bound-01M444QR`). If this work package was returned from review, every feedback item is part of your work.

---

## Objectives & Success Criteria

WP03, WP04 and WP05 were built in parallel lanes that never saw each other. This work package checks them together.

- An attestation survives the run's own `approved -> done` record and the gate re-check (spec US2 scenario 6).
- The mission's new tests and the owning suites pass on the integrated base.
- The issue's own reproducer exits 0 in all four combinations (SC-005).

Implementation command: `.venv/bin/spec-kitty agent action implement WP07 --agent implementer --mission approved-claim-bound-01M444QR`

## Context & Constraints

Read first, in this order:

1. `.kittify/charter/charter.md` (binding) and `spec-kitty charter context --action implement --json`.
2. `kitty-specs/approved-claim-bound-01M444QR/spec.md`, `plan.md` (sections D-1 to D-6), `research.md`, `data-model.md`, `contracts/consolidate-refusals.md`.
3. `kitty-specs/approved-claim-bound-01M444QR/research/code-grounding.md` for file and line references. Line numbers were taken at `9adc68803f`; re-locate by symbol name (`codegraph explore "<symbol>"`).

Rules that bind every work package of this mission:

- **CLI binary**: always `.venv/bin/spec-kitty` and `.venv/bin/python -m pytest`. The bare `spec-kitty` on PATH is a stale install. Never `uv run`.
- **No heavy suites**: never `make test-full`, never a bare `tests/architectural/` run. Run the files named in this prompt.
- **Test economy**: each new test must pin one distinct behaviour. No test per helper, no duplicate of an existing pin. Prefer extending a parametrized test over adding a sibling.
- **Quality**: `ruff check` and `mypy --strict` clean on changed files, complexity <= 15, no new `# noqa` or `# type: ignore`. Format check: `uv run --frozen ruff format --check --force-exclude <changed files>`.
- **Status imports**: import status symbols only through the `specify_cli.status` facade. Git reads go through `consolidation/git_probes.py`; do not shell out to git directly from new consolidation code.
- **Byte-identity**: no existing refusal code or text changes. New texts are additions.
- **No fail-open**: an absent approval stamp is never replaced by the lane tip, in product code or by a test switch (spec C-003).
- **Terminology**: Mission and work package; `--mission`, never `--feature`.
- **Commits**: conventional messages; every commit ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model or tool identifiers in commit messages.
- **Tracers**: do not edit `kitty-specs/approved-claim-bound-01M444QR/tracers/*.md` in a lane worktree (parallel lanes would conflict). Put tooling friction and unplanned design decisions in this prompt's Activity Log and in your hand-back report; the orchestrator records them.

## Branch Strategy

- **Strategy**: see `branch_strategy` in the frontmatter (written by `finalize-tasks`)
- **Planning base branch**: issue-5668-approved-claim-bound
- **Merge target branch**: issue-5668-approved-claim-bound

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path `spec-kitty agent action implement` resolves, do not construct it.

## Subtasks & Detailed Guidance

### Subtask T028 – Attestation across the gate

- **Purpose**: US2 scenario 6 spans the attestation (WP04) and the gate re-check (WP03).
- **Steps** (`tests/terminus/test_approved_bound_integration.py`, markers `integration`, `git_repo`):
  1. Build the `post_approval_support` mission, strip WP01's approval stamps, run `consolidate --attest-approved-reviewed WP01 --attest-reason "..."` for both strategies.
  2. Assert: exit 0, the banner is printed, the approved content of both lanes is on the target, WP01 is `done`, and the status log holds the attestation followed by the `approved -> done` record.
  3. If WP04's e2e already asserts exactly this on the integrated code, do not duplicate it: say so in the Activity Log and write no new test.
- **Files**: `tests/terminus/test_approved_bound_integration.py`.

### Subtask T030 – Orchestrator contract version and review follow-ups (from the WP05 review)

- **Purpose**: WP05 added the envelope key `data["preflight_error_code"]` and a new way `consolidate-mission` can refuse. The repository's precedent bumps the orchestrator-api contract version for both (1.9.0 for the additive `teardown_error_code` key, 1.7.0 for a call that can newly refuse). No work package owned those files.
- **Steps**:
  1. `src/specify_cli/orchestrator_api/envelope.py`: add a `# 1.10.0:` changelog comment in the style of its neighbours (what was added: `data.preflight_error_code` on `PREFLIGHT_FAILED` from `consolidate-mission`, carrying `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING` or `APPROVAL_STAMP_NOT_ON_LANE`) and set `CONTRACT_VERSION = "1.10.0"`.
  2. `tests/specify_cli/orchestrator_api/test_contract_version.py`: update the pins and the docstring to 1.10.0.
  3. `docs/api/orchestrator-api.md`: the version, a `1.10.0` entry, and a `data.preflight_error_code` section next to `teardown_error_code`.
  4. `tests/orchestrator_api/test_consolidate_mission_post_approval.py`: add the assertion `envelope["error_code"] == "PREFLIGHT_FAILED"` to the refusing cases.
  5. `src/specify_cli/orchestrator_api/consolidation.py` (`_approved_bound_claim_base`, about line 423): only `GitProbeError` is caught around `resolve_placement_only`; any other exception escapes without an envelope. Catch what the executor catches for the same call and fail closed with the same `PREFLIGHT_FAILED` shape. No lane may be merged on any error.
  6. Run `tests/orchestrator_api tests/contract/test_orchestrator_api.py tests/specify_cli/orchestrator_api/test_contract_version.py tests/agent/test_orchestrator_commands_integration.py -q`, and search for other pins of the version string: `grep -rn "1\.9\.0" src tests docs --include="*.py" --include="*.md" --include="*.json" --include="*.yaml"`.
- **Files**: the five files above (out-of-map for this work package; WP05 is merged into your base).

### Subtask T031 – Resume after an interruption between the lane merge and the gate (from the WP03 review)

- **Purpose**: a hole, confirmed by the WP04 reviewer in a simulated form (the late commit was put on the mission branch with `update-ref` on a LANES mission; `consolidate` then exits 0 and the late file lands, with or without an attestation). Not yet reproduced through a real killed run. Sequence: a run passes the claim-time check; a content commit is added to an approved lane; the lane is merged into the mission branch; the run is killed before the gate. On `consolidate --resume` the claim-time check takes the **live** mission branch as an anchor (`reconciliation._mission_branch_anchor`, called from the claim builder; `phase_claim.py` about line 507). The live mission branch already contains the late commit, so the commit is exempt; the gate re-check validates against tips recaptured on the resume, which also include it; and the claim rebuilt on the resume reads the lane tip, so the old content checks attribute it. If that is what happens, the late commit lands with the banner.
- **Steps**:
  1. Red first. In `tests/terminus/test_post_approval_resume.py` (WP05's file, now on your base) add one test using the same `_InterruptedPostApproval` harness: inject the content commit on the lane **before** its merge (reuse the injection approach of `tests/terminus/test_post_approval_gate_recheck.py`), kill after the lane merge and before the gate, then `consolidate --resume`. Assert the ideal: non-zero exit, `LANE_MOVED_AFTER_APPROVAL`, late file not on the target. Run it. If it is green already, the hole does not exist: keep the test only if no existing test pins this sequence, record the result, and skip step 2. If the harness cannot kill at that point, report what you found.
  2. Fix (only if red). On a resume, the mission-branch anchor must be the mission branch tip captured **before the first mutation of the run** (`ConsolidationState.pre_mutation_refs` holds it and is never recaptured on a resume), not the live tip. The tool's own merge of the mission branch into a stale lane brings in other lanes' commits; those must stay exempt, so add each other bounded lane's approval stamps as anchors (content reachable from an approval stamp was reviewed). Do not use any live branch name that this run moved. Keep the fresh-run behaviour byte-for-byte. Files: `reconciliation.py` and, if the state must be passed in, `phase_claim.py` (WP02's files, merged into your base).
  3. Run `tests/terminus/test_resume_*.py`, `tests/terminus/test_post_approval_resume.py`, `tests/consolidation/test_approved_bound.py`, and the whole `tests/consolidation tests/terminus` once more. A resume test that newly refuses means the anchors are too narrow: fix the anchors, never the test.
  4. If the fix is larger than about 40 lines of source or changes a fresh run's verdict anywhere, stop and hand back with the diagnosis.

### Subtask T032 – Pin the case the gate re-check really closes, and tidy what the reviews found

- **Steps**:
  1. The plain "late file" injection of `tests/terminus/test_post_approval_gate_recheck.py` was already failed by the older content checks before the gate change; only the named refusal is new. The WP03 reviewer constructed the case the older checks miss: on a LANES mission, a late commit on lane-a that writes lane-b's approved blob (same path, identical content as lane-b's approved file) passed the old gate with exit 0 and the banner under both strategies. Add that case to the same test file as one parametrized test over both strategies (LANES topology), asserting the refusal, no banner and the pre-run tips. Correct the module docstring: it says the plain late commit "rides the lane merge to the target and exits 0", which is false for that fixture.
  2. `tests/terminus/canceled_dependency_support.py::strip_lane_head_stamps` (about lines 205-216) writes a lone newline into an empty log copy, so a second call raises `JSONDecodeError`. Fix the helper (skip blank lines / do not write an empty line), then make `tests/terminus/test_unstamped_approval_attestation.py` use the shared helper again and delete its local `_strip_stamps`.
  3. `tests/consolidation/test_approved_bound.py`: the unit test near line 318 pins the same rule as `test_attested_mixed_lane_refuses_content_committed_after_the_attestation[unstamped]`; keep one.
  5. `src/specify_cli/consolidation/approved_attestation.py` (from the WP04 review): the repeat-attestation refusal says "holds content committed after the earlier attestation" also when the lane was merged with the target or rewritten; say "moved past the earlier attestation" so the text is true in every case (update the one test that pins the text). The docstrings near lines 7-9 and 81 say an earlier attestation "is accepted" without the condition; state the condition. The module imports seven underscore-private names from `reconciliation.py`: where T031 already touches `reconciliation.py`, expose the ones that are used as a small public seam (and add them to `__all__` only if the dead-symbol gate then passes); if that grows beyond a rename, leave it and note it for the PR.
  4. `tests/terminus/test_post_approval_commit_refused.py::test_printed_recovery_command_runs_and_sends_the_work_package_back` runs six CLI cells for one command template: keep the two topology cells and assert the other codes render the same command without running it.
- **Files**: the test files named above (out-of-map for this work package; all are on your base).

### Subtask T029 – Owning suites on the integrated base

- **Steps**:
  1. Run, and record passed, failed, xfailed and skipped counts for each:
     ```bash
     .venv/bin/python -m pytest tests/consolidation tests/terminus tests/orchestrator_api -q -n auto --dist loadfile -p no:cacheprovider
     .venv/bin/python -m pytest tests/status -q -n auto --dist loadfile
     .venv/bin/python -m pytest tests/cli -q -n auto --dist loadfile
     .venv/bin/python -m pytest tests/integration -q -k "consolidate or merge" -n auto --dist loadfile
     .venv/bin/python -m pytest tests/consolidation/test_single_rollback_authority.py tests/status/test_lane_head.py tests/specify_cli/cli/commands/test_merge_cli_golden.py -q
     .venv/bin/python -m pytest tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_layer_rules.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_coord_read_residuals_closeout.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_ruff_format_enforcement.py tests/architectural/test_ruff_format_exclude_ratchet.py -q
     ```
  2. Classify every red per the CLAUDE.md baseline-red gotcha: re-run the failing test on `issue-5668-approved-claim-bound` at its pre-mission commit. Red there too: record it as pre-existing with the evidence. Green there: it is this mission's; fix it if it is inside this mission's files, otherwise hand back with the diagnosis.
  3. `ruff check` on the mission's changed files, the format check with `--force-exclude`, and `mypy --strict` on the changed source modules.
- **Files**: fixes only where a red is this mission's.

### Subtask T027 – Run the issue's reproducer

- **Steps**:
  1. Fetch the script: `unset GITHUB_TOKEN; gh api repos/spec-kitty/spec-kitty/issues/5668 -q .body` and extract the bash block in the `<details>` section to a scratch file outside the repository.
  2. Make sure the CLI under test is this lane's code: the lane worktree is not the editable install. Run the script with a binary that executes this worktree's sources (for example a wrapper script that runs `PYTHONPATH=<worktree>/src <repo>/.venv/bin/python -m specify_cli "$@"`), and say in the Activity Log how you made sure. Record the wrapper's path so the reviewer can re-run one cell.
  3. Run it in four empty directories with a throwaway `HOME` (`lanes|coord` x `squash|merge`). Each must exit 0 ("fixed"). Record the four outputs in the Activity Log; they go into the PR.
- **Files**: none in the repository.

## Test Strategy

See T029 for the commands. One new test file at most.

## Risks & Mitigations

- **Baseline reds.** Do not chase a red that is also red before the mission; record it.
- **Stale install.** Tests that shell out to `spec-kitty` need this worktree's code; `run_terminus` uses `python -m specify_cli`, check which interpreter and source path it resolves.

## Review Guidance

- Re-run one reproducer cell yourself with the recorded wrapper.
- Every red in the Activity Log is classified with evidence.
- No duplicate of WP04's e2e was added.
- Confirm the implementer ran `ruff check`, the format check and `mypy --strict` on the changed files and that all were clean.
- Reviewer and implementer are different agents. Judge each new test: does it pin a distinct behaviour, and would it fail if the behaviour were removed?

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:45:00Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status> --mission approved-claim-bound-01M444QR` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done --mission approved-claim-bound-01M444QR` for subtasks.
