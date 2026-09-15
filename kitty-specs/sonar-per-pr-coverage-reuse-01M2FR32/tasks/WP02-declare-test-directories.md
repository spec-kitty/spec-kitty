---
work_package_id: WP02
title: Declare the undeclared test directories
dependencies:
- WP01
requirement_refs:
- FR-006
- NFR-002
planning_base_branch: issue-4334-sonar-reuse-shard-coverage
merge_target_branch: issue-4334-sonar-reuse-shard-coverage
branch_strategy: Planning artifacts for this mission were generated on issue-4334-sonar-reuse-shard-coverage. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4334-sonar-reuse-shard-coverage unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
history:
- date: '2026-09-14'
  note: Created by /spec-kitty.tasks after post-plan adversarial squad recut.
agent_profile: python-pedro
authoritative_surface: .github/ci-module-registry.yml
create_intent:
- scripts/ci/capture_shard_timings.py
- tests/release/coverage_breadth_evidence.md
execution_mode: code_change
owned_files:
- .github/ci-module-registry.yml
- .github/ci-shard-timings.json
- tests/release/ci_retirement_scrub.json
- .github/workflows/ci-router.yml
- scripts/ci/capture_shard_timings.py
- tests/architectural/test_module_shard_registry.py
- tests/architectural/test_ci_router_transcription_guards.py
- tests/architectural/test_retirement_scrub.py
- tests/release/coverage_breadth_evidence.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

Apply the resolved initialization, boundaries, directives and tactics, and state which you applied.
`spec-kitty charter context` reporting `governance unresolved` is a known pre-existing repository
condition — reconstruct from `.kittify/charter/charter.md` and say so. Retry any
`RuntimeError: Global asset input changed`.

## Objective

Give `tests/unit` (26 files) and `tests/specify_cli/runtime` (3 files) a declared home in the test
inventory, so that retiring the duplicate-measurement step does not remove their **per-change**
execution.

## Context you need before starting

The inventory is a **four-file cascade**, not one file:

| File | Role |
|---|---|
| `.github/ci-module-registry.yml` | the declared rows: name, roots, coverage targets, slice count, explicit test dirs |
| `tests/release/ci_retirement_scrub.json` | the recognised-group vocabulary; rows are **bijective** with it |
| `.github/ci-shard-timings.json` | measured per-test durations; balancing is computed from these |
| `.github/workflows/ci-router.yml` | path filter groups per row |

**Accurate framing** (an earlier draft overstated this): those directories are **not** unrun today.
The scheduled interpreter sweep selects them by marker. 479 of their 531 tests run there and in the
step being retired; what this WP restores is **per-change** execution. The remaining 52 are a
pre-existing marker-excluded group filed as **#4351** — do not absorb it here.

## Subtasks

### T007 — Commit a reproducible shard-timings capture script

**Purpose**: `.github/ci-shard-timings.json` was produced by an ad-hoc pytest plugin that **no longer
exists in the tree**. Regenerating it is currently archaeology. Fix that before relying on it.

**Steps**:
1. Write `scripts/ci/capture_shard_timings.py` that records per-test durations in the same shape the
   committed file uses (ordered float lists keyed by module).
2. Record the invocation and the producing run id in the file's metadata fields, matching the
   existing convention.
3. Add a focused unit test for the script's aggregation logic — not a broad integration test.

**Validation**: running the script reproduces a file of the committed shape.

### T008 — Measure durations for the two new directories

**Steps**:
1. Run the capture script over both directories.
2. Record the producing run id alongside the data.

**Validation**: the timings file gains entries for both new rows, with a recorded provenance.

**The trap this exists to avoid**: the runner falls back to uniform weights for a **whole module**
when the number of recorded durations does not equal the number of collected tests — and **no gate
notices**. The balancing guard reads the *committed* file, so it passes vacuously on stale data. That
is why measurement is a subtask and not a footnote.

### T009 — Add the two rows and their recognised-group entries

