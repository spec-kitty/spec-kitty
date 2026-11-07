---
work_package_id: WP01
title: The record names no model, and the commit is attributed
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Op record and auto-commit
history:
- at: '2026-11-02T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/invocation/
create_intent:
- src/specify_cli/git/commit_attribution.py
- tests/specify_cli/invocation/test_op_commit_attribution.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/invocation/record.py
- src/specify_cli/invocation/executor.py
- src/specify_cli/invocation/writer.py
- src/specify_cli/invocation/propagator.py
- src/specify_cli/git/commit_attribution.py
- src/specify_cli/cli/commands/profile_invocation.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/specify_cli/invocation/test_record.py
- tests/specify_cli/invocation/test_executor.py
- tests/specify_cli/invocation/test_op_commit_attribution.py
- tests/specify_cli/status/test_resolved_binding_linkage.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The record names no model, and the commit is attributed

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in
the frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## Objectives & Success Criteria

Deliver both halves of issue #7013 on the Op-record seam:

1. **No model identifier in a committed Op record.** `OpStartedEvent` no longer
   declares `model_id`; `ProfileInvocationExecutor.invoke()` no longer fills it.
   A record written before the change still parses and keeps its bytes.
2. **The Op auto-commit carries the operator's attribution.** The message built
   by `_commit_op_record` gains a final `Co-Authored-By: <Name> <email>`
   paragraph, resolved from `.kittify/config.yaml` `commit.co_author` or from an
   explicit per-close value, on both the per-record and doctor-sweep spine paths.
3. **The knock-on effect is honest.** The dispatch→claim seam can no longer
   prove a resolved model, so a `--model` assertion is refused with an
   actionable message and the claim records `RESOLVED_MODEL_ABSENT` — never a
   fabricated value.

Acceptance: `spec.md` FR-001…FR-008, NFR-001…NFR-003, C-001…C-003;
`contracts/op-record-attribution.md` is the normative shape.

## Context & Constraints

- Read `kitty-specs/op-record-model-and-coauthor-01M6EJV5/plan.md`,
  `research.md` (decisions D1–D5) and
  `contracts/op-record-attribution.md` before editing.
- The op record model is `src/specify_cli/invocation/record.py`
  (`OpStartedEvent`, schema v2). `to_jsonl_line()` omits `None` fields, so a
  removed field needs no writer change beyond removing the argument.
- The auto-commit lives in
  `ProfileInvocationExecutor._commit_op_record` →
  `_op_commit_kwargs` → `safe_commit(message=...)`.
- The #6410 skip rules and the #6564 protected-branch refusal run **before** any
  attribution consideration and must keep their current outcomes.
- `kitty-ops/<ULID>.jsonl` files are an immutable archive root
  (`tests/architectural/test_archive_root_byte_identical.py`): never modify one.
- No new dependency, no schema version bump, no new config file.

## Branch Strategy

- **Strategy**: single-branch mission; all work lands on the mission branch and
  merges to `main`.
- **Planning base branch**: main
- **Merge target branch**: main

## Subtasks & Detailed Guidance

### Subtask T001 – Red test: no model identifier in a written record

- **Purpose**: Pin the absence of the field through the production path, with a
  positive control so the probe cannot be vacuous.
- **Steps**: In `tests/specify_cli/invocation/test_executor.py`, replace
  `test_invoke_persists_catalog_winning_model_in_started_event` with a test that
  patches `_compute_recommendation` to return a catalog candidate naming a model
  and asserts the written `started` line has **no** `model_id` and no other key
  whose value is that model string. In `tests/specify_cli/invocation/test_record.py`,
  change `test_mission_and_wp_present_when_set` so it no longer passes
  `model_id`, and add a test that `OpStartedEvent.model_validate` of a legacy
  line carrying `model_id` succeeds **and** `to_jsonl_line()` does not re-emit
  the key. Run them and record the failure before fixing.
- **Files**: `tests/specify_cli/invocation/test_executor.py`,
  `tests/specify_cli/invocation/test_record.py`

### Subtask T002 – Remove the field and its writer

- **Purpose**: Make T001 green with the smallest viable diff.
- **Steps**: Delete `model_id` from `OpStartedEvent`; delete the
  `durable_model_id` computation and the `model_id=` argument in
  `ProfileInvocationExecutor.invoke()`; update the optional-field comments in
  `invocation/writer.py` and the docstring in `invocation/propagator.py` so they
  no longer list `model_id`. Do not add `extra="forbid"` — legacy lines must
  keep validating.
- **Files**: `src/specify_cli/invocation/record.py`,
  `src/specify_cli/invocation/executor.py`,
  `src/specify_cli/invocation/writer.py`,
  `src/specify_cli/invocation/propagator.py`

### Subtask T003 – Red test: the claim refuses a model it cannot prove

- **Purpose**: Prove the removal cannot silently produce a fabricated resolved
  model.
- **Steps**: In `tests/specify_cli/status/test_resolved_binding_linkage.py`,
  update `_write_dispatch_op` to stop passing `model_id`, and rewrite the
  model-specific cases: (a) a `--model` with `--invocation-id` raises
  `ValueError` naming the missing evidence and telling the caller to omit
  `--model`; (b) the same binding still resolves the profile, mission, WP and
  action; (c) the emitted claim delta records `RESOLVED_MODEL_ABSENT` for the
  model slot. Keep the existing "never frontmatter-coerced" positive control.
- **Files**: `tests/specify_cli/status/test_resolved_binding_linkage.py`

### Subtask T004 – Narrow the dispatch binding

