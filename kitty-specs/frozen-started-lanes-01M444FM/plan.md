# Implementation Plan: Frozen lanes for started work packages

**Branch**: `issue-5573-frozen-started-lanes` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/frozen-started-lanes-01M444FM/spec.md`
**Grounding**: [research/code-grounding.md](research/code-grounding.md), post-specify squad
[research/squad-post-specify.md](research/squad-post-specify.md)

## Branch contract

- **Current branch at plan start**: `issue-5573-frozen-started-lanes`.
- **Planning/base branch**: `issue-5573-frozen-started-lanes`.
- **Merge target for completed changes**: `issue-5573-frozen-started-lanes` (`branch_matches_target: true`).
- **Publication**: `consolidate` lands lanes into this topic branch **locally only**; publication is a PR from this
  branch to `main`, merged by the operator.

## Summary

Re-finalizing an active mission recomputes lanes. Lane ids are then read back by membership overlap alone, so a
started work package can move to a different lane: by a tie, by greedy group order, or by re-minting an orphaned id
(#5573).

The fix makes started work packages' recorded lanes a **constraint input** of the pure lane computation:
- **Preserve:** a lane that holds started work keeps its id, and started lane-mates stay together.
- **Refuse:** only unsatisfiable cases are refused. These are two started lanes forced into one, a removed started
  work package, and a kind change across the planning lane. The refusal has one typed error,
  `LANE_MEMBERSHIP_FROZEN`.
- **Evidence:** the finalize shell gathers it (history-based started set from the status log, plus a lane-work-tip
  fallback).
- **Before any write:** the shell evaluates it in a read-only preflight before finalize's first status write, so
  `--validate-only` refuses identically. The write chokepoint re-checks it.

## Technical Context

**Language/Version**: Python 3.11+ (the repository's floor), mypy-strict clean, ruff clean, complexity ≤ 15
**Primary Dependencies**: typer and rich (CLI shell only), ruamel.yaml (frontmatter), git CLI (lane-tip refs); no
new dependency (C-006)
**Storage**: files: `kitty-specs/<mission>/lanes.json` (lane manifest), `status.events.jsonl` (append-only status log),
git refs `refs/spec-kitty/lane-tip/<branch>`
**Testing**: pytest. Compute-level tests are `fast`, including the stdlib `itertools` permutation sweep.
End-to-end tests are `integration` + `git_repo`; they drive the real `finalize_tasks` with real git and real lane
worktree allocation.
**Target Platform**: the Spec Kitty CLI on Linux, macOS and Windows (git required)
**Project Type**: single project (`src/specify_cli`, `tests/`)
**Performance Goals**: re-finalize overhead ≤ 200 ms for 30 work packages (NFR-001). That is one event-log read and
one `git for-each-ref` for all lane tips.
**Constraints**:
- lane computation and the compute-and-persist core stay git-free and meta-free (C-002);
- existing refusal texts stay byte-identical (C-003);
- no new gates or allowlists (C-004);
- `implement.py` and `core/mission_creation.py` are untouched (C-005).
**Scale/Scope**: about 6 source files and about 8 test files; no layer move; one new ADR

## Charter Check

| Charter rule | Status | How the plan honours it |
|---|---|---|
| Single canonical authority | PASS | One "started" predicate (`lanes.frozen_membership.started_wp_ids`, consuming the status facade's `StatusEvent`/`Lane`). One invariant owner (`lanes.compute`), re-checked at the single `lanes.json` write chokepoint. The two older "execution begun" predicates answer a different question; their unification is filed as #5702. |
| Architectural alignment / layer pair | PASS | All surfaces are inside `specify_cli`. `lanes → status` already imports through the facade. Compute stays pure: the shell resolves evidence, the same pattern as `planning_commit_sha`. |
| ATDD-first / Standing Order 4 (red-first) | PASS | WP01 commits the red end-to-end reproduction through `agent mission finalize-tasks` before any fix commit. |
| Standing Order 2 / DIRECTIVE_025 (tidy-first, boy-scout) | PASS | WP01 opens with behaviour-preserving enablers: extract the status read-dir resolver, and a shared finalize test runner that records the exit code. Boy-scout fixes are scoped to touched test files (the vacuous #3311 / provenance-guard assertions). |
| Standing Order 5 (non-vacuous gates) / C-004 | PASS | No new architectural gate or allowlist. The invariant is pinned by behaviour tests, including a permutation sweep with a same-fixture positive control. |
| Refusals: named code, non-destructive remedy (#3931 / #5078) | PASS | `LANE_MEMBERSHIP_FROZEN` with a reason-specific remedy. No reset/restore/delete recipes. |
| Existing refusal texts byte-identical | PASS | No existing message or code changes. A new error branch is added in the terminal renderer. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted dirs plus named architectural gate files only (see Test plan). |
| Terminology canon | PASS | Mission / work package; `--mission` in remedies. The terminology guard runs. |
| Pack tiers | N/A | No doctrine pack edits. |
| ADR for architectural change | PASS | New ADR `docs/adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md`. |

No violations, so Complexity Tracking is empty.

## Design

### Flow (after the fix)

```mermaid
sequenceDiagram
    participant CLI as finalize_tasks (mission_finalize.py)
    participant Pre as frozen-lane preflight (mission_finalize_lanes.py)
    participant St as status facade (read_events) + started_wp_ids
    participant Tip as lane_tip (recorded_tip_branches)
    participant FM as lanes.frozen_membership (pure)
    participant C as lanes.compute (pure)
    participant P as compute_and_persist (writer)
    CLI->>Pre: after ownership gates, before first status write
    Pre->>St: read events (absent → ∅; malformed/unresolvable → refuse)
    Pre->>Tip: one for-each-ref (only when lanes.json exists)
    Pre->>FM: build_frozen_membership(previous, started, tips, present, eligible)
    Pre->>C: compute_lanes(..., previous_lanes, frozen=…)  (dry, no write)
    C-->>CLI: LaneMembershipFrozenError → terminal renderer, exit 1, restore
    CLI->>P: pipeline: compute_and_write_lanes(..., frozen=…)
    P->>C: compute_lanes(frozen) then assert_frozen_membership_honoured → write
