---
work_package_id: WP05
title: Battery partition plugin and registry battery entry
dependencies:
- WP03
requirement_refs:
- FR-003
- FR-004
- FR-013
- C-010
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
phase: Phase 3 - Battery partition
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/battery_partition_plugin.py
- tests/ci/test_battery_partition_plugin.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/battery_partition_plugin.py
- tests/ci/test_battery_partition_plugin.py
- .github/ci-module-registry.yml
- tests/architectural/test_module_shard_registry.py
- scripts/ci/capture_shard_timings.py
- tests/ci/test_capture_shard_timings.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Battery partition plugin and registry battery entry

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

This WP builds the **runtime half** of the battery partition and makes the registry tell the
truth about the battery. It does **not** edit any workflow (WP12 reshapes `ci-router.yml`) and
does not touch `_gate_coverage.py` (WP06 adds the static partition proof).

1. **`scripts/ci/battery_partition_plugin.py`** (FR-003/FR-004, D-02, D-23): a pytest plugin,
   loaded with `python -m pytest … -p scripts.ci.battery_partition_plugin --battery-part <fast|i/n>`,
   that makes one pytest invocation execute exactly one part of the base battery:
   - parts are computed **deterministically in every process** — controller and every xdist
     worker — from the registry + timings via `scripts.ci.shard_select` (WP02:
     `enumerate_base_files`, `battery_parts`). A digest shipped through xdist `workerinput`
     cross-checks that each worker computed the same part (D-23);
   - `pytest_ignore_collect` skips every enumerated base file **not** in the part; it never
     ignores directories, `conftest.py`, `_*.py` helpers or non-enumerated files (contract
     semantics 3: an enumeration gap appears as an overlap, never a silent loss);
   - a **runtime self-check** fails the session when any executed test's file is outside the
     part (D-23);
   - it fails closed (`pytest.UsageError`) when the invocation's paths / marker / whole-file
     deselects differ from the registry `base`, when `i/n` disagrees with `shard_count`, and —
     under `GITHUB_ACTIONS` only — when the xdist worker count differs from registry `workers`;
   - it reports FR-005 timing mismatches once (controller), and prints a per-part summary
     (files, predicted load, workers seen, slowest test, per-file seconds; roster budget
     overruns and any test > 180 s as `::warning::`) to the log and `$GITHUB_STEP_SUMMARY`.
2. **Registry** `special_tiers.architectural` rewritten (FR-013, D-26) to hold only facts with
   no other home: trigger descriptor, workers, base selection, fast roster with budgets,
   shard count, granularity, timings key. The false `always_on: true`, `filter_group: null` and
   the stale note go. No trigger-group list, no nightly-backstop key.
3. **Registry pin tests** in `test_module_shard_registry.py` (T021) assert the new entry against
   the workflows and the base enumeration; the old test that pinned the drift is replaced.
4. **`capture_shard_timings.py --suite architectural --from-junit DIR`** (D-29): per-file
   battery timings from CI junit artefacts, merged into
   `.github/ci-shard-timings.json` → `battery_file_durations.architectural` with
   `battery_capture_provenance.architectural`. WP14 seeds those keys first (from census logs);
   this mode is the reproducible refresh path.

## Context & Constraints

- Read first: `research.md` decision log, especially **D-02, D-05, D-06, D-23, D-24, D-26, D-28,
  D-29** (D-22…D-34 supersede R1 where they differ), then R1 §1 "D-PLUG", §4a-§4e, §5;
  `contracts/battery-partition.md`; `data-model.md` (Battery base selection, Fast-gate roster,
  Battery shard partition, Shard timings).
- **Superseded R1 details — do NOT implement**: R1 §4a's `non_src_filter_groups` and
  `nightly_backstop` registry keys (D-26 removed both); R1's "compute parts in `pytest_configure`
  on the controller only" (D-23: every process — under `--dist loadfile` the controller does not
  collect, the workers do).
