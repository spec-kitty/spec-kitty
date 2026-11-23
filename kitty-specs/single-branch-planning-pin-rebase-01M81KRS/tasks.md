# Tasks: single_branch planning pin across a rebase

**Mission**: `single-branch-planning-pin-rebase-01M81KRS` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first unit tests for the pin primitives (real temporary git repos) | WP01 | |
| T002 | `pin_branch_line(meta, target_branch)` | WP01 | |
| T003 | `follow_pin_by_patch_id` with a typed miss, over `patch_id_of` | WP01 | |
| T004 | Derivation anchors on the Mission `tasks/` directory and its last re-add | WP01 | |
| T005 | Red-first real-CLI tests: the #7793 scenario, no-match refusal, derived freeze, minted-branch window | WP01 | |
| T006 | Capture, refresh and derive on the pin branch line (single_branch) | WP01 | |
| T007 | Explicit re-pin follows by patch-id; named refusals | WP01 | |
| T008 | Window guard on re-pin and automatic refresh | WP01 | |
| T009 | Derived-pin freeze; `no_pin_underivable` reason and texts | WP01 | |
| T010 | `move-task` single_branch remedies name the live re-pin route | WP02 | |
| T011 | Doctor: warn on a `None` rebuilt pin; name next steps | WP02 | |
| T012 | ADR `2026-10-04-5` amendment and changelog fragment | WP02 | |

## Work Package WP01: Pin authority and finalize pin decisions

**Goal**: one resolver for the pin branch line, a patch-id follow and a derivation anchor that survives a re-add or a rename, wired into finalize. The #7793 re-pin follows by patch-id, a no-match refuses, no pin empties the window, a derived pin survives a plain finalize, and a minted-branch Mission pins on its mission branch. **Priority**: P1. **Independent test**: `tests/integration/test_7793_single_branch_repin_patch_id.py` through the real CLI.

**Dependencies**: None

Requirement refs: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, FR-009

T001 Red-first unit tests for the pin primitives (WP01)
T002 `pin_branch_line(meta, target_branch)` (WP01)
T003 `follow_pin_by_patch_id` with a typed miss (WP01)
T004 Derivation anchor on the Mission `tasks/` directory and its last re-add (WP01)
T005 Red-first real-CLI tests (WP01)
T006 Capture, refresh and derive on the pin branch line (WP01)
T007 Explicit re-pin follows by patch-id; named refusals (WP01)
T008 Window guard on re-pin and automatic refresh (WP01)
T009 Derived-pin freeze; `no_pin_underivable` reason and texts (WP01)

Prompt: [tasks/WP01-pin-authority-and-finalize-decisions.md](tasks/WP01-pin-authority-and-finalize-decisions.md)

## Work Package WP02: Messages, doctor and ADR

**Goal**: every message names a live next step; the doctor rebuild is never silent; the ADR records the rules and residuals. **Priority**: P2.

**Dependencies**: WP01

Requirement refs: FR-007, FR-010

T010 `move-task` single_branch remedies name the live re-pin route (WP02)
T011 Doctor: warn on a `None` rebuilt pin; name next steps (WP02)
T012 ADR amendment and changelog fragment (WP02)

Prompt: [tasks/WP02-messages-doctor-adr.md](tasks/WP02-messages-doctor-adr.md)
