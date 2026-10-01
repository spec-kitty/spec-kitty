# Implementation Plan: CI runtime stabilisation

**Branch**: `issue-5510-ci-runtime-stabilisation` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/ci-runtime-stabilisation-01M3TZH6/spec.md`

## Summary

Make the architectural safety net honest first (nightly full-battery backstop), then cut the
battery's critical path (explicit four workers, an always-on fast static-gate job, a two-leg
file-partitioned battery matrix balanced by one shared shard selector, per-file caching of
duplicated scans), close the CI-config blind spot (a new `ci_config` path group that selects the
battery), remove duplicate runs and selections (legacy router module-path jobs, the duplicate
corpus lane, ready-for-review re-runs of already-green commits) and keep them out with a live
cross-job uniqueness check, split the consolidation module shard, and record the policy changes
as ADR amendments and a contract amendment. All design choices, alternatives and operator
decisions are consolidated in [research.md](research.md) (decision log D-01…D-37).

## Technical Context

**Language/Version**: Python 3.11+ (CI scripts and tests); GitHub Actions workflow YAML
**Primary Dependencies**: pytest, pytest-xdist (pinned, `-n 4` supported), dorny/paths-filter (existing), GitHub REST API via the in-workflow `GITHUB_TOKEN` through the preinstalled `gh` CLI (no new dependency)
**Storage**: Repository files — `.github/ci-module-registry.yml`, `.github/ci-shard-timings.json`, workflow artifacts (tested-key markers)
**Testing**: pytest; red-first ATDD tests under `tests/ci/` and `tests/architectural/`; static workflow-shape tests; recorded-API-fixture unit tests for the skip-if-green helper; measurement via the PR's own CI plus dispatched router runs (C-011 evidence file)
**Target Platform**: GitHub-hosted `ubuntu-24.04` public runners (4 vCPU, 16 GB)
**Project Type**: single (CI infrastructure inside the existing repository)
**Performance Goals**: battery slowest leg median ≤ 14 min; fast gate ≤ 5 min from pipeline start; each consolidation shard p90 ≤ 15 min with the two shards within 25% of each other
**Constraints**: battery job timeouts ≤ 30 min; peak memory < 12 GB per battery leg; no new workflow file (17/20 ceiling); no local full `tests/architectural` run (C-009); router two-authority lockstep (C-003); battery non-required (C-004)
**Scale/Scope**: ~3,561 battery tests in 237 files; 21 module rows; ~17,000 tests overall; 7 workflows touched (`ci-router.yml`, `ci-modules.yml`, `module-tests.yml`, `packs.yml`, `ci-nightly.yml`, `ci-aggregate.yml`, `ci-charter-shard-recapture.yml`)
**Dependency changes**: none (DIRECTIVE_051 supply-chain controls: not triggered — no package added, upgraded or removed; GitHub actions already SHA-pinned are reused, no new third-party action)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Charter rule | Status | Evidence |
|---|---|---|
| Single canonical authority (DIRECTIVE_044) | PASS | One shard selector (D-01), partition in registry + gate model (D-02), uniqueness extends `_gate_coverage` / `test_same_tier_uniqueness` (D-14); C-010 |
| Architectural alignment (DIRECTIVE_001) | PASS | Router two-authority contract respected and amended by a new contract file (D-09, D-10); battery stays non-required (C-004) |
| ATDD-first (charter ATDD-First Discipline) | PASS (planned) | Every concern names its red-first test (research R1–R3 "ATDD red-first") |
| Architectural gate discipline (Standing Order #5) | PASS | Partition proof and uniqueness check carry positive controls (injected unassigned file; injected overlapping job); allowlist shrink-only, capped |
| Campsite cleaning first (Standing Order #2) | PASS (planned) | Opening tidy-first steps: extract the inline LPT heredoc to `scripts/ci/shard_select.py` behaviour-preserving; fix registry drift; fix capture marker drift |
| Mission tracer files (Standing Order #3) | PASS | Seeded on the coordination branch at specify |
| No full heavy suites in mission (NO_FULL_HEAVY_SUITES_IN_MISSION) | PASS | C-009; validation via PR CI and dispatched router runs |
| Decision documentation (DIRECTIVE_003) | PASS | 10 Decision Moments; ADR amendments + contract amendment (FR-014) |
| Red-main discipline (Standing Order #9) | PASS | No red test is skipped or green-washed; the nightly backstop makes an honest red visible |
| No version numbers in scope | PASS | None |
| Terminology canon | PASS | `test_no_legacy_terminology.py` green; "CI path routing" / "gate selection" named senses |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-runtime-stabilisation-01M3TZH6/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0 (decision log D-01…D-37 + delegate sections R1–R3)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1 (measurement + validation runbook)
├── contracts/
│   ├── router-two-authority-amendment.md
│   ├── battery-partition.md
│   └── green-match.md
├── checklists/requirements.md
├── decisions/           # Decision Moments
└── tasks.md             # /spec-kitty.tasks (not created here)
```

