# Tasks: Owned single-branch lifecycle authority

**Mission**: owned-single-branch-lifecycle-authority-01M4J70Y
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research/provenance**: [research.md](./research.md)
**Topology**: single_branch (sequential WPs, one per command surface) · **Target**: main (PR-bound)

Six work packages, one per broken surface, chained sequentially (each depends on the previous) because every WP converges on the shared `OwnedCheckout` + placement seam. Each WP is ATDD red-first: adopt/rebase the issue's reproduction test (RED on the planning base) then the fix (GREEN). Completion is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`, not by ticking boxes.

## Subtask Index

| Task | Description | WP | Parallel |
|------|-------------|----|----------|
| T001 | ATDD: port owned decision reproduction (RED) | WP01 | |
| T002 | Thread owned through host decision verbs | WP01 | |
| T003 | Thread owned through decision service + emit placement | WP01 | |
| T004 | EXTEND owned through orchestrator-api decision verbs (#5874 D2) | WP01 | |
| T005 | Validate green | WP01 | |
| T006 | ATDD: port owned prerequisite reproduction (RED) | WP02 | |
| T007 | Thread owned.write_branch into prerequisite emitter | WP02 | |
| T008 | Validate green | WP02 | |
| T009 | ATDD: port owned requirement-mapping reproduction (RED) | WP03 | |
| T010 | Add --owned-checkout to map-requirements and mint once | WP03 | |
| T011 | Thread owned through mapping state + placement | WP03 | |
| T012 | Owned guard in emit_inner_state_changed | WP03 | |
| T013 | Validate green | WP03 | |
| T014 | ATDD #5880: port owned PR-bound finalization reproduction (RED) | WP04 | |
| T015 | ATDD #5892: port single-branch lane-preview reproduction (RED) | WP04 | |
| T016 | #5880 fix: consume owned write branch, skip legacy recovery | WP04 | |
| T017 | #5892 fix: single-branch lane preview parity | WP04 | |
| T018 | Validate green | WP04 | |
| T019 | ATDD recording: port owned analysis-recording reproduction (RED) | WP05 | |
| T020 | Recording fix: thread owned through discovery/placement/commit | WP05 | |
| T021 | ATDD authority: port template-mirror + owned-charter reproductions (RED) | WP05 | |
| T022 | Authority fix (rebased): admit package-identical mirror, owned charter generate | WP05 | |
| T023 | Validate green + terminology guard | WP05 | |
| T024 | Verify-green and record evidence | WP06 | |
| T025 | By-construction owned resolver-not-consulted invariant test (new) | WP06 | |
| T026 | Tidy latent smell (resolve → resolve_for_owned when owned) | WP06 | |
| T027 | Validate green | WP06 | |

## Work Packages

### WP01 — Decision Moment owned authority (#5874) · [tasks/WP01-owned-decision-authority.md](./tasks/WP01-owned-decision-authority.md)

- **Goal**: Resolve an owned single_branch mission at the Decision Moment entry points (host CLI + orchestrator-api) and thread the fact through the decision service/emit placement.
- **Priority**: P1 · **Dependencies**: none (specify entry point; MVP of the owned lifecycle).
- **Independent test**: owned open→list→resolve→verify lands under `owned.mission_dir`, zero repository-root leak.
- **Subtasks**: T001 T002 T003 T004 T005 · **Risk**: keep `resolve_owned_or_adopt` (non-owned fallback); extend orchestrator-api (branch omitted it).

### WP02 — Owned prerequisite branch contract (#5877) · [tasks/WP02-owned-prerequisite-branch.md](./tasks/WP02-owned-prerequisite-branch.md)

- **Goal**: Carry `owned.write_branch` as the prerequisite capsule's `expected_checkout_branch`.
- **Priority**: P1 · **Dependencies**: WP01.
- **Independent test**: protected-mint mission reports `branch_matches_target: true` with the minted write branch while keeping the protected landing target.
- **Subtasks**: T006 T007 T008 · **Risk**: non-owned passes `None` → identical legacy contract.

### WP03 — Owned requirement mapping (#5878) · [tasks/WP03-owned-requirement-mapping.md](./tasks/WP03-owned-requirement-mapping.md)

- **Goal**: Add `--owned-checkout` to map-requirements and thread the fact through selection, reads, protection and commit routing; refuse a foreign mission in `emit_inner_state_changed`.
- **Priority**: P1 · **Dependencies**: WP02.
- **Independent test**: mapping lands owned, stale primary untouched; foreign-mission annotation refused.
- **Subtasks**: T009 T010 T011 T012 T013 · **Risk**: `core/paths.py` untouched; confirm `mission_write_lock` composition.

### WP04 — Owned finalize-tasks (#5880 + #5892) · [tasks/WP04-owned-finalize-tasks.md](./tasks/WP04-owned-finalize-tasks.md)

- **Goal**: Consume the owned write branch in finalize branch setup (skip legacy recovery when owned) and compute the validate-only lane preview with the stored single_branch topology.
- **Priority**: P1 (#5880) / P2 (#5892) · **Dependencies**: WP03.
- **Independent test**: PR-bound owned finalize preserves the landing target and never calls the legacy triad; validate-only preview == real-run single lane.
- **Subtasks**: T014 T015 T016 T017 T018 · **Risk**: rebase small edits onto drifted base; preserve legacy refusal for non-owned.

### WP05 — Owned record-analysis + material/charter authority (#5893) · [tasks/WP05-owned-record-analysis.md](./tasks/WP05-owned-record-analysis.md)

- **Goal**: Resolve and record the owned mission's analysis from the owned checkout; admit a package-identical GLOBAL template mirror with a freshness identity and thread owned through `charter generate` (operator D3).
- **Priority**: P1 · **Dependencies**: WP04.
- **Independent test**: report commits on owned HEAD, primary unchanged; package-identical mirror admitted; external-authority guards (beyond the reviewed mirror) intact.
- **Subtasks**: T019 T020 T021 T022 T023 · **Risk**: keep the relaxation byte-identical only (C-002); run terminology guard.

### WP06 — Review/cycle owned resolver invariant (#5947) · [tasks/WP06-review-cycle-owned-invariant.md](./tasks/WP06-review-cycle-owned-invariant.md)

- **Goal**: Pin by construction that an owned review/cycle arm never consults `get_main_repo_root`; tidy the one latent smell. Verify-green (no fabricated red).
- **Priority**: P0 (nightly) · **Dependencies**: WP05.
- **Independent test**: poisoned-resolver invariant test passes; existing 24 tests stay green with no expectation edits.
- **Subtasks**: T024 T025 T026 T027 · **Risk**: cannot run the full nightly sweep in-mission; the invariant test hardens by construction.

## MVP

WP01 is the MVP slice — without owned Decision Moment resolution the owned lifecycle cannot even enter the specify interview.

## Dependencies & sequencing

Strict chain WP01 → WP02 → WP03 → WP04 → WP05 → WP06 (sequential single_branch). The dependency gate refuses to claim a WP until its predecessor is `approved`/`done`.
