# Tasks: Status lock directory name single-source

**Mission**: `status-lock-dir-name-ssot-01M68JA7` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6516-status-lock-dir-name-ssot`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: drain both audit-gate exemptions and capture the red on `status/locking.py` (and `review/lock.py`) | WP01 | |
| T002 | Name the runtime-state directory once in `specify_cli/paths/windows_paths.py`; export it from `specify_cli.paths`; use it in `get_runtime_root()` | WP01 | |
| T003 | Re-point `status/locking.py` at the owner constant, dropping the misleading `..._HOME` name — the fallback directory itself does not move | WP01 | |
| T004 | Re-point `review/lock.py`'s `LOCK_DIR` at the owner constant, keeping the public name | WP01 | |
| T005 | Add the allowlist-bypassed scan pin so the `status/locking.py` exemption cannot be re-added silently | WP01 | |
| T006 | Green: audit gate, status lock fallback + reentrancy suites, review-lock consumers, runtime-root resolution, ruff/mypy | WP01 | |
| T007 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry, bold impact-first lead with `(#6516)` | WP02 | [P] |
| T008 | File the per-PR audit-routing follow-up issue (issue #6516's second half) and record its number | WP02 | [P] |
| T009 | Verify `check_docs_freshness --ci` (errors=0) and the terminology gate; record commands for the PR body | WP02 | [P] |

## Phase 1 — Story 1/2/3 (P1/P2)

### WP01 — Name the runtime-state directory once and put the module back under the guard ([tasks/WP01-runtime-state-directory-name-owner.md](tasks/WP01-runtime-state-directory-name-owner.md))

- **Goal**: the runtime-state directory name lives in exactly one module — the path authority the FR-010 guard already sanctions — and both repository-local consumers take it from there, so neither hand-rolls the literal and neither needs an audit-gate exemption.
- **Priority**: P1 (MVP)
- **Independent test**: removing both allowlist entries makes `tests/audit/test_no_legacy_path_literals.py` fail naming `src/specify_cli/status/locking.py:65` and `src/specify_cli/review/lock.py:36`; after the change it passes, `tests/status/test_lock_fallback_never_mints_marker.py` passes unmodified, and `specify_cli.paths` exports the name that both constants equal.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, C-001, C-002, SC-001, SC-002, SC-003, SC-004, SC-005
- **Included subtasks**:

T001 Red-first drain and red capture (WP01)
T002 Owner constant in the path authority (WP01)
T003 Status-lock consumer (WP01)
T004 Review-lock consumer (WP01)
T005 Allowlist-bypassed pin (WP01)
T006 Green + blast radius (WP01)

- **Sketch**: remove the two allowlist entries and run the gate to see the red → add the constant and use it in `get_runtime_root()` → re-point both consumers → add the bypass-scan assertion → re-run the gate, the lock suites and the runtime-root suite.
- **Dependencies**: none
- **Risks**: `LOCK_DIR` is imported by `cli/commands/agent/workflow.py` and four test modules (keep the name); `windows_paths.py` must stay an import leaf (NFR-001); the fallback directory and the global home must not move (C-001).

## Phase 2 — Documentation and follow-up (P2)

### WP02 — Record the change and hand the routing half over ([tasks/WP02-changelog-and-routing-followup.md](tasks/WP02-changelog-and-routing-followup.md))

- **Goal**: the `[Unreleased]` changelog states what changed for a maintainer, and the issue's second half (a `src/specify_cli/status/**` diff does not route `tests/audit/**` per PR) exists as a filed follow-up for the maintainer to decide.
- **Priority**: P2
- **Independent test**: `CHANGELOG.md` has one `[Unreleased]` entry citing `(#6516)` under 1,200 characters; a new issue exists that names the router path group and module registry as the fix surface and cites #6516; `check_docs_freshness --ci` reports errors=0.
- **Requirements**: C-003, SC-004
- **Included subtasks**:

T007 Changelog entry (WP02)
T008 Routing follow-up issue (WP02)
T009 Docs freshness + terminology verification (WP02)

- **Dependencies**: WP01 (records the shipped behaviour)
- **Risks**: the changelog must not claim the routing gap is fixed; the docs freshness check reads a shared, concurrently rebuilt cache, so verify rather than regenerate the whole reference.

## Parallelization

WP02 depends on WP01. Inside WP01 the four source edits are serial (T002 before T003/T004), but T005 can be written in parallel with T003/T004 once the red from T001 is captured. Inside WP02, T007–T009 touch separate surfaces (changelog, tracker, verification) and land as one commit.

## Dependency graph

```
WP01 (code + gate)
  └── WP02 (changelog + follow-up)
```