```

### The constraint inside `compute_lanes` (pure)

The new keyword-only input is `frozen: FrozenLaneMembership | None = None`. The default `None` keeps every
existing caller byte-identical.

1. **Kind and removal checks.** For each binding `wp → lane` (lane taken from the previous manifest):
   - the WP is absent from the dependency graph and not retired → conflict `started_wp_removed`;
   - the WP is now a planning artifact but bound to a code lane, or the reverse → conflict `started_wp_kind_changed`;
   - the WP is absent and retired (excluded by the existing #3713 cancellation projection) → no conflict, but its lane
     id is reserved.
2. **Keep started lane-mates together.** After the overlap rules (so their evidence is still logged), union every pair of present code WPs bound to the
   same lane id. Record a `CollapseEvent(rule="frozen_lane_membership")`, so the collapse report shows why.
3. **Pass 0 of `_assign_stable_lane_ids`.** For each group, compute the set of distinct bound lane ids of its members:
   - one id → the group takes it;
   - two or more → conflict `started_lanes_collapsed`, naming every bound WP and lane.
4. **Passes 1 and 2 (unchanged algorithm, documented).**
   - Pass 1: overlap read-back over the ids not yet claimed (most shared members, then the lowest prior lane id).
   - Pass 2: mint the next free id, skipping every id claimed **and** every reserved id (FR-004).
5. **Raise once.** All conflicts are collected and raised together as `LaneMembershipFrozenError(conflicts)` before
   any manifest is built.
6. `SINGLE_BRANCH` ignores `frozen`: there is one repository-root lane and nothing to move.

### Evidence (the finalize shell, IO allowed)

- **Status surface.** Resolve the read dir with the extracted `_resolve_status_read_dir` (the same coordination-aware
  recipe `_execution_has_begun` uses; tidy-first extraction).
  - No `lanes.json` yet → frozen is empty (first finalize, unchanged).
  - Surface unresolvable → raise `status_unreadable`.
  - No event log → no history-started WPs.
  - `StoreError` → raise `status_unreadable`.
- **Started set.** `started_wp_ids(events)` is pure and lives in `lanes/frozen_membership.py`. It consumes `StatusEvent`
  and `Lane` through the `specify_cli.status` facade, so `status/__init__.py` is not modified. A WP is started if any of its events has `to_lane ∉ {planned, blocked, canceled}`.
- **Lane-tip fallback.** `lane_tip.recorded_tip_branches(repo_root)` makes one `git for-each-ref` call. For each prior
  code lane with no history-started member, if `lane_created_branch(previous, lane_id)` has a tip, all of that lane's
  prior members count as started.
- **Builder.** `build_frozen_membership(previous, started, tipped_branches, present_wp_ids, eligible_wp_ids)`, pure, in
  `lanes/frozen_membership.py`:
  - bindings: started WPs that are recorded in a lane;
  - retired: present minus eligible.

### Preflight and threading

- **Preflight placement.** `finalize_tasks` calls `_preflight_frozen_lane_membership` right after
  `_run_finalize_ownership_gates` and before `_emit_tasks_started`, the first status write. This covers
  `--validate-only` too. Skipped when:
  - the run is a `--refresh-planning-commit` run (it never recomputes membership);
  - the mission has no code lanes (`SINGLE_BRANCH`).
- **Preflight work.** It builds the frozen membership and dry-runs `compute_lanes` with the previous manifest. On
  success it returns the `FrozenLaneMembership`, which is threaded through `_run_commit_pipeline` →
  `_compute_and_write_lanes` → `compute_and_write_lanes(frozen=…)`. The evidence is read once and the result is
  deterministic.
- **Validate-only preview.** `_emit_validate_only_report` passes `previous_lanes` and `frozen` to its preview compute,
  so the preview lane ids match a real run (squad finding 13).
- **Writer chokepoint.** `compute_and_write_lanes` runs `assert_frozen_membership_honoured(manifest, frozen)` before
  `write_lanes_json`, as defence in depth. It sits beside `assert_topology_matches_manifest`.
- **Rendering.** `_emit_finalize_error_with_revert_note` gets a `LaneMembershipFrozenError` branch:
  - JSON: `{"error", "error_code", "reason", "conflicts", "next_step"}`;
  - console: one line per conflict plus the remedy.

  The existing except path restores the mission write scope (frontmatter, `tasks.md`, `meta.json`), so a refusal
  leaves everything byte-identical (SC-003).

### Refusal contract

See [contracts/lane-membership-frozen.md](contracts/lane-membership-frozen.md). There is one code,
`LANE_MEMBERSHIP_FROZEN`, and the `reason` is one of:
- `started_lanes_collapsed`
- `started_wp_removed`
- `started_wp_kind_changed`
- `status_unreadable`

When conflicts carry several reasons, the top-level reason is the first in that order, and each conflict carries its
own reason and remedy.

## Project Structure

### Documentation (this mission)

```
kitty-specs/frozen-started-lanes-01M444FM/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/lane-membership-frozen.md
├── research/code-grounding.md, research/squad-post-specify.md
├── traces/ (tooling-friction.md, approach.md, design-decisions.md)
└── tasks.md + tasks/WP*.md   (/spec-kitty.tasks)
```

### Source code touched

```
src/specify_cli/
├── lanes/frozen_membership.py            # NEW: started_wp_ids, FrozenLaneMembership, MembershipConflict, build_frozen_membership,
│                                         #      assert_frozen_membership_honoured (all pure)
├── lanes/compute.py                      # + LaneMembershipFrozenError; frozen input in compute_lanes /
│                                         #   _assign_stable_lane_ids (pass 0, pre-union, reservation)
├── lanes/compute_and_persist.py          # + frozen kw; chokepoint post-check
├── lanes/lane_tip.py                     # + recorded_tip_branches(repo_root) (one for-each-ref)
└── cli/commands/agent/
    ├── mission_finalize_planning_pin.py  # tidy-first: extract _resolve_status_read_dir
    ├── mission_finalize_lanes.py         # + _gather_frozen_lane_membership, _preflight_frozen_lane_membership;
    │                                     #   frozen threaded into compute_and_write_lanes
    ├── mission_finalize.py               # preflight call + re-export; thread frozen into the pipeline
    ├── mission_finalize_commit.py        # thread frozen; LaneMembershipFrozenError render branch
    └── mission_finalize_bootstrap.py     # validate-only preview: previous_lanes + frozen
