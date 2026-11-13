# Tasks: Bound reconciliation windows at the Mission base (#7560)

**Mission**: `mission-base-window-bound-01M78XB4` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `fix/7560-dependency-ref-spine-base`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Fork-shape fixture builder: report-2 shape (upstream pin + overlay base, target lacks it) | WP01 | |
| T002 | Report-1 shape: lane merges a newer upstream commit | WP01 | |
| T003 | Strict-xfail acceptance: plain and declared `--dry-run` and real run, both shapes | WP01 | |
| T004 | Green soundness ratchets on the fork shape (post-base Mission work still refuses) | WP01 | |
| T005 | Non-fork control: verdicts unchanged when the target reaches the base | WP01 | |
| T006 | `MISSION_BASE_SHA_KEY` + `mission_metadata` field | WP02 | [P] |
| T007 | Record the base at topic/protected mint and at coordination-branch create | WP02 | |
| T008 | `consolidation/mission_base.py`: `MissionBase`, `resolve_mission_base` (recorded → derived → unavailable) | WP02 | |
| T009 | `pre_mission_history(window_base, base)` | WP02 | |
| T010 | Unit tests: resolver provenance, fail-closed paths, recording | WP02 | |
| T011 | Claim fields `mission_base`, `pre_mission_shas/blobs/deletions` | WP03 | |
| T012 | Resolve the base and pre-Mission history inside `build_approved_wp_set` | WP03 | |
| T013 | Guard: Mission-spine and recorded-tip walks drop pre-Mission commits | WP03 | |
| T014 | Provenance note line on the run and the forecast | WP03 | |
| T015 | Facade re-exports + claim-level unit tests | WP03 | |
| T016 | Closed-world per-commit filter exempts pre-Mission shas | WP04 | |
| T017 | Squash blob/deletion axes and vacuous-window check exempt pre-Mission content | WP04 | |
| T018 | Patch-id window excludes pre-Mission commits | WP04 | |
| T019 | Flip WP01's strict xfails to passing; verifier unit tests | WP04 | |
| T020 | ADR `2026-09-29-1` amendment | WP05 | [P] |
| T021 | Changelog fragment | WP05 | [P] |
| T022 | CLAUDE.md "Declared dependency ref" paragraph | WP05 | [P] |
| T023 | #7593 gate if PR #7596 has merged, else record blocked | WP05 | |

## Phase 1 — Reproduction

### WP01 — Red acceptance on the fork shapes ([tasks/WP01-red-acceptance-fork-shapes.md](tasks/WP01-red-acceptance-fork-shapes.md))

**Goal**: pin #7560 red through `spec-kitty consolidate`, both reported shapes, plus green soundness ratchets. **Priority**: P1. **Independent test**: the new test module runs; xfails are strict.
**Dependencies**: none.

T001 Fork-shape fixture builder (WP01)
T002 Report-1 shape (WP01)
T003 Strict-xfail acceptance (WP01)
T004 Soundness ratchets (WP01)
T005 Non-fork control (WP01)

**Risks**: harness commits planning and status on the target; the fixture must rewind the target so it lacks the base without breaking the coordination surface.

## Phase 2 — Foundation

### WP02 — Mission base authority ([tasks/WP02-mission-base-authority.md](tasks/WP02-mission-base-authority.md))

**Goal**: record the Mission base at creation and resolve it with provenance. **Priority**: P1.
**Dependencies**: none (parallel with WP01).

T006 Meta key (WP02)
T007 Record at mint/create (WP02)
T008 Resolver module (WP02)
T009 Pre-Mission history (WP02)
T010 Unit tests (WP02)

**Risks**: fail-closed derivation; never pick a base above Mission work.

## Phase 3 — Behaviour change

### WP03 — Guard and claim bounded at the base ([tasks/WP03-guard-and-claim.md](tasks/WP03-guard-and-claim.md))

**Goal**: the #6771 guard ignores pre-Mission history; the claim carries the pre-Mission sets and the base's provenance. **Priority**: P1.
**Dependencies**: WP02.

T011 Claim fields (WP03)
T012 Resolve in claim builder (WP03)
T013 Guard walks (WP03)
T014 Provenance note (WP03)
T015 Facade + unit tests (WP03)

### WP04 — Verifier axes bounded at the base ([tasks/WP04-verifier-axes.md](tasks/WP04-verifier-axes.md))

**Goal**: closed-world, squash and patch-id axes exempt pre-Mission history; WP01 turns green. **Priority**: P1.
**Dependencies**: WP01, WP03.

T016 Closed-world filter (WP04)
T017 Squash axes (WP04)
T018 Patch-id window (WP04)
T019 Flip xfails + tests (WP04)

## Phase 4 — Governance

### WP05 — ADR amendment, changelog, CLAUDE.md ([tasks/WP05-adr-changelog-docs.md](tasks/WP05-adr-changelog-docs.md))

**Goal**: record the verdict change. **Priority**: P2.
**Dependencies**: WP04.

T020 ADR amendment (WP05)
T021 Changelog fragment (WP05)
T022 CLAUDE.md paragraph (WP05)
T023 #7593 gate, conditional on PR #7596 (WP05)

## Deferred fold

FR-009 (#7593) is WP05 T023: conditional on PR #7596 having merged (plan.md, "Deferred fold").
