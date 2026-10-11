# Mission Specification: Repo-relative retrospective record_path

**Mission Branch**: `fix/retrospective-record-path-relative`
**Created**: 2026-10-12
**Status**: Draft
**Input**: Fix #5868 — the `RetrospectiveCaptured` status event records an absolute `record_path`, leaking a machine-local path (including a username) into the Mission's tracked `status.events.jsonl`. Expected: a repository-relative path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A captured retrospective records a portable path (Priority: P1)

An operator (or the runtime on their behalf) captures a mission retrospective. The
CLI appends a `RetrospectiveCaptured` event to the mission's tracked
`status.events.jsonl`. The `record_path` carried by that event must name the
record *relative to the repository root* (`kitty-specs/<slug>/retrospective.yaml`),
so the committed log is portable and never embeds the operator's home directory
or username.

**Why this priority**: This is the whole mission. The tracked event log is an
authoritative, committed artifact; an absolute path in it leaks machine-local
identity into shared history and must be hand-scrubbed (as it was on #5856).

**Independent Test**: Capture a retrospective in a temporary repository whose root
sits under a path containing a username-like segment, then read the emitted
`RetrospectiveCaptured` event back: its `record_path` equals
`kitty-specs/<slug>/retrospective.yaml`, is not absolute, and contains no segment
of the host root above the repository.

**Acceptance Scenarios**:

1. **Given** a repository at an absolute root, **When** `emit_captured` writes a
   `RetrospectiveCaptured` event for a mission, **Then** the persisted
   `record_path` is the repository-relative POSIX path
   `kitty-specs/<slug>/retrospective.yaml` and is not an absolute path.
2. **Given** a repository root whose absolute path contains a username-like
   segment (e.g. `/home/<user>/...`), **When** the event is emitted, **Then** that
   segment does not appear anywhere in the persisted `record_path`.
3. **Given** the event log is read back by the retrospective gate / reducer,
   **When** the `record_path` is resolved against the repository root, **Then** it
   points at the same on-disk `retrospective.yaml` the record was written to
   (behaviour that depends on the path is preserved).

---

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | The `RetrospectiveCaptured` status event (`src/specify_cli/retrospective/lifecycle_events.py` `emit_captured`) MUST persist `record_path` as a repository-relative path (`kitty-specs/<slug>/retrospective.yaml`), using `/` separators, rather than an absolute filesystem path. | Draft | [build] | no |
| FR-002 | The persisted `record_path` MUST NOT contain any segment of the repository root's absolute path (no leading `/`, no home-directory or username segment), for any repository root location. | Draft | [build] | no |
| FR-003 | A reader that joins the persisted `record_path` onto the repository root MUST resolve to the same `retrospective.yaml` location the record was written to (no behavioural regression for consumers of the field). | Draft | [ratchet] | no |

### Non-Functional Requirements

| ID | Requirement | Status | Threshold |
|----|-------------|--------|-----------|
| NFR-001 | The change MUST NOT alter any other field of the `RetrospectiveCaptured` envelope (byte-identical except `record_path`). | Draft | 0 other fields changed |
| NFR-002 | The fix MUST land with an issue-pinned red-first regression test (`@pytest.mark.regression`, `#5868`) that fails on the absolute-path behaviour through the real `emit_captured` entry point before the fix and passes after. | Draft | 1 regression test, red→green |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | Forward-only: newly-emitted events are repository-relative; no backfill/migration of absolute paths already committed to append-only logs (Decision `specify.scope.migration`, resolved forward-only). | Accepted |
| C-002 | The `record_path` value is part of the retrospective-events contract and remains a `string`; only its absolute→relative form changes. The separate Mission-Status Read-API contract (which omits the property entirely) is a different surface and is untouched. | Accepted |
| C-003 | New/changed code passes `ruff` and `mypy` with zero issues; complexity ≤ 15; no suppressions added. | Accepted |

## Success Criteria *(mandatory)*

- SC-001: For any repository root location, a freshly-emitted `RetrospectiveCaptured` event carries `record_path == "kitty-specs/<slug>/retrospective.yaml"` and no absolute/host-root/username segment. — [build] · no-op passable: no
- SC-002: The red-first regression test for #5868 fails on `main` (absolute path) and passes with the fix. — [ratchet] · no-op passable: no

## Key Entities

- **`RetrospectiveCaptured` event** — the canonical lifecycle event appended to `status.events.jsonl`; the `record_path` field is the subject of this mission.
- **`retrospective.yaml`** — the durable PRIMARY-home record at `kitty-specs/<slug>/retrospective.yaml`, resolved by `resolve_retrospective_home(repo_root, slug)`.

## Assumptions

- `resolve_retrospective_home(repo_root, slug)` always composes the home under `repo_root` (via `_compose_primary_feature_dir` joining `KITTY_SPECS_DIR`), so a repository-relative path is always derivable without a filesystem walk.
- No consumer relies on `record_path` being absolute; readers resolve it against the repository root (verified against the gate/reducer read paths during grounding).

## Out of Scope

- Backfilling or rewriting absolute `record_path` values already committed to existing logs.
- The sibling `feedback_path` on review events and any other event field — only `RetrospectiveCaptured.record_path` is in scope for #5868.
