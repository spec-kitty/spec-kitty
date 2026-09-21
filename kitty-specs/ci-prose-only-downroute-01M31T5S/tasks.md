# Tasks: CI down-route of prose-only .py diffs

**Mission**: ci-prose-only-downroute-01M31T5S | **Branch**: `feat/ci-prose-only-downroute`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contract**: [contracts/prose-only-classifier.md](./contracts/prose-only-classifier.md)

Three work packages after the post-tasks adversarial squad (research R10). WP01 is
the pure classifier; WP02 (ci-modules + ci-router wiring) and WP03 (ci-aggregate
coverage honesty) both depend on WP01 and touch disjoint files, so they can run as
parallel lanes. MVP is all three together — the down-route is only safe with the
fail-closed classifier, both routing surfaces wired, AND the coverage gate kept
honest (squad F1). Squad findings and dispositions: research.md R10.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first `tests/ci/test_prose_only.py`: docstring/comment True cases, code/mixed False cases, `# type:`/`# noqa` False, doctest-docstring False, parse-error/no-base False | WP01 | |
| T002 | Implement `scripts/ci/prose_only.py` `is_prose_only(base, head)` — AST dump compare + docstring strip, `type_comments=True` | WP01 | |
| T003 | Add the `# type:`/`# noqa`/`# pragma` tokenize guard (R5) and the doctest-docstring guard (R4) | WP01 | |
| T004 | Add aggregate helpers `reduced_paths()` and `pr_is_prose_only()` + their tests (all-or-nothing, no unmapped-src) | WP01 | |
| T005 | Prove ruff/format/mypy clean and the classifier is IO-free (no yaml/fnmatch) | WP01 | |
| T006 | Wire `ci-modules.yml` changed-files step to reduce prose-only `.py` before `select_modules` (git show base/head; git-show failure keeps the path) | WP02 | |
| T007 | Add `prose_only` output via a SEPARATE `prose-scan` job in `ci-router.yml` (F2 — avoids the phantom-group regex); path classification via `gate_selection` | WP02 | |
| T008 | Add `prose-scan` to `needs:` and gate arch battery + code shards off (`&& prose_only != 'true'`); force docs lane on; add to `router-gate` needs | WP02 | |
| T008b | Grep suite for code-shard `__doc__`/`getdoc` asserters; record residual risk (HIGH-2) | WP02 | |
| T009 | Extend `tests/ci/test_ci_module_wiring.py`: reduced-list drops prose-only, mixed not reduced; hand-pinned golden lane-set (SC-001, F4) | WP02 | |
| T010 | Confirm path-purity + coherence guards stay green (`test_gate_selection_authority`, `test_local_gate_parity`, `test_ci_integrity_oracle_nonvacuous`) — SC-004 | WP02 | |
| T011 | Red-first `tests/ci/test_aggregate_source.py`: prose-only critical `.py` absent from `critical.diff.patch`, real code retained | WP03 | [P] |
| T012 | Exclude proven-prose-only `.py` from `critical.diff.patch` in `aggregate_source.py` (reuse WP01 classifier; fail-closed keeps the file) | WP03 | [P] |
| T013 | Verify honest path: mixed PR still scores real code; ci-aggregate tests green (FR-009) | WP03 | [P] |

## Work Packages

### WP01 — Pure prose-only classifier (foundation)

**Prompt**: [tasks/WP01-pure-prose-only-classifier.md](./tasks/WP01-pure-prose-only-classifier.md)
**Goal**: a pure, fail-closed `is_prose_only(base, head)` predicate + aggregate
helpers, fully unit-tested, with no filesystem/git/network IO.
**Priority**: P1 (MVP foundation). **Depends on**: none.
**Requirements**: FR-001, FR-002, FR-006 (NFR-001/002/003).
**Independent test**: `pytest tests/ci/test_prose_only.py` — in-memory strings only.
**Included subtasks**: T001, T002, T003, T004, T005.
**Est. prompt size**: ~280 lines.

### WP02 — Routing wiring: ci-modules + ci-router (depends on WP01)

**Prompt**: [tasks/WP02-two-surface-workflow-wiring.md](./tasks/WP02-two-surface-workflow-wiring.md)
**Goal**: wire the classifier into the two routing surfaces so a proven prose-only PR
skips the module matrix + arch battery + code shards and runs the docs lane; every
other PR routes as today. `prose_only` comes from a SEPARATE `prose-scan` job (F2).
**Priority**: P1. **Depends on**: WP01.
**Requirements**: FR-003, FR-004, FR-005, FR-007, FR-008 (SC-001, SC-002, SC-004).
**Independent test**: `pytest tests/ci/test_ci_module_wiring.py` + the hand-pinned
golden lane-set; path-purity/coherence arch guards stay green.
**Included subtasks**: T006, T007, T008, T008b, T009, T010.
**Est. prompt size**: ~380 lines.

### WP03 — Coverage-gate honesty: ci-aggregate (depends on WP01)

**Prompt**: [tasks/WP03-coverage-gate-honesty.md](./tasks/WP03-coverage-gate-honesty.md)
**Goal**: exclude proven-prose-only `.py` from the `critical.diff.patch` that
diff-cover scores, so skipping a critical-path module's shard cannot false-red the
coverage gate on a docstring edit (squad F1).
**Priority**: P1. **Depends on**: WP01. Parallel with WP02 (disjoint files).
**Requirements**: FR-009.
**Independent test**: `pytest tests/ci/test_aggregate_source.py`.
**Included subtasks**: T011, T012, T013.
**Est. prompt size**: ~200 lines.

## Dependencies

- WP02 **Depends on** WP01.
- WP03 **Depends on** WP01. WP02 and WP03 are independent (parallel lanes).
