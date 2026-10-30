# Mission Specification: Changelog WP acceptance reads the canonical lane

**Mission Branch**: `issue-6612-changelog-wp-lane-reducer`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6612 — `release/changelog.py` reads a work package's lane as the last `to_lane` in file order, bypassing the reducer.

**Issue**: spec-kitty/spec-kitty#6612 (P2, reliability/release). Evidence: gap G-13 in `docs/architecture/event-ledger-writers-and-readers.md`.

## Mission Boundary

In scope: the WP-acceptance read in `src/specify_cli/release/changelog.py` (`_wp_lane_from_event_log` / `_is_accepted_wp`), routed through the canonical lane reader over the resolved status surface; red-first regression tests for the out-of-order-log and coordination-topology cases; the corrupt-log loud failure; a changelog entry; and updating the G-13 gap row in the event-ledger doc.

Out of scope: the preflight actor lookup ordering (the other G-13 item — it is documented as deliberate and stays); the retrospective readers' own Lamport folds; the Java read API; any change to the reducer, the placement seam, or the status store.

## Terminology

- **Lane**: the canonical work-package lifecycle state (`specify_cli.status.models.Lane`). "Accepted" for the changelog means lane `approved` or `done`.
- **Reducer**: the single wall-clock fold `spec_kitty_events.diary.reduce_parsed` reached by `status/reducer.py::reduce`; orders events by `at`, then `event_id`, and applies from-lane continuity and the approved-departure lift.
- **Resolved status surface**: the directory holding the authoritative `status.events.jsonl` for a mission — the coordination worktree's mission dir under a coordination topology, the primary mission dir otherwise (the placement seam's `STATUS_STATE` read).
- **File order**: the physical order of lines in `status.events.jsonl`. Not lane order after a union merge or an out-of-order append.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The changelog classifies WP acceptance by the reduced lane, not file order (Priority: P1)

A maintainer runs `spec-kitty agent release prep`. A mission's `status.events.jsonl` has lines whose physical order disagrees with reducer order (union merge via the `.gitattributes` merge driver, or a clock-skewed append). The changelog must list a WP as accepted exactly when the **reducer** puts it in `approved`/`done` — today the last `to_lane` in file order wins and can mis-classify.

**Why this priority**: This is the defect's core wrong answer; everything else in the mission protects or complements it.

**Independent Test**: Build a mission fixture whose log is written `[approval (later at), departure (earlier at)]`; `build_changelog_block` must include the WP (reducer lane `approved`) even though the last `to_lane` in file order is not accepted.

**Acceptance Scenarios**:

1. **Given** a mission whose log, in file order, ends on a non-accepted `to_lane` but whose latest event by `at` transitions to `approved`, **When** `build_changelog_block` runs, **Then** the WP appears in the changelog block.
2. **Given** a mission whose log, in file order, ends on an accepted `to_lane` but whose latest event by `at` leaves it non-accepted, **When** `build_changelog_block` runs, **Then** the WP does not appear.

### User Story 2 - The changelog reads the resolved status surface, including the coordination branch (Priority: P1)

A coordination-topology mission's authoritative event log lives in its coordination worktree; the primary mission dir may hold a stale copy. The changelog must read the **resolved** surface — today it reads `mission_dir / "status.events.jsonl"` directly and can act on the stale primary copy.

