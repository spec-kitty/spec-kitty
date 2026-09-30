---
title: CI Job Timings — ci-test-topology-performance-01KXBJRT
description: Committed E4 timings artifact for the CI test-topology performance mission — pre-mission baseline, post-change budgets, and real per-leg wall-clock from a CI run.
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/testing/testing-parallel.md
- docs/plans/testing/test-suite-acceleration-plan.md
- kitty-specs/ci-test-topology-performance-01KXBJRT/data-model.md
- kitty-specs/ci-test-topology-performance-01KXBJRT/spec.md
---

# CI Job Timings — `ci-test-topology-performance-01KXBJRT`

> **Superseded.** Timings for the retired `ci-quality.yml` shard topology of mission `01KXBJRT`; the modular CI from #3995 (the lean CI reinstatement) replaced those jobs. See [CI gate mechanics](../../development/reference/ci-gate-mechanics.md). Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

This is the mission's **E4 timings artifact** (`data-model.md` E4, mirroring
`tests/architectural/_gate_coverage.py`'s `_TIMINGS_BASELINE` shape). Per
IC-07 / the project's flakiness policy
([docs/development/testing-flakiness.md](../../development/testing/testing-flakiness.md)):
**budgets here are measured and recorded, never asserted live.** No pytest
guard reads this file; a human/agent re-measures and updates it when the
topology changes again.

## 1. Pre-mission baseline (the grounding evidence)

