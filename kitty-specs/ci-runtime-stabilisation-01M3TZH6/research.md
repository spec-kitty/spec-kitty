# Research: CI runtime stabilisation

Phase 0 research for `ci-runtime-stabilisation-01M3TZH6` (issue #5510). Three profile-loaded
architect-alphonso research delegates mapped each requirement group to files, same-commit pins
and red-first tests (R1 battery structure, R2 CI path routing and duplicate removal, R3
skip-if-green / caching / consolidation / decision records). The orchestrator adjudicated their
divergences and recorded operator decisions; that consolidated log comes first and governs
where it differs from a delegate section below.

Evidence base: the 24-hour CI census (2026-09-30T05:06Z → 2026-10-01T05:06Z) and the pre-spec
squad; raw census data was kept in the session scratchpad and is summarised in spec.md Context.

## Consolidated decision log

| # | Decision | Rationale | Alternatives rejected | Source |
|---|----------|-----------|----------------------|--------|
| D-01 | `scripts/ci/shard_select.py` is the single shard selector (test-granularity for module rows, file-granularity for the battery); the inline heredoc in `module-tests.yml` and the copy in `test_module_shard_registry.py` reuse it | C-010 single authority; FR-005 fixed once | Second selector for the battery | R1 D-SEL |
| D-02 | Battery split applied by a pytest plugin reading a literal `--battery-part fast\|1/2\|2/2` flag; `_gate_coverage` gains a partition field so the three-way proof is static | FR-004 partition evaluable by the gate model; FR-010 depends on it | `--ignore` lists in YAML; per-job path lists | R1 D-PLUG |
| D-03 | New always-on `architectural-fast` router job; `architectural-heavy` stays one job key as a 2-leg `include:` matrix (`fail-fast: false`) | Keeps `HEAVY_BATTERY_GATE` / `selected_code_shards == {"architectural-heavy"}` pins; fast job follows terminology/layer-rules/archive-freeze pattern | Two named heavy jobs (breaks single-constant oracle model) | R1 D-JOB; operator DM 01M3V1FAQV07WJF3RYAFN9J7GC (always-on) |
| D-04 | Nightly `architectural-backstop` job in `ci-nightly.yml` runs the plain base command (no partition plugin), wired into `nightly-summary.needs` with escalation + terminal fail-loud, 40-min timeout | FR-001 independent of the split it backstops; release gate reads nightly overall result | Router schedule (conflicts with byte-pinned concurrency and `inputs.mode`) | R1 §2, pre-spec architect |
| D-05 | Literal `-n 4` (CI only) in battery legs, fast job, backstop and Packs corpus; `-q` dropped so xdist prints `created: 4/4 workers`; static guard test | FR-002 evidence + regression guard; Makefile untouched (C-005) | `-n logical` (32 workers on dev boxes) | R1 §3, pre-spec risk lens |
| D-06 | Fast roster: 32 deterministic ratchet/census files + the partition test (~260 worker-s; + the #5503 allowlist-loader schema gate as row 34, ≈ 266 — D-37), budgets in the registry checked statically against committed timings | NFR-002 ≤ 5 min with margin; no flaky runtime assertion | Runtime budget assertion | R1 §4b |
| D-07 | Memory sampler: background `/proc/meminfo` (MemTotal−MemAvailable) sampling, cgroup `memory.peak` secondary | NFR-005 needs whole-job peak; `/usr/bin/time -v` reports one worker only | `/usr/bin/time -v` | R1 §6 |
| D-08 | Per-test timeout authority stays `pytest.ini timeout=240` (#3143); watch `test_module_length_agreement` setup under 4 workers | Single timeout authority | Per-test markers | R1 §7 |
| D-09 | New non-src `ci_config` filter group (workflows, `.github/actions/**`, `scripts/ci/**`, `pytest.ini`, `pyproject.toml`, `Makefile`, module registry, shard timings) gating only the battery; `HEAVY_BATTERY_NON_SRC_GROUPS = {"architectural","ci_config"}`; `gate_selection.py` unchanged (derives from the filter block); `uv.lock` / `tests/conftest.py` excluded | FR-007; #4386 `ci` group ruling untouched | Widening `ci` group (breaks registry scrub mirror) | R2 FR-007; operator DM 01M3V02DWR56AAPTF06J46YXH0 |
| D-10 | Router-two-authority contract amendment is a NEW file in this mission's `contracts/` (kitty-specs/ is byte-frozen by `test_archive_root_byte_identical.py`); the frozen contract is not edited | Archive freeze | Appending to the frozen contract (R3 proposal — rejected after checking the freeze gate) | R2 vs R3, orchestrator adjudication |
| D-11 | Delete router `tests (cli|status|consolidation)` + router-gate needs + ledger rows; the 2 stress tests they alone ran are homed by the existing nightly `stress` lane; the 7 performance tests were already skipped there and run in nightly `performance` | FR-008 | Keeping them as fast signal | R2 FR-008 |
| D-12 | Packs owns corpus: Packs `changes` computes `corpus` via `gate_selection.select_gates` (covers unmatched-src fan-out, `kitty-specs`/`.kittify` leaves, `packs/internal/**`); corpus job `continue-on-error`, out of `packs-gate.needs`; `--cov=charter.offering`; router `tests (corpus)` deleted; `corpus` joins `_DELIBERATELY_UNGATED_FILTER_GROUPS`; pack-manifest test deselected from corpus with its blocking job's trigger widened | FR-009, operator DM 01M3V027T8WF0CR3D1B8VY2VZ0 | Copying globs into packs.yml | R2 FR-009 |
| D-13 | The 35 corpus tests with no other blocking per-PR home (29 in `tests/contract/test_example_round_trip.py`; **40 / 34 on `bc826fcbcb`, D-37**) get a blocking-lane home and are deselected from the Packs corpus run (no double execution) | Operator DM 01M3V1F4H388T9Q01Y4PMA77BS | Accept advisory | operator |
| D-14 | FR-010: one real collect-only of the tree (~35–45 s on CI) + per-job filtering with pytest's marker evaluator, module rows and battery legs expanded via the shared selector; tiers keyed on OS family only (module rows run 3.11, router/packs 3.12 — interpreter-keyed tiers would hide the very duplicates being removed); reasoned shrink-only allowlist (expected 4 entries, cap 10) | FR-010/NFR-004; ≤ ~55 s | Per-job collect-only (~150 s+ on CI); interpreter-keyed tiers | R2 FR-010, orchestrator decision |
| D-15 | FR-011: stdlib helper `scripts/ci/green_match.py`; a step in each selection job (router/packs `changes`, ci-modules `generate-matrix`) skips the path-filter step so every path-gated job skips; no `if:`/`needs:` changes; key = (workflow, PR, head SHA, merge-commit first parent) self-recorded by executing runs as artifact `ci-tested-key-pr<N>-base-<sha>` (matched by name); skip runs upload `ci-green-match-run-<id>-attempt-<n>` and are never chained from; Aggregate `collect` re-points to the matched run after re-verifying identity, else fails; `actions: read`; any lookup error → run normally | The Actions API's `pull_requests[].base.sha` reports the CURRENT base, not the tested one; diff-cover must not be silently skipped | Matching on API base SHA (unsound); job-level `if:` (touches golden lane tests) | R3 §1; operator DMs 01M3V02AV3002PNZYY8HFJ6DQF, 01M3V1F7JYH2YNZCM4TAHB3Q3P |
| D-16 | FR-011 Aggregate half verified offline (recorded API fixtures) in-mission; live verification on the first post-merge ready-for-review PR is a recorded follow-up; Sonar re-uploading an identical informational report on skip runs is accepted | `workflow_run` executes main's workflow file | Splitting FR-011 | operator DM 01M3V1F7JYH2YNZCM4TAHB3Q3P, orchestrator |
| D-17 | FR-006: per-file pure cached function keyed on (resolved root, selection inputs) returning immutable findings, cleared at file end; mutation/self-mutation tests call the uncached primitive. In scope now: `test_interpreter_shard_coverage.py` (~34 s dup), `test_clock_call_ban.py` (~23 s dup). Dead-symbol files: PR #5503 already adds a session cache and deletes `test_refresh_dead_symbol_hashes.py` → fold/verify only after #5503 lands (C-007), else record verified-by-#5503. **Dead-symbol clause superseded by D-37** (#5503 merged; WP13 adds the file-end finalizer) | Avoid conflicting with #5503 | Caching ASTs (+1.1 GB RSS precedent) | R3 §2 |
| D-18 | FR-012: copy commit d460f55d91 (charter split): `shard_count: 2`, local recapture via `capture_shard_timings.py --module consolidation`, drop consolidation from `_MISMATCH_ALLOWLIST` and lower `_BASELINE_ALLOWLIST_COUNT` 20 → 18 in the same commit (see D-31); fix the capture marker drift (`capture_shard_timings.py` selects `not performance`, consumers `not performance and not stress`) as a prerequisite; follow-up under #5086 for automatic recapture | Recapture workflow is charter-only and main-only | Using the recapture workflow | R1 §0, R3 §3, orchestrator |
| D-19 | FR-014: dated `## Amendment (2026-10-…)` sections on ADR 2026-09-23-1 and 2026-09-26-1 (the latter correcting "green nightly means the full suite ran"); docs `updated:` bumps on `ci-gate-mechanics.md`, `testing-parallel.md`; regenerate the docs retrieval index | DIRECTIVE_003; docs freshness | Editing accepted ADR text in place | R3 §4 |
| D-20 | Companion gotchas: re-run `derive_pinning_inventory.py` after editing `_gate_coverage.py` / `test_no_duplicate_suite_execution.py` (`tests/release/pinning_rule_inventory.json` records line numbers); `_gate_coverage.py` is in the ruff-format exclude (formatting it ⇒ drop it from the exclude in the same commit); workflow file count 17/20 — add no workflow file; duplicate-suite check must count per matrix leg | Known CI-only reds | — | R1, memory |
| D-21 | Spec baseline correction: consolidation's last 7 green runs took 15.5–26.2 min (census p90 47.7 included PR-specific outliers); FR-012 still applies (uniform weights: 782 timings vs 1,617 collected) | Honest baseline | — | R3 §0 |

Follow-ups to file (out of scope): `ci-quality.yml` also re-runs on `ready_for_review`; automatic consolidation timings recapture (#5086); live verification of the Aggregate half of FR-011 after merge.


## Post-plan squad folds (architect-alphonso, researcher-robbie, planner-priti)

These supersede the decision log above where they differ.

| # | Fold | Source |
|---|------|--------|
| D-22 | **Blocking home for the 35 (D-13 design)** (**40 orphaned node ids / 34 from the round-trip file / 403 whole-file at `bc826fcbcb`, D-37**): the router keeps ONE small required job, `tests (corpus-blocking)`, gated on the `corpus` path group, running exactly the 35 orphaned node ids (all 29 corpus tests of `tests/contract/test_example_round_trip.py`, the 5 of `tests/integration/test_mission_review_contract_gate.py`, and `tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance` — the marker over whole files would select 398); Packs deselects exactly those node ids. Consequently `corpus` does NOT join `_DELIBERATELY_UNGATED_FILTER_GROUPS` (amends D-12); ledger row + `router-gate.needs` entry added. | planner-priti HIGH; orchestrator decision |
| D-23 | **Partition under xdist**: `battery_parts` is computed deterministically in EVERY process (controller and workers) from registry + timings (or shipped via `workerinput`); a pytester test at `-n 2` asserts worker-collected files == the part; a runtime self-check fails when an executed file is outside the part. | architect MAJOR |
| D-24 | **One base-file enumeration**: `shard_select.enumerate_base_files(...)` is used by the plugin and by the gate-model partition (`battery_parts`); a test asserts the two agree. | architect MAJOR |
| D-25 | **Pinned-file lane discipline**: all edits to `_gate_coverage.py`, `_ci_integrity_oracle.py` and `test_no_duplicate_suite_execution.py` are sequenced (no two parallel lanes edit them); `tests/release/pinning_rule_inventory.json` is regenerated (never hand-merged) on any lane-merge conflict and once more in the final WP. | architect MAJOR, planner MED |
| D-26 | **Registry holds only facts with no other home**: roster, budgets, `shard_count`, `timings_key`, workers. Trigger groups are NOT copied into the registry (the workflow `if:` is the authority, mirrored only by `HEAVY_BATTERY_NON_SRC_GROUPS`). The nightly backstop location is not a registry key (keeps the nightly WP off the registry lane). | architect MINOR, planner LOW |
| D-27 | **Shared base binding**: one pure `bind_tested_base(parents, head)` used by `aggregate_source.py` and `green_match.py`; `aggregate_source.py` + its tests are in IC-09's surfaces; mind the bare `from prose_only import` at `aggregate_source.py:13`. | architect MINOR |
| D-28 | **Helper names**: `scripts/ci/corpus_select.py` (not `packs_corpus_selection.py`); `scripts/ci/memory_sampler.py` is a separate new file with its own test. FR-010 logic lives in a new sibling `tests/architectural/_live_uniqueness.py`, not in the 2,799-line `_gate_coverage.py`; plugin hooks delegate to pure helpers ≤ 15 complexity. | architect MINOR, planner MED |
| D-29 | **Battery timings bootstrap is its own CI-dispatch step**: the router battery emits no junit and `ci-shard-timings.json` has no battery key; local capture is forbidden (C-009). Battery legs upload junit; a dispatched run captures per-file timings (`capture_shard_timings.py --suite architectural --from-junit`), then budgets are finalised. Until then the selector's median-weight rule balances by file count. | planner HIGH |
| D-30 | **Sequencing**: the `ci_config` group is the FIRST router edit (every later mission commit then runs the battery on PR CI — C-011 evidence); the skip-if-green work lands helper → Aggregate re-point → workflow wiring (wiring before the re-point would silently drop diff-cover); FR-010's red-first test is recorded on the merge-base (it is only red before the duplicate jobs are removed) and lands after the router battery reshaping. | planner MED |
| D-31 | **Citations corrected**: consolidation allowlist baseline is `_BASELINE_ALLOWLIST_COUNT` at `tests/architectural/test_module_length_agreement.py:151` (not `_baselines.yaml`, which #5503 edits) and must drop **20 → 18** (allowlist already holds 19 entries); `test_ci_module_wiring.py` is under `tests/ci/`; `load_workflow_models()` is at `_gate_coverage.py:2155`; `_CONSUMER_MARKER_EXPR` at `test_module_length_agreement.py:111`; router job line anchors match the current base (verified by the WP writers) but shift with each lane edit — anchor by job name. | researcher MAJOR/MINOR, planner LOW |
| D-32 | **Nightly is currently red on main** (last four runs, P0s #5418/#5505/#5506/#5507): the backstop is judged on its own job conclusion in the evidence file; its escalation path is being rewritten by open PR #5521 (#5517; touches only `nightly_escalation.py` + its test) — coordinate (land after, or adapt on rebase). **D-37**: #5521 merged; CLI unchanged, WP04 re-anchored. | researcher MAJOR |
| D-33 | **Campsite additions**: stale "latent selection mismatch" prose in `recapture_charter_shard_timings.py:61-68` and `ci-charter-shard-recapture.yml:69-71` (with the marker-drift fix); retired job names in `test_ci_collection_completeness.py:365`, `docs/development/how-to/pr-landing.md:542`, `scripts/verify_shard_3115.sh:450`, `known-friction-points.md`, `tests/release/coverage_breadth_evidence.md` (with the docs work). | researcher MINOR, planner LOW |
| D-34 | **Related issues to cite** (context, not folded): #4708 (backstop closes its architectural part), #5250 (OS-family tiers vs interpreter guard), #5098 (ci-parity), #4368 (unmatched-src fan-out now feeds Packs corpus), #1868 (CI suite-map seam epic). | researcher |
| D-35 | **Tasks-phase corrections from the WP writers**: `bind_tested_base` lives in `scripts/ci/green_match.py` (the bare `from prose_only import` makes `aggregate_source.py` unimportable in tests; `aggregate_source.py` reuses it at runtime); `green_match.py` transports via `gh api` (not urllib) so the fake-`gh` harness in `tests/ci/test_aggregate_attempts.py` can drive it; a skip marker is bound to its run attempt (`created_at >= run_started_at`) so a "re-run all jobs" attempt never re-points (contract row A4); on a skip run the always-on lanes and `prose-scan` still run (recorded residual); ADR `description:` fields are at the 180-char cap and stay unchanged; `ci-aggregate.yml` anchors are by step name; the C-011 evidence file is orchestrator-owned (kitty-specs/, not a code WP). | WP writers |
| D-36 | **Battery timings seed (amends D-29)**: WP14 seeds the `architectural` per-file timings key in `.github/ci-shard-timings.json` from the census battery logs' `--durations` sections, without any local heavy run: per file, the median over all 68 router `architectural battery` job logs of the summed ≥ 1 s phase durations (a file absent from a log counts as 0 s) plus a per-test floor of 0.12 s × the file's current collected test count (research R1 §4b `est` column) for the hidden sub-second phases; every enumerated base file gets a key (D-24). The seed carries full provenance (`battery_capture_provenance.architectural`: producer `census-seed`, method, the 68 job ids, window, `workers: 2`, base marker, `superseded_by`). The CI-dispatched junit capture (`capture_shard_timings.py --suite architectural --from-junit`, D-29) is no longer the bootstrap: it becomes the refresh path that supersedes the seed. | analyze remediation (F4); WP14 |
| D-37 | **Post-rebase drift (2026-10-01, base `bc826fcbcb`; rebased from `ecb5dd914a`)** — PR #5503 and PR #5521 landed. (1) **#5503**: deleted `test_refresh_dead_symbol_hashes.py` / `_refresh_dead_symbol_hashes.py`; rewrote `test_no_dead_symbols.py` around `@functools.lru_cache(maxsize=1)` `_real_tree_inputs()` (`:1166`); added `_dead_symbol_allowlist.py`, `dead_symbol_allowlist.yaml`, `test_dead_symbol_allowlist_{contract,loader}.py`; added `tests/contract/_module_relocations.py` + five round-trip tests; edited `ci-gate-mechanics.md` (`updated: '2026-10-01'`), the retrieval index and page inventory. (2) **#5521**: `nightly_escalation.py` now triages every filed/bumped issue (type Bug, `priority:P0`+`from:ci`, milestone by title, sub-issue of #5106); CLI unchanged. (3) **#5523** fixed on main by `e3794ded2d` and CLOSED (issue-matrix verdict verified-already-fixed): the pinning inventory is green on the base, so no WP folds it. **WP updates**: WP13 — FR-006 dead-symbol half: the once-per-file walk is #5503's `_real_tree_inputs` `lru_cache(maxsize=1)` (no conditional). That cache has process lifetime and holds `CorpusModule` trees and source, so WP13 owns `test_no_dead_symbols.py` and adds the R3 §2.2 module-scoped `cache_clear()` finalizer with its red-first test `test_real_tree_inputs_cleared_at_file_end`. Accepted cost: M11 (`test_dead_symbol_allowlist_contract.py`) loses its cross-file cache hit, ~30 s more on that worker, recorded in WP14's `known_drift`. Interpreter-shard / clock-ban anchors unchanged. WP04 — re-anchored on the merged escalation API (no new flag/permission; new pins named). WP05/WP14 — all 32 roster paths still exist and are unchanged; roster gains row 34 `test_dead_symbol_allowlist_loader.py` (47 tests, 0.7 s single-file, budget 10, formula-only seed ≈ 5.6 s); `test_dead_symbol_allowlist_contract.py` excluded (30 s single-file: its M11 test builds the real `src/` walk); base now 235 files / 3394 tests; seed records `known_drift` for the post-census files. WP10 — corpus orphan set recounted 35 → **40** (round-trip 29 → 34; whole-file 398 → 403; `39 passed, 1 skipped`). WP01 — recapture-script anchors unchanged; test file now pins behaviour, not wording. WP02 — battery counts. WP06/WP19 and every "pre-existing #5523 red" note — removed; WP19's expected inventory diff carries no #3143 row; WP19 drops its #5503/#5521 rebase conditionals. | Rebase onto merged colliding PRs (D-32, R3 §2.6) | Keep pre-merge conditionals in the prompts | post-rebase drift check |

Pre-existing red found during tasks: `test_pinning_inventory_fresh.py` fails on `main` (#5523) — the first inventory regeneration in this mission folds it. **Superseded by D-37**: fixed on main by `e3794ded2d`, #5523 CLOSED; nothing to fold.

Upstream drift check (2026-10-01): `skupstream/main` is 15 commits ahead of 956ed5e8d8; four touch the planned paths (`test_issue_named_test_census.py`, three one-line `pyproject.toml` removals for #5353) — none changes CI jobs, selectors, registry, timings or oracles. Colliding PRs: #5503 (docs index, `ci-gate-mechanics.md`, dead-symbol files), #5521 (nightly escalation), #5469 (`pyproject.toml` format-exclude neighbourhood — trivial rebase).

---


<!-- delegate section: R1 — Battery structure -->
## R1 — Battery structure (FR-001 / FR-002 / FR-003 / FR-004 / FR-005 / FR-013 / NFR-005 / C-010)

Mission `ci-runtime-stabilisation-01M3TZH6`, plan-phase research. Base: branch `issue-5510-ci-runtime-stabilisation` (HEAD f800c9a22c, = skupstream/main 956ed5e8d8 + spec commits).
Profile applied: **architect-alphonso** (design/decide/specify, no implementation code; directives 001/003/031/032/041/043/044/051) + `charter context --action plan` (DDD/ATDD-first, single canonical authority, DIRECTIVE_043 close-the-class, terminology canon: "CI path routing", never bare "routing").
Read-only research; no repo edits. Evidence files in this directory: `perfile.py`/`perfile.json` (per-file battery seconds, median of 68 census logs), `candidates.txt` (237 battery files classified).

---

### 0. Ground truth (what exists today, with anchors)

| Surface | Anchor | Today |
|---|---|---|
| Battery job | `.github/workflows/ci-router.yml:555-606` (`architectural-heavy`) | one job, `timeout-minutes: 30`, `fetch-depth: 0`, `uv run --frozen pytest tests/architectural -q -m "not performance and not stress and not timing" -n auto --dist loadfile` + 4 `--deselect` (terminology, layer_rules, pyproject_shape, archive_root_byte_identical) at :603-606 |
| Fast always-on arch lanes | `ci-router.yml:475-545` (`terminology`, `layer-rules`, `archive-freeze`) | `if:` = fork guard only, no filter group; 5-10 min timeouts |
| Router gate | `ci-router.yml:736-764` | `needs:` must equal every non-gate top-level job (`test_dual_mode_contract.py:269-322`); classifies jobs-API rows by *display name* (`scripts/ci/router_gate.py:76-92`), so matrix legs are classified automatically |
| LPT shard selector | **inline heredoc** in `.github/workflows/module-tests.yml:169-266` | collect-only `-m "not performance and not stress"` (:221-226); positional pairing with `ci-shard-timings.json` `module_test_durations[module]`; **silent** `durations = [1.0]*len(node_ids)` on length mismatch (:251-252, the #5092 defect); greedy LPT with stable sort + lowest-index tie-break (:254-260) |
| Algorithm twin | `tests/architectural/test_module_shard_registry.py:108-120` `_lpt_bin_pack` | loads-only re-implementation used by the skew gate (:269-308) |
| Marker constant copies | `module-tests.yml:222,348` `"not performance and not stress"`; `test_module_length_agreement.py:110` `_CONSUMER_MARKER_EXPR` (same); **`scripts/ci/capture_shard_timings.py:76` `SELECTION_MARKER_EXPR = "not performance"` (drifted — omits `not stress`)** | three copies, one already divergent |
| Registry battery entry | `.github/ci-module-registry.yml:864-878` `special_tiers.architectural` | `always_on: true`, `filter_group: null`, note says "minus the 3 fast always-on gates" — all three false (code-scoped since #5168; 4 deselects since #4365) |
| Registry pin | `test_module_shard_registry.py:331-368` | asserts `always_on is True`, `deserialized is True`, `filter_group in (None, "")` — pins the drift |
| Oracle | `tests/architectural/_ci_integrity_oracle.py:74-96, 192-221` | `MUST_RUN_ALWAYS_ON_GATES` (7 jobs), `HEAVY_BATTERY_GATE = "architectural-heavy"`, `HEAVY_BATTERY_NON_SRC_GROUPS = {"architectural"}`; exact-equality `job_gates[HEAVY] == src_backed ∪ NON_SRC` |
| Gate selection | `scripts/ci/gate_selection.py:108-115` (`_job_gates`: one entry per top-level job key), `:81-85` (`code_shard_jobs`) | a matrix job is ONE key |
| Gate-coverage model | `tests/architectural/_gate_coverage.py:289-307` (`Gate`), `:329-345` (`_matrix_includes`/`substitute_matrix`: only `include:` lists expand into per-leg gates), `:407-428` (`parse_pytest_invocation`), `:823-861` (`parse_workflow`, `Gate.shard = mvars["shard"]`), `:1482-1518` (`CompiledGate`), `:1910-1979` (`collect_job_nodeids`) | static (paths, ignores, marker) only; **no notion of a runtime partition**; file is in `[tool.ruff.format].exclude` |
| Duplicate-suite ledger | `tests/architectural/test_no_duplicate_suite_execution.py:241-276` (`AUTHORIZED_PER_CHANGE_SUITE_JOBS`), `:401-416` (`suite_executing_jobs` counts gates per `(workflow, job)`), `:953-962` (≤1 invocation per job) | a 2-leg `include:` matrix would count 2 → red |
| Nightly arch coverage | `.github/workflows/ci-nightly.yml:577` (`interpreter-matrix-shard-3`, Python 3.13, `-m "fast or unit"`) | 664/3,561 battery tests; no full-battery job; `nightly-summary.needs` at :1097 |
| Nightly lane pattern | `ci-nightly.yml:912-998` (`integration-next`) | `if: always()` + `set +e` + exit→`$GITHUB_ENV` + `nightly_escalation.py --suite-key` + terminal fail-loud (exit 5 NOT exempt for directory lanes) |
| Nightly pins | `tests/ci/test_nightly_exit_code_honesty.py:65-69` (`_DIRECTORY_LANES`), `:292-297` (every escalating job ∈ summary needs); `tests/ci/test_nightly_timeout_headroom.py:51` (`_is_nightly_target`, `ceil((max+0:30)*1.5)` rule) | |
| Release gate | `scripts/ci/release_nightly_gate.py:105` | keys on the **run conclusion** of `ci-nightly.yml` for the release SHA → any failing (non-`continue-on-error`) nightly job blocks release automatically |
| Per-test timeout authority | `pytest.ini:12-35` `timeout = 240` (#3143, landed by PR #5478 "[#3143] One per-test timeout authority in pytest.ini"); pinned by `tests/architectural/test_pytest_ini_timeout_default.py` (value + `timeout_method` unset) | no `@pytest.mark.timeout` anywhere in `tests/architectural` |
| Corpus | `.github/workflows/packs.yml:182` (`-n auto`, `--cov=src/doctrine` dead); router `tests-corpus` `ci-router.yml:685-710` (`-n auto`) | FR-009 deletes the router copy |
| Workflow-count ceiling | `test_module_shard_registry.py:402-` | 17 workflow files vs ceiling 20 → **do not add a workflow file** for the battery |
| Pinning inventory | `scripts/ci/derive_pinning_inventory.py` → `tests/release/pinning_rule_inventory.json` (records **line numbers**; gate `tests/release/test_pinning_inventory_fresh.py`) | tracks rules in `_gate_coverage.py` (3), `test_no_duplicate_suite_execution.py` (14), `test_ci_quality_path_filters.py` (2), `test_module_length_agreement.py` (1), `test_workflow_coherence.py` (5) → any edit that shifts those lines needs `python3 scripts/ci/derive_pinning_inventory.py` + `--check` in the same commit |

Measured battery facts (68 cached logs): pytest step 1378 s on 2 workers ⇒ ≈2,756 worker-s; ≥1 s tests sum to 2,206 s (132 files); 105 files have no ≥1 s test; collection 36 s for 3,561 items; job setup is only ~20 s (checkout full history 13 s, setup-uv 5 s, `uv sync` 2 s). Slowest single test 119.5 s setup (`test_module_length_agreement`), 116 s call (`test_interpreter_shard_coverage`).

---

### 1. Cross-cutting design decision (resolves Q1 + Q3): one shared selector, one plugin, one matrix job

#### Decision D-SEL — `scripts/ci/shard_select.py` is THE shard selector (both granularities)

Pure functions + a CLI, no workflow-inline algorithm left anywhere:

- `MODULE_SELECTION_MARKER_EXPR = "not performance and not stress"` — the single marker authority for module shards (imported by `capture_shard_timings.py` and `test_module_length_agreement.py`; fixes the drifted `"not performance"` copy).
- `lpt_assign(items: Sequence[tuple[str, float]], bins: int) -> list[list[str]]` — greedy LPT, **stable** sort by weight desc over the caller's order, least-loaded bin with lowest-index tie-break (byte-identical to `module-tests.yml:254-260`).
- `lpt_loads(weights, bins) -> list[float]` — replaces the body of `_lpt_bin_pack` (C-010: one algorithm; the skew test's independence is about not trusting the registry's *claim*, not about re-typing the algorithm).
- `resolve_positional_weights(node_ids, durations) -> WeightResolution` — test granularity; on length mismatch keeps the **uniform fallback (module-tests behaviour unchanged)** but returns a `mismatch` record.
- `resolve_file_weights(files, file_durations) -> WeightResolution` — file granularity; keyed by repo-relative path (robust to the daily test-count drift: 3,255→3,386 inside the census window); a file with no timing gets the **median** of known weights (never uniform-for-all), stale keys are reported; both are a `mismatch` record.
- `report_mismatch(resolution, *, label)` — prints `::warning title=shard timings::…` and appends one line to `$GITHUB_STEP_SUMMARY` (FR-005 / #5092 AC2).
- `battery_parts(base_files, roster, shard_count, file_durations) -> dict[str, frozenset[str]]` — `"fast"` = roster ∩ base; `"i/n"` = LPT of (base − roster) by file weight, items pre-sorted by path for determinism.
- CLI `python -m scripts.ci.shard_select module --module M --shard i/n --test-dirs JSON --python VENV_PY --out shard_tests.txt` — the module-tests step body moves here verbatim (same collect-only argv, same `"::" in line` filter, same exit-64 floors, same output file). `-m` form keeps `test_workflow_script_import_guard.py` green.

**Rationale:** C-010 names "the single shared shard selector"; today the algorithm exists twice and the marker three times (one divergent). #5092 AC3 explicitly asks for a `tests/ci`-covered helper. Positional pairing is unfit for the battery (test count drifts daily); per-file keying is.
**Alternatives:** (a) keep module-tests inline and write a second battery selector — rejected (C-010 duplicate authority); (b) per-test granularity for the battery — rejected: `--dist loadfile` and file-scoped caches (FR-006) need whole files on one runner; (c) `pytest-split`/new dependency — rejected (supply-chain, and it would be a third algorithm).

#### Decision D-PLUG — the partition is applied *inside* pytest by a plugin, with a literal flag the gate model can read

`scripts/ci/battery_partition_plugin.py`, loaded as `uv run --frozen python -m pytest tests/architectural … -p scripts.ci.battery_partition_plugin --battery-part <fast|1/2|2/2>`:

- `pytest_addoption`: `--battery-part`.
- `pytest_configure` (controller only, i.e. no `workerinput`): read registry + timings, compute parts, validate `n == special_tiers.architectural.shards.shard_count` and `numprocesses == workers` when `GITHUB_ACTIONS` is set (fail closed with `UsageError`), emit FR-005 warnings, print the part's file list and predicted load.
- `pytest_ignore_collect(collection_path)`: return `True` only for an enumerated base test-module file (`config.getini("python_files")` globs under the arg paths, minus whole-file `--deselect`s) that is **not** in this part. Never ignores directories, `conftest.py`, `_*.py` helpers or non-enumerated files — so any enumeration gap shows up as an *overlap* (caught by the proof), never as a silent loss. Ignored files are never imported → collection per leg is cheaper than today's 36 s.
- `pytest_runtest_logreport` (controller): aggregate per-file seconds and slowest test; `pytest_terminal_summary` writes the per-file table, slowest test, and xdist workers seen (`pytest_testnodeready`, `optionalhook=True`) to the log and step summary; `::warning::` when a roster file exceeds its budget or any test exceeds the NFR-003 180 s bound.

`python -m pytest` (not the console script) is required so `-p scripts.…` imports at pre-parse; xdist workers insert cwd into `sys.path` themselves. Verify once in the implementing WP with a 2-worker collect-only.

**Rationale:** the alternative "pre-step writes a file list, pytest reads `@argfile`" hides the selection from every static reader (`_gate_coverage`, `test_no_duplicate_suite_execution`'s command-indirection guard) and costs a second full collection. A literal `--battery-part` argument is statically parseable *and* executed by pytest itself, so the static model and the runtime are the same function (`battery_parts`). File-granularity + identical marker/deselect arguments in every part ⇒ node-level union = base node set by construction (marker filtering is per item and file-independent).
**Alternatives:** (a) argfile/`--ignore` list generated at runtime — rejected (static invisibility); (b) hooks inside `tests/architectural/conftest.py` — viable fallback if `-p` import fails, but less visible in the command line; (c) committed per-shard file lists in the registry — rejected (a second, hand-maintained roster; C-010).

#### Decision D-JOB — two router jobs: an always-on `architectural-fast` and the existing `architectural-heavy` as a 2-leg `include:` matrix

```yaml
  architectural-fast:            # always-on, like terminology/layer-rules/archive-freeze
    if: <fork guard only>
    name: architectural fast gates (ratchet/census, always-on)
    timeout-minutes: 8
    # checkout fetch-depth: 0 (13 s; removes "works in shard, fails here" history surprises)
    run: uv run --frozen python -m pytest tests/architectural -m "<base marker>" -n 4 --dist loadfile <4 --deselect> -p scripts.ci.battery_partition_plugin --battery-part fast

  architectural-heavy:           # key unchanged
    name: architectural battery (heavy, code-scoped) ${{ matrix.shard }}
    timeout-minutes: 30          # NFR-003: ≤30; legs expected 7-10 min (≤60% rule holds)
    needs: [changes, prose-scan] # unchanged
    if: <unchanged OR-list (+ ci_config from FR-007)>
    strategy:
      fail-fast: false           # a red in leg 1 must not hide leg 2's reds (deterministic gates; avoids a second 10-min round trip)
      matrix:
        include: [{shard: '1/2'}, {shard: '2/2'}]
    run: … same base command … --battery-part ${{ matrix.shard }}
```

How the pins adapt:
- `HEAVY_BATTERY_GATE` stays a **single constant** (`gate_selection._job_gates` sees one key); `selected_code_shards == frozenset({"architectural-heavy"})` (`test_gate_selection_authority.py:67`) and every `jobs["architectural-heavy"]` pin in `tests/ci/test_ci_module_wiring.py:388-441` stay green unchanged.
- `architectural-fast` has no filter group ⇒ it is in `router.always_on_jobs`, never in `code_shard_jobs`; add it to `MUST_RUN_ALWAYS_ON_GATES` (`_ci_integrity_oracle.py:74-84`) and to `_ALWAYS_ON_JOB_NAMES` (`test_ci_module_wiring.py:319`).
- `router-gate.needs` (`ci-router.yml:744-764`) += `architectural-fast` (forced by the needs==all-jobs invariant). Router gate needs no other change: matrix legs post as two API rows and are classified like any job.
- `AUTHORIZED_PER_CHANGE_SUITE_JOBS` += `("ci-router.yml","architectural-fast")` with reason; reword the `architectural-heavy` reason ("two file-partitioned matrix legs; pairwise disjoint with architectural-fast, proven by test_battery_partition").
- `suite_executing_jobs` (`test_no_duplicate_suite_execution.py:401-416`) must count invocations **per matrix leg** (`(workflow, job, gate.shard)`, job-level value = max over legs) — otherwise the 2-leg matrix trips `test_no_authorized_job_executes_the_suite_more_than_once`. Add a fault-injection pair: 2 legs × 1 invocation = clean; 1 leg × 2 invocations = red.

**Rationale:** a matrix keeps shard count a *data* value (registry `shard_count` ↔ legs pinned) and keeps the oracle/gate-selection single-constant model; named jobs `architectural-heavy-1/2` would turn shard count into job identity and multiply every pin. `include:` (not a plain axis) is required because `_gate_coverage._matrix_includes` expands only `include:` lists into per-leg `Gate`s with `shard` labels.
**Why the fast job is always-on (not battery-scoped):** FR-003 says "modelled on the terminology / layer-rules / archive-freeze fast lanes", which are always-on; always-on is a strict superset for C-001, puts the deterministic ratchets on docs-only PRs too (C-002-friendly), keeps the oracle change to one set membership, and costs ~2 runner-min per docs-only PR. Alternative (same `if:` as the battery) would need a second heavy-gate constant (`HEAVY_BATTERY_GATES`) and a second exact-equality pin. → flagged as the one operator-visible choice (see §9).

---

### 2. FR-001 — Nightly full-battery backstop

**Decision:** one new job `architectural-backstop` in `ci-nightly.yml`, running the **base command without the plugin**: `uv run --frozen python -m pytest tests/architectural -m "not performance and not stress and not timing" -n 4 --dist loadfile <same 4 --deselect> --junitxml=out/reports/xunit-nightly-architectural.xml`, wrapped in the `integration-next` pattern (`if: always()`, `set +e`, `ARCH_BACKSTOP_EXIT` → `$GITHUB_ENV`, artefact upload, `nightly_escalation.py --suite-key architectural` on main, terminal fail-loud with **exit 5 not exempt** — it is a directory lane), `fetch-depth: 0`, memory sampler, in `nightly-summary.needs` + an echo line, no `continue-on-error` (so the run conclusion, which `release_nightly_gate.py:105` reads, goes red). `timeout-minutes: 40` with a `# headroom (#5378): max-suite>=23:30 …` comment derived from the census -n 2 maximum (`ceil((23.5+0.5)*1.5)=36` → 40), re-based after the first measured runs.

**Rationale:** the backstop must be *independent* of the partition machinery — if the plugin or selector ever dropped a file, a plugin-free base run still executes it. Equality "backstop = fast ∪ shard1 ∪ shard2" is then a theorem proven statically (FR-004 proof: parts' union = base files) plus once at node level (§4 test b). A single job is enough: estimated ~14-17 min at `-n 4`; it is off the PR critical path. Its junit is also the **recapture source** for per-file battery timings (§4, D-TIM).
**Alternatives:** (a) a 3-leg matrix re-running the PR parts — rejected: proves only that the parts run, not that nothing outside them exists; (b) a router `schedule:` trigger — rejected by the memo (router two-authority + concurrency semantics); (c) folding the battery into `interpreter-matrix-shard-3` — rejected: different interpreter (3.13, complementary by design) and a fast/unit marker lane.

**Files:** `.github/workflows/ci-nightly.yml` (new job before `nightly-summary` ~:1093; `needs` :1097; echo line ~:1114). No change to `_interpreter_shard_roster.py` or `tests/ci/test_interpreter_matrix_env_pinning.py` (backstop is not an interpreter shard; the 3.13 fast/unit arch overlap stays intentional and documented).
**Pins that move in the same commit:** `tests/ci/test_nightly_exit_code_honesty.py:65-69` `_DIRECTORY_LANES += {"architectural-backstop": "ARCH_BACKSTOP_EXIT"}` (picks up the sentinel/exit-5/summary checks automatically); `tests/ci/test_nightly_timeout_headroom.py:51` `_is_nightly_target` += the key.
**Red-first test (ATDD):** `tests/ci/test_nightly_architectural_backstop.py` (runs in the `ci` module row on every CI-path PR): parse `ci-nightly.yml` with `gc.parse_workflow` → exactly one gate for `architectural-backstop` whose `paths == registry base.paths`, `ignores == base.deselect`, `marker_expr == base.marker`, no `--battery-part`, `-n 4`; job ∈ `nightly-summary.needs`; has the escalation step with `--suite-key architectural`; no `continue-on-error`. Red today (no job; `fast or unit` only). Plus a mutation test (drop the job from `needs` → the check function reports it).
**Size: M.**

---

### 3. FR-002 — Explicit `-n 4` (CI only) + evidence + regression guard

**Decision:** literal `-n 4` in exactly four CI commands — `architectural-fast`, both `architectural-heavy` legs (one line), `architectural-backstop`, Packs `built-in-corpus-suite` (`packs.yml:182`; router `tests-corpus` is deleted by FR-009). Registry `special_tiers.architectural.workers: 4` is the declared value. `Makefile` keeps `-n auto` (C-005; already pinned by `test_makefile_tier_topology.py`, no change). Module shards stay serial.
**Evidence (gw0–gw3):** drop `-q` from these four commands — at default verbosity xdist itself prints `created: 4/4 workers` and `4 workers [N items]` (`xdist/dsession.py:78-80` suppresses `report_line` only at `verbose < 0`); the plugin additionally lists `gw0..gw3` from `pytest_testnodeready` in the terminal + step summary for the battery legs.
**Regression guard (red-first):** `tests/ci/test_xdist_worker_policy.py` — for each of the four jobs, the parsed pytest command carries `-n 4` (equal to registry `workers`) and never `-n auto`/`-n logical`; mutation fixtures for both regressions. Runtime belt-and-braces: the plugin refuses to start under `GITHUB_ACTIONS` when `numprocesses != workers`.
**Rationale:** `-n auto` = `psutil.cpu_count(logical=False)` = 2 on the 4-vCPU runner (verified by the research squad; logs only show gw0/gw1). A literal is reviewable and the registry pin makes a runner-size change a one-line edit.
**Alternative:** `-n logical` — rejected: depends on psutil's presence, hides the count from static review, and FR-002 asks for an explicit count.
**Size: S.**

---

### 4. FR-003 + FR-004 + FR-005 — fast roster, two-shard partition, visible mismatch

#### 4a. Registry schema (FR-013 + C-010 home)

Replace `ci-module-registry.yml:864-878` with:

```yaml
special_tiers:
  architectural:
    trigger: code_scoped               # was always_on: true (false since #5168)
    non_src_filter_groups: [architectural, ci_config]   # == _ci_integrity_oracle.HEAVY_BATTERY_NON_SRC_GROUPS (ci_config lands with FR-007)
    deserialized: true
    workers: 4                         # FR-002, CI only (C-005)
    base:
      paths: [tests/architectural]
      marker: "not performance and not stress and not timing"
      deselect:                        # owned by the always-on lanes; == union of their pytest paths
        - tests/architectural/test_no_legacy_terminology.py
        - tests/architectural/test_layer_rules.py
        - tests/architectural/test_pyproject_shape.py
        - tests/architectural/test_archive_root_byte_identical.py
    fast_gate:
      job: architectural-fast
      max_file_budget_seconds: 90
      max_total_measured_seconds: 300  # Σ measured roster seconds (4 workers ⇒ ≤ ~75 s wall)
      roster:                          # {path, budget_seconds, reason}
        - …
    shards:
      job: architectural-heavy
      shard_count: 2
      granularity: file
      timings_key: architectural       # ci-shard-timings.json battery_file_durations.architectural
    nightly_backstop: {workflow: ci-nightly.yml, job: architectural-backstop}
```
Workflows keep their literal arguments (the gate model must see them); the registry declares, the pin tests enforce equality (the same "mirror + exact-equality pin" pattern the oracle already uses). Shard count, roster and budgets exist **only** here; the plugin reads them at runtime.

#### 4b. Fast roster (Q2)

Admission rule (recorded in the registry comment): deterministic static gate (reads repo/AST/config, no product-CLI round trip), measured file seconds ≤ its budget ≤ 90 s, Σ measured ≤ 300 worker-s; priority to gates that went red in the census window. Excluded on purpose: `test_no_dead_symbols.py` (149 s, C-007/#5503), `test_dead_symbol_allowlist_contract.py` (30 s single-file; shares that file's real `src/` walk — D-37), `test_interpreter_shard_coverage.py` (206 s), and — once FR-010 lands — the live `test_same_tier_uniqueness.py` (real collect-only per job, heavy).

Census medians (seconds of ≥1 s tests per file, median of 68 runs at `-n 2`; `est` adds 0.12 s × test count for sub-second tests):

| # | File (tests/architectural/…) | median | tests | reds in window | est | budget |
|---|---|---|---|---|---|---|
| 1 | test_inline_meta_read_gate.py | 52.9 | 43 | 8 | 58.1 | 80 |
| 2 | test_ruff_format_exclude_ratchet.py | <1 | 6 | 5 | 0.7 | 10 |
| 3 | test_untrusted_path_containment.py | 20.3 | 12 | 4 | 21.8 | 35 |
| 4 | test_issue_named_test_census.py | <1 | 9 | 4 | 1.1 | 10 |
| 5 | test_finalize_refresh_pin_authority.py | <1 | 5 | 4 | 0.6 | 10 |
| 6 | test_no_manual_global_state_mutation.py | 9.0 | 44 | 3 | 14.3 | 25 |
| 7 | test_status_events_writes_gate.py | 11.7 | 25 | 2 | 14.7 | 25 |
| 8 | test_safe_commit_import_boundary.py | 13.6 | 18 | 2 | 15.7 | 25 |
| 9 | test_owned_checkout_single_authority.py | 14.5 | 8 | 2 | 15.5 | 25 |
| 10 | test_no_write_side_rederivation.py | 4.8 | 27 | 2 | 8.1 | 15 |
| 11 | test_mission_resolver_walker_gate.py | 4.0 | 4 | 2 | 4.5 | 10 |
| 12 | test_docs_cli_reference_parity.py | 1.6 | 9 | 2 | 2.7 | 10 |
| 13 | test_coord_read_residuals_closeout.py | 7.3 | 11 | 2 | 8.6 | 15 |
| 14 | tool_artifact_enrolment/test_enrolment_inventory.py | <1 | 1 | 1 | 0.1 | 10 |
| 15 | test_timing_coverage_invariant.py | <1 | 71 | 1 | 8.5 | 15 |
| 16 | test_status_module_boundary.py | 3.3 | 6 | 1 | 4.0 | 10 |
| 17 | test_src_reachability_guard.py | 9.4 | 5 | 1 | 10.0 | 15 |
| 18 | test_no_tmp_paths_in_tests.py | 1.1 | 4 | 1 | 1.6 | 10 |
| 19 | test_no_dead_modules.py | 8.9 | 3 | 1 | 9.2 | 15 |
| 20 | test_module_shard_registry.py | <1 | 18 | 1 | 2.2 | 10 |
| 21 | test_lifted_root_no_checklist_surface.py | 1.4 | 2 | 1 | 1.6 | 10 |
| 22 | test_json_contract_enumeration.py | 15.6 | 126 | 1 | 30.7 | 45 |
| 23 | test_completion_manifest_freshness.py | <1 | 1 | 1 | 0.1 | 10 |
| 24 | test_cli_console_single_seam.py | <1 | 4 | 1 | 0.5 | 10 |
| 25 | test_gate_selection_authority.py (CI-config) | 3.1 | 25 | – | 6.1 | 15 |
| 26 | test_ci_integrity_oracle_nonvacuous.py | <1 | 10 | – | 1.2 | 10 |
| 27 | test_dual_mode_contract.py | <1 | 25 | – | 3.0 | 10 |
| 28 | test_ci_quality_path_filters.py | <1 | 12 | – | 1.4 | 10 |
| 29 | test_no_duplicate_suite_execution.py | 1.0 | 59 | – | 8.1 | 20 |
| 30 | test_pytest_ini_timeout_default.py | <1 | 2 | – | 0.4 | 10 |
| 31 | test_makefile_tier_topology.py | <1 | 13 | – | 1.6 | 10 |
| 32 | test_workflow_coherence.py | <1 | 16 | – | 1.9 | 10 |
| 33 | test_battery_partition.py (new, static proof) | – | – | – | ~2 | 10 |
| 34 | test_dead_symbol_allowlist_loader.py (post-census, #5503; D-37) | – | 47 | – | 5.6 | 10 |

Σ est ≈ **260 worker-s** (≈ 266 with row 34, D-37; measured under today's 2-worker contention; standalone will be lower). Sizing: 4 workers ⇒ ≈65-75 s wall, floored by the longest file (≈58 s); collection of ~34 files ≈10-15 s; setup ≈20 s (measured) → **≈1.8-2.2 min** job; with the brief's conservative 90 s startup ≈2.7 min ≤ 3 min. NFR-002 (≤5 min from pipeline start) holds with ~2.5 min margin. Final budgets are re-derived from the first nightly backstop junit (`ceil(1.5 × measured)`, floor 10 s); the CI-config rows (25-32) make CI-config PRs get their wiring verdict in ~2 min, independent of FR-007.

Budget enforcement: **static and deterministic** — `test_module_shard_registry.py` asserts each roster file's committed `battery_file_durations` value ≤ its `budget_seconds` ≤ `max_file_budget_seconds` and Σ ≤ `max_total_measured_seconds`; a recapture that pushes a file over budget reds there with the remedy "move it to the shards or raise its budget within the caps". Runtime overrun in the fast job is a `::warning::` + summary line only (runner-hardware spread is 1.77× — a hard runtime budget would mint a flake class, contrary to the flakiness policy).

#### 4c. Timings data (D-TIM)

`.github/ci-shard-timings.json` gains additive keys `battery_file_durations.architectural: {path: seconds}` and `battery_capture_provenance.architectural: {producer, run_ids, workers, selection, captured_at}` (no schema pins exist on top-level keys). Producer: `scripts/ci/capture_shard_timings.py --suite architectural --from-junit <dir> --run-id … --write` aggregating testcase `time` per file (xunit2 `classname` → path), sourced from CI artefacts (`gh run download`) — never a local battery run (C-009). Bootstrap: first `mode=full` dispatch runs with all files at default weight and the loud FR-005 warning; recapture from the nightly backstop / that dispatch's junit; commit. (The 68-log census medians in `perfile.json` are a planning estimate only — the committed data must come from the reproducible producer.)

#### 4d. FR-005 behaviour

- Module granularity: on `len(durations) != len(node_ids)` → still uniform weights (behaviour unchanged) **plus** `::warning title=shard timings::module <m>: <committed> committed durations vs <collected> collected — uniform weights` and one step-summary line. Today this will fire for the five allow-listed modules in `test_module_length_agreement.py` (consolidation/missions/post_merge/release/status) — intended visibility.
- File granularity: missing-file → median default + warning listing files; stale keys → warning; never uniform-for-all, never silent.
- Fold: `capture_shard_timings.SELECTION_MARKER_EXPR` imports `MODULE_SELECTION_MARKER_EXPR` — the current `"not performance"` vs consumer `"not performance and not stress"` divergence guarantees a length mismatch for any module containing stress tests (status today) and would bite FR-012's consolidation recapture if consolidation ever gains one. **Hand to the FR-012 owner.**

#### 4e. Partition proof evaluable by `_gate_coverage` (FR-004)

- `Gate` gains `partition: str | None = None` (parsed from `--battery-part X` in `parse_pytest_invocation`; `-p` plugin args kept in an `extra_args` tuple). `CompiledGate.selects` adds "relpath ∈ `battery_parts(...)[partition]`" (lazily computed once per base). `collect_job_nodeids` appends `-p scripts.ci.battery_partition_plugin --battery-part X` so FR-010's real collect-only sees the true leg selection. With that, FR-010's same-tier comparison sees fast/1/2/2/2 as disjoint without any allowlist entry — **FR-010 depends on this extension**.
- `_gate_coverage.py` is in `[tool.ruff.format].exclude`: edit without reformatting, or reformat and drop it from the exclude in the same commit (ratchet companion).

**Tests (red-first):**
- (a) `tests/architectural/test_battery_partition.py` — in the fast roster, no collection, ~1-2 s. From the gates `gc.parse_workflow(ci-router.yml)` actually yields for `architectural-fast` and each `architectural-heavy` leg: all share identical `(paths, ignores, marker)` == registry `base`; their partitions are exactly `{"fast"} ∪ {f"{i}/{n}"}` with `n = shard_count`; `battery_parts` sets are pairwise disjoint and union == enumerated base files; roster ⊆ base; deselect set == union of the always-on arch lanes' pytest paths; skew of the two LPT loads ≤ 20 % (reusing `lpt_loads`). **Positive controls (US2-AS3):** a fixture workflow with leg `2/2` removed → "file in no set"; a duplicated leg → "file in two sets"; a stub selector that leaks a roster file into a shard → overlap; an injected synthetic file with no timing → assigned to exactly one leg and reported as missing-timing.
- (b) `tests/architectural/test_battery_partition_collection.py` — in a shard (~60-70 s): one real `collect_job_nodeids(base)` + one per part with the plugin → node-level union == base, pairwise disjoint (FR-001 AS-1 / FR-004 at node level; exercises the real `pytest_ignore_collect`).
- (c) `tests/ci/test_shard_select.py` — `lpt_assign` == the legacy inline algorithm (embedded verbatim as the reference) over randomized inputs incl. ties and mismatches; module-mode CLI writes the same `shard_tests.txt`; mismatch emits annotation + summary line (stdout/`GITHUB_STEP_SUMMARY` captured); file-mode median default and stale reporting; determinism under shuffled input order. #5092 AC3.
- (d) `tests/ci/test_battery_partition_plugin.py` — pytester-based: `--battery-part fast` collects only roster files, `1/2`/`2/2` disjoint, bad `i/n` vs registry → UsageError, conftest/helpers never ignored.

**Size:** FR-003 **M**, FR-004 **L**, FR-005 **S**.

---

### 5. FR-013 — Registry describes the battery truthfully

**Decision:** registry rewrite per §4a; rewrite `test_special_tiers_encode_heavy_pole_deserialization` (`test_module_shard_registry.py:331-368`; keep its `integration-next` half) into `test_special_tiers_architectural_matches_the_workflows`:
`trigger == "code_scoped"` ⇔ `router.job_gates[shards.job] == src_backed ∪ set(non_src_filter_groups)` and `set(non_src_filter_groups) == oracle.HEAVY_BATTERY_NON_SRC_GROUPS`; `fast_gate.job ∈ router.always_on_jobs` and ∈ `MUST_RUN_ALWAYS_ON_GATES`; `base.*` == parsed args of all four battery commands (fast, legs, backstop); `shard_count == len(matrix.include)`; `workers ==` parsed `-n`; `nightly_backstop.job ∈ nightly-summary.needs`; roster/budget rules of §4b. Also: `_lpt_bin_pack` body → `shard_select.lpt_loads`; `out_of_matrix_test_dirs` reason text for `tests/architectural` (registry ~:471) updated; docstring refs in `_interpreter_shard_roster.py:79-81` and `test_coverage_artefact_contract.py:274-276` re-pointed.
**Rationale:** the registry is the only place that can hold shard count/roster/budgets; everything else it states is checked against the workflows so it can never again be a second, wrong authority (the current `always_on: true` is pinned *by a test*).
**Size: S-M.**

---

### 6. NFR-005 — memory sampler (Q5)

**Decision:** `scripts/ci/memory_sampler.py` run as `python3 -m scripts.ci.memory_sampler start --interval 2 --out "$RUNNER_TEMP/mem.json" &` in a step before pytest (background processes persist across steps within a job), and `… report --in … --threshold-gb 12` in an `if: always()` step after it. It samples `/proc/meminfo` `MemTotal − MemAvailable` (system-wide non-reclaimable use — the OOM-relevant number on the 16 GB VM; page cache is excluded because it is counted as available), records baseline, peak and peak−baseline, and additionally reads the job cgroup's `memory.peak` (cgroup v2, kernel 6.x on ubuntu-24.04, path from `/proc/self/cgroup`) when readable, reported as secondary. Output: one log line + step-summary line; `::warning::` at ≥ 10 GB, `::error::`-annotation (not a job failure) at ≥ 12 GB. Used in both battery legs, the fast job, and the nightly backstop.
**Rejected:** `/usr/bin/time -v` reports the max RSS of the *largest single* process, not the sum across xdist workers, and wrapping the pytest command breaks the gate model's command parse (blind-runner guard); cgroup `memory.peak` alone counts page cache from the full-history checkout and uv cache.
**Tests:** `tests/ci/test_memory_sampler.py` (meminfo parsing, peak tracking, threshold rendering, cgroup-path fallback). **Size: S.**

---

### 7. Per-test timeout guard under `-n 4` (Q6)

**Authority:** `pytest.ini` `timeout = 240` (#3143, PR #5478), pinned by `tests/architectural/test_pytest_ini_timeout_default.py`; no per-test markers in the battery. **Decision: do not touch it** — no `--timeout` CLI flag (would undercut the single authority), no `@pytest.mark.timeout` (NFR-003's 180 s is a duration bound, not a kill threshold). Guards instead: (1) FR-006 lands before or with the `-n 4` flip — it removes the duplicate collections in the two ≥100 s families; (2) the plugin reports the slowest test per leg and annotates any test > 180 s; (3) LPT naturally separates the heaviest files across legs. **Residual risk:** `test_module_length_agreement.py::test_non_allowlisted_modules_agree_with_live_collection` (119.5 s *setup*, subprocess collections of whole module trees, not in FR-006's file list) could approach 180 s under SMT contention — watch it in the first `mode=full` dispatch; remedy is caching/narrowing that setup, not a timeout bump.

---

### 8. Change list per FR (files + pins that must move in the same commit)

| FR | Change | Same-commit companions |
|---|---|---|
| FR-001 | `ci-nightly.yml` new `architectural-backstop` + summary needs/echo | `tests/ci/test_nightly_exit_code_honesty.py:65-69`; `tests/ci/test_nightly_timeout_headroom.py:51`; new `tests/ci/test_nightly_architectural_backstop.py`; registry `nightly_backstop` |
| FR-002 | `-n 4` + drop `-q` in fast/legs/backstop/`packs.yml:182` | new `tests/ci/test_xdist_worker_policy.py`; registry `workers` |
| FR-003 | `ci-router.yml` new `architectural-fast` (+ `router-gate.needs`) | `_ci_integrity_oracle.py:74-84`; `test_no_duplicate_suite_execution.py:241-276`; `test_ci_module_wiring.py:319`; `test_gate_selection_authority.py:113-117` (optional strengthening); registry roster |
| FR-004 | `architectural-heavy` → 2-leg `include:` matrix, `fail-fast: false`; `scripts/ci/shard_select.py`; `scripts/ci/battery_partition_plugin.py`; `_gate_coverage.py` `Gate.partition`/`extra_args`, `CompiledGate`, `collect_job_nodeids`; `capture_shard_timings.py --suite/--from-junit`; `ci-shard-timings.json` battery keys | `test_no_duplicate_suite_execution.py:401-416, 953-962` (per-leg count) + fault-injection; new tests §4e(a)(b)(c)(d); `tests/ci/test_capture_shard_timings.py`; **`python3 scripts/ci/derive_pinning_inventory.py` + `--check`** (line-number inventory over `_gate_coverage.py`, `test_no_duplicate_suite_execution.py`, `test_module_length_agreement.py`); ruff-format-exclude companion for `_gate_coverage.py` |
| FR-005 | `module-tests.yml:169-266` → `python -m scripts.ci.shard_select module …` | `test_module_length_agreement.py:110` and `capture_shard_timings.py:76` import the marker constant; `tests/ci/test_shard_select.py`; `test_dual_mode_contract.py:217-240` untouched (run step unchanged) |
| FR-013 | registry `special_tiers.architectural` rewrite | `test_module_shard_registry.py:108-120, 331-368`; registry out-of-matrix reason text |
| NFR-005 | `scripts/ci/memory_sampler.py` + steps in 4 jobs | `tests/ci/test_memory_sampler.py` |

Unchanged on purpose: `Makefile` (C-005; `test_makefile_tier_topology.py` already pins `-n auto`), `module-tests.yml` run step and serial shards, `gate_selection.py` (C-003 — no parallel encoding; the matrix is invisible to it by design), `_interpreter_shard_roster.py` (code), `tests/ci/test_interpreter_matrix_env_pinning.py`, `release_nightly_gate.py` (run-conclusion based), `pytest.ini`.

**Suggested WP order:** WP-a FR-001 backstop + registry `base`/`workers` + FR-002 flags (prerequisite, independent of the plugin) → WP-b shared selector extraction + FR-005 (behaviour-preserving, characterization-tested) → WP-c plugin + gate-model partition + registry roster/shards + router fast job/matrix + sampler (FR-003/004/013, NFR-005) → WP-d timings bootstrap from a `mode=full` dispatch + budget finalisation + evidence file (C-011). FR-007 (`ci_config`) should land before or with WP-c so `non_src_filter_groups` is written once; FR-010 consumes WP-c's `Gate.partition`.

### 9. Sizing and expected outcome

| Item | Size | Expected effect |
|---|---|---|
| FR-001 | M | nightly arch coverage 18.6 % → 100 % of the per-PR battery selection; ~15 min nightly job |
| FR-002 | S | 2 → 4 workers |
| FR-003 | M | ratchet/census red in ≈2-3 min (NFR-002 ≤ 5) |
| FR-004 | L | legs ≈7-10 min each (≈2,300-2,500 worker-s ÷ 2 legs ÷ ~2.9 effective cores + ~40 s overhead) → slowest of {fast, leg1, leg2} ≈10 min vs 23.4 baseline (NFR-001 ≤ 14) |
| FR-005 | S | silent fallback becomes an annotation; marker drift closed |
| FR-013 | S-M | registry stops contradicting the workflow |
| NFR-005 | S | per-leg peak memory in log + summary |

### 10. Operator-level question (one)

**Should the fast static gate job be always-on (runs on docs-only PRs, ≈2 runner-min each, can red a docs-only PR on a ratchet/census gate) or scoped to the battery's trigger?** Recommendation: always-on — it is what FR-003's "modelled on the terminology / layer-rules / archive-freeze fast lanes" implies, it is a strict superset for C-001, and it keeps the oracle change to one set membership. Everything else above is resolvable at plan level.


<!-- delegate section: R2 — CI path routing and duplicate removal -->
## R2 — CI path routing and duplicate removal (FR-007, FR-008, FR-009, FR-010; C-002, C-003, C-008)

Mission `ci-runtime-stabilisation-01M3TZH6`, plan-phase research. Base: branch `issue-5510-ci-runtime-stabilisation` @ f800c9a22c.

**Profile applied:** architect-alphonso (design/decide, no implementation code; directives 001/003/031/032/041/043/044/051), plus the plan-action charter context (ATDD-first, single canonical authority, DDD tiered rigour, `NO_FULL_HEAVY_SUITES_IN_MISSION`, Terminology Canon: "CI path routing" and "gate selection", never bare "routing").

Inputs read: `spec.md` (authoritative), `OPTIONS-MEMO.md`, `kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/router-two-authority.md`.

Evidence was gathered with collect-only and model runs only. No battery and no whole-repo suite was run. The scratch scripts are `universe.py`, `overlap.py` and `corpus_only.py` in this directory, and `universe.json` holds the 51,476-node universe.

---

### 0. Load-bearing facts discovered (read these first)

| # | Fact | Evidence |
|---|------|----------|
| F1 | `gate_selection.py` needs **no code change** for a non-src `ci_config` group. `src_backed_groups` is derived (`any glob startswith "src/"`, gate_selection.py:72-74). `routing_groups` already includes any new group, so it joins the run-all fold. `select_modules` intersects with registry names (gate_selection.py:309-317), so a non-registry group is excluded automatically. | Simulated on a scratch copy of the router (`ci-router.sim.yml`). A workflow-only, `pytest.ini`, `pyproject.toml`, `Makefile`, registry or timings diff each selects `architectural-heavy`, sets `unmatched_src=False` and leaves the module selection unchanged. `docs/x.md` and `packs/...` still select no battery. With `HEAVY_BATTERY_NON_SRC_GROUPS={"architectural","ci_config"}`, the oracle's `assert_must_run_gates_wired` and `assert_no_zero_gated_group` pass. |
| F2 | The router `corpus` output already folds in the unmatched-src fan-out: `corpus: (mode==full \|\| unmatched) && 'true' \|\| filter.corpus` (ci-router.yml:88). The router corpus job's trigger set is therefore {router `corpus` globs (ci-router.yml:177-186)} ∪ {any `src/**` matched by no src-backed group} ∪ {`workflow_dispatch mode=full`}. | ci-router.yml:88, 177-186, 218-251 |
| F3 | Packs' `built_in` covers only `packs/built-in/**`, `tests/doctrine/**`, the pack-manifest test, the skills manifest, regression snapshots and `src/charter/offering/{schemas,drg}/**` (packs.yml:83-95). It does **not** cover `packs/internal/**` (internal lane only), `kitty-specs/**/{spec.md,plan.md,tasks/**,contracts/**,acceptance-matrix.json}`, `.kittify/{charter,glossaries,doctrine}/**`, or the unmatched-src fan-out. `push` forces `built_in=true` (packs.yml:75-76), so every main push already runs the corpus suite. | packs.yml:75-95 |
| F4 | Stress/performance tests that only the router cli/status/consolidation jobs ran: **2 stress** (`tests/status/test_emit_durability.py::test_two_concurrent_distinct_verdicts_are_both_durable`, `tests/status/test_journal_lock_unification.py::test_co1_locked_and_rehomed_writers_never_lose_a_row`) and **7 performance** (1 cli, 1 consolidation, 5 status). There are **0 timing** tests. The 3 `windows_ci` tests in `tests/cli` are not in this set: the `cli` module row selects them (it excludes only performance and stress), and on Linux they are skips. | `pytest --collect-only -m stress\|performance\|timing\|windows_ci tests/cli tests/status tests/consolidation` |
| F5 | The nightly `stress` job (`pytest -m "stress and not windows_ci"`, ci-nightly.yml:345) **collects both stress tests**. The nightly `performance` job collects all 7 performance tests. In the router jobs the performance tests were **skipped** anyway: conftest.py:327-331 skips `performance` unless `SPEC_KITTY_RUN_PERFORMANCE=1`, which only the nightly sets. | collect-only of both nightly commands |
| F6 | Measured per-PR overlaps today, from one real universe collection plus per-job selection with pytest's own `-m` evaluator. Router `tests-cli`×module `cli` = **889**; `tests-status`×`status` = **1,311**; `tests-consolidation`×`consolidation` = **1,460**; router `tests-corpus`×Packs corpus = **1,542** (identical); corpus×module `charter` = **1,483**; corpus×`glossary` = **8**; corpus×battery = **16** (3 files); Packs `built-in-pack-manifest`×battery = **4**; pack-manifest×corpus (both in Packs, same trigger) = **4**. | `overlap.py` |
| F7 | Universe collection cost: **23.1 s** for 51,476 nodes, single process, on this host. Per-job filtering over the universe adds **1.7 s** for 34 jobs. | `universe.py`, `overlap.py` |
| F8 | **Interpreter split:** router and Packs jobs pin `python-version: '3.12'`, but the module rows run on **3.11.15**. `module-tests.yml` uses the warmup action, whose setup-uv has no `python-version`, so uv falls back to `.python-version` = 3.11.15. A strict "same interpreter tier" would put the router-vs-module duplicates in *different* tiers, and FR-010 could not detect the exact duplicates it targets. | `.python-version`, ci-router.yml (each `setup-uv … python-version: '3.12'`), `.github/actions/warmup/action.yml:62` |
| F9 | `kitty-specs/` is an **immutable archive root** (`tests/architectural/test_archive_root_byte_identical.py:96-97`, always-on `archive-freeze` job). `router-two-authority.md` belongs to an accepted mission (`ci-pipeline-reinstatement-01M1X35E`, meta.json accepted 2026-09-07). An **in-place amendment would turn the always-on archive freeze red.** | test_archive_root_byte_identical.py:1-20, 96-120 |
| F10 | The gate model cannot see dynamic selections. `module-tests.yml`/`ci-modules.yml::test` parses to `paths=[]`, `marker='not performance and not stress'`, which `CompiledGate` reads as the whole tree with that marker (`_gate_coverage.py:1482-1500`). The FR-004 battery shards will have the same problem. A live uniqueness check must expand these through the same selector the workflow runs. | `load_gates()` dump |
| F11 | `_gate_tier` keys tiers on job-name prefixes `fast-tests`/`integration-tests` (`_gate_coverage.py:2457-2463`). **No live job has either prefix**, so the relation is vacuous on today's workflows. The "retired" docstring premise of `test_same_tier_uniqueness.py:25-35` ("no workflow YAML left to parse") is stale. | `_gate_coverage.py:2457`, `test_same_tier_uniqueness.py:25-53` |
| F12 | 35 corpus-marked tests have **no other per-PR home** and become advisory-only when the corpus lane is downgraded: `tests/contract/test_example_round_trip.py` (29), `tests/integration/test_mission_review_contract_gate.py` (5), `tests/doctrine/test_shipped_profiles.py` (1). | `corpus_only.py` |
| F13 | Required checks are `router gate`, `CI Modules gate` and `Clean install verification` (ADR 2026-09-23-1). `packs gate` is **not** required. However, `ci-fleet-verdict` reads the **Packs workflow-run conclusion** (`scripts/ci/fleet_verdict.py:37-46, 99-117`), so a red corpus job turns the fleet verdict red unless the job is `continue-on-error`. | ADR 2026-09-23-1; fleet_verdict.py |

---

### FR-007 — CI-config changes select the battery

#### Decision
Add one new **non-src** dorny group `ci_config` to the router filter block. Gate **only** the battery jobs on it, and wire it into the three derived surfaces. Leave the `ci` group, its registry row and its scrub mirror byte-identical.

```yaml
ci_config:
  - '.github/workflows/**'
  - '.github/actions/**'          # composite actions are spliced into workflows (_gate_coverage._splice_step_level_actions); workflow-equivalent
  - 'scripts/ci/**'
  - 'pytest.ini'
  - 'pyproject.toml'
  - 'Makefile'
  - '.github/ci-module-registry.yml'
  - '.github/ci-shard-timings.json'
```

- **Authority 1 (ci-router.yml):** insert the block after `architectural:` (ci-router.yml:209-210). Do **not** add it to the `unmatched` loop (ci-router.yml:228-248). It is non-src (contract Invariant 2), and `test_unmatched_union_covers_every_src_backed_group` requires the loop to equal the src-backed set exactly.
- **Output fold:** add `ci_config: ${{ (inputs.mode == 'full' || steps.unmatched.outputs.unmatched == 'true') && 'true' || steps.filter.outputs.ci_config }}` next to ci-router.yml:98. `test_changes_outputs_cover_every_routing_group` requires outputs to equal routing groups.
- **Authority 2:** add `|| needs.changes.outputs.ci_config == 'true'` to the battery `if:` (ci-router.yml:560-582). After FR-003/FR-004, add it to **every** battery job (shard 1, shard 2, and the fast gate job if that job is path-scoped rather than always-on). The `&& prose_only != 'true'` conjunct stays as the single outer AND, as it is today (C-002, see below).
- **gate_selection.py:** no change (F1).
- **Contract amendment (C-003):** the archived contract cannot be edited in place (F9). Record the amendment as a **new** file: `kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md`. Title it "Amendment 2026-10 to ci-pipeline-reinstatement-01M1X35E/contracts/router-two-authority.md". It records:
  - (a) Invariant 2 is extended. `ci_config` is a third named non-src group that gates the battery. The `ci` group still gates no router job (#4386 unchanged). The by-design closure of #5302 is reversed **for CI-configuration paths only**; other `scripts/**` and new `tests/**` trees still rely on the FR-001 nightly backstop.
  - (b) The router corpus job is retired and Packs becomes the sole corpus executor (FR-009). The router `corpus` group stays as a non-gating, named data family, consumed by `prose-scan` and by the Packs corpus selection.
  - (c) The battery is now a job family (FR-003/FR-004).

  Point to it from the ci-router.yml header comment (ci-router.yml:1-16) and from `docs/development/reference/ci-gate-mechanics.md`.

#### Rationale
- These are the gates that guard CI configuration (workflow-coherence, gate-coverage, registry, timings, pytest.ini/pyproject shape). The battery is their only per-PR home, so the PR that edits these files should run them (US-4).
- A separate group keeps `ci` single-purpose: it is the module-matrix CI path routing mirror of the registry row and the scrub (pinned by `test_scrub_carries_the_ci_group_verbatim` and `test_router_src_filters_derive_from_scrub_verbatim`). The glob overlap with `ci` is intentional and has precedent: `core_misc`, `unit` and `execution_context` already overlap.
- Non-src keeps C-008 intact. A `src/**` path that matches no group still trips `unmatched`, and `ci_config` can never mask it because it is excluded from the loop.

#### Alternatives considered
- **Gate the battery on the existing `ci` group.** Rejected. It violates FR-007's "ci untouched", breaks `test_ci_group_gates_no_router_job_and_stays_out_of_the_catch_all`, and misses pytest.ini, pyproject, Makefile, the registry and timings.
- **Fold the CI-config globs into `architectural`.** Rejected. It conflates "a gate changed" with "the config a gate guards changed", and its registry note says "sole per-PR home of tests/architectural".
- **Add `uv.lock`, `tests/conftest.py` and `.github/ci-foreign-coverage-baseline.json`.** Not in the spec list. `uv.lock` would fire the battery on every dependency bump, which costs runner minutes. Left as an optional operator call (Q3). `.github/actions/**` **is** included, because a composite action is part of the workflow (the gate model splices it).
- **Change `on.paths` (Gate-0).** Rejected (#3008; the router deliberately has no Gate-0).

#### Same-commit pins to move
| File:anchor | Change |
|---|---|
| `tests/architectural/_ci_integrity_oracle.py:86-96` | `HEAVY_BATTERY_NON_SRC_GROUPS = frozenset({"architectural", "ci_config"})`. Update the comment, which currently says only `ci` gates nothing. After FR-003/FR-004, `HEAVY_BATTERY_GATE` (`:84`) becomes `HEAVY_BATTERY_GATES: frozenset[str]`, and `assert_must_run_gates_wired` (`:208-223`) checks each member — coordinate with R1. |
| `tests/architectural/test_ci_integrity_oracle_nonvacuous.py:234-235` | Passes automatically through the constant. Re-key to `HEAVY_BATTERY_GATES` when the battery is sharded. |
| `tests/architectural/test_workflow_coherence.py:290-309` | No set change (`ci_config` is gated, so it is consumed). The `corpus` addition is under FR-009. |
| `tests/ci/test_ci_module_wiring.py:1-29` (docstring) | Remove "The architectural battery's heavy job is gated on src-backed groups, so it would skip such a PR". It becomes false. |
| `tests/ci/test_ci_module_wiring.py:122-140` `test_ci_infra_only_diffs_route_to_the_named_group` | Change `matched_groups == {"ci"}` to `== {"ci", "ci_config"}`. The `ci` group still routes; `ci_config` now co-matches. |
| `tests/ci/test_ci_module_wiring.py:168-173` `test_ci_infra_diff_alongside_src_change_keeps_the_src_routing` | `{"ci","ci_config","consolidation"}`. The `tests-consolidation` assertion moves to the battery (FR-008). |
| `tests/ci/test_ci_module_wiring.py:336-359` `_BASE_CONTEXT_ALL_FALSE` | Add `"changes.ci_config": False`. **Mandatory:** `_GhIfEvaluator._eval_condition` asserts that every referenced key is modelled, so all three golden tests turn red without it. |
| `tests/ci/test_ci_module_wiring.py:143-165` `test_ci_group_gates_no_router_job_and_stays_out_of_the_catch_all` | **No change needed.** It stays valid because `ci` still gates nothing. Optionally extend the docstring to name `ci_config` as the battery-gating sibling. |
| `tests/architectural/test_gate_selection_authority.py:150-163` `test_non_vacuity_floor` | No change. Optionally add `"ci_config"` to the non-src floor. |
| `tests/architectural/test_ci_router_transcription_guards.py:147-189` | No edit. It enforces outputs == routing groups and loop == src-backed. Implementation must satisfy it. |
| `tests/architectural/test_ci_quality_path_filters.py:163-215` | No edit. The docs-only path stays battery-free. |
| `tests/architectural/test_workflow_coherence.py::test_every_restored_filter_glob_is_live` | Every new glob matches a tracked file (verified: `.github/actions/warmup/action.yml`, registry, timings, pytest.ini, pyproject.toml and Makefile are all tracked). |

#### ATDD red-first
1. `tests/architectural/test_gate_selection_authority.py::test_ci_config_only_diff_selects_the_battery[...]`. Parametrize over one representative path per `ci_config` glob. Assert that the battery job(s) ⊆ `selected_jobs`, `not unmatched_src`, and `select_modules(path)` equals today's answer (`{"ci"}` for workflows and scripts/ci, `∅` otherwise). **Red today** for every path. Companion test: `test_docs_only_diff_still_skips_the_battery`.
2. `tests/ci/test_ci_module_wiring.py::test_golden_ci_config_only_pr_runs_the_heavy_battery_and_no_module_shard`. Evaluate the real battery `if:` with `changes.ci_config=True` and everything else false, and expect True. **Red today**: the key is absent from the `if:`, so the evaluator returns False.

#### C-002 (#4851) check
The `prose_only` subtraction stays the outer AND. A docstring-only `scripts/ci/*.py` diff is down-routed off the battery, exactly as it would be for `src/**`. That is safe under #4851 because raw-prose gates live in always-on lanes (`terminology`, `layer-rules`, `archive-freeze`, `docs-lint`, and the forced-on docs lane). The FR-003 fast gate job must keep that property: if it is path-scoped and holds a raw-source reader, it must be always-on instead. Flag this to R1. Workflow YAML, pytest.ini, pyproject and Makefile are not `.py`, so they can never be prose-only.

**Size: S.**

---

### FR-008 — Remove duplicate router module-path jobs

#### Decision
Delete `tests-consolidation`, `tests-status` and `tests-cli` (ci-router.yml:609-656) and their `router-gate.needs` rows (ci-router.yml:759-761). The single stress lane for the two router-only stress tests is the **existing nightly `stress` job** (ci-nightly.yml:313-375), which collects both (F5). The 7 performance tests lose nothing: the router skipped them for lack of `SPEC_KITTY_RUN_PERFORMANCE`, and the nightly `performance` job executes them.

#### Rationale
- The module rows `cli`, `status` and `consolidation` already run 889/890, 1,311/1,318 and 1,460/1,461 of these tests (F6). The remainder is exactly 2 stress tests plus 7 skipped performance tests (F4).
- `pytest.ini`'s `stress` marker doc declares the stress home as "deselected from the per-PR AND full module-tests slices and run serially … by the dedicated ci-nightly lane". The router running them per-PR (no `-m`) was incidental, and it contradicts the marker's own xdist and coverage-race rationale.
- The jobs have no coverage or xunit consumer (OPTIONS-MEMO §3), so `ci-aggregate` is unaffected. Required checks (`router gate`) keep their names (F13).
- `tests/architectural/test_marker_job_completeness.py`, which checks that every registered marker is routed to a job, still finds `stress` and `performance` homes in ci-nightly.yml.

#### Alternatives considered
- **Keep a slim router job running `-m stress tests/status`.** Rejected. It recreates a per-PR stress lane on a coverage-instrumented, co-scheduled runner, which the marker doc forbids. It also needs a new ledger row. Recorded in evidence instead: the 2 stress tests move from "per-PR on status-path PRs" to "nightly".
- **Add `stress` to the module rows' marker expression.** Rejected (C-005; serial module shards must not grow stress; coverage-thread race).

#### Same-commit pins to move
| File:anchor | Change |
|---|---|
| `.github/workflows/ci-router.yml:604-656` | Delete the 3 jobs and the "Code shards" banner text, and update the header comment. |
| `.github/workflows/ci-router.yml:759-761` | Remove from `router-gate.needs`. `tests/architectural/test_dual_mode_contract.py:270-312` `test_router_gate_step_wiring_and_needs_invariant_are_pinned` enforces needs == every non-gate job, so both edits must land together. |
| `tests/architectural/test_no_duplicate_suite_execution.py:258-260` | Delete the three ledger rows. `test_every_authorized_ledger_row_still_names_a_live_suite_job` (:939-951) turns red otherwise. Add the FR-003/FR-004 battery jobs in the commit that creates them (R1). |
| `tests/ci/test_ci_module_wiring.py:334` `_CODE_SHARD_JOB_NAMES` | Replace the hand tuple with `router.code_shard_jobs` (derived from gate_selection). The prose-only golden then asserts that **every** code-scoped job, meaning the battery family, is subtracted. Add a non-vacuity assert that the set is non-empty. |
| `tests/ci/test_ci_module_wiring.py:391-393, 421-426, 440-444` | Drop the per-shard asserts or re-key them to the battery family. |
| `tests/architectural/test_gate_selection_authority.py:78-83` `test_src_group_diff_selects_its_shard_and_heavy_arch` | Replace `"tests-consolidation" in selected_code_shards` with a check on the battery (and rename the test). |
| `tests/architectural/test_gate_selection_authority.py:129-148` `test_authority_parses_the_yaml_not_a_hardcoded_map` | The baseline at `:134-135` asserts `tests-consolidation`. Switch it to `"consolidation" in baseline.matched_groups and not baseline.unmatched_src`. The post-mutation asserts (`:146-147`) already carry the proof. Note: run-all re-selects the battery, so `selected_code_shards` can no longer distinguish the two states. |
| `tests/architectural/test_local_gate_parity.py:124-136` | Replace `"tests-consolidation"` with the battery job(s). |
| `tests/architectural/test_ci_integrity_oracle_nonvacuous.py:160-195` | No change. These are synthetic `Router` objects; renaming `tests-cli` is optional campsite work. |
| `tests/architectural/test_dual_mode_contract.py:330-368` | No change. These are synthetic `classify()` inputs. |
| Prose-only refs (campsite; no assertion depends on them) | `tests/cli/test_lazy_command_module_imports.py:36`, `tests/cli/test_register_commands_lazy_import_shape.py:9-24`, `tests/performance/test_cli_startup_agent_commands_freshness.py:28`. Each says "ci-router.yml's hardcoded tests-cli job"; change it to "the `cli` module row". |

#### ATDD red-first
The FR-010 live uniqueness test is the red-first oracle (spec FR-008, "no-op passable: no"). It reports 889, 1,311 and 1,460 overlapping nodes today. Optional direct pin: `test_router_runs_no_module_owned_test_tree`, which asserts that no ci-router.yml gate's positional paths fall inside a registry row's resolved test dirs. That is a generic structural guard against re-adding a module-path job under a new name. It is red today.

**Size: S.**

---

### FR-009 — Single, advisory corpus lane (Packs owns it)

#### Router corpus trigger set vs Packs (question 2)
- **Router corpus job fires on (F2):** `packs/**` (which includes `packs/internal/**`), `kitty-specs/**/spec.md`, `kitty-specs/**/plan.md`, `kitty-specs/**/tasks/**`, `kitty-specs/**/contracts/**`, `kitty-specs/**/acceptance-matrix.json`, `.kittify/charter/**`, `.kittify/glossaries/**`, `.kittify/doctrine/**`, **plus** any unmatched `src/**` (C-008 fan-out), **plus** dispatch `mode=full`. Push to main is diff-based.
- **Packs corpus job fires on (F3):** `built_in`, meaning `packs/built-in/**`, `tests/doctrine/**`, `tests/architectural/test_pack_manifest_no_author_edit.py`, `.kittify/command-skills-manifest.json`, the regression and skills snapshots, `src/charter/offering/{schemas,drg}/**`, dispatch `mode=full`, and **every push** (packs.yml:75).
- **Missing from Packs:** `packs/internal/**` for the corpus job, all five `kitty-specs` leaves, the three `.kittify` roots, and the unmatched-src fan-out. **Packs is already a superset on push** (forced), so the gap is PR-only.

#### Decision
1. **Packs `changes` job gains a router-derived `corpus` output, computed through the single gate-selection authority.** No glob copy. Add a step modelled on the router's `prose-scan`:
   - Use the existing checkout with `fetch-depth: 0` and `python3 -m pip install pyyaml==6.0.2`.
   - Compute the PR diff (`base.sha..sha`; on push use `event.before`).
   - Call a new small module `scripts/ci/packs_corpus_selection.py`. It has a pure `corpus_selected(paths, *, router, mode) -> bool` that returns `"corpus" in sel.matched_groups or sel.unmatched_src or mode == "full"`, where `sel = gate_selection.select_gates(paths, router=router)`. The module also has a thin IO `__main__`.
   - Fail closed: a missing or null base SHA, or a git error, gives `true`.
   - Output fold: `corpus: ${{ (inputs.mode == 'full' || github.event_name == 'push') && 'true' || steps.corpus.outputs.selected }}`.
2. **Corpus job** (`built-in-corpus-suite`, packs.yml:155-182):
   - `if: needs.changes.outputs.built_in == 'true' || needs.changes.outputs.corpus == 'true'`
   - **Advisory:** add job-level `continue-on-error: true` so the Packs run conclusion, and therefore the fleet verdict (F13), stays green. **Remove it from `packs-gate.needs`** (packs.yml:253-261) so the gate never blocks on it, whatever `needs.<job>.result` reports under continue-on-error. Add a final `if: failure()` step that emits `::warning::corpus suite failed (advisory, FR-009)`.
   - **Coverage target:** replace the dead `--cov=src/doctrine` with `--cov=charter.offering`. This is the dotted form the module-tests convention uses, and it names the same code `src/doctrine` became (`_gate_coverage.cov_target_repo_path` maps it to `src/charter/offering`, which exists). Rename the job display name to `built-in / -m corpus suite (advisory)`. That name is not a required check.
   - **Remove the in-workflow duplicate:** add `--deselect tests/architectural/test_pack_manifest_no_author_edit.py`, and widen `built-in-pack-manifest` (packs.yml:140-153) to `if: built_in == 'true' || corpus == 'true'`. The **blocking** pack-manifest guard then runs on every trigger the corpus lane runs on, and the 4-node Packs-internal overlap disappears without weakening a blocking gate.
   - Keep `fetch-depth: 0`, the `__pycache__` sweep step (pinned by `test_pycache_sweep.py`) and the `-m "corpus and not windows_ci"` exit-5 floor (#3008). The `-n 4` worker setting belongs to R1 (FR-002).
3. **Router:** delete `tests-corpus` (ci-router.yml:676-710) and its `router-gate.needs` row (`:763`). **Keep the router `corpus` filter group and output** (ci-router.yml:88, 177-186). It still feeds `prose-scan`'s doc-like glob set (ci-router.yml:372), the Packs selection, and Invariant 2. Register it as deliberately ungated.

#### Rationale
- Reusing `gate_selection.select_gates` is exactly contract Invariant 3: one importable function that parses the two authorities and is reused by CI path routing. The unmatched-src fan-out (C-008) comes for free and stays correct if the router's src groups change. Option A below would need the src-group list re-encoded in packs.yml, which C-003 and #2476 forbid.
- `continue-on-error` plus exclusion from `packs-gate` is what makes "advisory" true on all three verdict surfaces: the PR check, `packs gate`, and the fleet verdict on the Packs run conclusion.
- Removing the router copy also removes the only *required* path for corpus (via `router gate`). That is the operator-accepted downgrade. F12 names its concrete blast radius: 35 tests.

#### Alternatives considered
- **A. Copy the router `corpus` globs into a Packs dorny group, with a lockstep subset test.** Rejected on its own: it cannot express the unmatched-src fan-out without re-encoding every src group (C-003). As a hybrid, a dorny `corpus` copy plus the gate_selection step only for `unmatched`, it is still two encodings. **B (chosen)** has one encoding.
- **Trigger the corpus job on `any_src` (`src/**`).** Rejected. Every code PR would pay about 1,500 corpus tests, which is the waste this mission removes.
- **Drop `--cov` entirely** (no consumer; coverage belongs to the CI Modules shards). Considered. It is cheaper at runtime, but the spec says "corrected". If the planner prefers runtime, removal is acceptable with a one-line note.
- **Leave `built-in-corpus-suite` in `packs-gate.needs` with only `continue-on-error`.** Rejected. Whether `needs.<job>.result` reports `success` or `failure` under job-level continue-on-error is not something to stake a gate on. Excluding the job is unambiguous.

#### Same-commit pins to move
| File:anchor | Change |
|---|---|
| `.github/workflows/packs.yml:71-97` | `changes`: `fetch-depth: 0`, the PyYAML install, the `corpus` step and the `corpus` output. **Coordinate with FR-011.** The skip-if-green helper is also "folded into each workflow's selection output", so one Python step in Packs `changes` should compute both. |
| `.github/workflows/packs.yml:140-182, 249-262` | Pack-manifest `if:` widened; corpus job `if:`, `continue-on-error`, `--cov`, deselect, name and warning step; `packs-gate.needs` minus the corpus job. Update the header comment (packs.yml:21-25). |
| `.github/workflows/ci-router.yml:658-710, 763` | Delete `tests-corpus` and its needs row. Update the "Non-code shards" banner. |
| `tests/architectural/test_workflow_coherence.py:290-309` | `_DELIBERATELY_UNGATED_FILTER_GROUPS = frozenset({"any_src", "ci", "corpus"})`, with a rationale bullet: corpus gates no router job; its consumers are `prose-scan` and Packs `corpus_selected`; it is pinned by the new test below. Without this, FR-003b `test_every_restored_filter_group_is_consumed_live` turns red. |
| `tests/architectural/test_no_duplicate_suite_execution.py:262` | Delete the `("ci-router.yml","tests-corpus")` row. Re-word `:270` to "Packs lane: the corpus suite (sole owner, advisory, FR-009)". |
| `tests/ci/test_ci_module_wiring.py:406-411` | Drop `jobs["tests-corpus"]["needs"]`. |
| `tests/architectural/test_ci_corpus_trigger_completeness.py:44-57` | This test is stale: it reads `ci-quality.yml`. Repoint it to Packs: assert that `corpus_selected` is true for one probe per router `corpus` glob plus an unmatched-src probe. Reconcile `_CORPUS_GLOBS` (`:59-72`) with the live router `corpus` group: `.kittify/release/downstream-verified.json` appears in the test but **not** in the router. Either add that glob to the router `corpus` group (it is a tracked file, so it passes the glob-live check), or drop it from the test. Recommendation: add it to the router; it was meant to be a corpus root. Note: `_CORPUS_MARKED_MODULES` (the curated registry) stays as is. |
| `.github/ci-module-registry.yml:739-746` | The `tests/contract` out-of-matrix reason names "ci-router.yml's marker-selected 'tests (corpus)' job". Change it to the Packs advisory corpus lane. (This is prose; check whether `test_module_shard_registry.py` pins reason text. It does not appear to.) |
| `docs/development/reference/ci-gate-mechanics.md:114-121` | "the corpus shard (`tests-corpus`, driven by `ci-router.yml`)" becomes the Packs advisory corpus lane, and the doc should note that a red there no longer blocks `router gate`. |
| `tests/architectural/test_same_tier_uniqueness.py:48-53` | `_TRIGGER_DISJOINT_FAST_JOBS` is superseded by the FR-010 allowlist. |

#### ATDD red-first
1. `tests/ci/test_packs_corpus_selection.py`. A truth table for `corpus_selected`: each router corpus glob probe gives True; `packs/internal/x.yaml` gives True; `kitty-specs/m/spec.md` gives True; `src/specify_cli/__unmapped__/x.py` gives True; `src/specify_cli/consolidation/x.py` gives False; `docs/x.md` gives False; `mode="full"` gives True. **Red today** (the module does not exist).
2. `tests/architectural/test_ci_corpus_trigger_completeness.py::test_packs_corpus_lane_covers_every_router_corpus_trigger`. A superset check against the **live** router `corpus` group, so new router globs are covered automatically, plus the golden evaluation of the corpus job `if:`. **Red today.**
3. `tests/ci/test_packs_corpus_lane_is_advisory.py`. Assert `continue-on-error: true`, absence from `packs-gate.needs`, `router gate.needs` without any corpus job, and that no ci-router.yml job selects `-m corpus`. **Red today.**
4. `tests/architectural/test_workflow_coherence.py::test_every_literal_cov_target_is_live`. Over `load_workflow_models().cov_targets`, skip `$`-expanded targets and require `Path(cov_target_repo_path(t)).exists()`. **Red today**, and only on `packs.yml src/doctrine` (verified: the only other targets are `$target`).
5. A pin for the now-ungated `corpus` group, alongside the `ci` pin: `test_corpus_group_gates_no_router_job_and_feeds_prose_scan_and_packs`.

**Size: M.**

---

### FR-010 — Live cross-job test-set uniqueness

#### Decision
Restore the live half of `test_same_tier_uniqueness.py` over the gate-coverage model. Per-job selection is evaluated over **one real `--collect-only` universe**. The `-m` expressions are evaluated by pytest's own `Expression` on each item's real `iter_markers()` set, through the existing `CompiledGate`. A small real-collection fidelity anchor backs it up.

1. **Per-change gate set (`_gate_coverage.per_change_gates()`).** Parse workflows whose `on:` is per-change. Move `change_triggered`/`NON_CHANGE_TRIGGER_EVENTS` from `test_no_duplicate_suite_execution.py` into `_gate_coverage` as the single classifier, and have the ledger test import it (campsite; C-010 "no second enumerator"). Skip reusable-only `module-tests.yml`. Then **expand dynamic gates** through the same selector the workflow runs:
   - `ci-modules.yml::test`: one `Gate` per registry row with `paths = module_test_dirs(row)` and `marker = "not performance and not stress"`. `module_test_dirs` must be the **shared shard selector** that FR-004/FR-005 extract from the inline Python at `module-tests.yml:170-266`. Its rule is "registry `test_dirs` that exist, else `tests/<module>`". Do not re-derive it: it is *not* `gate_selection._canonical_test_mirror` (for example, the `next` row resolves to `tests/next` here and to `tests/runtime` there). **Dependency:** FR-010 lands after the shard-selector extraction, or performs it.
   - The battery shards (FR-004): one `Gate` per shard, built from the same selector in file-granularity mode.
   - Keep expansion **opt-in**. `load_gates()` default behaviour is unchanged, so `test_marker_job_completeness`, `test_fast_tier_marker_completeness` and the census keep their current semantics. Making it the default would surface out-of-matrix tests as orphans in `analyze()` and widen scope.
2. **Tier re-key (`_gate_tier`).** Today it keys on the job-name prefixes `fast-tests`/`integration-tests` (dead). The new tier key is **OS family** (`runs-on` → `ubuntu`/`windows`/`macos`) for per-change jobs. The interpreter is recorded on the gate but **does not split per-PR tiers**, because interpreter diversity is the nightly matrix's job (F8; see Q1). `same_tier_shard_counts` and `shard_counts_for_test` generalise from `{count_fast_shards, count_integration_shards}` to `dict[tier, count]`.
3. **Pairwise relation.** Add `pairwise_overlaps(gates_by_job, universe) -> dict[(JobKey, JobKey), frozenset[nodeid]]`. It computes `_selected_nodeids` once per job (O(jobs×N), not O(pairs×N)) and intersects within the same tier. `cross_job_disjoint_selection` is kept as the two-job primitive. `analyze()` is unchanged; its duplicate count stays report-only.
4. **Allowlist** in `test_same_tier_uniqueness.py` (C-010). Entries are `OverlapAllowance(job_a, job_b_family, scope, reason, issue)`. `job_b_family` may name the battery family (fast gate ∪ shards), because shard membership is data-driven. `scope` is a marker or a file set. Rules:
   - Every overlapping node must be covered by an entry.
   - Every entry must match at least one live node; a stale entry fails.
   - `len(ALLOWLIST) <= _ALLOWLIST_CEILING <= 10`. The ceiling is a ratchet constant and may only be lowered.
   - Every `reason` and `issue` must be non-empty.
5. **Fidelity anchor** (cheap). For the small jobs (terminology, layer-rules, archive-freeze, Packs pack-manifest and packaging-safety, plus the FR-003 fast gate roster), assert that the modelled selection equals `collect_job_nodeids(gate)`, i.e. a real scoped collect-only. Estimated cost is about 5-10 s.

#### Expected allowlist after FR-008/FR-009 (4 entries, ceiling 4 ≤ 10)
| # | Pair | Nodes (today's tree) | Scope | Reason |
|---|------|------|------|------|
| 1 | Packs corpus × module `charter` | 1,483 / 73 files | marker `corpus` | Corpus-reader overlay: the Packs lane fires on pack, kitty-specs and .kittify data diffs plus unmatched src; the module row fires on `src/charter/**`. It re-judges the readers against changed data (#3008, #3315). |
| 2 | Packs corpus × module `glossary` | 8 / 1 file | marker `corpus` | Same overlay (`tests/glossary/test_gate_terms.py`). |
| 3 | Packs corpus × battery family | 12 / 2 files (`test_bare_prose_corpus_ratchet`, `test_transition_guard_shrink_only`) | file set | Corpus ratchets must run on data-only diffs. The battery is code-scoped, and dropping them from the battery would break C-001. |
| 4 | Packs `built-in-pack-manifest` × battery family | 4 / 1 file | file set | The blocking pack-manifest guard on built-in data diffs. The battery copy covers code diffs (C-001). |

#### Cost (question 3)
- **Per-job real collect-only** (about 33 per-change jobs: 21 module rows, about 9 router jobs, 3 Packs jobs): about 33 × 2-3 s startup plus about 1.1× the universe size. Roughly 100 s locally and 150 s or more on a 4-vCPU runner. **Rejected** for the PR battery.
- **One real collect per distinct `-m` expression, partitioned by path:** the corpus expression alone needs a whole-tree collect, so this means about 2 whole-tree collections. Roughly 50 s locally and about 75 s on CI. Rejected.
- **Chosen: one universe collect plus model filtering.** 23 s locally (F7). On CI expect about 35-45 s, plus about 2 s of filtering and about 5-10 s of fidelity anchor, for **≤ about 55 s**. Node-ids and markers are real; the only modelled step is path-prefix and `-m` evaluation by pytest's own `Expression`. The residual risk, conftest-driven deselection or `-k`, is what the fidelity anchor covers. This is the established GC-2b pattern (`_gate_coverage.py:2647-2660`).
- Shard balancing (FR-004) must carry this file's new duration in the timings. That is R1's concern, flagged here.

#### Rationale
This extends the existing single selection engine (D-044: `CompiledGate` and `_selected_nodeids`) and the existing uniqueness test (C-010). It adds no new authority. Registry expansion reuses the workflow's own selector, so "computed from the commands the workflows actually run" holds. It bites today: about 8,200 overlapping pair-nodes (F6).

#### Alternatives considered
- **Keep job-prefix tiers and rename jobs.** Rejected: brittle naming, which is how the relation became vacuous.
- **Strict OS×interpreter tier.** Rejected (F8). It would put router 3.12 and modules 3.11 in different tiers and hide the duplicates. The alternative fix, pinning the router and Packs to `.python-version`, changes the interpreter the battery runs on. Q1.
- **Per-node allowlist entries.** Rejected: thousands of entries, which makes the cap meaningless. Pair×scope entries keep the cap at ≤ 10 and still fail on new overlap shapes.

#### Same-commit pins to move
| File:anchor | Change |
|---|---|
| `tests/architectural/_gate_coverage.py:2457-2463` `_gate_tier` | Re-key to OS family from the job's `runs-on`. Needs a `runs_on` field on `Gate` (populated in `parse_workflow`, `:823-861`) or a model lookup. |
| `tests/architectural/_gate_coverage.py:2466-2508` `shard_counts_for_test`, `same_tier_shard_counts` | Generalise to a per-tier count. |
| `tests/architectural/_gate_coverage.py:2511-2538` | Add `pairwise_overlaps`; keep `cross_job_disjoint_selection`. |
| `tests/architectural/_gate_coverage.py:864-869` `load_gates`, plus new `per_change_gates()` | Opt-in dynamic expansion. |
| `tests/architectural/test_no_duplicate_suite_execution.py` (the `change_triggered` family, about lines 330-410) | Import from `_gate_coverage` instead of defining locally (single classifier). |
| `tests/architectural/test_same_tier_uniqueness.py:1-162` | Rewrite the docstring (stale premise, F11). Replace `_TRIGGER_DISJOINT_FAST_JOBS` with the allowlist. Restore the live tests. Re-target the synthetic fault-injection tests (`:56-162`) to the new tier keys: the synthetic gates must carry an OS tier rather than rely on a `fast-tests-*` name. |

#### ATDD red-first
1. `test_no_per_change_overlap_outside_the_allowlist`. **Red on today's tree** (router cli/status/consolidation/corpus, plus the Packs-internal pack-manifest duplicate). It turns green only after FR-008 and FR-009.
2. `test_allowlist_entries_are_reasoned_live_and_capped`. Every entry matches a live overlap (stale fails), and `len <= ceiling <= 10`.
3. `test_planted_overlap_outside_allowlist_is_reported`. A synthetic third job duplicating one module row's dir is flagged; the same overlap inside an allowlisted scope is not.
4. `test_modelled_selection_matches_real_collect_for_anchor_jobs` (fidelity).
5. `test_per_change_gate_set_is_non_vacuous`. It includes at least one module row, one battery gate and one Packs gate, and expands `ci-modules.yml::test` into exactly as many gates as there are registry rows.

**Size: L.**

---

### Question 4 — gate_selection.py and the new non-src group
**No code change** (F1, simulated). The edits are confined to:
- the router YAML (filter, output fold, battery `if:`)
- `_ci_integrity_oracle.HEAVY_BATTERY_NON_SRC_GROUPS`
- `test_ci_module_wiring.py` (two `matched_groups` pins and the golden context key)
- the new red-first tests in `test_gate_selection_authority.py`

`test_workflow_coherence._DELIBERATELY_UNGATED_FILTER_GROUPS` does not change for FR-007; it gains `corpus` under FR-009. FR-009 adds a *consumer* of gate_selection (`scripts/ci/packs_corpus_selection.py`) and does not modify it.

### C-008 (#3463) compliance
- `ci_config` is outside the `unmatched` loop, so an unmapped `src/**` path still forces run-all in the router.
- The Packs corpus lane honours the same fan-out through `select_gates(...).unmatched_src`.
- The deleted router jobs leave the run-all set as {battery, modules via `select_modules` run-all, docs, e2e}. Run-all still means "everything that runs per PR".

### Cross-group coordination
- **R1 (FR-002/003/004/005).** Battery job names and family: the oracle's `HEAVY_BATTERY_GATES`, the ledger rows, the FR-010 battery family in the allowlist, and `ci_config` on every path-scoped battery job. The shared shard selector API (`module_test_dirs(row)`, file-mode shard assignment) is a prerequisite for FR-010 expansion. FR-002 sets the `-n 4` worker count on the Packs corpus job.
- **FR-011.** Fold the skip-if-green helper into the same new Python step in Packs `changes` (one step and one fetch, not two).
- **FR-013/FR-014.** The registry battery entry. The contract amendment must be a **new file** (F9). The ADR amendments are in `docs/adr/3.x` (not frozen).

### Sizing
FR-007 **S** · FR-008 **S** · FR-009 **M** · FR-010 **L** (depends on the shard-selector extraction).

### Operator-level questions
- **Q1 (FR-010 tier semantics; blocks FR-010 acceptance).** Per-PR module rows run on Python 3.11 (`.python-version`) and router/Packs jobs on 3.12. Under a strict "same OS/interpreter tier", the router-vs-module duplicates are cross-tier and FR-010 cannot flag them.
  - *Recommended:* the per-PR tier is OS-family only, and interpreter diversity stays with the nightly matrix.
  - *Alternative:* align router and Packs onto `.python-version`, which changes the battery's interpreter.
- **Q2 (FR-009 blast radius; confirmation).** The advisory downgrade leaves 35 corpus-marked tests with no blocking per-PR home: `tests/contract/test_example_round_trip.py` (29), `tests/integration/test_mission_review_contract_gate.py` (5) and `tests/doctrine/test_shipped_profiles.py` (1). No blocking alternative exists that fires on the same data-path trigger. Confirm acceptance, or exempt them, for example by keeping a blocking `-m corpus` job restricted to these files in Packs.
- **Q3 (optional).** Should `ci_config` also cover `uv.lock`, `tests/conftest.py` and `.github/ci-foreign-coverage-baseline.json`? They are not in the spec list. The recommendation is `.github/actions/**` in, the rest out (`uv.lock` would put the battery on every dependency bump).


<!-- delegate section: R3 — Skip-if-green, caching, consolidation, decision records -->
## R3 — Plan research: FR-011 skip-if-green, FR-006 per-file scan caching, FR-012 consolidation split, FR-014 decision records, C-007 #5503

Mission: `ci-runtime-stabilisation-01M3TZH6` · branch `issue-5510-ci-runtime-stabilisation` · base `956ed5e8d8`
Profile applied: **architect-alphonso** (design/decide, no implementation code; directives 001/003/031/032/041/043/044/051) plus the `plan` charter context (ATDD-first, single canonical authority, closing a defect class by construction, the shrink-only ratchet discipline, DIRECTIVE_043 for defect classes).
Read-only on the repo. The local measurements ran one gate file at a time (C-009), using `.venv/bin/python -m pytest <file> -n0 --durations=12` under `/usr/bin/time -v`. Raw output is in `plan-research/dur_*.txt`.

---

### 0. Headline findings (read these first)

1. **`pull_requests[].base.sha` on a run object cannot serve as the tested-base key.** The API returns a *live projection* of the PR. Every 2026-09-30 router run for PR #5444 now reports base `956ed5e8d8`, today's main tip, and merged PRs report `pull_requests: []`. `scripts/ci/aggregate_source.py:76-78` already documents this. Router and Packs runs also carry **`referenced_workflows: []`** (verified via REST), so the only immutable record, the `refs/pull/N/merge` merge commit, is missing from those run objects. FR-011 therefore has **each executing run record its own tested key** as an artifact *name* (see §1.3).
2. **A skip run that changes nothing in CI Aggregate stays green but quietly drops diff-cover.** A CI Modules run with an empty selection reaches `reconcile_shards.py` with `selected=[]`. PR triggers get no fallback (`source_eligibility.py` returns `NotAMainSource`), so the result is `complete=true` and `coverage=false`. `diff-cover` then skips and `aggregate-gate` stays green. Docs-only PRs already take this path today. FR-011 therefore needs a **re-point step in `ci-aggregate.yml` `collect`**: when the source is a skip run, aggregate the *matched* run's evidence.
3. **`ci-aggregate.yml` changes cannot be proven on the mission PR.** `workflow_run` executes the default-branch copy (C-006 note, `ci-aggregate.yml` sonar-pr comment). The re-point half of FR-011 is proven by unit tests plus a step-simulation test (the `tests/ci/test_aggregate_attempts.py` pattern) and by the first post-merge ready-for-review. This is an evidence caveat for C-011.
4. **#5503 already delivers FR-006 for the dead-symbol files.** On its head `e986a257`, PR #5503 **deletes** `tests/architectural/test_refresh_dead_symbol_hashes.py` and `_refresh_dead_symbol_hashes.py`. It also rewrites `test_no_dead_symbols.py` (−3126/+724) with a session cache, `@functools.lru_cache(maxsize=1) _real_tree_inputs()`, read-only `MappingProxyType` views and a pin test, `test_real_tree_inputs_are_read_only`. FR-006 for the dead-symbol files therefore reduces to **"sequence after #5503, then verify and bound the cache lifetime."** No mission edit to those files should precede #5503.
5. **The consolidation baseline in the spec is stale.** The last 7 green CI runs of `module-tests (consolidation shard 1/1)` took 15.5–26.2 min (median ~19.7), not a 47.7 p90. The suite has **1617 tests** under the consumer marker, against **782** committed timings, so today's selection falls back to uniform weights. The CI xunit artifact from run 36816208389 shows 788 s of test time. With measured weights, an LPT split into 2 bins gives 394 s / 394 s (skew 0.0%). NFR-006 (≤ 26 min p90) is comfortably reachable with 2 shards.

---

### 1. FR-011 — Skip-if-green on `ready_for_review`  · **Size: L**

#### 1.1 Decision

One shared, stdlib-only, unit-tested helper **`scripts/ci/green_match.py`** with two subcommands:

- `decide` runs in each of the three PR workflows. It decides `skip` and names the marker artifact the run must upload.
- `effective-source` runs in `ci-aggregate.yml` `collect`. It re-points aggregation from a skip run to the run it matched.

It folds into each workflow's **existing selection job** as one step. It never adds a routing group and never adds a new top-level job.

| Workflow | Selection job | How `skip` folds in |
|---|---|---|
| `ci-router.yml` | `changes` (line 57) | New step `id: green` right after checkout. The dorny `filter` step (line 97) and the `unmatched` step (line 211) gain `if: steps.green.outputs.skip != 'true'`. With both skipped, every `changes.outputs.<group>` expression (lines 61-103) evaluates to `''`, so every `needs.changes.outputs.X == 'true'` job gate is false and every path-gated job skips. **No job `if:`, no `needs:` and no output expression changes.** |
| `ci-modules.yml` | `generate-matrix` (line 89) | Step `id: green` after checkout. `changed-files` (line 135) gains `&& steps.green.outputs.skip != 'true'`. The `build` step (line 225) receives `GREEN_SKIP`; on skip it forces `effective_selected = set()`, so the matrix is `[]`, `has-selection=false` and `selected-modules.json = []`, and it prints the matched run. |
| `packs.yml` | `changes` (line 71) | Step `id: green` after checkout. The dorny `filter` step (line 79) gains the same `if:`. Outputs `(inputs.mode == 'full' \|\| push) && 'true' \|\| ''` give `''` on a PR, so every lane skips. |

Each selection job gets **job-level** `permissions: {contents: read, actions: read}`. A job-level block replaces the workflow-level grant, so `contents` is restated (the same pattern as the `summarize` job in `ci-modules.yml:415-421`).

Each selection job also gets one `actions/upload-artifact` step for the marker the helper names:

- **Executing PR runs** upload `ci-tested-key-pr<N>-base-<base40>` (≈ 1 KB JSON body with `{pr, head, base, merge_sha, workflow, run_id}`, `retention-days: 30`).
- **Skip runs** upload `ci-green-match-run-<id>-attempt-<n>` instead. A skip run never uploads a tested-key marker, so no run can chain off a run that did no work.

Required gates still report:

- `router gate` reads job conclusions; `skipped` is non-blocking (`scripts/ci/router_gate.py:46`).
- `CI Modules gate` blocks only on failure or cancelled (`ci-modules.yml:368-374`).
- `packs gate` does the same (`packs.yml:276-283`).

All three post **success** on the PR head, which ADR 2026-09-23-1 needs.

#### 1.2 Rationale

- **The router fold must stay out of the `if:` parse surface.** `scripts/ci/gate_selection.py:52` `_GROUP_REF` parses `needs.changes.outputs.<name>` from every job's `if:`.
  - A new `skip` output on `changes`, referenced in a job `if:`, would be mis-parsed as a routing group. Every gated job would stop counting as always-on, and the completeness oracle would break. This is the exact hazard `ci-router.yml:262-271` cites for keeping `prose-scan` separate.
  - Suppressing the *filter step* keeps `skip` invisible to both authorities and to `gate_selection.py`. That is correct: skip is an event-level suppression of the same class as the fork guard, not a path→group fact.
  - C-003 holds: no parallel encoding and no third authority.
- **Minimal pinned-test churn.**
  - `tests/ci/test_ci_module_wiring.py` golden lane tests evaluate job `if:`s against a modelled `changes.*` context (lines 239, 335-357, 430+). They are untouched because the `if:`s do not change.
  - `tests/architectural/test_dual_mode_contract.py::test_router_gate_step_wiring_and_needs_invariant_are_pinned` (line 269) requires router-gate `needs` == all non-gate jobs. It is untouched because no job is added.
  - `tests/ci/test_fork_guard.py` (line 124) requires every self-starting job to be fork-guarded. It is untouched because no new self-starting job is added.
- **Immutable key.** `(workflow file, pull_request, PR number, head_sha, tested base)`.
  - `head_sha` is immutable on the run object.
  - The tested base is the **first parent of `GITHUB_SHA`**, the `refs/pull/N/merge` commit, read via `GET /repos/{r}/git/commits/{sha}`. The helper requires `parents[1] == event.pull_request.head.sha`, the same binding `aggregate_source.py:93-96` enforces.
  - The REST lookup avoids the shallow-clone graft problem: at `fetch-depth: 1`, `HEAD^1` does not resolve.
  - Verified live: merge `ba1439e0…` has parents `[956ed5e8 (base), ac5b816e (head)]`.
- **Artifact name, not content.** `GET /repos/{r}/actions/runs/{id}/artifacts?name=<marker>` filters server-side, so no zip download is needed. Expiry is visible (`expired: false` is required).
- **Fail-safe direction.** Any uncertainty means *run*: an API error, a missing marker, a pre-mission run, an expired artifact, or a binding mismatch. The helper never skips on doubt.

#### 1.3 Helper contract (`scripts/ci/green_match.py`)

Design rules:

- A pure core with no I/O: `decide(event: EventMeta, tested: TestedKey | None, candidates: list[RunMeta], markers: Mapping[int, frozenset[str]]) -> Skip | Run`.
- A thin `main()` edge over `urllib` and `GITHUB_TOKEN`, modelled on `scripts/ci/fleet_verdict.py`'s `GitHub` class but with **no `scripts.*` import and no `yaml`**. It runs as a bare script before any `uv sync`, which `tests/ci/test_workflow_script_import_guard.py` enforces automatically.
- Outputs, written to `$GITHUB_OUTPUT`: `skip`, `reason`, `marker`, `matched-run-id`, `matched-run-attempt`, `matched-run-url`.
- On skip, it also writes a `$GITHUB_STEP_SUMMARY` line and a `::notice::` naming the matched run. This satisfies acceptance scenario 4: "its log names the matched prior run".

`decide` algorithm:

1. If `GITHUB_EVENT_NAME != pull_request`, return Run(`not-a-pull-request`) with `marker=''`. This covers push, `workflow_dispatch`, `workflow_call` (nightly) and schedule.
2. Resolve the tested key from the merge-commit parents. If the binding fails, return Run(`merge-ref-unbound`) with `marker=''`.
3. If `action != ready_for_review`, return Run(`not-ready-for-review`) with `marker=tested-key`.
4. If `GITHUB_RUN_ATTEMPT != 1`, return Run(`re-run-never-suppressed`) with `marker=tested-key`. Re-running a skip run is the documented way to force execution.
5. List candidates: `GET actions/workflows/<file>/runs?event=pull_request&head_sha=<head>&status=success&per_page=100`. Keep runs where `id != GITHUB_RUN_ID`, `path == .github/workflows/<file>`, `status == completed` and `conclusion == success`. Walk them newest first.
6. For each candidate, check `artifacts?name=ci-tested-key-pr<N>-base-<base>` for a non-expired entry. On the first hit, return **Skip(run)** with `marker=ci-green-match-run-<id>-attempt-<n>`.
7. Otherwise return Run(`no-green-run-for-key`) with `marker=tested-key`.

Any `HTTPError`, `URLError`, `JSONDecodeError` or `KeyError` returns Run(`lookup-failed: …`) with a `::warning::`.

`effective-source` (used by CI Aggregate):

- Input: the source run JSON plus its artifacts list. If no `ci-green-match-run-*` marker is present, the source is returned unchanged.
- If a marker is present:
  1. Fetch the matched run attempt.
  2. Require `path == .github/workflows/ci-modules.yml`, `event == pull_request`, a completed/success run, and `head_sha ==` the source `head_sha`.
  3. Require **tested-identity equality** recomputed from each run's immutable `referenced_workflows` merge ref. Both are CI Modules runs and carry it.
  4. Emit the matched `run-id` and `attempt`.
- On any mismatch, **exit non-zero**, so `collect` fails and the aggregate goes red, with the message "re-run CI Modules to execute". It never falls through to the empty-selection green.

To reuse the derivation, extract a pure `tested_identity(run) -> (head, base, pr)` from `scripts/ci/aggregate_source.py:prepare_source` (lines 71-96). `prepare_source` keeps calling it, so behaviour is unchanged.

#### 1.4 CI Aggregate wiring (`.github/workflows/ci-aggregate.yml`)

- **New first step** in `collect` (before line 233, "Prepare exact source…"): `id: effective-source`. It runs `gh api` for the source attempt and its artifacts, then `python3 scripts/ci/green_match.py effective-source`.
- **Replace the source-run expressions** that `collect` steps use (`github.event.workflow_run.id || inputs.source_run_id` and the attempt twin) with `steps.effective-source.outputs.run-id` / `run-attempt`. Affected:
  - The `env:` blocks at lines 236-237 (Prepare), 266-267 (select-current) and 305-306 (wait-for-artifacts).
  - `run-id:` at lines 287 (selected-modules download) and 324 (download-current).
  - **Keep the step names and env var names** (`SOURCE_RUN_ID`, `SOURCE_RUN_ATTEMPT`). `tests/ci/test_aggregate_attempts.py:111-130` executes these steps' `run:` bodies by name or id, and `scripts/ci/wait_for_artifacts.py:178-180` reads the env names.
- **Leave unchanged**:
  - The `run-name` (line 51). It stays bound to the *skip* run id, because `scripts/ci/fleet_verdict.py:243-263` (`automatic_aggregate`) finds the aggregate by `display_title == "CI Aggregate source <latest CI Modules run id> attempt N"`, and the latest run for the head is the skip run.
  - The concurrency group.
  - `diff-cover` and `aggregate-gate`.
- **Effect**: `prepare_source`, `select_source_artifacts`, `reconcile_shards` and `diff-cover` all run on the matched run's evidence, which reproduces the matched run's own aggregate.
  - The fallback step (`source_eligibility.py`) still yields `NotAMainSource` for PR triggers, so a skip run can never be picked as a backfill source.
  - A skip run's aggregate cancelling the still-running matched aggregate (same head-branch concurrency group, `ci-aggregate.yml:78-80`) is harmless: the survivor recomputes the same verdict.
- **What Fleet Verdict sees**: CI Router, CI Modules and Packs runs show `completed/success` for the skip runs, and the bound aggregate shows success. The `[ci]` comment links the skip runs, whose logs and summaries name the matched run. `fleet_verdict.py` needs no change.
- **What Sonar sees**: `sonar-pr` re-uploads the identical per-change analysis. It is idempotent per PR key, informational and `continue-on-error`. **Decision: leave it** (minimal blast radius). An optional seventh conjunct, `not-a-green-replay`, would save ~5–10 runner-min per occurrence but widens the pinned evaluator (`ci-aggregate.yml:465-490`, `tests/ci/test_sonar_pr_analysis.py`). Not recommended now.

#### 1.5 Negative cases (each a parametrised unit row in `tests/ci/test_green_match.py`)

**Must run (no skip):**

- **N1** — Event is `push`, `workflow_dispatch`, `workflow_call` or `schedule`.
- **N2** — Action is `opened`, `synchronize` or `reopened`. These runs upload a tested-key marker.
- **N3** — `run_attempt > 1`.
- **N4** — No run exists for the head.
- **N5** — The prior run is `queued` or `in_progress`. With `cancel-in-progress` per ref, a `ready_for_review` arriving mid-draft-run cancels that draft run anyway.
- **N6** — The prior run's conclusion is `failure`, `cancelled`, `timed_out`, `action_required`, `startup_failure`, `neutral` or `skipped`.
- **N7** — The prior run is green but its marker's base differs (the base moved).
- **N8** — The marker's PR number differs (same commit in two PRs).
- **N9** — The prior run is green with no marker: a pre-mission run, or a skip run (no chaining).
- **N10** — The marker artifact has `expired: true`.
- **N11** — Merge `parents[1]` differs from the event head (merge ref lag).
- **N12** — Any HTTP or JSON failure.
- **N13** — The candidate is the current run.
- **N14** — The candidate's `path` names another workflow.
- **N15** — Fork PR. `pull_requests[]` is empty for forks; the helper never reads it, so the decision is correct.

**Must skip:**

- **P1** — Ready-for-review, attempt 1, a green run with the same head and a matching marker. Skip, print the run.
- **P2** — Multiple matches: the newest is chosen.

**Aggregate:**

- **A1** — The marker names a missing run, a non-success run, a different head, a different workflow, or a different tested identity: `collect` fails.
- **A2** — No marker: outputs are byte-identical to today (regression row).
- **A3** — A `workflow_dispatch` replay of a skip run re-points too.

#### 1.6 Files to change

| File | Anchor | Change |
|---|---|---|
| `scripts/ci/green_match.py` | new | pure `decide` / `effective_source` + `main()` edges |
| `scripts/ci/aggregate_source.py` | 71-96 | extract `tested_identity(run)`; `prepare_source` calls it |
| `.github/workflows/ci-router.yml` | 57-60 (job header), ~96 (after checkout), 97, 211 | job permissions; `green` step; `if:` on filter + unmatched; marker upload step; header comment (lines 1-17) noting the event-level suppression |
| `.github/workflows/ci-modules.yml` | 89-98, 135-136, 225-310, 312-317 | permissions; `green` step; changed-files `if:`; build-step skip fold; marker upload |
| `.github/workflows/packs.yml` | 71-80 | permissions; `green` step; filter `if:`; marker upload |
| `.github/workflows/ci-aggregate.yml` | 220-233 (new first step), 236-237, 266-267, 287, 305-306, 324; header comment (lines 1-48) | effective-source resolution + re-pointed references |
| `.github/ci-module-registry.yml` | `ci` row (`tests/ci` covers `scripts/ci`) | no change expected; confirm `scripts/ci/green_match.py` falls under the `ci` row's roots |

#### 1.7 Pinned tests and oracles that move in the same commit

- **`tests/ci/test_aggregate_attempts.py`** (step-execution simulation). Add the effective-source step to its fake-`gh` world. The endpoints `actions/runs/42/attempts/2` and `/artifacts` already exist in the fixture.
- **`tests/architectural/test_coverage_artefact_contract.py`.**
  - Lines 155 and 168 assert the reports-glob download and dispatch/mode handling. Re-check after the `run-id:` substitution.
  - Line 754 (`…embeds_stale_fallback_and_collision_guard_language`) asserts header prose. Keep that language and append, don't rewrite.
- **`tests/architectural/test_workflow_coherence.py`** (lines 120 and 128: needs-result reads; every filter group consumed). No new filter group and no new `needs`, so expected green. Run it.
- **`tests/architectural/test_ci_router_transcription_guards.py`** (lines 147 and 230). Outputs are unchanged; run it.
- **`tests/architectural/test_gate_selection_authority.py`, `test_ci_quality_path_filters.py`, `_ci_integrity_oracle.py` users.** Must stay green, proving C-003.
- **`tests/ci/test_fork_guard.py`, `tests/architectural/test_dual_mode_contract.py`.** Must stay green (no new job).
- **`tests/ci/test_workflow_script_import_guard.py`.** Auto-includes the new bare-invoked script.
- **`tests/architectural/test_no_duplicate_suite_execution.py` / `_gate_coverage.py`.** These parse `pull_request_types` (`_gate_coverage.py:1081,1369`). Trigger types are **unchanged**, which is a deliberate choice. The rejected alternative was dropping `ready_for_review`, which would also have stopped draft→ready from ever running a PR that never ran.
- **`tests/ci/test_ci_module_wiring.py`.** Golden contexts are unaffected; re-run.

#### 1.8 ATDD red-first tests

1. `tests/ci/test_green_match.py` — **red first** with the full N1–N15 / P1–P2 table against a not-yet-existing `decide` (ImportError counts as red), then green.
   - Plus a mutation-style control: make `decide` return `Skip` whenever `conclusion == success`, ignoring markers, and **N7/N8/N9 must fail**. This proves the base, PR and marker conjuncts carry the decision (Standing Order #5).
2. `tests/ci/test_green_match_wiring.py` (static YAML parse) — red first. For each of the three workflows it asserts:
   - (a) the selection job has a step invoking `scripts/ci/green_match.py decide --workflow <own filename>`;
   - (b) job-level `actions: read`;
   - (c) every dorny/changed-files step carries `if: steps.green.outputs.skip != 'true'`;
   - (d) a marker-upload step consumes `steps.green.outputs.marker`;
   - (e) **no job-level `if:` references `green`**, which pins the `_GROUP_REF` safety;
   - (f) `pull_request.types` still contains `ready_for_review`.
   
   For `ci-aggregate.yml` it asserts the first `collect` step is `effective-source`, and that no `collect` step outside it references `github.event.workflow_run.id` or `inputs.source_run_id` (`run-name` is exempt).
3. `tests/ci/test_aggregate_attempts.py::test_green_match_source_is_repointed_to_the_matched_run` and `…_unverifiable_green_match_fails_collect` — red first (the step does not exist yet).
4. `tests/ci/test_aggregate_source.py::test_tested_identity_matches_prepare_source` — red until the extraction lands.

**Live acceptance (C-011 evidence):**

- On the mission PR: open as draft, wait for green, mark ready. Record the skip runs for Router, Modules and Packs, their "matched run" log lines, and required-check success.
- The aggregate re-point half **can only be observed after merge**: on the first post-merge PR that goes draft→ready, record its CI Aggregate run.
- Caveat: during the mission PR window, the mission branch's CI Modules skip run feeds **main's** old aggregate. It goes green with `coverage=false` (diff-cover skipped). That run therefore proves nothing about the re-point and must not be counted as FR-011 evidence.

#### 1.9 Alternatives considered

- **Drop `ready_for_review` from `types:`.** Rejected: a PR opened as draft and never pushed again would then get no run when it is marked ready. The operator chose the guard (Decision Moment).
- **Use `pull_requests[].base.sha` as the key.** Rejected: it is a live projection (verified, §0.1).
- **Add a `skip` output on `changes` and AND it into each job `if:`.** Rejected: `_GROUP_REF` mis-parse, golden-test churn, and the router-gate `needs` invariant.
- **Add a dedicated `green-match` job per workflow.** Rejected as heavier:
  - router-gate `needs` gains a job;
  - the new job needs a fork guard;
  - the expensive jobs' `needs` and `if:` change;
  - `test_ci_module_wiring.py`'s golden context must model a new key.
- **Encode the tested key in the run step name or `run-name`.** Step-name rendering in the jobs API is undocumented. Changing `run-name` alters the PR UI title. Rejected in favour of documented artifact names.
- **Copy the matched run's artifacts into the skip run.** Rejected: `select_source_artifacts.py:39-80` binds every report artifact to a shard *execution interval* of the source run, so a copy is (correctly) refused.
- **Let the empty-selection green stand.** Rejected: it silently drops diff-cover on that head, which violates the spirit of C-001 and the acceptance scenario that requires aggregation to "reuse the matched run's coverage artifacts".

Observation, not in scope: `ci-quality.yml:5` also re-runs on `ready_for_review`. The spec limits FR-011 to three workflows. ci-quality hosts the required `Clean install verification` (~24 s), so the saving would be marginal.

---

### 2. FR-006 — Per-file caching of repeated scans  · **Size: S** (interpreter + clock) **plus a verify-only follow-up** (dead-symbol, after #5503)

#### 2.1 Measured before-durations (local, 32-core host, `-n0`, one file at a time)

| File | Wall | Duplicated cost (local) | Peak RSS | Duplication |
|---|---|---|---|---|
| `test_interpreter_shard_coverage.py` | 94 s | **~34 s** | 0.72 GB | `test_no_shard_collects_zero_tests` (33.95 s) collects every roster shard; `test_shard_union_equals_full_selection…` (58.76 s) collects the full selection **and every shard again**. The shard subprocess collections are the duplicate. |
| `test_clock_call_ban.py` | 60 s | **~22.7 s** | 0.94 GB | `test_no_banned_wall_clock_call_outside_the_door` (22.70 s) and `test_every_call_exemption_entry_is_a_real_violation` (23.10 s) run the identical `collect_call_ban_violations(scan.iter_python_files())` |
| `test_refresh_dead_symbol_hashes.py` | 95 s | **0 s in-file** (one 93.7 s test, one walk) | 0.54 GB | Duplication is *cross-file* only; **#5503 deletes this file** |
| `test_no_dead_symbols.py` | 116 s | **~60–70 s** (`test_no_public_symbol…` 37.1 s, `test_bite_k…` 30.5 s, `test_auto_exempt_disjoint…` 29.4 s, `…source_module_is_live…` 8.8 s, facade 6.3 s each redo walk + import edges + collision index; the bare walk is ~3.2 s — `test_walk_modules_widening…`) | 0.54 GB (whole file; trees held transiently) | six `_walk_modules()` call sites on base (lines 2436, 3810, 4122, 4372, 4447, 4607) |

CI cost is roughly 2× local (OPTIONS-MEMO: ~91 s, ~49 s and ~75 s duplicates in CI).

#### 2.2 Decision — one caching seam per file: a pure cached function plus a file-lifetime clear

The pattern, identical in each file:

- Make the expensive computation a **module-level pure function** decorated `@functools.cache`.
- **Key it on the resolved scan root and the selection inputs.** Return an **immutable** value (tuple or frozenset), so no caller can contaminate the cache.
- Hold **findings only**: node-id strings or `(relpath, violation)` tuples, never ASTs.
- Bound the lifetime to the file with a module-scoped autouse fixture, `yield; fn.cache_clear()`. Under `--dist loadfile` that equals "once per file" and frees memory before the worker's next file.
- Self-mutation and monkeypatch tests keep calling the **uncached** primitive, so their honesty is unchanged.

**`tests/architectural/test_interpreter_shard_coverage.py`**

- Add `_collect_memo(repo_root: Path, paths: tuple[str, ...], ignores: tuple[str, ...], marker_expr: str | None) -> frozenset[str]` (cached). It wraps the module-global `collect_job_nodeids` looked up at call time. `Gate` is an unhashable mutable dataclass (`_gate_coverage.py:288`), so the key is the selection-relevant fields, never `gate.job`.
- `_coverage_completeness_violations(shards, collect=None)` (line 561): `collect = collect or collect_job_nodeids`, resolved **at call time**.
- The two real tests (lines 550 and 591) pass the memoised collector.
- The mutation tests (lines 647 and 670) call it without `collect`, so they hit the monkeypatched fake (`_install_fake_collect_job_nodeids`, line 629). They cannot be served a cached real result.

**`tests/architectural/test_clock_call_ban.py`**

- Add `_tree_call_sites(root: Path, files: tuple[Path, ...]) -> tuple[CallSite, ...]` (cached), called as `_tree_call_sites(scan.REPO_ROOT.resolve(), tuple(scan.iter_python_files()))`.
- It is used by the two real-tree tests (lines 108 and 134).
- `test_stale_exemption_removal_reds_the_gate` (line 149) monkeypatches `scan.REPO_ROOT` to `tmp_path` and calls `collect_call_ban_violations([module])` directly. It stays uncached. Even if it went through the cache, the key's root differs, so it would get a fresh scan.
- The planted-offender tests (lines 218-420) never touch the real tree.
- The shared scope module `_clock_gate_scan.py` stays unchanged, so `test_clock_import_ban.py` keeps parity.

**`tests/architectural/test_no_dead_symbols.py`** — do **not** edit before #5503 lands (C-007). After it lands:

- #5503's `_real_tree_inputs()` is `lru_cache(maxsize=1)` with **process lifetime** and holds `corpus`, which contains trees and source (needed downstream by `resolve_symbol_key`).
- Mission fold: add the same module-scoped autouse `cache_clear()` finalizer, so the trees live only while this file runs on its worker. This is the one reasoned exception to "findings not trees". It is bounded to the file; measured whole-file peak RSS today is 0.54 GB, well inside NFR-005.
- Verify with `--durations` that `_walk_modules` executes once per file.

**`tests/architectural/test_refresh_dead_symbol_hashes.py`**: **N/A** (deleted by #5503). If #5503 were abandoned, this file has no in-file duplicate anyway.

#### 2.3 Rationale

- Under `--dist loadfile`, a per-file cache is the only cache that helps (OPTIONS-MEMO §7).
- A function-level cache keyed on the resolved root makes honesty structural: a monkeypatched root cannot be served the real tree's findings.
- Returning immutable values closes the "a test mutates the cache" class (the precedent is #5503's F-06 read-only pin).
- Holding findings keeps NFR-005 headroom once FR-002 raises workers to 4.

#### 2.4 Alternatives considered

- **Module-scoped fixture holding the result.** Equivalent lifetime, but a fixture is keyed on nothing. A later test calling the scan under a monkeypatched root would bypass the fixture rather than get a correct fresh value. Kept only as the `cache_clear` finalizer.
- **`functools.cache` without a clear.** Process-lifetime: on a 4-worker runner, the memory of a finished file stays resident. Rejected for anything holding trees; harmless for node-id sets but kept uniform.
- **Cache inside `_gate_coverage.collect_job_nodeids`.** Shared by many files, where other self-mutation tests run collections under tmp roots and monkeypatches. Too wide a blast radius. Rejected.
- **Merge the duplicate tests into one.** Loses the separate failure signals FR-005/SC-003 named. Rejected.

#### 2.5 ATDD red-first tests

- `test_interpreter_shard_coverage.py::test_collect_memo_invokes_the_collector_once_per_selection`. Monkeypatch `collect_job_nodeids` with a counting fake, call `_collect_memo` twice with equal keys and once with different `ignores`, and assert 2 calls. Red: `_collect_memo` does not exist yet.
- `…::test_mutation_controls_bypass_the_memo`. Warm the memo with a real-shaped fake world A, then install fake world B and run `_coverage_completeness_violations(INTERPRETER_SHARDS)` without `collect`. Assert it reports B's planted gap. This proves the mutation tests cannot be served cached results.
- `test_clock_call_ban.py::test_tree_call_sites_scans_once_per_root_and_rescans_a_new_root`. With `tmp_path` trees A and B, a counting wrapper over `_violations_for_file` sees each file once per root, and root B is scanned fresh.
- `…::test_tree_call_sites_returns_an_immutable_value` (asserts `isinstance(..., tuple)`).
- **Acceptance**: re-run each file with `--durations=12`. Expected: the second consumer drops from ~23 s / ~34 s to < 1 s. Every existing self-mutation test still passes, and each still fails when its injected violation is present (they are unchanged).
- **Post-#5503**: `test_no_dead_symbols.py::test_real_tree_inputs_cleared_at_file_end`. Assert the autouse finalizer is registered with module scope.

#### 2.6 C-007 sequencing (#5503)

**#5503 state**: OPEN, not draft, head `stijn-dejongh/spec-kitty@e986a257`, updated 2026-10-01T01:39Z, title "[#5346] Unmask green-but-skipped tests… key the dead-symbol allowlist by (module, name)".

**Overlap with this mission's surfaces:**

- `test_no_dead_symbols.py` — 25 hunks, **every `_walk_modules` consumer**.
- `test_refresh_dead_symbol_hashes.py` / `_refresh_dead_symbol_hashes.py` — deleted.
- `_symbol_key.py`.
- `tests/architectural/README.md`.
- `docs/development/reference/ci-gate-mechanics.md` — an FR-014 target here.
- `docs/development/docs-retrieval-index.yaml` and `page-inventory.yaml` — both generated, and FR-014 regenerates them too.
- `tests/ci/test_recapture_charter_shard_timings.py`.
- `tests/conftest.py`.
- `pyproject.toml` / `ruff.toml`.

**Recommendation:**

1. Land the FR-006 interpreter + clock work in any WP; it has no overlap.
2. Put the dead-symbol fold (the `cache_clear` finalizer plus verification) in a **separate, last-sequenced WP gated on #5503 merging**. If #5503 has not merged when tasks finalize, record FR-006 for the dead-symbol files as "delivered by #5503, verified post-merge" in the issue matrix.
3. Rebase this mission onto post-#5503 main **before** the FR-014 docs WP. Then regenerate `docs-retrieval-index.yaml` (`scripts/docs/docs_index.py --write`) and the page inventory once, rather than resolving generated-file conflicts.

---

### 3. FR-012 — Split the consolidation module shard  · **Size: S** (data + one measured capture)

#### 3.1 Decision

Copy the precedent commit `d460f55d91` ("ci(registry): split charter into 7 per-PR shards and recapture its durations (#5378)"). It touched only `.github/ci-module-registry.yml` (+18) and `.github/ci-shard-timings.json`, changed only the target module's entries, and left the reasoning in a registry comment.

1. `.github/ci-module-registry.yml:27` — change `shard_count: 1` to `shard_count: 2`, with a comment block in the charter style (lines 161-204) recording:
   - the run-id;
   - the collected, passed and skipped counts and the summed seconds;
   - the CI evidence (recent 7 successes 15.5–26.2 min serial; xunit sum 788 s);
   - the LPT-2 projection.
2. Recapture locally: `.venv/bin/python scripts/ci/capture_shard_timings.py --module consolidation --run-id landing-5510-consolidation-split --write`.
   - It is serial and runs the consumer's own `test_dirs` (`tests/consolidation`, `tests/specify_cli/consolidation`, `tests/terminus`), resolved from the registry by `resolve_test_dirs` (`capture_shard_timings.py:160`).
   - This is a module suite, not `tests/architectural` and not the whole repo, so it is within C-009. It is the same mechanism the charter precedent used.
   - Expected list length: **1617**. This was measured now: `pytest <those dirs> -m "not performance" --collect-only` gives 1617, identical under `not performance and not stress`, because consolidation has no stress tests.
3. `tests/architectural/test_module_length_agreement.py:121`:
   - **delete** the `"consolidation"` entry from `_MISMATCH_ALLOWLIST`;
   - **lower** `_BASELINE_ALLOWLIST_COUNT` (line 151) from 20 to 19.
   
   Both go in the same commit. `test_allowlisted_modules_still_genuinely_mismatch` (line 419) is an always-hard-failing ratchet and goes red if the entry outlives the recapture. The constant follows the shrink-only discipline its comment (lines 145-150) asks for.
4. Update the comment in `.github/workflows/ci-charter-shard-recapture.yml:26` and `:41`. "`charter` (and `agent`, the only other non-allowlisted module)" becomes charter, agent and consolidation.

#### 3.2 Why not the recapture workflow

`ci-charter-shard-recapture.yml` cannot be used for consolidation:

- It is hard-coded to `charter` (FR-009/C-001 of mission `per-pr-shard-timings-recapture-friction-01M3H7V8`; `scripts/ci/recapture_charter_shard_timings.py`).
- Its recapture job is gated to `refs/heads/main` (F4).
- It publishes with a PAT to a fixed branch.

Dispatching it for consolidation would need a code change that the spec puts out of scope (#5086 remainder).

#### 3.3 Consequence to flag

Once consolidation leaves the allowlist, the scheduled `strict-shard-timings-check` hard-fails on **any** future consolidation count drift, and no automatic recapture exists for it. Per PR, drift stays a `ShardTimingsDriftWarning` (#5189), and FR-005 makes the uniform-weight fallback visible.

Consolidation gains tests often (`tests/terminus`). Expect periodic manual recaptures, or a follow-up that generalises the scheduled recapture to more modules. Suggest filing a child of #5086.

#### 3.4 Pins and oracles

- `tests/architectural/test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent` (line 269) runs LPT over the committed durations at `shard_count=2` and must stay ≤ 20% skew. The xunit-based projection is 0.0%. The heaviest single test is 39.3 s of 788 s, so it cannot unbalance 2 bins.
- `test_module_length_agreement.py`:
  - `test_non_allowlisted_modules_agree_with_live_collection` (line 352) now covers consolidation;
  - `test_allowlist_does_not_exceed_baseline` (line 402);
  - `test_allowlisted_modules_still_genuinely_mismatch` (line 419).
- Coverage and aggregation adjust **automatically**:
  - basenames come from `(module, shard, of)` (`test_coverage_artefact_contract.py:135`);
  - `reconcile_shards.py` and `wait_for_artifacts.py` read registry-expected shards;
  - the nightly `full-module-matrix` expands the registry.
  
  No YAML or test edits are needed. `tests/ci/test_aggregate_attempts.py:52` uses a synthetic `shard-1-of-1` name and is unaffected.
- `module-tests.yml` `timeout-minutes: 58` (line 124) is unchanged.

#### 3.5 ATDD red-first

1. Delete the allowlist entry and lower the constant **first**. Run `SPEC_KITTY_STRICT_SHARD_TIMINGS=1 pytest tests/architectural/test_module_length_agreement.py -k "non_allowlisted or baseline"`.
   - Red: committed 782 vs collected 1617.
   - Then recapture, and the same command goes green. This is the honest red→green, through the existing gate and with no new pin.
2. `test_inter_shard_skew_within_twenty_percent` must be green at `shard_count=2` with the new data.
3. **NFR-006 evidence**: ≥ 3 CI runs of `module-tests (consolidation shard k/2)` with p90 ≤ 26 min. Expected ~10 min each (394 s of tests per shard plus ~3 min setup/coverage). Record the run IDs per C-011.

#### 3.6 Alternatives

- **3 shards.** Unnecessary given the measured weights; it adds runner start-up overhead. Keep the spec's 2.
- **Recapture without a split.** Fixes the weights but leaves a ~20-min serial job on the critical path. Rejected.
- **Extend the scheduled recapture to consolidation.** Out of scope (#5086 remainder). Follow-up.

**Campsite observation for the FR-005 owner (pre-existing, not consolidation-affecting):** `capture_shard_timings.py:76` uses `SELECTION_MARKER_EXPR = "not performance"`, while the consumer, `module-tests.yml:222`, and the length gate, `test_module_length_agreement.py:110`, use `"not performance and not stress"`. The capture docstring (lines 14-17) also misquotes the consumer. For any module that has stress tests, the capture over-collects and the lengths disagree by construction. It is worth one line in FR-005's scope, or an issue.

---

### 4. FR-014 — Decision records and docs  · **Size: S–M** (prose + generated-index regen)

#### 4.1 Amendment-section convention

Repository precedent:

- `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md:177`: `### Amendment 2026-09-29 — <one-line>`.
- `2026-07-23-2-…:176`: `## Amendment (2026-09-22)`.
- `2026-08-13-*`: `## Amendment note (2026-09-27)`.

**Decision:** append, after the existing sections, `## Amendment (2026-10-0X) — <topic> (mission ci-runtime-stabilisation, #5510)` with Context / Decision / Consequences sub-paragraphs. Never rewrite the original Decision text, because ADRs are immutable plus amendments.

Required regeneration, because a new H2 changes the anchors:

- `docs/development/docs-retrieval-index.yaml` via `scripts/docs/docs_index.py --write`, guarded by `tests/docs/test_docs_index_freshness.py` and `tests/docs/test_docs_index.py`.
- `page-inventory.yaml` is keyed on frontmatter fields (tag, divio_type, owning_workstream, current_target, notes), not `updated`, so it needs **no** regen unless the frontmatter changes (`scripts/docs/inventory_lockfile.py`).

#### 4.2 ADR `docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md`

(94 lines; `updated: '2026-09-23'` at line 6.) Amendment — **skip-if-green on ready-for-review**:

- The router, modules and packs selection jobs suppress selection on a green match. The required `router gate` and `CI Modules gate` still post success on the PR head, so the required-check model is unchanged.
- The match key is `(workflow, pull_request, PR, head, merge-parent base)`. Tested-key markers are artifacts.
- Negative cases: re-run and dispatch are never suppressed.
- CI Aggregate re-points to the matched run. Fleet binds by the skip run's display title.
- "Re-run the workflow to force execution" is the escape hatch.

Bump `updated:` to the amendment date and extend `description:`. Because `description` feeds the retrieval-index abstract, regenerate the index.

#### 4.3 ADR `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md`

(83 lines; **no `updated:` field**. Only 9 of 140 3.x ADRs carry one, and no docs tool gates it. Adding `updated:` is optional; I recommend adding it for discoverability.)

Amendment — **nightly architectural backstop, sharded battery, worker policy**. This covers FR-001/002/003/004, which are other research tracks; R3 contributes only the convention. The amendment must correct the false claim at line 59, "A green nightly now means the full suite ran", which is untrue for `tests/architectural` (18.6%).

#### 4.4 Router-two-authority contract

`kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/router-two-authority.md`. Its precedent for later-mission amendments is the appended `### Diff-scoped matrix (mission ci-modules-diff-scoping)` section (line 31). Append:

- `### CI-config path group (mission ci-runtime-stabilisation, FR-007)`. This reverses the #4386/#5302 "no job gates on `ci`" ruling *for the battery only*, via the new `ci_config` group; the `ci` group stays untouched (owned by another research track).
- `### Event-level suppression: skip-if-green (FR-011)`. It is **not** a third authority:
  - it suppresses the selection step, never edits a filter glob or a job `if:`;
  - `gate_selection.py` deliberately does not model it, as with the fork guard;
  - the `_GROUP_REF` hazard is why it lives on a step.
- Amend the `ci-aggregate.yml` bullet (the last bullet of the diff-scoped section) with the effective-source re-point. On a source carrying a green-match marker, aggregation uses the verified matched attempt, and an unverifiable marker fails closed.

Referencing tests (`tests/ci/test_ci_module_wiring.py:20`, `_ci_integrity_oracle.py:87,196`, `test_ci_integrity_oracle_nonvacuous.py:223`) cite sections by name: **do not rename** existing headings.

#### 4.5 Testing and CI docs

All carry `updated:`; bump it on edit.

- `docs/development/reference/ci-gate-mechanics.md` (`updated: '2026-09-30'`).
  - §"How CI is wired" (lines 27-50): add ready-for-review skip-if-green, the fast gate plus two battery shards, CI-config→battery and the corpus owner. Line 47 currently says "`architectural-heavy` job runs the full battery on code PRs".
  - §"The architectural gate battery" (line 150): describe the shards and the fast roster.
  - **#5503 also edits this file**, which is a sequencing reason to rebase first.
- `docs/development/testing/testing-parallel.md` (`updated: '2026-09-30'`): the CI worker policy (`-n 4` explicit in CI vs `-n auto` locally, C-005) and the nightly backstop. Line 271 shows a `-n auto` full-run recipe; keep it, since it is local.
- `docs/development/testing/testing-flakiness.md`: only if FR-002/003 change timeout guidance (owned elsewhere).
- `.github/ci-module-registry.yml` comments: FR-013 (owned elsewhere).
- Run `pytest tests/architectural/test_no_legacy_terminology.py` (prose pre-push rule) and the docs-index freshness tests. Avoid bare "routing" (Terminology Canon): write "CI path routing", "gate selection" or "selection-step suppression".

#### 4.6 ATDD

FR-014 is no-op passable (prose). The automated guards are `test_docs_index_freshness.py`, the docs-freshness inventory lockfile and terminology; review verifies the rest.

One cheap, honest pin is worth adding with FR-011: `tests/ci/test_green_match_wiring.py` asserts that ADR 2026-09-23-1 contains an `## Amendment` heading mentioning "skip-if-green". This follows the `test_ci_aggregate_embeds_stale_fallback_and_collision_guard_language` precedent of pinning prose that carries a contract. Optional.

---

### 5. Sizing summary

| FR | Size | Driver |
|---|---|---|
| FR-011 | **L** | new helper + 4 workflow edits + aggregate re-point + `aggregate_source` extraction + ~25 unit rows + simulation tests; aggregate half provable only post-merge |
| FR-006 | **S** (+ XS post-#5503 fold) | two local cached functions + finalizers + 4–5 tests; dead-symbol already done by #5503 |
| FR-012 | **S** | one registry line + comment, one local capture (~2–5 min serial locally; 788 s CI test time), allowlist −1 / constant −1, comment fix in recapture workflow |
| FR-014 | **S–M** | two ADR amendments, contract amendment, two docs pages, index regen; conflict-prone with #5503 |

Suggested WP order:

1. FR-012, which is independent and gives a fast NFR-006 evidence start.
2. FR-006 (interpreter + clock).
3. FR-011.
4. Post-#5503 rebase, then the dead-symbol fold.
5. FR-014 docs, last.

### 6. Operator-level questions

1. **FR-011 evidence window.** The CI Aggregate re-point can only run from `main` (`workflow_run`). Is it acceptable that NFR/SC-005 evidence for "aggregation reuses the matched run's artifacts" is recorded **post-merge**, from the first draft→ready PR, as a C-011 follow-up line rather than a pre-merge gate? The alternative is to defer the aggregate half to a follow-up PR, which is worse because skip runs would silently drop diff-cover meanwhile.
2. **Consolidation timing drift after leaving the allowlist.** Accept that the scheduled `strict-shard-timings-check` will go red on future consolidation test additions with no automatic recapture (manual recapture, or a #5086 follow-up)? Or keep consolidation in the allowlist and recapture only the weights? The second option is not possible: the ratchet's stale-entry test forces removal once the counts agree.
3. **Sonar on skip runs.** The recommendation is to leave the duplicate informational re-upload. Confirm, or ask for the seventh `not-a-green-replay` conjunct.


- Resolved in WP13: the #5503 tree cache is cleared per file by a finalizer (FR-006).
