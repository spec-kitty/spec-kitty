---
work_package_id: WP03
title: 'Charter status and activation re-pins (#7181, #7182)'
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- C-004
- NFR-001
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: issue-7183-nightly-reds-remediation
merge_target_branch: issue-7183-nightly-reds-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-7183-nightly-reds-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7183-nightly-reds-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Re-pins
history:
- at: '2026-11-07T21:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/cli/commands/test_charter_generate_autotrack.py
- tests/integration/test_charter_status_freshness.py
- tests/specify_cli/test_charter_activate_cli.py
- tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 - Charter status and activation re-pins (#7181, #7182)

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

- FR-004, FR-005, FR-006, C-004. Ten nodes pass, each at least as strong as before.
- Nodes: `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py::test_status_json_error_is_parseable`; `tests/integration/test_charter_status_freshness.py::test_freshness_state_invalid_when_charter_yaml_unparseable`; six in `tests/specify_cli/test_charter_activate_cli.py` (`TestLayerAwareActivation::test_org_artifact_listed_by_all_can_be_activated_and_deactivated`, `TestLayerAwareActivation::test_project_artifact_listed_by_all_can_be_activated`, `TestCascadeScope::test_cascade_all_activates_referenced_kinds`, `TestCascadeScope::test_cascade_scope_limits_to_selected_kind`, `TestCascadeScope::test_cascade_scope_is_not_collapsed_to_bool`, `TestNoCascadeWarning::test_absent_cascade_warns_about_referenced`); and `tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py::test_ambiguous_directive_keeps_siblings_and_reports_json[False]` and `[True]`.

## Context & Constraints

- Spec User Story 3; research.md rows #7181, #7182.
- Two JSON envelopes coexist by design: `charter status` uses `{ok, error:{code,message}}` (#6557 `9bee2389`, `specify_cli.cli.json_contract.json_error`); the interview keeps `_emit_error`'s `{"result":"error","success":false,"error":<str>}` (`src/specify_cli/cli/commands/charter/_common.py`). Never re-pin the interview to the status envelope.
- Canonical assertion pattern to copy: `tests/specify_cli/cli/commands/charter/test_status_broken_charter_6557.py` (about lines 188 and 250).
- Absent-key rule: #6685 (`09bca55275`): a first `charter activate` on a keyless project writes NO allow list for kinds whose `effective_when_absent` is `all`. Seed pattern: `tests/specify_cli/cli/commands/charter/test_charter_activate_commands_core.py` and `tests/charter/activation/test_stored_spelling_6527.py` (`seed_activation_ledger(root, ...)` from `tests/_factories/activation_ledger.py`, already imported in the activate CLI test).
- Collision refusal: `a8dd1812a6` (Decision `file_name_collision`, `ActivationIdCollisionError`): the interview refuses a declared id whose file name another layer uses for a different id; only UNKNOWN ids are still warned-and-skipped.

## Subtasks & Detailed Guidance

### Subtask T008 - `test_status_json_error_is_parseable`

- RED first (see T012 commands). Replace the old `{"error": <str>, "result": "error", "success": False}` equality with
  `assert payload == {"ok": False, "error": {"code": "CHARTER_STATUS_FAILED", "message": "repo root unavailable"}}` plus `assert result.exit_code != 0`. Import `CHARTER_STATUS_FAILED` from `specify_cli.cli.commands.charter.status` if it exists there (matching the #6557 file's style), else use the literal. The test's purpose (error JSON stays parseable, no Rich formatting) is kept and the code is now pinned.

### Subtask T009 - unparseable `charter.yaml` freshness test

- `charter status` now runs the soundness gate (`_assert_charter_sound_for_status`) BEFORE freshness, so an unparseable `charter.yaml` refuses with exit 1 `ACTIVE_CHARTER_CONFIG_INVALID` instead of reporting `freshness.charter_source.state == "invalid"`. Re-pin (rename to `test_unparseable_charter_yaml_refuses_status_with_typed_code`, keep the docstring history and cite #6557): keep the same fixture and the same patch trio as `_invoke_status_json`, but invoke directly (the helper hard-asserts exit 0), assert `result.exit_code == 1`, `payload["ok"] is False`, `payload["error"]["code"] == "ACTIVE_CHARTER_CONFIG_INVALID"`, `"charter.yaml" in payload["error"]["message"]`. The computer-level `invalid` state stays pinned by `tests/specify_cli/charter_freshness/test_computer.py`.

### Subtask T010 - six activate tests (Group A)

- Add a helper next to `_config`: `_seed_present_lists(project_root, *keys)` calling `seed_activation_ledger(project_root, **{key: [] for key in keys})` with a docstring citing #6685. A present (empty) list makes the plan append instead of staying implicit. Keep EVERY existing assertion unchanged. Seeds per node: (1) and (2) `activated_directives`; (3) `activated_agent_profiles`, `activated_directives`, `activated_tactics`; (4) the same three; (5) `activated_agent_profiles`, `activated_directives`, `activated_paradigms`, `activated_tactics`; (6) `activated_agent_profiles` only (so `activated_directives` stays absent and `not data.get(...)` holds).
- Strength extras in the same file (currently passing vacuously because nothing is written): seed `activated_agent_profiles` in `TestNoCascadeWarning::test_no_cascade_does_not_activate_referenced` so the no-cascade exclusion is genuinely exercised; optionally seed the lists in `TestCascadeScope::test_bad_cascade_token_exits_1`.
- Do NOT touch `TestRegistration`, `TestFailClosedConfig`, `TestMissionTypeGeneralized`, or `TestDeactivate` (a seeded list would break `test_none_state_records_an_exclusion`).

### Subtask T011 - two ambiguous-directive interview nodes (Group B)

- Re-pin both params (rename to `test_colliding_directive_selection_refuses_the_interview`, keep `parametrize("required", [False, True])`, keep the fixture and config unchanged). Assert: `exit_code == 1`; JSON `payload["result"] == "error"`, `payload["success"] is False`; the error text contains `Cannot store directive 'TEAM-SEC'`, `used by files in more than one layer`, and both `company/directives/security.directive.yaml` and `team/directives/security.directive.yaml`. For `required=False` also assert `The interview answers were saved; no activation list was written.` and that `TEAM-SEC` is not in `.kittify/config.yaml`. For `required=True` (org-required pre-fill refuses before saving) assert the "answers were saved" sentence is absent.
- Drop only the post-interview assertions that are unreachable under the refusal (their subject is covered by `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py::test_ambiguous_answer_is_reported_without_dropping_resolvable_sibling` and `tests/charter/activation/test_stored_spelling_6527.py` around lines 430-459). Note that in the history. The file's other test, `test_generate_rejects_ambiguous_required_directive_without_interview`, passes and stays untouched.
- Verify the exact message fragments against the live output before asserting (the research quotes them; confirm).

### Subtask T012 - Evidence and neighbour guards

- RED on all ten nodes first (one run per file). Then GREEN plus: `tests/specify_cli/cli/commands/charter/test_status_broken_charter_6557.py`, `tests/charter/activation/test_stored_spelling_6527.py`, `tests/charter/test_interview_leaves_absent_key_absent_6685.py`, `tests/specify_cli/cli/commands/charter/test_charter_activate_commands_core.py`, and whole-file runs of the four owned files (the activate CLI file takes about two minutes).
- Lint and format on the four files. Do not add global state (`test_charter_generate_autotrack.py` is in `tests/architectural/global_state_allowlist/S1.yaml`).
- Strength spot-check (not committed): confirm one re-pinned test fails when its guarded behaviour is reverted (e.g. drop the seed in one activate test and see it go red for the right reason).
- Commit: `test(nightly): re-pin charter status and activation tests to the typed refusal, absent-key and collision contracts (#7181, #7182)`.

## Risks & Mitigations

- Envelope mix-up: asserting the status envelope on the interview would go red immediately. Mitigation: copy shapes from the named sibling files.
- Vacuous passes: the extras in T010 remove assertions that pass for the wrong reason.

## Review Guidance

- Every original assertion in the six activate tests still present; interview nodes assert the interview's own JSON shape; nothing deleted without a named stronger home; RED evidence for all ten nodes.

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