- **Purpose**: Make T003 green.
- **Steps**: In `src/specify_cli/cli/commands/agent/workflow.py`, drop
  `op_model = event.model_id` and the model-equality branch; raise a clear
  `ValueError` when `--model` is supplied with `--invocation-id` (the Op no
  longer carries a model to correlate), keep the profile/mission/WP/action
  correlation untouched, and leave `resolved_model = None` so the status seam
  records explicit-absence. Update `_MODEL_OPT_HELP` to say what the flag now
  means. Check the `--model` help text on `agent tasks move-task`
  (`src/specify_cli/cli/commands/agent/tasks.py`) is still accurate — if not, fix
  the help string only.
- **Files**: `src/specify_cli/cli/commands/agent/workflow.py`

### Subtask T005 – Red tests: the trailer

- **Purpose**: Drive the whole attribution half red before implementing it.
- **Steps**: Create `tests/specify_cli/invocation/test_op_commit_attribution.py`
  using the existing git fixtures in
  `tests/specify_cli/invocation/_op_git.py` (`track_op_record_on_current_branch`,
  `checkout_issue_branch`, `run_git`). Cover, each through `complete_invocation`:
  1. `commit.co_author` configured → `git log -1 --format=%B` ends with
     `Co-Authored-By: <value>`;
  2. a doctor-sweep close (`closed_by="doctor_sweep"`) → the spine commit carries
     it too;
  3. no `commit.co_author` → the message is exactly the bare subject (the
     pre-change shape), with a configured-value assertion on the same fixture as
     the positive control;
  4. an explicit `co_author=` overrides the configured value (only the explicit
     one appears);
  5. a malformed configured value → `OpCommitOutcome(committed=False)` whose
     refusal names `commit.co_author`, the completed event still on disk, and no
     new commit;
  6. a blank explicit value is a usage error / `ValueError` before any write.
  Also cover a value already spelled `Co-Authored-By: ...` not being
  double-prefixed.
- **Files**: `tests/specify_cli/invocation/test_op_commit_attribution.py`

### Subtask T006 – The canonical trailer resolver

- **Purpose**: One owner for "what is the operator's attribution trailer".
- **Steps**: Add `src/specify_cli/git/commit_attribution.py` with:
  `InvalidCoAuthor` (a `ValueError` subclass) and
  `resolve_co_author_trailer(repo_root, explicit=None) -> str | None`. Read
  `.kittify/config.yaml` with `ruamel.yaml`'s `YAML(typ="safe")`, the same shape
  `review/test_timeout.py` uses (mapping checks, absent file → no value), accept
  `commit.co_author` as `Name <email>` or a full `Co-Authored-By: Name <email>`,
  normalise to the single `Co-Authored-By: ` prefix, treat a blank value as
  absent, and raise `InvalidCoAuthor` for anything else (the message names
  `commit.co_author`). Add focused unit tests in the same new test file for the
  parser (`Name <email>`, already-prefixed, blank, malformed, absent key, absent
  file).
- **Files**: `src/specify_cli/git/commit_attribution.py`

### Subtask T007 – Wire it into the commit and the CLI

- **Purpose**: Make T005 green.
- **Steps**:
  - `complete_invocation(..., co_author: str | None = None)` accepts the
    override and passes it to `_commit_op_record`.
  - `_commit_op_record` resolves the trailer once, then appends it as the final
    paragraph of `message` for both the per-record and the spine commit. Resolve
    **after** the skip/protected-branch decisions, so those outcomes are
    unchanged; an `InvalidCoAuthor` becomes
    `OpCommitOutcome(committed=False, refusal=str(exc))` — never an exception
    out of `complete_invocation`.
  - `profile-invocation complete` gains
    `--co-author` (help: operator attribution trailer for the Op commit;
    overrides `commit.co_author`) and passes it through; a blank value is a
    `typer.BadParameter` (exit 2) before anything is written.
  - The `--json` payload shape is contract-frozen: do not add fields to it.
- **Files**: `src/specify_cli/invocation/executor.py`,
  `src/specify_cli/cli/commands/profile_invocation.py`

### Subtask T008 – Prove the halves and run the gates

- **Purpose**: Non-vacuity and no fake green.
- **Steps**:
  1. Run the targeted suites:
     `uv run pytest tests/specify_cli/invocation tests/specify_cli/status/test_resolved_binding_linkage.py -q`.
  2. Revert the schema half in a scratch stash and confirm the T001/T003 tests go
     red; restore, revert the attribution half, confirm T005 goes red; restore.
     Record both observations with
     `spec-kitty agent tasks add-history WP01 --note "..."` (the event log is the
     owner of this record; a `code_change` WP may not write into `kitty-specs/`).
  3. Run `make test-fast` (never a full heavy suite).
  4. `git status --short -- kitty-ops/` must show no modified pre-existing
     `<ULID>.jsonl`.
- **Files**: none (the observation goes to the WP event log via `add-history`).

## Test Strategy

Red first, through production entry points:
`ProfileInvocationExecutor.invoke`, `complete_invocation`,
`_resolve_dispatch_binding`, and the `profile-invocation complete` CLI. Assert on
the written JSONL and on `git log -1 --format=%B`, not on helper internals. Keep
the "no trailer configured" ratchet on the same fixture as the configured case so
neither can drift.

## Definition of Done

- T001–T008 done, each test written before its fix.
- No `model_id` in any record written by the new code path; legacy lines still
  parse and are never rewritten.
- Trailer present on both commit paths when configured, absent and unchanged when
  not, explicit override wins, malformed config refuses visibly.
- `make test-fast` green; targeted suites green; no pre-existing `kitty-ops/`
  file modified.

## Risks & Reviewer Guidance

- Review the refusal path first: a close must never fail because of attribution,
  and must never commit unattributed when a trailer was configured.
- Check that `contracts/op-record-attribution.md` R-rules all have a test.
- Check the claim seam: no model string may reach the status delta except
  `RESOLVED_MODEL_ABSENT`.
