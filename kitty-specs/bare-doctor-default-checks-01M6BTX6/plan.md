# Implementation Plan: bare `spec-kitty doctor` default run

**Branch**: `issue-6969-bare-doctor-default-checks` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/bare-doctor-default-checks-01M6BTX6/spec.md`

## Summary

Replace the #4678 bare-invocation refusal (`help + exit 2`) with a real default run:
`spec-kitty doctor` with no subcommand resolves the project root, runs three fast,
read-only, project-level checks (`command-files`, `state-roots`, `ops`), prints one line
per check naming its subcommand, and exits 0 when healthy / 1 when any check reports a
finding (including a check that raises). The aggregation lives in a new `_*-doctor`
sibling module; `doctor.py`'s `@app.callback` only resolves the root and delegates.
Help text, changelog and the setup-doctor skill are updated to match.

## Technical Context

**Language/Version**: Python 3.11 (repo baseline; `pyproject.toml`)
**Primary Dependencies**: Typer (CLI group), Rich (`Console`), pytest
**Storage**: N/A — reads `.kittify/`, `kitty-specs/`, `.kittify/events/*.jsonl` and the
global agent command directories only
**Testing**: pytest (`pytest.ini`); the new tests are `unit` + `fast`, driven through
`typer.testing.CliRunner` (the pre-existing entry point), no subprocess
**Target Platform**: CLI, Linux/macOS/Windows
**Project Type**: single project (`src/specify_cli/...`, `tests/...`)
**Performance Goals**: the bare invocation completes in-process well inside the fast
suite budget; the set is capped at three checks (NFR-001)
**Constraints**: read-only (NFR-002); existing subcommand contracts untouched (NFR-003);
no new group-level flags (C-003)
**Scale/Scope**: three checks, one new sibling module, one shell change, one test file,
three doc/changelog edits

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
|---|---|---|
| ATDD-First Discipline (C-011) | Pass | The defect is driven red-first through the existing `doctor` entry point (`CliRunner` on the registered root), then green. |
| `change-apply-smallest-viable-diff` | Pass | One new sibling module + one delegation in the shim + tests + docs; no refactor of the other 20 subcommands. |
| Locality of Change (DIRECTIVE_024) | Pass | Edits stay in `cli/commands/`, the one test file that pins the old guard, the changelog and the setup-doctor skill. |
| Single canonical authority (console) | Pass | Output goes through `_doctor_shared.console` (C-002); no second `Console()`. |
| #2059 doctor shim rule | Pass | Aggregation is a new sibling; `doctor.py` keeps only the `@app.callback` shell and a delegation (C-001). |
| Pre-existing Failure Reporting Rule | Pass | No gate is weakened; any unrelated red is reported in the PR `## Deferred`. |
| No full heavy suites in mission | Pass | Targeted `pytest` selections only. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/bare-doctor-default-checks-01M6BTX6/
├── plan.md              # this file
├── research.md          # discovery + Phase 0
├── quickstart.md        # Phase 1: how to see the new behaviour
├── spec.md
└── tasks.md             # /spec-kitty.tasks output
```

No `data-model.md` or `contracts/` — the mission adds one CLI behaviour with no new
entity store and no external interface; `meta.json` records `contracts: none`.

### Source Code (repository root)

```
src/specify_cli/cli/commands/
├── doctor.py                    # change: @app.callback delegates; help string updated
└── _default_run_doctor.py       # new: the default check set + aggregate renderer

tests/cli/
├── test_doctor_default_run.py                     # new: red-first exit-code + summary tests
└── test_top_level_group_empty_invocation.py       # update: replace the exit-2 pin

tests/architectural/
└── test_cli_placeholder_output.py                 # comment refresh only (doctor stays in CALLBACK_PATHS)

docs/
├── changelog/CHANGELOG.md       # [Unreleased] entry
├── api/cli-commands.md          # targeted refresh of the `spec-kitty doctor` help block
└── ... (setup-doctor skill source under src/charter/offering/skills/)
```

## Design

### Module placement (C-001)

`_default_run_doctor.py` exports:

- `DefaultCheck` — frozen dataclass: `command` (the owning subcommand name),
  `description` (one line), `collect` (callable `Path -> list[str]`, empty = healthy).
- `DEFAULT_CHECKS` — the ordered tuple of three checks, each a thin adapter over an
  existing data primitive:
  | `command` | primitive | finding text |
  |---|---|---|
  | `command-files` | `check_command_file_health(root)` | one line per issue dict |
  | `state-roots` | `check_state_roots(root).healthy` + `.warnings` | the warnings / the unhealthy flag |
  | `ops` | `list_orphan_ops(root)` | one line per orphan record |
- `CheckResult` — frozen dataclass: `check`, `findings`, `error`.
- `run_default_checks(repo_root) -> list[CheckResult]` — runs each check inside a
  `try/except Exception`, so a raising check becomes a failed result and the rest still
  run (FR-005).
- `render_default_run(results) -> int` — prints the summary and returns the exit code
  (0 healthy / 1 any finding or error).

`doctor.py`'s `_doctor_group` becomes: if a subcommand was invoked, return; else resolve
the project root through the existing `_doctor_shared.resolve_project_root_or_exit`
seam (exit 1 when not in a project) and call `run_default_checks` + `render_default_run`,
raising `typer.Exit(code=...)`.

### Output shape (FR-003, FR-004)

```
Default checks (3)

  ok    command-files  agent command files match the installed version
  FAIL  state-roots    1 finding -- full report: spec-kitty doctor state-roots
         <the finding line(s)>
  ok    ops            no orphan Op records

2 of 3 checks healthy. Run `spec-kitty doctor <subcommand>` for the full report.
```

Every line names the subcommand; a finding line names the subcommand that renders it in
full. Exit 0 only when every result is healthy; otherwise 1.

### Why aggregate data primitives, not the subcommand shells

The subcommand shells print Rich output and raise `typer.Exit`; calling them from the
group callback would either capture stdout or couple the exit codes. The three data
primitives are the same functions those shells use, so the default run cannot drift from
the subcommand's verdict (research.md Decision 3).

### Risks

- **Help-drift gate**: changing the group `help=` string requires the matching edit of the
  recorded block in `docs/api/cli-commands.md` (`HELP-DRIFT` in
  `scripts/docs/check_cli_reference_freshness.py`). Mitigated by a targeted edit plus a
  `check_cli_reference_freshness` run.
- **`identity`/`topology` exclusion**: deliberate (research.md Decision 1); the summary
  line still points at them via the subcommand list, and the issue says "where cheap".
- **`--json` absent on the bare group**: deliberate (research.md Decision 6); follow-up
  only if a maintainer asks.

## Implementation Concern Map

| IC | Concern | Verification |
|---|---|---|
| IC-01 | Default check table + per-check isolation (exception → finding) | `test_doctor_default_run.py` healthy / planted-finding / raising-check cases |
| IC-02 | Group callback delegation + not-in-project exit 1 | `CliRunner` on the registered root in a `tmp_path`, and in a fixture project |
| IC-03 | Read-only guarantee | fixture content snapshot before/after |
| IC-04 | Help/changelog/skill doc parity | `doctor --help` assertion + doc greps |

## Phase 0 — research

`research.md` already carries the discovery evidence and the six decisions; no
`NEEDS CLARIFICATION` item remains. Phase 0 adds nothing further.

## Phase 1 — design

`quickstart.md` records how a reviewer sees the behaviour before/after. No
`data-model.md` (no new persisted entity) and no `contracts/` (no external interface);
`meta.json` declares `contracts: none` with the rationale.
