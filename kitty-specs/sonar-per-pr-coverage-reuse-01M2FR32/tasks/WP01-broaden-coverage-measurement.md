---
work_package_id: WP01
title: Broaden coverage measurement
dependencies: []
requirement_refs:
- FR-013
- FR-016
- NFR-002
- NFR-009
planning_base_branch: issue-4334-sonar-reuse-shard-coverage
merge_target_branch: issue-4334-sonar-reuse-shard-coverage
branch_strategy: Planning artifacts for this mission were generated on issue-4334-sonar-reuse-shard-coverage. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4334-sonar-reuse-shard-coverage unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-sonar-per-pr-coverage-reuse-01M2FR32
base_commit: 576801bc0249171bb037e4ccdc5ccbe66c186ba7
created_at: '2026-09-14T14:39:22.903856+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- date: '2026-09-14'
  note: Created by /spec-kitty.tasks after post-plan adversarial squad recut.
agent_profile: python-pedro
authoritative_surface: .github/workflows/module-tests.yml
create_intent:
- tests/architectural/test_coverage_breadth.py
- tests/release/coverage_breadth_baseline.json
- tests/release/coverage_breadth_evidence.md
execution_mode: code_change
owned_files:
- .github/workflows/module-tests.yml
- tests/architectural/test_coverage_breadth.py
- tests/release/coverage_breadth_baseline.json
- tests/release/coverage_breadth_evidence.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile:

```
/ad-hoc-profile-load python-pedro
```

Apply the resolved initialization, boundaries, directives and tactics, and state which you applied.
If `spec-kitty charter context` reports `governance unresolved`, that is a known pre-existing
repository condition — reconstruct from `.kittify/charter/charter.md` and say that you did.
If any `spec-kitty` command fails with `RuntimeError: Global asset input changed`, retry it; that is
a self-healing startup race.

## Objective

Make every matrix slice measure the **full top-level package set** instead of only the package its
own module is named for, so a test that exercises another module's code stops having its coverage
measurement silently discarded.

Then record the four baselines every later acceptance claim in this mission depends on.

## Why this matters (read before touching anything)

Today 16 of 17 inventory rows declare a **narrow** coverage target. When a test in one module's test
directory executes another module's source, the producing slice's narrow `--cov` **drops the hit** —
the line is not recorded as zero, it is *absent*. Measured consequence:

| | covered statements | of the 128,878-statement union |
|---|---|---|
| matrix union (34 slices) | 71,070 | 55.15% |
| the step being retired | 42,933 | 33.31% |

4,391 statements are covered by the retiring step and **not** by the matrix. Without this work
package, the mission would trade a visible 21.8-point understatement for a smaller but permanent one.

**58 of 72 `specify_cli` subpackages** are currently measured only through one broad-target row whose
tests do not exercise most of them — including `auth` (37 files), `tool_surface` (41), `core` (48),
`tracker` (18), `migration` (18), `retrospective` (15).

## ⚠️ This work package is NOT behaviour-preserving

Broadening changes which files appear in the coverage reports. The blocking change-coverage gate
pre-scores with `absent = statements - set(coverage.measured_lines(path) or ())`
(`scripts/ci/validate_diff_coverage.py:57`) and then enforces a ≥90% threshold
(`.github/workflows/ci-aggregate.yml:412`). Files that were **absent** become
**present-but-uncovered**, which means they enter the denominator and the threshold can now bite.

**You are changing merge-blocking behaviour for every pull request in this repository.** Treat this
as the riskiest package in the mission. T003 and T006 exist precisely to make that consequence
visible before it surprises someone.

## Constraints

- **Do not touch `.github/ci-module-registry.yml` or `tests/release/ci_retirement_scrub.json`.**
  An earlier design broadened the registry's `cov_targets`; that is blocked by
  `tests/architectural/test_module_shard_registry.py:163-183`, which asserts each row's targets equal
  its recognised-group entry **verbatim** because those entries are census-derived ownership records.
  Breadth is therefore applied in the **runner**, leaving ownership data untouched. This is an
  operator ruling — do not revisit it.
- Those two files belong to WP02. Stay inside your `owned_files`.

## Subtasks

### T001 — Red-first: assert every slice measures the full package set

**Purpose**: pin the intended behaviour before changing it. This must be RED on the current tree.

**Steps**:
1. Create `tests/architectural/test_coverage_breadth.py`.
2. Parse `.github/workflows/module-tests.yml` and locate the step that builds the coverage flags.
3. Assert that the coverage targets it produces are the **full top-level package set**, independent
   of the matrix inputs — i.e. the flags do not vary per module.
4. Derive the expected package set from the source tree (top-level packages under `src/`), never from
   a hand-copied literal — a hardcoded list is a second authority and will drift.
5. Add `pytestmark` — this repo enforces a marker on every test file
   (`tests/architectural/` convention; check neighbours for the right marker).

**Validation**: the test FAILS on the current tree, naming the per-module derivation as the reason.
Capture that red output; the reviewer will ask for it.

**Do not**: assert against a literal expected string of the `run:` block. Assert the derived
*behaviour* — which targets are produced — so the test survives reformatting.

### T002 — Broaden the coverage-target derivation

**Purpose**: make T001 green.

**Steps**:
1. In `.github/workflows/module-tests.yml`, the run step currently builds one `--cov=<target>` flag
   per entry of the `cov_target` input. Replace that derivation with the constant full top-level
   package set.
2. Keep the `cov_target` input itself — it remains the row's ownership declaration and other gates
   read it. You are changing what the runner *measures*, not what the inventory *declares*.
