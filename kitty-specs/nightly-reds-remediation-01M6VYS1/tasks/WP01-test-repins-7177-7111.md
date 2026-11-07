---
work_package_id: WP01
title: 'Test re-pins without production change (#7177, #7111)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-003
planning_base_branch: issue-7183-nightly-reds-remediation
merge_target_branch: issue-7183-nightly-reds-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-7183-nightly-reds-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7183-nightly-reds-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Re-pins
history:
- at: '2026-11-07T21:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/cli/commands/test_merge_cli_golden.py
- tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 - Test re-pins without production change (#7177, #7111)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). If this WP was returned from review, address every feedback item first.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

- FR-001, FR-002, NFR-001..004. Both nodes pass; neighbouring guards stay green; no `src/` change.
- Nodes: `tests/specify_cli/cli/commands/test_merge_cli_golden.py::test_help_pins_one_line_help_and_every_visible_flag` and `tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py::test_migration_actor_is_stored_whole_and_stays_a_reconstruction_seed`.

## Context & Constraints

- Spec: `kitty-specs/nightly-reds-remediation-01M6VYS1/spec.md` (User Story 1). Research decisions: `research.md`.
- Both nodes live in out-of-matrix trees (nightly only), so only a local run proves them.
- Charter: `.kittify/charter/charter.md` Standing Order 4 (judge the test; stale means re-pin).

## Subtasks & Detailed Guidance

### Subtask T001 - Pin `--dependency-ref` in the consolidate flag golden (#7177)

- **Purpose**: #6771 (`9c2881c6`) added a visible, repeatable `--dependency-ref` option to `consolidate`; the golden is a strict hand-maintained set, so it fails by design until re-pinned.
- **Steps**:
  1. RED: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_merge_cli_golden.py -q` (expect 1 failed, 10 passed, `unexpected (new/renamed): ['--dependency-ref']`).
  2. In `EXPECTED_PARSER_LONG_FLAGS` add `"--dependency-ref"` keeping the per-flag comment style, e.g. `# #6771 (9c2881c6): repeatable external dependency ref (inherited history), recorded on the transaction record and threaded into the claim build and the closed-world forecast.`
  3. Do not touch `EXPECTED_HIDDEN_LONG_FLAGS` (the option is visible) or `EXPECTED_DRY_RUN_PAYLOAD_KEYS` (no payload key changed).
  4. GREEN: same command, expect 11 passed.
- **Files**: `tests/specify_cli/cli/commands/test_merge_cli_golden.py`.
- **Notes**: there is no generator; do not edit `kitty-specs/decompose-merge-god-module-01KVXHDK/contracts/cli-surface-contract.md` (historical snapshot). Strength check: the test must still fail for any other flag drift (the set equality is unchanged).

### Subtask T002 - Rewrite the orchestrator-api migration-actor test to seed in-process (#7111)

- **Purpose**: #6754 (`f22a7b6275`, PR #6811) makes a caller-supplied `migration:` actor refuse with `USAGE_ERROR`; only an in-process migration may write a reconstruction seed. The test must write the seed through that mandated path and keep its three seed predicates.
- **Steps**:
  1. RED: `PWHEADLESS=1 .venv/bin/python -m pytest tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py -q` (expect 1 failed, 8 passed).
  2. In `test_migration_actor_is_stored_whole_and_stays_a_reconstruction_seed`, replace `_start_implementation(repo_root, "migration:backfill")` with an in-process seed write, using the same helpers the neighbouring test in the same file already uses (`from specify_cli.status import build_system_actor`, `from tests._support.status_seed import seed_status_event`, a `StatusEvent` with `from_lane=Lane.PLANNED`, `to_lane=Lane.CLAIMED`, `force=True`, `execution_mode="worktree"`, `actor=build_system_actor("migration:backfill")`). Never hand-append JSONL.
  3. Expected actor is now `{"tool": "migration:backfill", "role": "system", "profile": None, "model": None}` (role `system`, NOT `implementer`).
  4. Keep, on the row read back through `read_events_raw`: the actor equals that dict; `is_migration_actor(raw["actor"])`; `diary._is_reconstruction_seed(diary.StatusEvent.from_dict(dict(raw)))`; `reduces_as_reconstruction_seed(raw["actor"])` (from `tests/_support/reconstruction_seed.py`). Remove any helper left unused by the rewrite.
  5. Update the docstring: a `migration:` actor is written in-process by migrations (`build_system_actor`), stored whole, and stays a reconstruction seed; a caller-supplied one is refused (#6754), covered by `tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py`. Cite `f22a7b6275`.
  6. GREEN: same command, expect 9 passed.
- **Files**: `tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py`.
- **Notes**: do not assert the refusal here (already covered for all four verbs elsewhere; a duplicate would orphan the stored-whole pin). Do not touch `src/`, the guard or its refusal matrices. This is a rewrite, not a one-line re-pin; say so in the history note.

### Subtask T003 - Evidence and neighbour guards

- Run and record: `test_merge_cli_golden.py` (11 passed), `test_wp_lifecycle_structured_actor_6400.py` (9 passed), `tests/status/test_caller_seed_refusal_6754.py tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py` (must stay green), optionally `tests/unit/migration/test_system_actor_6722.py`.
- Lint and format on both files (`ruff check`, `ruff format --check --force-exclude`).
- Strength spot-check (not committed): remove `"--dependency-ref"` again and confirm the golden fails; temporarily drop one seed predicate source (e.g. build the actor with role `implementer`) and confirm the test fails.
- Commit: `test(nightly): re-pin the consolidate flag golden and the orchestrator-api migration actor test (#7177, #7111)`.

## Test Strategy

Commands above; the tests are the deliverable.

## Risks & Mitigations

- Keeping the `implementer` role expectation after the rewrite would be wrong (builder writes `system`). Mitigation: assert the full 4-key dict.

## Review Guidance

- Confirm RED output was captured for both nodes, the three seed predicates are still asserted, nothing in `src/` changed, and the refusal matrices are untouched.

## Branch Strategy

- **Strategy**: `single_branch` (no lanes; WPs run one after the other in the write checkout)
- **Planning base branch**: `issue-7183-nightly-reds-remediation`
- **Merge target branch**: `issue-7183-nightly-reds-remediation`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change by hand.

## Rules that bind every WP (charter and spec)

- **Never weaken a test to green it.** A re-pin keeps every original behavioural assertion and adds the new contract. If you cannot re-pin without loosening an assertion or deleting a pin without a stronger home, STOP and report an operator decision.
- Cite the contract-change commit in a comment on the re-pinned lines or in the commit message.
- RED first: run each exact node id on the current tree before editing and keep the failure output (summary line). After the edit run the same ids, then the owning files and named gates. Record the exact commands and passed/failed counts in the WP's `add-history` note and the commit message.
- Run tests as `PWHEADLESS=1 .venv/bin/python -m pytest <ids> -q` (not a bare `uv run`). No full suites, no `make test-fast` over the repo (NO_FULL_HEAVY_SUITES_IN_MISSION); the targeted nodes, owning files and named gates are the verification.
- `uv run --frozen ruff check <files>` and `uv run --frozen ruff format --check --force-exclude <files>` must report 0 issues. No `noqa`, no `type: ignore`, no allowlist additions.
- Touch only this WP's owned files. A tiny justified out-of-map edit needs a one-line rationale in the history note.
- Commit per WP, ending the message with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do NOT push, open a PR, review, approve, accept or consolidate; the stop point is `for_review`.

## Progress & Status

Progress lives in the status event log, never in this file.

- Progress note: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- Subtask done: `spec-kitty agent tasks mark-status T00x --status done`
- Move: `spec-kitty agent tasks move-task <WPID> --to for_review`
- View: `spec-kitty agent tasks status`

Implementation command: `spec-kitty agent action implement <WPID> --agent claude --mission nightly-reds-remediation-01M6VYS1`
