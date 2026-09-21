---
work_package_id: WP02
title: Finalize re-pin surface
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-009
- FR-010
- NFR-001
- NFR-002
planning_base_branch: fix/finalize-repin-orphaned-planning-commit
merge_target_branch: fix/finalize-repin-orphaned-planning-commit
branch_strategy: Planning artifacts for this mission were generated on fix/finalize-repin-orphaned-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/finalize-repin-orphaned-planning-commit unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Implementation
history:
- timestamp: '2026-09-21T00:00:00Z'
  agent: system
  action: Prompt generated via tasks phase authoring
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/orchestrator_api/envelope.py
- tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py
- tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py
- docs/api/agent-subcommands.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match.

---

## Objective

Make `spec-kitty agent mission finalize-tasks` handle the orphaned-pin (mid-mission-rebase) case: a plain run stops silently preserving a proven orphan and fails closed with a recovery hint (degrading to preserve when the tip is uncapturable / non-git / foreign), and a new `--refresh-planning-commit --allow-orphaned` re-pins the recorded `planning_commit_sha` to the target-branch tip. Bare `--refresh-planning-commit` keeps its #4141 advance-only refusal. Issue #4827; research.md D3/D4/D7; contracts/finalize-repin-contract.md.

## Context

`mission_finalize.py::_preserve_or_capture_planning_commit_sha` (~L2169) is the decision seam. Today: execution-not-begun → `captured`; else no-flag → `preserved` (returns the recorded SHA, even when orphaned); `--refresh-planning-commit` → advance-only, refused via `_recorded_planning_sha_is_ancestor_of_tip` (~L2148) on any non-ancestor. `_report_planning_sha_decision` (~L2280) prints a drift WARN that misfires (research.md D7 / #4178). The Typer flag surface is on `finalize_tasks` (~L3080). Consume the WP01 classifier here; retire the duplicate `_recorded_planning_sha_is_ancestor_of_tip` in favor of the shared predicate (single authority, DIRECTIVE_044).

## Subtasks

### T004 — Red-first repro (@pytest.mark.regression, pinned to #4827)
Extend the `test_issue_4141_refresh_planning_commit.py` real-git harness in a NEW file `tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py`. After execution begins, **rebase** the mission/target branch so the recorded planning SHA is orphaned (present, not an ancestor of the new tip). Write these RED against the pre-fix entry point:
- plain finalize (no flag) → today PRESERVES the orphan (assert the desired post-fix behavior: fails closed, `lanes.json` untouched, message names `--refresh-planning-commit --allow-orphaned` + the recorded/tip SHAs) → RED now.
- `--refresh-planning-commit --allow-orphaned` → re-pins to the new tip, `action: "repinned"`, `previous_sha` == orphaned SHA → RED now.
Mark `@pytest.mark.regression` and reference #4827 in the module docstring.

### T005 — Add `--allow-orphaned`
Add `allow_orphaned: Annotated[bool, typer.Option("--allow-orphaned", help=...)] = False` to `finalize_tasks` (~L3101, beside `refresh_planning_commit`); thread it through `_run_commit_pipeline`/`_compute_and_write_lanes` to `_preserve_or_capture_planning_commit_sha`. Default False is load-bearing (keeps the #4141 refusal test green).

### T006 — Wire the classifier into the decision seam
In `_preserve_or_capture_planning_commit_sha`, after the execution-begun/`read_lanes_json` guard, capture the tip and call the WP01 `classify_recorded_pin(repo_root, recorded, tip)`:
- `advanced` → existing behavior (bare `--refresh-planning-commit` refreshes to tip; no-flag preserves-and-warns).
- `orphaned` + `--refresh-planning-commit --allow-orphaned` → re-pin: `PlanningCommitResolution(sha=tip, action="repinned", previous_sha=recorded, branch_tip=tip)`.
- `orphaned` + `--refresh-planning-commit` (no `--allow-orphaned`) → refuse; message MUST still contain the substring "not an ancestor" (keeps `test_refresh_refused_when_recorded_sha_not_ancestor` green).
- `orphaned` + no flag → fail closed BEFORE any write (`typer.Exit(1)`), naming the `--refresh-planning-commit --allow-orphaned` recovery + recorded/tip SHAs.
- `foreign` → refuse even with `--allow-orphaned` (object absent; investigate).
- `indeterminate` (tip uncapturable / non-git) → DEGRADE to the historical `preserved` (no abort) — protects `test_issue_3311_...`.
Keep the function ≤ 15 complexity (extract small helpers for the orphan/foreign branches if needed).

### T007 — Report the decision (FR-009) + fold #4178 (FR-010)
- Add `repinned` to the `PlanningCommitResolution.action` docstring/vocabulary and to `_report_planning_sha_decision` (human) + the `--json` `planning_commit` payload.
- Move the decision print to AFTER `write_lanes_json` (#4178 print-before-write).
- Correct the preserve-path drift WARN so it (a) does not fire on the tool's own finalize bookkeeping commit and (b) points an orphan at `--allow-orphaned`, not bare `--refresh-planning-commit`.

### T008 — Golden-contract + help text
Add `--allow-orphaned` to `_EXPECTED_FLAGS["finalize-tasks"]` in `tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py` (exact set-equality). Update the `--refresh-planning-commit` help text to mention the `--allow-orphaned` escape hatch for the rebase case.

### T009 — Contract + doc regen
Bump `orchestrator_api/envelope.py` `CONTRACT_VERSION` 1.5.0 → 1.6.0 with a changelog comment for the additive `repinned` action. Regenerate `docs/api/agent-subcommands.md` via `scripts/docs/build_cli_reference.py` (then `scripts/docs/check_cli_reference_freshness.py --ci` must report 0). Commit the regenerated doc in THIS WP so the doc-freshness gate is green at this commit.

### T010 — Un-mark and verify
After the fix, demote the T004 repro from `@pytest.mark.regression` to a focused permanent test (per ADR 2026-07-17-1). Run and record: the new #4827 file, `test_issue_4141_refresh_planning_commit.py`, `test_issue_3311_finalize_rewrites_active_lanes.py`, `test_mission_cli_golden_contract.py`.

## Branch Strategy

Planning branch and merge target: `fix/finalize-repin-orphaned-planning-commit`. Per computed lane from `lanes.json`.

## Definition of Done

- All four flag/no-flag orphan paths behave per contract; foreign refused; non-git/uncapturable degrades to preserve.
- `repinned` reported in human + JSON; report prints after the write.
- Golden-contract, help text, envelope, CLI-ref doc all updated in this WP (no gate red at this commit).
- #4141 + #3311 suites green unmodified; the #4827 repro green post-fix.
- `ruff` / `ruff format --check` / `mypy` clean; complexity ≤ 15; no new suppressions.

## Risks / reviewer guidance

- **NFR-001 trap**: `test_issue_3311_...` seeds a synthetic absent SHA in a NON-GIT workspace and asserts preserve on a plain run — the `indeterminate`/`foreign` degrade path MUST keep it green. `test_refresh_refused_when_recorded_sha_not_ancestor` MUST stay green (the "not an ancestor" substring + `--allow-orphaned` default False).
- These test files live OUTSIDE `make test-fast` — the PR *Tests run* must name them explicitly.
- Retire the duplicate ancestry helper rather than leaving two authorities (DIRECTIVE_044).
