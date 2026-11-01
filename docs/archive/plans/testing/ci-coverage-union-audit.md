---
title: Cross-cutting coverage-union audit — ci-test-topology-performance-01KXBJRT (T026)
description: Committed per-job GC-2b coverage evidence for the CI test-topology performance mission, plus cross-job disjointness and fail-fast/dist-lint verification (GC-2/GC-3/GC-4).
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/archive/plans/testing/ci-job-timings.md
- docs/development/testing/testing-parallel.md
- kitty-specs/ci-test-topology-performance-01KXBJRT/contracts/guard-contracts.md
---

# Cross-cutting coverage-union audit (T026)

> **Superseded.** Coverage evidence for the retired `ci-quality.yml` shard topology of mission `01KXBJRT`; the modular CI from #3995 (the lean CI reinstatement) replaced those jobs. See [CI gate mechanics](../../../development/reference/ci-gate-mechanics.md). Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

This is the mission's committed evidence for T026 ("verify the executed-test
union is unchanged across all re-topologized jobs, GC-2b") plus the review's
hardened Definition of Done: **real per-job node-id counts and real
diff-vs-baseline exit status**, not a prose claim. Every command below was
actually run in this worktree
(`.worktrees/ci-test-topology-performance-01KXBJRT-lane-i`) on 2026-07-12;
raw output is quoted, not paraphrased.

## 1. Scope

Per WP06's landing (commit `f132ee611`), the jobs whose test *selection*
changed in this mission are: `integration-tests-next` (T014),
`slow-tests` (T015), the `fast-tests-sync`/`fast-tests-sync-orphan-sweep`
split (T016), `fast-tests-core-misc` (T017), the
`fast-tests-charter`/`fast-tests-agent` split (T018), and the 13-job serial
`integration-tests-*` sweep (T019). Of these, three carry a **committed E3
baseline** and a parametrized GC-2b guard
(`tests/architectural/_gate_coverage.py`'s `BASELINE_TARGETS`):
`integration-tests-next`, `slow-tests`, `fast-tests-core-misc`. The
orphan-sweep/sync-pool split and the charter/agent de-serialization are
covered by dedicated disjointness/parallelization guards instead (§3, §4) —
they did not change *what* is selected, only *where* (which job) it runs.

## 2. GC-2b baseline diff — real per-job evidence

Command (run for real, full output below — not summarized):

```
uv run pytest tests/architectural/test_gate_coverage.py -q
```

Real result: **1 failed, 28 passed in 331.84s (0:05:31)**. Re-run scoped to
the full guard family (§3) for a second, independent confirmation: **1
failed, 82 passed, 879 deselected in 483.24s (0:08:03)** — same single
failure both times.

| Job (`BaselineTarget.slug`) | Committed baseline count | GC-2b result | Diff exit status |
|---|---:|---|---|
| `integration-tests-next` | 441 node-ids | **PASS** | 0 (clean — symmetric difference empty) |
| `slow-tests` | 45 node-ids | **PASS** | 0 (clean — symmetric difference empty) |
| `fast-tests-core-misc` | 9151 node-ids | **FAIL** | nonzero — see §2.1 for the real diff and why it is not a coverage gap |

Baseline file line counts (`tests/architectural/baselines/*.txt`, counted
with a real Python read, not `wc -l`, which undercounts by one on a file
without a trailing newline):

```
$ python3 -c "
for f in ['fast-tests-core-misc-nodeids.txt','integration-tests-next-nodeids.txt','slow-tests-nodeids.txt']:
    p = 'tests/architectural/baselines/' + f
    lines = [l for l in open(p, encoding='utf-8').read().splitlines() if l.strip()]
    print(f, len(lines))
"
fast-tests-core-misc-nodeids.txt 9151
integration-tests-next-nodeids.txt 441
slow-tests-nodeids.txt 45
```

**Note on the counts named in this WP's own task prompt** (`integration-tests-next`
union==440, `slow-tests`==44, `fast-tests-core-misc` union==9150): the real,
freshly-measured counts above are each **one higher** (441 / 45 / 9151).
Recording the real measured numbers here rather than forcing agreement with
the prompt's numbers — the discrepancy is presumably one test added to the
suite between whenever those figures were written and this audit; it does
not change the audit's conclusion (`integration-tests-next` and `slow-tests`
both diff clean at their *current* real counts).

