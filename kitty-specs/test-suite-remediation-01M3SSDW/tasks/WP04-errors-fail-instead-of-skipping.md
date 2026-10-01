---
work_package_id: WP04
title: Errors fail instead of skipping
dependencies: []
requirement_refs:
- FR-004
- FR-011
- NFR-001
- NFR-004
- NFR-005
- C-001
- C-007
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 468aab2747c0628f9b63be98a152bcd6b15de843
created_at: '2026-09-30T20:54:41.036178+00:00'
subtasks:
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 1 - Masked greens
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_support/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/conftest.py
- tests/_support/shared_build_artifacts.py
- tests/doctrine/test_wheel_packaging.py
- tests/cross_cutting/versioning/test_version_detection.py
- tests/stress/test_concurrent_emits.py
- tests/architectural/test_real_home_isolation_guard.py
- tests/retrospective/test_events_shapes.py
- tests/upgrade/test_unified_bundle_migration.py
- tests/specify_cli/core/test_wps_manifest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Errors fail instead of skipping

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission test-suite-remediation-01M3SSDW` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- **FR-004**: Tests and fixtures that today turn a build, packaging-metadata, time-budget, home-isolation or declared-dependency error into a **skip** now **fail** and name the error. This covers masked-greens rows 10, 11, 13, 14, 15, 17 and 18, plus the dead row-12 helper, which is deleted.
- **Exemption list (keep, do not touch)**: the masked-greens "Declared platform / tool-guard list":
  - symlinks unsupported;
  - Docker absent;
  - Playwright absent;
  - git capability or checkout shape;
  - the by-design topology refusal;
  - the CI auth environment;
  - the env-gated chokepoints (the quarantine and performance skips in `tests/conftest.py`).
- **FR-011**: each conversion has a planted-break record: before SKIP, after FAIL or ERROR.
- **NFR-001**: executed counts per file ≥ before.
- **NFR-004**: the stale #3595 citation on the performance chokepoint in `tests/conftest.py` is corrected (a campsite).
- **RK-3 (option b, binding)**:
  - the stress budget moves into a separate test marked `timing` that **also** carries `stress`;
  - the proof is `--collect-only -m timing` / `-m stress`;
  - **no** stress or timing run (C-001).

## Context & Constraints

- Read first: `spec.md` FR-004; `plan.md` IC-04 and the RK-3 ruling; `research.md` D-8; `research/masked-greens.md` rows 10–15, 17 and 18 plus the "Declared platform / tool-guard list"; `quickstart.md` §FR-004.
- **Why these are errors, not platforms**: `build`, `hatchling`, `jsonschema` and `spec-kitty-events` are declared dependencies. Their absence is a stale venv (CLAUDE.md baseline-red category 4), not a platform condition.
- **Format-excluded** (edit without `ruff format`):
  - `tests/cross_cutting/versioning/test_version_detection.py`;
  - `tests/stress/test_concurrent_emits.py`;
  - `tests/architectural/test_real_home_isolation_guard.py`;
  - `tests/upgrade/test_unified_bundle_migration.py`;
  - `tests/specify_cli/core/test_wps_manifest.py`.
- **Not format-excluded**: `tests/conftest.py` (in `ruff.toml` per-file-ignores, `F401`), `tests/_support/shared_build_artifacts.py`, `tests/doctrine/test_wheel_packaging.py` and `tests/retrospective/test_events_shapes.py`.
- **Cross-cutting**: `tests/conftest.py`. Its definition names are pinned by `tests/architectural/test_home_owner_behaviour.py`, so do not rename or remove any conftest function or fixture.
- **Pinned texts**: `tests/architectural/test_timing_coverage_invariant.py:327-337` pins the stress file's functional assertion texts **verbatim** (`"eid"`, `"eid not in event_ids"`, `"events_path.exists()"`, `"len(lines) == n"`, …). They must stay in the non-timing stress test.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP04 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** **Never** run `tests/stress/test_concurrent_emits.py` for real; use `--collect-only` only (RK-3). Run a wheel-building consumer **by node**, once. Never run a test directory as a whole, never `make test-full`, and no stress, timing, e2e or performance suite. Run `make test-fast` once.
2. **Planted breaks never land (C-007).** Scratch edits, or scratch conftest plugins kept **outside** the repository (`-p` with a `PYTHONPATH` pointing at your scratchpad). Revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Planted-break protocol (FR-011)**: before SKIP, after FAIL or ERROR, with the error named in the output.
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP04 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail|quarantine)|importorskip" <owned files>`. Every surviving skip must be on the exemption list and carry a reason. Every defect citation must be to an open issue.
6. **Quality (NFR-005).** `uv run --frozen ruff check <owned files>`, plus `ruff format --check` on the non-excluded files. Add no new `noqa` or `type: ignore`. Keep complexity ≤ 15. Hoist repeated literals (S1192).
7. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions|tooling-friction --entry "..." --actor claude-sonnet-5`.
8. **Baseline-red gotcha.** Classify any red you did not cause (CLAUDE.md); never green-wash it.
9. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits. One commit per row group is preferred (DIRECTIVE_046).

### Additional mission-wide rules (analysis folds)

- **A. New product defect (FR-005, DM-01M3SSV4; analysis C1).** If an unmasked or converted test exposes a **new** product defect, never re-mask it.
  - If the fix fits this WP: make it red-first, as a failing test commit followed by a **separate** `fix(...)` commit touching only the product file(s). It is a sanctioned out-of-map `src/` edit: record a one-line rationale in your WP notes, file an issue (`gh issue create`) and add its issue-matrix row (`spec-kitty agent issue-verdict ... --verdict fixed`). The "`git diff --stat src/` must be empty" rule is lifted for exactly that commit.
  - Otherwise: mark the test `xfail(strict=True, reason="<newly filed open issue>")` and tell the orchestrator.
- **B. Evidence completeness (FR-011; analysis C2).** The evidence in your review note and final report is the **full** per-item record, never a summary. For each item give:
  - `path::function::mutation` (the planted break);
  - the old form's result under the break;
  - the new form's (or covering guard's) result under the break;
  - the result after the revert;
  - the exact command.

  If `move-task --note` rejects the length, put the full records in the WP's review-ref artifact or the lane commit message body, and tell the orchestrator where they are. The per-WP reviewer must be able to check each item before approval.
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T015 – Rows 10–11: the build and install fixtures fail; #3595 campsite

- **Purpose**: `build_artifacts` and `installed_wheel_venv` convert a packaging defect into a SKIP for every consumer. A wheel that won't build or install is exactly the defect FR-004 names.
- **Files**: `tests/conftest.py`, `tests/_support/shared_build_artifacts.py`.
- **Anchors**:
  - `tests/conftest.py`:
    - `_build_tool_available` at `:1209`;
    - `build_artifacts` at `:1221-1242`, with `pytest.skip("python -m build not available")` at `:1234` and `except SharedBuildError as error: pytest.skip(str(error))` at `:1241-1242`;
    - `installed_wheel_venv` at `:1246-1278`, with three skips at `:1260`, `:1268` and `:1276`;
    - the performance chokepoint comment and reason at `:322-333`, which cite #3595 (CLOSED).
  - `tests/_support/shared_build_artifacts.py`:
    - `SharedBuildError` docstring at `:82`: "callers turn this into a skip";
    - `default_wheel_sdist_builder` at `:63-78`.
- **Steps**:
  1. `build_artifacts`: replace the build-tool skip with `pytest.fail("python -m build not available — `build` is a declared test extra; re-sync the venv (uv sync --frozen --all-extras)", pytrace=False)`. Replace the `SharedBuildError` skip with `pytest.fail(f"wheel/sdist build failed: {error}", pytrace=False)`, or just let it propagate. Either way the output must **name** the build stderr.
  2. `installed_wheel_venv`: turn all three skips into `pytest.fail(...)` with the same messages, e.g. "Failed to install wheel: {stderr}".
  3. Change the `SharedBuildError` docstring to "callers fail loudly with this error (FR-004)".
  4. **Optional, recommended**: make `default_wheel_sdist_builder` pass `--no-isolation`. `hatchling` is pinned in the `test` extra for exactly this, and it removes the only non-product failure mode (network). Only do this if `python -m build --no-isolation` works in the synced venv; otherwise leave it and note why.
  5. **Campsite (NFR-004)**: rewrite the chokepoint comment and the `skip_performance` reason so they no longer cite the closed #3595. The live harness is the nightly performance job that sets `SPEC_KITTY_RUN_PERFORMANCE=1`; verify with `grep -n SPEC_KITTY_RUN_PERFORMANCE .github/workflows/ci-nightly.yml`. You may keep "#3595 (closed)" as provenance. **Do not change** the chokepoint behaviour (it is on the exemption list).
- **Planted break (rows 10–11)**: in a scratch copy of `pyproject.toml`, plant an invalid `[tool.hatch.build.targets.wheel].packages` entry. Run **one** `build_artifacts` consumer by node, e.g. the first test in `tests/doctrine/test_wheel_packaging.py` (`uv run --frozen pytest "tests/doctrine/test_wheel_packaging.py::<first test>" -n0 -q -rs`).
  - Before (stash your conftest change): SKIP. After: ERROR naming the build stderr.
  - Revert `pyproject.toml`. Run the build **only once** per state.
- **Verification**: `uv run --frozen pytest tests/architectural/test_home_owner_behaviour.py -n0 -q` stays green, which proves the conftest definition names are unchanged.

### Subtask T016 – Row 12: delete the dead `_build_wheel_fallback`

- **Purpose**: Dead code that would mask a build failure as a skip if anyone ever called it. A repo-wide grep finds no caller.
- **Files**: `tests/doctrine/test_wheel_packaging.py`.
- **Anchors**: the stale "fallback fixtures below" comment block at `:12-18`; `_build_wheel_fallback` at `:33-48`, with skips at `:43` and `:47`.
- **Steps**:
  1. `git grep -n "_build_wheel_fallback"` must show only the definition.
  2. Delete the function and the stale comment block. Remove imports that become unused (`tempfile`, `subprocess`, …, only if unused).
  3. `uv run --frozen ruff check tests/doctrine/test_wheel_packaging.py`.
- **Evidence**: kind DELETE (no behaviour). The covering guard is the T015 `build_artifacts` conversion (quickstart Break #10).
- **Parallel?**: Yes.

### Subtask T017 – Row 13: the 11 version-detection skip sites fail

- **Purpose**: Unreadable package metadata is always a defect. The session `test_venv` fixture (`tests/conftest.py:1187-1200`) already fails loudly when the venv cannot be built, and the same file's `test_package_metadata_accessible` (`:340-348`) already uses `pytest.fail` for this condition.
- **Files**: `tests/cross_cutting/versioning/test_version_detection.py` (format-excluded).
- **Anchors**: skip sites at `:40`, `:75`, `:88`, `:106`, `:151`, `:177`, `:239`, `:242`, `:301`, `:321` and `:367`. Tests named in the plan include `test_version_matches_package_metadata` (`:67`), `test_cli_version_matches_package_metadata` (`:82`) and `test_no_hardcoded_version_in_init` (`:98`).
- **Steps**:
  1. Baseline: `uv run --frozen pytest tests/cross_cutting/versioning/test_version_detection.py -n0 -q -rs`. Expect 18 passed, 0 skipped.
  2. At each site, replace `pytest.skip(...)` with `pytest.fail(...)` and the same message, or remove the `try/except` and let the exception propagate. Match the style of `:340-348`.
     - `:40` is `returncode != 0` from a subprocess: fail with its stderr.
     - `:239/:242` ("Could not locate pyproject.toml"): in a repo checkout this is a defect. Fail.
  3. If `"Package metadata not available"` appears 3 or more times, hoist it to a module constant (S1192).
- **Planted break**: a scratch plugin in your scratchpad that monkeypatches `get_installed_version` (find its import site in the file) to return `None`. Run it with `PYTHONPATH=<scratch> uv run --frozen pytest -p <plugin> tests/cross_cutting/versioning/test_version_detection.py -n0 -q -rs`.
  - Before: **7 SKIPPED** + 2 FAILED. After: **9 FAILED**.
  - Also the product break: hardcode `__version__ = "0.4.13"` in a scratch edit of `src/specify_cli/__init__.py`. `test_version_matches_package_metadata` goes RED. Revert.
- **Parallel?**: Yes.

### Subtask T018 – Row 14: split the stress budget into a `timing` + `stress` test (RK-3)

- **Purpose**: `if duration > 60.0: pytest.skip(...)` at `:257-262` turns a budget breach into a skip. A bare `pytest.fail` in the stress test would be a wall-clock flake, which the flakiness policy forbids (no retry-to-green). So split it: correctness stays PASS/FAIL in the stress test, and the SC-12 budget becomes its own honest `timing` test.
- **Files**: `tests/stress/test_concurrent_emits.py` (format-excluded; module `pytestmark = [pytest.mark.stress, pytest.mark.slow, pytest.mark.git_repo]` at `:39`).
- **Anchors**:
  - `test_concurrent_emits_produce_valid_event_log` at `:178-262`, with `started = time.monotonic()` / `duration = ...` around `:190-196`;
  - the skip at `:257-262`;
  - `_emitter_count()` at `:167`.
- **Steps**:
  1. **Tidy first**: hoist `_SC12_BUDGET_SECONDS = 60.0` to module level.
  2. **Factor the workload** into a helper, e.g. `_run_concurrent_emits(stress_repo: Path) -> _EmitRun`. It holds the pool map and the timing, and returns `results`, `duration`, `n`, `wp_ids` and `events_path`.
     - Keep **all** functional assertions (`assert not failures`, `events_path.exists()`, `len(lines) == n`, the per-line loop with `eid`, `eid not in event_ids`, `seen_wps == set(wp_ids)`, …) textually inside `test_concurrent_emits_produce_valid_event_log`, which stays non-timing. `test_timing_coverage_invariant.py` pins them verbatim.
  3. Delete the skip block at `:257-262` from the stress test. It now asserts correctness only.
  4. Add a new test, e.g. `test_concurrent_emits_meet_sc12_budget`, decorated `@pytest.mark.timing` and `@pytest.mark.timeout(120)`. It inherits `stress` from the module `pytestmark`; add `@pytest.mark.stress` explicitly if you prefer. It runs the helper and asserts the budget through the house helper `tests._perf_helpers.assert_timing_budget(run.duration, _SC12_BUDGET_SECONDS, name="duration")` (signature `(measured, budget, *, name=...)`; the performance-marker guard already vets its call sites, `test_timing_coverage_invariant.py:517`). Fall back to a plain `assert run.duration <= _SC12_BUDGET_SECONDS` only if the helper does not fit. Use only the vocabulary tokens `duration` and `budget`; do not copy the functional assertion texts into it.
  5. Check marker registration: `timing` is registered in `pytest.ini:57`. Confirm nothing forbids `timing` + `stress` on the same test, and read `tests/architectural/test_performance_marker_guard.py` and `test_timing_coverage_invariant.py` before writing.
- **Proof (RK-3 option b)**: run no stress or timing workload. Use:
  ```bash
  uv run --frozen pytest tests/stress/test_concurrent_emits.py --collect-only -q -m timing   # lists the new budget test
  uv run --frozen pytest tests/stress/test_concurrent_emits.py --collect-only -q -m stress   # lists BOTH tests (stress job runs the budget test too)
  uv run --frozen pytest tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_performance_marker_guard.py -n0 -q
  ```
  Record the outputs. The red run with the budget monkeypatched to `0.0` is **not** performed (no operator exception; RK-3).
- **Edge cases**: If the invariant or marker guard requires `timing` tests to be registered elsewhere (e.g. a ledger), that ledger is outside this WP's files. Stop and report rather than editing it.

### Subtask T019 – Row 15: the home-isolation skip becomes an assert

- **Purpose**: `pytest.skip(_SKIP_PRE_WP04)` fires **only** when isolation regresses, so the guard disarms exactly when it should bite. WP04's isolation shipped long ago.
- **Files**: `tests/architectural/test_real_home_isolation_guard.py` (format-excluded).
- **Anchors**:
  - `_SKIP_PRE_WP04` at `:61-66`;
  - the pre-WP04 docstrings at `:17`, `:201` and `:239`;
  - `test_no_real_home_mutation_under_xdist` at `:236-267`, whose skip is at `:258-259`;
  - `# pragma: no cover` at `:267` and `:270` on `_assert_real_sentinel_untouched`.
  - Keep the distinct `_NO_WORKER_HOMES` message (`:68-80`); it is a different failure.
