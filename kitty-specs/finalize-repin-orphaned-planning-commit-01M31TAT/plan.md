# Implementation Plan: Finalize re-pins an orphaned planning_commit_sha after a rebase

**Branch**: `fix/finalize-repin-orphaned-planning-commit` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT/spec.md`

## Summary

A mid-mission rebase rewrites the planning commit to a new SHA, orphaning the `planning_commit_sha` recorded in `lanes.json`. `finalize-tasks` today silently preserves that dead SHA (no flag) or refuses to re-point it (`--refresh-planning-commit` is advance-only), and every downstream consumer of the field then dead-ends against an unreachable commit. This plan splits the collapsed "not an ancestor → refuse" predicate into a **4-way classification against the target-branch tip** (captured / current-advanced / orphaned / foreign), adds a sanctioned operator re-pin (`--refresh-planning-commit --allow-orphaned`), makes a plain finalize **fail closed on a proven orphan** (while degrading to preserve on non-git/foreign/uncapturable), and centralizes orphan **detection** in the shared `_merge_recorded_planning_commit` helper plus the two other consumers (`check_claim_ancestry`, `_mt_resolve_owned_review_base`) so no call site surfaces the orphan as a false conflict, a dead-base diff, or a bare refusal. finalize stays the sole **writer** (C-001).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer (CLI), git (subprocess via existing `_capture_target_branch_tip` / `subprocess.run` helpers); no new third-party dependency
**Storage**: `lanes.json` (mission planning manifest) — existing `LanesManifest` model, existing `read_lanes_json` / `write_lanes_json`
**Testing**: pytest — real-git-repo integration harness already established in `test_issue_4141_refresh_planning_commit.py`; unit tests for the classifier helper
**Target Platform**: Linux/macOS developer + CI (spec-kitty CLI)
**Project Type**: single (spec-kitty CLI monorepo, `src/specify_cli/`)
**Performance Goals**: N/A — the added git predicates (`merge-base --is-ancestor`, `cat-file -e`) run once per finalize/allocation, negligible
**Constraints**: no new dependency; `ruff` + `ruff format --check` + `mypy` clean with no new suppressions; touched functions ≤ 15 cyclomatic complexity; no new blanket ignores
**Scale/Scope**: ~3 source modules changed (`mission_finalize.py`, `lanes/worktree_allocator.py`, `lanes/implement_support.py`, `cli/commands/agent/tasks_move_task.py`), 1 CLI flag added, ~5 test files touched (2 new red-first + corrected-expectation edits), 1 contract version bump, 1 CLI-reference doc regen

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter loaded (compact). Relevant standing orders and their disposition:

- **Single canonical authority (DIRECTIVE_044).** The fix REDUCES parallel authority: it centralizes orphan detection in the shared `_merge_recorded_planning_commit` helper and keeps finalize the sole writer (C-001), rather than adding a second re-pin site. It reconciles the four writers on one tip-capture rule (C-002). ✅ aligned.
- **ATDD-first / red-first (ADR 2026-07-17-1).** Every defect lands an issue-pinned `@pytest.mark.regression` repro that is RED through the pre-existing entry point before the fix. ✅ planned (WP sequencing below).
- **Architectural integrity (DIRECTIVE_001).** Re-pin target = tip, adversarially confirmed safe on coord/lanes topology (C-004); does not touch lane parent/topology (NFR-004); FR-009/ADR-2026-07-29-1 provenance preserved (fresh equally-frozen snapshot). ✅ aligned.
- **Terminology canon.** No `feature*` aliases introduced; the field stays `planning_commit_sha`; the new action value is `repinned`. ✅.
- **Tiered rigour.** Core domain logic (the classifier, the re-pin decision) gets focused unit + integration tests; glue (help text, doc regen) is lighter. ✅.

No violations to justify in Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT/
├── plan.md              # This file
├── spec.md              # Committed
├── research.md          # Phase 0 output (design decisions + adversarial evidence)
├── data-model.md        # Phase 1 output (the pin classification state model)
├── contracts/
│   └── finalize-repin-contract.md   # CLI flag + JSON action vocabulary + error contracts
├── checklists/requirements.md
├── tracer-approach.md
├── tracer-design-decisions.md
├── tracer-tooling-friction.md
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/agent/
│   ├── mission_finalize.py     # classifier + re-pin decision + --allow-orphaned + report (FR-001..005,009,010)
│   └── tasks_move_task.py      # _mt_resolve_owned_review_base orphan-aware (FR-008)
├── lanes/
│   ├── worktree_allocator.py   # _merge_recorded_planning_commit orphan detection (FR-006); error class
│   ├── implement_support.py    # reconcile merge (:352) + check_claim_ancestry (:497) (FR-006, FR-007)
│   └── compute_and_persist.py  # (writer, unchanged behavior; consistency check only — C-002)
└── orchestrator_api/envelope.py # CONTRACT_VERSION 1.5.0 -> 1.6.0 for `repinned` (C-007)

tests/
├── specify_cli/cli/commands/agent/
│   ├── test_issue_4827_repin_orphaned_planning_commit.py   # NEW red-first (finalize side)
│   ├── test_issue_4141_refresh_planning_commit.py          # unchanged (regression-verify)
│   ├── test_issue_3311_finalize_rewrites_active_lanes.py    # corrected expectation (non-git preserve stays)
│   └── test_mission_cli_golden_contract.py                  # frozenset += --allow-orphaned
└── lanes/
    ├── test_issue_4827_allocator_orphan_pin.py             # NEW red-first (consumer side)
    ├── test_lane_base_common_ancestor.py                   # corrected expectation
    └── test_worktree_allocator_atomicity.py                # corrected expectation
docs/api/agent-subcommands.md                               # regen via scripts/docs/build_cli_reference.py
docs/changelog/CHANGELOG.md                                 # [Unreleased] Fixed entry
```

**Structure Decision**: Single-project spec-kitty CLI layout. The fix is confined to the status/lanes/finalize surfaces named above; `coordination/commit_router.py` is explicitly out of scope (C-003, overloaded-name collision).

## Parallel Work Analysis

Single-orchestrator, sequential mission (per field-report L2 posture). The work decomposes into a small dependency chain rather than parallel waves:

### Dependency Graph

```
WP01 (shared classifier helper: 4-way classification against target tip, object-presence probe)
   │  ← foundation; every other WP consumes it
   ├─→ WP02 (finalize re-pin decision + --allow-orphaned + fail-closed/degrade + report; FR-001..005,009,010)
   └─→ WP03 (consumer detection: _merge_recorded_planning_commit + implement_support + tasks_move_task; FR-006,007,008)
             │
             └─→ WP04 (surface + docs + changelog: golden-contract frozenset, envelope 1.6.0, CLI-ref regen, CHANGELOG; C-007)
```

WP02 and WP03 both depend only on WP01 and could run in parallel, but a single orchestrator will run them sequentially (WP02 then WP03). WP04 depends on WP02 (the flag surface).

### Work Distribution
- **Sequential foundation**: WP01 (the classifier) must land first — it is the single authority both the finalize path and the consumers call.
- **Agent assignment**: python-pedro (implement), reviewer-renata/opus (review). Single owner per WP; no cross-WP file overlap (WP02 owns `mission_finalize.py`; WP03 owns the lanes/consumer files; WP04 owns tests-surface/docs).

### Coordination Points
- Red-first repros (WP02 finalize, WP03 allocator) are authored failing against the pre-fix entry points before their fixes land.
- The corrected-expectation edits (NFR-001 named surface) land in the WP that changes the behavior they assert.
