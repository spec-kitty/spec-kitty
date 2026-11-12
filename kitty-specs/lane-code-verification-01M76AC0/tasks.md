# Tasks: Lane worktrees run and verify lane code

**Mission**: `lane-code-verification-01M76AC0` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `fix/7547-lane-code-verification`

Subtask completion is event-sourced: record it with
`spec-kitty agent tasks mark-status Txxx --status done --mission lane-code-verification-01M76AC0`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red tests: builder environment recipe and probe (planted change, lane-venv foreign/verified pair) | WP01 | |
| T002 | `LaneTestInvocation` + `build_lane_test_invocation` + `environ()` | WP01 | |
| T003 | Probe: tracked regular packages under `src/`, interpreter choice, `find_spec` child, 5 s timeout | WP01 | |
| T004 | `origin_inside` with injectable path module (POSIX + Windows forms) | WP01 | [P] |
| T005 | `EvidenceTree` capture via `kernel.git` (HEAD, dirty, relative path) | WP01 | |
| T006 | Red tests: `implement --json` key + banner + planted change through the CLI | WP02 | |
| T007 | `LaneWorkspaceResult.lane_test_invocation` (default `None`), built at return | WP02 | |
| T008 | `implement --json` key and banner block; update the two exact-shape goldens | WP02 | |
| T009 | Prompt blocks in implement and review prompt builders (extracted renderer) | WP02 | |
| T010 | Red tests: `run_env` reaches both runners; baseline uses the same recipe; aggregation REFUSE tier | WP03 | |
| T011 | `GateOutcome.FOREIGN_TREE`; plain `run_env` parameter through `evaluate_*` to `_run_raw_command` and `run_scoped_tests_at_head`; strip list moves to the leaf | WP03 | |
| T012 | Baseline run applies the environment recipe rooted at the baseline worktree | WP03 | |
| T013 | `TransitionGateContext.run_env` → handler | WP03 | [P] |
| T014 | `AggregateDecision.REFUSE`, `refusing_verdicts`, `should_exit` | WP03 | [P] |
| T015 | Red tests through `move-task --to for_review`: refusal, same-fixture positive control, `--force`, unverified never refuses, skip path untouched | WP04 | |
| T016 | Hook builds invocation + probe + evidence inside the fail-open; `FOREIGN_TREE` short-circuit; `run_env` into context and override tier | WP04 | |
| T017 | Effect: representative, `refused` flag, third emit branch with `EVIDENCE_TREE_MISMATCH`, console line | WP04 | |
| T018 | Metadata: conditional `evidence_tree`, `force_bypassed` for foreign, `bypassed_refusal`; hand-authored parity cell | WP04 | |
| T019 | ADR `2026-08-13-6` amendment (provenance refusal, `--force`, fault carve-out) | WP05 | |
| T020 | Changelog fragment `7554.fixed.md` | WP05 | [P] |
| T021 | Red tests: a lane created by `spec-kitty implement` in a pinning repo gets verified packs trees (warm cache) / remedy and no tree (cold cache) | WP06 | |
| T022 | `lane_packs.place_pinned_packs(lane)`: read lane pins, offline `fetch_to_cache`, `place_pack`, report | WP06 | |
| T023 | Call it from `open_lane_checkout` after the worktree is added; surface the remedy on a cold cache | WP06 | |

## Phase 1 — Foundation

### WP01 — Lane test invocation and probe (IC-01)
Prompt: [tasks/WP01-lane-test-invocation-and-probe.md](tasks/WP01-lane-test-invocation-and-probe.md)
- **Goal**: one leaf module that builds a lane's test invocation and proves which tree it loads.
- **Priority**: P1 · **Dependencies**: none
- **Independent test**: unit + child-process tests in `tests/lanes/test_lane_invocation.py`.

