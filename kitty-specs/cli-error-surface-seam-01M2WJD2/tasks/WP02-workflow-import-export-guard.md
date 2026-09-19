---
work_package_id: WP02
title: workflow import/export input guard (#4738)
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Adoption
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/workflow.py
create_intent:
- tests/specify_cli/cli/commands/test_workflow_guard.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/workflow.py
- src/runtime/next/_internal_runtime/workflow_registry.py
- tests/specify_cli/cli/commands/test_workflow_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – `workflow import`/`export` input guard (#4738)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## 🔴 BINDING SQUAD AMENDMENTS (post-tasks fold — read before implementing)

These override any conflicting guidance below.

1. **Re-parent `UnknownWorkflowError` as a `GuardedReadError` subclass** in `workflow_registry.py` (owned by this WP) so the global hook renders it cleanly. Today `workflow.py` has NO try/except around `load_workflow_file`, so `UnknownWorkflowError` also tracebacks; the hook only catches `GuardedReadError`. Add a subtask/step to T008. (This satisfies the spec Edge Case + Done-when "workflow_id-mismatch presents via the hook".)
2. **Guard the raw read at `workflow.py:85`** — `_copy_workflow` does `source.read_bytes()`, a raw read reachable from both `import` and `export`. Route it through `kernel.read_guarded` (raising `WorkflowFileError`) so WP08's construction gate finds no unguarded read in this in-scope module. Add to T008 (owned_files already covers `workflow.py`).
3. **"Remove the command-local try/except" is a no-op** — there is none today around `load_workflow_file` (import `:62`, export `:45`). Treat T008/Review-Guidance "removal" as "confirm none exists; if present, remove it."
4. **Depends on WP01** (frontmatter corrected). Do not start until `kernel.read_guarded` + `GuardedReadError` + the global hook exist.

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`spec-kitty workflow import <file>` and `spec-kitty workflow export <id> <dest>`
currently crash with a raw traceback (`yaml.YAMLError`, `pydantic.ValidationError`,
wrong-top-level-type, unreadable file) instead of a clean typed error. Close #4738
by routing both commands' `load_workflow_file` calls through the WP01 guarded-read
seam, so the crash surfaces as a `WorkflowFileError` the global hook presents.

**Done when**:
- `workflow import bad.yaml` (malformed YAML) → exit 1, clean message naming the
  file, zero traceback frames.
- `workflow import` with valid-YAML-but-wrong-schema, or a wrong-top-level-type
  file (e.g. a YAML list instead of a mapping) → the same clean "invalid workflow
  file" error, no pydantic traceback.
- `workflow import` of an unreadable file (permission denied / missing) → the same
  clean error, no `OSError` traceback.
- `workflow export <id> <dest>` of a corrupt resolved/override workflow → the same
  clean typed error path, no traceback (acceptance scenario 3 in spec.md — this is
  the export path FR-004 explicitly calls out as needing its own scenario, since
  research.md flagged it as previously unverifiable).
- `--json` on either command emits exactly one JSON object on stdout under
  `contracts/error-envelope.md`'s shape.
- The existing `UnknownWorkflowError` message (workflow_id mismatch) still presents
  correctly via the hook — this mission changes surface, not behavior, for that
  case (spec.md Edge Cases).

## Context & Constraints

**Depends on WP01.** Do not start until `kernel.guarded_read.read_guarded`,
`kernel.errors.GuardedReadError`, and the global Typer hook exist and are merged/
available on your branch — you are a pure consumer of that seam here.

- Follow the adoption pattern in `kitty-specs/cli-error-surface-seam-01M2WJD2/
  quickstart.md` ("Reading a state/config/input file in a command") verbatim —
  do not re-derive a different shape. The command stops try/excepting for
  presentation; the global hook renders `WorkflowFileError`.
- **Reference the existing canonical catch tuple.** `workflow_registry.py:176`
  (inside `list_available_workflows`) already guards `load_workflow_file` with
  `except (OSError, UnknownWorkflowError, ValidationError, yaml.YAMLError):` — that
  tuple (minus `UnknownWorkflowError`, which is a distinct, already-handled domain
  case, not a read failure) is your reference set for the `errors=` argument you
  pass to `read_guarded`/the guard you add.
- `import_workflow` calls `load_workflow_file(source)` at
  `src/specify_cli/cli/commands/workflow.py:62`; `export_workflow` calls
  `load_workflow_file(source, requested_workflow_id=workflow_id)` at
  `src/specify_cli/cli/commands/workflow.py:45`. Both are candidates for the guard;
  decide (and document in your Activity Log) whether the guard wraps the call
  inside `workflow.py` or inside `load_workflow_file` itself in
  `workflow_registry.py` — prefer guarding as close to the actual `open`/`yaml.safe_
  load`/`model_validate` call as possible so `list_available_workflows`'s existing
  `except (...)` catch (which deliberately swallows failures to skip unlisted
  workflows) keeps working unchanged.
- Define `WorkflowFileError` as a `GuardedReadError` subclass in
  `src/runtime/next/_internal_runtime/workflow_registry.py` (co-located with the
  function it guards) — do not invent a second error type elsewhere for the same
  failure mode (C-002, single canonical authority).
- Charter constraints: complexity ≤ 15, ruff + mypy clean with zero new
  suppressions, ≥ 90% new-code coverage, `--mission` terminology only (this WP has
  no `--feature`/`--mission` surface itself, but do not introduce one).
- ATDD discipline (C-003): T007's red-first regression must run through the real
  `workflow import`/`workflow export` CLI entry point (via Typer's `CliRunner` or
  equivalent), not by calling `load_workflow_file` directly — the traceback you are
  fixing is what the operator sees at the command boundary.

## Branch Strategy

- **Strategy**: Single branch — all WPs land directly on the mission branch.
- **Planning base branch**: `fix/cli-error-surface-seam`
- **Merge target branch**: `fix/cli-error-surface-seam` (a PR later targets `main`)

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first: `workflow import`/`export` bad-file tracebacks

- **Purpose**: pin the current crash with an issue-referenced regression BEFORE
  touching production code (C-003, red-first).
- **Steps**: Write `@pytest.mark.regression` tests in
  `tests/specify_cli/cli/commands/test_workflow_guard.py` that invoke the real
  `workflow import`/`workflow export` Typer commands (via the CLI test runner) with:
  (a) a malformed-YAML file, (b) a valid-YAML file with the wrong schema (or wrong
  top-level type, e.g. a bare list), (c) an unreadable file (e.g.
  `os.chmod(path, 0o000)` — skip gracefully on platforms where this doesn't apply,
  e.g. Windows/root), and (d) for export, a corrupt resolved/override workflow file
  on disk. Confirm each test is RED on the current tree (asserts a traceback /
  non-zero unexpected exit today) before writing the fix. Reference #4738 in the
  test docstring/marker context.
- **Files**: `tests/specify_cli/cli/commands/test_workflow_guard.py` (new).
- **Parallel?**: Yes — independent of WP03–WP07 (distinct owned files).
- **Notes**: Use a temp directory fixture for the workflow files; do not depend on
  any repo-committed fixture that might already be gitignored (see the
  "Gitignored test fixtures false-green" gotcha — verify your fixtures are
  git-trackable or created at test time).

### Subtask T008 – `WorkflowFileError` + guard the `load_workflow_file` callers

- **Purpose**: FR-003/FR-004 — turn the four red scenarios green via the WP01 seam.
- **Steps**: Add `class WorkflowFileError(GuardedReadError): ...` to
  `src/runtime/next/_internal_runtime/workflow_registry.py`. Wrap the read+parse+
  validate sequence inside (or immediately around) `load_workflow_file` with
  `kernel.guarded_read.read_guarded`, passing `errors=(yaml.YAMLError,
  pydantic.ValidationError)` (plus any additional exception your wrong-top-level-
  type repro surfaces — e.g. `AttributeError`/`TypeError` if `yaml.safe_load`
  returns a non-mapping and the code indexes into it before pydantic validation;
  add that to the tuple with a one-line comment explaining why) and
  `error_cls=WorkflowFileError`. Remove `import_workflow`'s and `export_workflow`'s
  own try/except-for-presentation in `workflow.py` — the command no longer catches
  for presentation; the global hook (WP01) renders `WorkflowFileError`. Keep
  `list_available_workflows`'s existing `except (OSError, UnknownWorkflowError,
  ValidationError, yaml.YAMLError):` untouched — it deliberately swallows to skip,
  which is a different (non-presentation) concern from this guard.
- **Files**: `src/runtime/next/_internal_runtime/workflow_registry.py`,
  `src/specify_cli/cli/commands/workflow.py`.
- **Parallel?**: Yes.
- **Notes**: If `load_workflow_file`'s signature or return shape is used by other
  callers beyond `import_workflow`/`export_workflow`/`list_available_workflows`,
  grep for all call sites first (`grep -rn "load_workflow_file" src/ tests/`) and
  confirm none of them relies on catching a bare `yaml.YAMLError`/
  `ValidationError` directly at their own call site — if one does, that site now
  needs to catch `WorkflowFileError` (or `GuardedReadError`) instead, or it will
  silently stop catching once you route the raise through the new type.

### Subtask T009 – Green including `--json` envelope

- **Purpose**: prove the fix and lock the machine contract (NFR-002).
- **Steps**: Flip T007's regressions to assert the new behavior: exit 1, an
  actionable message naming the file, zero traceback frames on any stream. Add a
  `--json` variant for at least the malformed-YAML import case and the corrupt-
  export case, asserting stdout is exactly one parseable JSON object matching
  `contracts/error-envelope.md` (`error`, `kind` = `"WorkflowFileError"`, `path`).
  Re-run the full `test_workflow_guard.py` file plus the WP01 back-compat
  regression (`tests/specify_cli/test_error_backcompat.py`) to confirm this WP's
  subclassing didn't disturb it.
- **Files**: `tests/specify_cli/cli/commands/test_workflow_guard.py`.
- **Parallel?**: Yes.
- **Notes**: Also assert the untouched `UnknownWorkflowError` case (workflow_id
  mismatch) still presents its existing message via the hook, unchanged in wording
  — spec.md's Edge Cases require this to be presentation-only churn, not a
  behavior change.

## Test Strategy

- `tests/specify_cli/cli/commands/test_workflow_guard.py` — the full red-then-green
  suite from T007/T009, run through the real Typer CLI entry point.
- Run `make test-fast` plus this WP's targeted module tests: any existing
  `tests/` file(s) covering `workflow_registry.py` and `workflow.py` (mirror the
  source tree; if none obviously exists, `grep -rl "workflow_registry\|load_workflow_file" tests/ --include="*.py"`)
  to confirm no existing test regressed.
- Typecheck the two owned source files with the project's configured mypy
  invocation — a green pytest run does not substitute for clean mypy diagnostics.
- `ruff check .` and `ruff format --check .` (whole-repo, per `CLAUDE.md`) before
  handing off.

## Risks & Mitigations

- **Silently narrowing `list_available_workflows`'s swallow-to-skip behavior**:
  that function's `except (...)` intentionally treats a bad workflow file as "not
  listed," not as a presentation error. Do not route it through the hook or
  change its control flow — only `import_workflow`/`export_workflow` change
  surface.
- **Missed downstream catcher**: a caller of `load_workflow_file` outside
  `workflow.py` that catches `yaml.YAMLError`/`ValidationError` directly will stop
  catching once the raise becomes `WorkflowFileError`. Census all call sites before
  finalizing (see T008 notes).
- **Wrong-top-level-type case not covered by the declared tuple**: if a bare
  YAML list/scalar produces an exception type outside `(yaml.YAMLError,
  ValidationError)` (e.g. `AttributeError` from indexing a list), add it to the
  declared tuple explicitly rather than widening to a bare `Exception` catch.

## Review Guidance

- Confirm the red-first commits/history show the regression failing on the
  pre-fix tree (or that the Activity Log documents this) before the fix landed.
- Confirm `import_workflow`/`export_workflow` no longer try/except for
  presentation — the hook is the only renderer.
- Confirm the `--json` envelope matches `contracts/error-envelope.md` exactly
  (`error`/`kind`/`path` keys, single object, nothing else on stdout).
- Confirm `list_available_workflows`'s existing swallow-to-skip catch is
  untouched and its own tests (if any) still pass.
- If typed sources changed, confirm the implementer ran the configured mypy check
  in addition to pytest and that mypy diagnostics passed.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started implementation
- 2026-01-12T11:00:00Z – codex – Implementation complete, ready for review
- 2026-01-12T11:30:00Z – claude – Review passed, all tests passing  ← LATEST (at bottom)
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-09-19T10:45:02Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### Optional Phase Subdirectories

For large features, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