### Source Code (repository root)

```
.github/
├── workflows/
│   ├── ci-router.yml        # architectural-fast job, architectural-heavy 2-leg matrix, ci_config group, -n 4,
│   │                        #   router cli/status/consolidation/corpus jobs removed, green-match step
│   ├── ci-modules.yml       # green-match step in generate-matrix
│   ├── module-tests.yml     # inline LPT heredoc → scripts/ci/shard_select.py
│   ├── ci-charter-shard-recapture.yml # stale "latent selection mismatch" prose (campsite, D-33)
│   ├── packs.yml            # sole corpus owner (advisory), -n 4, select_gates-derived trigger, green-match step
│   ├── ci-nightly.yml       # architectural-backstop job
│   └── ci-aggregate.yml     # collect re-points to the matched run on skip-if-green
├── ci-module-registry.yml   # battery entry (fast roster + budgets, shard count, ci_config), consolidation shard_count 2
└── ci-shard-timings.json    # battery per-file timings, consolidation recapture
scripts/ci/
├── shard_select.py          # NEW: single shard selector (test + file granularity, loud mismatch)
├── green_match.py           # NEW: skip-if-green decision helper
├── corpus_select.py         # NEW (small): Packs corpus selection via gate_selection.select_gates
├── memory_sampler.py        # NEW: background peak-memory sampler (NFR-005)
├── battery_partition_plugin.py # NEW: pytest plugin applying --battery-part (fast | 1/2 | 2/2)
├── capture_shard_timings.py # marker alignment with consumers
└── gate_selection.py        # unchanged (derives from filter block)
tests/
├── architectural/
│   ├── _gate_coverage.py         # partition field, live per-PR tier keys
│   ├── _live_uniqueness.py       # NEW: FR-010 expansion + pairwise overlap (sibling of _gate_coverage)
│   ├── _ci_integrity_oracle.py   # MUST_RUN_ALWAYS_ON_GATES, HEAVY_BATTERY_NON_SRC_GROUPS
│   ├── test_same_tier_uniqueness.py        # live assertions restored
│   ├── test_no_duplicate_suite_execution.py
│   ├── test_interpreter_shard_coverage.py  # per-file cache
│   ├── test_clock_call_ban.py              # per-file cache
│   └── test_module_length_agreement.py     # consolidation leaves allowlist
└── ci/                           # test_shard_select.py, test_green_match.py, test_battery_partition.py, …
docs/adr/3.x/2026-09-23-1-*.md, 2026-09-26-1-*.md   # dated amendments
docs/development/testing/*.md, docs/development/**/ci-gate-mechanics.md
```

**Structure Decision**: single-project layout; all changes live in existing CI surfaces plus three
small new `scripts/ci/` helpers and one pytest plugin, each with focused tests.

## Implementation Concern Map

> Concerns are not work packages; `/spec-kitty.tasks` translates them. `ci-router.yml` is a hot
> file touched by several concerns — tasks must sequence those edits (one lane or explicit order)
> to avoid lane merge conflicts.

