---
work_package_id: WP05
title: Orchestrator and resume entry points
dependencies:
- WP02
requirement_refs:
- FR-011
planning_base_branch: issue-5668-approved-claim-bound
merge_target_branch: issue-5668-approved-claim-bound
branch_strategy: Planning artifacts for this mission were generated on issue-5668-approved-claim-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5668-approved-claim-bound unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-claim-bound-01M444QR
base_commit: 1571015860025be91d106c4f550b3c6b6b1a6246
created_at: '2026-10-04T21:47:05.971580+00:00'
subtasks:
- T021
- T022
- T023
phase: Phase 3 - Completing the fix
history:
- at: '2026-10-04T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/
create_intent:
- tests/orchestrator_api/test_consolidate_mission_post_approval.py
- tests/terminus/test_post_approval_resume.py
execution_mode: code_change
owned_files:
- src/specify_cli/orchestrator_api/consolidation.py
- tests/orchestrator_api/test_consolidate_mission_post_approval.py
- tests/terminus/test_post_approval_resume.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP05 – Orchestrator and resume entry points

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

No entry point lands a post-approval commit (spec FR-011, SC-006).

- `orchestrator-api consolidate-mission` on a mission with code lanes evaluates the lane check before its first lane merge and returns its `PREFLIGHT_FAILED` envelope with the refusal code; no lane is merged.
- `consolidate --resume` refuses a commit added to a not-yet-consolidated lane between the interruption and the resume, and does not refuse the tool's own merges.

Implementation command: `.venv/bin/spec-kitty agent action implement WP05 --agent implementer --mission approved-claim-bound-01M444QR`

## What WP02 delivered (read before the subtasks)

WP02 is approved. These exist on your lane's base; call them, do not redefine or edit them:

- `consolidation/approved_bound.py`: `APPROVED_REVIEWED`, `ATTEST_APPROVED_FLAG`, `BoundRefusalCode`, `BoundRefusal.render()`, `approval_stamp(events, wp_id)`, `check_lane(...)`, `commits_beyond`, `content_commits`. The printed recovery command is `spec-kitty agent tasks move-task <WP> --to in_progress --mission <mission>`.
- `consolidation/reconciliation.py`: `approved_bound_refusal(repo_root, feature_dir, lanes_manifest, *, coord_base_ref, excluded_canceled_wp_ids=(), excluded_window_base=None, event_log=None) -> str | None` and `lane_tips_moved_refusal(repo_root, lanes_manifest, *, validated_tips, anchor_shas, planning_prefix, approved_wp_ids=None) -> str | None`. The claim carries `ApprovedWpCommitSet.bound_lane_tips`.
- Run state (`run_state.py`, set in `phase_claim._capture_reconciliation_claim`): `validated_lane_tips: dict[str, str]`, `bound_anchor_shas: tuple[str, ...]`.
- `tests/terminus/post_approval_support.py` (frozen: import it, do not edit it): `build_post_approval_mission(tmp_path, "lanes" | "coord")` returning a two-lane `CoordMission`, `add_post_approval_commit(mission, lane=...)`, `strip_approval_stamps(mission, wp_id)`, `rework_and_reapprove(mission, wp_id)`, `lane_worktree`. Test helpers that re-record approvals at the current lane tips: `restamp_approvals_at_lane_tips` (`tests/terminus/conftest.py`), `tests/consolidation/approval_stamps.py`.
- `tests/architectural/test_no_dead_symbols.py` is red on the base for five names that have no `src/` caller yet: `APPROVED_REVIEWED`, `ATTEST_APPROVED_FLAG`, `approval_stamp` (WP04 imports them), `lane_tips_moved_refusal` (WP03), `approved_bound_refusal` (WP05). Your work package clears its own names; the others stay red on your lane until the lanes are consolidated. Do not add an allowlist entry.
- Running mypy on one file alone reports a spurious `no-any-return` because of the repository's `follow_imports = "skip"` override; run `.venv/bin/mypy --strict src/specify_cli/consolidation` (the package) instead.

- **For this work package**: `approved_bound_refusal` returns `None` when the claim base cannot be resolved, so pass a base that resolves (take it from the same resolution the executor uses and resolve it to a SHA first; if it does not resolve, refuse). It also does not catch an unmaterializable status snapshot: wrap that case and fail closed with the existing preflight error shape.

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

### Subtask T021 – Red test for the orchestrator code-lane path

