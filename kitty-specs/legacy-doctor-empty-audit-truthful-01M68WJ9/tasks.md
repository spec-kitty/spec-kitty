# Tasks: Legacy doctor audits report what they did not check

**Mission**: `legacy-doctor-empty-audit-truthful-01M68WJ9` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `main` (PR branch `issue-6891-legacy-doctor-empty-audit-truthful`)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first `CliRunner` tests on the real `doctor` app: legacy no-list fixture → no `healthy` claim in `doctor skills` / `doctor tool-surfaces`, and the line names the absent agent list | WP01 | |
| T002 | Same-fixture positive controls: stated list + installed command skills keeps `all manifest entries healthy (N)`; stated list + deleted managed file still exits 1 naming the gap; legacy collision still exits 1 | WP01 | |
| T003 | Carry the already-loaded `AgentConfig` through the command-skill state tuple and the tool-surface config read (no added `load_agent_config` call) | WP01 | |
| T004 | One shared module-private renderer for the truthful line (subject + examined phrase); wire `_print_command_skill_report` | WP01 | |
| T005 | Wire `_print_tool_surface_human` (surfaces examined == 0) and keep `--json` key sets unchanged (human-only key in `_HUMAN_ONLY_KEYS`) | WP01 | |
| T006 | `load_agent_config` call-count test pinning the `6f73b2a98e` baseline (`skills` 3, `tool-surfaces` 1) | WP01 | |
| T007 | Half-by-half non-vacuity: revert the skills half and the tool-surfaces half in turn, each turns only its own test red | WP01 | |
| T008 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (bold impact-first lead, `(#6891)`, before/after, <1,200 chars) | WP01 | |
| T009 | Update any doc that documents the two summary strings (none expected — confirm with a grep and record the result) | WP01 | [P] |
| T010 | `doctor skills --fix` on the legacy fixture: no repair claim, same truthful line, no file changes on disk | WP01 | |
| T011 | Ratchet: `doctor command-files` output and exit code on the legacy fixture are unchanged (C-003) | WP01 | |
| T012 | Track the state-tuple stub in `test_doctor_slash_commands.py` (the loader now carries the loaded `AgentConfig`) | WP01 | |

## Phase 1 — P1 (MVP): the report stops claiming health over zero examined surfaces

### WP01 — Naming what the legacy audits did not check ([tasks/WP01-legacy-doctor-empty-audit.md](tasks/WP01-legacy-doctor-empty-audit.md))

- **Goal**: A legacy project (no `agents.available` list) gets `Command Skills: no stated agent list (every agent is available) — nothing to check` and `Tool Surfaces: no stated agent list (every agent is available) — nothing to check`, each naming what was not examined, instead of `all … healthy (0 …)`. Stated-list projects keep their existing summary, findings and exit codes.
- **Priority**: P1 (MVP — the whole defect)
- **Independent test**: on the legacy fixture, both commands exit 0, the output contains `no stated agent list` and `nothing to check`, and contains neither `all manifest entries healthy` nor `all surfaces healthy`; on the stated-list fixture the healthy line survives with a non-zero count and a deleted managed file still exits 1.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, C-005
- **Included subtasks**: T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011
- **Sketch**: write the red tests (T001/T002) and record the transcript → extend the state tuple with the loaded config → one shared note renderer → wire the skills report → wire the tool-surface report → green → call-count test → revert each half in turn (T007) → `--fix` (T010) and `command-files` (T011) ratchets → changelog (T008) → grep for doc strings (T009).
- **Dependencies**: none
- **Risks**:
  - `_assemble_skills_payload` sets `ok` twice; the note must be attached only after the **final** `ok`, or a project with a real slash-command gap would lose its findings to a "nothing to check" line.
  - `doctor skills --fix` in the legacy shape must not claim a repair.
  - `--json` key sets are frozen: the reason rides a human-only payload key.
  - PR #6894 (#6493, open) touches the same functions for the stated-empty shape; keep the diff narrow and reuse `explicit_agent_list` instead of adding a predicate.

## Parallelization

Single WP; T009 is the only subtask that can run beside T008.

## MVP

WP01 is the whole mission: the three-line summary change plus its red-first proof,
positive control, call-count pin and changelog entry.
