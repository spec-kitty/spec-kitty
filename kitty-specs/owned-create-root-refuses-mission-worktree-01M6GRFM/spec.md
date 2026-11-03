# Mission Specification: Owned create root refuses a Mission worktree

**Mission Branch**: `kitty/mission-owned-create-root-refuses-mission-worktree-01M6GRFM`
**Created**: 2026-11-03
**Status**: Draft
**Input**: Issue #6956 — "[bug] mission create --owned-checkout admits a registered coordination worktree"

## Summary

`resolve_owned_create_root` is the one create-level owned-claim minter. It runs the
ownership-claim check (foreign, nested, broken pointer, repository root) and nothing
else, because at create time no Mission is bound: there is no `meta.json`, no
`lanes.json`, no topology and no write branch to validate. That was deliberate, and it
left a documented residual: a **registered** coordination worktree — and a registered
lane worktree — is admitted as the create root.

Two commands consume that permissive admission:

1. `spec-kitty agent mission create <slug> --owned-checkout <coord-worktree>` scaffolds a
   whole new Mission inside another Mission's coordination worktree, and only the leaf
   guards refuse *after* the scaffold decision.
2. The read-only startup gates (`startup_project_checkout`) and the Op record commands
   (`resolve_owned_op_record_root`) consult that checkout for schema, legacy and record
   placement.

Nothing escalates today — write custody is unchanged and the startup consult is
read-only — so this is a P3 boundary defect, not a live escalation. It is still a
boundary defect: the same claim is refused by the leaf and admitted by the create.