docs/adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md   # NEW
docs/architecture/execution-lanes.md, docs/api/finalize-tasks-internals.md,
docs/context/topology.md (glossary: started work package, LANE_MEMBERSHIP_FROZEN), CHANGELOG.md
tests/
├── integration/test_refinalize_keeps_started_lanes.py   # NEW e2e (red-first)
├── lanes/test_frozen_lane_membership.py                     # NEW compute-level + permutation sweep (fast)
├── lanes/test_lane_identity.py                              # merge/split/tie cases; boy-scout
├── status/test_compute_and_persist_core.py                  # chokepoint post-check
└── specify_cli/cli/commands/agent/test_finalize_provenance_guard.py,
    test_issue_3311_finalize_rewrites_active_lanes.py        # boy-scout: real lane assertions, exit code recorded
```

**Structure decision**: a single project. The new pure module `lanes/frozen_membership.py` keeps
`compute.py` (1,102 lines) from growing a second concern. It holds the evidence model and the builder; `compute.py`
only consumes it.

## Test plan (blast radius, per CLAUDE.md and NO_FULL_HEAVY_SUITES_IN_MISSION)

- **Baseline:** `make test-fast`.
- **Owning directories:**
  - `tests/lanes`
  - `tests/status`
  - `tests/specify_cli/cli/commands/agent` (finalize/mission)
  - `tests/specify_cli/lanes`
  - `tests/cli`, filtered by `-k "finalize or lanes"`
  - `tests/integration`, filtered by `-k finalize`
  - `tests/tasks/test_finalize_tasks_lanes_disjoint_fan_in.py`
  - `tests/unit/migration/test_mission_state_lanes_rebuild.py`
- **Architectural gate files (specific):**
  - `test_status_module_boundary.py`
  - `test_cold_import_status_boundary.py`
  - `test_finalize_refresh_pin_authority.py`
  - `test_json_contract_enumeration.py`
  - `test_no_write_side_rederivation.py`
  - `test_status_events_writes_gate.py`
  - `test_cli_error_surface_seam.py`
  - `test_no_worktree_name_guess.py`
  - `test_layer_rules.py`
  - `test_no_dead_symbols.py` (the live dead-symbol gate; the allowlist-contract file cannot fail)
  - `test_no_legacy_terminology.py`
  - `test_ruff_format_enforcement.py` (formatting is checked through `ruff format --check --force-exclude` on the
    changed files)
- **Quality:** `ruff check`, `ruff format --check --force-exclude <files>`, `mypy` on the changed files. Complexity is measured with `ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15'`, because `ruff.toml` baselines C901 off for `compute.py`. `compute_lanes` (already 35) must not grow, and every new helper is ≤ 15.