**Steps**:
1. Add two rows to `.github/ci-module-registry.yml` with explicit `test_dirs` for the two directories.
2. Add matching groups to `tests/release/ci_retirement_scrub.json`. The registry's `roots` and
   coverage targets must equal the group's **verbatim** — a gate asserts ordered list equality.
3. **Modelling decision you must make and record**: these are test directories with no distinct
   source ownership; their source surfaces already belong to other groups. Decide how to express
   `roots` without perturbing router path routing or the unmatched-union guard, and write the
   rationale into the mission's design-decisions tracer. Do not improvise silently.
4. Note: `test_dirs`, when declared, is **preferred over** the `tests/<module>` default, not unioned
   with it — so a row that declares it must list everything it wants run.

**Validation**: the bijection and verbatim-consumption gates pass.

### T010 — Wire the router filter groups

**Steps**: for each new row, add the output, the path filter, the unmatched-union entry, and extend
the always-on architectural job's condition. Three separate router guards assert these transcriptions
match the recognised groups verbatim and that the union is complete.

**Validation**: `pytest tests/architectural/test_ci_router_transcription_guards.py -q` passes.

### T011 — Re-freeze the non-vacuity floor; run the gate battery

**Steps**:
1. The registry gate asserts a row-count floor. Going from 17 to 19 rows may require re-freezing it —
   check the constant and re-freeze **only if** the contract requires (shrink-only ratchets move one
   way; read the assertion before editing the number).
2. Run the full inventory gate battery.

**Validation**: `pytest tests/architectural/test_module_shard_registry.py tests/architectural/test_retirement_scrub.py tests/architectural/test_ci_router_transcription_guards.py -q` passes.

### T012 — Prove collection and fresh balancing

**Steps**:
1. Confirm both directories collect more than zero tests under the runner's selection (the runner
   exits non-zero on a zero-collection row — that is the floor to rely on).
2. Confirm the balancing guard passes against the **fresh** data from T008, not stale committed data.
3. Append the per-slice runtime the two new rows add to `tests/release/coverage_breadth_evidence.md`
   (shared with WP01, which established it) — the mission's aggregate budget counts these rows.

**Validation**: recorded evidence of collection counts and slice runtimes.

## Branch Strategy

- **Planning base branch**: `issue-4334-sonar-reuse-shard-coverage`
- **Final merge target**: `issue-4334-sonar-reuse-shard-coverage`
- Worktrees are allocated per computed lane from `lanes.json`; `spec-kitty implement WP02` resolves
  the path. Do not reconstruct it.

**Test scope (operator ruling):** run **targeted tests only** — your own new tests plus the specific gate files your diff touches (locate them with `grep -rl "<symbol>" tests/ --include="*.py"`). **Do not run the full `tests/architectural/` battery** — it is heavy, has been observed killing dispatched agent processes, and belongs to CI. Record the exact commands and counts in your handoff; "targeted tests pass, full arch suite deferred to CI" is the honest statement.

## Definition of Done

- [ ] A committed, tested capture script exists — regenerating timings is no longer archaeology
- [ ] Both rows declared, with recognised-group entries matching verbatim
- [ ] Router transcriptions complete; all three router guards pass
- [ ] Timings measured fresh, with a recorded producing run
- [ ] Both directories collect >0 tests in the matrix
- [ ] The `roots` modelling decision is recorded in the design-decisions tracer with its rationale
- [ ] `ruff check .` and `ruff format --check .` clean

## Reviewer Guidance

- **Check the timings are measured, not fabricated.** A list of the right length passes every gate
  while silently degrading balancing to a test-count split. Ask for the producing run id.
- **Check the `roots` decision is recorded**, not improvised — these rows have no distinct source
  ownership and the choice perturbs router routing.
- **Do not accept "the skew gate passes" as evidence of balance.** It reads the committed file; on
  stale data it passes vacuously. That is the finding this subtask exists for.
- **Reviewer ≠ implementer** (C-007).