**Why this priority**: This is the split-brain class (#1735) the rest of the CLI already closed; the changelog is the last raw reader of the primary path.

**Independent Test**: In a git fixture with a materialized coordination worktree carrying `WP01 → approved` and a stale primary copy carrying `WP01 → in_review`, `build_changelog_block` must include the WP.

**Acceptance Scenarios**:

1. **Given** a coordination-topology mission whose coordination surface reduces WP01 to `approved` while the primary copy shows `in_review`, **When** `build_changelog_block` runs, **Then** WP01 is listed for that mission.
2. **Given** a legacy mission with no `meta.json`-resolvable placement and a local `status.events.jsonl`, **When** `build_changelog_block` runs, **Then** the local log is still read through the reducer (legacy behavior preserved, no regression).

### User Story 3 - A corrupt status log fails loudly (Priority: P2)

Today `_wp_lane_from_event_log` silently skips lines that fail `json.loads`. Every other reader of the log fails loudly (`StoreError` with the 1-based line number). The changelog must do the same.

**Why this priority**: A silently-skipped corrupt line is a silent misclassification — the same wrong answer as story 1, one cause over.

**Independent Test**: A mission whose log contains a corrupt line makes `build_changelog_block` raise `StoreError`; on current main it silently skips the line.

**Acceptance Scenarios**:

1. **Given** a mission whose `status.events.jsonl` contains a line that is not valid JSON, **When** `build_changelog_block` runs, **Then** it raises the canonical store error naming the line, instead of skipping it.

### Edge Cases

- A mission with **no event log at all** (pre-3.x feature): the legacy YAML-frontmatter `status` fallback must keep working (accepted set `done`/`accepted`/`merged`).
- A mission with an event log but **no events for the WP**: frontmatter fallback, as today (`get_wp_lane` returns `Lane.UNINITIALIZED`).
- A coordination-topology mission whose coordination worktree is **not materialized** (fresh clone): there is no readable authoritative surface; the WP falls back to the legacy frontmatter read — never to the stale primary copy.
- A mission whose declared coordination branch was **deleted from git**: the canonical `CoordinationBranchDeleted` failure propagates (the #1848 data-loss guard every reader shares).
- The repo has **no `kitty-specs/` directory** or no tags: unchanged behavior (empty block / all missions).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Reducer-ordered lane read | As a release maintainer, I want WP acceptance in the changelog decided by the reduced lane so that log line order cannot mis-classify a WP. | High | Open | [build] | no |
| FR-002 | Resolved status surface | As a release maintainer, I want the changelog to read the mission's resolved status surface (coordination branch under coordination topology) so that a stale primary copy cannot mis-classify a WP. | High | Open | [build] | no |
| FR-003 | Corrupt log fails loudly | As a release maintainer, I want a corrupt `status.events.jsonl` to fail the changelog build loudly so that damage is visible instead of silently misclassifying WPs. | Medium | Open | [build] | no |
| FR-004 | Legacy fallback preserved | As a release maintainer with pre-3.x missions, I want the frontmatter `status` fallback kept for missions with no event log so that old features still appear in the changelog. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One lane authority | The changelog performs zero raw parses of `status.events.jsonl`; every lane value comes from `status.lane_reader.get_wp_lane` (verified by grep/AST in review, and by the existing event-log readers gate where applicable). | Architectural | High | Open |
| NFR-002 | No new network or write IO | `build_changelog_block` stays read-only and network-free (FR-014 of the release-prep contract); the placement seam is used read-side only. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Smallest viable diff | The fix stays inside `src/specify_cli/release/` plus tests, the changelog entry, and the G-13 doc row; no changes to the reducer, the placement seam, or the status store. | Technical | High | Open |
| C-002 | Canonical surfaces only | No new status-surface derivation: placement/lane reads go through the existing seams (`placement_seam` / `lane_reader`), never a hand-composed path (read-side bypass gate). | Technical | High | Open |

### Key Entities

- **Work package (WP)**: a `tasks/WP*.md` file with a `work_package_id`; accepted for the changelog when its reduced lane is `approved` or `done`.
- **Status event**: one JSONL row of `status.events.jsonl` (`event_id`, `at`, `from_lane`, `to_lane`, …).
- **Status surface**: the directory holding the authoritative `status.events.jsonl` (primary mission dir, or the coordination worktree's mission dir under coordination topology).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A mission whose log file order disagrees with reducer order is classified by the reducer's lane in `build_changelog_block` output — [build] · no-op passable: no
- **SC-002**: A coordination-topology mission is classified from its coordination-branch log, not the stale primary copy — [build] · no-op passable: no
- **SC-003**: A corrupt `status.events.jsonl` line makes `build_changelog_block` raise the canonical store error — [build] · no-op passable: no
- **SC-004**: All pre-existing `tests/release/` behavior for frontmatter-only missions still passes unchanged — [ratchet] · no-op passable: no