### IC-01 — Shared shard selector and visible mismatch

- **Purpose**: One shard selector for module rows and the battery, with a loud timing-length mismatch, extracted behaviour-preserving from the inline heredoc (campsite first).
- **Relevant requirements**: FR-005, FR-004 (enabler), FR-012 (enabler), C-010
- **Affected surfaces**: `.github/workflows/module-tests.yml` (heredoc :169-266), `scripts/ci/shard_select.py` (new), `tests/architectural/test_module_shard_registry.py` (`_lpt_bin_pack` reuse), `scripts/ci/capture_shard_timings.py` (marker drift)
- **Sequencing/depends-on**: none
- **Risks**: behaviour drift in module-row sharding — guard with a byte-identical selection test against current timings before switching.

### IC-02 — Battery partition: registry roster, plugin, gate-model proof

- **Purpose**: Registry-held fast roster with per-file budgets and battery shard count; a pytest plugin (`scripts/ci/battery_partition_plugin.py`) applying `--battery-part`; `_gate_coverage` partition field and the three-way partition proof with an injected-unassigned-file positive control.
- **Relevant requirements**: FR-003, FR-004, FR-013, C-010
- **Affected surfaces**: `.github/ci-module-registry.yml`, `.github/ci-shard-timings.json` (battery per-file timings), `scripts/ci/battery_partition_plugin.py`, `tests/architectural/_gate_coverage.py` (format-exclude + pinning inventory companions), `tests/architectural/test_module_shard_registry.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `_gate_coverage.py` whole-tree fallback flagging legs as duplicates; pinning-inventory line drift.

### IC-03 — Router battery jobs, workers and memory evidence

- **Purpose**: Always-on `architectural-fast` job; `architectural-heavy` as a 2-leg matrix; literal `-n 4` with worker evidence; memory sampler; router-gate / oracle / ledger companions.
- **Relevant requirements**: FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, NFR-005
- **Affected surfaces**: `.github/workflows/ci-router.yml`, `.github/workflows/packs.yml` (corpus `-n 4`), `tests/architectural/_ci_integrity_oracle.py`, `tests/ci/test_ci_module_wiring.py`, `test_dual_mode_contract.py`, `test_no_duplicate_suite_execution.py` (per-leg counting), worker-count guard test
- **Sequencing/depends-on**: IC-02; on `ci-router.yml` after IC-07 (D-30 order)
- **Risks**: SMT oversubscription on subprocess-heavy tests (watch `test_module_length_agreement` setup); hot file `ci-router.yml`.

### IC-04 — Nightly full-battery backstop

- **Purpose**: `architectural-backstop` job in `ci-nightly.yml` running the full base command, wired into `nightly-summary.needs` with escalation and fail-loud, so a green nightly means the full battery ran.
- **Relevant requirements**: FR-001, SC-003
- **Affected surfaces**: `.github/workflows/ci-nightly.yml`, `tests/ci/test_nightly_exit_code_honesty.py`, nightly escalation key, fork-guard tests
- **Sequencing/depends-on**: none (independent of the split by design); land first
- **Risks**: nightly timeout (40 min) vs full battery on 4 workers.

### IC-05 — `ci_config` path group and contract amendment

- **Purpose**: CI-config-only changes select the battery via a new non-src group; amendment recorded as a new contract file.
- **Relevant requirements**: FR-007, C-003, C-008
- **Affected surfaces**: `.github/workflows/ci-router.yml` (filter block, output fold, battery `if:`), `_ci_integrity_oracle.HEAVY_BATTERY_NON_SRC_GROUPS`, `tests/ci/test_ci_module_wiring.py` (`matched_groups`), golden-test `_BASE_CONTEXT_ALL_FALSE`, `contracts/router-two-authority-amendment.md`
- **Sequencing/depends-on**: none — this is the FIRST `ci-router.yml` edit (D-30), so every later mission commit runs the battery on PR CI (C-011 evidence); IC-06 → IC-07 → IC-03 → IC-09 follow it on the same file in one sequenced lane
- **Risks**: two-authority drift — `test_gate_selection_authority.py` must stay green without a `gate_selection.py` edit.

### IC-06 — Remove duplicate router module-path jobs

- **Purpose**: Delete router `tests (cli|status|consolidation)`; stress home recorded (nightly `stress` lane).
- **Relevant requirements**: FR-008
- **Affected surfaces**: `.github/workflows/ci-router.yml`, router-gate `needs`, `test_no_duplicate_suite_execution.py` ledger + stale check, tests asserting `tests-consolidation`
- **Sequencing/depends-on**: IC-05 (same file, D-30 order)
- **Risks**: branch-protection required-check names (stable required check is `router gate`; verify).

### IC-07 — Single advisory corpus lane, blocking home for the orphaned corpus tests

- **Purpose**: Packs owns corpus (advisory) with a `select_gates`-derived trigger, router `tests (corpus)` removed, dead coverage target fixed, the otherwise-orphaned corpus tests (40 at base bc826fcbcb) given a blocking-lane home and deselected from the corpus run.
- **Relevant requirements**: FR-009, C-001 (scoped exception)
- **Affected surfaces**: `.github/workflows/packs.yml`, `.github/workflows/ci-router.yml`, `scripts/ci/corpus_select.py` (new), `_DELIBERATELY_UNGATED_FILTER_GROUPS`, pack-manifest blocking job trigger, `tests/contract/test_example_round_trip.py` home
- **Sequencing/depends-on**: IC-06 (same file)
- **Risks**: Fleet Verdict reading a red advisory corpus run (job-level `continue-on-error`, out of `packs-gate.needs`).

### IC-08 — Live cross-job test-set uniqueness

- **Purpose**: Re-key `_gate_coverage` tiers to live per-PR jobs (OS-family tiers), restore live assertions in `test_same_tier_uniqueness.py`, one collect + per-job marker filtering, reasoned shrink-only allowlist (≤ 10).
- **Relevant requirements**: FR-010, NFR-004, SC-004
- **Affected surfaces**: `tests/architectural/_gate_coverage.py`, `tests/architectural/test_same_tier_uniqueness.py`, pinning inventory
- **Sequencing/depends-on**: IC-01, IC-02, IC-03 (lands after the router battery reshaping, D-30), IC-06, IC-07
- **Risks**: runtime ≤ ~55 s inside the battery; vacuity — positive control injects an overlapping job.

### IC-09 — Skip-if-green on ready-for-review

- **Purpose**: `scripts/ci/green_match.py` decides skip from a self-recorded tested key; selection jobs of router/modules/packs fold it in; Aggregate re-points to the matched run; ADR 2026-09-23-1 amendment.
- **Relevant requirements**: FR-011, SC-005
- **Affected surfaces**: `scripts/ci/green_match.py` (new), `.github/workflows/ci-router.yml`, `ci-modules.yml`, `packs.yml`, `ci-aggregate.yml`, `tests/ci/test_green_match.py` (15 negative cases, recorded fixtures)
- **Sequencing/depends-on**: IC-05, IC-06, IC-07 (same files) — last router edit
- **Risks**: Aggregate half only observable post-merge (follow-up); any lookup error must fall through to a normal run.

### IC-10 — Per-file caching of duplicated scans

- **Purpose**: Cache identical scans/collections once per file in `test_interpreter_shard_coverage.py` and `test_clock_call_ban.py`. In `test_no_dead_symbols.py`, merged PR #5503 already supplies the walk cache (`_real_tree_inputs`). This concern adds its file-end `cache_clear()` finalizer so no syntax tree outlives its file (D-37).
- **Relevant requirements**: FR-006, C-007
- **Affected surfaces**: the two test files + `tests/architectural/test_no_dead_symbols.py` (finalizer only)
- **Sequencing/depends-on**: none
- **Risks**: self-mutation tests silently reading the real tree — red-first tests prove the cache is bypassed.

### IC-11 — Consolidation module shard split

- **Purpose**: `shard_count: 2`, local timings recapture with aligned markers, leave the mismatch allowlist (`_BASELINE_ALLOWLIST_COUNT` 20 → 18; the allowlist already holds 19).
- **Relevant requirements**: FR-012, NFR-006
- **Affected surfaces**: `.github/ci-module-registry.yml`, `.github/ci-shard-timings.json`, `tests/architectural/test_module_length_agreement.py` (`_BASELINE_ALLOWLIST_COUNT` :151, 20 → 18)
- **Sequencing/depends-on**: IC-01 (capture marker fix)
- **Risks**: future consolidation test-count drift reds the scheduled strict check (follow-up under #5086).

### IC-12 — Decision records and documentation

- **Purpose**: Dated amendments on ADR 2026-09-23-1 and 2026-09-26-1 (guarded by a red-first static ADR-amendment test under `tests/docs/`), testing/CI docs, docs retrieval index, registry prose. The NFR evidence file is orchestrator-owned (D-35) and only cited by path.
- **Relevant requirements**: FR-013 (prose), FR-014; C-011 is cited, not delivered (orchestrator closeout)
- **Affected surfaces**: `docs/adr/3.x/2026-09-23-1-*.md`, `docs/adr/3.x/2026-09-26-1-*.md`, `docs/development/testing/testing-parallel.md`, `ci-gate-mechanics.md`, docs index, a new `tests/docs/` ADR-amendment test
- **Sequencing/depends-on**: all others (documents shipped behaviour). The base `bc826fcbcb` already carries #5503's docs edits (D-37).
- **Risks**: docs-freshness / terminology gates.

## Validation strategy

- Per concern: the red-first tests named in research.md and the WP prompts, the owning test files, `make test-fast`, and the SPECIFIC architectural gate files each change implicates (never the whole directory locally).
- Mission level: the PR's own CI (FR-007 makes CI-config edits select the battery) plus `workflow_dispatch` router runs in `pr` and `full` mode on the branch; run IDs, durations, worker counts and peak memory recorded in `evidence/ci-measurements.md` (C-011) against NFR-001…NFR-006.

## Post-plan squad folds

The post-plan brownfield squad (split-brain, canonical-source/foldable, undersizing) returned
FOLD-FIRST / LAND-PLAN with no blockers; its folds are recorded as research.md D-22…D-34 (tasks-phase and analyze
corrections D-35, D-36; post-rebase drift D-37; the full log is D-01…D-37) and govern task generation. In short:

- **IC-02 splits three ways**: plugin + registry entry (D-23, D-24, D-26); gate-model partition proof; and a battery timings seed + budget finalisation (D-36: seeded from the census battery logs' `--durations` medians plus a 0.12 s per-test floor, with provenance; the CI-dispatched junit capture of D-29 is the later refresh path, not the bootstrap).
- **IC-03 splits**: memory sampler as its own new-file unit (D-28); fast job + 2-leg matrix + `-n 4` + worker guard + junit upload.
- **IC-05 is the first router edit** (D-30); IC-06 → IC-07 (with the `tests (corpus-blocking)` router job, D-22) → IC-03 → IC-09 wiring follow in one sequenced lane over `ci-router.yml`.
- **IC-09 splits** helper (+ shared `bind_tested_base`, D-27) → Aggregate re-point → workflow wiring (D-30).
- **IC-04 stays off the registry** (D-26) and is judged on its own job conclusion while main's nightly is red (D-32). PR #5521 has merged with the escalation CLI unchanged (D-37).
- **IC-08** lives in `_live_uniqueness.py` (D-28), lands after the battery reshaping, red-first recorded on the merge-base (D-30).
- **Pinned files** (`_gate_coverage.py`, `_ci_integrity_oracle.py`, `test_no_duplicate_suite_execution.py`) are edited in sequence; the pinning inventory is regenerated, never hand-merged (D-25).
- **Campsite additions** (D-33) ride with the selector extraction and the docs work.
- Context citations (not folded): #4708, #5250, #5098, #4368, #1868 (D-34).