- Depends on WP02 (`enumerate_base_files`, `resolve_file_weights`, `battery_parts`,
  `BatteryPartition`, `report_mismatch` in `scripts/ci/shard_select.py`) and WP03 (last registry
  edit before you). Do not re-implement any of them (C-010); if one is missing or wrong, stop and
  raise it with the orchestrator.
- C-009: no full local run of `tests/architectural`. Collect-only runs with the plugin are allowed
  (they are the quickstart's partition smoke).
- Lane discipline: `uv run --frozen …`; never `git stash`. Terminology: Mission; "gate selection".
- Plugin hooks delegate to pure helpers, each ≤ 15 complexity (D-28); `mypy --strict` and ruff
  clean; constants for repeated literals; every helper unit-tested.
- Do not name `make test-fast`, `ci-quality.yml` or `sonarcloud` in new files (they are the
  pinning-inventory subjects scanned under `scripts/` and `tests/`).

### Current-state anchors (verified 2026-10-01; anchor by job name — router lines drift)

| What | Where |
|---|---|
| Battery job | `.github/workflows/ci-router.yml` job `architectural-heavy` (≈ :555-606): `uv run --frozen pytest tests/architectural -q -m "not performance and not stress and not timing" -n auto --dist loadfile` + 4 `--deselect` (terminology, layer_rules, pyproject_shape, archive_root_byte_identical). Console-script `pytest` today; WP12 switches it to `python -m pytest … -p scripts.ci.battery_partition_plugin` |
| Always-on arch lanes | jobs `terminology` (`pytest tests/architectural/test_no_legacy_terminology.py`), `layer-rules` (`test_layer_rules.py test_pyproject_shape.py`), `archive-freeze` (`test_archive_root_byte_identical.py`) — their union is exactly the 4 deselects |
| Registry entry | `.github/ci-module-registry.yml:864-878` `special_tiers.architectural`: `job: architectural-heavy`, `always_on: true` (false since #5168), `deserialized: true`, `filter_group: null`, note "minus the 3 fast always-on gates" (it is 4 deselects since #4365) |
| Out-of-matrix reason | same file ≈ :468-475, `tests/architectural` reason "runs the full tests/architectural tree … a module row would only double-run it" |
| Pin that encodes the drift | `tests/architectural/test_module_shard_registry.py:331-368` `test_special_tiers_encode_heavy_pole_deserialization` (asserts `always_on is True`, `filter_group in (None, "")`; its second half pins the retired `integration_tests_next` tier and the nightly `integration-next` wiring — keep that half) |
| Only reader of `special_tiers` | that test (grep over `src`, `scripts`, `tests`) |
| Oracle constants | `tests/architectural/_ci_integrity_oracle.py:89` `HEAVY_BATTERY_GATE = "architectural-heavy"`, `:96` `HEAVY_BATTERY_NON_SRC_GROUPS` |
| Router model | `scripts/ci/gate_selection.py` `load_router()` → `Router.job_gates`, `.always_on_jobs`, `.code_shard_jobs` |
| Gate model | `from tests.architectural import _gate_coverage as gc`; `gc.parse_workflow(path)` → `Gate(workflow, job, shard, paths, ignores, marker_expr)`; `ignores` includes `--deselect` entries |
| Capture CLI | `scripts/ci/capture_shard_timings.py:246-255` `_parse_args`: `--module` is `required=True`; `--write` xor `--output` |
| Capture tests | `tests/ci/test_capture_shard_timings.py`, incl. `test_script_help_works_without_installed_package` (`python -I -S … --help` from a temp cwd: stdlib-only import path) |
| pytest / xdist | 9.0.3 / 3.8.0; junit default family `xunit2` (testcase `classname` dotted, no `file` attribute; `time` = setup+call+teardown) |
| Base size | 235 enumerated files (239 − 4 deselected); 3394 tests under the base marker (collect-only on `bc826fcbcb`, 2026-10-01; 234 / 3357 at planning — D-37) |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T018 – Red-first: subprocess tests — each part collects only its files at `-n 0` and `-n 2`; out-of-part execution fails

- **Purpose**: Pin the partition contract under the real execution model (xdist workers collect)
  before the plugin exists (D-23 architect MAJOR).
- **Harness decision**: this repo does not enable `pytester` (no rootdir conftest loads it; see the
  note in `tests/architectural/test_home_owner_behaviour.py:24-28`). Drive pytest in a
  **subprocess** over a synthetic tree instead. This is also the more faithful test: run with
  `cwd = REPO_ROOT` and **no `PYTHONPATH`**, so `-p scripts.ci.battery_partition_plugin` must
  import exactly as it will on CI (`python -m pytest` puts cwd on `sys.path` for the controller;
  xdist workers must resolve it too — this test is where you find out).
- **Steps** (in `tests/ci/test_battery_partition_plugin.py`):
  1. Fixture `battery_tree(tmp_path)`: `tmp_path/pytest.ini` (`[pytest]` only), a synthetic base
     `tests/architectural/` with ~10 `test_*.py` files (one nested in a subdir), one `conftest.py`
     defining a fixture used by two files, one `_helper.py` imported by a test, and one whole-file
     deselected `test_deselected.py`. Each test body is trivial (`assert True`). A fixture
     registry `tmp_path/registry.yml` with a `special_tiers.architectural` entry in the T020
     schema (roster = 3 of the files, `shard_count: 2`, `workers: 2`) and a timings file
     `tmp_path/timings.json` with `battery_file_durations.architectural` for some files.
  2. Helper `run_part(part, *, n)` → `subprocess.run([sys.executable, "-m", "pytest", str(tmp_path / "tests/architectural"), "-m", BASE_MARKER, "--deselect", "tests/architectural/test_deselected.py", "-p", "scripts.ci.battery_partition_plugin", "--battery-part", part, "--battery-registry", str(registry), "--battery-timings", str(timings), "--rootdir", str(tmp_path), "-c", str(tmp_path / "pytest.ini"), *(["-n", str(n), "--dist", "loadfile"] if n else []), "--junitxml", str(junit), "-p", "no:cacheprovider", "-q"], cwd=REPO_ROOT, env=<os.environ minus PYTHONPATH and GITHUB_ACTIONS>, …)`.
     The positional path is absolute (cwd is the real repo, whose own `tests/architectural`
     must not be touched); `--deselect` node ids are `--rootdir`-relative, as pytest matches
     them. So the plugin resolves registry base paths and runs the enumeration against
     `config.rootpath`, and normalises positional args to rootpath-relative before comparing
     them with `base.paths`. On CI cwd == rootpath, so both forms coincide.
  3. Executed-file oracle: parse the junit file (`xml.etree.ElementTree`), map each testcase
     `classname` to a file (see T022's resolver — reuse it, do not write a second one), and assert
     the executed file set == the part computed by `shard_select.battery_parts` from the same
     fixture data. Do this for `fast`, `1/2`, `2/2`, at `n=0` **and** `n=2`. Assert the union of
     the three executed sets == the enumerated base and that they are pairwise disjoint.
     (`--collect-only` cannot prove the xdist path: xdist disables distribution under
     `--collect-only`, so the `-n 2` cases must really run the trivial tests.)
  4. Fail-closed cases: `--battery-part 3/2` and `--battery-part 1/3` (vs `shard_count: 2`) →
     non-zero exit with a `UsageError` message naming the registry; a missing `-m` or a different
     deselect set → `UsageError`; with `GITHUB_ACTIONS=true` and `-n 1` vs `workers: 2` →
     `UsageError`; without `GITHUB_ACTIONS`, `-n 1` is accepted.
     Accepted equivalents (no `UsageError`): the base deselects passed as
     `--ignore=tests/architectural/test_deselected.py` instead of `--deselect`; and
     `GITHUB_ACTIONS=true` + `--collect-only` with no `-n` (the gate model's
     `collect_job_nodeids` shape — WP06 T024 step 7 drives the real call). A directory
     `--ignore` is still rejected.
  5. Self-check positive control: add a synthetic `conftest.py` hook `pytest_collect_file` that
     returns a `pytest.Module` for a file named `extra_check.py` (not matching `python_files`, so
     it is outside the enumeration) — the realistic enumeration-gap case. Running any part must
     exit non-zero with the self-check message naming `extra_check.py`.
  6. Inert without the flag: `-p scripts.ci.battery_partition_plugin` with no `--battery-part`
     collects everything.
  6a. **FR-005 production path (battery half)**: one subprocess case where one enumerated base
     file has **no** entry in `timings.json`, run with `GITHUB_STEP_SUMMARY=<tmp file>` in the env
     (and `-n 2`, so the "controller only" rule is exercised). Assert the **plugin's** stdout
     contains exactly one line starting `::warning title=shard timings::` naming that file (not
     one per worker), and that the step-summary file gained the matching mismatch line. This is
     the end-to-end proof that the plugin calls `shard_select.report_mismatch` on the real path —
     the helper's own unit tests (WP02) do not prove the wiring.
  7. Pure-helper unit tests (fast): `parse_part`, the invocation-vs-base comparison, the executed-
     outside-part detector, the digest function, the summary renderer, the `GITHUB_ACTIONS`
     worker check.
  8. Mark subprocess tests `@pytest.mark.slow`, pure ones `@pytest.mark.fast`. Commit red.
- **Files**: `tests/ci/test_battery_partition_plugin.py` (new).
- **Parallel?**: No — gates T019.
- **Ordering**: step 3's junit oracle reuses T022's classname resolver
  (`capture_shard_timings.junit_file_seconds`). Land that helper (T022 step 2, with its own unit
  tests) **before** T018 can go green; the red-first commit may import it and fail on
  `ImportError`/`AttributeError` together with the missing plugin, but do not write a private
  resolver in the test to get around the order.
- **Notes**: Keep the synthetic tree tiny so the six real runs finish in a few seconds.

### Subtask T019 – Implement the plugin

- **Purpose**: Apply the partition inside pytest with a literal, statically readable flag
  (D-02), deterministic in every process (D-23), using the one enumeration (D-24).
- **Steps**:
  1. Module docstring: purpose, invocation form, the every-process rule, the never-ignore list,
     and the self-check. `__all__`.
  2. `pytest_addoption(parser)`: group `battery-partition`; `--battery-part`
     (`fast` or `i/n`), `--battery-registry` (default `<rootpath>/.github/ci-module-registry.yml`),
     `--battery-timings` (default `<rootpath>/.github/ci-shard-timings.json`).
  3. Pure helpers (each small, typed, tested):
     - `parse_part(value) -> PartSpec` (`fast` or `(i, n)`, `1 <= i <= n`);
     - `load_battery_spec(registry_mapping) -> BatterySpec` (frozen dataclass mirroring the T020
       schema; raises `ValueError` with the key path on any schema problem);
     - `load_battery_timings(timings_mapping, key) -> dict[str, float]` (missing key → `{}`);
     - `invocation_mismatches(args, marker, deselects, spec) -> list[str]` — compares resolved
       positional paths, the `-m` expression and the whole-file deselect set with `spec.base`.
       A whole-file `--ignore=<file>` (and `--ignore <file>`) counts as equivalent to
       `--deselect <file>` for this comparison: the gate model's `collect_job_nodeids`
       (`tests/architectural/_gate_coverage.py:1940`) passes the base deselects as
       `--ignore=<file>`, and WP06 forwards `--battery-part` through it. Compare the **union** of
       whole-file `--deselect` and `--ignore` file paths with `base.deselect`; a directory
       `--ignore` or a node-level `--deselect file::test` is still a mismatch;
     - `compute_partition(spec, root, timings) -> BatteryPartition` →
       `enumerate_base_files(spec.base.paths, deselect=spec.base.deselect, root=root)` then
       `battery_parts(base, spec.roster_paths, spec.shard_count, timings)`;
     - `part_digest(files) -> str` (sha256 of the sorted newline-joined paths);
     - `files_outside_part(executed_relpaths, part_files) -> list[str]`.
  4. `pytest_configure(config)` (every process, only when `--battery-part` is set): load spec +
     timings (`yaml` imported here, lazily), validate (part vs `shard_count`, invocation vs base;
     under `GITHUB_ACTIONS` also `config.option.numprocesses == spec.workers` on the controller —
     **skipped under `--collect-only`**, which runs no tests and is how the gate model collects a
     part without `-n`; on CI, `GITHUB_ACTIONS` is set for those collections too),
     compute the partition, stash `PartitionState(part_files, enumerated, digest)` on
     `config.stash`. On a worker (`hasattr(config, "workerinput")`), compare its digest with
     `config.workerinput["battery_part_digest"]` and raise `pytest.UsageError` on disagreement.
     Report FR-005 mismatch (`shard_select.report_mismatch`) **only on the controller**.
  5. `@pytest.hookimpl(optionalhook=True) pytest_configure_node(node)` (controller): put the
     digest into `node.workerinput["battery_part_digest"]`.
  6. `pytest_ignore_collect(collection_path, config)`: return `True` iff the path is a **file**
     whose rootpath-relative posix path ∈ `enumerated − part_files`; otherwise return `None`
     (never `False` — `False` forces collection and overrides other ignore logic).
  7. Self-check: `pytest_runtest_logreport(report)` on the controller (or the single process)
     records the file of each `when == "call"` (and setup errors) report; `pytest_sessionfinish`
     computes `files_outside_part`; when non-empty, print a red `::error::` line naming them and
     set `session.exitstatus = pytest.ExitCode.TESTS_FAILED` (respect an already-worse status).
  8. Evidence/summary: `@pytest.hookimpl(optionalhook=True) pytest_testnodeready(node)` collects
     worker ids (gw0…); accumulate per-file seconds from reports; `pytest_terminal_summary` prints
     part, file count, predicted load, workers seen, slowest test, top-10 per-file seconds;
     `::warning::` for any roster file over its `budget_seconds` (fast part) and any single test
     > 180 s (NFR-003); one summary block appended to `$GITHUB_STEP_SUMMARY` when set. Runtime
     overruns are warnings only (runner spread is ~1.77× — a hard runtime budget would mint a
     flake class; the static budget check is WP14's test).
  9. `uv run --frozen mypy --strict scripts/ci/battery_partition_plugin.py`; ruff clean.
- **Files**: `scripts/ci/battery_partition_plugin.py` (new).
- **Parallel?**: After T018.
- **Notes**: Under `--dist loadfile` each file lands on one worker, so file-granularity parts
  keep file-scoped fixtures and the FR-006 per-file caches intact.

### Subtask T020 – Registry `special_tiers.architectural` schema + fast roster

- **Purpose**: FR-013 — the registry entry stops being a second, wrong authority (D-26).
- **Steps**:
  1. Replace `.github/ci-module-registry.yml` `special_tiers.architectural` (keep the retired-tier
     comment above it) with:
     ```yaml
     architectural:
       # Facts with no other home (D-26). Trigger GROUPS are not copied here: the router job
       # `if:` is the authority, mirrored only by _ci_integrity_oracle.HEAVY_BATTERY_NON_SRC_GROUPS.
       trigger: code_scoped        # pinned against gate_selection: shards.job is a code-shard job
       deserialized: true
       workers: 4                  # CI only (C-005); FR-002 literal `-n 4` lands with WP12
       base:
         paths: [tests/architectural]
         marker: "not performance and not stress and not timing"
         deselect:                 # == union of the always-on terminology/layer-rules/archive-freeze lanes
           - tests/architectural/test_no_legacy_terminology.py
           - tests/architectural/test_layer_rules.py
           - tests/architectural/test_pyproject_shape.py
           - tests/architectural/test_archive_root_byte_identical.py
       fast_gate:
         job: architectural-fast
         max_file_budget_seconds: 90
         max_total_measured_seconds: 300
         roster:                   # {path, budget_seconds, reason}; admission rule in the comment
           - {path: tests/architectural/test_inline_meta_read_gate.py, budget_seconds: 80, reason: "..."}
           # …
       shards:
         job: architectural-heavy
         shard_count: 2
         granularity: file
         timings_key: architectural
     ```
  2. Roster: **33 entries** — the 32 files of research R1 §4b rows 1-32 with the budgets in that
     table (initial values; WP14 finalises them against seeded timings), plus R1 §4b **row 34**
     `tests/architectural/test_dead_symbol_allowlist_loader.py` (budget 10; added by PR #5503,
     D-37). Reasons: "red N× in the 2026-09-30 census window" for rows 1-24, "CI-config wiring
     verdict" for rows 25-32, and for row 34 "schema gate over the committed
     `dead_symbol_allowlist.yaml` (L1-L10 + real-file invariants); post-census file, measured
     0.7 s / 47 tests single-file on 2026-10-01; never walks `src/`". Write the admission
     rule as a comment: deterministic static gate, measured seconds ≤ budget ≤ 90, Σ measured
     ≤ 300 worker-s, priority to gates that went red in the census; excluded on purpose:
     `test_no_dead_symbols.py` (C-007/#5503), `test_dead_symbol_allowlist_contract.py` (its M11
     test drives the real `_real_tree_inputs()` `src/` walk: 30 s single-file, the same cost
     class as `test_no_dead_symbols.py`), `test_interpreter_shard_coverage.py`.
     All 33 paths exist on base `bc826fcbcb` (verified 2026-10-01 post-rebase; none of rows
     1-32 was changed or renamed by #5503/#5521). Row 33 of the R1 table (the partition proof test) is
     **not** added here: WP06 creates `tests/architectural/test_battery_partition_proof.py`
     after this WP; adding a non-existent path would red the roster ⊆ base pin. **WP14 adds
     row 33** (budget 10 s + reason) — it owns the registry next and depends on WP06; WP06 does
     not edit the registry.
  3. Rewrite the `out_of_matrix_test_dirs` reason for `tests/architectural`: its per-PR home is
     the architectural battery described by `special_tiers.architectural` (fast roster plus
     file-partitioned shards) and the always-on terminology/layer-rules/archive-freeze lanes; a
     module row would double-run it.
- **Files**: `.github/ci-module-registry.yml`.
- **Parallel?**: Yes, alongside T019 after T018.
- **Notes**: `workers: 4` is declared now; nothing reads it at runtime until WP12 passes `-n 4`
  (the plugin's worker check is gated on `GITHUB_ACTIONS` and the router does not load the plugin
  yet).

### Subtask T021 – Registry pin tests (drift fixed: no `always_on: true`)

- **Purpose**: Every fact the entry states is checked against its authority, so the registry can
  never again silently contradict the workflow (FR-013).
- **Steps** (in `tests/architectural/test_module_shard_registry.py`):
  1. Split `test_special_tiers_encode_heavy_pole_deserialization`: keep the
     `integration_tests_next`-retired / `integration-next` wiring half unchanged under its own
     name; replace the architectural half with the tests below. Update the module docstring's
     "architectural pole always-on" sentence.
  2. `test_special_tiers_architectural_schema`: exact key set (no `always_on`, `filter_group`,
     `note`, `non_src_filter_groups`, `nightly_backstop`); types; `workers >= 1`;
     `shard_count >= 2`; `granularity == "file"`; roster entries have non-empty `path`, `reason`,
     int `budget_seconds <= max_file_budget_seconds`; roster paths unique.
  3. `test_special_tiers_architectural_trigger_matches_gate_selection`: `trigger == "code_scoped"`,
     `shards.job == HEAVY_BATTERY_GATE`, `shards.job in load_router().code_shard_jobs`,
     `shards.job not in load_router().always_on_jobs`.
  4. `test_special_tiers_architectural_base_matches_router_commands`: every `gc.Gate` of job
     `shards.job` in `ci-router.yml` (one today, one per matrix leg after WP12) has
     `paths == base.paths`, `marker_expr == base.marker`, `set(ignores) == set(base.deselect)`;
     and `set(base.deselect)` == the union of the pytest paths of the router's always-on
     architectural lanes (`terminology`, `layer-rules`, `archive-freeze`).
  5. `test_fast_roster_is_inside_the_base`: every roster path ∈
     `shard_select.enumerate_base_files(base.paths, deselect=base.deselect, root=_REPO_ROOT)`.
  6. Red-first: write these first; they fail on the current entry (`always_on`, missing keys).
  7. Workflow-side equality for the fast job, the legs and the worker count is **not** asserted
     here: `architectural-fast` and the matrix do not exist until WP12. WP06's partition proof
     pins `shard_count` against the legs; WP12's worker-policy test pins `-n 4 == workers` and
     adds `architectural-fast` to the always-on oracle. Never add a skip or `if job exists`
     branch here to pre-empt that — a tolerant pin is a green-wash.
- **Files**: `tests/architectural/test_module_shard_registry.py`.
- **Parallel?**: With T020.
- **Notes**: This file is on the fast roster itself; keep it fast (no subprocess).

### Subtask T022 – `capture_shard_timings.py --suite architectural --from-junit` + tests

- **Purpose**: A reproducible producer for battery per-file timings from CI junit (D-29); never a
  local battery run (C-009).
- **Steps**:
  1. CLI: make `--module` (repeatable) and `--suite {architectural}` a required mutually
     exclusive pair; `--from-junit DIR` (repeatable; each DIR = one run's downloaded junit
     artefacts, required with `--suite`); `--run-id` (repeatable with `--suite`, one per DIR, for
     provenance); `--write` xor `--output` unchanged. `--help` must still work under `-I -S`.
  2. `junit_file_seconds(xml_paths, base_files) -> dict[str, float]`: parse each `*.xml` with
     `xml.etree.ElementTree` (stdlib; our own CI artefacts, no external entities are resolved by
     expat), sum testcase `time` per file. Resolve `classname` (xunit2: dotted module path, then
     optional class names, e.g. `tests.architectural.test_x.TestY`) to the **longest dotted
     prefix** whose `/`-joined `.py` path ∈ `base_files`; unresolved classnames are counted and
     reported, never guessed. This resolver is the one T018 reuses.
  3. Across several DIRs (runs), the per-file value is the **median** over the runs in which the
     file appears; round like the module tables (`_ROUNDING_PLACES`).
  4. `merge_battery_capture(payload, suite, durations, provenance) -> dict` (pure, additive,
     idempotent): replaces `battery_file_durations[suite]` and
     `battery_capture_provenance[suite]` together, leaves every other key untouched. Required
     provenance fields: `producer`, `captured_at`, `selection` (the base marker), `workers`,
     `files_measured`; the junit producer adds `source: "junit"`, `run_ids`, `unresolved_testcases`.
     WP14 calls this same function to write its census seed — export it in `__all__`.
  5. Base files come from `shard_select.enumerate_base_files` with the registry `base` (YAML read
     lazily).
  6. Tests in `tests/ci/test_capture_shard_timings.py`: classname resolution (module-level test,
     class-nested test, nested dir, unresolvable); per-file sums; median across 3 runs; merge
     leaves `module_*` tables untouched and replaces both battery tables together; CLI argument
     exclusivity; `--help` under `-I -S` still green; a two-run end-to-end through `main()` with
     `--output` into `tmp_path`. Use small synthetic junit XML fixtures written in the test.
- **Files**: `scripts/ci/capture_shard_timings.py`, `tests/ci/test_capture_shard_timings.py`.
- **Parallel?**: Independent of T019-T021 after T018.
- **Notes**: Battery junit does not exist yet (the router battery emits none until WP12). WP14
  seeds from census logs; the first nightly backstop / `mode=full` dispatch junit refreshes it
  through this mode.

## Test Strategy

```bash
uv run --frozen pytest tests/ci/test_battery_partition_plugin.py tests/ci/test_capture_shard_timings.py \
  tests/ci/test_shard_select.py tests/ci/test_workflow_script_import_guard.py -q
uv run --frozen pytest tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_ci_integrity_oracle_nonvacuous.py tests/architectural/test_gate_selection_authority.py -q
make test-fast
uv run --frozen ruff check scripts/ci tests/ci tests/architectural/test_module_shard_registry.py
uv run --frozen ruff format --check .
uv run --frozen mypy --strict scripts/ci/battery_partition_plugin.py scripts/ci/capture_shard_timings.py
```

Partition smoke on the real tree — **collect-only**, no tests run (C-009); record the three
counts in the Activity Log and check `fast + 1/2 + 2/2 == 3394` on `bc826fcbcb` (or the live base count):

```bash
B='-m "not performance and not stress and not timing" --deselect tests/architectural/test_no_legacy_terminology.py --deselect tests/architectural/test_layer_rules.py --deselect tests/architectural/test_pyproject_shape.py --deselect tests/architectural/test_archive_root_byte_identical.py'
for p in fast 1/2 2/2; do
  eval uv run --frozen python -m pytest tests/architectural $B -p scripts.ci.battery_partition_plugin --battery-part $p --collect-only -q | tail -1
done
eval uv run --frozen python -m pytest tests/architectural $B --collect-only -q | tail -1
```

Until WP14 seeds timings, the legs balance by file count with the loud FR-005 warning — expected.
The pinning inventory is green on base `bc826fcbcb` (#5523 fixed by `e3794ded2d`, CLOSED; D-37); this WP adds no delta (`python3 scripts/ci/derive_pinning_inventory.py --check`
stays green).

## Risks & Mitigations

- **Workers compute a different part** (non-determinism, different cwd/rootpath) → digest
  cross-check via `workerinput`; T018 runs `-n 2`.
- **Plugin not importable in xdist workers on CI** → T018 runs from `cwd=REPO_ROOT` with no
  `PYTHONPATH`, the CI condition; if workers cannot import it, fall back to registering the hooks
  from `tests/architectural/conftest.py` (R1 alternative b) — raise it with the orchestrator
  first, because that file is not owned here.
- **Silent loss** → the plugin never ignores non-enumerated files; the self-check fails on any
  executed out-of-part file; WP06 proves the static partition.
- **Registry pin too strict for WP12's matrix** → T021 step 4 iterates all gates of the job, so
  two legs with the same base pass unchanged.

## Review Guidance

- **Red on planning base, green on WP tip**: T018/T021 tests at the first commit (red: plugin
  absent, registry still `always_on: true`), green at the tip.
- Confirm parts are computed in every process and the digest check exists (D-23), and that the
  `-n 2` cases really execute tests (not `--collect-only`).
- Confirm `pytest_ignore_collect` returns `None`, never `False`, and only for enumerated files.
- Confirm the self-check positive control (custom-collected `extra_check.py`) fails the run.
- Confirm the FR-005 subprocess case asserts the plugin's own `::warning title=shard timings::`
  line (once, with `-n 2`) and the step-summary line — not only the helper.
- Confirm `--ignore=<file>` is accepted as a whole-file deselect and the worker check is skipped
  under `--collect-only` (both have a subprocess case).
- Confirm the registry has no trigger-group list and no nightly key (D-26), no `always_on`.
- Confirm the collect-only smoke counts in the Activity Log sum to the base count.
- `mypy --strict`, ruff, ruff format clean; hooks ≤ 15 complexity, logic in tested helpers.
- FR-003 (roster held in the registry), FR-004 (runtime partition), FR-013 (truthful registry),
  C-010 (one selector, one enumeration).

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

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
