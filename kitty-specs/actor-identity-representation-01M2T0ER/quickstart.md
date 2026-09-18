# Quickstart: verifying the actor-identity representation fixes

How a reviewer confirms the four defects are fixed. Run from a lane worktree for the mission.

## Prerequisites

- Editable install current: `.venv/bin/python -m pip install -e .` (never a bare `uv run`, which
  re-syncs and destroys a hand-built `.venv`).
- A scratch mission with a finalized WP to exercise the live CLI paths, OR run the mission's
  regressions directly.

## Run the regressions (red-first proof)

Each defect has an issue-pinned `@pytest.mark.regression`. On the WP's `planning_base_branch`
(current `main`, of which `be490214` is an ancestor) they are RED (except #3029 — see below);
after the fix they are GREEN.

```
PWHEADLESS=1 .venv/bin/python -m pytest tests/status/ tests/specify_cli/cli/commands/agent/ -m regression -q
```

Targeted per WP:

- #4665: `tests/status/test_work_package_lifecycle*.py` + the live fresh-worktree claim integration under `tests/specify_cli/cli/commands/agent/`.
- #4670: `tests/specify_cli/cli/commands/agent/review/` — claim → generated handoff → completion (approval AND rejection).
- #4673: `tests/specify_cli/cli/commands/agent/` — implement → for_review → review → reject → fix-mode claim → for_review (no `--force`).
- #3029: run the live `move-task --agent` persistence check FIRST; if red, it is the repro; if green, the characterization test + evidence closes the issue.

## Live smoke (optional, exercises the real CLI)

```
spec-kitty agent action implement WP01 --mission <M> --agent codex:gpt-6:python-pedro:implementer
# expect: WP moves to in_progress AND the prompt renders, in ONE invocation, no self-conflict
```

## Gate checks

```
uv run --frozen ruff check .
uv run --frozen ruff format --check .
.venv/bin/python -m mypy --strict src/specify_cli/status src/specify_cli/cli/commands/agent
```

## Definition of done (mission)

- SC-001..SC-005 met; historical events byte-unchanged (NFR-001); issue-matrix verdicts recorded
  for #4665/#4670/#4673/#3029; FR-007 recorded green or partially-met-upstream-blocked with a filed
  `spec-kitty-events` follow-up handle if the reducer residual bites.