3. Leave the report path, the junit path, the marker deselection and the shard selection untouched.
4. Add a comment stating why the flags are constant and pointing at this mission, so a future reader
   does not "fix" it back to the per-module form.

**Validation**: T001 passes. Targeted re-run of `tests/architectural/test_module_shard_registry.py` still passes (the gate you must prove you did not break).

### T003 — Measure and record the aggregate cost

**Purpose**: the mission's headline metric is **aggregate** runner-minutes. A per-slice budget cannot
protect it: 34 slices each absorbing one minute is +34 minutes against ~22 saved.

**Steps**:
1. Run one representative slice both ways (narrow vs broadened) locally and record wall-clock, XML
   bytes, and covered-statement count. A prior measurement on one slice gave **+14.3 s (+9.9%)** and
   **+30,200 covered statements outside that slice's own module** — reproduce and confirm the shape.
2. From the branch's own CI run, record the **aggregate** job-duration sum across the matrix, before
   and after.
3. Record the reconciled artefact **total bytes** (~29.8 MB before; expect ~6× after) and the
   downstream parse step's duration.
4. Write all of it to `tests/release/coverage_breadth_evidence.md`, with the producing run ids.
   (Committed test-adjacent data, matching the convention the other committed CI data files follow.)

**Validation**: the file exists, every number cites a run id or a reproducible command.

**If aggregate cost exceeds the saving**: that is a finding to surface, not to absorb. Say so
plainly in the evidence file and stop for a ruling. The operator has accepted a runtime-for-accuracy
trade, but "net negative" is a different fact than "somewhat slower".

### T004 — Record the per-file coverage baseline

**Purpose**: NFR-009 and SC-004 both compare against "a recorded baseline". A baseline with no path
is one an implementer invents at approval time.

**Steps**:
1. Produce the retiring step's per-file covered-line counts (the reproduction command is in
   `quickstart.md` §2).
2. Produce the post-change matrix union's per-file counts.
3. Commit both as machine-readable data in `tests/release/coverage_breadth_baseline.json`, with
   the producing run ids recorded alongside.

**Validation**: both artefacts exist and are diffable by T006.

### T005 — Derive and commit the marker-mismatch exception set

**Purpose**: FR-016. Some tests are selected by the retiring step and deselected by **every** matrix
slice, because the retiring step's marker expression does not exclude the performance family while
every slice does. These are a declared exception to "no per-file regression" — and they must be
*derived*, not listed from memory.

**Steps**:
1. Write the derivation as a committed script or test: the set difference between the retiring step's
   selection and the slices' selection over the same directories.
2. Run it. At the time of planning it returned exactly 5 tests, all in `tests/status`. Confirm the
   current number rather than trusting that one.
3. Commit the derivation **and** its output, so the set can be re-derived rather than re-read.

**Validation**: re-running the derivation reproduces the committed output.

**Note**: a separate, larger dormant group (52 tests in one file, excluded by markers from every
selection including the scheduled sweep) is already filed as **#4351**. It is pre-existing and not
this mission's to fix — do not absorb it.

### T006 — Prove no per-file coverage regression

**Purpose**: close the loop on NFR-009 / SC-004.

**Steps**:
1. Diff the two baselines from T004 per file.
2. Any file whose covered-line count decreased must be explained by the T005 exception set.
3. Anything else is a real regression — investigate rather than widening the exception set.
4. Record the verdict in `tests/release/coverage_breadth_evidence.md`.

**Validation**: a committed comparison showing zero unexplained regressions, and the count of
statements recovered (expect ≥2,808 from the breadth fix).

## Branch Strategy

- **Planning base branch**: `issue-4334-sonar-reuse-shard-coverage`
- **Final merge target**: `issue-4334-sonar-reuse-shard-coverage`
- Execution worktrees are allocated **per computed lane** from `lanes.json`. Do not create a worktree
  by hand and do not reconstruct the path — `spec-kitty implement WP01` resolves it.

**Test scope (operator ruling):** run **targeted tests only** — your own new tests plus the specific gate files your diff touches (locate them with `grep -rl "<symbol>" tests/ --include="*.py"`). **Do not run the full `tests/architectural/` battery** — it is heavy, has been observed killing dispatched agent processes, and belongs to CI. Record the exact commands and counts in your handoff; "targeted tests pass, full arch suite deferred to CI" is the honest statement.

## Definition of Done

- [ ] T001's test was RED before T002 and is GREEN after (the reviewer will ask for both outputs)
- [ ] Coverage flags are constant across slices and derived from the source tree, not a literal list
- [ ] `.github/ci-module-registry.yml` and `tests/release/ci_retirement_scrub.json` are **untouched**
- [ ] Aggregate runner-minutes, artefact bytes and parse duration are recorded with run ids
- [ ] Per-file baselines committed; zero unexplained regressions
- [ ] The marker-mismatch exception set is derived by a committed script, not transcribed
- [ ] Targeted tests pass: the new breadth test + `test_module_shard_registry.py` + any file found by `grep -rl "module-tests" tests/ --include="*.py"`. Full arch suite deferred to CI.
- [ ] `ruff check .` and `ruff format --check .` both clean (format is a separate gate from lint)

## Reviewer Guidance

- **Demand the red output.** A test written after the change is not red-first.
- **Check the expected package set is derived**, not hardcoded. A literal list is a second authority.
- **Check the aggregate number, not the per-slice one.** The per-slice budget cannot protect the
  aggregate criterion — that was a squad finding, and it is the most likely way this mission ships
  net-negative while every stated constraint passes.
- **Check the registry and recognised-group files are untouched.** Broadening them reds a verbatim
  gate 17 times; if you see them in the diff, the implementer took the refuted path.
- **Reviewer ≠ implementer** (C-007).
