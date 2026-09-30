---
title: 'Fast-Follow Spec: Implement-Loop Friction Quick-Wins'
description: 'Fast-follow spec for the implement-loop friction quick-wins: topology default, pre-review-gate escape hatch, finalize per-branch hashes, and charter first-run parity.'
doc_status: deprecated
updated: '2026-08-12'
---

> **RETIRED (shipped)** — the primary quick-win this fast-follow scoped, #2581 (coord-topology
> default), closed 2026-07-12 as COMPLETED; the friction fixes landed via `ec3e2c528` /
> `266d757f5` and mission `loop-reliability-ci-red-burndown-01KXWWD6`. Retained for historical
> reference; do not consult for current behavior.

# Mission Spec (materialization-ready): Implement-Loop Friction Quick-Wins

**Status**: Draft spec — ready to materialize via `spec-kitty agent mission create` in a clean project-root checkout.
**Created**: 2026-07-12
**Origin**: friction logged live during mission `coord-shadows-followups-01KXBCZ1` (`traces/tooling-friction-trace.md`), then investigated (planner-priti lens, code-verified) into a scoped fast-follow.
**Parent epics**: #2017 (workflow-guard friction — primary) + #2160 (coord-topology authority — co-parent).

> **Why a doc, not a live mission:** at authoring time the shared project-root checkout was in active use by a concurrent `ci-test-topology-performance` mission (a cross-mission collision that itself is one of the friction lessons). `spec-kitty agent mission create` refuses to run from a worktree, so this spec is authored as a document to be dropped into a real mission once a clean checkout/clone is available. Content is mission-spec quality (issue matrix + FR/NFR/C + WP outline).

## Context

The `coord-shadows-followups` mission repeatedly hit implement/review-loop friction. A code-verified investigation mapped each witnessed friction to an existing or new ticket and scoped a **quick-wins** fast-follow — deliberately excluding the hard async redesign. The goal: clear the highest-friction, low-risk points so the next larger slices run against a smoother loop.

## Tracked Issues (Issue Matrix)