**Decision (the issue's "What to decide").** Refuse at the create claim, with the leaf's
own refusal code, decided by the leaf's own predicates. A refusal that arrives *after* a
scaffold decision has already cost the operator a half-created Mission; the create seam
is where the claim is minted, so it is where a claim the leaf would refuse must die. The
fix adds no resolver, no refusal code and no second authority for "is this checkout
registered to a Mission".

## User Scenarios & Testing

### User Story 1 - A coordination worktree is refused before anything is scaffolded (Priority: P1)

An operator, or an automated runner, passes `--owned-checkout` pointing at a registered
coordination worktree (`<repo>/.worktrees/<mission>-<mid8>-coord`). The create command
refuses with the leaf's typed code `OWNED_CHECKOUT_IS_MISSION_WORKTREE`, and no
`kitty-specs/<slug>` directory, no branch switch and no commit happens in that checkout.

**Why this priority**: this is the reported defect and the only path with a side effect.

**Independent Test**: build a repository with a materialised, registered coordination
worktree, invoke the real `agent mission create --owned-checkout <coord> --json` entry
point, and assert exit 1, the typed refusal payload, and that the claimed checkout's tree
and branch are byte-identical afterwards.

**Acceptance Scenarios**:

1. **Given** a repository whose coordination worktree is registered and materialised,
   **When** `agent mission create <slug> --owned-checkout <coord-worktree> --json` runs,
   **Then** it exits non-zero with `OWNED_CHECKOUT_IS_MISSION_WORKTREE` and writes nothing
   into the claimed checkout.
2. **Given** the same repository, **When** the same command names an ordinary linked
   owned checkout, **Then** the create proceeds exactly as it does today (positive
   control on the same fixture).

### User Story 2 - A registered lane worktree is refused at the create claim too (Priority: P2)

An operator passes `--owned-checkout` pointing at a registered lane worktree
(`<repo>/.worktrees/<slug>-lane-<id>`). The create claim refuses it with the same typed
code, instead of scaffolding a Mission into another Mission's lane write surface.

**Why this priority**: same class, narrower blast radius (a lane worktree exists only for
a Mission that already has `lanes.json`), and it is the second half of the residual the
issue names.

**Independent Test**: build a repository with one registered lane worktree, invoke the
real `agent mission create --owned-checkout` entry point, and assert the typed refusal and
the unchanged checkout.

**Acceptance Scenarios**:

1. **Given** a registered lane worktree, **When** a create names it, **Then** it is
   refused with `OWNED_CHECKOUT_IS_MISSION_WORKTREE` before any scaffold.
2. **Given** a linked owned checkout that merely *lives under* `.worktrees/` but whose
   directory name is not a lane-worktree name, **When** a create names it, **Then** it is
   admitted (the carrier-contract trap: classification alone must never refuse it).

### User Story 3 - The refusal reaches every create-seam consumer, and the docs stop claiming otherwise (Priority: P3)

Because the refusal lives in the minter and not in one command, the read-only startup
consult and the Op record commands inherit it, and the docstrings that documented the old
residual stop documenting a residual that no longer exists.

**Why this priority**: consistency and honesty of the seam; no new behaviour beyond 1 and 2.

**Independent Test**: assert the startup-gate selector returns the repository root for a
coordination-worktree claim (its fail-safe path), and grep-level assertion that the
"known residual" prose is gone from both modules.

**Acceptance Scenarios**:

1. **Given** a coordination-worktree claim, **When** the read-only startup selector runs,
   **Then** it keeps the repository root for startup gates rather than redirecting them.
2. **Given** the final diff, **When** a reader opens `_owned_checkout.py` and
   `owned_mission.py`, **Then** the create-level contract is described as it now behaves.

### Edge Cases

- **Unregistered `-coord` directory (husk)**: not refused. The registry disposes, not the
  name — the same rule the leaf already applies.
- **A legitimate owned checkout under `.worktrees/`**: admitted; its directory name does
  not parse as a lane-worktree name, so the lane leg does not fire.
- **Symlinked claim to a coordination worktree**: refused, because the predicates classify
  the resolved path (the claim is already resolved before the check runs).
- **Unreadable worktree registry**: refusal, fail closed, with the registry exception's own
  error code — mirroring `_require_not_mission_worktree`.
- **No `--owned-checkout`**: unchanged; the create seam is not consulted at all.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Create claim refuses a coordination worktree | As an operator, I want `--owned-checkout` pointing at a registered coordination worktree refused at the create claim, so that a Mission is never scaffolded inside another Mission's coordination surface. | High | Open | [build] | no |
| FR-002 | Create claim refuses a lane worktree | As an operator, I want `--owned-checkout` pointing at a registered lane worktree refused at the create claim, so that a Mission is never scaffolded into another Mission's lane write surface. | High | Open | [build] | no |
| FR-003 | One refusal code, one predicate owner | As a maintainer, I want the create refusal to reuse the leaf's `OWNED_CHECKOUT_IS_MISSION_WORKTREE` code and the leaf's existing coordination predicate, so that the two altitudes cannot drift apart. | High | Open | [build] | no |
| FR-004 | Every create-seam consumer inherits it | As a maintainer, I want the refusal to live in the minter, so the startup-gate consult and the Op record commands inherit it without each re-implementing it. | Medium | Open | [build] | no |
| FR-005 | Legitimate owned checkouts stay admitted | As an operator, I want an ordinary linked owned checkout — including one physically under `.worktrees/` — to keep working, so the fix does not trade one false admission for one false refusal. | High | Open | [ratchet] | yes — guarded by the same-fixture positive control in US1-AS2 and US2-AS2 |
| FR-006 | The documented residual is retired | As a reader, I want the docstrings in `owned_mission.py` and `_owned_checkout.py` to describe the create-level contract as it now behaves, so that the next reader does not re-file this issue. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new git call per claim | The create-record refusal may add at most ONE worktree-registry read per minted claim, on the same budget the leaf already spends, so the read-only startup path does not gain a per-command git cost. | Performance | High | Open |
| NFR-002 | Fail closed on an unreadable registry | An unreadable worktree registry refuses the claim with the registry's own typed error code rather than admitting it. | Security | High | Open |
| NFR-003 | Behaviour-identical for every admitted claim | Every claim the create seam admits today and should still admit produces the same `OwnedCreateRoot` fields and the same CLI payload as before this change. | Reliability | High | Open |
| NFR-004 | Production-path coverage | The refusal tests drive the real `agent mission create --owned-checkout` CLI entry point and the real minter, not only a helper. | Testability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No second authority | The coordination leg MUST reuse `_is_coordination_worktree`; the lane leg MUST reuse the canonical slug-free lane-worktree directory grammar (`parse_lane_worktree_dir`). No new predicate, no new registry reader, no new refusal code. | Technical | High | Open |
| C-002 | Leaf behaviour unchanged | `resolve_owned_mission`, `adopt_owned_checkout` and the leaf's `lanes.json`-based lane check are not modified; the `test_owned_checkout_single_authority` allowlist stays empty. | Technical | High | Open |
| C-003 | No topology admission change | The create seam still performs no topology or write-branch check (the Mission does not exist yet); this Mission only adds the Mission-worktree legs. | Technical | High | Open |
| C-004 | CI is the full oracle | Validation is targeted fast suites plus the architectural gates; no full heavy suite locally. | Technical | Medium | Open |

### Key Entities

- **`OwnedCreateRoot`**: the validated create-time owned root, minted only by
  `resolve_owned_create_root`. Its mint does not change shape; only the refusals in front
  of it grow.
- **Worktree registry**: `git worktree list --porcelain`, the disposer of topology
  claims — already read once per claim by the coordination predicate.
- **Mission worktree**: a registered coordination worktree (`-coord`) or a registered
  lane worktree (`<slug>-lane-<id>`), the two shapes the leaf refuses.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `agent mission create --owned-checkout <registered coordination worktree>`
  exits non-zero with `OWNED_CHECKOUT_IS_MISSION_WORKTREE` and leaves the claimed
  checkout's HEAD and worktree byte-identical — [build] · no-op passable: no
- **SC-002**: `agent mission create --owned-checkout <registered lane worktree>` refuses
  the same way, while an ordinary linked owned checkout on the same fixture still
  completes — [build] · no-op passable: no
- **SC-003**: The two modules that documented the residual no longer claim it, and
  `tests/architectural/test_owned_checkout_single_authority.py` stays green with an empty
  allowlist — [ratchet] · no-op passable: no
