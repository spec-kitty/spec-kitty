# Tasks: CI runtime stabilisation

**Mission**: `ci-runtime-stabilisation-01M3TZH6` · **Issue**: #5510 · **Branch**: `issue-5510-ci-runtime-stabilisation`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md) (Implementation Concern Map IC-01…IC-12 + post-plan folds), [research.md](research.md) (decision log D-01…D-37 — governs), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

Subtask completion is event-sourced: record it with `spec-kitty agent tasks mark-status Txxx --status done`. The rows below are references, not checkboxes.

## Global rules for every work package

- **ATDD red-first** (charter ATDD-First Discipline): the first commit of each WP adds the failing test(s) named in its prompt; implementation follows.
- **No local heavy suites** (C-009 / `NO_FULL_HEAVY_SUITES_IN_MISSION`): run `make test-fast`, the owned test files, and the SPECIFIC architectural gate files your change implicates — never `pytest tests/architectural` as a whole or `make test-full`.
- **Lane discipline**: in a lane worktree always use `uv run --frozen …`; never `git stash`.
- **Pinned-file companions (D-20, D-25)**: reformatting a file listed in `[tool.ruff.format].exclude` requires dropping it from the exclude in the same commit.
- **Pinning-inventory rule (stated once; prompts defer to it)**: `tests/release/pinning_rule_inventory.json` is regenerated (`scripts/ci/derive_pinning_inventory.py`, then `--check`) — never hand-merged; on a lane conflict, regenerate — **only** by:
  - the WPs that edit pinned files — lane-a **WP06** (`_gate_coverage.py`, its only WP owner); router lane **WP08, WP09, WP10, WP12** (`test_no_duplicate_suite_execution.py`) — as an out-of-map companion with a one-line rationale. **WP06 is the first** regenerator (the base inventory is fresh since main `e3794ded2d` closed #5523 — research D-37 — so any `--check` delta is the regenerating WP's own line shifts);
  - **WP19**, which does the final regeneration on the final tip;
  - the **post-consolidation orchestrator folds** (see Orchestrator closeout), which edit pinned files on the mission branch after lane consolidation and regenerate once more.
  **WP01, WP16, WP17 and every other WP (WP02, WP03, WP04, WP05, WP07, WP11, WP13, WP14, WP15, WP18) NEVER regenerate it**: they run `--check`/`--stdout`, confirm their diff adds no new delta, and record any delta in their Activity Log for WP19. (WP07 edits `_ci_integrity_oracle.py`, which carries no inventory rule; it runs `--check` only.)
- **Anchor by job name, not only line number** — research anchors match the current base, but every lane edit shifts them.
- **Pre-existing failures (charter Pre-existing Failure Reporting Rule — binding)**: a red you did not cause and that is also red on the planning base must, before you continue past it, have a GitHub issue — cite the existing one (e.g. nightly P0s #5418/#5505/#5506/#5507) or open one (command, failure summary, why it is pre-existing) — and be cited in the Activity Log. Never just "note it and move on".
- **Pinning inventory is green on the base**: `tests/release/test_pinning_inventory_fresh.py` / `derive_pinning_inventory.py --check` pass on `bc826fcbcb` (#5523 fixed by `e3794ded2d` and CLOSED; issue-matrix verdict verified-already-fixed — D-37). A `--check` delta on your tip is therefore yours: a non-regenerating WP records it for WP19; a regenerating WP folds it.
- Workflow file count is at 17/20 — add no new workflow file.

## Dependency graph and lanes (indicative; `finalize-tasks` computes lanes)

```
Selector/registry chain : WP01 → WP02 → WP03 → WP05
                                          WP05 → WP06 → WP14
Router chain            : WP07 → WP08 → WP09 → WP10 → WP12 → WP18
Battery reshaping joins : WP04, WP06, WP10, WP11, WP14 → WP12
Uniqueness              : WP06, WP12 → WP15
Skip-if-green           : WP16 → WP17 → WP18   (WP18 depends on WP12, WP17)
Independent day-one     : WP04, WP07, WP11, WP13, WP16
Docs (last)             : all → WP19
Post-consolidation folds: (orchestrator, mission branch, after lane consolidation) — see closeout
```

**Intended lanes** — lanes are connected components of `owned_files` overlap; cross-lane
dependencies are fine as long as the lane graph stays acyclic:

- **lane-a** (selector/registry): WP01, WP02, WP03, WP05, WP06, WP14. WP06 is the only WP
  that owns `_gate_coverage.py` and `test_battery_partition_proof.py` (it also provides the
  OS-family tier model WP15 consumes).
- **Router lane**: WP07, WP08, WP09, WP10, WP12, WP18 — shares `ci-router.yml` (and
  `test_no_duplicate_suite_execution.py` for WP08–WP12).
- **WP15 lane** (own lane): owns only `_live_uniqueness.py` and `test_same_tier_uniqueness.py`;
  depends on WP06 (lane-a) and WP12 (router lane). Nothing depends on WP15 except WP19.
- WP04, WP11, WP13, WP16, WP17, WP19 are placed by their own ownership.
- WP12 does **not** own the partition proof; WP15 does **not** own `_gate_coverage.py`,
  `test_battery_partition_proof.py` or `test_no_duplicate_suite_execution.py` (it imports
  `change_triggered` / `NON_CHANGE_TRIGGER_EVENTS` from it); WP18 does **not** own
  `test_no_duplicate_suite_execution.py`.
- Cross-lane cleanups (the partition proof's transitional branch; WP08's directory pre-check;
  the dead legacy prefix-tier helpers) are **post-consolidation orchestrator folds**, not WP
  work — see Orchestrator closeout.

---

## Phase 1 — Foundations (selector, campsite)

### WP01 — Campsite: extract the shard selector without behaviour change

**Goal**: Move the inline LPT selector heredoc out of `module-tests.yml` into `scripts/ci/shard_select.py` byte-for-byte equivalent in selection; make `test_module_shard_registry.py` reuse it; align `capture_shard_timings.py`'s marker with the consumers and fix the stale prose that described the drift. Tidy-first (Standing Order #2). **Priority**: P1. **Independent test**: identical shard assignment for every module row before/after on committed timings. **Prompt**: [tasks/WP01-campsite-extract-shard-selector.md](tasks/WP01-campsite-extract-shard-selector.md) (~424 lines)

T001 Red-first: characterization test pinning current module-row shard assignments from the inline heredoc for every registry row (WP01)
T002 Extract `scripts/ci/shard_select.py` (test-granularity mode, pure functions, CLI entry used by `module-tests.yml`) (WP01)
T003 Switch `module-tests.yml` to the script; reuse it from `test_module_shard_registry.py::_lpt_bin_pack` (WP01)
T004 Single marker-expression constant; `capture_shard_timings.py` imports it (`not performance and not stress`) (WP01)
T005 Fix stale "latent selection mismatch" prose in `recapture_charter_shard_timings.py` and `ci-charter-shard-recapture.yml` (WP01)

**Dependencies**: none. **Risks**: silent module-row reshuffle — T001 guards it.

### WP02 — Selector: loud mismatch, file granularity, single base enumeration

**Goal**: FR-005 (#5092 AC2) — a timing-length mismatch emits `::warning::` + a step-summary line; add a file-granularity mode (missing file → median weight, never uniform-for-all); add `enumerate_base_files(...)` as the single battery file enumeration (D-24). **Priority**: P1. **Prompt**: [tasks/WP02-selector-loud-mismatch-file-mode.md](tasks/WP02-selector-loud-mismatch-file-mode.md) (~343 lines)

T006 Red-first tests: mismatch warning + summary line; file mode balances with median weight; enumeration matches pytest collection for `tests/architectural` (WP02)
T007 Implement loud mismatch in test mode (module rows keep their assignment) (WP02)
T008 Implement file-granularity mode + `enumerate_base_files` (WP02)
T009 `test_module_length_agreement.py` imports the shared marker constant (WP02)

**Dependencies**: WP01.

### WP03 — Split the consolidation module shard

**Goal**: FR-012 — consolidation `shard_count: 2`, local recapture with aligned markers, leave `_MISMATCH_ALLOWLIST`, `_BASELINE_ALLOWLIST_COUNT` 20 → 18 (D-18, D-31). Copy the charter precedent commit `d460f55d91`. **Priority**: P3. **Prompt**: [tasks/WP03-split-consolidation-shard.md](tasks/WP03-split-consolidation-shard.md) (~348 lines)

T010 Red-first: strict length-agreement for consolidation fails (782 vs ~1617) + unconditional pin that the consolidation registry row has `shard_count >= 2` (the recapture alone must not green it) (WP03)
T011 Recapture consolidation timings locally via `capture_shard_timings.py --module consolidation` (single module, not a heavy suite) (WP03)
T012 Registry `shard_count: 2`; remove consolidation from `_MISMATCH_ALLOWLIST`; baseline 20 → 18 (WP03)
T013 Verify balanced split prediction (~394 s/shard) and record it for the evidence file (WP03)

**Dependencies**: WP02.

## Phase 2 — Honest safety net

### WP04 — Nightly full-battery backstop

**Goal**: FR-001 — `architectural-backstop` job in `ci-nightly.yml` running the full base battery command (no partition plugin), `-n 4`, 40-min timeout, escalation + terminal fail-loud, in `nightly-summary.needs`; stays off the registry (D-26); PR #5521 (nightly escalation triage rewrite) has merged with the CLI unchanged — the new `--suite-key architectural` step needs no new flag (D-32, D-37). **Priority**: P1. **Prompt**: [tasks/WP04-nightly-full-battery-backstop.md](tasks/WP04-nightly-full-battery-backstop.md) (~442 lines)

T014 Red-first: nightly test asserting a job whose architectural selection equals the per-PR base (no `fast or unit` filter) and is in `nightly-summary.needs` (WP04)
T015 Add the `architectural-backstop` job (pattern: `integration-next`), fork guard, escalation key (WP04)
T016 Wire into `nightly-summary.needs` and exit-code honesty tests (WP04)
T017 Verify the release nightly gate reads the overall nightly conclusion (no extra wiring) and document it in the job comment (WP04)

**Dependencies**: none. **FR-001 is jointly evidenced**: WP04 proves command parity (backstop selection == per-PR base); WP06's partition proof proves fast ∪ S1 ∪ S2 = base.

## Phase 3 — Battery partition

### WP05 — Battery partition plugin and registry battery entry

**Goal**: FR-003/FR-004/FR-013 — `scripts/ci/battery_partition_plugin.py` (`--battery-part fast|1/2|2/2`), parts computed in EVERY process (D-23), runtime self-check; registry `special_tiers.architectural` rewritten to hold only facts with no other home (D-26: workers, base, fast roster with budgets, shard count, timings key); `capture_shard_timings.py --suite architectural --from-junit` mode. **Priority**: P1. **Prompt**: [tasks/WP05-battery-partition-plugin-and-registry.md](tasks/WP05-battery-partition-plugin-and-registry.md) (~505 lines)

T018 Red-first: subprocess tests — each part collects only its files at `-n 0` and `-n 2`; executed-file-outside-part self-check fails; FR-005 production path (a file with no timing → the plugin itself emits `::warning title=shard timings::` once and the step-summary line). Its junit oracle reuses T022's `junit_file_seconds`, which must land first (WP05)
T019 Implement the plugin (pure helpers ≤ 15 complexity; uses `shard_select.enumerate_base_files`); whole-file `--ignore=<file>` ≡ `--deselect <file>` vs the registry base; worker-count check skipped under `--collect-only` (WP05)
T020 Registry `special_tiers.architectural` schema + fast roster (33 entries: R1 §4b rows 1-32 + row 34 `test_dead_symbol_allowlist_loader.py` (D-37); budgets, reasons; roster row 33 — the partition proof — is added by WP14) (WP05)
T021 Registry pin tests in `test_module_shard_registry.py` (drift fixed: no `always_on: true`) (WP05)
T022 `capture_shard_timings.py --suite architectural --from-junit` + tests (WP05)

**Dependencies**: WP03 (registry chain), WP02.

### WP06 — Gate-model partition field and three-way proof

**Goal**: FR-004 — `_gate_coverage` gains a partition field evaluating literal `--battery-part` commands; a static test proves fast ∪ S1 ∪ S2 = base, pairwise disjoint, with an injected-unassigned-file positive control. **Priority**: P1. **Prompt**: [tasks/WP06-gate-model-partition-proof.md](tasks/WP06-gate-model-partition-proof.md) (~445 lines)

T023 Red-first: partition-proof test with positive control (injected unassigned file fails); the "one unpartitioned battery gate" shape branch is transitional — a post-consolidation orchestrator fold (tasks.md closeout) deletes it once WP12 has partitioned the router (WP06)
T024 `_gate_coverage.Gate` partition field + `battery_parts` via the shared selector; test that `collect_job_nodeids` on a partitioned gate returns the part's node ids (no UsageError / exit 4); OS-family tier model for WP15 (D-14, moved from WP15 T061): `Gate.runs_on` (not in equality), `_splice_local_uses` carries the delegate's `runs-on` when the caller has none, `os_family` / `gate_os_tier` / `os_tier_shard_counts` replacing the dead `fast-tests`/`integration-tests` prefix tiers (legacy helpers left for the closeout fold), unit tests in new `test_gate_os_tier.py` (WP06)
T025 Format-exclude companion and pinning-inventory regeneration (WP06)
T026 Prove the plugin's enumeration equals the model's (D-24 equality test) (WP06)

**Dependencies**: WP05. Sole WP owner of `_gate_coverage.py` and `test_battery_partition_proof.py` (lane-a). Does **not** edit `.github/ci-module-registry.yml` (WP14 adds the proof to the fast roster). Co-owns `scripts/ci/battery_partition_plugin.py` only to export an existing loader / pure keep-decision helper (behaviour-preserving) — this shared ownership also keeps WP05 → WP06 → WP14 → WP12 in one execution lane.

### WP14 — Battery per-file timings seed and fast-roster budgets

**Goal**: FR-004/NFR-001/NFR-002 — seed `.github/ci-shard-timings.json` battery per-file durations from the census battery logs' `--durations` sections (realistic production data; no local heavy run), with provenance (D-36: per-file median of summed ≥ 1 s phases + 0.12 s × collected tests); finalise roster budgets; add fast-roster row 33 (`tests/architectural/test_battery_partition_proof.py`, created by WP06; budget 10 s + reason) — WP14 owns the registry after WP05; predicted leg balance recorded. Later refresh comes from junit via WP05's capture mode (D-29 is the refresh path, D-36). **Priority**: P1. **Prompt**: [tasks/WP14-battery-timings-seed-and-budgets.md](tasks/WP14-battery-timings-seed-and-budgets.md) (~396 lines)

T027 Red-first: static budget check fails without battery timings (roster Σ and per-file budgets vs committed timings) (WP14)
T028 Derive per-file medians from the 68 census logs (`<session-scratchpad>/ci-research/battery/logs/`) and write the `architectural` timings key with provenance (WP14)
T029 Finalise roster budgets; add roster row 33 (the partition proof, budget 10 s + reason); record predicted S1/S2 loads (WP14)

**Dependencies**: WP05, WP06 (WP06 creates the partition-proof file that WP14 adds to the fast roster; WP06 does not touch the registry).

## Phase 4 — CI path routing and duplicate removal (router chain)

### WP07 — `ci_config` path group selects the battery

**Goal**: FR-007 — new non-src `ci_config` filter group gating only the battery (first router edit, D-30); `HEAVY_BATTERY_NON_SRC_GROUPS = {architectural, ci_config}`; `ci` group untouched; `gate_selection.py` unchanged. **Priority**: P1. **Prompt**: [tasks/WP07-ci-config-path-group.md](tasks/WP07-ci-config-path-group.md) (~285 lines)

T030 Red-first: gate selection for a workflow-only / `pyproject.toml`-only diff selects `architectural-heavy`; prose-only still does not (WP07)
T031 Add the group to the filter block, output fold and battery `if:` in `ci-router.yml` (WP07)
T032 Oracle constant + `tests/ci/test_ci_module_wiring.py` `matched_groups` + golden `_BASE_CONTEXT_ALL_FALSE` (WP07)
T033 Confirm `test_gate_selection_authority.py`, `test_ci_quality_path_filters.py` and the `ci`-group pin pass unchanged (WP07)

**Dependencies**: none.

### WP08 — Remove the duplicate router module-path jobs

**Goal**: FR-008 — delete router `tests (cli)`, `tests (status)`, `tests (consolidation)`; router-gate `needs` and ledger rows; repoint tests asserting `tests-consolidation`; the 2 stress tests are homed by the nightly `stress` lane (verify). **Priority**: P2. **Prompt**: [tasks/WP08-remove-router-module-path-jobs.md](tasks/WP08-remove-router-module-path-jobs.md) (~257 lines)

T034 Red-first: ledger / dual-mode tests asserting the three jobs are absent, plus a deliberate directory-level structural pre-check in `test_no_duplicate_suite_execution.py` that WP15's live check subsumes and a post-consolidation orchestrator fold (tasks.md closeout) removes (WP08)
T035 Delete the jobs, `needs` entries, ledger rows; fix stale `tests-cli` prose (`test_ci_collection_completeness.py`, `scripts/verify_shard_3115.sh`) (WP08)
T036 Repoint tests that asserted `tests-consolidation`; update `test_local_gate_parity.py` (WP08)
T037 Verify the 2 stress tests are collected by the nightly stress lane; record it (WP08)

**Dependencies**: WP07.

### WP09 — Packs is the sole (advisory) corpus owner

**Goal**: FR-009 — `scripts/ci/corpus_select.py` (corpus via `gate_selection.select_gates`); Packs corpus trigger ⊇ router corpus trigger; job-level `continue-on-error`, out of `packs-gate.needs`; `--cov=charter.offering`; `-n 4`; router `tests (corpus)` deleted; pack-manifest test deselected from corpus with its blocking job's trigger widened. **Priority**: P2. **Prompt**: [tasks/WP09-packs-sole-corpus-owner.md](tasks/WP09-packs-sole-corpus-owner.md) (~279 lines)

T038 Red-first: superset test (every changed-path set that selected router corpus selects Packs corpus) + `corpus_select` unit tests (WP09)
T039 Implement `corpus_select.py` and wire Packs `changes` (pre-sync pattern as in `ci-modules.yml`) (WP09)
T040 Packs corpus job: advisory (`continue-on-error`, out of `packs-gate.needs`), `-n 4`, coverage target fixed (WP09)
T041 Delete router `tests (corpus)` + needs/ledger rows; update `test_workflow_coherence.py`, `test_ci_corpus_trigger_completeness.py` (WP09)
T042 Pack-manifest test: deselect from corpus, widen its blocking job trigger (WP09)

**Dependencies**: WP08.

### WP10 — Blocking home for the orphaned corpus tests

**Goal**: D-13/D-22 — router `tests (corpus-blocking)` job gated on the `corpus` group running exactly the orphaned node ids — 40 on base `bc826fcbcb` (35 at planning; #5503 added five round-trip tests, D-37; whole-file marker selection would be 403); Packs deselects them; `corpus` stays a gated group; ledger + `router-gate.needs`. **Priority**: P2. **Prompt**: [tasks/WP10-corpus-blocking-home.md](tasks/WP10-corpus-blocking-home.md) (~261 lines)

T043 Red-first: the orphaned corpus node-ids (40 post-rebase) are selected by exactly one required job and no advisory job (WP10)
T044 Add the router job, `needs` entry, ledger row (WP10)
T045 Packs deselects exactly those node ids; verify the count (40 post-rebase, D-37) by collect-only (WP10)

**Dependencies**: WP09.

## Phase 5 — Battery reshaping

### WP11 — Memory sampler

**Goal**: NFR-005 — `scripts/ci/memory_sampler.py`: background `/proc/meminfo` (MemTotal−MemAvailable) sampling with cgroup `memory.peak` secondary; start/stop CLI; prints a parseable peak line. **Priority**: P2. **Prompt**: [tasks/WP11-memory-sampler.md](tasks/WP11-memory-sampler.md) (~353 lines)

T046 Red-first unit tests with fake `/proc/meminfo` and cgroup files (WP11)
T047 Implement the sampler (stdlib only; runs before `uv sync`) (WP11)
T048 Output contract (`peak_rss_bytes=… source=…`) documented in the module docstring (WP11)

**Dependencies**: none.

### WP12 — Router battery reshaping: fast job, 2-leg matrix, four workers

**Goal**: FR-002/FR-003/FR-004 — always-on `architectural-fast` (roster), `architectural-heavy` as a 2-leg `include:` matrix (`fail-fast: false`), literal `-n 4` with `-q` dropped (worker evidence), junit upload, memory sampler wired, timeouts ≤ 30; oracle/ledger/dual-mode companions (per-leg counting); static worker-policy guard across the 4 workflows. **Priority**: P1. **Prompt**: [tasks/WP12-router-battery-reshaping.md](tasks/WP12-router-battery-reshaping.md) (~659 lines)

T049 Red-first: worker-policy guard (`-n 4` literal for battery legs, fast job, backstop, Packs corpus; fails on `-n auto`) (WP12)
T050 Red-first: router shape tests — fast job always-on, heavy matrix legs `1/2`,`2/2`, router-gate needs; registry ↔ router: `fast_gate.job == "architectural-fast"`, `shard_count == len(include)`, `workers ==` literal `-n` (WP12)
T051 `architectural-fast` job + `MUST_RUN_ALWAYS_ON_GATES` + ledger row (WP12)
T052 `architectural-heavy` 2-leg matrix; `HEAVY_BATTERY_GATE` model kept; deselects unchanged; per-leg duplicate-suite counting; the partition proof is not edited here — a post-consolidation orchestrator fold (tasks.md closeout) removes its transitional branch (WP12)
T053 Wire memory sampler + junit upload + timeouts ≤ 30 on fast and legs (WP12)
T054 Companion tests: `test_dual_mode_contract.py`, `tests/ci/test_ci_module_wiring.py`, `test_gate_selection_authority.py`; regenerate pinning inventory (WP12)

**Dependencies**: WP04, WP06, WP10, WP11, WP14. Router lane; does **not** own `test_battery_partition_proof.py` (its transitional branch is removed by a post-consolidation orchestrator fold, tasks.md closeout). The registry ↔ router equalities (T050) live in `tests/ci/test_ci_module_wiring.py`.

### WP13 — Per-file caching of duplicated scans

**Goal**: FR-006 — per-file cached pure function keyed on (resolved root, selection inputs) returning immutable findings, cleared at file end, in `test_interpreter_shard_coverage.py` and `test_clock_call_ban.py`; mutation/self-mutation tests call the uncached primitive. Dead-symbol file: PR #5503 (merged) supplies the `_real_tree_inputs` `functools.lru_cache(maxsize=1)` walk cache at `test_no_dead_symbols.py:1166`. That cache has process lifetime and holds the trees and source for all of `src/`. WP13 owns `test_no_dead_symbols.py` and adds the module-scoped autouse `cache_clear()` finalizer with a red-first test, so no syntax tree outlives its file (FR-006, R3 §2.2). Accepted cost: M11 loses its cross-file cache hit, ~30 s on that worker. `test_refresh_dead_symbol_hashes.py` was deleted by #5503 (C-007, D-37). **Priority**: P3. **Prompt**: [tasks/WP13-per-file-scan-caching.md](tasks/WP13-per-file-scan-caching.md) (~478 lines)

T055 Red-first: cache-bypass tests (self-mutation scans see their own tmp tree; cache hit count == 1 for duplicate requests) + production path: both REAL consumer pairs driven through a counting fake of the uncached primitive, one call per distinct key + `test_real_tree_inputs_cleared_at_file_end` (dead-symbol finalizer registered with module scope; clears via a stub) (WP13)
T056 Cache in `test_interpreter_shard_coverage.py` (`collect_job_nodeids` duplicates) (WP13)
T057 Cache in `test_clock_call_ban.py` (duplicate scan pair) (WP13)
T058 Dead-symbol file-end finalizer (`_clear_real_tree_inputs` → `_real_tree_inputs.cache_clear()`), verify every `_real_tree_inputs()` consumer; measure before/after per-file durations (single-file runs); record the dead-symbol disposition (WP13)

**Dependencies**: none.

## Phase 6 — Duplicate-selection guard

### WP15 — Live cross-job test-set uniqueness

**Goal**: FR-010/NFR-004 — new `tests/architectural/_live_uniqueness.py` (one collect-only + per-job marker filtering; module rows and battery legs expanded via the shared selector; OS-family tiers); restore live assertions in `test_same_tier_uniqueness.py` with a reasoned shrink-only allowlist (≤ 10, expected 4); import `change_triggered`/`NON_CHANGE_TRIGGER_EVENTS` from `test_no_duplicate_suite_execution.py` (not moved; WP15 does not own that file); consume WP06's OS-family tiers (WP15 edits neither `_gate_coverage.py` nor the partition proof); runtime ≤ ~55 s. **Priority**: P2. **Prompt**: [tasks/WP15-live-cross-job-uniqueness.md](tasks/WP15-live-cross-job-uniqueness.md) (~314 lines)

T059 Red-first on the merge-base: the restored live check fails on main's workflows (router cli/status/consolidation/corpus overlaps); archive `.github` whole (splicing reads `.github/actions`); record the red (WP15)
T060 `_live_uniqueness.py`: collection, per-job filter, expansion, pairwise overlap (WP15)
T061 Consume WP06's OS-family tiers (`gate_os_tier` / `os_tier_shard_counts`, provided by WP06 T024 incl. the delegate `runs-on` splice); re-target the synthetic same-tier tests off the legacy prefix helpers; interpreter-split test (D-14) (WP15)
T062 Restore live assertions + allowlist (reasoned, shrink-only, cap 10) + positive controls (injected overlapping job; retired router duplicate shape); the partition proof's transitional branch and WP08's T034 directory guard are left for the post-consolidation orchestrator folds (tasks.md closeout) (WP15)
T063 Import (not move) the `change_triggered` helpers from `test_no_duplicate_suite_execution.py`; pinning inventory `--check` only (WP15 edits no pinned file); runtime measurement (WP15)

**Dependencies**: WP06, WP12. Own lane; owns only `_live_uniqueness.py` and `test_same_tier_uniqueness.py`.

## Phase 7 — Skip-if-green on ready-for-review

### WP16 — `green_match` helper and shared base binding

**Goal**: FR-011 — `scripts/ci/green_match.py` (pure `decide`, thin REST edge, stdlib only, runs before `uv sync`); one pure `bind_tested_base(parents, head)` extracted from `aggregate_source.py` into `green_match.py` (D-35) and reused by `aggregate_source.py`; 15 negative cases over recorded API fixtures. **Priority**: P2. **Prompt**: [tasks/WP16-green-match-helper.md](tasks/WP16-green-match-helper.md) (~532 lines)

T064 Red-first: parametrised `decide` table (all contract rows incl. 15 negatives) (WP16)
T065 Implement `decide`, tested-key binding via commits API, artifact-name matching (WP16)
T066 Extract `bind_tested_base` / `merge_reference` into `scripts/ci/green_match.py` (D-35); `aggregate_source.py` imports and reuses them (behaviour-preserving; existing tests green) (WP16)
T067 `effective-source` subcommand (used by WP17) with fixtures (WP16)
T068 Workflow-script import guard + mypy/ruff clean (WP16)

**Dependencies**: none.

### WP17 — CI Aggregate re-points to the matched run

**Goal**: FR-011 — `ci-aggregate.yml` `collect` gets a first `effective-source` step; every source-run reference re-points to its outputs; step and env names preserved; `run-name` unchanged; mismatch fails `collect`. **Priority**: P2. **Prompt**: [tasks/WP17-aggregate-repoint.md](tasks/WP17-aggregate-repoint.md) (~409 lines)

T069 Red-first: `test_aggregate_attempts.py`-style test executing the step bodies with a green-match marker fixture (WP17)
T070 Add the step; re-point the env blocks and `run-id:` inputs (WP17)
T071 Mismatch → fail with "re-run CI Modules to execute"; no empty-selection green; `test_coverage_artefact_contract.py` updated (WP17)

**Dependencies**: WP16.

### WP18 — Wire skip-if-green into router, modules and packs

**Goal**: FR-011/SC-005 — a first step in router `changes`, packs `changes`, ci-modules `generate-matrix` runs the helper (`actions: read`); on skip the path-filter step is skipped; executing runs upload the tested-key artifact, skip runs the marker; no job `if:`/`needs:` changes. **Priority**: P2. **Prompt**: [tasks/WP18-wire-skip-if-green.md](tasks/WP18-wire-skip-if-green.md) (~509 lines)

T072 Red-first: workflow-shape tests (helper step first; filter step conditional; artifacts uploaded; permissions) + skip-context golden test via the existing `_eval_gh_if` / `_GhIfEvaluator` (every path-gated job's `if:` is false when selection outputs are empty; D-35 `prose_only` residual pinned exactly) (WP18)
T073 Router `changes` wiring (WP18)
T074 Packs `changes` wiring (WP18)
T075 CI Modules `generate-matrix` wiring (WP18)
T076 Golden lane / fork-guard / router-gate tests stay green (`test_no_duplicate_suite_execution.py` run, not edited); record a follow-up for live Aggregate verification post-merge (WP18)

**Dependencies**: WP12, WP17. Router lane.

## Phase 8 — Documentation and decision records

### WP19 — ADR amendments, contract reference, docs, inventories

**Goal**: FR-013 (prose)/FR-014 — dated `## Amendment (2026-10-…)` on ADR 2026-09-26-1 (nightly backstop, sharded battery, worker policy; correct "green nightly means the full suite ran") and ADR 2026-09-23-1 (skip-if-green); testing/CI docs (`testing-parallel.md`, `ci-gate-mechanics.md`, `known-friction-points.md`, `pr-landing.md` stale names), `tests/release/coverage_breadth_evidence.md`; docs retrieval index regen; final pinning-inventory regeneration; terminology + docs-freshness checks; a red-first static test `tests/docs/test_ci_runtime_adr_amendments.py` (collected by the router `tests (docs)` job) pins both dated amendments and their contract links. **Priority**: P3. **Prompt**: [tasks/WP19-docs-and-decision-records.md](tasks/WP19-docs-and-decision-records.md) (~565 lines)

T077 Red-first: static test `tests/docs/test_ci_runtime_adr_amendments.py` asserting both dated `## Amendment` sections and their `contracts/` links (red today); then ADR 2026-09-26-1 amendment (WP19)
T078 ADR 2026-09-23-1 amendment (WP19)
T079 Testing/CI docs updates with `updated:` bumps; stale job names (WP19)
T080 Docs retrieval index regeneration; docs-freshness + terminology checks (WP19)
T081 Final `pinning_rule_inventory.json` regeneration and `coverage_breadth_evidence.md` (WP19)
T082 Verify and evidence #4351 and #4729 (verified-already-fixed): `tests/unit/status/test_mission_status_aggregate.py` is collected by a CI job (registry `unit` row); nightly `integration-next` is wired (commit `1e290b09ae`); evidence pointers in the WP19 Activity Log for the issue-matrix verdicts (WP19)

**Dependencies**: WP01–WP18.

---

## Orchestrator closeout (not a work package)

- **C-011 evidence file**: `kitty-specs/ci-runtime-stabilisation-01M3TZH6/evidence/ci-measurements.md`, written by the **orchestrator** after the mission PR's own CI runs and the dispatched router runs (`mode=pr` and `mode=full`) and the nightly backstop dispatch. It records **≥ 3 run IDs per NFR-001…NFR-006 (for NFR-006 dispatch `ci-modules.yml -f mode=full` ×3 or use three nightly `full-module-matrix` runs) and for SC-001 / SC-002** (SC-001 = pipeline start → conclusion of the last battery job; SC-002 = pipeline start → fast gate job conclusion), each with the measured value against its target, plus any operator waiver for an NFR-003 slowest-test breach (inputs: the measurements WP03, WP04, WP12, WP13 and WP15 put in their Activity Logs; WP12 carries SC-001/SC-002 in its `requirement_refs`).
- No work package writes this file (it lives under `kitty-specs/`, D-35); WP19's ADR amendments only cite it by path.
- **Post-consolidation orchestrator folds** — applied by the orchestrator on the mission branch
  (`issue-5510-ci-runtime-stabilisation`) **after lane consolidation and before the mission PR**,
  as one commit per fold, each red-first where it adds a control. They exist because each cleanup
  spans two lanes (removing it inside a WP would join lanes and create a lane-dependency cycle):
  - **(a) Partition proof — delete the transitional branch.** In
    `tests/architectural/test_battery_partition_proof.py` (WP06) delete the shape branch WP06
    marked `# TRANSITIONAL …` that tolerates "exactly one unpartitioned battery gate" (and its
    control pinning the tolerance, if any), so the rule is "every gate partitioned, partitions ==
    `{fast} ∪ {i/n}`"; add `test_lone_unpartitioned_battery_gate_is_reported` (fixture workflow
    with one unpartitioned battery job → a shape message, via the same `partition_violations`).
    Precondition: WP12's partitioned router is on the branch; the live proof stays green over the
    three partitioned gates; no collection added (10 s fast-roster budget).
  - **(b) Remove WP08's temporary directory-overlap pre-check** from
    `tests/architectural/test_no_duplicate_suite_execution.py` (the self-contained T034 block:
    `module_owned_test_dirs`, `router_dirs_owned_by_a_module`,
    `test_router_runs_no_module_owned_test_tree`, `test_router_module_tree_guard_flags_a_planted_job`).
    Precondition: WP15's live check, incl. its node-level twin
    `test_retired_router_duplicate_shape_is_reported`, is on the branch and green — if not, do not
    remove (never leave FR-008 unguarded). Keep the per-change classifier (`change_triggered`,
    `NON_CHANGE_TRIGGER_EVENTS`, …) — `_live_uniqueness.py` imports it.
  - **(c) Delete the dead legacy prefix-tier helpers** in `tests/architectural/_gate_coverage.py`
    (`_FAST_TIER_PREFIX`, `_INTEGRATION_TIER_PREFIX`, `_gate_tier`, `shard_counts_for_test`,
    `same_tier_shard_counts`), left in place by WP06 because their only consumer
    (`test_same_tier_uniqueness.py`) lived in WP15's lane. Precondition: `rg` shows no remaining
    consumer after WP15 re-targeted its tests onto `gate_os_tier` / `os_tier_shard_counts`.
  - Folds (b) and (c) edit pinned files: regenerate `tests/release/pinning_rule_inventory.json`
    (`scripts/ci/derive_pinning_inventory.py`, then `--check`, `tests/release/test_pinning_inventory_fresh.py`).
    Run `test_battery_partition_proof.py`, `test_no_duplicate_suite_execution.py`,
    `test_same_tier_uniqueness.py`, `test_gate_os_tier.py`, `test_marker_job_completeness.py`
    and `test_ruff_format_exclude_ratchet.py` (specific files, C-009), and record them in the PR's
    *Tests run*.

---

## Subtask index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001–T005 | Selector extraction (campsite) | WP01 | |
| T006–T009 | Loud mismatch, file mode, enumeration | WP02 | |
| T010–T013 | Consolidation split | WP03 | |
| T014–T017 | Nightly backstop | WP04 | [P] |
| T018–T022 | Partition plugin + registry | WP05 | |
| T023–T026 | Partition proof | WP06 | |
| T027–T029 | Battery timings seed + budgets | WP14 | |
| T030–T033 | `ci_config` group | WP07 | [P] |
| T034–T037 | Remove router module-path jobs | WP08 | |
| T038–T042 | Packs corpus owner | WP09 | |
| T043–T045 | Corpus-blocking home | WP10 | |
| T046–T048 | Memory sampler | WP11 | [P] |
| T049–T054 | Router battery reshaping | WP12 | |
| T055–T058 | Per-file scan caching | WP13 | [P] |
| T059–T063 | Live uniqueness | WP15 | |
| T064–T068 | `green_match` helper | WP16 | [P] |
| T069–T071 | Aggregate re-point | WP17 | |
| T072–T076 | Skip-if-green wiring | WP18 | |
| T077–T082 | ADR-amendment red-first test; docs and decision records; #4351/#4729 evidence | WP19 | |

**MVP**: WP04 (honest nightly) + WP07 (CI-config CI path routing) are independently valuable on day one; the battery speed-up lands with WP12.
