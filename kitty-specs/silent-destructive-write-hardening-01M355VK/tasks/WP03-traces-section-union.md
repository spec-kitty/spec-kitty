---
work_package_id: WP03
title: Traces merge driver section-level union (#4894)
dependencies: []
requirement_refs:
- FR-007
- FR-008
planning_base_branch: fix/silent-destructive-write-hardening
merge_target_branch: fix/silent-destructive-write-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/silent-destructive-write-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/silent-destructive-write-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-silent-destructive-write-hardening-01M355VK
base_commit: 286b75cccb0cbfeb6cc7e65550337527c27bba81
created_at: '2026-09-22T18:44:01.567522+00:00'
subtasks:
- T012
- T013
- T014
- T015
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/merge_driver.py
create_intent:
- tests/merge/test_traces_driver_section_union_4894.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/merge_driver.py
- tests/merge/test_merge_driver_wrappers_2709.py
- tests/merge/test_traces_driver_section_union_4894.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile via `/ad-hoc-profile-load`
(profile: `python-pedro`, role: `implementer`). Adopt its identity, boundaries, and discipline
for the whole work package.

## Objective

Fix #4894: the `spec-kitty-traces` custom merge driver (bound to `kitty-specs/**/traces/*.md` on
EVERY ordinary `git merge`/`rebase`/`cherry-pick`) silently deletes repeated non-empty lines from
authored markdown. `union_trace_texts` walks ours then theirs with one shared `seen` set and drops
every non-empty line already emitted — including markdown fences, headings, table separators, and
prose that legitimately recurs across sections — then writes the result and exits 0, recording a
clean merge. A file with four fenced blocks emerges with one fence line.

## Structural root cause (wrong granularity + base-blindness)

- `merge_driver.py:304-325 union_trace_texts`: line-level GLOBAL dedup is only sound for documents
  whose non-empty lines are globally unique — markdown is not.
- `merge_driver.py:328-338 merge_driver_traces`: ignores `%O` (2-way), always writes `%A`, returns 0.

**Do NOT make this fail-closed like the acceptance/issue-matrix drivers** (`_merge_field:411-466`
raises for a diverged verdict field). Those are keyed row artifacts with verdict authority; traces are
keyless append-union prose, so failing closed on every repeat would abort nearly every real merge.
The right fix is section/block-level union (+ 3-way base-awareness).

**Do NOT touch `_union_acceptance_history` (`merge_driver.py:237-245`)** — its `seen` set dedups whole
history ENTRIES by canonical-JSON equality, which is correct record-granularity dedup, not the bug.

## Guidance per subtask

### T012 — Red-first regression test
Add `tests/merge/test_traces_driver_section_union_4894.py` with a `@pytest.mark.regression` test
pinned to #4894: two branches each append a `## section` containing a ```` ``` ```` fence and repeated
prose to the same `traces/*.md` from a common base, then `git merge` (driver active). Assert the merged
file contains both sections with all fence lines and repeated prose intact (or a git conflict). RED
before the fix (witness fences collapse to 1). Follow the QA repro script in the issue.

### T013 — Section/block-level union in `union_trace_texts`
Replace line-level global dedup with union at the `<!-- section:... -->` delimiter granularity the
docstring already names: collapse only whole duplicate sections/blocks; preserve repeated lines WITHIN
distinct sections. Guarantee INV-3: every non-empty line present in either input is present in the
output (or the driver conflicts). Keep append order stable (ours' sections, then theirs' new sections).

### T014 — 3-way base-awareness in `merge_driver_traces`
Consume `%O` (base) so the driver can distinguish "a line/section both sides inherited from base" from
"a genuinely new one," matching the sibling matrix drivers' 3-way shape. If a genuine structural
conflict cannot be unioned safely, fall back to a non-zero git conflict rather than a lossy exit-0.

### T015 — Unit tests + sibling-unchanged
Focused unit tests over `union_trace_texts` (and the 3-way path): repeated line within one distinct
section preserved; two identical whole sections deduped to one; INV-3 property over representative
inputs. Add an assertion (or leave existing behavior verified) that `_union_acceptance_history` is
unchanged. Update `tests/merge/test_merge_driver_wrappers_2709.py` only if an existing case encodes
the old lossy line-dedup behavior (record a one-line rationale).

## Definition of Done

- T012 regression RED before, GREEN after.
- INV-3 holds; section-granularity union; not fail-closed on ordinary repeats.
- `_union_acceptance_history` behavior unchanged.
- Blast radius green: `tests/merge/`, `tests/architectural/test_merge_reconciliation_class_guard.py`,
  `tests/upgrade/migrations/test_m_3_2_6_meta_traces_merge_drivers.py`. `ruff`, `ruff format --check`,
  `mypy` clean. Touched functions ≤15 complexity.

## Reviewer guidance

Confirm dedup is section-granularity (not line); confirm repeated lines within distinct sections
survive; confirm no non-empty input line is dropped without a conflict; confirm the acceptance-history
dedup is untouched; confirm the regression test fails on merge-base.
