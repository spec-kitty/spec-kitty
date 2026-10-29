---
work_package_id: WP04
title: Off-renderer owned refusals, cross-command pin, changelog
dependencies:
- WP03
requirement_refs:
- FR-006
- FR-015
- NFR-001
- SC-002
- SC-004
planning_base_branch: issue-6354-owned-issue-verdict-cleanup
merge_target_branch: issue-6354-owned-issue-verdict-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-6354-owned-issue-verdict-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6354-owned-issue-verdict-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
base_commit: 6b36738295f1b7107f77b7b16d0bfafa7351f414
created_at: '2026-10-29T05:14:46.460899+00:00'
subtasks:
- T017
- T018
- T019
- T020
- T021
phase: Phase 4 - Close the class
history:
- at: '2026-10-27T19:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/integration/test_owned_refusal_c2_shape.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_create.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/agent/test_agent_feature.py
- tests/specify_cli/cli/commands/agent/test_mission_create*.py
- tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py
- tests/integration/test_owned_refusal_c2_shape.py
- tests/architectural/test_json_contract_enumeration.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Off-renderer owned refusals, cross-command pin, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP04 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

WP02 moved every renderer caller to the C2 owned refusal and provided the single
non-validating builder `owned_refusal_payload` in
`src/specify_cli/cli/commands/_owned_checkout.py`. Two owned refusals still bypass it:

- `agent mission create` (`agent/mission_create.py:509-530`) hand-builds `{success, error_code, error}` through `_emit_json` (which also adds `spec_kitty_version`).
- the move-task owned catch-all (`agent/tasks_move_task.py:1726-1740`) prints `{error_code, error}` for **any** `ActionContextError` code on an owned run.

Then pin the whole class with one test and record the change.

Done when:
- FR-006: both paths emit `owned_refusal_payload(...)` (mission create with `stamp_version=True`, which `_emit_json` already provides; see T017).
- FR-015 / SC-002: one parametrized test drives an owned refusal through every in-scope `--json` command and asserts the exact contract, with a same-fixture success control (SC-004).
- C2 enumeration gate records what its structure supports (T020).
- `docs/changelog/CHANGELOG.md` `[Unreleased]` names both issues.

## Context & Constraints