| Item | Issue | Surface | Verdict | Linkage |
|------|-------|---------|---------|---------|
| Topology default mints coord husk on a non-primary feature branch without `--pr-bound` | #2581 | `cli/commands/agent/mission_create.py:~401`, `core/mission_creation.py:~215` | in-mission | Closes #2581; child #2160, sibling #2533 |
| Pre-review gate runs a synchronous multi-minute pytest that reads as a hang | #2573 | `cli/commands/agent/tasks_move_task.py::_mt_run_pre_review_gate`, `review/pre_review_gate.py:388` | in-mission (partial) | Closes #2573 (env+flag+progress; full async redesign deferred, noted on #2573) |
| `finalize-tasks --json` reports one `commit_hash` for a two-branch commit set (facet B) | #2549 | `cli/commands/agent/mission_finalize.py:1296-1332,1406-1407`, `coordination/commit_router.py` | in-mission | Closes #2549 (facet B; facet A — lane mis-route — deferred, follow-up on #2549) |
| `charter synthesize` over-demands companion tactics on empty config (#2526 regression) | #2577 | `cli/commands/charter/_synthesis.py:61` `_build_synthesis_request` | in-mission | Closes #2577; relates #2526 |
| Sync-daemon deaf to `SPEC_KITTY_SYNC_DISABLE` (dup across #2573/#2555/#2570) | #2573 | consolidate onto #2573 | note | consolidate — do not spawn a 4th tracker |
| Surface `/spec-kitty.analyze` in tasks→implement handoff | #2582 | doc/skill | **EXCLUDED — post-mission op** | operator-directed |
| First-approval issue-matrix scope-conflation | #2583 | approve gate | **EXCLUDED — post-mission op** | operator-directed (touches approve-gate semantics — treat carefully) |
| Approve clean-tree check scoped to WP code, not all `kitty-specs/` | #2017 | approve pre-flight | **OPTIONAL stretch** | #2017 Class A2/A3; include only if capacity |

Epics #2017 / #2160 stay open. #2582/#2583 are handled as post-mission ops per operator direction.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A feature-branch mission doesn't force a coord husk (Priority: P1)

A maintainer runs `spec-kitty agent mission create` on a dedicated feature/fork branch without `--pr-bound`. The mission should default to a coord-less topology (`single_branch`) rather than minting a coordination branch that must be manually flattened.

**Acceptance**: create on a non-primary branch without `--pr-bound` → `topology: single_branch`, no `coordination_branch` minted; primary-branch / `--pr-bound` / explicit-coord paths still get `coord`; a red-first test pins the feature-branch default.

### User Story 2 — The pre-review gate is skippable and legible (Priority: P1)

A maintainer runs `move-task --to for_review` and either sees streamed progress (not a silent multi-minute hang) or can skip the gate with an explicit flag / honored env var.

**Acceptance**: `--skip-pre-review-gate` flag skips the gate; `SPEC_KITTY_SYNC_DISABLE` (and the minimal-import env) are honored; when the gate runs, progress is surfaced. The full async redesign is out of scope (deferred on #2573). Tests: flag skips; env honored; gate still enforceable by default.

### User Story 3 — finalize-tasks reports the full commit set (Priority: P2)

An automated caller reads `finalize-tasks --json` and gets **per-branch** commit hashes for a two-branch (coord-topology) commit set, so `commit_hash` + `files_committed` are consistent.

**Acceptance**: under coord topology, the JSON reports the feature-branch AND coordination-branch commit hashes (a mapping or list), not a single `commit_hash` that omits the placement-partition commit; a flat/single-branch mission still reports its single commit; a test pins both shapes. Facet A (lane mis-route) is out of scope.

### User Story 4 — charter synthesize works on an empty/first-run config (Priority: P2)

A maintainer runs `charter synthesize` on an empty/first-run project. It must not fail-closed demanding a `how-we-apply-<directive>` companion tactic for every built-in directive.

**Acceptance**: empty config → 0 companion-tactic demands (first-run parity with pre-#2526), per a charter/doctrine-owner decision (NOT the spec-forbidden test-seeding anti-pattern); a red-first empty-config parity test. Fix surface: the three-state fallback in `_build_synthesis_request` resolving `config_roots.directives` to all built-ins.

### Edge Cases

- Topology default must not regress primary-branch / `--pr-bound` / multi-agent coord creation.
- `--skip-pre-review-gate` must not become the silent default — the gate stays enforceable.
- finalize per-branch reporting must be backward-compatible for flat missions (single commit).
- charter empty-config fix must not suppress genuinely-required companion tactics on a NON-empty config.

## Requirements

### Functional Requirements

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| FR-001 | Derive create-time topology default from branch/pr-bound context (feature-branch + no `--pr-bound` → `single_branch`, no coord branch) | High | Open |
| FR-002 | `--skip-pre-review-gate` flag + honor `SPEC_KITTY_SYNC_DISABLE`/minimal-import env on the pre-review gate | High | Open |
| FR-003 | Surface pre-review-gate progress (no silent multi-minute hang) | Medium | Open |
| FR-004 | `finalize-tasks --json` reports per-branch commit hashes for a two-branch commit set (facet B) | Medium | Open |
| FR-005 | `charter synthesize` empty/first-run config demands 0 companion tactics (first-run parity) | Medium | Open |
| FR-006 | Consolidate the sync-daemon env-deafness fix onto #2573 (one home, retire dup framing in #2555/#2570) | Low | Open |

### Non-Functional Requirements

| ID | Requirement | Category | Status |
|----|-------------|----------|--------|
| NFR-001 | Every behavior change (topology default, gate skip, finalize JSON shape, charter empty-config) carries a red-first or characterization test | Maintainability | Open |
| NFR-002 | 0 new ruff/mypy findings; terminology + arch gates green | Maintainability | Open |
| NFR-003 | Backward compatibility: primary/coord create, default gate enforcement, flat-mission finalize JSON, non-empty charter synth all unchanged | Reliability | Open |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | Pre-review-gate async redesign is OUT (deferred on #2573) — this mission does env+flag+progress only | Open |
| C-002 | #2549 facet A (lane mis-route of `status.*`) is OUT (deferred) | Open |
| C-003 | charter empty-config fix requires a charter/doctrine-owner decision; the naive test-seed fix is spec-forbidden | Open |
| C-004 | #2582/#2583 are post-mission ops, NOT WPs of this mission | Open |
| C-005 | Fork PR to Priivacy-ai/main; operator merges | Open |

## Success Criteria

- **SC-001**: A feature-branch create without `--pr-bound` yields `single_branch` (no manual flatten); primary/coord paths unchanged (red-first pinned).
- **SC-002**: The pre-review gate is skippable via flag + honors the disable env; default enforcement intact.
- **SC-003**: `finalize-tasks --json` reports the full two-branch commit set under coord topology; flat missions unchanged.
- **SC-004**: `charter synthesize` on an empty config demands 0 companion tactics (first-run parity restored).
- **SC-005**: Full gate green; #2581/#2573/#2549(B)/#2577 addressed; #2582/#2583 tracked as ops; epics stay open.

## Proposed work package outline (for /tasks materialization)

- **WP01 — Topology default (FR-001)**: `mission_create.py` + `core/mission_creation.py`; red-first feature-branch test. Independent. Closes #2581.
- **WP02 — Pre-review-gate skip/env/progress (FR-002/003, C-001)**: `tasks_move_task.py::_mt_run_pre_review_gate` + `review/pre_review_gate.py`; flag + env + progress tests. Closes #2573 (partial). *Owned-files note: overlaps the #2576 rollback seam module — coordinate if coord-shadows PR #2584 unmerged.*
- **WP03 — finalize-tasks per-branch hashes (FR-004, C-002)**: `mission_finalize.py` result builder + `coordination/commit_router.py`; two-branch + flat JSON-shape tests. Closes #2549 (facet B).
- **WP04 — charter empty-config parity (FR-005, C-003)**: `charter/_synthesis.py::_build_synthesis_request`; red-first empty-config parity test; charter/doctrine-owner decision. Closes #2577.
- **WP05 (optional stretch) — approve clean-tree scope (F6)**: scope the approve pre-flight to WP code, not all `kitty-specs/`; #2017.

DAG: all WPs independent (disjoint surfaces). WP02 has an external merge-coordination note vs coord-shadows PR #2584 (both touch `tasks_move_task.py`, different functions).

## Post-mission ops (operator-directed, NOT WPs)

- **#2582** — surface `/spec-kitty.analyze` as a required tasks→implement handoff step (doc/skill).
- **#2583** — don't gate the FIRST per-WP approval on whole-mission issue-matrix completeness (move to accept/merge). Note: touches approve-gate semantics — needs a targeted test even as an op.

## Assumptions

- Filed pre-spec: #2581 (topology default), #2582/#2583 (ops). #2573/#2549/#2577 pre-exist.
- Materialize via `spec-kitty agent mission create` in a clean checkout; if it defaults to coord on the feature branch, flatten per the documented procedure (this mission's FR-001 fixes that going forward).
