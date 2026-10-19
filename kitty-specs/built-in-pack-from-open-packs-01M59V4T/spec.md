# Mission Specification: Built-in pack sourced from open-packs

**Mission Branch**: `feat/6451-built-in-from-open-packs`
**Created**: 2026-10-19
**Status**: Draft
**Input**: Issue #6451, "Stop vendoring packs/built-in in core; source it from spec-kitty-open-packs (dev, tests, uv, release)". Operator decisions from 2026-10-19 extend the same approach to `packs/internal/`.

## Purpose

Core holds committed copies of the built-in pack and the internal pack, and the authoritative source of both lives in `spec-kitty-open-packs`. Fixes land in the core copy first and have to be ported back to open-packs (#6395 → #6420, #6436); if they are not, the next re-vendor quietly reverts them. The drift gate has gaps (#6421), and the pin needs its own maintenance (#6364). This mission makes open-packs the only source of both packs. Core keeps one pin file per pack, and every place that needs a pack fetches the pinned open-packs commit. Consumers keep receiving the built-in pack at the same location in installed wheels, with exactly the pinned content.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contributor gets the packs from a pin (Priority: P1)

A contributor clones core and runs the documented setup. The pinned built-in and internal packs appear at `packs/built-in` and `packs/internal`, their digests verified, and the tests read them from those paths.

**Why this priority**: Without this step nothing else in development or testing works once the committed trees are gone.

**Independent Test**: In a fresh clone with no `packs/built-in` or `packs/internal` tree, run the setup command and confirm both trees are present and match their pin digests.

**Acceptance Scenarios**:

1. **Given** a fresh clone with network access, **When** the contributor runs the setup, **Then** both packs are fetched at their pinned commits, their digests are verified, and they are placed at the canonical paths.
2. **Given** the pinned commit was fetched earlier and is in the local cache, **When** the setup runs with no network, **Then** it succeeds from the cache.
3. **Given** no network and no cache, **When** any command needs the built-in pack, **Then** it fails with a message that names the command to run. It never continues silently with a missing or partial pack.
4. **Given** a fetched tree whose content does not match the pin digest, **When** the sync runs, **Then** it refuses and leaves no mismatched tree in place.

### User Story 2 - Release ships the pinned built-in pack (Priority: P1)

A maintainer builds a wheel. The wheel contains `packs/built-in` with exactly the pinned content, and the internal pack is never included.

**Why this priority**: Consumers depend on byte-identical built-in doctrine, and a wrong wheel is a defect they would not notice.

**Independent Test**: Build a wheel and an sdist from a clean checkout. Confirm the wheel's `packs/built-in` matches the pin digest and that neither artifact contains `packs/internal`. Then build a wheel from that sdist with no network.

**Acceptance Scenarios**:

1. **Given** a git checkout, **When** the wheel is built, **Then** the build fetches or reuses the pinned built-in tree, verifies its digest, and includes it as `packs/built-in`.
2. **Given** an sdist, **When** a wheel is built from it with no network, **Then** the build succeeds, because the sdist carries the built-in tree.
3. **Given** any build, **When** the artifacts are inspected, **Then** `packs/internal` is absent from both.

### User Story 3 - Maintainer bumps a pin (Priority: P2)

A maintainer moves core to a newer open-packs commit using one command. The command rewrites the pin with the commit, subtree path and digest.

**Why this priority**: Bumping is the routine path once the vendored tree is gone.

**Independent Test**: Run the bump against a known open-packs commit and confirm the pin's commit and digest change, and that no tracked pack tree is written.

**Acceptance Scenarios**:

1. **Given** an open-packs commit, **When** the maintainer runs the bump, **Then** the pin records that commit, the subtree path and the computed digest, and nothing under `packs/<pack>/` becomes tracked.
2. **Given** open-packs moved the pack from `built-in/` to `packs/built-in/` (open-packs#50), **When** the maintainer bumps with the new subtree path, **Then** the sync and the build use that path with no code change.

### User Story 4 - CI checks the pin, not a tree (Priority: P2)

CI fetches the pinned packs, verifies them, and runs the regeneration and DRG consistency checks against the fetched trees. The drift gate is gone.

**Why this priority**: The gates must stay meaningful once there is no committed tree.

**Independent Test**: Change a pin's digest to a wrong value in a branch and confirm CI goes red at the verification step.

**Acceptance Scenarios**:

1. **Given** a pin with an unresolvable commit or a mismatched digest, **When** CI runs, **Then** it fails at pin verification.
2. **Given** valid pins, **When** CI runs, **Then** the regeneration and DRG `--check` gates evaluate the fetched trees.

### Edge Cases

- An unreachable open-packs remote with no cache gives an actionable failure, never a partial tree.
- A stale fetched tree left over from a previous pin is detected by digest and replaced or refused, never used.
- Lane worktrees each resolve the packs, either through the shared cache or by fetching.
- Windows CI: the sync makes no use of symlinks.
- A `packs/built-in` committed again by mistake is caught by a gate.

## Domain Language

| Canonical term | Meaning | Avoid |
|---|---|---|
| Pin | `packs/<pack>.source.yaml`: repository, commit, subtree, tree digest | lockfile (ambiguous with `uv.lock`) |
| Sync | Fetching the pinned subtree, verifying its digest, placing it at `packs/<pack>` | vendor (retired meaning) |
| Pin bump | Rewriting a pin to a new open-packs commit | re-vendor |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|---|---|---|---|---|
| FR-001 | Core tracks no files under `packs/built-in/` or `packs/internal/`. Both paths are gitignored, and a gate fails if either path is tracked. | Proposed | [build] | no |
| FR-002 | Each pack has a pin `packs/<pack>.source.yaml` with `repository`, `commit`, `subtree` and `tree_digest`. The built-in pin keeps `requires_core`. | Proposed | [build] | no |
| FR-003 | A sync command fetches each pinned subtree, verifies its digest, and places it at `packs/<pack>`. It reuses a local cache keyed by commit when one is available. | Proposed | [build] | no |
| FR-004 | The sync refuses on a digest mismatch, an unresolvable commit, or no network with no cache. Each refusal is an actionable error, and no mismatched tree is left in place. | Proposed | [build] | no |
| FR-005 | When the built-in pack is missing, resolving it raises an error that names the sync command. | Proposed | [build] | no |
| FR-006 | `make dev-setup` and CI run the sync before the tests. | Proposed | [build] | no |
| FR-007 | A wheel built from a git checkout includes the pinned built-in tree at `packs/built-in` (same installed location as today), after verifying its digest. | Proposed | [build] | no |
| FR-008 | The sdist carries the pinned built-in tree, and a wheel builds from the sdist with no network. | Proposed | [build] | no |
| FR-009 | Neither the wheel nor the sdist ever contains `packs/internal`. | Proposed | [ratchet] | no |
| FR-010 | `charter pack vendor` becomes a pin-bump helper that writes `commit`, `subtree` and `tree_digest` to a pin and copies no tree. | Proposed | [build] | no |
| FR-011 | The subtree path comes from the pin, so both the `built-in/` layout and the `packs/built-in/` layout of open-packs#50 work. C-006 is updated. | Proposed | [build] | no |
| FR-012 | CI fails when a pin's commit cannot be resolved or its digest does not match. The regeneration and DRG `--check` gates run against the fetched trees. | Proposed | [build] | no |
| FR-013 | The drift gate (#6421) and the drift-gate part of #6364 are retired, because a committed tree no longer exists to drift. | Proposed | [build] | no |
| FR-014 | ADR `2026-08-16-2` is amended (and `2026-08-16-3` cross-referenced), and the CLAUDE.md pack-tier and template-source text says to edit in open-packs and then bump the pin. | Proposed | [build] | no |
| FR-015 | A clean-install check verifies that the installed wheel's `packs/built-in` matches the pin digest. | Proposed | [build] | no |

### Non-Functional Requirements

| ID | Requirement | Threshold | Status |
|---|---|---|---|
| NFR-001 | A warm-cache sync of both packs is fast | ≤ 5 s | Proposed |
| NFR-002 | A cold sync of both packs over a normal connection is bounded | ≤ 60 s | Proposed |
| NFR-003 | Installed-wheel content identity | 100% digest match with the pin; 0 differing files | Proposed |
| NFR-004 | Cross-platform | Sync passes on Linux and Windows CI with no symlinks | Proposed |

### Constraints

| ID | Constraint | Status |
|---|---|---|
| C-001 | The installed runtime path `packs/built-in` and the `built_in_root()` resolution contract are unchanged for consumers. | Active |
| C-002 | The packaging invariant of ADR `2026-08-16-3` holds: internal is never shipped. | Active |
| C-003 | No runtime or network fetch on consumer installs. Runtime fetch is #3022 and out of scope. | Active |
| C-004 | open-packs is not made an installable package in this mission. | Active |
| C-005 | Open-packs#50 may merge before or after this mission. | Active |
| C-006 | No `[tool.uv.sources]` overrides or committed path dependencies. | Active |

## Success Criteria *(mandatory)*

- SC-001: A fresh clone reaches a green `make test-fast` with only the documented setup step and no manual copying. — [build] · no-op passable: no
- SC-002: Every released wheel's built-in pack matches its pin exactly (0 differing files). — [build] · no-op passable: no
- SC-003: Updating to a new open-packs commit takes one command and one reviewed pin diff, with no tree diff. — [build] · no-op passable: no
- SC-004: No pack fix has to be ported back from core to open-packs, because core has nothing to edit. — [build] · no-op passable: no

## Key Entities

- **Pin**: per-pack source record (repository, commit, subtree, digest; `requires_core` for built-in).
- **Pack cache**: local, commit-keyed store of fetched subtrees, shared across worktrees.
- **Fetched pack tree**: the gitignored `packs/<pack>` directory, valid only when its digest matches the pin.

## Assumptions

- The first pins target the commits already recorded in core (built-in `7f063aec`, subtree `built-in`). The internal pin's first commit is whichever open-packs commit matches core's current `packs/internal` digest. If none matches, one is published first.
- The sync uses `git` (shallow or sparse fetch). That is already a dev and CI prerequisite.
- The regeneration and DRG checks keep their current semantics and only switch to the fetched tree as input.

## Related

#6451 (this), #6421, #6364, #3022, #3504, #6420. Open-packs PR spec-kitty/spec-kitty-open-packs#50.
