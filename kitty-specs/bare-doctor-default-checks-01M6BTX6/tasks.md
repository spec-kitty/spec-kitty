# Tasks: bare `spec-kitty doctor` default run

**Mission**: bare-doctor-default-checks-01M6BTX6
**Branch**: `issue-6969-bare-doctor-default-checks`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) · [quickstart.md](./quickstart.md)

Replace #4678's bare-invocation refusal (`help + exit 2`) with a real default run: three
fast read-only project checks (`command-files`, `state-roots`, `ops`), one summary line
per check naming its subcommand, exit 0 when healthy / 1 on any finding. The aggregation
lives in a new `_default_run_doctor` sibling (the `doctor.py` shim only delegates), the
exit code is pinned by a red-first test through the existing entry point, and help,
changelog and the setup-doctor skill are updated to match.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: pin bare `doctor` exit code and summary lines through the registered root (fails today with exit 2) | WP01 | — |
| T002 | New `_default_run_doctor.py`: `DefaultCheck`/`CheckResult`, the three-check table over existing data primitives, `run_default_checks` with per-check exception isolation | WP01 | — |
| T003 | `render_default_run` summary renderer (names each subcommand; finding lines name the full-report subcommand) and the 0/1 exit contract | WP01 | — |
| T004 | `doctor.py` `@app.callback`: resolve project root through the shared seam and delegate; keep the subcommand fast-path | WP01 | — |
| T005 | Update the #4678 pin in `tests/cli/test_top_level_group_empty_invocation.py` to the new contract | WP01 | — |
| T006 | Read-only proof: fixture content unchanged after a bare run | WP01 | — |
| T007 | Update the group help string + the recorded `spec-kitty doctor` block in `docs/api/cli-commands.md` | WP01 | — |
| T008 | `[Unreleased]` changelog entry and the setup-doctor skill text | WP01 | — |
| T009 | Targeted lint/type/test gate run and the aggregate self-review | WP01 | — |

---

## WP01 — Default diagnostic run for a bare `doctor`

**Prompt**: [tasks/WP01-default-diagnostic-run.md](tasks/WP01-default-diagnostic-run.md)

**Summary**
- **Goal**: bare `spec-kitty doctor` runs `command-files`, `state-roots` and `ops`, prints a per-check summary naming each subcommand, and exits 0 (healthy) / 1 (any finding, including a raising check).
- **Priority**: P0 — the whole mission.
- **Independent test**: `CliRunner` on the registered root in a fixture project: exit 0 and three summary lines when healthy; exit 1 and the owning subcommand named when one check finds something.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004.

**Depends on**: none.

**Subtasks**
- T001: write `tests/cli/test_doctor_default_run.py` first and show it red on the current code (exit 2, no check lines).
- T002/T003: the sibling module — the check table, per-check isolation, the renderer and the exit code.
- T004: the `@app.callback` delegation; not-in-project stays exit 1.
- T005: retire the exit-2 assertion in the older test, keep its intent (no "Missing command" prose, help still reachable).
- T006: read-only assertion over the fixture.
- T007/T008: help text, `docs/api/cli-commands.md`, changelog and skill docs.
- T009: `pytest` selections, `ruff`, `mypy` on the touched files, `check_cli_reference_freshness`.

## Dependencies

Single work package; no dependency edges.