- **Steps**:
  1. Replace the `if not _isolation_active_from_homes(...): pytest.skip(_SKIP_PRE_WP04)` with `assert _isolation_active_from_homes(worker_homes, str(real_home)), <diagnostic naming worker_homes and real_home>`.
  2. Delete `_SKIP_PRE_WP04`, the stale `# pragma: no cover` markers on the now-reachable body, and the "pre-WP04" wording in the docstrings. Rewrite them to state that isolation is required.
  3. `uv run --frozen pytest tests/architectural/test_real_home_isolation_guard.py -n0 -q -rs`. Expect 8 passed, 0 skipped.
- **Planted break (M3)**: HOME is redirected **twice**, so both redirects must be neutered in a scratch edit of `tests/conftest.py`:
  - the `for var in _HOME_ENV_VARS:` loop in `_apply_home_env` (`:134`, the process-wide redirect called from `pytest_configure`);
  - **and** the loop in the autouse `_isolated_worker_home` fixture (`:418`).

  Neutering only the fixture loop leaves the probe worker on the `pytest_configure` home, so the guard stays green and the plant is vacuous. Before (stash your change): SKIP. After: FAIL. Revert.
- **Parallel?**: Yes.

### Subtask T020 – Rows 17–18: plain imports; exemption check; evidence

