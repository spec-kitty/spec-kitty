---
work_package_id: WP01
title: Reject --mission on non-mission-scoped migrate commands
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: fix/migrate-reject-mission-flag
merge_target_branch: fix/migrate-reject-mission-flag
branch_strategy: Planning artifacts for this mission were generated on fix/migrate-reject-mission-flag. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/migrate-reject-mission-flag unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-10-17T16:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/migrate_cmd.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/migrate_cmd.py
- tests/cli/test_mission_agnostic_flag.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Reject --mission on non-mission-scoped migrate commands

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Make the five non-mission-scoped `migrate` subcommands **reject** `--mission`
with an explicit, scope-neutral usage error (exit 2) instead of silently
accepting and ignoring it. The five commands:

| Command | Decorator (approx line) | Scope |
|---------|------------------------|-------|
| `charter-encoding` | `migrate_cmd.py:1013` | corpus-walk |
| `backfill-provenance` | `migrate_cmd.py:1094` | corpus-walk |
| `rewrite-opposed-by` | `migrate_cmd.py:1252` | pack-scoped (`--pack`) |
| `rebaseline-dossier-hashes` | `migrate_cmd.py:1532` | corpus-walk |
| `repin-hooks` | `migrate_cmd.py:~1599` | repo-repair |

Success = FR-001..FR-005, NFR-001..NFR-002, C-001..C-003, SC-001..SC-002 in
[spec.md](../spec.md) hold. Specifically:
- Each of the five exits 2 with a "not mission-scoped" message on `--mission <v>` and `--mission=<v>`.
- Each still runs normally when `--mission` is absent (unchanged `--dry-run`/`--json`).
- Every OTHER mission-agnostic leaf command still accepts `--mission` (#3953 invariant preserved).
- `--help` byte-identical; complexity ≤15; no blanket suppressions.

## Context & Constraints

- **Plan**: [plan.md](../plan.md) IC-01. **Research**: [research.md](../research.md) Decisions 3–5. **Charter**: `.kittify/charter/charter.md`.
- **Seam (C-001, verified by grounding squad)**: add a `CorpusWideCommand(TyperCommand)` in `migrate_cmd.py`. Because it is a `TyperCommand` *subclass*, the walker `make_leaf_commands_mission_agnostic` (`src/specify_cli/cli/helpers.py:222-239`) leaves it alone (it retargets only `cls is None or cls is TyperCommand`). **Do NOT edit `cli/helpers.py`.**
- **Reuse the existing #4964 machinery in `migrate_cmd.py`** (do not hand-roll, do not import real `click` for a new Option/Command):
  - `_given_on_command_line(ctx, name)` (~line 178) — true when the flag was typed on the command line (click-era-agnostic via `parameter_source_name`).
  - `_usage_error_class(ctx)` (~line 154) — resolves the `UsageError` from the invoking context's own click universe (real `click` ≤0.25 vs vendored `typer._click` 0.26+). Raising this gives a clean exit 2 in both eras; a real-`click` `UsageError` in a vendored dispatch escapes as a traceback (NFR-001).
  - `_with_ignored_mission_option(params)` and `_MISSION_OPTION_NAME` from `cli/helpers.py` — keep the hidden `--mission` option declared (so it parses and `--help` is unchanged), then reject it in `parse_args`.
- **Derived param name is `"mission"`** (empirically confirmed: the hidden `expose_value=False` option records `parameter_source == COMMANDLINE` when given, and its param name is `mission`).

## Branch Strategy

- **Strategy**: single_branch (direct in the write checkout)
- **Planning base branch**: fix/migrate-reject-mission-flag
- **Merge target branch**: fix/migrate-reject-mission-flag (PR → main)

> These fields are populated/normalized by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first regression repro (RED before the fix)

- **Purpose**: ADR 2026-07-17-1 red-first. Prove the defect through the real CLI entry point before touching the fix.
- **Steps**:
  1. In `tests/cli/test_mission_agnostic_flag.py`, add a parametrized test over the five command paths (`["migrate","backfill-provenance"]`, `["migrate","charter-encoding"]`, `["migrate","rebaseline-dossier-hashes"]`, `["migrate","rewrite-opposed-by"]`, `["migrate","repin-hooks"]`) that invokes each with `--mission ghost` via `CliRunner().invoke(app, [...])` and asserts `result.exit_code == 2` and a "not mission-scoped" substring in the output.
  2. Mark it `@pytest.mark.regression` and pin the issue: `@pytest.mark.regression` plus a comment `# red-first repro for #5294` (follow the repo's regression-marker convention — check a sibling `p0_repro`/`regression` usage first).
  3. Run it and CONFIRM IT IS RED on current code (the commands currently exit 0). Record the red output.
- **Files**: `tests/cli/test_mission_agnostic_flag.py`
- **Parallel?**: No (precedes the fix).
- **Notes**: Use the module's existing `_resolve`/`CliRunner` idiom. Keep the repro minimal.

### Subtask T002 – Add `CorpusWideCommand` to `migrate_cmd.py`

- **Purpose**: The rejecting command class (FR-001, FR-004, NFR-001, C-001, C-003).
- **Steps**:
  1. Define (near the #4964 helpers) a **scope-neutral** message constant, e.g. `_NOT_MISSION_SCOPED_MSG` — "`--mission` is not supported by this command: it is not mission-scoped. Drop `--mission` and re-run." **Do NOT claim "runs across the whole corpus/repository"** — that is inaccurate for `rewrite-opposed-by` (pack-scoped) and `repin-hooks` (repo-repair), and would contradict C-003 while still shipping green (tests assert only the `not mission-scoped` substring). Keep ≤ the S1192 threshold by hoisting it once.
  2. Define `class CorpusWideCommand(TyperCommand)` with:
     - `get_params(self, ctx)` → `return _with_ignored_mission_option(super().get_params(ctx))` (keeps the hidden option; `--help` unchanged).
     - `parse_args(self, ctx, args)` → call `super().parse_args(ctx, args)`, then `if _given_on_command_line(ctx, "mission"): raise _usage_error_class(ctx)(_NOT_MISSION_SCOPED_MSG, ctx=ctx)`, then `return` the parsed result.
  3. Keep cyclomatic complexity ≤15; add a focused unit test if the class grows a branch (C-002).
- **Files**: `src/specify_cli/cli/commands/migrate_cmd.py`
- **Parallel?**: No.
- **Notes**: Import `TyperCommand` the same way the module/`helpers.py` already does (typer-native). Do not add a real-`click` import.

### Subtask T003 – Retarget the five decorators

- **Purpose**: Point the five commands at the new class (FR-001).
- **Steps**:
  1. Add `cls=CorpusWideCommand` to each of the five `@app.command(name=...)` decorators: `charter-encoding`, `backfill-provenance`, `rewrite-opposed-by`, `rebaseline-dossier-hashes`, `repin-hooks`.
  2. Leave every mission-scoped command (`backfill-identity`, `backfill-merge-commit`, `backfill-topology`, `backfill-mission-type`, `normalize-lifecycle`, `backfill-runtime-state`, `backfill-wp-status`) UNTOUCHED — they declare a real `--mission`.
  3. Run T001's repro — it must now be GREEN.
- **Files**: `src/specify_cli/cli/commands/migrate_cmd.py`
- **Parallel?**: No (depends on T002).
- **Notes**: `backfill-wp-status` DOES take a real `--mission` — do NOT add it to the reject-set.

### Subtask T004 – Amend tree-wide invariant tests + add positive tests

- **Purpose**: FR-002, FR-003, FR-005. Keep the #3953 invariant honest.
- **Steps**:
  1. Amend `test_every_leaf_command_accepts_mission` and `test_reregistration_keeps_the_invariant`: define the five-command reject-set; assert every OTHER leaf accepts `--mission`, and assert the five are the reject-set (not silently folded into "accepts"). These tests must express the new intent, not merely stay green.
  2. Add positive tests: for each of the five, `--mission=ghost` (equals form) → exit 2 + message (FR-002); and run each with NO `--mission` (e.g. `--dry-run --json` in a tmp project or with a mocked backend) and assert it behaves as before — exit 0 / unchanged (FR-003 positive control).
  3. Confirm `tests/architectural/test_json_contract_enumeration.py` still passes (it invokes the five with `--dry-run`/`--json` only — default source, must NOT be rejected).
  4. Do NOT add a new assertion on the real app's `make_leaf_commands_mission_agnostic` return total: the five now fall outside the walker's retarget count. The existing exact-count assertions (lines ~136/278/293/327) are over synthetic apps and are unaffected — leave them, just don't introduce a real-app total that would now be wrong.
- **Files**: `tests/cli/test_mission_agnostic_flag.py`
- **Parallel?**: No (depends on T003).
- **Notes**: For FR-003's no-`--mission` positive control, prefer the lightest fixture that exercises the parse path without a slow corpus walk (a tmp project root, or assert parse-acceptance via `--help`/default-source).

### Subtask T005 – Convert transitional repro; verify --help; run blast radius

- **Purpose**: ADR 2026-07-17-1 (regression repros are transitional); NFR-002; blast-radius proof.
- **Steps**:
  1. Fold T001's `@pytest.mark.regression` repro into the focused positive tests from T004 (or move it to a permanent unit home) — do not leave it marked `regression` once the behavior has a focused test.
  2. Verify NFR-002: `spec-kitty migrate <cmd> --help` stdout is unchanged for each of the five (option stays hidden).
  3. Run the blast radius and record pass/fail counts in the PR: `tests/cli/test_mission_agnostic_flag.py`, `tests/cli/test_migrate_group_flags_4964.py` (the #4964 sibling — it forwards group flags `--dry-run`/`--verbose`/`--force` *into* these five subs via `ctx.default_map`; `CorpusWideCommand.parse_args` wraps `super().parse_args`, so a regression that disturbs the forwarded default_map surfaces only here — note `--mission` is NOT forwardable, so only the other three matter), `tests/architectural/test_json_contract_enumeration.py`, plus `tests/migrate/` and `tests/migration/` for the touched commands. Specific architectural gate file only (NO_FULL_HEAVY_SUITES_IN_MISSION) — never bare `tests/architectural/`.
- **Files**: `tests/cli/test_mission_agnostic_flag.py`
- **Parallel?**: No.
- **Notes**: Use `$PWD/src:$PWD` absolute PYTHONPATH if running subprocess CLI tests. Run narrow, file-scoped foreground pytest.

## Test Strategy

- Red-first regression repro (T001) RED before fix, GREEN after (T003).
- Positive reject tests (equals + space form, exit 2 + message) and positive controls (normal run without `--mission`) in `tests/cli/test_mission_agnostic_flag.py`.
- Tree-wide invariant tests amended to carve out the five.
- `--help` byte-stability check (NFR-002).

## Risks & Mitigations

- **Two-click-era traceback (NFR-001)**: raise via `_usage_error_class(ctx)`, never a bare `click.UsageError`. Mitigation: reuse the helper verbatim.
- **Invariant test stays green but lies**: actively rewrite both tree-wide tests to express the reject-set; do not rely on mechanical green.
- **Over-rejection of default paths (FR-003)**: `_given_on_command_line` fires only on `COMMANDLINE` source; the `--dry-run`/`--json` defaults must not trip it — guarded by the positive-control test.
- **`repin-hooks` line drift**: locate it by `@app.command(name="repin-hooks")`, not by line number.

## Review Guidance

- Confirm `cli/helpers.py` is NOT modified (walker left-alone contract).
- Confirm all five decorators carry `cls=CorpusWideCommand` and no mission-scoped command was touched.
- Confirm the message is scope-neutral (accurate for pack-scoped and repo-repair commands).
- Confirm the regression repro was converted (not left `@pytest.mark.regression`).
- Confirm `--help` is unchanged and `test_json_contract_enumeration` stays green.

## Progress & Status

Progress/history/status live in the status event log — do not hand-edit here.
- Record a note: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- Change status: `spec-kitty agent tasks move-task WP01 --to <status>`
- View: `spec-kitty agent tasks status`
