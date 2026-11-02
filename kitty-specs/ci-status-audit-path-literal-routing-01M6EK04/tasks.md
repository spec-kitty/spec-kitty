# Tasks: Route the path-literal audit on a `status/**` diff

**Mission**: `ci-status-audit-path-literal-routing-01M6EK04` · **Branch**: `issue-6879-ci-status-audit-path-literal-routing`
**Input**: [plan.md](./plan.md) (3 implementation concerns), [spec.md](./spec.md) (6 FRs, 3 NFRs, 4 constraints, 3 success criteria).

> Reference rows below are **not** checkboxes. Subtask completion is event-sourced —
> record with `spec-kitty agent tasks mark-status T0xx --status done`. The reduced
> event-log snapshot is the sole authority (#2816).

## Sequencing overview

One work package. The mission is deliberately small: two routing authorities, one job, one
live-routing guard test, one additive ledger row. There is no `src/` change, so no lane has
to be serialized behind another.

Order inside WP01 is red-first: T001 (the guard test, failing) precedes T002-T004 (the
wiring it asserts), T005 is the verification sweep.

The changelog fragment (`docs/changelog/unreleased/<pr>.internal.md`) is **not** a WP
subtask: it needs the PR number, so it is written in the mission wrap-up after the PR
exists.

## Requirement → Work-Package coverage

| Requirement | WP |
| --- | --- |
| FR-001 | WP01 (T002, T003) |
| FR-002 | WP01 (T003) |
| FR-003 | WP01 (T001, T002) |
| FR-004 | WP01 (T002, T003, T004) |
| FR-005 | WP01 (T001, T003) |
| FR-006 | WP01 (T001) |
| NFR-001 | WP01 (T003, T005) |
| NFR-002 | WP01 (T003) |
| NFR-003 | WP01 (T005) |
| SC-001 | WP01 (T001) |
| SC-002 | WP01 (T001, T005) |
| SC-003 | WP01 (T005) |

## Work Packages

## WP01 — Route the path-literal audit on a status diff

Add the `path_literal_audit` router group and the `tests-path-literal-audit` job that runs
`tests/audit/test_no_legacy_path_literals.py` on a `src/specify_cli/status/**` diff, with the
live-routing regression guard written first. Subtasks T001-T006; no dependencies; implementer
profile `python-pedro`. Details: [tasks/WP01-path-literal-audit-routing.md](./tasks/WP01-path-literal-audit-routing.md).

| WP | Title | Subtasks | Depends on | Profile | Model |
| --- | --- | --- | --- | --- | --- |
| WP01 | Route the path-literal audit on a status diff | T001-T006 | — | python-pedro (implementer) | cheaper tier (implementation) |

## Subtask Index

| ID | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | Red-first live-routing guard `tests/ci/test_path_literal_audit_routing.py` (positive + negative controls, job shape, prose-only golden) | WP01 | |
| T002 | Declare `path_literal_audit` as a NON-src group in the scrub `non_src_router_groups` and transcribe it verbatim into the router filter block and `changes.outputs` (deliberately not in the `unmatched` union or the heavy-battery `if:`) | WP01 | |
| T003 | Add the `tests-path-literal-audit` job (one pytest file, no marker filter) and its `router-gate` needs row | WP01 | |
| T004 | Add the additive `AUTHORIZED_PER_CHANGE_SUITE_JOBS` ledger row with rationale | WP01 | |
| T005 | Verification sweep: `tests/ci`, the six router/architectural guards, the guard file itself, a planted-literal red, ruff | WP01 | |