- **Purpose**: `orchestrator_api/consolidation.py::_execute_lane_merge` merges lanes directly on its code-lane path (`consolidate_lane_into_mission`, `integrate_mission_into_target`) with no claim and no verifier. Witness that it lands the late commit.
- **Steps**:
  1. Create `tests/orchestrator_api/test_consolidate_mission_post_approval.py`. Model it on `tests/orchestrator_api/test_consolidate_mission_protected_target.py` (how it builds a mission and invokes the command, how it reads the envelope).
  2. Build a mission with a code lane, WP01 approved through real transitions (reuse `tests/terminus/post_approval_support.py` if it can be imported from there; otherwise the smallest local builder), add the post-approval commit, invoke `consolidate-mission`.
  3. Assert: the envelope is the `PREFLIGHT_FAILED` shape, `data["preflight_error_code"] == "LANE_MOVED_AFTER_APPROVAL"`, the mission branch and the target are at their pre-run tips, the late file is on neither.
  4. Positive control: the same mission without the late commit consolidates.
  5. Run: red. Commit alone: `test(orchestrator-api): reproduce consolidate-mission landing a post-approval commit`.
- **Files**: `tests/orchestrator_api/test_consolidate_mission_post_approval.py`.

### Subtask T022 – Evaluate the check before the first lane merge

- **Steps**:
  1. In `_execute_lane_merge`, after the merge gates passed and before the `for lane in lanes_manifest.lanes: consolidate_lane_into_mission(...)` loop, call `reconciliation.approved_bound_refusal(...)`. WP02 defined it; do not edit `reconciliation.py`.
  2. Arguments: `coord_base_ref` as the executor's claim would resolve it for a fresh run (the coordination branch tip when the mission has one, else the mission branch: read `phase_claim._capture_reconciliation_claim`), the canceled-with-provenance work packages as the executor computes `excluded_canceled_wp_ids` (reuse that function), `excluded_window_base` = the target tip.
  3. On a refusal, fail the way `_refuse_protected_status_target` fails in this module, so the envelope is `PREFLIGHT_FAILED`. That precedent puts its code only into the error prose. Here the code must also be machine-readable: report it as `data["preflight_error_code"]` (a new, additive key; `teardown_error_code` means something else and is not reused). The test asserts that key exactly, not a substring of the prose. Keep the envelope contract stable: run `tests/contract/test_orchestrator_api.py` and `tests/specify_cli/orchestrator_api/test_contract_version.py`.
  4. The planning-only path calls `_run_lane_based_consolidation` and inherits the claim-time refusal; add no second check there.
  5. Keep `_execute_lane_merge` at complexity <= 15: put the call in a small helper `_refuse_post_approval_lane_content(...)`.
- **Files**: `src/specify_cli/orchestrator_api/consolidation.py`.
- **Notes**: this path has no rollback door, which is why the check must precede the first merge. The gate re-check does not apply here (spec, Known residuals).

### Subtask T023 – Resume

- **Purpose**: the claim is rebuilt on `--resume`, so the refusal is inherited; prove the refusing direction through a real resume. The passing direction is already pinned by the existing `test_resume_*` files and by WP02's "merge from the mission branch" unit case; do not add a test for it.
- **Steps** (`tests/terminus/test_post_approval_resume.py`):
  1. Use an existing interruption harness (`tests/terminus/rollback_harness.py`, or the pattern in `test_resume_recovers_lagging_checkouts.py`) to interrupt the two-lane mission of `post_approval_support` after the first lane was consolidated.
  2. Add a content commit to the second, not yet consolidated lane, then `consolidate --resume`: refused with `LANE_MOVED_AFTER_APPROVAL`, the late file is not on the target.
  3. This test is mandatory (FR-011). If no existing harness can produce the interruption, stop and hand back with what you found; do not replace it with a unit test.
- **Files**: `tests/terminus/test_post_approval_resume.py`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/orchestrator_api tests/contract/test_orchestrator_api.py tests/specify_cli/orchestrator_api/test_contract_version.py -q
.venv/bin/python -m pytest tests/terminus/test_post_approval_resume.py tests/terminus/test_resume_recovers_lagging_checkouts.py tests/terminus/test_resume_phantom_only.py -q
.venv/bin/python -m pytest tests/agent/test_orchestrator_commands_integration.py -q
```

## Risks & Mitigations

- **Envelope contract.** External orchestrators parse it. Add a code, do not rename or move existing keys; if the contract version test demands a bump, follow what it says and record it for the PR.
- **Different `coord_base_ref` than the executor.** A wrong base makes every commit "beyond the bound". Take it from the same resolution the executor uses.

## Review Guidance

- The check runs before the first `consolidate_lane_into_mission` call; the test proves no branch moved.
- No copy of the lane check logic in `orchestrator_api/`: one call into `reconciliation`.
- The envelope contract tests pass.
- Confirm the implementer ran `ruff check`, the format check and `mypy --strict` on the changed files and that all were clean.
- Reviewer and implementer are different agents. Judge each new test: does it pin a distinct behaviour, and would it fail if the behaviour were removed?

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:45:00Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status> --mission approved-claim-bound-01M444QR` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done --mission approved-claim-bound-01M444QR` for subtasks.
