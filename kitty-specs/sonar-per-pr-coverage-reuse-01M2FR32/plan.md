# Implementation Plan: Per-PR Sonar reuses CI Modules coverage

**Branch**: `issue-4334-sonar-reuse-shard-coverage` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/spec.md` (revised post-squad, commit `d934734`)

## Summary

Retire the per-change quality reporter's own test-executing step (median **22m32s**, n=12) and have
the report consume the coverage the per-module matrix already produced for the same commit.

Reuse alone is **not** sufficient: the matrix measures each module with a narrow coverage target, so
a test that exercises another module's code has the measurement dropped — 4,391 statements are
covered by the retiring step and not by the matrix, and **58 of 72** `specify_cli` subpackages are
measured only through one broad-target row whose tests do not exercise them. The plan therefore
corrects measurement **breadth first**, then moves the report onto the corrected measurement.

Three design rulings (plan Decision Moments, 2026-09-14) shape the approach:
1. The trusted default-branch checkout stays the working directory; the validated tested revision is
   fetched into a subdirectory and every analysis setting is passed explicitly from the trusted tree.
2. Every registry row broadens to top-level coverage targets, relying on coverage-report **union**
   semantics; the runtime cost is measured, not assumed.
3. `ci-aggregate.yml` gains a terminal verdict job so "never merge-blocking" becomes declarable.

## Technical Context

**Language/Version**: Python 3.11+ (gates, scripts); GitHub Actions workflow YAML; `make` targets
**Primary Dependencies**: `pytest` + `pytest-cov` (coverage production), `PyYAML` (registry/workflow parsing in gates), `coverage.py` XML reports, SonarSource `sonarqube-scan-action` / `sonarqube-quality-gate-action` (SHA-pinned), `actions/download-artifact`
**Storage**: Committed declarative data files — `.github/ci-module-registry.yml`, `.github/ci-shard-timings.json`, `tests/release/ci_retirement_scrub.json`; run-scoped GitHub Actions artefacts (`ci-aggregate-reconciled-coverage`, `ci-aggregate-source`)
**Testing**: `pytest`, targeted at `tests/architectural/`, `tests/release/`, `tests/ci/`; new fault-injection gates follow the in-repo synthetic-fixture precedent (`test_suite_jobs_gate_blocking.py::test_faultinjection_*`)
**Target Platform**: GitHub Actions `ubuntu-latest` stock runners (no self-hosted); SonarCloud as an external, non-blocking reporting service
**Project Type**: single (CI/pipeline configuration + architectural gates; no application runtime code)
**Performance Goals**: per-change runner-minutes fall by ≥15 (retiring step median 22m32s); broadened coverage targets add ≤3 min to the longest affected shard, **measured and recorded**; no shard approaches the 30-minute job cap
**Constraints**: report is advisory under every outcome (failure/timeout/cancellation/absence); must not run on the primary branch; must not grow the set of contributions processed alongside privileged credentials; analysis settings never read from the change under review; analysed revision must equal the measured revision
**Scale/Scope**: 17 registry rows → 19; 34 coverage shards → ~36; 4 workflow files, 3 committed data files, gate-module count **unknown until the FR-010 derivation runs** (the v1 estimate was ~4× low, so no number is asserted here), 2 documentation pages

## Charter Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Charter is present (`.kittify/charter/charter.md`, v1.4.0) and was loaded at session start.
`spec-kitty charter context --action plan --json` returns `mode: compact` with
`references_count: 0` and a **governance-unresolved** diagnostic (30+ selected directives absent
from `packs/built-in/directives/`). That is a pre-existing repository condition — logged as tooling
friction, raised for its own ticket, and **not** treated as a licence to skip the rules. Checks below
are made against the charter document itself.

| Charter rule | Status | Evidence |
|---|---|---|
| **SO#1 Adversarial squad at planning point-cuts** | PASS | 4-lens post-spec squad executed; findings folded at `d934734`; record in `work/4334-sonar-coverage-reuse/squad-post-spec.md`. Post-**plan** squad executed (3 lenses, `work/4334-sonar-coverage-reuse/squad-post-plan.md`) — it overturned two design rulings and corrected a false rationale I had given the operator. Post-tasks squad still owed. |
| **SO#2 Campsite cleaning / tidy-first** | **PARTIAL** | Corrected: WP01 is **not** behaviour-preserving — broadening changes which files appear in coverage reports, which changes the blocking change-coverage gate's `absent` set and its denominator. Calling it tidy-first mislabelled the riskiest work as the safe work. No genuine tidy-first enabler precedes the functional change; the doc-drift fold is closeout, not a preceding step. |
| **SO#3 Mission tracer files** | PASS | Seeded at `c7afae6`, appended through planning, including a correction of a rationale I got wrong. |
| **SO#4 Test remediation / red-first** | PASS (externally evidenced) | Circular self-citation removed. Evidence is the repo's own extraction harness (`test_dual_mode_contract.py:268-289`), confirmed reusable: authoring the execution condition as a heredoc evaluator yields five independent **behavioural** red-first checks before the job exists. Not "C-006 says so". |
| **SO#5 Architectural gate discipline** | **PARTIAL** | Concrete floor + self-mutation battery are specified (six mutations). The charter's triad also requires a **shrink-only ratchet**, absent from NFR-007 and the contract — owed. Evidence is external (the squad's independent vacuity proof against `_gate_coverage.py:80-90`), not self-citation. |
| **SO#6 Canonical sources & unification** | PASS | The registry stays the single declared authority for what CI runs (C-002). No third copy of the reconcile logic — the reuse consumes the existing published artefacts. |
| **SO#7 Git & workflow discipline** | PASS | C-008: topic branch → PR to `main`; the operator merges. No version numbers in scope. |
| **SO#8 Mission hygiene** | PASS | C-007 reviewer ≠ implementer. C-007 reviewer ≠ implementer holds. But the Automatic-Analysis issue **does not yet exist**, so an issue-matrix row for it cannot. **Now filed: #4350** (Automatic Analysis precondition) and **#4351** (dormant 52-test file). Issue-matrix rows owed for #4334, #4350, #4351, #825, #4248, #4011. |
| **SO#9 Red-main & release discipline** | **PARTIAL (closing obligation)** | The 52-test group is filed as **#4351**; the 5 `performance`-marked tests are enumerated by FR-016's derivation. Reported, not absorbed, not green-washed. Remaining closing obligation: the issue-matrix verdicts at approval. |
| **Terminology Canon** | PASS | Mission vocabulary throughout; no `feature*` aliases introduced. |
| **Identifier safety** | N/A | No user-derived storage identifiers in scope. |
| **Supply-chain safety (DIR-051)** | PASS-WITH-CONDITION | No dependency added, upgraded, or removed. Both SonarSource actions remain SHA-pinned and pin-parity must move with the job (FR-010). **Condition:** a verbatim relocation would carry two *floating* tags (`@v4`, `@v5`) into a fully SHA-pinned file, and would inherit a dependency-sync step the new job does not need — which would execute change-authored build config. Both must be dropped. See `research.md` §7. |

**No violations requiring Complexity Tracking justification.**

## Project Structure

### Documentation (this mission)

```
kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/
├── plan.md              # This file
├── spec.md              # Revised post-squad (d934734)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
├── checklists/          # Spec quality checklist
├── decisions/           # 7 Decision Moments (4 specify, 3 plan)
├── traces/              # Tracer files (tooling-friction, approach, design-decisions)
└── tasks.md             # Phase 2 — created by /spec-kitty.tasks, NOT here
```

### Source Code (repository root)

```
.github/
├── ci-module-registry.yml          # WP01 — cov_targets breadth + 2 new rows
├── ci-shard-timings.json           # WP01 — measured durations for the new rows
└── workflows/
    ├── ci-modules.yml              # (read-only: matrix caller, unchanged)
    ├── module-tests.yml            # (read-only: shard runner, unchanged)
    ├── ci-router.yml               # WP01 — filter groups for the new rows
    ├── ci-aggregate.yml            # WP02 — new reporting job + terminal verdict job
    └── ci-quality.yml              # WP03 — retire the sonarcloud job