**Red-first evidence.** WP01's end-to-end test fails on the base commit with exit 0 and WP02 on lane-a. It passes after
WP03.

**Property sweep (stdlib).** WPs WP01–WP04 start in two or three prior lanes. The sweep covers:
- every subset of started WPs;
- amendments: merge two lanes, merge three, split, add, remove;
- both lane-id orders.

The invariant: every started WP keeps its id, or the run raises `LaneMembershipFrozenError`. The positive control on
the same fixtures: with the started set empty, the result equals the base-commit algorithm.

## Implementation Concern Map

### IC-01 — Tidy-first enablers and the red reproduction

- **Purpose**: make the fix testable without behaviour change, then pin #5573 red through the real entry point.
- **Relevant requirements**: C-001, C-007, FR-001, FR-002, FR-005, FR-006 (end-to-end assertions), FR-011.
- **Affected surfaces**: `mission_finalize_planning_pin.py` (extract `_resolve_status_read_dir`); finalize test
  helpers; the new `tests/integration/test_refinalize_keeps_started_lanes.py`; boy-scout lane assertions in the
  #3311 and provenance-guard tests.
- **Sequencing/depends-on**: none.
- **Risks**: the red tests must fail for the right reason (lane moved / exit 0), not for harness errors. Plain `LANES`
  topology must be built with `make_mission(topology=LANES)`.

### IC-02 — The pure invariant: started predicate, frozen membership, lane computation, writer check

- **Purpose**: close the defect class by construction in the pure core.
- **Relevant requirements**: FR-001–FR-005, FR-008, FR-010, NFR-002, NFR-004, C-002, C-006.
- **Affected surfaces**: `lanes/frozen_membership.py` (new; includes `started_wp_ids`);
  `lanes/compute.py`; `lanes/compute_and_persist.py`; `lanes/lane_tip.py` (`recorded_tip_branches`); compute-level
  tests and the permutation sweep.
- **Sequencing/depends-on**: none. It can run in parallel with IC-01.
- **Risks**:
  - existing `test_lane_identity` / `test_compute` tests must stay byte-identical with `frozen=None`;
  - keep `_assign_stable_lane_ids` at complexity ≤ 15 by extracting the pass helpers.

### IC-03 — Finalize wiring: evidence, preflight, validate-only, rendering

- **Purpose**: feed real evidence into the constraint, and refuse before the first write with the named code.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-009, SC-001, SC-003, NFR-001, C-003, C-005.
- **Affected surfaces**: `mission_finalize_lanes.py`, `mission_finalize.py`, `mission_finalize_commit.py`,
  `mission_finalize_bootstrap.py`; more end-to-end tests:
  - malformed log refuses;
  - absent log proceeds;
  - removed started WP refuses;
  - the remedy resolves the refusal;
  - validate-only refuses.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**:
  - `_emit_tasks_started` is the first status write, so the preflight must precede it;
  - re-exports from `mission_finalize` keep historical patch targets working;
  - `--refresh-planning-commit` must skip the preflight.

### IC-04 — Decision record and operator docs

- **Purpose**: record the invariant and the refusal contract where operators and maintainers look.
- **Relevant requirements**: FR-006 (operator-facing remedy), C-008; post-specify squad findings 8 and 15.
- **Affected surfaces**: the new 4.x ADR; `docs/architecture/execution-lanes.md` (re-finalize section and lane-id
  rule); `docs/api/finalize-tasks-internals.md`; the `docs/context/topology.md` glossary; `CHANGELOG.md`.
- **Sequencing/depends-on**: IC-02 (the semantics are fixed by the spec and the contract).
- **Risks**: docs must mirror shipped behaviour; reconcile against the final code before accept.