- **Purpose**: `importorskip` or `except ImportError: skip` for **declared** dependencies hides a stale venv.
- **Files and anchors**:
  - `tests/retrospective/test_events_shapes.py`: `:307-311` (`except ImportError: pytest.skip("spec_kitty_events is not importable")`). **Also**, at `:318-319`, `pytest.skip("spec_kitty_events package is older than retrospective 4.1")` is a version guard. The declared floor is `spec-kitty-events>=10.4.0`, so verify `RETROSPECTIVE_EVENT_NAMES` exists upstream and convert it to an assert. Record it in the MG-17 evidence as an **inventory addition** (same class, campsite): masked-greens row 17 listed only `:311`.
  - `tests/upgrade/test_unified_bundle_migration.py`: `:345` and `:357` (`jsonschema = pytest.importorskip("jsonschema")`).
  - `tests/specify_cli/core/test_wps_manifest.py`: `:393`.
- **Steps**:
  1. Replace each with a plain `import` (module-level where idiomatic, or local inside the test). Drop the `# pragma: no cover` on the removed branch.
  2. Run:
     ```bash
     uv run --frozen pytest tests/retrospective/test_events_shapes.py tests/upgrade/test_unified_bundle_migration.py tests/specify_cli/core/test_wps_manifest.py -n0 -q -rs
     ```
     Masked-greens verified 48 passed; the one skip there is the performance chokepoint, which is on the exemption list.
  3. **Planted break**: a scratch plugin that sets `sys.modules["jsonschema"] = None` (and, separately, `sys.modules["spec_kitty_events.retrospective"] = None`). Before: SKIP. After: ERROR.
  4. **Exemption check**: `git diff <base> --stat` shows none of the files on the platform/tool-guard list (masked-greens "Declared platform / tool-guard list"), except `tests/conftest.py`, whose chokepoint **behaviour** is unchanged.
  5. **Skip hygiene** over all 9 owned files. `make test-fast` once.