scripts/ci/
├── aggregate_source.py             # WP02 — source record consumed as-is (see data-model)
└── fleet_verdict.py                # WP02 — read-only check that the verdict job suffices

tests/
├── release/
│   ├── ci_retirement_scrub.json    # WP01 — recognised group names (bijection gate)
│   ├── test_sonar_workflow.py      # WP03 — relocate the PR-only + pin-parity assertions
│   └── test_release_ci_ownership.py# WP03 — exact-job-set pin
└── architectural/
    ├── test_module_shard_registry.py      # WP01 — registry gates
    ├── test_suite_jobs_gate_blocking.py   # WP03 — allowlist rationale disposition
    └── test_no_duplicate_suite_execution.py  # WP04 — NEW: the fault-injection battery

docs/
├── convergence/interim-ci-producer.md          # WP05 — job inventory lockstep
└── development/reference/coverage-signals.md   # WP05 — #4011 doc drift
```

## Complexity Tracking

*No Charter Check violations. This table records deliberate scope expansions ruled by the operator,
so the trade stays auditable.*

| Expansion | Why needed | Simpler alternative rejected because |
|-----------|------------|--------------------------------------|
| Correct `cov_targets` breadth (FR-013) | Reuse alone permanently loses 2,808 statements; without this the mission trades a visible 21.8pp understatement for an invisible permanent one | "Declare + guard, fix later" leaves a known measurement defect in the surface this mission makes authoritative |
| Full inventory cascade (registry + scrub + timings + router) | Structurally correct module naming; the bijection gate refuses new rows otherwise | A two-line `test_dirs` fold on an existing row clears every gate and was genuinely viable — rejected by operator ruling in favour of correct naming |
| Terminal verdict job in `ci-aggregate.yml` | **Corrected rationale:** it buys *declarability* — a seam a test can assert the reporting job is excluded from — which SC-006 needs. It is **not** the enforcement mechanism. | The original rationale ("`continue-on-error` leaves timeout and cancellation unenforced") was **refuted live**: 10 sampled runs show 7 failed jobs and 10 green run conclusions, a job-level timeout is a job failure `continue-on-error` tolerates identically, and `cancelled` is absent from the verdict script's red set. Modelled on `ci-router.yml`'s skipped-tolerant `router-gate`, **not** `quality-gate` — both sibling jobs are legitimately skippable. |

## Parallel Work Analysis

*Recut after the post-plan squad. The earlier 5-WP / 2-lane cut had two false dependencies, a WP
shipping a job nothing asserted, and the battery's strongest mutation provable only against a
fixture.*

### Dependency Graph

```
Lane A (measurement)     WP01a breadth ──→ WP01b inventory cascade
                          (module-tests.yml,     (2 rows + scrub groups +
                           aggregate cost,        router x3 + re-measured
                           per-file baseline)     timings + capture script)

