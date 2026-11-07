# Implementation Plan: Cheap nightly reds remediation

**Branch**: `issue-7183-nightly-reds-remediation` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/nightly-reds-remediation-01M6VYS1/spec.md`

## Summary

Nineteen nightly-only test nodes are red on `main` (`13f873afb7`). Eighteen are stale pins to contracts that were changed on purpose; they are re-pinned in place, each at least as strong as before and citing the commit that moved its contract. One (#7178) is a production violation of the destructive-git-advice gate: the upgrade tracked-meta notice prints `git checkout -- <path>` inline. It is fixed by a new checkout-form renderer in the canonical `_git_remedies` module, used through a deferred import, with byte-identical notice output and an empty gate allowlist. Four work packages run sequentially on this single branch. Research input and per-issue decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest, typer CliRunner, ruff (existing; no dependency added or changed)
**Storage**: files only (test fixtures under `tmp_path`; one changelog fragment)
**Testing**: exact failing node ids run RED then GREEN, plus owning test files and named gates; no full or heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION)
**Target Platform**: Linux dev checkout; nodes run only in the nightly in CI
**Project Type**: single (brownfield CLI repository)
**Performance Goals**: N/A (the #7183 node 3 budget is a git-call count, `2 + 4 x real Missions`)
**Constraints**: brownfield point cuts only; allowlist stays empty; no `noqa` / `type: ignore`; complexity at or below 15; new helper gets same-PR unit tests
**Scale/Scope**: 19 nodes, 13 test files, 1 production module pair, 1 changelog fragment

## Charter Check

*GATE: passes before Phase 0 and after Phase 1.*

| Charter rule | Status |
|---|---|
| Single canonical authority (DIRECTIVE_044) | Pass. The destructive-recipe text keeps one home (`_git_remedies.py`); the notice stops owning a copy. |
| Test remediation discipline (Standing Order 4, DIRECTIVE_041) | Pass. Each test is judged: stale pins are re-pinned, never weakened; the one defect is fixed in product code; RED-first through the existing node ids. |
| Gate discipline (Standing Order 5) | Pass. Gate untouched, allowlist stays empty. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Pass. Only named nodes, owning files and named gates. |
| Git and workflow (Standing Order 7) | Pass. Topic branch, no push, no PR (the reviewer and operator own landing). |
| Mission hygiene (Standing Order 8) | Pass. Implementer stops at `for_review`; a distinct reviewer approves. |
| Terminology Canon | Pass. Mission, never Feature; senses of overloaded terms named. |

No violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-reds-remediation-01M6VYS1/
├── plan.md
├── research.md
├── spec.md
├── traces/              # tooling-friction, approach, design-decisions
├── checklists/requirements.md
└── tasks.md             # created by /spec-kitty.tasks
```

No `contracts/`, `data-model.md` or `quickstart.md`: the Mission defines no interface (`meta.json` carries `contracts: none` with a rationale).

### Source Code (repository root)

```
src/specify_cli/cli/commands/_git_remedies.py                          # WP02: add checkout_file_recipe
src/specify_cli/upgrade/tracked_meta_notice.py                         # WP02: use it (deferred import), drop _RESTORE
tests/specify_cli/cli/commands/test_git_remedies.py                    # WP02: unit tests for the renderer
tests/specify_cli/cli/commands/test_merge_cli_golden.py                # WP01 #7177
tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py      # WP01 #7111
tests/specify_cli/cli/commands/test_charter_generate_autotrack.py      # WP03 #7181
tests/integration/test_charter_status_freshness.py                     # WP03 #7181
tests/specify_cli/test_charter_activate_cli.py                         # WP03 #7182
tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py    # WP03 #7182
tests/specify_cli/cli/commands/test_merge.py                           # WP04 #7183 n1
tests/specify_cli/cli/commands/test_tasks_status_default_mission.py    # WP04 #7183 n2
tests/specify_cli/migration/test_residue_shared_walkers_6669.py        # WP04 #7183 n3
tests/integration/test_pack_skill_lifecycle.py                         # WP04 #7183 n4
tests/integration/test_single_branch_write_checkout_e2e.py             # WP04 #7183 n5
docs/changelog/unreleased/<id>.<section>.md                            # WP04 changelog fragment
```

**Structure Decision**: single project; edits stay inside the files above (C-001). The `_git_remedies` change touches no `__init__.py`, so no version bump is triggered.

## Complexity Tracking

Not applicable (no Charter Check violations).

## Implementation Concern Map

### IC-01 — Pure test re-pins with no production change

- **Purpose**: re-pin the consolidate flag golden and the orchestrator-api migration-actor test.
- **Relevant requirements**: FR-001, FR-002, NFR-001
- **Affected surfaces**: `test_merge_cli_golden.py`, `test_wp_lifecycle_structured_actor_6400.py`
- **Sequencing/depends-on**: none
- **Risks**: the #7111 rewrite is not a one-line re-pin; the expected actor is role `system`, not `implementer`.

### IC-02 — Git-remedies renderer

- **Purpose**: give the file-restore remedy its canonical renderer and route the notice through it.
- **Relevant requirements**: FR-003, C-002, C-003
- **Affected surfaces**: `_git_remedies.py`, `tracked_meta_notice.py`, `test_git_remedies.py`
- **Sequencing/depends-on**: none
- **Risks**: import cycle through `specify_cli.cli.commands` (deferred, function-level import as in `migration/mission_state.py`); pinned notice strings in `test_read_tracked_meta_6673.py` must stay byte-identical.

### IC-03 — Charter test re-pins

- **Purpose**: align `charter status` and activation or interview tests with the typed refusal, the absent-key rule and the collision refusal.
- **Relevant requirements**: FR-004, FR-005, FR-006, C-004
- **Affected surfaces**: four charter test files
- **Sequencing/depends-on**: none
- **Risks**: do not use the status envelope for the interview; do not seed lists in the deactivate tests; the cascade file takes about two minutes.

### IC-04 — The #7183 point cuts and changelog

- **Purpose**: re-pin five independent contracts (six nodes) and record the change.
- **Relevant requirements**: FR-007 to FR-012, NFR-001
- **Affected surfaces**: five test files, one changelog fragment, a follow-up note for the per-Mission git cost
- **Sequencing/depends-on**: none
- **Risks**: a one-off venv-rebuild red on the pack-skill lifecycle test must be reported, not retried to green silently.
