# Tasks: Owned create root refuses a Mission worktree

**Mission**: owned-create-root-refuses-mission-worktree-01M6GRFM
**Branch**: `kitty/mission-owned-create-root-refuses-mission-worktree-01M6GRFM`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md)
**Issue**: #6956 — `mission create --owned-checkout` admits a registered coordination worktree

Close the documented residual in the create-level owned-claim minter: `resolve_owned_create_root`
validates the ownership claim and nothing else, so it admits a **registered coordination worktree**
and a **registered lane worktree**. `agent mission create --owned-checkout` therefore scaffolds a
Mission inside another Mission's coordination surface, and the leaf's refusal arrives only
afterwards. The fix adds the two Mission-worktree legs to the create claim, reusing the leaf's own
`_is_coordination_worktree` predicate and the canonical slug-free lane-worktree directory grammar,
under the leaf's own `OWNED_CHECKOUT_IS_MISSION_WORKTREE` code — one seam, one code, no new
resolver. The startup-gate selector and the Op record commands inherit it by construction.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first CLI test: `mission create --owned-checkout <registered coord worktree>` refuses with the typed code and scaffolds nothing, plus the same-fixture positive control | WP01 | — |
| T002 | Red-first CLI test: a registered lane worktree refuses the same way, plus the `.worktrees/`-housed non-lane positive control | WP01 | — |
| T003 | Extract one shared registry classification helper (single `git worktree list` read, fail-closed translation) and re-point `_require_not_mission_worktree` at it | WP01 | — |
| T004 | Add the two Mission-worktree legs to `resolve_owned_create_root` with its own refusal text and the leaf's code | WP01 | — |
| T005 | Minter unit pins: coord/lane refused, husk and non-lane `.worktrees/` checkout admitted, unreadable registry refused, one registry read per mint | WP01 | — |
| T006 | Run the targeted fast suites and the architectural gates; confirm the leaf and the single-authority allowlist are untouched | WP01 | — |
| T007 | Retire the "known residual" prose in `owned_mission.py` and `cli/commands/_owned_checkout.py` | WP02 | — |
| T008 | Add the changelog fragment for the user-visible refusal | WP02 | — |
| T009 | Verify the docs surfaces this change touches: changelog style, spelling, and that no generated docs index needs regeneration | WP02 | — |

---

## WP01 — Create claim refuses a Mission worktree

**Prompt**: [tasks/WP01-create-claim-refuses-mission-worktree.md](tasks/WP01-create-claim-refuses-mission-worktree.md)

**Summary**
- **Goal**: Make `resolve_owned_create_root` refuse a registered coordination worktree and a
  registered lane worktree, red-first through the real `agent mission create --owned-checkout`
  entry point, without adding a resolver, a predicate or a refusal code.
- **Priority**: P0 — the whole defect.
- **Independent test**: build a repository with a registered coordination worktree and a registered
  lane worktree, invoke `agent mission create <slug> --owned-checkout <each> --json`, and assert
  exit 1 with `OWNED_CHECKOUT_IS_MISSION_WORKTREE` plus an unchanged claimed checkout; on the same
  fixture, an ordinary linked owned checkout and a `.worktrees/`-housed non-lane checkout still
  create.
- **Dependencies**: none.
- **Risks**: a second registry read would double the git cost on the read-only startup path; a lane
  leg keyed on `WorktreeTopology.LANE_WORKTREE` alone would refuse a legitimate owned checkout
  under `.worktrees/`; an unreadable registry must refuse, not admit.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, NFR-004,
  SC-001, SC-002, C-001, C-002, C-003

**Subtasks**: T001, T002, T003, T004, T005, T006

---

## WP02 — Contract prose and changelog record

**Prompt**: [tasks/WP02-contract-prose-and-changelog.md](tasks/WP02-contract-prose-and-changelog.md)

**Summary**
- **Goal**: Retire the two docstrings that still document the residual as a known hole, and record
  the user-visible refusal in the changelog assembly.
- **Priority**: P1 — without it the next reader re-files this issue.
- **Independent test**: read the two docstrings and confirm they describe the create-level contract
  as delivered, and run `check_changelog_style` plus `check_spelling --pass unreleased`.
- **Dependencies**: WP01 (the prose describes the behaviour WP01 delivers).
- **Risks**: over-claiming — the Op record commands still validate no Mission, topology or write
  branch, and the prose must say exactly what is and is not now shared.
- **Requirements**: FR-006, SC-003, C-002, C-004

**Subtasks**: T007, T008, T009