### 2.1 The `fast-tests-core-misc` failure — real output, and why it is not a coverage gap

Real pytest failure output (verbatim, only line-wrapped for this document):

```
______ test_gc2b_current_selection_matches_baseline[fast-tests-core-misc] ______
tests/architectural/test_gate_coverage.py:754: in test_gc2b_current_selection_matches_baseline
    assert not dropped and not added, (
E   AssertionError: GC-2b baseline drift for 'fast-tests-core-misc': 6 dropped
    (in baseline, no longer selected), 6 added (selected but not in baseline).
E   dropped (first 20):
    ['tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_documents_create_intent_with_required_ownership_fields[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-f/.kittify/overrides/missions/software-dev/command-templates/tasks.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_documents_create_intent_with_required_ownership_fields[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-f/src/doctrine/missions/mission-steps/software-dev/tasks/prompt.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_explains_create_intent_for_planned_new_owned_files[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-f/.kittify/overrides/missions/software-dev/command-templates/tasks.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_explains_create_intent_for_planned_new_owned_files[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-f/src/doctrine/missions/mission-steps/software-dev/tasks/prompt.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_prevents_duplicate_create_intent_stubs[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-f/.kittify/overrides/missions/software-dev/command-templates/tasks.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_prevents_duplicate_create_intent_stubs[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-f/src/doctrine/missions/mission-steps/software-dev/tasks/prompt.md]']
E   added (first 20):
    ['tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_documents_create_intent_with_required_ownership_fields[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-i/.kittify/overrides/missions/software-dev/command-templates/tasks.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_documents_create_intent_with_required_ownership_fields[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-i/src/doctrine/missions/mission-steps/software-dev/tasks/prompt.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_explains_create_intent_for_planned_new_owned_files[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-i/.kittify/overrides/missions/software-dev/command-templates/tasks.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_explains_create_intent_for_planned_new_owned_files[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-i/src/doctrine/missions/mission-steps/software-dev/tasks/prompt.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_prevents_duplicate_create_intent_stubs[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-i/.kittify/overrides/missions/software-dev/command-templates/tasks.md]',
     'tests/prompts/test_tasks_prompt_ownership_metadata.py::test_tasks_prompt_prevents_duplicate_create_intent_stubs[<repo-root>/.worktrees/ci-test-topology-performance-01KXBJRT-lane-i/src/doctrine/missions/mission-steps/software-dev/tasks/prompt.md]']
=========================== short test summary info ============================
FAILED tests/architectural/test_gate_coverage.py::test_gc2b_current_selection_matches_baseline[fast-tests-core-misc]
1 failed, 28 passed in 331.84s (0:05:31)
```

**Root-cause analysis (quantitative, not asserted):** every "dropped" node-id
and every "added" node-id names the *same 3 tests* in
`tests/prompts/test_tasks_prompt_ownership_metadata.py` (2 parametrized
`prompt_path` values each = 6), differing **only** in one substring:
`.worktrees/ci-test-topology-performance-01KXBJRT-lane-f` (the worktree the
baseline happened to be frozen from) vs. `-lane-i` (this worktree). Proof —
normalizing that one substring away and re-sorting both sets:

```python
norm_d = sorted(d.replace("lane-f", "<WORKTREE>") for d in dropped)   # 6 items
norm_a = sorted(a.replace("lane-i", "<WORKTREE>") for a in added)     # 6 items
assert norm_d == norm_a   # -> True (verified)
```