- **Evidence records**: MG-10/11 (CONVERT), MG-12 (DELETE), MG-13 (CONVERT, 7 SKIP → 9 FAIL), MG-14 (CONVERT, collect-only proof, with RK-3 noted), MG-15 (CONVERT) and MG-17/18 (CONVERT). Each gets before and after executed counts (NFR-001).

## Test Strategy

```bash
uv run --frozen pytest tests/cross_cutting/versioning/test_version_detection.py tests/architectural/test_real_home_isolation_guard.py tests/retrospective/test_events_shapes.py tests/upgrade/test_unified_bundle_migration.py tests/specify_cli/core/test_wps_manifest.py tests/doctrine/test_wheel_packaging.py tests/architectural/test_home_owner_behaviour.py tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_performance_marker_guard.py -n0 -q -rs
uv run --frozen pytest tests/stress/test_concurrent_emits.py --collect-only -q -m timing
uv run --frozen pytest tests/stress/test_concurrent_emits.py --collect-only -q -m stress
uv run --frozen ruff check tests/conftest.py tests/_support/shared_build_artifacts.py tests/doctrine/test_wheel_packaging.py tests/cross_cutting/versioning/test_version_detection.py tests/stress/test_concurrent_emits.py tests/architectural/test_real_home_isolation_guard.py tests/retrospective/test_events_shapes.py tests/upgrade/test_unified_bundle_migration.py tests/specify_cli/core/test_wps_manifest.py
uv run --frozen ruff format --check tests/conftest.py tests/_support/shared_build_artifacts.py tests/doctrine/test_wheel_packaging.py tests/retrospective/test_events_shapes.py
make test-fast
```

`tests/doctrine/test_wheel_packaging.py` builds a wheel through `build_artifacts`. It runs once, in the command above. Do not loop it.

## Risks & Mitigations

- **`tests/conftest.py` is cross-cutting.** Keep every definition name, and run `test_home_owner_behaviour.py`.
- **The wheel build is slow or network-bound.** `--no-isolation` removes the network dependency. If you skip that option, record the reason.
- **A timing test in a lane with no job** (RK-3): the `stress` mark puts it in the nightly stress job. Record that in the evidence.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- `rg -n "_build_wheel_fallback|_SKIP_PRE_WP04|importorskip\(\"jsonschema\"\)" tests` returns nothing.
- The collect-only outputs list the budget test under both `-m timing` and `-m stress`, and `test_timing_coverage_invariant.py` stays green.
- Re-run planted breaks #8, #9 and #12 (quickstart) yourself.
- No platform or tool guard changed behaviour.
- The #3595 citation now describes the live nightly harness.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-5, etc.)

**Initial entry**:

- 2026-09-30T19:32:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

Hand-off:

```bash
spec-kitty agent tasks mark-status T015 T016 T017 T018 T019 T020 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP04 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