Source: GitHub Actions run **29196440986**, `main` @ `db904ebc5`,
`workflow_dispatch`, overall **FAILURE** (unrelated Sonar quality-gate
failure — see `spec.md`'s Evidence section). This run is fully serial
(no `-n auto`, no `--durations`) and is the sole empirical basis for every
NFR-001..008 budget below.

| Job / leg | Minutes | `run_id` | Note |
|-----------|--------:|----------|------|
| `integration-tests-next` | 69.2 | 29196440986 | 441 tests fully serial; the dominant cost this mission targets. |
| `fast-tests-core-misc (specify-cli-rest)` | 12.2 | 29196440986 | Already a shard matrix but imbalanced vs `core-misc` (4.7 min). |
| `fast-tests-charter` | 12.0 | 29196440986 | Already `-n auto --dist loadfile`, but two sequential steps (charter + agent) summed on one job's wall-clock. |
| `slow-tests` | 10.7 | 29196440986 | ~4 min of this was full-tree collection tax. |
| `fast-tests-cli` | 8.3 | 29196440986 | `--dist loadfile` single-file tail on `test_charter_activate_commands.py`. |
| `fast-tests-sync` | 6.3 | 29196440986 | The serial orphan-sweep step was ~130 s of this job's wall-clock. |

## 2. Post-change topology — budgets recorded, not gated

The topology below is what actually shipped (WP01–WP06, verified against
`.github/workflows/ci-quality.yml` on this branch). **No real post-change
CI run of this shipped topology exists yet** — this mission's branch
(`feat/ci-test-topology-performance`) has not been pushed to a remote that
runs `ci-quality.yml`, and no PR has been opened. Recording fabricated
wall-clock numbers here would violate the project's flakiness/honesty
policy, so every `minutes` cell below is **PENDING** until a real run exists.
Re-run this section (see §5, "How to refresh this artifact") the first time
`ci-quality.yml` executes on this branch (or its PR), and replace the
`PENDING` rows with the real `--durations`/job-summary figures plus that
run's id.

| Job / leg | NFR target | Pre-change (§1) | Post-change minutes | `run_id` | Met? |
|-----------|-----------|-----------------:|---------------------:|----------|------|
| `integration-tests-next / next_shard_1` | NFR-001 ≤ 7 min | 69.2 (whole job, serial) | **PENDING** | *(none yet)* | PENDING |
| `integration-tests-next / next_shard_2` | NFR-001 ≤ 7 min | — | **PENDING** | *(none yet)* | PENDING |
| `integration-tests-next / next_shard_3` | NFR-001 ≤ 7 min | — | **PENDING** | *(none yet)* | PENDING |
| `slow-tests` | NFR-002 ≤ 4 min | 10.7 | **PENDING** | *(none yet)* | PENDING |
| `fast-tests-sync-orphan-sweep` (new job, WP06 T016) | NFR-003 ≥ ~130 s off `fast-tests-sync`'s critical path | ~130 s embedded in the 6.3 min above | **PENDING** | *(none yet)* | PENDING |
| `fast-tests-cli` | NFR-004 ≤ 5.5 min | 8.3 | **PENDING** | *(none yet)* | PENDING |
| `fast-tests-core-misc / specify-cli-rest` | NFR-007 ≤ 7 min | 12.2 | **PENDING** | *(none yet)* | PENDING |
| `fast-tests-core-misc / specify-cli-rest-2` (new shard, WP06 T017) | NFR-007 ≤ 7 min | — | **PENDING** | *(none yet)* | PENDING |
| `fast-tests-core-misc / core-misc` | NFR-007 ≤ 7 min | 4.7 (pre-mission, unchanged shard) | **PENDING** | *(none yet)* | PENDING |
| `fast-tests-charter` | NFR-008 ≤ 7 min | 12.0 (summed with agent) | **PENDING** | *(none yet)* | PENDING |
| `fast-tests-agent` (de-serialized from `fast-tests-charter`, WP06 T018) | NFR-008 (charter's split partner) | included in the 12.0 above | **PENDING** | *(none yet)* | PENDING |
| 13 serial `integration-tests-*` single-dir jobs swept to parallel (WP06 T019: `agent`, `charter`, `cli`, `dashboard`, `doctrine`, `lanes`, `merge`, `missions`, `post-merge`, `release`, `review`, `status`, `sync`, `upgrade` — see §3 for the exact 14-job enumeration incl. `integration-tests-next`) | not separately budgeted (NFR-001..008 only name the headline jobs) | not separately measured pre-mission | **PENDING** | *(none yet)* | n/a |

**Shard-leg balance skew (NFR-006, ≤ 20% wall-clock spread):** cannot be
computed until real per-leg minutes exist for `next_shard_1/2/3` and the
`fast-tests-core-misc` legs (§4 also flags that the `next_shard_N` split
itself is still WP01's placeholder bin-pack, not durations-rebalanced —
this NFR is doubly pending).

## 3. Runner core-count context (plan.md Technical Context)

`plan.md`'s Technical Context states: "GitHub Actions `ubuntu-latest`
runners (assume ≥4 cores for the interim budgets; confirmed by the FR-001
`--durations` run)." As of this writing GitHub-hosted `ubuntu-latest`
standard runners provide **4 vCPUs**. Record the *actual* observed core
count from the real run's `--durations=25` / job-summary output alongside
the `run_id` once §2 is filled in — do not assume it stayed at 4 without
checking, since GitHub's standard-runner spec can change between mission
authoring and the real run landing.

## 4. Known gaps affecting this artifact (do not silently omit)

- **`next_shard_N` balance is unmeasured.** `tests/_next_shard_map.py`'s own
  docstring says its 3-way split is "a **placeholder** — a greedy bin-pack
  over a `def test_` count proxy... provisional pending WP06's real
  `--durations=25` evidence... which rebalances this table from measured
  wall-clock." WP06's landed commit (`f132ee611`) parallelized
  `integration-tests-next` (T014) and rebalanced `fast-tests-core-misc`
  (T017), but did **not** touch `tests/_next_shard_map.py` to rebalance the
  `next_shard_N` split from real durations. NFR-006's ≤20% skew claim for
  the `next` tier is therefore still open — flagging here rather than
  silently marking it satisfied. Follow-up: once §2's real run exists, if
  any `next_shard_N` leg's minutes diverge from its siblings by >20%,
  rebalance `tests/_next_shard_map.py`'s file assignment from that run's
  per-file `--durations=25` output (same method `_arch_shard_map.py`
  documents using), not by re-guessing.
- **Coverage-union audit found a real (non-timing) gap** — see
  [`ci-coverage-union-audit.md`](ci-coverage-union-audit.md) for the full
  evidence: `GC-2b` is currently RED for `fast-tests-core-misc` in this
  environment, filed as
  [Priivacy-ai/spec-kitty#2607](https://github.com/Priivacy-ai/spec-kitty/issues/2607).
  It is a pre-existing baseline-portability defect unrelated to any test
  actually being dropped or double-run — see that document for the
  quantitative proof.

## 5. How to refresh this artifact

1. Push `feat/ci-test-topology-performance` (or its PR) and let
   `ci-quality.yml` run for real.
2. Pull each job's `--durations=25`/`--durations=50` output (uploaded as
   part of each job's `out/reports/` artifact) or the Actions run summary.
3. Replace every `PENDING` cell in §2 with the measured minutes and that
   run's numeric id; compute NFR-006 skew from the `next_shard_N` and
   `fast-tests-core-misc` rows.
4. If any NFR target is missed, do not silently adjust the target — record
   the miss plainly (this file is a measured record, not a gate) and open a
   follow-up if a rebalance or further split is warranted.
5. This file is a single point-in-time record, updated **in place** on
   re-measurement (per the mission's own risk mitigation) — do not append a
   second, conflicting timings table for a later run; supersede this one.
