# Tasks: Consolidate target-branch tip-capture helper + reclaim tasks-lifecycle squad MINORs

**Mission**: git-tip-helper-consolidation-01M3D4RT
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Single cohesive work package: the tip-capture consolidation and the two folded tidies
share a `core/vcs/git.py` + `mission_finalize.py` blast radius, so a split would
violate the non-overlapping-`owned_files` finalize gate. CORE rigour (error-handling
contract blast radius).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add `capture_branch_tip` to `core/vcs/git.py` (`--verify`, env param, documented ambiguity/error contract) | WP01 | |
| T002 | Reroute the 6 classifier-tip capture sites; delete `_capture_target_branch_tip`; migrate the 2 test patch/producer seams + refresh 3 stale docstring comments | WP01 | |
| T003 | Agreement test (valid / missing / ambiguous refs) — RED on ambiguous against bare `rev-parse`, GREEN with `--verify` | WP01 | |
| T004 | #4593 item1 — `full_history` param on `git_rev_list_count`; pass it at `tasks_dependency_graph.py`; issue-pinned merge-rich regression | WP01 | |
| T005 | #4152 item2 — remove dead `_raw_frontmatter_has_field` guard + redundant per-WP read; prove resolution unchanged | WP01 | |
| T006 | #4152 item3 — make the cyclic-dependency exit-code assertion load-bearing (drop `or 1`) | WP01 | |
| T007 | Blast-radius verification (targeted tests + ruff/format/mypy on touched files) + tracer append | WP01 | |

## Work Packages

### WP01 — Consolidate target-branch tip-capture + fold #4593 item1 and #4152 items 2&3

**Goal**: One canonical `capture_branch_tip` authority for every `classify_recorded_pin`
tip caller, with a documented ambiguity/error contract proven by a cross-call-path
agreement test; plus the two folded, behaviour-preserving tidies.
**Priority**: P1 (anchor).
**Execution mode**: code_change · **Rigour**: CORE.
**Independent test**: the agreement test (T003) is RED on the ambiguous-ref case against
the pre-consolidation bare-`rev-parse` path and GREEN after; existing tip/finalize/move-task
suites stay green (behaviour-preserving for valid refs).

**Included subtasks**: T001, T002, T003, T004, T005, T006, T007

**Implementation sketch**:
1. Add the helper (T001) → 2. reroute callers + delete the old helper + fix patch seams (T002)
→ 3. lock the contract with the agreement test (T003) → 4. fold #4593 (T004) → 5. fold #4152
items 2 & 3 (T005, T006) → 6. verify blast radius + tracer (T007).

**Dependencies**: none.
**Risks**: whack-a-field — `test_mission_finalize_phases.py:1083` monkeypatches
`_capture_target_branch_tip` and `test_lane_base_common_ancestor.py:378-395` imports/asserts
it directly; both must be migrated, not left dangling. Deleting the helper without updating
those seams reds the suite.

**Prompt**: [tasks/WP01-consolidate-tip-capture.md](./tasks/WP01-consolidate-tip-capture.md)

## Excluded / declined (recorded — Epic #4883 "never silently lost")

- **#4152 item 1** — DECLINED (conflicts with item 2; warns on the intended #4135 path).
- **#4593 item 2** — DECLINED (body-form on merged PR #4581).
- **#4611 (all)** — DROPPED; reparented under Epic #4441 (template authoring-contract completeness).

See [spec.md](./spec.md#issue-matrix-mandatory--mission-addresses-github-issues) for the full disposition ledger.