Lane B (topology)  WP02a detector substrate + verdict seam
                        │   (extend gate model beyond ci-quality.yml; router-gate-shaped
                        │    verdict job; battery mutations 1-4 proven RED against the
                        │    LIVE retiring step, before it is deleted)
                        ↓
                   WP02b reporting job
                        │   (two-tree replacement at trusted root; heredoc-evaluator
                        │    condition so all 5 conjuncts get behavioural red-first)
                        ↓
                   WP03 retirement + gate dispositions + docs lockstep
                        │
                        ↓
                   WP04 battery closeout (mutations 5-6 + non-vacuity floor)

PRECONDITION (operator, out-of-band): disable Automatic Analysis (**#4350**); exit criterion = a
non-zero published coverage measurement. Blocks FR-015/SC-010 only, not the build.
```

**Why this order.** The detector substrate moves **before** the retirement so battery mutation #1
("reintroduce the retiring step") is demonstrated red against **live source** rather than a synthetic
fixture — the non-vacuity standard the charter's gate discipline demands. Doing it after retirement
would leave only a fixture, reproducing the exact blindness the battery exists to close.

### Work Distribution

**Lane assignment follows the dependency graph, not the work-package count.** A lane branches from
the mission base, so a dependent work package on its *own* lane would start without its dependency's
changes and need a manual dependency merge. Sequential work shares one lane.

| Lane | Sequence | Owns (disjoint across lanes) |
|---|---|---|
| **A — measurement** | WP01a → WP01b | `.github/workflows/module-tests.yml`, `.github/ci-module-registry.yml`, `.github/ci-shard-timings.json`, `tests/release/ci_retirement_scrub.json`, `.github/workflows/ci-router.yml`, `scripts/ci/capture_shard_timings.py` (new), `tests/architectural/test_module_shard_registry.py`, `test_ci_router_transcription_guards.py`, `tests/release/test_retirement_scrub.py` |
| **B — topology & enforcement** | WP02a → WP02b → WP03 → WP04 | `.github/workflows/ci-aggregate.yml`, `.github/workflows/ci-quality.yml`, `tests/architectural/_gate_coverage.py`, `test_suite_jobs_gate_blocking.py`, `test_workflow_coherence.py`, `tests/release/test_sonar_workflow.py`, `test_release_ci_ownership.py`, `tests/_arch_shard_map.py`, the new battery module, `docs/convergence/interim-ci-producer.md`, `docs/development/reference/coverage-signals.md` |

The two lanes are genuinely independent: Lane A changes *what is measured*, Lane B changes *who reads
it*. Neither reads the other's files. Lane B's correctness does not depend on Lane A having landed —
only the mission's aggregate-cost claim does, and that is measured at consolidation.

**Lane B absorbs the documentation work** (formerly a third lane). C-010 requires those pages to move
*in the same change* as the topology they describe, and a lane for two doc pages would cost a branch,
worktree, review cycle and consolidation merge for zero critical-path gain.

### Coordination Points

- **WP01a publishes, to named paths, before WP01b starts**: the per-file coverage baseline
  (NFR-009/SC-004), the aggregate runner-minute delta, reconciled artefact **total bytes**, and the
  downstream parse step's duration (NFR-002). A baseline with no path is a baseline invented at
  approval time. Measured evidence to date: +9.9% on one slice, artefact ~6× — the size, not the
  runtime, is the risk to watch.
- **WP02a publishes the FR-010 gate inventory** as a committed machine-readable artefact produced by
  a committed derivation script, with a re-derive-and-diff gate. It becomes WP03's worklist. Derived,
  never transcribed — the v1 inventory was ~4× understated with four false positives.
- **WP01b must re-measure shard timings**, not inherit them: a length mismatch silently degrades
  balancing to a test-count split and **no gate notices**. The original capture plugin no longer
  exists in-tree, so WP01b commits a reproducible capture script.
- **Integration**: C-006's declared limit stands — a `workflow_run` handler executes only the
  default-branch copy of its file, so the production trigger cannot run pre-integration. Each WP
  proves what it can pre-merge (behavioural checks over extracted evaluators, synthetic fixtures) and
  the first post-integration run is **observed and recorded**, never assumed.
