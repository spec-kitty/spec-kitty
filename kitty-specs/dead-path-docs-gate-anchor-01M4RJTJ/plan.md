# Implementation Plan: Anchor Gate D's dead-path docs regex

**Branch**: `issue-6096-dead-path-gate-anchor` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/dead-path-docs-gate-anchor-01M4RJTJ/spec.md`

## Summary

Gate D (`tests/architectural/test_dead_builtin_doc_paths.py`) feeds an
unanchored regex to `git grep -nE`, so any longer path whose tail is
`…/src/charter/offering/<kind>/built-in` (or `…/*.graph.yaml`) is wrongly flagged
as a retired **top-level** reference. Fix: prepend an explicit left-boundary
alternation `(^|[^A-Za-z0-9_./-])` to `_MOVED_BUILTIN_DOC_RE` so a match is
admitted only at start-of-line or after a non-path, non-word character. Drive it
red-first with a self-mutation-proven regression test that exercises the real
`git grep` + regex against a synthetic `docs/` tree in both directions. No
product/runtime impact; precision-only.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pytest, `git grep` (ERE), stdlib `subprocess`
**Storage**: N/A
**Testing**: pytest; the gate shells out to `git grep`, so the regression test
builds a throwaway git repo under `tmp_path` and runs the real helper against it
(no mocking of the match engine).
**Target Platform**: Linux / macOS / Windows (same as the gate)
**Project Type**: single (CLI/library + tests)
**Performance Goals**: N/A (one `git grep` over `docs/`, unchanged)
**Constraints**: tighten the LEFT BOUNDARY only; do not loosen the guard's reach
or `_GUARD_DOC_EXCLUSIONS`; no suppressions; no new ratchet/allowlist; complexity ≤ 15.
**Scale/Scope**: one source file (`tests/architectural/test_dead_builtin_doc_paths.py`); two commits (red test, green fix).

## Charter Check

*GATE: Must pass before implementation. Re-check after design.*

- **Standing Order 4 (bug-fix / test-remediation):** red-first through the
  pre-existing entry point (the gate's own `git grep` + `_MOVED_BUILTIN_DOC_RE`);
  live evidence; never retry-to-green. → PASS by design (red test committed first).
- **Standing Order 5 (architectural-gate discipline):** non-vacuous,
  self-mutation-proven; do NOT loosen the guard; no new ratchet; empty-allowlist
  invariant preserved (Gate D has no allowlist and gains none). → PASS by design.
- **ATDD-First (C-011):** failing-first test committed as a separate commit
  before the fix; reviewer verifies RED on base, GREEN on final. → PASS by design.
- **Change-scope reconciler (DIRECTIVE_024/025 + smallest-viable-diff):** scope
  stays on Gate D; siblings audited (diagnosis note) and NOT widened. → PASS.
- **Terminology Canon:** no `feature`/Mission drift introduced. → PASS (no user-facing strings change).

No violations → Complexity Tracking omitted.

## Project Structure

### Documentation (this mission)

```
kitty-specs/dead-path-docs-gate-anchor-01M4RJTJ/
├── spec.md                      # confirmed intent + FR/NFR/C/SC
├── plan.md                      # this file
├── checklists/requirements.md   # spec quality checklist
├── research/diagnosis-6096.md   # diagnosis + red-first evidence + sibling audit
├── traces/{approach,design-decisions,tooling-friction}.md
└── tasks.md + tasks/            # /spec-kitty.tasks output
```

### Source Code (repository root)

```
tests/architectural/
└── test_dead_builtin_doc_paths.py   # Gate D: _MOVED_BUILTIN_DOC_RE (edited) + new regression test(s)
```

The gate currently inlines the `git grep` call in the test body. The fix adds
the left-boundary anchor to `_MOVED_BUILTIN_DOC_RE` and a small reusable helper
that runs the grep against a given `cwd`/pathspec, so the live gate and the new
regression test share one mechanism (no divergence between what runs in CI and
what the test exercises).

**Structure Decision**: Single-file change under `tests/architectural/`. No
`src/` change (the defect is in the gate itself). No `data-model.md` /
`contracts/` — there is no data model or external contract; `research/` carries
the design evidence.

## Implementation Concern Map

### IC-01 — Left-boundary anchor + self-mutation-proven regression

- **Purpose**: Tighten `_MOVED_BUILTIN_DOC_RE`'s left boundary so a nested/tail occurrence is not matched, while a genuine top-level reference still is; prove it red-first and both-ways.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-001, C-002, C-003; SC-001, SC-002, SC-003.
- **Affected surfaces**: `tests/architectural/test_dead_builtin_doc_paths.py` (the `_MOVED_BUILTIN_DOC_RE` constant, a shared grep helper, the live gate call, and a new regression test building a `tmp_path` git repo).
- **Sequencing/depends-on**: none (single concern).
- **Risks**: ERE differences across platforms (the leading alternation `(^|[^A-Za-z0-9_./-])` is plain POSIX ERE, no look-behind, so `git grep -E` supports it everywhere); the regression test must `git add` fixtures so `git grep` (working-tree tracked files) sees them.