T001 Red tests: builder environment recipe and probe (WP01)
T002 `LaneTestInvocation` + `build_lane_test_invocation` + `environ()` (WP01)
T003 Probe: tracked regular packages, interpreter choice, `find_spec` child, timeout (WP01)
T004 `origin_inside` with injectable path module (WP01)
T005 `EvidenceTree` capture via `kernel.git` (WP01)

Risks: probe interpreter choice; Windows paths; namespace packages excluded by design.

## Phase 2 — Surfaces (parallel after WP01)

### WP02 — Implement and prompts carry the invocation (IC-02)
Prompt: [tasks/WP02-implement-and-prompts-carry-the-invocation.md](tasks/WP02-implement-and-prompts-carry-the-invocation.md)
- **Goal**: `implement` prints/returns the verified invocation; implement and review prompts state it.
- **Priority**: P1 · **Dependencies**: WP01
- **Independent test**: planted change through `spec-kitty implement --json` (SC-001); prompt render tests (SC-003).

T006 Red tests through the implement CLI (WP02)
T007 `LaneWorkspaceResult.lane_test_invocation` (WP02)
T008 `--json` key, banner, golden updates (WP02)
T009 Prompt blocks (WP02)

Risks: open PR #7562 edits `implement_support.py` (`_claim_dirty_paths`); keep away from it.

### WP03 — Gate engine accepts a run environment and a refusal tier (IC-03, engine half)
Prompt: [tasks/WP03-gate-engine-run-environment-and-refusal-tier.md](tasks/WP03-gate-engine-run-environment-and-refusal-tier.md)
- **Goal**: the review engine runs head and baseline in the invocation's environment and knows the `foreign_tree` refusal tier.
- **Priority**: P1 · **Dependencies**: WP01
- **Independent test**: env-recorder tests on both runners and the baseline; aggregation unit cells.

T010 Red tests (WP03)
T011 `FOREIGN_TREE` + `run_env` plumbing (WP03)
T012 Baseline symmetry (WP03)
T013 Context `run_env` → handler (WP03)
T014 Aggregation REFUSE tier (WP03)

## Phase 3 — Gate hook

### WP04 — The for_review hook records evidence and refuses a foreign tree (IC-03, hook half)
Prompt: [tasks/WP04-for-review-hook-evidence-and-refusal.md](tasks/WP04-for-review-hook-evidence-and-refusal.md)
- **Goal**: `move-task --to for_review` records the evidence tree and refuses `EVIDENCE_TREE_MISMATCH` unless `--force`.
- **Priority**: P1 · **Dependencies**: WP01, WP02, WP03
- **Independent test**: CLI move-task tests with the lane-venv fixture pair (SC-002, SC-004).

T015 Red tests through move-task (WP04)
T016 Hook builds invocation/probe/evidence (WP04)
T017 Refusal effect (WP04)
T018 Metadata + parity cell (WP04)

### WP06 — New lanes get the pinned packs trees (#7577)
Prompt: [tasks/WP06-new-lanes-get-pinned-packs.md](tasks/WP06-new-lanes-get-pinned-packs.md)
- **Goal**: `spec-kitty implement` places the pinned, verified packs trees into a new lane.
- **Priority**: P1 · **Dependencies**: none
- **Independent test**: `spec-kitty implement` in a pinning fixture repo with a warm / cold cache.

T021 Red tests (WP06)
T022 Placement helper (WP06)
T023 Wire into lane creation (WP06)

## Phase 4 — Close-out

### WP05 — ADR amendment and changelog (IC-04)
Prompt: [tasks/WP05-adr-amendment-and-changelog.md](tasks/WP05-adr-amendment-and-changelog.md)
- **Goal**: governance record for the new refusal; user-facing changelog entry.
- **Priority**: P2 · **Dependencies**: WP04, WP06

T019 ADR amendment (WP05)
T020 Changelog fragment (WP05)

## MVP

WP01 + WP02 deliver the verified invocation (US1, US2); WP03 + WP04 deliver the gate (US3).
The sub-epic's done-when needs all four code packages.