- Contract and per-command table: `contracts/owned-refusal-envelope.md`, `data-model.md`.
- research.md §1.3 rows 22-23.
- The move-task catch-all keeps accepting any code (Engineering Alignment 4). Do not route it through `emit_owned_refusal` (its registry check would raise on unregistered codes; see `test_context_error_envelope_is_opt_in`).
- ATDD: T017/T018 tests red first; T019 is written after them and must pass.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6354-owned-issue-verdict-cleanup`
- **Merge target branch**: `issue-6354-owned-issue-verdict-cleanup`

```bash
spec-kitty agent action implement WP04 --agent claude --mission owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
```

## Subtasks & Detailed Guidance

### Subtask T017 – `agent mission create` owned refusal → C2

1. Red: re-pin `tests/agent/test_agent_feature.py:725-727` (today `{"success","error_code","error"} <= keys` and "no `message` key") to:
   `payload["ok"] is False`, `payload["error"] == {"code": <code>, "message": <msg>}`, the
   top-level keys are `{"ok", "error", "spec_kitty_version"}` (plus any mission alias keys
   `_emit_json` adds, so check what `_with_mission_aliases` does to a payload without
   mission keys; if it adds nothing, assert exact equality of the key set). Also re-pin
   any owned-refusal shape assertion in `tests/specify_cli/cli/commands/agent/test_mission_create*.py`
   (grep `error_code` / `success`). Leave non-owned create errors
   (`CoordinationBranchDiverged`, `MissionCreationError`) untouched (FR-011 controls).
2. Implement in `mission_create.py` (~509-530): `_emit_json(owned_refusal_payload(exc.code, error_msg))`.
   `_emit_json` stamps `spec_kitty_version` (via `_with_cli_version`, which skips the key
   if present), so do not also pass `stamp_version=True`; the result has one stamp either
   way, and `_emit_json` keeps the module's single emit path. Rewrite the comment block
   (it says "mirrors emit_owned_refusal ... exactly {success, error_code, error}") to name the
   C2 contract and ADR `2026-10-27-2`. Human mode unchanged.

### Subtask T018 – move-task owned catch-all → C2

1. Red: in `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py`, re-pin
   the catch-all's JSON assertions (around :878, :983, :1048: check which pin the owned
   catch-all versus the ordinary `{result: "error", ...}` diagnostics; only the owned
   catch-all changes). Include one case with an **unregistered** code (the catch-all's
   opt-in behaviour) to prove the non-validating builder is used.
2. Implement (~1737): `print(json.dumps(owned_refusal_payload(e.code, str(e)), indent=2))`.
   Update the comment: same shape as `emit_owned_refusal`, built by the shared
   non-validating builder because this arm accepts any `ActionContextError` code.

### Subtask T019 – Cross-command shape pin

Create `tests/integration/test_owned_refusal_c2_shape.py`:
- **Fixture**: one module-scoped owned setup (reuse the `checkouts` pattern from
  `tests/integration/test_explicit_checkout_commands.py`; if that fixture is
  function-scoped, build one module-scoped equivalent from the same factory helpers, or
  accept function scope and keep the parameter list as short as is honest). Measure and
  record the runtime in the history note.
- **Trigger**: the cheapest refusal that every command shares: `--owned-checkout <repository root checkout>`
  → `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` (or the code the minter actually returns for that
  claim; read it from `mission_runtime.OwnedRefusalCode`).
- **Parametrize** over every in-scope command that has `--json` and an `--owned-checkout`
  option: `agent issue-verdict`, `agent acceptance-verdict`, `agent context resolve`, `next`,
  `agent mission setup-plan`, `agent mission finalize-tasks`, `agent mission check-prerequisites`,
  `agent mission record-analysis`, `agent mission create`, `agent tasks status`,
  `agent tasks move-task`, `agent tasks mark-status`, `agent tasks map-requirements`,
  `spec-commit`, `accept`, `charter generate`, `dispatch`, `invocations list`,
  `profile-invocation complete`, `agent decision repair-runtime-lock`, and one
  `agent decision` verb (e.g. `list` or `open`). Each param carries its argv, its expected
  `context` (or `None`) and whether it stamps `spec_kitty_version` (table in `data-model.md`).
- **Assert per case**: exit code 1; `json.loads(stdout)`; `payload["ok"] is False`;
  `set(payload["error"]) == {"code", "message"}`; `payload["error"]["code"]` is the
  expected code; `set(payload) - {"ok", "error"}` equals exactly the expected optional keys;
  no top-level `error_code`; no file created or modified in either checkout (snapshot
  `git status --porcelain` before/after for both). stdout only (stderr carries no JSON).
- **Same-fixture success control** (SC-004, FR-011): for 2-3 representative commands
  (e.g. `agent tasks status`, `agent context resolve`, `next` query), run with a **valid**
  `--owned-checkout` and assert the success payload has no `ok: false` / `error` and still
  carries its documented success keys. This proves the probe sees real output.
- If a command cannot be driven cheaply (e.g. needs heavy state), keep it in the param
  list with a precondition helper; do not drop it silently. If one truly cannot be
  reached, mark that case `xfail(strict=True, reason=...)` with a tracker reference and say
  so in the history note (do not skip).

### Subtask T020 – C2 enumeration gate

Read `tests/architectural/test_json_contract_enumeration.py` (`ADOPTED` :100-148,
`PARSEABLE` :150-212, `DEFERRED` :227-473, `assert_json_result` :64-71). If the gate can
express "this command's owned-refusal error path is C2-adopted" (e.g. a case entry per
error scenario), add owned-refusal entries for the renderer callers. If its structure is
per-command only (one shape per command for every error), do **not** promote commands to
ADOPTED (their non-owned errors are not C2). Instead add a short docstring note pointing at
`tests/integration/test_owned_refusal_c2_shape.py` as the owned-refusal pin and ADR
`2026-10-27-2`. Do not loosen any existing assertion. Record which option you took.

### Subtask T021 – CHANGELOG

`docs/changelog/CHANGELOG.md`, `[Unreleased]` section, matching its existing style
(read 2-3 recent entries first). Entry content:
- **Fixed** (#6354): recording an issue verdict on an owned Mission that still holds a legacy `issue-matrix.md` now migrates it into the owned checkout instead of failing.
- **Changed** (#6353, breaking for JSON consumers of owned refusals): every owned-checkout refusal in `--json` mode now prints the CLI's C2 error contract `{"ok": false, "error": {"code", "message"}}` (plus `context` / `spec_kitty_version` where listed); the top-level `error_code`, `success`, `result` keys of the old per-command shapes are gone; the `agent decision` verbs' owned refusal moves to stdout; orchestrator-api contract `1.19.0`. ADR `2026-10-27-2`.

## Test Strategy

```bash
uv run --frozen pytest tests/agent/test_agent_feature.py tests/specify_cli/cli/commands/agent/test_mission_create*.py \
  tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py -q
uv run --frozen pytest tests/integration/test_owned_refusal_c2_shape.py -q
uv run --frozen pytest tests/architectural/test_json_contract_enumeration.py tests/architectural/test_owned_checkout_single_authority.py -q
uv run --frozen ruff check <touched>; uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy src/specify_cli/cli/commands/agent/mission_create.py src/specify_cli/cli/commands/agent/tasks_move_task.py
```

## Risks & Mitigations

- The cross-command test is slow. Keep one fixture and record its runtime; do not split into many modules.
- A command whose `--owned-checkout` refusal is raised before `--json` handling (human only) is out of the JSON matrix; list it in a comment with the reason.

## Review Guidance

- Every in-scope `--json` command is a parameter (compare against research §1.3); none dropped silently.
- Success control present on the same fixture.
- Mission create's non-owned errors unchanged; move-task's unregistered-code case covered.
- CHANGELOG entry present and accurate.

## Progress & Status

- `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP04 --to <status>`
- `spec-kitty agent tasks status`
