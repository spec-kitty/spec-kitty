---
work_package_id: WP07
title: Migrate group flags are honoured or refused (#4964)
dependencies: []
requirement_refs:
- FR-020
- FR-021
- FR-022
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
subtasks:
- T036
- T037
- T038
- T039
phase: Phase 2 - Silent-loss fixes
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/migrate_cmd.py
create_intent:
- tests/cli/test_migrate_group_flags_4964.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/migrate_cmd.py
- tests/cli/test_migrate_group_flags_4964.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Migrate group flags are honoured or refused (#4964)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (role `implementer`, agent `claude`); then `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Feedback items are your TODO list.

---

## Objectives & Success Criteria

Issue #4964: the `migrate` group callback (`cli/commands/migrate_cmd.py:~119-143`, `@app.callback(invoke_without_command=True)`) declares `--dry-run`, `--verbose/-v`, `--force`, then does `if ctx.invoked_subcommand is not None: return`. So `spec-kitty migrate --dry-run backfill-runtime-state` silently drops the flag and runs the **real** migration (writes `status_phase`, creates `status.events.jsonl`), exit 0.

Operator policy (Decision Moment `01M3KDD2GHGFS7J5616ZNQHE6Y`): honour it — forward a group flag to a subcommand that declares the same option; otherwise refuse with a usage error before anything runs.

Done means (FR-020–FR-022):
- FR-020: for every registered migrate subcommand that declares `--dry-run`, `migrate --dry-run <sub>` runs in dry-run mode; working tree unchanged.
- FR-021: a group-level `--dry-run` / `--force` / `--verbose` / `-v` given before a subcommand that does not declare it → click usage error (exit 2), nothing written. Census today: 10 subcommands declare `--dry-run` (backfill-identity, backfill-merge-commit, backfill-mission-type, backfill-provenance, backfill-runtime-state, backfill-topology, charter-encoding, normalize-lifecycle, rebaseline-dossier-hashes, rewrite-opposed-by); `repin-hooks` does not; none declare `--force`/`--verbose`.
- FR-022 (ratchet): trailing form `migrate <sub> --dry-run` unchanged; a trailing `--no-dry-run` (if the subcommand defines it) wins over a forwarded group flag; `migrate` with no subcommand runs its own body exactly as today (including `--dry-run`, `--force`).

## Context & Constraints

- Plan design decision **D7**; research **R6**. Verified by experiment on typer 0.24.2 / click 8.3.3: in the group callback, flags given on the command line are detectable with `ctx.get_parameter_source(name) == click.core.ParameterSource.COMMANDLINE`; the subcommand object is `ctx.command.get_command(ctx, ctx.invoked_subcommand)`; its declared options are `sub.params` (match by `param.name` and/or `param.opts`); forwarding works by setting `ctx.default_map = {**(ctx.default_map or {}), sub_name: {**existing, param.name: value}}` because click builds the subcommand context after the callback returns; `raise click.UsageError(msg, ctx=ctx)` exits 2.
- The callback already carries `# noqa: C901` — do not add logic inline; extract a helper `_forward_or_refuse_group_flags(ctx) -> None` (≤15 complexity) and call it in place of the early return (then return).
- The test must be **parametrised over the live registry** (enumerate `app`'s registered commands at test time) so a future subcommand is covered automatically.

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. `spec-kitty implement WP07`.

## Subtasks & Detailed Guidance

### Subtask T036 – Red-first repro (`tests/cli/test_migrate_group_flags_4964.py`)

Mark `@pytest.mark.regression`; confirm FAIL; record.
- Fixture: a scratch repo with a legacy mission needing migration (build like the issue's `legacy_fixture.sh`: a mission `meta.json` without `status_phase`, no `status.events.jsonl`, WP files with legacy frontmatter lanes — or reuse an existing legacy-mission fixture: `grep -rl "backfill-runtime-state\|backfill_runtime_state" tests`).
- For each subcommand declaring `--dry-run` (discovered from the Typer app): run `migrate --dry-run <sub>` via `CliRunner` (with any required args — e.g. `backfill-merge-commit` requires `--mission` and `--merge-commit`; derive from params' `required`); assert `git status --porcelain` empty afterwards and exit code 0, **and assert the flag was actually received** — the `(dry-run)` output prefix, a `dry_run: true` JSON field, or a spy on the backend function's `dry_run` kwarg (an unchanged tree alone is vacuous for subcommands with nothing to migrate). For `backfill-runtime-state` (the issue's repro), add a **positive control on the same fixture**: the non-dry-run form DOES write (proves the fixture is migratable).
- `migrate --dry-run repin-hooks` → exit 2, nothing written.
- `migrate --force backfill-runtime-state`, `migrate -v backfill-runtime-state` → exit 2, nothing written.

### Subtask T037 – Helper

- Implement `_forward_or_refuse_group_flags(ctx: typer.Context) -> None`: for each of the group's own params (`dry_run`, `verbose`, `force`) with COMMANDLINE source and a truthy value: find a param on the subcommand with the same `name` (and an option string overlapping the group's, e.g. `--dry-run`); if found → forward via `default_map`; else → `click.UsageError(f"'{flag}' is not supported by 'migrate {sub}'. Place supported flags after the subcommand, e.g. 'spec-kitty migrate {sub} --dry-run'.")`. Error text must name the flag, the subcommand and the supported position (NFR-003).
- Replace the early `return` with: call helper, then `return`.
- Update the group options' help text (`--dry-run`, `--verbose`, `--force`) to say that before a subcommand they are forwarded when the subcommand supports them and otherwise rejected (C-007).
- NFR-003: usage-error tests assert the message names the flag, the subcommand and the supported position.

### Subtask T038 – Ratchets

- Trailing form unchanged (`migrate backfill-runtime-state --dry-run` → no writes, same output as before).
- If a subcommand defines `--dry-run/--no-dry-run`: `migrate --dry-run <sub> --no-dry-run` → the trailing value wins (click precedence); if none defines `--no-dry-run`, document that and skip.
- `migrate --dry-run` with no subcommand → today's preview path (spot-check output unchanged).

### Subtask T039 – Convert and gate

```bash
uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py tests/cli/test_migrate_cmd_messaging.py -q
uv run --frozen pytest $(grep -rl "migrate_cmd\|\"migrate\"" tests/cli tests/specify_cli --include=*.py | sort -u) -q
uv run --frozen pytest tests/architectural/test_cli_error_surface_seam.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/migrate_cmd.py tests/cli/test_migrate_group_flags_4964.py && uv run --frozen ruff format --check src/specify_cli/cli/commands/migrate_cmd.py tests/cli/test_migrate_group_flags_4964.py
uv run --frozen mypy --strict src/specify_cli/cli/commands/migrate_cmd.py
make test-fast
```

Remove regression markers after green.

## Risks & Mitigations

- Some subcommands may require arguments or network/state; parametrise with per-subcommand arg builders from their declared params and skip only with an explicit, reasoned `pytest.param(..., marks=pytest.mark.skip(reason=...))` if a subcommand truly cannot run offline — never silently.
- `test_cli_error_surface_seam.py` may constrain how errors are raised in CLI modules; `click.UsageError` is the standard usage-error path — confirm the seam test allows it.

## Review Guidance

- Parametrised over the live registry; group flag never silently dropped.
- Helper extracted; callback complexity not increased.
- No-subcommand path and trailing flags unchanged.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