`norm_d == norm_a` is `True`: after stripping the worktree-path segment the
two sets are byte-identical. **Zero real content drift** — the same 3 tests
are collected and executed both before and after; nothing is dropped,
nothing double-runs, no coverage is lost.

**Why this happens:** `tests/prompts/test_tasks_prompt_ownership_metadata.py`
computes `_REPO_ROOT = Path(__file__).resolve().parents[2]` and parametrizes
with `ids=lambda path: path.as_posix()` — i.e. it embeds the **absolute
filesystem path** of the checkout into the pytest node-id. GC-2b's baseline
capture (`tests/architectural/_gate_coverage.py::collect_job_nodeids`) is a
real, unmodified `pytest --collect-only -q` subprocess, so it faithfully
records that absolute-path-bearing node-id verbatim. Any baseline frozen
from one checkout location will therefore mismatch a `pytest
--collect-only` run from any *other* checkout location for this one test
file, regardless of whether anything about its selection actually changed.
This is corroborated by the committed baseline file itself, which already
carries a mix of prior lanes' paths (`lane-a`, `lane-b`, `lane-c`, `lane-f`,
and one `lane-u`) — each prior WP's `--freeze-baselines` run only rewrote
the specific rows its own change affected, silently leaving the rest
worktree-path-stamped from whichever lane last touched them.

