---
work_package_id: WP12
title: 'Router battery reshaping: fast job, 2-leg matrix, four workers'
dependencies:
- WP04
- WP06
- WP10
- WP11
- WP14
requirement_refs:
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-004
- C-002
- C-005
- NFR-005
- SC-001
- SC-002
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T049
- T050
- T051
- T052
- T053
- T054
phase: Phase 5 - Battery reshaping
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_xdist_worker_policy.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-router.yml
- tests/architectural/_ci_integrity_oracle.py
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/architectural/test_dual_mode_contract.py
- tests/ci/test_ci_module_wiring.py
- tests/architectural/test_gate_selection_authority.py
- tests/ci/test_xdist_worker_policy.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 – Router battery reshaping: fast job, 2-leg matrix, four workers

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This WP turns the single 23-minute, 2-worker router battery into the shape that halves the
critical path and reports deterministic reds within minutes:

- **`architectural-fast`**, a new **always-on** job: the registry-held fast roster
  (`--battery-part fast`), modelled on `terminology` / `layer-rules` / `archive-freeze`
  (FR-003, NFR-002).
- **`architectural-heavy`** keeps its job key and its `if:`, and becomes a **2-leg `include:`
  matrix** (`--battery-part 1/2`, `2/2`, `fail-fast: false`) (FR-004, NFR-001).
- A literal **`-n 4`** with `-q` dropped, so xdist prints `created: 4/4 workers` (FR-002). A
  static guard covers all four battery-class commands: fast, both legs, the nightly backstop
  and the Packs corpus.
- Each fast job and leg starts the **memory sampler** (WP11) and uploads **junit**, with
  timeouts ≤ 30 (NFR-003, NFR-005).
- **Invocation**: `uv run --frozen python -m pytest … -p scripts.ci.battery_partition_plugin --battery-part <part>`.
- **Companions in the same commit(s)**:
  - oracle `MUST_RUN_ALWAYS_ON_GATES`;
  - the `AUTHORIZED_PER_CHANGE_SUITE_JOBS` ledger, with **per-matrix-leg counting**;
  - the router-gate `needs` set-equality;
  - the golden lane tests in `tests/ci/test_ci_module_wiring.py`;
  - `test_gate_selection_authority.py`;
  - pinning-inventory regeneration.

Done means every red-first test (T049, T050) is red on the planning base and green on the tip,
and every pinned companion is green. Measurement evidence is collected from dispatched runs
(C-011), and **C-004** holds: the path-scoped battery stays a non-required check, and branch
protection is unchanged.

## Context & Constraints

- **Read first**: in `research.md`, decision rows D-03 (job shape), D-05 (`-n 4`, `-q`
  dropped), D-06 (fast roster), D-07 (sampler), D-08 (timeout authority stays in `pytest.ini`)
  and D-20 (per-leg counting). Then the post-plan fold rows D-23 (partition in every xdist
  process), D-25 (pinned-file discipline), D-29 (junit for timings) and D-30 (sequencing).
  Then R1 §1 "D-JOB" (how the pins adapt), §3 (FR-002), §6 (sampler), §7 (per-test timeout)
  and §8 (change list). Also read `contracts/router-two-authority-amendment.md` A2,
  `contracts/battery-partition.md`, `data-model.md`, `quickstart.md` and
  `.kittify/charter/charter.md`.
- **You land last in the router lane (D-30)**. Before you start, the base must contain:
  - WP07: `ci_config` group in the battery `if:`;
  - WP08: router `tests (cli|status|consolidation)` deleted;
  - WP09: router `tests (corpus)` deleted, Packs corpus on `-n 4`;
  - WP10: `tests (corpus-blocking)`;
  - WP04: nightly `architectural-backstop` on `-n 4`;
  - WP06: `Gate.partition`, the part-aware `CompiledGate`, `test_battery_partition_proof.py`;
  - WP11: `scripts/ci/memory_sampler.py`;
  - WP14: battery per-file timings, plus the finalised roster budgets in
    `.github/ci-module-registry.yml` `special_tiers.architectural`.

  **Re-read the live files**. Every anchor below was taken on the planning base, before those
  WPs. Anchor by **job name**, not line number.
- **Keep the single-constant model (D-03)**: `HEAVY_BATTERY_GATE = "architectural-heavy"`
  stays a single string, and `gate_selection._job_gates` sees one key per job, so a matrix is
  one key. Do **not** introduce `HEAVY_BATTERY_GATES`. That R2 suggestion is superseded by
  D-03. Do not edit `scripts/ci/gate_selection.py` (C-003).
- **Do not edit** `_gate_coverage.py` (WP06 owns the partition model; D-25),
  `.github/ci-module-registry.yml`, `packs.yml`, `ci-nightly.yml` or `pytest.ini`.
  `pytest.ini` keeps `timeout = 240` (D-08, pinned by `test_pytest_ini_timeout_default.py`).
  Do not add `--timeout` or per-test markers.
- **C-005**: the `Makefile` keeps `-n auto`, and module shards stay serial.
- **C-009**: never run `tests/architectural` whole, nor `make test-full`. The full battery
  verdict comes from the PR's own CI and the dispatched router runs.
- **Workflow ceiling**: 17/20. Add jobs, never files.
- **Terminology**: "Mission", never "feature". Say "CI path routing" / "gate selection",
  never bare "routing".

### Current-state anchors (planning base, verified 2026-10-01)

| Surface | Anchor | Today |
|---|---|---|
| Battery job | `ci-router.yml` job `architectural-heavy` (≈:555-606) | `name: architectural battery (heavy, code-scoped)`; `timeout-minutes: 30`; `needs: [changes, prose-scan]`; `if:` = OR of src-backed groups + `architectural` (+ `ci_config` after WP07) `&& prose_only != 'true'`; checkout `fetch-depth: 0`; `setup-uv … python-version: '3.12'`; `uv run --frozen pytest tests/architectural -q -m "not performance and not stress and not timing" -n auto --dist loadfile` plus 4 `--deselect` |
| Fast-lane pattern | jobs `terminology` (≈:475), `layer-rules` (≈:508), `archive-freeze` (≈:531) | `if:` = the canonical fork guard **only**, no `needs`, 5–10 min timeouts; archive-freeze uses `fetch-depth: 0` |
| Router gate | job `router-gate` (≈:736-790) | `needs:` lists every non-gate job; classifies jobs-API rows **by display name** into a dict (`scripts/ci/router_gate.py::_parse_conclusions`) |
| Needs invariant | `test_dual_mode_contract.py:269` `test_router_gate_step_wiring_and_needs_invariant_are_pinned` | `set(needs) == {all jobs} - {"router-gate"}` |
| Oracle | `_ci_integrity_oracle.py:74-96` | `MUST_RUN_ALWAYS_ON_GATES` = {ruff, import-linter, regen-check, terminology, layer-rules, archive-freeze, docs-lint}; `HEAVY_BATTERY_GATE`; `HEAVY_BATTERY_NON_SRC_GROUPS` ({architectural} → {architectural, ci_config} after WP07); `assert_must_run_gates_wired` (≈:189) |
| Oracle consumer | `test_ci_integrity_oracle_nonvacuous.py:232-235` | `router.always_on_jobs >= MUST_RUN_ALWAYS_ON_GATES`; heavy ∈ `code_shard_jobs`; exact equality on heavy's groups |
| Ledger | `test_no_duplicate_suite_execution.py:241-276` `AUTHORIZED_PER_CHANGE_SUITE_JOBS`; `:230` `AUTHORIZED_SUITE_INVOCATIONS_PER_JOB = 1` | `("ci-router.yml","architectural-heavy"): "Path-routed lane: the architectural pole."` |
| Counting | `suite_executing_jobs` (≈:401-416) | counts one per `Gate` per `(workflow, job)`, so a 2-leg `include:` matrix counts **2** → `test_no_authorized_job_executes_the_suite_more_than_once` (≈:953) goes red. Also consumed by `real_suite_step_host` (≈:763) and `jobs_of` (≈:847) |
| Indirection guard | `indirect_command_form` (≈:1707) | flags a `${{ }}` in **command** position; `--battery-part ${{ matrix.shard }}` as an argument is fine |
| Golden tests | `tests/ci/test_ci_module_wiring.py:319` `_ALWAYS_ON_JOB_NAMES`, `:336` `_BASE_CONTEXT_ALL_FALSE`, golden tests ≈:362-445 | always-on jobs must have `if == _FORK_GUARD`; `jobs["architectural-heavy"]["needs"] == ["changes", "prose-scan"]` |
| Gate selection | `test_gate_selection_authority.py:58-67` | `selected_code_shards == frozenset({"architectural-heavy"})` for an architectural-only diff; `:107` always-on test lists `{"terminology", "layer-rules"}` |
| Matrix expansion | `_gate_coverage._matrix_includes` / `parse_workflow` | only a static `include:` **list** expands; `Gate.shard = mvars["shard"]`. This is the **first** static `include:` list in a change-triggered workflow (`ci-modules.yml` uses `fromJson`) |
| Upload pin | `ci-nightly.yml` | `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1` (15 uses; reuse this SHA, DIR-051) |
| Pinning inventory | `scripts/ci/derive_pinning_inventory.py` → `tests/release/pinning_rule_inventory.json` | 14 line-numbered rules in `test_no_duplicate_suite_execution.py`; **green on base `bc826fcbcb`** (#5523 closed by `e3794ded2d`, D-37) |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T049 – Red-first: the worker-policy guard

- **Purpose**: FR-002's regression guard. `-n auto` resolves to the **physical** core count
  (2 on the 4-vCPU runner). The guard pins a literal `-n 4`, equal to the registry `workers`,
  on every battery-class command, and forbids auto-detection and `-q`. It is red today
  because the router legs still run `-n auto -q` and `architectural-fast` does not exist.
- **Steps**:
  1. Create `tests/ci/test_xdist_worker_policy.py` with `pytestmark = pytest.mark.fast`
     (it runs in the `ci` module row).
  2. Declare the targets as data:
     ```python
     BATTERY_CLASS_JOBS: tuple[tuple[str, str], ...] = (
         ("ci-router.yml", "architectural-fast"),
         ("ci-router.yml", "architectural-heavy"),     # every matrix leg
         ("ci-nightly.yml", "architectural-backstop"),
         ("packs.yml", "built-in-corpus-suite"),
     )
     ```
     Read the expected worker count from `.github/ci-module-registry.yml` →
     `special_tiers.architectural.workers` (WP05). Never hard-code `4` in the comparison.
  3. Write one production function,
     `worker_policy_violations(workflows: Mapping[str, dict[str, Any]], *, workers: int) -> list[str]`.
     For each target job, take every logical pytest line: the job's `run:` steps through
     `gc.join_continuations`, keeping lines where `gc.suite_invocations(line)` is non-empty,
     and expanded per `include:` leg with `gc.substitute_matrix`. Tokenise with `shlex.split`,
     then report:
     - a job with **no** pytest line (non-vacuity; a renamed job must not silently pass);
     - a missing worker flag. Accept `-n N`, `-nN`, `--numprocesses N` and `--numprocesses=N`;
     - a value that is not the literal `str(workers)`. This catches `auto`, `logical` and any
       other number;
     - a present `-q`/`--quiet` (FR-002 log evidence);
     - for the router jobs only: a missing `--dist loadfile`.
  4. The live test, `test_battery_class_commands_use_the_registry_worker_count`, asserts
     `worker_policy_violations(live, workers=registry_workers) == []`. Load workflows with
     `gc.load_spliced_workflow`.
  5. Mutation tests, each on a deep copy of the live dicts and each calling the same function
     and asserting the specific message:
     - `-n 4` → `-n auto`;
     - `-n 4` → `--numprocesses=logical`;
     - `-n` removed;
     - `-q` re-added;
     - job key renamed, which is the non-vacuity case.
  6. Add `test_makefile_keeps_auto_detection_locally`, a C-005 sanity check: the `Makefile`
     still says `-n auto`. Delegate to, or simply call, the existing
     `tests/architectural/test_makefile_tier_topology.py` facts. Do not duplicate its parsing;
     a one-line `"-n auto" in Makefile text` check is enough.
  7. Run the file and confirm it is **red**. Record which targets fail. Expect the router
     fast job (missing) and the legs (`-n auto`, `-q`). The backstop (WP04) and Packs (WP09)
     should already pass. If Packs still carries `-q` or `-n auto`, that is a WP09 gap:
     raise it with the orchestrator, because `packs.yml` is not yours.
- **Files**: `tests/ci/test_xdist_worker_policy.py` (new).
- **Parallel?**: Yes with T050 (different files), both before any YAML edit.
- **Notes**: keep every helper ≤ 15 complexity (`_worker_value(tokens)`, `_pytest_lines(job)`).
  Do not mention the pinning-inventory subjects (`ci-quality.yml`, `sonarcloud`,
  `make test-fast`) in this file.

### Subtask T050 – Red-first: router shape and wiring tests

- **Purpose**: pin the new topology before writing YAML. Each test below fails on the
  planning base, for the reason given.
- **Steps**:
  1. `tests/ci/test_ci_module_wiring.py`:
     - Append `"architectural-fast"` to `_ALWAYS_ON_JOB_NAMES`. The existing golden prose-only
       test then asserts `jobs["architectural-fast"]["if"] == _FORK_GUARD`. It is red today
       with a `KeyError`.
     - `test_architectural_heavy_is_a_two_leg_include_matrix`: `strategy["fail-fast"] is False`
       (a literal boolean, deliberately **not** mode-keyed: the gates are deterministic and a
       red leg must not hide the other leg's reds). The legs' `shard` values must equal
       `[f"{i}/{n}" for i in 1..n]`, where `n` is the registry
       `special_tiers.architectural.shards.shard_count` (read the key path WP05 shipped).
       Each leg carries a filesystem-safe `label`. `needs` and `if:` stay as they are.
     - `test_battery_leg_display_names_are_distinct`: the heavy job's `name:` must contain
       `${{ matrix.shard }}`. Without it, `router_gate._parse_conclusions` stores two API rows
       under one display name, and a red leg can be **overwritten** by a green one.
     - `test_battery_commands_are_partitioned_and_plugin_loaded`: the fast job's pytest line
       contains `python -m pytest`, `-p scripts.ci.battery_partition_plugin` and
       `--battery-part fast`. The heavy line contains `--battery-part ${{ matrix.shard }}`.
       Both share the base `tests/architectural`, the marker
       `not performance and not stress and not timing` and the same four `--deselect`s. Parse
       these through `gc.parse_workflow` (`Gate.partition`, WP06), not by regex.
     - `test_battery_jobs_sample_memory_and_upload_junit`:
       - in each battery job, a step running `scripts.ci.memory_sampler start` comes **before**
         the pytest step;
       - a step running `scripts.ci.memory_sampler stop` with `if: always()` comes **after** it;
       - the pytest line has `--junitxml=out/reports/…`;
       - an `actions/upload-artifact@043fb46…` step has `if: always()`, and its artifact name
         differs per leg (it contains `${{ matrix.label }}`).
     - `test_battery_job_timeouts`: fast `timeout-minutes` ≤ 10, legs ≤ 30 (NFR-003).
     - `test_registry_battery_entry_matches_the_router_shape` (registry ↔ workflow equalities
       WP05 deliberately did **not** pin, because the jobs did not exist yet — see WP05 T021
       step 7; they live here, not in `test_module_shard_registry.py`):
       - `special_tiers.architectural.fast_gate.job == "architectural-fast"` and that job key
         exists in `ci-router.yml`;
       - `shards.shard_count == len(jobs["architectural-heavy"]["strategy"]["matrix"]["include"])`;
       - `workers ==` the literal `-n` value of the fast job and of every heavy leg — parse it
         with T049's `_worker_value` helper (import it; one tokenizer, not two).
       Red today: `KeyError` (no fast job, no `strategy`).
     - `test_golden_docs_only_pr_runs_the_fast_battery_but_not_the_legs`: under
       `_BASE_CONTEXT_ALL_FALSE` + `prose-scan.prose_only=False`, the heavy `if:` evaluates
       False, and the fast job has only the fork guard, so it is unconditional.
  2. `tests/architectural/test_dual_mode_contract.py`: add
     `test_router_gate_needs_include_the_battery_family`, asserting
     `{"architectural-fast", "architectural-heavy"} <= set(router-gate needs)`. The existing
     set-equality test then also covers the new job.
  3. `tests/architectural/test_gate_selection_authority.py`: add
     `test_fast_battery_job_is_always_on_and_never_a_code_shard`, asserting
     `"architectural-fast" in router.always_on_jobs`, that it is not in `code_shard_jobs`, and
     that it is selected for `docs/x.md`, a `ci_config`-only path and a `src/**` path. Extend
     `test_fast_arch_gates_are_always_on_and_selected_even_for_docs` to include it. Leave
     `test_architectural_only_diff_selects_the_heavy_battery`
     (`selected_code_shards == {"architectural-heavy"}`) **unchanged**: it proves the matrix is
     still one key.
  4. Run all new or extended tests and confirm they are **red**. Record that in the Activity Log.
- **Files**: `tests/ci/test_ci_module_wiring.py`, `tests/architectural/test_dual_mode_contract.py`, `tests/architectural/test_gate_selection_authority.py`.
- **Parallel?**: Yes with T049.
- **Notes**: the golden tests evaluate real `if:` strings with `_GhIfEvaluator`, which asserts
  that every referenced key is modelled. WP07 added `changes.ci_config` to
  `_BASE_CONTEXT_ALL_FALSE`; confirm it is there before you start.

### Subtask T051 – `architectural-fast` job, oracle membership, ledger row

- **Purpose**: FR-003. The deterministic ratchet and census gates report in about 2–3 min,
  on every PR shape.
- **Steps**:
  1. Insert the job directly **after `archive-freeze`**, before the heavy-battery comment
     block, in `ci-router.yml`:
     ```yaml
       # FAST always-on architectural gates (FR-003, #5510): the registry-held
       # roster (special_tiers.architectural.fast_gate) of deterministic ratchet /
       # census gates, run as --battery-part fast so a red shows in ~2-3 min on
       # every PR shape (docs-only included; C-002). Disjoint from the two
       # architectural-heavy legs by construction (test_battery_partition_proof.py).
       architectural-fast:
         if: (github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')
         name: architectural fast gates (ratchet/census, always-on)
         runs-on: ubuntu-24.04
         timeout-minutes: 10
         steps:
           - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
             with:
               fetch-depth: 0
           - name: Start memory sampler (NFR-005)
             run: python3 -m scripts.ci.memory_sampler start --out "$RUNNER_TEMP/memory-sampler.json"
           - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
             with:
               python-version: '3.12'
           - run: |
               uv sync --frozen --all-extras
               uv run --frozen python -m pytest tests/architectural \
                 -m "not performance and not stress and not timing" \
                 -n 4 --dist loadfile \
                 --deselect tests/architectural/test_no_legacy_terminology.py \
                 --deselect tests/architectural/test_layer_rules.py \
                 --deselect tests/architectural/test_pyproject_shape.py \
                 --deselect tests/architectural/test_archive_root_byte_identical.py \
                 -p scripts.ci.battery_partition_plugin --battery-part fast \
                 --junitxml=out/reports/xunit-architectural-fast.xml
           - name: Report peak memory (NFR-005)
             if: always()
             run: python3 -m scripts.ci.memory_sampler stop --out "$RUNNER_TEMP/memory-sampler.json"
           - name: Upload battery junit (timings recapture source, D-29)
             if: always()
             uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
             with:
               name: ci-router-architectural-fast-junit
               path: out/reports/
               if-no-files-found: warn
     ```
     Copy the fork-guard string, every SHA and the deselect list **from the live file**. Do not
     retype them from this prompt. Use the exact sampler CLI that WP11 shipped (read its
     module docstring).
  2. Add `architectural-fast` to `router-gate.needs`, next to `archive-freeze`.
  3. `_ci_integrity_oracle.py`: add `"architectural-fast"` to `MUST_RUN_ALWAYS_ON_GATES`, and
     extend the comment (FR-003, #5510: the always-on fast roster; disjoint from the
     code-scoped heavy legs). `HEAVY_BATTERY_GATE` and `HEAVY_BATTERY_NON_SRC_GROUPS` stay
     as they are.
  4. `test_no_duplicate_suite_execution.py`: add the ledger row
     `("ci-router.yml", "architectural-fast")` with the reason "Always-on lane: the
     registry-held fast roster of deterministic ratchet/census gates (FR-003). Pairwise
     disjoint with both architectural-heavy legs via --battery-part (proven by
     test_battery_partition_proof.py), so no battery test runs twice."
- **Files**: `.github/workflows/ci-router.yml`, `tests/architectural/_ci_integrity_oracle.py`, `tests/architectural/test_no_duplicate_suite_execution.py`.
- **Parallel?**: No (after T049/T050).
- **Notes**:
  - Always-on is the operator decision (DM 01M3V1FAQV07WJF3RYAFN9J7GC; D-03). It costs about
    2 runner-min per docs-only PR and keeps raw-source readers always-on (C-002).
  - No `needs:`, so it starts immediately. NFR-002 (≤ 5 min from pipeline start) depends on it.
  - The sampler `start` step runs after checkout (the script is in the repo) and before
    `uv sync`, so the baseline is the idle runner. It uses system `python3` (stdlib only).

### Subtask T052 – `architectural-heavy` as a 2-leg matrix; per-leg duplicate counting

- **Purpose**: FR-004. Two file-partitioned legs, each about 7–10 min on 4 workers, against
  23.4 min today. The duplicate-suite ledger must count per leg, or the matrix trips its own
  guard.
- **Steps**:
  1. Reshape the job and keep the key, `needs` and `if:` byte-identical (they include
     `ci_config` from WP07):
     ```yaml
       architectural-heavy:
         name: architectural battery (heavy, code-scoped) ${{ matrix.shard }}
         runs-on: ubuntu-24.04
         timeout-minutes: 30
         needs: [changes, prose-scan]
         if: >-
           <unchanged>
         strategy:
           # Deterministic gates: a red in leg 1 must not cancel leg 2's verdict
           # (avoids a second ~10-min round trip). Deliberately NOT mode-keyed.
           fail-fast: false
           matrix:
             include:
               - shard: '1/2'
                 label: '1-of-2'
               - shard: '2/2'
                 label: '2-of-2'
         steps:
           # checkout (fetch-depth: 0, keep its comment), sampler start, setup-uv 3.12, then:
           #   uv run --frozen python -m pytest tests/architectural \
           #     -m "not performance and not stress and not timing" \
           #     -n 4 --dist loadfile <same 4 --deselect> \
           #     -p scripts.ci.battery_partition_plugin --battery-part ${{ matrix.shard }} \
           #     --junitxml=out/reports/xunit-architectural-heavy-${{ matrix.label }}.xml
           # sampler stop (if: always()), upload-artifact
           #   name: ci-router-architectural-heavy-${{ matrix.label }}-junit (if: always())
     ```
     The matrix variable **must be named `shard`**: `_gate_coverage.parse_workflow` reads
     `mvars["shard"]` for `Gate.shard`. The number of legs must equal the registry
     `shard_count`; the plugin also fails closed at runtime (D-23). `label` exists because
     artifact names cannot contain `/`.
  2. Rewrite the comment block above the job. Keep the authority-#2 explanation, and add the
     partition and the fast sibling, the per-leg evidence (workers, sampler, junit), and
     pointers to `contracts/router-two-authority-amendment.md` A2 and
     `test_battery_partition_proof.py`. If WP07 did not already add a pointer to the
     amendment file in the `ci-router.yml` header comment, add one.
  3. `test_no_duplicate_suite_execution.py`, per-leg counting (D-20):
     - Add `LegKey = tuple[str, str, str | None]` and
       `suite_invocations_per_leg(workflows_dir, *, makefile=None) -> dict[LegKey, int]`,
       keyed `(path.name, gate.job, gate.shard)`.
     - Redefine `suite_executing_jobs` as `(workflow, job) -> max(count over that job's legs)`.
       Its callers (`unauthorized_suite_jobs`, `real_suite_step_host`, `jobs_of`, the live
       tests) keep their `dict[JobKey, int]` contract.
     - Update both docstrings: the ledger authorises one execution **per leg**. A leg is a
       static `include:` entry, labelled by its `shard` variable.
     - Fault-injection pair, written red-first **before** the counting change. Write each
       fixture as a tmp workflow, or a copy of the real tree with an injected job:
       - `test_matrix_legs_each_running_the_suite_once_count_as_one`: a 2-leg `include:` job
         with one pytest step gives `suite_executing_jobs == 1` for that job;
       - `test_a_matrix_leg_running_the_suite_twice_is_detected`: the same job with two pytest
         steps gives 2, and is reported by the same comparison
         `test_no_authorized_job_executes_the_suite_more_than_once` uses. Extract that
         comparison into a small production function if needed, so the live test and the
         fault injection share it.
     - Reword the `architectural-heavy` ledger reason: "Path-routed lane: the architectural
       battery as two file-partitioned matrix legs (--battery-part 1/2, 2/2), each one
       execution; pairwise disjoint with each other and with architectural-fast (proven by
       test_battery_partition_proof.py)."
  4. `real_suite_step_host` needs a workflow whose sole suite job runs once and whose command
     appears exactly once in the file's own text. The heavy legs share **one** text line, so
     `ci-router.yml` hosts several suite jobs and is not selected. Confirm the derived host is
     still found (run the mutation-1/2/3 tests).
  5. **Do not edit the partition proof** (`tests/architectural/test_battery_partition_proof.py`
     is owned by WP06 only — not by this WP; lane split, owned_files disjointness). Its
     transitional "exactly one unpartitioned gate" shape branch, marked by WP06, still accepts
     the fully partitioned router this WP produces, so the live proof stays green over the three
     partitioned gates. **The transitional branch is removed by a post-consolidation orchestrator
     fold (tasks.md closeout)** on the mission branch after lane consolidation, once this router
     shape has landed, together with its positive control.
- **Files**: `.github/workflows/ci-router.yml`, `tests/architectural/test_no_duplicate_suite_execution.py`.
- **Parallel?**: No.
- **Notes**:
  - The router gate needs no other change. The legs post two API rows with distinct display
    names (T050), and both are classified.
  - `gate_selection` and the oracle still see one key, so
    `selected_code_shards == {"architectural-heavy"}` stays green.
  - C-004: do not add any battery job to the required-check list. The required check remains
    `router gate`.

### Subtask T053 – Sampler, junit, timeouts on fast and both legs

- **Purpose**: NFR-005 evidence (peak memory per job), NFR-003 headroom, and the junit that
  WP05's `capture_shard_timings.py --suite architectural --from-junit` consumes for timings
  refresh (D-29).
- **Steps**:
  1. Confirm the three steps in each battery job: sampler `start` before setup-uv; sampler
     `stop` with `if: always()` after pytest; upload with `if: always()`.
  2. Timeouts: fast `10`, legs `30`. Legs are expected at 7–10 min, which satisfies NFR-003's
     "≤ 60% of the job timeout on the slowest recorded run" with a wide margin. Re-base later
     from evidence; never above 30.
  3. Drop `-q` everywhere in the battery commands, so xdist prints `created: 4/4 workers` and
     `4 workers [N items]`. The plugin (WP05) additionally lists `gw0..gw3` and the slowest
     test in the step summary.
  4. Run `actionlint` if it is available locally (optional). Run `uv run --frozen python -c
     "import yaml,sys; yaml.safe_load(open('.github/workflows/ci-router.yml'))"` as a minimum
     syntax check.
- **Files**: `.github/workflows/ci-router.yml`.
- **Parallel?**: No.
- **Notes**: watch `test_module_length_agreement.py::test_non_allowlisted_modules_agree_with_live_collection`.
  It has a 119.5 s setup under 2 workers, and SMT contention at 4 workers may push it toward
  the 180 s NFR-003 bound (R1 §7). If the dispatched runs show it over 180 s, record it and
  raise a follow-up; at closeout NFR-003 then needs either the fix or an operator waiver the
  orchestrator records in the evidence file. The remedy is narrowing that setup, never a timeout bump.

### Subtask T054 – Companion tests green; regenerate the pinning inventory; evidence

- **Purpose**: close every same-commit pin, then collect the measurements that NFR-001,
  NFR-002, NFR-003 and NFR-005 are judged on.
- **Steps**:
  1. Run the companion and pin files (see Test Strategy). Every red-first test from
     T049/T050 is now green, and these neighbours must also be green:
     - `test_ci_integrity_oracle_nonvacuous.py`;
     - `test_ci_router_transcription_guards.py`;
     - `test_ci_quality_path_filters.py`;
     - `test_workflow_coherence.py`;
     - `test_battery_partition_proof.py` (WP06; run it, do not edit it — its
       transitional-branch removal is a post-consolidation orchestrator fold, tasks.md closeout), now over three partitioned gates;
     - `test_module_shard_registry.py` (WP05's pins, unchanged by this WP: schema, trigger,
       and base == every `gc.Gate` of `shards.job`, which now iterates both legs). The
       `fast_gate.job`, `shard_count == len(include)` and `workers ==` literal `-n` equalities are
       **T050's** `test_registry_battery_entry_matches_the_router_shape` in
       `tests/ci/test_ci_module_wiring.py`, not this file (this WP does not own it);
     - `test_nightly_architectural_backstop.py` (WP04), whose family check now compares the
       backstop against three router gates.
  2. Regenerate: `python3 scripts/ci/derive_pinning_inventory.py`, then `--check`, then
     `pytest tests/release/test_pinning_inventory_fresh.py`. `tests/release/pinning_rule_inventory.json`
     is an out-of-map companion, so record a one-line rationale in the Activity Log. Never
     hand-merge it: on a lane conflict, regenerate (D-25).
  3. Evidence (C-011), after the branch is pushed under the mission's push authorization
     (never to `main`): the orchestrator or operator dispatches
     `gh workflow run ci-router.yml --ref issue-5510-ci-runtime-stabilisation -f mode=pr` and
     `-f mode=full`. The PR's own CI runs also select the battery, because the diff touches
     `ci_config` paths. For each run, record:
     - the run id;
     - the fast-job and per-leg durations;
     - the `created: 4/4 workers` line;
     - the `peak_rss_bytes=` line;
     - the slowest test;
     - the fast job's finish time relative to pipeline start.

     The targets are NFR-001 (slowest of fast/legs, median ≤ 14 min over ≥ 3 runs), NFR-002
     (fast ≤ 5 min from start), NFR-003 (≤ 60% of the timeout; slowest test ≤ 180 s) and
     NFR-005 (< 12 GB). Put them in the Activity Log; the **orchestrator records them** in
     `kitty-specs/ci-runtime-stabilisation-01M3TZH6/evidence/ci-measurements.md` at closeout
     (tasks.md "Orchestrator closeout"), not WP19 and not this WP.
- **Files**: `tests/release/pinning_rule_inventory.json` (regenerated companion).
- **Parallel?**: No (last).
- **Notes**: a red you did not cause (for example a pre-existing P0) goes through the
  baseline-red gotcha: confirm it is red on the merge-base, then note it in the PR. Never retry
  it to green.
  **Pre-existing Failure Reporting Rule (charter, binding):** such a red needs a GitHub issue — cite the existing one or open one (command, failure summary, why it is pre-existing) — before you continue past it.

## Test Strategy

Red-first: T049 and T050 files are red on the planning base (fast job missing, `-n auto -q`,
single non-matrix heavy job) and green on the tip. The T052 fault-injection pair is red before
the per-leg counting change.

```bash
uv run --frozen pytest tests/ci/test_xdist_worker_policy.py tests/ci/test_ci_module_wiring.py \
  tests/ci/test_nightly_architectural_backstop.py tests/ci/test_fork_guard.py \
  tests/ci/test_memory_sampler.py tests/ci/test_battery_partition_plugin.py -q
# Specific architectural gate files this change implicates (never the bare directory):
uv run --frozen pytest tests/architectural/test_dual_mode_contract.py \
  tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_no_duplicate_suite_execution.py \
  tests/architectural/test_ci_integrity_oracle_nonvacuous.py \
  tests/architectural/test_ci_router_transcription_guards.py \
  tests/architectural/test_ci_quality_path_filters.py \
  tests/architectural/test_workflow_coherence.py \
  tests/architectural/test_battery_partition_proof.py \
  tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_local_gate_parity.py \
  tests/architectural/test_marker_job_completeness.py -q
uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
make test-fast
uv run --frozen ruff check tests/ci/test_xdist_worker_policy.py tests/ci/test_ci_module_wiring.py \
  tests/architectural/_ci_integrity_oracle.py tests/architectural/test_no_duplicate_suite_execution.py \
  tests/architectural/test_dual_mode_contract.py tests/architectural/test_gate_selection_authority.py
uv run --frozen ruff format --check .
uv run --frozen mypy tests/ci/test_xdist_worker_policy.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
# Partition sanity, collection only. Reuse WP05's base args: without the base marker and the
# four deselects the plugin raises UsageError BY DESIGN (invocation != registry base).
B='-m "not performance and not stress and not timing" --deselect tests/architectural/test_no_legacy_terminology.py --deselect tests/architectural/test_layer_rules.py --deselect tests/architectural/test_pyproject_shape.py --deselect tests/architectural/test_archive_root_byte_identical.py'
for p in fast 1/2 2/2; do
  eval uv run --frozen python -m pytest tests/architectural $B -p scripts.ci.battery_partition_plugin --battery-part $p --collect-only -q | tail -1
done   # the three counts sum to the unpartitioned base count
```

Record the exact commands and the pass/fail counts in the Activity Log and the PR's
*Tests run* section.

## Risks & Mitigations

- **Hot file `ci-router.yml`**: WP12 lands after WP07–WP10 in one sequenced lane (D-30).
  Rebase on their merged state and re-read every anchor.
- **Router-gate dict collision masks a red leg**: distinct display names via
  `${{ matrix.shard }}`, pinned by T050.
- **Duplicate-suite guard reds on its own matrix**: per-leg counting plus the fault-injection
  pair (T052).
- **Partition drift between plugin, registry and workflow**: WP06's proof, WP05's registry
  pins, and the plugin's runtime self-check (D-23) all run in CI.
- **SMT oversubscription or memory at 4 workers**: the sampler records the peak. A peak of
  10 GB or more raises a warning; 12 GB or more raises an error annotation. Fall back to
  `-n 3` only by operator decision, as a registry `workers` edit plus the literal.
- **NFR-001 misses on the first runs because timings are seeded**: WP14 seeded the per-file
  durations. Recapture from these runs' junit (WP05 capture mode) if the leg skew is over 20%.
- **Inventory line drift**: the base inventory is fresh (#5523 closed, D-37); your regeneration
  covers your own line shifts plus any lane-a regeneration you merged in. Never hand-merge.

## Review Guidance

- Check out the planning base and run `test_xdist_worker_policy.py` plus the T050 tests:
  they are **red**. On the tip they are green.
- Diff the three battery commands: identical base args, `python -m pytest`, `-p` plugin,
  `--battery-part fast` / `${{ matrix.shard }}`, `-n 4`, `--dist loadfile`, no `-q`, and
  `--junitxml`.
- Matrix: a static `include:` list, variable `shard`, `fail-fast: false` as a literal, the
  name contains `${{ matrix.shard }}`, and artifact names use `label`.
- `HEAVY_BATTERY_GATE` is still a single string. `gate_selection.py`, `_gate_coverage.py`,
  the registry, `packs.yml`, `ci-nightly.yml` and `pytest.ini` are untouched.
- `tests/architectural/test_battery_partition_proof.py` is untouched by this WP and green over
  the three partitioned gates (its transitional branch is removed by the post-consolidation orchestrator fold, tasks.md
  closeout — not here).
- `test_registry_battery_entry_matches_the_router_shape` pins `fast_gate.job`,
  `shard_count == len(include)` and `workers ==` the literal `-n`.
- `MUST_RUN_ALWAYS_ON_GATES`, `router-gate.needs` and the ledger row are all updated. Per-leg
  counting has its fault-injection pair, and both tests call the production comparison.
- The inventory was regenerated with a rationale. Evidence run ids are recorded or explicitly
  pending dispatch.
- Confirm the implementer ran mypy as well as pytest on the new typed test file and that its
  diagnostics passed.
- **Definition of Done**: FR-002, FR-003 and FR-004 are wired and statically guarded. C-004
  holds. NFR-001, NFR-002, NFR-003 and NFR-005 have dispatched-run evidence recorded (≥ 3 runs
  each), or the WP is explicitly handed to the orchestrator for the remaining runs.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