**This is a genuine, real finding — not a coverage-preservation regression**
introduced by WP01–WP06 (none of those WPs' `owned_files` touch
`tests/prompts/test_tasks_prompt_ownership_metadata.py` or
`_gate_coverage.py`'s collection method), but a **pre-existing baseline-
portability defect**: the E3 mechanism assumes the comparison always runs
from the same absolute path it was frozen from, which is not guaranteed
across developer machines, worktrees, or (critically) **CI's own checkout
path**, which will not match any locally-frozen lane path either. Filed as
a tracked follow-up rather than silently worked around:
[Priivacy-ai/spec-kitty#2607](https://github.com/Priivacy-ai/spec-kitty/issues/2607)
("GC-2b fast-tests-core-misc baseline is not portable across checkout
paths"). Per this WP's own risk mitigation ("file it back to the owning
WP rather than silently adjusting this WP's docs to match broken
behavior"), WP09 does **not** self-authorize a fix here: `_gate_coverage.py`
and the baseline files are WP02's owned surface, and
`tests/prompts/test_tasks_prompt_ownership_metadata.py` is unowned by any
WP in this mission — both are out of scope for a docs/audit WP to patch.

## 3. Cross-job disjointness (GC-2's "orphan-sweep ∩ parallel pool == ∅" clause)

`test_orphan_sweep_and_sync_pool_are_disjoint_today` — evaluated against the
**real, current** topology (not a synthetic fixture): locates the real
`fast-tests-sync-orphan-sweep` gate and the real `fast-tests-sync` pool gate
by `(job, marker_expr)`, and asserts
`gc.cross_job_disjoint_selection([orphan_gate], [pool_gate], universe)` is
empty. **Result: PASS** (part of the 82-passed run in §4). The pool's
`--ignore=tests/sync/test_orphan_sweep.py` (plus the 3 other
`FIXED_RANGE_SUITES` members' `--ignore=` entries) keeps the intersection
empty.

The synthetic unit guard `test_cross_job_disjoint_selection_is_pure_and_detects_overlap`
also **PASSED**, confirming the disjointness primitive itself correctly
detects a real overlap when the `--ignore` is removed (fault-injection),
not just that it returns empty by construction.

## 4. Full guard-family run — real output

Command:

```
uv run pytest tests/architectural/ -k "shard_marker_completeness or gate_coverage or serial_port_preservation or workflow_dist_lint or marker_baseline or job_count_ceiling" -q
```

Real result: **1 failed, 82 passed, 879 deselected in 483.24s (0:08:03)** —
the single failure is the §2.1 finding; every other guard in this family is
green, including:

- **GC-1 (shard partition):** `test_arch_shard_marker_completeness.py` (3
  tests) and `test_next_shard_marker_completeness.py` (3 tests) — every
  `arch`/`next` group test carries exactly one shard marker, union ==
  full root universe. **PASS.**
- **GC-3 (serial real-port isolation):** `test_serial_port_preservation.py`
  (7 tests, generalized to the whole `FIXED_RANGE_SUITES` registry) —
  including `test_no_daemon_run_in_parallel_and_serial_pass_preserved` and
  4 fault-injection cases (each proven to bite on a synthetic violation).
  **PASS.**
- **GC-4 (workflow-distribution lint):** `test_workflow_dist_lint.py` (14
  tests) — no bare `--dist load`; every `-n auto` paired with
  `--dist loadfile`; every `FIXED_RANGE_SUITES` member absent from every
  `-n auto` job; **every sharded matrix in `.github/workflows/*.yml` sets
  `strategy.fail-fast: false`** (`test_matrix_jobs_set_fail_fast_false_in_current_workflows`,
  plus 3 fault-injection cases proving the check bites on `true` and on a
  missing field). **PASS** — confirms C-006 held for every new/changed
  matrix this mission touched (`next_shard_N`, the rebalanced
  `fast-tests-core-misc`, `arch-adversarial`'s pre-existing matrix), not
  just the ones a single WP directly guards.
- **GC-5 (marker-baseline stability):** `test_marker_baseline.py` (5 tests)
  — the `@slow`/`@stress`/`@quarantine`-marked test set does not grow vs
  the committed `marker_baseline.txt` (64 lines). **PASS.**
- **Job-count ceiling:** `test_job_count_ceiling.py` (3 tests) — the
  `quality-gate.needs` roster (grown 47→49 by WP06 T020: enrolling
  `fast-tests-sync-orphan-sweep` and `integration-tests-sync-real-port`)
  stays under the committed ceiling. **PASS.**
- **Model-fidelity spot-check:** `test_model_fidelity_spotcheck_sharded_next_tier`
  — the modeled `next` tier selection equals a fresh, independent real
  `pytest --collect-only` of that job. **PASS.**
- **Both GC-2b fault-injection cases**
  (`test_gc2b_bites_on_baseline_file_side_injection`,
  `test_gc2b_bites_on_producer_side_selection_shrink`) — proving the guard
  itself would catch a real baseline-side or producer-side coverage drop,
  not just that it happens to pass today. **PASS.**

## 5. Outcome

**Not clean — one real (non-coverage) gap found, documented, and filed.**
Per this WP's own Definition of Done and Review Guidance ("confirm the
audit is documented with an explicit outcome — clean, or gaps found and
how they were resolved — not silently skipped"):

- `integration-tests-next` and `slow-tests`: **GC-2b clean**, 0 dropped, 0
  added, at their real current counts (441 / 45).
- `fast-tests-core-misc`: **GC-2b red today in this environment**, but
  proven (§2.1, quantitative normalization) to be 0 real dropped/double-run
  tests — a pre-existing baseline-portability defect unrelated to any
  WP01–WP06 change, filed as
  [#2607](https://github.com/Priivacy-ai/spec-kitty/issues/2607) rather than
  silently worked around. **This defect will also surface on the first
  real CI run of this mission's PR** (CI's checkout path matches none of
  the locally-frozen lane paths either) — flagging here so it is not
  mistaken for a real WP06 regression when that CI run goes red on this
  one parametrized test.
- Cross-job disjointness (orphan-sweep ∩ sync pool), `fail-fast: false` on
  every sharded matrix, and the real-port structural-isolation guarantee:
  all **PASS** against the real, current topology, with fault-injection
  cases confirming each guard actually bites when the invariant is
  violated (not vacuously green).
