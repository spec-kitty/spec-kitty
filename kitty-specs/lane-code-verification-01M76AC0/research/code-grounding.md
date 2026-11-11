---
type: reference
updated: 2026-11-11
---

# Code grounding: lane worktrees run and verify lane code (#7547 / #7554)

Audience: the planner and implementers of this Mission (software-engineer persona).
Base: `origin/main` at `ba45c46c`. Produced by a read-only squad: code grounding
(architect-alphonso), tracer evidence mining (researcher-robbie), foldable-issue
discovery (planner-priti), then a fresh-context second opinion (reviewer-renata) that
re-ran the probes. The squad's full reports are in the appendices; this section is the
reconciled synthesis. Where the second opinion corrected a first-pass claim, the
correction is what is stated here.

## 1. What actually imports which tree (reproduced twice)

Throwaway worktree, no venv inside it, root `.venv` editable install (`.pth` → root `src`).

| Invocation, cwd = lane | `specify_cli` loads from |
|---|---|
| `<root>/.venv/bin/python -m pytest` or `.venv/bin/pytest` | lane, only because `pytest.ini:9` `pythonpath = src` |
| same with `-c /dev/null` (no ini) | ROOT |
| a subprocess spawned by a test under lane pytest | ROOT (`pytest.ini` does not reach children) |
| `<root>/.venv/bin/python -c 'import specify_cli'` | ROOT |
| `<root>/.venv/bin/spec-kitty`, global `~/.local/bin/spec-kitty` | ROOT |
| bare `python3` | `ModuleNotFoundError` |
| any of the above with `PYTHONPATH=<lane>/src` | lane, except: `-I` ignores it; the uv workspace member `spec_kitty_services` still loads from ROOT; the CLI then fails `BuiltInPackMissing` (no packs tree in the lane) |

`importlib.metadata` still reports the root dist-info under `PYTHONPATH`, so only a
module `__file__` check proves which tree ran.

## 2. Why #5096 / PR #5913 did not end it

`tests/_support/import_origin.py` (called from `tests/conftest.py` `pytest_configure`)
asserts that `specify_cli` comes from the same checkout as the conftest. It is:
pytest-only; self-consistency only (running the root's tests from the root passes it);
repo-internal (consumers get nothing); silent when pytest cannot start; blind to
subprocesses; and it records nothing the gate or review can see. #5913's own notes
call it a backstop that does not fire in normal setups. No tracer records it firing.

## 3. Where a test command lives today

- One authority: `.kittify/config.yaml` → `review.test_command` (+ `test_output_format`),
  read by `review/baseline.py::_get_test_command` and consumed through
  `review/scope_source.py::DeclaredCommandScopeSource.test_command()` (FR-011: no new
  config key).
- Agents are never told it. `implement` prints `cd <lane>` and the FR-006
  `export SPEC_KITTY_TEST_DB_NAME=...` block (`cli/commands/implement.py` ~L310-316)
  and nothing about interpreter or command. `build_implement_prompt_lines` /
  `build_review_prompt_lines` (`cli/commands/agent/workflow_executor.py` L1576 / L2262)
  carry no command. The built-in pack prompts (fetched; not editable here) say only
  "all tests pass"; the review prompt's deletion test is meaningless if the reviewer
  imports the root.
- `lanes/lane_env.py::lane_test_env` is a stated extension point for lane-scoped env
  (FR-006), flowing into `LaneWorkspaceResult`, `WorkspaceContext` (whose `from_dict`
  drops unknown keys, so new fields are backward-compatible) and `implement --json`.
  It is an env dict printed as `export` lines, so an invocation belongs in a sibling
  field, not inside it. Nothing reads it back and the gate never applies it, so the
  FR-006 DB isolation does not cover gate runs today.

## 4. The pre-review gate

- Wiring: `move-task --to for_review` → `cli/commands/agent/tasks_move_task_gates.py::_mt_run_transition_gates`
  → doctrine-bound handler → `review/pre_review_gate.py::evaluate_pre_review_gate`.
  `gate_repo_root = worktree_path or main_repo_root` (L1220-1221): it runs with cwd = lane.
- Production path (declared command): `_evaluate_via_scope_source` → `_run_raw_command`
  runs `["sh","-c", review.test_command]` with `env=_gate_run_env()` (inherit +
  `PWHEADLESS=1`). It does **not** strip `PYTHONPATH` / `UV_PROJECT_ENVIRONMENT` /
  `VIRTUAL_ENV`; only the WP-frontmatter override tier (`run_scoped_tests_at_head`,
  `_strip_interpreter_path_env`, L114-119, L475-478) does. An inherited
  `UV_PROJECT_ENVIRONMENT=<root>/.venv` would aim `uv run` at the root venv and likely
  re-sync and repoint its editable install at the lane (hypothesis; #1907 class).
- `resolve_pytest_command` (`review/_interpreter.py`, `uv run --project <lane>` else
  `sys.executable -m pytest`) has one caller, the override tier (#5985's fallback is
  reachable only there).
- Evidence recorded: `policy_metadata["pre_review_gate"]` (`tasks_move_task_gates.py`
  L576-631): outcome, reason, failure counts and node ids, targets, block/force flags,
  run state, budget fields. **No tree path, HEAD SHA, dirty flag, interpreter or import
  origin.**
- Outcomes (`GateOutcome`): `no_coverage`, `no_new_failures`, `new_failures`,
  `unverified_baseline`, `source_mismatch`, `timed_out`, `cancelled`, `skipped`,
  `scope_oversized`. `review/verdict_aggregation.py` precedence: TERMINAL {timed_out,
  cancelled, scope_oversized} (not `--force`-bypassable) > BLOCK (`new_failures` and
  `review.fail_on_pre_review_regression` and not `--force`) > warn-and-proceed. Terminal
  or block → `typer.Exit(1)` with a `diagnostic` dict; there are no named refusal codes.
  `tests/review/test_verdict_aggregation.py:40-46` enumerates the outcomes.
- `no_coverage` triggers: empty scope; `review.test_command` unset/malformed; run did
  not launch or produced no JUnit; the skip flag / `SPEC_KITTY_SKIP_PRE_REVIEW_GATE`
  (recorded as `no_coverage` with reason "gate skipped — …"); no changed files or a
  planning lane; a handler crash (fail-open). A repo that never declared the gate gets
  `skipped`.
- ADR `2026-08-13-6`'s "trust failures are always BLOCKING" is about pack/doctrine
  trust, not test-evidence provenance; using it to justify a fail-closed refusal needs
  an operator ruling and an amendment, and it meets the C-003 rule that gate evaluation
  never breaks `move-task`.
- The declared command cannot be instrumented in place (argv after `sh -c` does not
  reach pytest; this repo's inline `PYTEST_ADDOPTS` overrides the env), so provenance
  must come from a separate probe plus git facts.
- Tree data must stay out of `scope_source_identity`: the baseline is captured in a
  different tree on purpose, so adding tree data there would flip existing baselines to
  `SOURCE_MISMATCH`.
- `orchestrator_api/wp_lifecycle.py:910-911`: the orchestrator-api `for_review`
  transition never runs the pre-review gate (out of scope; new issue).
- Agent-reported evidence (`status/models.py::VerificationResult`, the `--evidence`
  dict) mirrors `spec_kitty_events.VerificationEntry`, which drops extra fields, so it
  cannot carry tree provenance without a `spec-kitty-events` release. The gate's own
  run is the only evidence the CLI controls end to end.

## 5. Touch set, gates and cost

| File | Lines | 90d commits | Role | Gates / invariants |
|---|---|---|---|---|
| `src/specify_cli/lanes/lane_env.py` | 111 | 1 | lane-scoped env (FR-006) | stable dict shape is the extension contract |
| `src/specify_cli/lanes/implement_support.py` | 1147 | 50 | lane create/reuse, context persist | `test_lane_adoption_single_seam.py`, `test_status_read_single_door.py:229`; open PR #7562 touches `_claim_dirty_paths` |
| `src/specify_cli/workspace/context.py` | 1444 | 17 | `WorkspaceContext`, `resolve_workspace_for_wp` | `test_owned_checkout_single_authority.py:103`, `test_status_read_single_door.py:237` |
| `src/specify_cli/cli/commands/implement.py` | 478 | 53 | implement CLI, JSON, banner | tests in `tests/specify_cli/cli/commands/` (out-of-matrix, nightly only) |
| `src/specify_cli/cli/commands/agent/workflow_executor.py` | 2650 | 48 | implement/review prompt lines | `test_trio_seam_only.py`, `test_commit_recipe_strings.py:404-412`, `test_no_write_side_rederivation.py:104`, `test_execution_context_parity.py` |
| `src/specify_cli/review/pre_review_gate.py` | 1289 | 14 | scope → run → verdict | `kernel.locks`, `kernel.paths.is_windows` (OS-detect ban) |
| `src/specify_cli/review/_interpreter.py` | 98 | 6 | `resolve_pytest_command` | `tests/review/test_interpreter_and_scoped_lock.py` |
| `src/specify_cli/review/verdict_aggregation.py` | 151 | – | pure precedence | `tests/review/test_verdict_aggregation.py` |
| `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` | 1481 | 15 | for_review gate orchestration, metadata | `test_no_write_side_rederivation.py:172` |

Cross-cutting rules for a new module: git reads through `kernel.git` (porcelain and
path-listing owner gates, empty allowlists); OS detection through
`kernel.paths.is_windows`; every new public name needs a production caller
(dead-symbol gate); keep a new `lanes/` helper a leaf (known `lanes` ↔ `status`
deferred-import cycle). No candidate function is at C901 ≥ 12 (nearest: 11,
`_mt_pre_review_gate_console_warning`); the ceiling is 15. Gate-engine tests spawn real
subprocesses (three files: 83 passed in 111 s), so new tests should use the injectable
launch/wait seams.

## 6. Design options

| Option | For | Against |
|---|---|---|
| Per-lane venv (`uv sync` in each lane) | true isolation of code and deps | slow, network-bound per lane; Python/uv only; implement must bootstrap it |
| `PYTHONPATH=<lane>/src` injection | instant, no install | defeated by `-I`; workspace members and packs still come from root; Python/src-layout only; dependency drift unseen |
| Shared venv + path probe | works with any invocation; is the provenance the done-when needs | detects rather than prevents; consumers need a package to probe; non-Python gets git facts only |
| **Hybrid (squad recommendation)** | leaf builder `lanes/lane_invocation.py` used by implement and the gate: cwd = lane, `review.test_command`, strip `PYTHONPATH`/`UV_PROJECT_ENVIRONMENT`/`VIRTUAL_ENV`, apply `lane_test_env`, add `PYTHONPATH=<lane>/src` only for a Python src-layout lane without its own `.venv`; a child-process probe with exactly that env/cwd checks `__file__` of the lane's top-level packages → verified / foreign / unverified; the gate records `evidence_tree` (path, HEAD, dirty, probe) and refuses only on `foreign` | two seams; a new gate outcome needs an aggregation tier and an ADR touch |

Decisions this raises are escalated to the operator (see `foldable-issues.md` §3).

---

## Appendix A — code grounding report (architect lens)

See the squad report reproduced below for line-level detail.

## Code grounding: lane code verification (#7554 / sub-epic #7547)

Checkout `/home/user/spec-kitty`, branch `fix/7547-lane-code-verification` at `ba45c46c` (origin/main).
Profile adopted: architect-alphonso. Charter read (Governing Principles, Standing Orders 1-9), `charter context --action plan` loaded.
The clone is **shallow (50 commits)**, so `git log --since=90.days` is useless here; 90-day churn below comes from the GitHub commits API (`gh api repos/spec-kitty/spec-kitty/commits?path=...&since=2026-08-13`).

---

### 0. Headline findings

1. **A per-lane env seam already exists.** It is `lanes/lane_env.py::lane_test_env(mission_slug, lane_id)` (FR-006, test DB name). The value flows into `LaneWorkspaceResult.lane_test_env`, gets persisted in `WorkspaceContext.lane_test_env`, goes out in the `implement --json` payload, and is printed by `implement` as `export K=V`. This is the natural home for a lane test invocation. Today it carries only `SPEC_KITTY_TEST_DB_NAME`.
2. **There is exactly one project "test command" concept:** `.kittify/config.yaml` → `review.test_command` (+ `review.test_output_format`). It is read by `review/baseline.py::_get_test_command` (L221-245) and consumed through `review/scope_source.py::DeclaredCommandScopeSource.test_command()` (L337-373). That method wraps the command in `["sh","-c",...]`. The command is never shown to the implementing or reviewing agent: neither the implement or review prompt lines nor the built-in pack prompts mention it.
3. **The production pre-review gate already runs in the lane.** `gate_repo_root = worktree_path or st.main_repo_root` (`tasks_move_task_gates.py:1220`), and it runs as cwd = lane (`pre_review_gate.py::_launch_scoped_process`, L436-464). It records **no provenance**: no tree path, no HEAD SHA, no import origin, no interpreter. The `policy_metadata["pre_review_gate"]` fields are at `tasks_move_task_gates.py:576-631`.
4. **The production gate path does not strip interpreter-redirect env.** `_strip_interpreter_path_env` (`pre_review_gate.py:114-119`) strips `PYTHONPATH`, `UV_PROJECT_ENVIRONMENT` and `VIRTUAL_ENV`. It is applied **only** in `run_scoped_tests_at_head` (L475-478, the FR-004 override tier). The declared-command path `_run_raw_command` (L880-948) uses `_gate_run_env()` unchanged. An inherited `UV_PROJECT_ENVIRONMENT=<root>/.venv` therefore redirects `make test-fast`'s `uv run` fallback onto the root's env. That env's editable `.pth` points at the root's `src`. Whether `pytest.ini` then rescues the run is covered in §4. (Hypothesis: not reproduced end-to-end here, because doing so would require a `uv sync` into a lane.)
5. **Probe results (§4).** In a lane with cwd = lane, `<root>/.venv/bin/python -m pytest` imports **the lane's** `src`, because `pytest.ini pythonpath = src` prepends it. `<root>/.venv/bin/python -c 'import specify_cli'` imports **the root's** `src`, and so do `<root>/.venv/bin/spec-kitty` and the global `~/.local/bin/spec-kitty` (a uv tool install, editable → root `src`). Bare `python3` gives `ModuleNotFoundError`. `PYTHONPATH=<lane>/src` makes every one of them import the lane.
6. **No C901 hotspots ≥12** in the candidate files. The nearest is `_mt_pre_review_gate_console_warning` (11), `tasks_move_task_gates.py:633`.

---

### 1. How `implement` creates/reuses a lane and what it emits

#### Call chain
- `cli/commands/implement.py` (478 lines). The `implement` command starts at L319. `_json_payload`-style dict at ~L231-249: `workspace`, `workspace_path`, `branch`, `mission_slug`, `mission_number`, `mission_type`, `wp_id`, `lane_id`, `execution_mode`, `status`, `lane_test_env`.
- `_report_workspace_created` (L252-266) prints the tracker, the mission branch and the lane branch.
- `_print_workspace_ready_banner` (L269-316) prints `cd <workspace_path>` and the "CRITICAL: Change to the lane worktree" banner. It then prints the **FR-006 block** (L310-316): `export SPEC_KITTY_TEST_DB_NAME=...`. That is the only test-related thing implement prints. It says nothing about the interpreter, the venv or a test command.
- `lanes/implement_support.py` (1147 lines). `LaneWorkspaceResult` dataclass (L355-387): `workspace_path, branch_name, workspace_name, lane_id, mission_branch, is_reuse, vcs_backend_value, execution_mode, resolution_kind, lane_test_env, hook_backup_path, wp_stamped`.
  - Fresh lane (L571-614): stamps WP frontmatter provenance (`base_branch`, `base_commit`, `created_at`), builds `WorkspaceContext(... lane_test_env=lane_test_env(mission_slug, lane_id))` and calls `persist_lane_context`.
  - Reuse (L564-570): `refresh_reused_lane_context` (#3946).
  - Return (L616-633): `lane_test_env=lane_test_env(mission_slug, lane_id)`.
  - The worktree itself comes from `lanes/worktree_allocator.py`, which also sets `lane_test_env=` at L954-978. Checkout policy (sparse status exclusion) lives in `lanes/lane_checkout.py::open_lane_checkout` (493 lines).
- `workspace/context.py` (1444 lines). `WorkspaceContext` dataclass (~L160-215): `wp_id, mission_slug, worktree_path (relative), branch_name, base_branch, base_commit, dependencies, created_at, created_by, vcs_backend, lane_id, lane_wp_ids, current_wp, lane_test_env`. `from_dict` filters unknown keys (L203-215), so a new field stays backward-compatible on read. `ResolvedWorkspace` (L218+) is what `resolve_workspace_for_wp` returns.
- `lanes/lane_env.py` (111 lines). `SPEC_KITTY_TEST_DB_NAME_ENV`, `lane_test_db_name`, `lane_test_env` (L99-111). Its docstring says: "The mapping shape is stable so additional lane-scoped env vars can be added in the future without breaking callers that `env.update(lane_test_env(...))`". **This is an explicit extension point.**

#### `agent action implement` / review prompt assembly
- `cli/commands/agent/workflow.py` (2655 lines): `implement` at L1539 and `review` at L2430 resolve `workspace.worktree_path` (L1806 and L2549).
- `cli/commands/agent/workflow_executor.py` (2650 lines):
  - `build_implement_prompt_lines` (L1576-~1700, C901 = 9) emits `Workspace: <path>` (L1602), the agent identity, the charter context, the isolation banner, topology and "WHEN YOU'RE DONE". It also emits `📍 WORKING DIRECTORY: cd <workspace_path>` (L1649). **It carries no test command and no interpreter.** It says "Implementation complete and tested" with no guidance on how to test.
  - `build_review_prompt_lines` (L2262+) is the same shape: `Workspace:` (L2286), `cd <workspace_path>` (L2355), then "# Read code, run tests, check against requirements" (L2358) with no command.
  - `implement_finalize_and_print` (L1732) and `review_finalize_and_print` (L2412) print `📍 Workspace: cd ...`.
  - `capture_and_commit_baseline` (L1413, C901 = 9) runs the declared command via `capture_baseline(... scope_source=resolve_scope_source(authority_root))` in a **detached base-branch worktree**, not in the lane.
- No structured JSON from `agent action implement` is consumed by templates. The templates get the rendered prompt text. `implement --json` (the top-level command) is the only structured output, and it already carries `lane_test_env`.

#### Existing "test command" / interpreter concepts (grep of src/)
| Concept | Location | Notes |
|---|---|---|
| `review.test_command` (+ `test_output_format`) | `review/baseline.py:221-245` | the single project-config test command; this repo sets `PYTEST_ADDOPTS="--junitxml={output_file}" make test-fast` (`.kittify/config.yaml:26-27`) |
| `pre_review_test_command` (deprecated key) | `tasks_move_task_gates.py:118`, warning at L822 | legacy |
| `pre_review_test_scope` (WP frontmatter override) | `tasks_move_task_gates.py:120,255` | FR-004 override tier |
| `resolve_pytest_command` | `review/_interpreter.py:64-98` | `uv run --frozen [--extra test] --project <repo_root> python -m pytest ...`, else `sys.executable -m pytest` |
| `assert_pytest_available` | `cli/commands/_test_env_check.py:45-57` | `sys.executable -c 'import pytest'`; it checks the CLI's interpreter, not the lane's |
| typer/click lock-parity | `_test_env_check.py:117-163` | env-skew warn |
| `checkout_root_of(package_file)` | `services/resolution.py:121-137` | **reusable**: maps `specify_cli.__file__` → source checkout root, or None for a wheel/PYTHONPATH (with no `src/` parent) |
| `lane_test_env` | `lanes/lane_env.py` | FR-006 |
| `hook_installer` pins `sys.executable` | `policy/hook_installer.py:124-150` | different concern |
| `lanes/consolidation.py:759` | `venv_bin = Path(sys.executable).parent` | PATH prepend for a merge driver |

There is no `verify_command`. There is no charter `available_tools` key that names a test command (hypothesis: not exhaustively searched in the charter offering; no hit in `src/specify_cli`).

### 2. Where the prompts get their test command

They don't get one.
- `packs/built-in/missions/mission-steps/software-dev/implement/prompt.md` (378 lines) says "Write tests first (TDD)" (L170), "Verify tests pass" (L172) and "All tests pass" (L185, L374), and nothing else. There is no `pytest`, `PYTHONPATH`, venv, `uv run` or `make test` anywhere in it.
- `.../review/prompt.md` (323 lines) says "Check that tests exist and pass" (L177) and "All tests pass" (L190). It includes the "deletion test" (L194-200), which tells the reviewer to delete the fix and confirm the test fails. **That check is meaningless if the reviewer's run imports the root's `src`.** There is no command and no import-origin instruction.
- Pack content is fetched from `spec-kitty-open-packs` (pin `packs/built-in.source.yaml`, commit `a79c3631`). Prompt edits must be made upstream, so any core-side fix should surface the command **from the CLI**: in implement output and in the `build_*_prompt_lines` text, which core owns.
- The only project-config surface is `review.test_command` in `.kittify/config.yaml`.

### 3. The pre-review gate

#### Entry and wiring
- `move-task --to for_review` → `tasks_move_task_gates.py::_mt_run_transition_gates` (L1377-1435). It runs only for `FOR_REVIEW` and in this order:
  1. Skip check (L1395-1398): the `--skip-pre-review-gate` flag, then `SPEC_KITTY_SKIP_PRE_REVIEW_GATE` (`core/env.py:74-83`, #3980).
  2. Timeout validation.
  3. `_mt_capture_baseline_if_missing` (ADR `2026-10-12-1`: baseline at for_review at the lane fork point, lock-free and fail-open).
  4. `_mt_resolve_transition_gate_verdicts`.
  5. Byproduct enrolment.
  6. `_mt_translate_gate_verdicts`.
  7. `_mt_emit_transition_gate_effect`.
- Inputs: `_mt_resolve_transition_gate_inputs` (L1204-1225). `worktree_path = _mt_resolve_pre_review_workspace(st)` (L275-306, via `resolve_workspace_for_wp`). Changed files are the merge-base diff plus dirty paths. **`gate_repo_root = worktree_path or st.main_repo_root`** (L1220). Config/command authority comes from `_mt_config_authority_root` (L762), the main repo (#?), so a lane's stale `.kittify/config.yaml` cannot drop the gate (comment at L722-735).
- Dispatch: the doctrine-resolved bindings (`review/gate_bindings.py`) → `review/gate_registry.py::_spec_kitty_pre_review_handler` (L102-120) → `pre_review_gate.evaluate_pre_review_gate(changed_files, repo_root=ctx.repo_root, ...)` (L632-670).

#### What it runs and how
- Scope comes from the injected `ScopeSource`. In production that is `DeclaredCommandScopeSource(repo_root)` via `resolve_scope_source` (the GitHub census source is retired, #380). It does no per-file narrowing and runs the whole declared command.
- `evaluate_with_scope` (L1052-1191) does a budget assessment (`gate_budget.assess_scope_budget`; `SCOPE_OVERSIZED` stops the run). It then goes to either:
  - `scope_source is None` (FR-004 override tier): `run_scoped_tests_at_head` (L441-560), which uses `resolve_pytest_command` and **strips `PYTHONPATH`/`UV_PROJECT_ENVIRONMENT`/`VIRTUAL_ENV` on the uv path only** (L475-478, #2803 fix "strip inherited interpreter-path variables from the uv lane gate").
  - Otherwise (production): `_evaluate_via_scope_source` (L955-1049) → `_run_raw_command` (L880-948). That runs `["sh","-c","<rendered review.test_command>"]` with `cwd=repo_root` (the lane) and `env=_gate_run_env()` (inherit + `PWHEADLESS=1`, L96-107). **It does no interpreter-env stripping.** The run is serialized by the machine lock `_scoped_run_lock` (L247-285, #2493).
- Interpreter: for the declared command, whatever the shell resolves. For this repo, `make test-fast` uses `pytest_cmd := .venv/bin/pytest`, relative to cwd, so it uses the lane's `.venv` if one exists (Makefile L147-150). Otherwise it falls back to `uv run --frozen pytest`, which **will create and sync `<lane>/.venv`**. That costs time and network, but the result is the lane's code. An inherited `UV_PROJECT_ENVIRONMENT` would redirect it (hypothesis, see finding 4).

#### Outcomes, severities, exit codes
- `GateOutcome` (L578-598): `no_coverage`, `no_new_failures`, `new_failures`, `unverified_baseline`, `source_mismatch`, `timed_out`, `cancelled`, `skipped`, `scope_oversized`.
- `verdict_aggregation.aggregate_verdicts` (L72-151) is pure. Its precedence is TERMINAL {`timed_out`, `cancelled`, `scope_oversized`} > BLOCK (only `new_failures`, AND `review.fail_on_pre_review_regression`, AND not `--force`) > WARN_PROCEED.
- `_mt_emit_transition_gate_effect` (L1340-1374): terminal or block → `_output_error` with `diagnostic={"result":"error","error":"pre-review gate <outcome>","transition_applied":False,"pre_review_gate":metadata}` and **`typer.Exit(1)`**. Everything else warns and proceeds. There are no named refusal codes (unlike consolidate's `UPPER_SNAKE` codes). ADR `2026-08-13-6` (severity ladder; "trust failures are always BLOCKING") is **not implemented on this path**: there is no `ERROR_SEVERITY` anywhere in `src/`.
- `no_coverage` triggers:
  - (a) an empty narrowed scope (`describe_empty_reason`);
  - (b) `test_command() is None`, i.e. `review.test_command` unset or malformed (`_NO_TEST_COMMAND_REASON`, L953);
  - (c) the run did not complete: launch `OSError` or no JUnit (`"scoped test run did not complete: ..."`);
  - (d) the skip path: flag or env → `_mt_emit_skipped_gate` (L1327-1337) builds `_mt_empty_scope_verdict("gate skipped — <reason>")`, a `no_coverage` with empty scope, and prints `SKIPPED (...)`;
  - (e) empty changed files (`_PRE_REVIEW_NO_CHANGED_FILES_REASON`, L414) and the planning-lane reason (#6792, L418-433);
  - (f) a handler crash → fail-open `no_coverage` (`_mt_fail_open_gate`, L1046).

  A repo with no declared gate gets `skipped` (#3821, `_mt_not_declared_skip_verdict`, L532).
- **Evidence recorded:** `st.pre_review_gate_metadata` is written into the transition's `policy_metadata["pre_review_gate"]` in `status.events.jsonl`. Fields (L576-631): `outcome, reason, new_failure_count, new_failure_nodeids, pre_existing_failure_count, affected_shard_count, matched_shard_groups, matched_composite_dirs, test_targets, block_enabled, blocked, force_bypassed, run_state`. Budget fields are added when present (`budget_classification, scope_identity, effective_budget_seconds, matched_budget_rule, classification_candidate, observed_elapsed_seconds, classification_guidance`), plus `recovery_choices` and `transition_applied`. The baseline artifact has `source_identity` (`scope_source_identity`, the command + parse mode), which feeds `SOURCE_MISMATCH`.
- **What it does not record:** tree path, lane HEAD SHA, dirty state, interpreter, `sys.path` and module origin. The JUnit XML carries a `file` attribute per testcase, but only failures are parsed (`baseline._parse_junit_xml`, L248+), and only the `file:line` of failures is kept.
- Other "evidence" surfaces:
  - `status/models.py` has `DoneEvidence.verification: list[VerificationResult{command, result, summary}]` (L~480-550), populated from the `--evidence` dict in `status/emit.py:486`. This is the existing "verification command" record, but nothing ties it to a tree.
  - `lanes/for_review_gate.py` (318 lines) is the commit gate (`git rev-list <base>..refs/heads/<lane>`, `LANE_BRANCH_MISSING`). It concerns commits, not tests.

#### Regression gate
"Pre-review regression gate" and "pre-review gate" are the same thing (mission `review-regression-gate-01KWX6DF`). Its opt-in block key is `review.fail_on_pre_review_regression` (`_mt_pre_review_block_enabled`, L180).

### 4. Editable install and the probe

- Build backend: hatchling (`pyproject.toml` `[build-system]`, L137). The editable install writes `.venv/lib/python3.11/site-packages/_editable_impl_spec_kitty_cli.pth`, which contains the line `/home/user/spec-kitty/src` (repeated six times), and `spec_kitty_services_editable.pth` → `packages/spec-kitty-services`. `direct_url.json`: `{"url":"file:///home/user/spec-kitty","dir_info":{"editable":true}}`.
- The global shim `/root/.local/bin/spec-kitty` → `~/.local/share/uv/tools/spec-kitty-cli/bin/spec-kitty`. Its `uv-receipt.toml` reads `editable = "/home/user/spec-kitty"`, and its own `_editable_impl_spec_kitty_cli.pth` → `/home/user/spec-kitty/src`. A stale global shim is therefore pinned to the root checkout's `src`. If it were a non-editable wheel, it would be pinned to that wheel's frozen code.
- `pytest.ini`: `pythonpath = src` (rootdir-relative). pytest inserts it at `sys.path[0]` during early config, ahead of the site-packages `.pth` entries.

Probe: throwaway `git worktree add --detach .../scratchpad/wt-probe HEAD`, no venv inside it, then removed and pruned.

| Invocation (cwd = lane unless noted) | `specify_cli.__file__` resolves to |
|---|---|
| bare `python3 -c 'import specify_cli'` (system 3.11) | `ModuleNotFoundError` |
| `<root>/.venv/bin/python -c 'import specify_cli'` | **ROOT** `src` (sys.path[0] = `''`, which has no package; the `.pth` wins) |
| `PYTHONPATH=src <root>/.venv/bin/python -c ...` | lane |
| `<root>/.venv/bin/python -m pytest probe_t` (lane `pytest.ini`) | lane |
| cwd = ROOT, `.venv/bin/python -m pytest <lane>/probe_t` | lane (rootdir and inifile come from the lane path argument) |
| `<root>/.venv/bin/spec-kitty`, `~/.local/bin/spec-kitty` | **ROOT** |
| `PYTHONPATH=<lane>/src <global shim python> -c ...` | lane (kernel and charter also resolve to the lane) |
| `PYTHONPATH=<lane>/src <root>/.venv/bin/python -c 'import specify_cli,kernel,charter'` | all lane |

Notes:
- With `PYTHONPATH` injection, `importlib.metadata.version("spec-kitty-cli")` and the entry points still come from the **root's** dist-info. A version-equality check would therefore not detect cross-tree runs; only a module `__file__` check does.
- `specify_cli/__main__.py` exists, so `python -m specify_cli` works as a lane-correct CLI under `PYTHONPATH`.
- Tests that shell out to the CLI: about 73 test files reference a `"spec-kitty"` argv. The `run_cli` / `isolated_env` fixtures (`tests/conftest.py:~1385-1430`) pop `PYTHONPATH` and set it to `REPO_ROOT/src`, where REPO_ROOT is the conftest's checkout, which makes them lane-correct. Tests that call `["spec-kitty", ...]` with the ambient env resolve the shim on `PATH`, which is the root (hypothesis: not audited per file).

#### Why #5096's guard (`tests/_support/import_origin.py`, called from `tests/conftest.py:224-229`) does not cover the reported cases
1. **It checks self-consistency, not lane identity.** It asserts that `specify_cli` comes from the same checkout as the conftest. An agent that runs `cd <root> && .venv/bin/pytest tests/...` passes the guard while testing the root's (unfixed) code. Nothing ties the run to the lane under review.
2. **It is pytest-only.** It does not cover `python -c`, scripts, `python -m specify_cli`, `spec-kitty` CLI reproduction steps, `mypy`/`ruff` or manual verification. Those are exactly the root-importing cases in the table above.
3. **It is repo-internal.** It lives in spec-kitty's own `tests/`. Consumer projects (any language, any layout) get nothing from it.
4. **It does not fire when the run cannot start.** In the `ModuleNotFoundError: pytest` case (a lane with no venv, bare python), the agent improvises (`PYTHONPATH`, the root venv, the global shim) and the guard never runs or runs elsewhere.
5. **It checks only `specify_cli`, and only the importing process.** Subprocesses the tests spawn (the CLI shim on `PATH`) are not checked.
6. **It records nothing.** Neither review nor the pre-review gate can see that the guard ran or where. Provenance is not in the evidence.
7. **The prompt edit was in `packs/built-in`,** which is fetched from upstream. (Hypothesis: the specific prompt text from #5096 was not located in the current pinned implement/review prompts; grep finds no PYTHONPATH or import-origin wording there. It may have been lost in the open-packs move, or it lives in another step's prompt.)

### 5. Per-file map (likely touch set)

| File | Lines | 90d commits (API) | Responsibility | Notes / invariants |
|---|---|---|---|---|
| `src/specify_cli/lanes/lane_env.py` | 111 | 1 | lane-scoped env mapping (FR-006) | the stable `dict[str,str]` shape is the stated extension contract; tests in `tests/lanes/test_lane_db_isolation.py` |
| `src/specify_cli/lanes/implement_support.py` | 1147 | 50 | lane resolution/creation/reuse, context persist, `LaneWorkspaceResult` | gated by `test_lane_adoption_single_seam.py` (self-heal re-entry, L50) and `test_status_read_single_door.py:229`; CLAUDE.md Execution Workspace Strategy ("implement is the only supported way to prepare a workspace"; "agent commands must consume the resolved workspace path") |
| `src/specify_cli/workspace/context.py` | 1444 | 17 | `WorkspaceContext` and `ResolvedWorkspace`, `resolve_workspace_for_wp` | `test_owned_checkout_single_authority.py:103` (resolve_workspace_for_wp single authority), `test_workspace_resolution_doc.py`, `test_status_read_single_door.py:237`; `from_dict` tolerates unknown keys |
| `src/specify_cli/cli/commands/implement.py` | 478 | 53 | top-level implement CLI, JSON payload, banner | very high churn; `_json_safe_output`; tests `tests/specify_cli/cli/commands/test_implement_{writeside,characterization,phases}.py` (out-of-matrix dir: nightly only, CLAUDE.md baseline-red category 6) |
| `src/specify_cli/cli/commands/agent/workflow_executor.py` | 2650 | 48 | implement/review prompt lines, baseline capture | `test_trio_seam_only.py:97` (workflow.py → cores and executor split), `test_commit_recipe_strings.py:404-412` (recipe strings in this file), `test_no_write_side_rederivation.py:104`, `test_execution_context_parity.py` (agent/** path filter) |
| `src/specify_cli/review/_interpreter.py` | 98 | 6 | `resolve_pytest_command` (uv-run vs `sys.executable`) | `tests/review/test_interpreter_and_scoped_lock.py`; docstring names the #2803 residual (the `sys.executable` fallback is not lane-isolated) |
| `src/specify_cli/review/pre_review_gate.py` | 1289 | 14 | scope → head run → verdict | lock and OS-detect exemptions history (`_exemptions/lock-ban-wp04.txt`, `os-detect-ban-wp04.txt`, now routed via `kernel.locks`/`kernel.paths.is_windows`); 17 test files under `tests/review/` |
| `src/specify_cli/review/scope_source.py` | 501 | 15 | `ScopeSource` port, `DeclaredCommandScopeSource`, `scope_source_identity` | `dead_symbol_allowlist.yaml:188-189,1066-1076` (factory-constructed category); FR-011 "no new config key is invented" in the `test_command` docstring |
| `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` | 1481 | 15 | for_review gate orchestration and metadata | `test_no_write_side_rederivation.py:172`; quarantined `follow_imports="skip"` mypy note (L232-234) |
| `src/specify_cli/review/verdict_aggregation.py` | 151 | – | pure precedence | adding an outcome means deciding membership in `_TERMINAL_OUTCOMES` or BLOCK |
| `src/specify_cli/status/models.py` (`VerificationResult`) | – | – | done-evidence verification rows | an extension candidate for provenance |
| `src/specify_cli/services/resolution.py` (`checkout_root_of`) | – | – | maps a package file to its checkout | reuse it for the CLI self-origin check |

Notable fixes (from the API) on the gate files:
- `pre_review_gate.py`:
  - "strip inherited interpreter-path variables from the uv lane gate" (#2803 follow-up)
  - "baseline capture no longer takes the pre-review-gate lock (#6062)"
  - "skip the pre-review gate in repos that never declared it (#3821)"
  - #6751 (opaque declared-command identity)
  - #6746 (bounded budgets)
  - #3697 (observable/budget-aware)
- `_interpreter.py`:
  - "run lane pytest with declared test extra"
  - "detect a PEP 735 test dependency group for the uv lane gate"
- `tasks_move_task_gates.py`:
  - "capture the for_review baseline at the lane's fork point"
  - #6750
  - #6792 planning-lane reason

Architectural layer: all candidates sit inside `specify_cli` (the top layer). Moving the lane-invocation helper into `kernel` would be a layer decision (`kernel <- charter <- ... <- specify_cli`, `tests/architectural/test_layer_rules.py`). `lanes` vs `status` has a known deferred-import cycle (`for_review_gate.py` docstring L13-18), so keep a new lanes-side helper a leaf. Git reads should go through `kernel.git` (`test_git_path_listing_owner.py`, `test_remote_contact_owner.py`).

Test cost: `tests/review/test_interpreter_and_scoped_lock.py` + `tests/lanes/test_lane_db_isolation.py` + `tests/review/test_pre_review_gate_engine.py` = 83 passed, 1 skipped in **111 s** (serial, root venv). The engine tests spawn real subprocesses, so they are heavy. Budget for that, or use the injectable `wait`/`monotonic`/`process launch` seams (`_ProcessWait`, `_launch_scoped_process`) for unit tests.

### 6. C901 (threshold 11 → nothing ≥12)
`ruff check --isolated --select C901 max-complexity=8` on the candidates gives:

| Function | Location | Complexity |
|---|---|---|
| `_mt_pre_review_gate_console_warning` | `tasks_move_task_gates.py:633` | 11 |
| `commit_workflow_change` | `workflow_executor.py:265` | 10 |
| `_capture_baseline_via_config` | `baseline.py:442` | 10 |
| `_observe_process` | `pre_review_gate.py:368` | 10 |
| `ensure_workspace_materialized` | `workflow_executor.py:517` | 9 |
| `capture_and_commit_baseline` | `workflow_executor.py:1413` | 9 |
| `build_implement_prompt_lines` | `workflow_executor.py:1576` | 9 |
| `resolve_active_wp_for_branch` | `context.py:470` | 9 |

The ceiling is 15. Adding branches to `build_implement_prompt_lines` or the console-warning renderer should go through extracted helpers.

### 7. Candidate seams

**(a) Lane verified-test-invocation seam.** Extend `lanes/lane_env.py` (or a sibling leaf such as `lanes/lane_invocation.py`) with a pure builder: `lane_test_invocation(lane_root, *, mission_slug, lane_id, config_authority_root) -> LaneTestInvocation{cwd, env, argv|shell, probe_argv}`. Sources:
- `review.test_command`, through the one authority `_get_test_command` / `DeclaredCommandScopeSource`; no new config key (FR-011);
- `lane_test_env`;
- the interpreter-isolation rule, unified with `_strip_interpreter_path_env`, which today lives privately in `pre_review_gate.py`. This removes the divergence where only the override tier strips.

**(b) Implement printing and recording it.**
- `LaneWorkspaceResult` / `WorkspaceContext` get a new field, as `lane_test_env` already did (`from_dict` tolerates it).
- `implement --json` gets the field (`implement.py` ~L248).
- `_print_workspace_ready_banner` gets a block next to FR-006 (L310-316).
- `build_implement_prompt_lines` / `build_review_prompt_lines` get a "TEST IN THIS LANE" block (core-owned, no pack edit needed).

**(c) Pre-review gate provenance and refusal.**
- In `_run_raw_command` / `run_scoped_tests_at_head`, capture the run's provenance: cwd, lane HEAD via `kernel.git`, dirty flag, and an optional import-origin probe for Python projects.
- Record it in `_mt_pre_review_gate_metadata` as e.g. `evidence_tree: {path, head_sha, origin_check}`.
- Add a new `GateOutcome` (e.g. `foreign_tree` / code `EVIDENCE_TREE_MISMATCH`) that is a **refusal** regardless of `block_enabled`. That needs a new aggregation tier, because today only TERMINAL refuses unconditionally. ADR `2026-08-13-6` classes trust failures as BLOCKING, which argues for fail-closed.
- For agent-supplied evidence (`--evidence` `VerificationResult`), add `tree`/`head_sha` and have review/approve compare them to the lane tip.

### 8. Design options

| Option | How | Pros | Cons |
|---|---|---|---|
| **Per-lane venv** (`uv sync --frozen` in each lane, or `uv run --project <lane>` creating `<lane>/.venv`) | what `make test-fast`'s fallback and `resolve_pytest_command` already do implicitly | true isolation: deps and code both lane-correct; CLI entry point and metadata lane-correct | slow, disk-heavy and network-dependent per lane; implement would have to bootstrap it (or the first test pays); fails offline; consumer projects may not use uv/Python at all |
| **PYTHONPATH injection** (`PYTHONPATH=<lane>/src` + the root/shared interpreter; CLI via `python -m specify_cli`) | proven by the probe: every module resolves to the lane | zero install, instant, works with the global shim's interpreter | Python- and `src`-layout-specific; `importlib.metadata` version and entry points still come from the root dist-info; dependency drift between the lane's `pyproject`/`uv.lock` and the shared venv goes undetected; the `run_scoped_tests_at_head` docstring notes the `sys.executable` fallback "may rely on inherited PYTHONPATH" while the uv path strips it, so two opposite rules would have to be reconciled |
| **Shared venv + path probe** (keep whatever interpreter; run a cheap origin probe, e.g. `python -c 'import <pkg>; print(<pkg>.__file__)'` or JUnit/`--co` file paths, and refuse when the origin is outside `<lane>`) | `checkout_root_of` already exists for spec-kitty itself | detects instead of prescribing; works with any invocation the agent picks; this is the evidence-provenance half the done-when needs anyway | detection only; for a consumer the package name to probe must be declared or derived (hypothesis: from `pyproject [project.name]`/packages, or a new optional `review.import_probe`); a non-Python project needs a git-tree-only check (cwd + HEAD) |
| **Hybrid (recommended to evaluate)** | (a) implement emits a lane invocation = declared command + cwd = lane + interpreter-redirect env stripped + (spec-kitty/Python) `PYTHONPATH=<lane>/src` only when no lane venv exists; (c) the gate and the review record provenance (cwd, HEAD SHA, origin probe) and refuse a mismatch | each half is independently testable; the probe makes the invocation choice verifiable, which matches "provably imports the lane's code" | two seams to land; the new refusal outcome needs an aggregation and ADR touch |

Open questions for the planner:
1. Does a provenance refusal honour `--force` / `SPEC_KITTY_SKIP_PRE_REVIEW_GATE`? Note that a skip is currently recorded as `no_coverage`, which is indistinguishable from a real gap except by the reason text.
2. Should the declared-command path strip `UV_PROJECT_ENVIRONMENT`/`VIRTUAL_ENV`, as the override tier does?
3. Where should the evidence for manual (non-gate) agent test runs live: `VerificationResult` or a new `policy_metadata` key?

---

## Appendix B — second opinion (reviewer lens)

## Second opinion: lane code verification (#7554 / sub-epic #7547)

Reviewer: reviewer-renata profile, read-only. Charter read; `charter context --action review` loaded.
Checkout `/home/user/spec-kitty` @ `ba45c46c`. Probes ran in a throwaway detached worktree
(`scratchpad/wt-challenge`, no venv, no packs), since removed and pruned (`git worktree list` clean).
Inputs challenged: `research-code-grounding.md`, `research-evidence.md`, `research-foldable.md`.

---

### 1. Confirmed

#### 1.1 Probe table (reproduced, cwd = lane, interpreter = `<root>/.venv/bin/python`)
| Row | Result | Status |
|---|---|---|
| `python -c 'import specify_cli, kernel'` | ROOT `src` for both | confirmed |
| `PYTHONPATH=src python -c ...` | lane | confirmed |
| `python -m pytest` (lane `pytest.ini`, `pythonpath = src`, `pytest.ini:9`) | lane | confirmed |
| `<root>/.venv/bin/pytest` | lane | confirmed |
| `python -m pytest -c /dev/null` (ini ignored) | ROOT | new control: the lane result depends on `pytest.ini` alone |
| cwd = ROOT, `python -m pytest <lane>/ptest` | lane (rootdir and ini come from the path argument) | confirmed |
| inherited `PYTHONPATH=<root>/src` + lane pytest | lane (the ini entry goes ahead of PYTHONPATH) | new, consistent with M1i |
| `<root>/.venv/bin/spec-kitty --version` | runs ROOT code (shebang `#!/home/user/spec-kitty/.venv/bin/python3`, editable `.pth` → `/home/user/spec-kitty/src`) | confirmed |

#### 1.2 Pre-review gate production path
- Production scope source is `DeclaredCommandScopeSource` (`review/scope_source.py:480`, through `tasks_move_task_gates.py:857` `_mt_resolve_scope_source`). Its `test_command()` (`scope_source.py:337-373`) returns `["sh","-c",<rendered review.test_command>]`. The template is read from the **config authority root** (`scope_source_root=_mt_config_authority_root(st)`, `tasks_move_task_gates.py:1222`), not from the lane.
- Run: `_evaluate_via_scope_source` → `_run_raw_command` (`pre_review_gate.py:880-948`). `env=_gate_run_env()` (L96-107) means inherit everything and set `PWHEADLESS=1`. **No strip.** `_strip_interpreter_path_env` (L117-119) is called only at L478, inside `run_scoped_tests_at_head`, and only when `command[0] == "uv"`.
- cwd = `repo_root` = `gate_repo_root = worktree_path or st.main_repo_root` (`tasks_move_task_gates.py:1221`), via `_launch_scoped_process` (`pre_review_gate.py:408-435`, `cwd=str(repo_root)`).
- No tree provenance. `_mt_pre_review_gate_metadata` (`tasks_move_task_gates.py:569`) has no path, HEAD, dirty or origin field.
- `no_coverage` triggers (a)-(f) are as listed in code-grounding §3. The skip path builds a `no_coverage` verdict (`_mt_emit_skipped_gate`, L1327), so a skip and a real coverage gap can only be told apart by the reason text. Confirmed.

#### 1.3 `resolve_pytest_command`'s `sys.executable` fallback (#5985) is not on the production path
`resolve_pytest_command` has exactly one caller, `run_scoped_tests_at_head` (`pre_review_gate.py:471`). That is reached only when `scope_source is None` (L1114-1121), which happens only in the **FR-004 WP-frontmatter `pre_review_test_scope` override tier** (`tasks_move_task_gates.py:374-392`). Within that tier, the fallback fires only without `uv` on PATH, or when the lane has no `pyproject.toml` + `uv.lock` pair (`_interpreter.py:87`). The research's framing overstates it (see 2.4).

#### 1.4 Seam and backward compatibility
- `WorkspaceContext.from_dict` drops unknown keys (`workspace/context.py:197-209`), so a new field reads safely from old context files and vice versa.
- `implement --json` is a hand-built dict (`implement.py:231-249`). No contract fixture, JSON schema or golden file pins its key set. The only key-set assertion is the error envelope (`test_implement_characterization.py:1062`, `{"status","error","wp_id"}`). `test_implement_phases.py:312` asserts `payload["lane_test_env"] == {}` for a planning lane. `tests/lanes/test_lane_db_isolation.py:193,224,265` index by key or compare a hand-built context. **New top-level JSON keys and new context fields are additive-safe.** The orchestrator-api `CONTRACT_VERSION` (`orchestrator_api/envelope.py:216`, 1.27.0) does not cover `implement --json`.
- `policy_metadata` is a free dict in `spec_kitty_events.diary` (`diary.py:491`), so nested keys under `pre_review_gate` are safe. `cutover_eligibility._policy_metadata_carries_runtime_evidence` already counts a `pre_review_gate`-only dict as runtime evidence, and a nested field does not change that.

#### 1.5 Fold calls I agree with
- #2803 is closed. #3959 is perf (REFS). #1907: fold only the detection half. #3074, #5140, #6851 and #3260 are REFS. #2330 is a design constraint. The PR collision call is correct: only #7562 overlaps.

---

### 2. Refuted or corrected

#### 2.1 "PYTHONPATH makes every invocation import the lane" (code-grounding §4/§8)
It is true for imports, but not for the rest of what the lane needs.
- **`-I` (and `-P`/`PYTHONSAFEPATH`) ignore PYTHONPATH.** Reproduced: `PYTHONPATH=src python -I -c ...` imports ROOT. The evidence tracer `runtime-status-read-door…:19` reports the same.
- **The lane CLI does not run under PYTHONPATH in an unsynced lane.** `PYTHONPATH=<lane>/src <root>/.venv/bin/spec-kitty --version` fails with `charter.offering.pack_paths.BuiltInPackMissing`, because the lane has only `packs/*.source.yaml`. The same `<root>/.venv/bin/spec-kitty --version` without PYTHONPATH succeeds, running ROOT code. Pack-touching tests fail the same way under lane pytest. **A lane-correct import is necessary but not sufficient:** the untracked generated inputs (`packs/built-in`, `packs/internal`) must also be present or redirected. This is the dominant post-#5913 friction (M4, 8 missions), and none of the reports put it in the design.
- **uv workspace member stays on ROOT.** `spec_kitty_services` resolves to `/home/user/spec-kitty/packages/spec-kitty-services/...` even under lane pytest (`spec_kitty_services_editable.pth`). PYTHONPATH=`<lane>/src` does not cover it. A strict rule of "any module loaded from another worktree refuses" would false-refuse every dogfood gate run that uses the shared venv.

#### 2.2 "Put the invocation in `lane_test_env`" (code-grounding headline 1 / §7a)
`lane_test_env` is typed `dict[str,str]` of **env vars**. It is printed verbatim as `export K=V` (`implement.py:311-317`), and its docstring promises callers can `env.update(...)` it. A command, a cwd, an unset-list and a probe result do not fit that shape. Putting `PYTHONPATH` in it would silently inject it into every future `env.update` caller, which contradicts the uv-path strip at `pre_review_gate.py:478`. The seam is right (`LaneWorkspaceResult` → `WorkspaceContext` → `implement --json` → banner); the field is not. Add a **sibling** field (`lane_test_invocation`) and keep `lane_test_env` as the env sub-part.

Also: **nothing reads the persisted `lane_test_env` back.** `grep` finds only writers and printers, and the pre-review gate never merges it. The FR-006 test-DB isolation therefore does not apply to the gate's own run. This is a latent gap the same seam closes.

#### 2.3 "ADR 2026-08-13-6 says trust failures are BLOCKING, so fail closed" (code-grounding §7c)
In that ADR, "trust and tamper failures" means **pack and executable-doctrine trust** (ADR -2 and -4, untrusted publishers). It does not mean the provenance of test evidence. Reading a foreign-tree run as a "trust failure" is an extension that needs an operator ruling and an ADR amendment. The ADR also restates the **C-003 invariant: gate evaluation never breaks `move-task`** (fail-open via `_mt_fail_open_gate`). A new refusal tier collides with C-003 and has to be carved out explicitly.

#### 2.4 "#5985 is exactly #7554 inside the gate" (foldable)
Overstated.
- The production (declared-command) path never calls `resolve_pytest_command` (see 1.3).
- In this repo, the override tier with the fallback would still import the lane through `pytest.ini`.
- In a consumer repo without `uv.lock`, `sys.executable` is spec-kitty's own tool venv. That venv usually lacks pytest and the consumer's dependencies, so the result is `no_coverage`, not a wrong-tree run.

##5985 item 2 is a small, legitimate fold *if* the override tier is re-pointed at the shared lane-invocation builder. #5985 item 1 ("should `no_coverage` refuse") is a separate policy question with a large blast radius (every `no_coverage` trigger, C-003). Do not fold it under "refuse foreign evidence".

#### 2.5 `UV_PROJECT_ENVIRONMENT` is understated (code-grounding finding 4)
`make test-fast` falls back to `uv run --frozen pytest` when the lane has no `.venv/bin/pytest`. With an inherited `UV_PROJECT_ENVIRONMENT=<root>/.venv`, uv would **sync the root venv to the lane project**, which includes re-installing the editable `.pth` to point at the lane. That is the #1907 / M5a repoint, a destructive side effect on the root checkout, not just a wrong-tree read. This is a hypothesis (I did not run a sync), but it follows uv's documented project-env semantics. `VIRTUAL_ENV`, by contrast, is ignored by `uv run` in project mode unless `--active` is passed (uv 0.11.32 here), so stripping it mainly matters for non-uv commands. **The declared path should get the same strip as the uv override path.** That is a one-line, low-risk fix.

---

### 3. Missed

1. **Subprocess children escape `pytest.ini`.** Probe K: a lane pytest test runs `subprocess.run([sys.executable, "-c", "import specify_cli"])`, and the child prints ROOT `src` (`PYTHONPATH` unset). An in-process origin check (the #5096 guard, or a pytest-plugin probe) passes while CLI-shelling tests exercise root code. M3b is exactly this. Env-level `PYTHONPATH` (or a lane venv) propagates to children; `pytest.ini` does not. **The proof must therefore probe a child process launched with the invocation's own env and cwd**, not pytest's `sys.path`.
2. **Packs and untracked generated inputs** (2.1). `kernel/paths.py:38` already owns one `SPEC_KITTY_PACKS_ROOT` override, a candidate redirect when the lane pins equal the root pins. Otherwise implement should warn or refuse "packs not synced in this lane". This is a spec-kitty dogfood concern; a consumer project has no packs tree to sync.
3. **The orchestrator-api `for_review` path never runs the pre-review gate.** `orchestrator_api/wp_lifecycle.py:910-911` runs only `_enforce_for_review_commit_gate`. "The gate refuses foreign evidence" covers `move-task` only. External orchestrators bypass it. That is a REFS item or a new issue; the contract version is unaffected unless the gate is added there.
4. **No argv injection is possible for the declared command.** The run is `[*["sh","-c",cmd], *targets]`, so anything appended becomes `$0`/`$1`, not pytest args (acknowledged at `pre_review_gate.py:657-667`). This repo's command sets `PYTEST_ADDOPTS=` inline (`.kittify/config.yaml:27`), which overrides any inherited `PYTEST_ADDOPTS`, so a provenance plugin cannot be injected through the env either. **Provenance must come from a separate probe process with the same env and cwd**, plus git facts. It cannot be instrumented inside the user's run.
5. **Baseline is another tree by design.** It is captured in a detached base-branch worktree (`workflow_executor.py:1413`; at the for_review fork point per ADR 2026-10-12-1). A tree or HEAD field must not enter `scope_source_identity`. If it did, every existing baseline would flip to `SOURCE_MISMATCH`. Record the tree beside the identity, never inside it.
6. **Package-name derivation for consumers.** `[project].name` is not the import name (`spec-kitty-cli` → `specify_cli`, `kernel`, `charter`, `runtime`, `glossary`, `mission_runtime`). A cheap and reasonably general rule is the top-level packages tracked in the lane (`git ls-files` of `src/*/__init__.py`, else `*/__init__.py` at the root, via `kernel.git`), checked so that origin is under the lane. Namespace packages (no `__init__`) are invisible to that rule and degrade to "unverified". Non-Python projects get git-only provenance (cwd = lane, HEAD SHA, dirty flag), recorded and never refused.
7. **Windows.** The declared path already returns `None` (→ `no_coverage`) when no POSIX shell exists. A PYTHONPATH join must use `os.pathsep`. Any OS branch must go through `kernel.paths.is_windows` (the OS-detection ban scans `src/`).
8. **Verdict-aggregation test enumerates outcomes.** `tests/review/test_verdict_aggregation.py:40-46` (`_NON_TERMINAL`, `_TERMINAL`) must learn any new `GateOutcome`. TERMINAL outcomes are **not `--force`-bypassable** (`verdict_aggregation.py:124-131`: terminal precedes block); only the skip flag or env var bypasses them. Placing a new outcome in TERMINAL vs BLOCK is the policy choice.
9. **Agent-supplied evidence surfaces cannot carry tree data today without an external release.** `VerificationResult{command,result,summary}` (`status/models.py:480`) mirrors `spec_kitty_events.status.VerificationEntry` (`status.py:416`, `ConfigDict(frozen=True)`, extra *ignored*). New fields would be silently dropped on the library parse path unless `spec-kitty-events` is released, and per CLAUDE.md a fix there is consumed only via PyPI. Review-cycle artifacts and `review_result` carry no tree either. **Today the only evidence the CLI controls end to end is the gate's own run**, so "refuse evidence from another tree" can only mean "the gate refuses its own run when its probe shows a foreign origin". Agent-reported runs can only be *recorded*, not refused, in this mission.

---

### 4. Architectural gates a new module would meet
- **Layering:** all candidates are inside `specify_cli`. `review/` does not import `lanes/` today; it imports `status`. Keep the invocation builder a leaf (`lanes/lane_invocation.py`, beside `lane_env.py`) that imports only `kernel` and stdlib. Gate code (`review/`) and implement (`lanes/`, `cli/`) both consume it. This avoids the known `lanes`↔`status` deferred-import cycle. No `LayerRule` blocks `review → lanes`; still prefer injecting the invocation through `TransitionGateContext` to keep `review/` free of a new edge.
- **`test_git_path_listing_owner.py`** (empty allowlist): any dirty check (`status --porcelain`) or path listing must go through `kernel.git` (`status_entries`, `tree_paths`). Read HEAD with the existing `status/lane_head.py` reading, not a new `rev-parse`.
- **OS-detection ban** (`_os_detection_scan.py`, `src/` only): use `kernel.paths.is_windows`.
- **Dead-symbol gate** (`test_no_dead_symbols.py`, `__all__` plus non-`__all__` cross-module names) and charter C-007 `__all__` convention: every new public name needs a production caller in the same PR.
- **Lock-primitive ban:** reuse `_scoped_run_lock` (`kernel.locks`); no new lock.
- **CI routing:** the `ci-module-registry.yml` globs `src/specify_cli/lanes/**` and `src/specify_cli/review/**` cover new files, so `test_gate_selection_authority.py` is unaffected.
- **Single-seam gates:** `test_lane_adoption_single_seam.py` and `test_lane_allocation_single_seam.py` cover `implement_support.py`/`worktree_allocator.py`. Add the field at the existing `lane_test_env=` sites (`implement_support.py` fresh / reuse / return; `worktree_allocator.py:954-978`) rather than as a new allocation path. `test_no_write_side_rederivation.py` lists `tasks_move_task_gates.py`: the gate must consume the persisted or rebuilt invocation through the builder, not re-derive paths.
- `tests/specify_cli/cli/commands` is out of matrix (nightly only), so the implement CLI tests need an explicit local run.

---

### 5. Recommendation

#### Design: "one lane-invocation builder, env-scrubbed, child-probed, recorded; refuse only on proven foreign origin"
1. **Builder (new leaf `lanes/lane_invocation.py`):**
   - Signature: `build_lane_test_invocation(lane_root, *, mission_slug, lane_id, config_root) -> LaneTestInvocation{cwd, command, env_unset, env_set, interpreter_strategy}`.
   - `command` is `review.test_command` through the one authority `_get_test_command` (FR-011: no new config key).
   - `env_unset` is `PYTHONPATH`, `UV_PROJECT_ENVIRONMENT`, `VIRTUAL_ENV`.
   - `env_set` is `lane_test_env(...)` plus, **only for a Python src-layout lane with no `<lane>/.venv`**, `PYTHONPATH=<lane>/src` joined with `os.pathsep`.
   - Do not build per-lane venvs by default: that costs time, network and contention (M5b), and #3959 is the perf track.
2. **Probe:** run one child process with exactly that env and cwd. For Python, it checks `__file__` of the lane's tracked top-level packages against the lane root. It returns `verified | foreign(origin) | unverified(reason)`. Non-Python projects get `unverified(non-python)` and only git provenance. This is the "provably imports the lane's code" proof. The acceptance test is the planted-change test from the done-when: plant a sentinel in the lane `src`, and the probe and the printed command must see it.
3. **implement:**
   - Add `lane_test_invocation` (with probe result) to `LaneWorkspaceResult`, `WorkspaceContext` and `implement --json`.
   - Banner block beside FR-006.
   - A "TEST IN THIS LANE" block in `build_implement_prompt_lines` / `build_review_prompt_lines`. These are core-owned, so no open-packs pin bump is needed and there is no collision with #7425.
   - Warn when the lane pins packs but the tree is missing.
4. **Gate:**
   - The declared path and the override path both take env and cwd from the builder. This applies the strip on the declared path, applies `lane_test_env` to the gate, and replaces the `sys.executable` fallback with the lane invocation (#5985 item 2).
   - Run the probe first and record `pre_review_gate.evidence_tree = {path, head_sha, dirty, probe}` beside, never inside, `scope_source_identity`.
   - Refuse (new outcome, e.g. `foreign_tree`) only on `probe == foreign`.
   - Treat the root-venv `spec_kitty_services` case as out of the probed set, because only tracked lane packages are probed.
   - `unverified` is recorded, never refused.

Why not the alternatives:
- Per-lane venv is correct but slow and network-bound, and it fails offline.
- Bare PYTHONPATH injection without a probe proves nothing under `-I`, and nothing for packs.
- A probe without the env scrub detects but leaves `UV_PROJECT_ENVIRONMENT` able to repoint the root venv.

#### Fold set
- **CORE:** #7554.
- **FOLD:**
  - #5985 **item 2 only** (the override tier uses the builder).
  - The newly found gap "gate ignores `lane_test_env`" (no issue yet; file it or fold it as an FR).
  - Strip on the declared path (part of #7554's gate half).
  - #1907 detection half (the probe reports a repointed or foreign origin).
- **REFS, not fold:**
  - #3123: a lock-parity / ambient-PATH diagnostic, a different surface; the builder can serve it later.
  - #5985 item 1 (policy).
  - #3959, #3074, #5140, #6851, #3260, #2330, #7361.
  - Orchestrator-api gate absence: new issue.

#### Decisions the operator must rule on
1. **Refusal severity of `foreign_tree`:**
   - TERMINAL (not `--force`-bypassable, skip env only);
   - BLOCK, force-bypassable and independent of `fail_on_pre_review_regression`;
   - or record-only.

   TERMINAL or BLOCK needs an ADR 2026-08-13-6 amendment and a C-003 carve-out.
2. **Default interpreter strategy:** PYTHONPATH injection over the shared venv (recommended), or a lane venv (`uv sync` at implement).
3. **Packs in lanes:** whether in scope. Options: an `SPEC_KITTY_PACKS_ROOT` redirect when pins match, implement running or requiring `make sync-packs`, or warn-only.
4. **#5985 item 1:** should `no_coverage` (pytest not importable) refuse? Recommend no for this mission.
5. **Whether "spec-kitty implement" in the done-when also covers the `agent action implement` / review prompt lines.** Recommended yes: that is where agents actually read.
6. **Consumer scope:** non-Python projects get recorded git provenance only and are never refused. Confirm.
7. **Orchestrator-api `for_review`** runs no pre-review gate: in scope or a separate issue?

---

## Appendix C — tracer evidence (researcher lens)

## Evidence: lane-worktree interpreter/import-origin friction (#7554 / sub-epic #7547)

Researcher: researcher-robbie profile, read-only. Checkout `/home/user/spec-kitty` (shallow, 50 commits, so
`git log` dating of tracer files is not usable; dates come from `meta.json` `created_at` and the dated
entries themselves). Paths below are relative to `kitty-specs/` unless they start with `src/`, `tests/`, `docs/`.

### 0. The cut line: PR #5913 (fix for #5096)

- Merged **2026-10-08T17:25:53Z** (`gh api repos/spec-kitty/spec-kitty/pulls/5913`).
- Scope: `tests/_support/import_origin.py` (`assert_checkout_source`), called from `tests/conftest.py:23,228`
  in `pytest_configure`; raises `specify_cli imported from outside this checkout` when `specify_cli.__file__`
  is not `<checkout>/src/specify_cli/__init__.py`. Also: implement prompt asks for the consumer's configured
  linter, and upgrade-preview fixtures use the active interpreter / `shutil.which("spec-kitty")` instead of
  `<cwd>/.venv/bin/python`.
- Its own landing notes say the guard is a **backstop that does not fire in normal setups**, because
  `pytest.ini:9` `pythonpath = src` already puts the checkout's own `src` first for pytest (PR #5913 body,
  "Landing pass"). Its "Deferred" section: "Lane interpreter provisioning and the separate pre-review
  `no_coverage` diagnostic facet (#2803) remain outside this fail-loud scope."
- CHANGELOG: `docs/changelog/CHANGELOG.md:594`.
- Consequence for dating: **the guard covers only pytest processes.** It cannot see `python -c`, scripts,
  the `spec-kitty` console script (shim or editable), subprocesses a test spawns, or the pre-review gate's
  own interpreter. No tracer anywhere records the guard firing (`grep -rn "imported from outside" kitty-specs` → 0 hits).

### 1. Mechanism table

Counts = distinct missions whose tracers record the symptom (an entry may count under two mechanisms).
"Post" = mission created on/after 2026-10-08 or entry dated after it.

| ID | Mechanism | Pre-#5913 | Post-#5913 | Best exemplars |
|----|-----------|-----------|------------|----------------|
| M1 | pytest / `python -m pytest` with the root venv imports root `src` (or agents believe it does) | ~21 | 1 symptomatic, 2 confirming mitigation | test-suite-friction F5; verdict-matrix L35-37; journal L437-464; event-push L88-101 |
| M1i | Inverse: `pytest.ini pythonpath=src` pins lane `src`, so a base/other-tree overlay via `PYTHONPATH` is silently shadowed (base-vs-head proofs run the fixed code) | 4 | 2 | honest-consolidation L7; single-rollback L8; lane-worktree-model-hardening L60 |
| M2 | Non-pytest Python (`python -c`, repro scripts, `scripts/docs/*`) needs a hand-built `PYTHONPATH` | 8 | 3 | startup-assess F-4; runtime-status-read-door L19; event-push L181-190 |
| M3a | Stale/global `spec-kitty` shim (pyenv, pipx, `uv tool`, sibling clone) shadows the checkout CLI | 9 | 3 | requirement-id-grammar L5; analyze-prompt L313-331; docsite-frontmatter L22 |
| M3b | Checkout CLI (editable) cannot run lane code; anything that shells out to `spec-kitty` runs root `src` | 5 | 1 | startup-assess F-4; runtime-status-read-door L16 |
| M3c | Self-hosting: `consolidate` runs from the editable checkout it lands into, mixes old/new modules mid-run (`ImportError`) | 1 | 2 | single-branch-topology-honesty L15 (#5334); lane-worktree-model-hardening L115-128 |
| M4 | Lane worktree has no venv, or a venv without extras (`pytest`/`ruff`/`respx`/`pytestarch`/`pip`); `ModuleNotFoundError`; packs missing | ~27 | 8 | design-phase L203-222; test-suite-friction L40-51; quick-win L11,L15; runtime-status-read-door L15 |
| M5a | Editable install repointed / shared venv bound to the wrong tree | 3 | 1 | event-push L88-101; journal L437-457; reject-invalid L7 |
| M5b | Per-run test-venv bootstrap (`.pytest_cache/spec-kitty-test-venv`) cost, lock contention, staleness (#3283; #3959-adjacent) | 2 | 5 | op-record L8; cascade-stem L7; owned-refusal L5 |
| M6a | Pre-review gate `no_coverage` because its interpreter lacks pytest (runs outside project env) | 3 | 0 recorded | templates-as-config L133-137, L283; implement-review-loop-recovery L17 |
| M6b | Pre-review gate `no_coverage — no changed files` / excluded scope (wrong tree or branch diffed) | 2 | 2 | journal L153-164; events-service-cutover L11; docsite-publication-llms-parity L6 |
| M6c | Pre-review gate timeouts / `source_mismatch` / empty scope (no verdict at all) | 3 | ~19 | live-fresh-claim L9; companion-wheel L7; residue-safe L14,L18 |
| M7 | Verification not carried forward: each implementer/reviewer rediscovers env + test command, reviewers re-run tests | 4 (tracer) | 3 (tracer) + gist C6/3.3/6.7/7.5 | runtime-status-read-door L15; docsite-publication L6; gist 7.5 |

### 2. Occurrences by mechanism (file:line, date, symptom, workaround)

#### M1 — pytest with the root venv imports root `src`

Pre-#5913:
- `test-suite-friction-remediation-01KXDKBX/tracer-tooling-friction.md:11` (2026-07-13): "F5 — In a clone/lane, bare `python`/`pytest` imports the PRIMARY src." Workaround: `.venv/bin/…` or `uv run`. Confirmations at `:40`, `:42`, `:44` (WP06/WP11/WP12) and `:51` (WP05).
- `coord-shadows-followups-01KXBCZ1/traces/tooling-friction-trace.md:17` (2026-07-12): bare pytest imports PRIMARY editable install; `uv run` builds lane-local venv.
- `mission-type-single-source-gate-wiring-01KXKHVZ/traces/tooling-friction.md:11` (2026-07-15); `mission-step-authority-01KXNZMT/traces/tooling-friction.md:15` (2026-07-16): same rule, "always `uv run`".
- `loop-reliability-ci-red-burndown-01KXWWD6/traces/tooling-friction.md:6` (2026-07-19): "bare `uv run pytest` in a lane tests PRIMARY src, #2803".
- `journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:437-464` (2026-07-28): CRITICAL ADDENDUM — `_editable_impl_spec_kitty_cli.pth` holds the main checkout's absolute path; before/after across worktrees imported identical source, producing "byte-identical" tautologies. Workaround: `PYTHONPATH=$WT/src` or dedicated venv; claims re-verified (`:506-529`).
- `resolution-activation-foundation-01KZ9FKG/traces/tooling-friction.md:66-69` (2026-08-05): "Lane worktree editable-install trap … false green/red. Passed this instruction to every implement/review subagent."
- `dossier-guard-reexport-analyze-cleanup-01M0NHRT/tracer-tooling-friction.md:289` (2026-08-22): root `.venv` + `PYTHONPATH=<lane-b>/src`.
- `accept-path-remediation-honesty-01M0TWZP/tracer-tooling-friction.md:192-201` (2026-08-24): venv absent in lane; must set `PYTHONPATH=<worktree>/src` and check `specify_cli.__file__`; "a wrong-copy false-green here would be maximally deceptive".
- `custom-mission-guard-failure-blocking-inert-01M0STY0/tracer-tooling-friction.md:218-225` (2026-08-24): "lane worktrees do not carry the venv."
- `next-committed-state-authority-01M1CA8W/tracer-tooling-friction.md:14` (2026-08-31): global pyenv `python`/`pytest` resolve `specify_cli` to a sibling clone.
- `design-phase-orchestrator-api-01M1HE6M/tracer-tooling-friction.md:203-222` (2026-09-02): root venv resolves `3837/src`; fixed by `uv sync --frozen --all-extras` inside the lane.
- `event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:25-31` (2026-09-03): `PYTHONPATH="$(pwd)/src" /primary/.venv/bin/python -m pytest`; `:181-190` clarifies that `pytest.ini pythonpath=src` alone suffices for pytest, PYTHONPATH still needed for bare `python -c`.
- `verdict-matrix-rmw-preservation-01M32M9G/tracer-tooling-friction.md:35-37` (2026-09-22): "must run as `PYTHONPATH="$PWD/src" <main>/.venv/bin/python -m pytest` or they silently import the MAIN checkout's (unfixed) editable source."
- `ownership-boundary-overwrite-hardening-01M35ER3/traces/tooling-friction.md:13` (2026-09-22): `PYTHONPATH=<worktree>/src` + in-process CliRunner.
- `upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-blast-radius.md:4-58`, `tracer-red-first.md:26,58` (2026-09-24): every recorded command carries `PYTHONPATH="$PWD/src" <repo-root>/.venv/bin/python -m pytest`.
- `ci-nightly-interpreter-matrix-45min-timeout-01M3G17F/tracer-tooling-friction.md:297-312` (2026-09-26): ran root venv because diff touched no `src/`; "A WP whose diff DOES touch `src/` would need to `uv sync` a lane-local venv first".
- `audit-archived-missions-conflict-markers-4957-01M3G1GP/traces/tooling-friction.md:17` (2026-09-27): symlinked root venv → `identify_source` "Source mismatch"; built lane venv (~2 min).
- `charter-epic-golden-path-nfr-budget-01M35H35/tracer-approach.md:178`, `tracer-design-decisions.md:868` (2026-09-22): PYTHONPATH pointed at the integration worktree's `src/`.
- `upgrade-project-global-state-01M44538/traces/tooling-friction.md:8,15` (2026-10-04): "import root `src/` unless `PYTHONPATH=src` is set (also #5096 territory)".
- `implement-degod-01M44488/traces/tooling-friction.md:27-28` (2026-10-04): new lane reuses root editable install; needed own `uv sync --frozen --all-extras`.
- `pack-shipped-builtin-override-sanction-01M45WB7/traces/tooling-friction.md:10` (2026-10-05): "Every implementer had to be told this."
- `skill-surface-upgrade-integrity-01M482Z3/traces/tooling-friction.md:12` (2026-10-06): `PYTHONPATH=<worktree>/src` or pytest.ini's pythonpath.

Counter-evidence (pytest already lane-correct via `pytest.ini`): `single-branch-claim-gaps-01M43MVY/traces/tooling-friction.md:9` (2026-10-04) "`pytest.ini` `pythonpath = src` makes pytest in the lane worktree import the lane's own code. I verified this … Anything that shells out to `spec-kitty` would still run the root checkout's code." This, plus `event-push…:181-190`, shows that by Sept–Oct many M1 reports reflected agent belief and folklore rather than the pytest path actually failing. PR #5913's landing notes agree.

Post-#5913:
- `persistent-deactivation-ledger-01M59YAA/traces/tooling-friction.md:29` (2026-10-20): "A base-comparison worktree needs its own src on PYTHONPATH. The editable install imports the main checkout's `src`, so a plain run inside a scratch worktree silently tests HEAD." Workaround `PYTHONPATH=<wt>/src:<wt>`. Invocation form not stated. Under pytest the guard would have fired, so this is most likely a non-pytest run (M2) or a run from outside the scratch tree.
- Mitigation confirmed: `quick-win-remediation-01M72855/traces/tooling-friction.md:11` (2026-11-10) "tests ran with the root .venv interpreter (pytest.ini pythonpath=src resolves the lane's sources)"; `runtime-status-read-door-01M73HHB/traces/tooling-friction.md:16` (2026-11-11) "`pytest` imports the lane's code only because the lane's `pytest.ini` sets `pythonpath = src`".

#### M1i — `pythonpath=src` shadows a deliberate overlay

- `lane-branch-naming-authority-01M3EVC4/traces/tooling-friction.md:34` (2026-09-26): "`pytest.ini` `pythonpath=src` overrides PYTHONPATH unless run from the target tree." Filed #5160.
- `honest-consolidation-txn-start-01M3M0YW/traces/tooling-friction.md:7` (2026-09-28): "`PYTHONPATH=<main>/src` does **not** give a base run from inside a lane: the first 'base red' proof silently ran the fixed code (9/9 green)." Base run must happen from the repo root.
- `single-rollback-authority-01M3RCP4/traces/tooling-friction.md:8` (2026-09-30): scratch `src` on PYTHONPATH is shadowed; planted-break proof must edit the worktree.
- `single-branch-claim-gaps-01M43MVY/traces/tooling-friction.md:9` (2026-10-04): verified before trusting red→green.
- Post: `lane-worktree-model-hardening-01M6QY1M/traces/tooling-friction.md:60` (2026-11-06): "the red-first check needed a separate base export because PYTHONPATH pins the lane src." `persistent-deactivation-ledger-01M59YAA/traces/approach.md:23` (2026-10-20): base `src` overlaid through `PYTHONPATH` for NFR timing.

#### M2 — non-pytest Python

- `event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:186-190` (2026-09-03): explicit PYTHONPATH still needed for bare `python -c "import specify_cli"`.
- `startup-assess-cold-concurrency-01M3EQ9S/tracer-tooling-friction.md:13` (F-4, 2026-09-26) and `tracer-approach.md:16`: repro against lane tip only via "a hand-built `PYTHONPATH`-prefixed interpreter wrapper … verified with a manual `hasattr(build_serialized)` probe"; asks for `--pythonpath-override` or `spec-kitty --lane <slug>`.
- `implement-rework-resume-01M3QA1X/traces/approach.md:5` (2026-09-29): "Green via real CLI (lane code on `PYTHONPATH`)".
- `mission-status-health-drift-ops-01M464D3/tracer-tooling-friction.md:19` (F-11, 2026-10-05): `compute_lanes` scratch check needs `PYTHONPATH=src`.
- Docs scripts need `PYTHONPATH=.` (package-root flavour): `team-kitty-launch-defaults-01M1XJ4Y/traces/tooling-friction.md:19` (2026-09-07), `tech-agnostic-language-fallback-01M3NP53/traces/tooling-friction.md:21` (2026-09-29), `charter-test-cwd-isolation-01M43CM3/traces/tooling-friction.md:16` (2026-10-04), `upgrade-outcome-single-rendering-01M444Q6/traces/tooling-friction.md:16` (2026-10-04).
- Post: `command-skill-names-and-antigravity-01M5DBWT/traces/tooling-friction.md:9` (2026-10-21) `ModuleNotFoundError: scripts`; `lane-worktree-model-hardening-01M6QY1M/traces/approach.md:33` (2026-11) "scripts/docs checks need PYTHONPATH=<worktree>"; `runtime-status-read-door-01M73HHB/traces/tooling-friction.md:19` (2026-11-11): "repro scripts cannot run with `python -I` plus `PYTHONPATH` … `-I` ignores `PYTHONPATH`". Workaround: manual `sys.path` insert.

#### M3a — stale global `spec-kitty` shim

- `single-authority-topology-cleanup-01KVRJ6P/traces/tooling-friction-trace.md:52-54` (2026-06-22): pipx non-editable 3.2.2; `pipx install --force --editable .`.
- `coord-read-residuals-…-01KW2M8V/traces/tooling-friction-trace.md:44` (2026-06-26): version-mismatched binary from another clone's venv.
- `next-committed-state-authority-01M1CA8W/tracer-tooling-friction.md:9,15` (2026-08-31): CLI editable from a sibling clone; live `next` proof needs `PYTHONPATH=<lane>/src`.
- `token-target-issuer-guard-01M319HS/traces/tooling-friction.md:5` (2026-09-21).
- `verdict-matrix-rmw-preservation-01M32M9G/tracer-tooling-friction.md:15-17` (2026-09-22): "Global `spec-kitty` shim is 4.0.0rc4 (pyenv)".
- `analyze-prompt-context-load-01M3F4BV/tracer-tooling-friction.md:313-331` (2026-09-27): a test's `shutil.which` found stale `~/.local/bin/spec-kitty` v3.2.7 ahead of `.venv/bin` (rc5), so an architectural gate became "vacuous … false green with no env override, false red with the worktree-scoping override". Workaround: prepend `.venv/bin` to `PATH`. Same entry `:288-307`: `regenerate-graph` resolves `built_in_root()` via install location and wrote into the main checkout. Workaround `SPEC_KITTY_PACKS_ROOT`.
- `requirement-id-grammar-01M3NRCA/traces/tooling-friction.md:5` (2026-09-29): pyenv shim → stale 4.0.0rc3; "The alignment lens ran its first repro on rc3 by mistake."
- `coord-artifact-single-home-01M3V4BE/traces/tooling-friction.md:15` (2026-10-01): editable of a sibling checkout; `--json` reports rc3, `--version` rc5. `traces/approach.md:29`: dedicated throwaway venv `pip install -e <lane>` for NFR timing.
- `shared-collection-and-shard-recapture-01M42V58/traces/tooling-friction.md:6` (2026-10-04): PATH `spec-kitty` is a separate pipx install.
- **Post:** `owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/tracer-tooling-friction.md:5` (2026-10-29): cached test venv and global `uv tool` install kept old `spec_kitty_events` → "16 false reds and a crashing CLI until both were rebuilt."
- **Post:** `docsite-frontmatter-migration-01M6BRJK/traces/tooling-friction.md:22,26` (2026-11-01): PATH `spec-kitty` = uv-tool editable from `/opt/spec-kitty`, 257 commits behind, same `4.0.0rc8` string; lifecycle commands ran stale code through WP02 for_review; fix `uv tool install --force --editable .`; asks that `--version` print the import path.
- **Post:** `report-only-pinned-pack-inputs-01M6GRG8/traces/tooling-friction.md:9` (2026-11-03): `record-analysis` recorded with `uv run` (editable) is immediately stale under global `~/.local/bin/spec-kitty`.

#### M3b — checkout CLI cannot run lane code

- `startup-assess-cold-concurrency-01M3EQ9S/tracer-tooling-friction.md:13` (F-4, 2026-09-26): "Neither the global `spec-kitty` nor `.venv/bin/spec-kitty` can be pointed at a lane worktree's code".
- `ownership-boundary-overwrite-hardening-01M35ER3/traces/tooling-friction.md:13` (2026-09-22).
- `single-branch-claim-gaps-01M43MVY/traces/tooling-friction.md:9` (2026-10-04).
- `upgrade-project-global-state-01M44538/traces/tooling-friction.md:14` and `second-clone-origin-reconciliation-01M48V8W/traces/tooling-friction.md:6` (2026-10-04/06): tests hard-coding `<cwd>/.venv/bin/python` red in lanes. This is the part PR #5913 fixed.
- **Post:** `runtime-status-read-door-01M73HHB/traces/tooling-friction.md:16` (2026-11-11): "Any test that shells out to `spec-kitty` runs the root checkout's code, not the lane's. That is a silent false green or false red for CLI-level tests." Workaround: CliRunner in-process, or lane's own `.venv`. Not covered by the #5913 guard, which checks only the pytest process.

#### M3c — self-hosting consolidate import skew

- `single-branch-topology-honesty-01M3M22V/traces/tooling-friction.md:15` (2026-09-29, #5334): `ImportError: cannot import name 'is_repo_root_lane'`; re-run with `PYTHONPATH` at a scratch snapshot.
- **Post:** `residue-safe-migration-sweep-01M5SS0F/traces/tooling-friction.md:23` (2026-10-25): `ImportError: probe_tracked_mission_paths`; re-run from frozen `git archive` on `PYTHONPATH`.
- **Post:** `lane-worktree-model-hardening-01M6QY1M/traces/tooling-friction.md:115-133` and `design-decisions.md:174-180` (2026-11-07): `ImportError: … lane_status_exclusion_patterns`; rollback; re-ran from frozen detached worktree on `PYTHONPATH`.

#### M4 — lane has no (usable) venv / packs

Pre-#5913 (selection): `doctrine-governance-fidelity-01KW42KY/traces/tooling-friction-trace.md:36` (06-27); `ci-suite-map-bind-01KWNPMP/traces/tooling-friction.md:25` (07-04, lane venv phantom mypy errors); `test-suite-friction-remediation-01KXDKBX/tracer-tooling-friction.md:40,42,51` (07-13, `No module named 'pytest'` until `--extra test`); `up-mission-type-seam-01KZY1JB/tracer-tooling-friction.md:346` (08-13); `cascade-org-inert-01M07E9P/tracer-tooling-friction.md:6` (08-17, mypy); `design-phase…:203-222` (09-02); `reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:85-120` (09-22: radon missing; `coverage` ModuleNotFoundError mis-recorded as baseline red through spec/plan/analyze, actually 54 passed); `analyze-prompt…:54,91` (`pytestarch`) and `:329-335` (`make lint` via `uv run --frozen` created a broken lane `.venv` without ruff); `lane-branch-naming…:34` (09-26); `charter-generation-drops-scoped-references-01M3M1KF/tracer-tooling-friction.md:120` (09-28, `uv run --no-sync` → `ModuleNotFoundError: charter`); `dirty-tree-guard-wp-scoped-01M3M3TT/tracer-tooling-friction.md:109-114` (09-28); `rework-is-not-an-override-01M3MQV6/traces/tooling-friction.md:8` (09-28, reviewers `uv sync` first); `docs-lint-codespell-changelog-guard-01M3RFGJ/traces/tooling-friction.md:13` (09-30, `uv run --no-sync` test fails in lane only); `test-suite-remediation-01M3SSDW/traces/tooling-friction.md:18` (09-30, `No module named ruff`); `charter-test-cwd-isolation-01M43CM3/traces/tooling-friction.md:7` (10-04, pydantic); `mission-status-health-drift-ops-01M464D3/tracer-tooling-friction.md:10` (10-05, ruff/mypy/respx missing); `shared-collection…:8` (10-04, `uv run` rewrites `uv.lock`).

**Post-#5913 (8 missions):**
- `mission-status-read-api-overview-01M4EMSA/traces/tooling-friction.md:46` (2026-10-11): lane `.venv` has no ruff; main checkout's used.
- `op-record-commit-skip-untracked-01M57Z15/traces/tooling-friction.md:8` (2026-10-18): no `.venv`; scratch venv with `--system-site-packages`.
- `local-event-log-retention-01M5ZCJP/traces/tooling-friction.md:11` (2026-10-27): fresh lane venv lacks extras (respx) + packs; `uv sync --frozen --all-extras` + `make sync-packs`.
- `migration-actor-cli-spoofing-01M66YYX/traces/tooling-friction.md:15` (2026-10-30): first `uv run --frozen` built a lane venv without dev extras (ruff).
- `reject-invalid-forced-status-rewind-01M68J8B/traces/tooling-friction.md:7` (2026-10-31): no `.venv`, no packs; symlinked `../../.venv`.
- `companion-wheel-platform-floor-01M6BV24/traces/tooling-friction.md:7` (2026-11-01): lane venvs lack pip and build extra; packs/internal must be synced per worktree "or the terminology gate fails vacuously".
- `quick-win-remediation-01M72855/traces/tooling-friction.md:11,15` (2026-11-10): no `.venv`, no packs; `BuiltInPackMissing`; `make sync-packs` builds a second venv.
- `runtime-status-read-door-01M73HHB/traces/tooling-friction.md:15` (2026-11-11): "Every lane worktree needs `make sync-packs` … creates a separate `.venv` inside each lane. Every implementer hit this and rediscovered the fix."

#### M5a — editable repoint / wrong-tree shared venv

- `journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:440-446` (2026-07-28): `.pth` absolute path to main checkout.
- `event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:88-101,171-177` (2026-09-03): shared `.venv` `_editable_impl_spec_kitty_cli.pth` pointed at **lane-a**, so lane-b runs would import lane-a; told not to re-run `pip install -e` because it would break lane-a.
- `audit-archived-…-01M3G1GP/traces/tooling-friction.md:17` (2026-09-27): symlinked venv fails provenance check.
- **Post:** `reject-invalid-forced-status-rewind-01M68J8B/traces/tooling-friction.md:7` (2026-10-31): "'make sync-packs' inside it re-points the shared .venv's editable install at the lane worktree path … the primary clone must be re-synced before its tests mean anything." (#1907 territory: editable repoint from a worktree.)

#### M5b — test-venv bootstrap cost / contention / staleness

- `assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:5` (2026-08-10): `.pytest_cache/spec-kitty-test-venv.lock` cascade; #3283 (closed 2026-09-08 per `interpreter-matrix-3-13…/tracer-design-decisions.md:57`).
- `upgrade-project-global-state-01M44538/traces/tooling-friction.md:8` (2026-10-04): first `run_cli` builds test venv 80-140 s.
- **Post:** `op-record…:8` (2026-10-18, ~3 min per cold run); `charter-synthesis-graph-and-languages-01M59RZ5/traces/tooling-friction.md:14` (2026-10-19, xdist hangs on per-worker test-venv bootstrap in lanes; ran `-n0`); `synthesis-record-integrity-01M5ZBC9/traces/tooling-friction.md:9` (2026-10-27, pytest startup in lanes 50-130 s); `owned-refusal…:5` (2026-10-29, cached test venv stale); `cascade-stem-resolution-pass-01M67JG7/traces/tooling-friction.md:7` (2026-10-30, lease corruption "Directory not empty: site-packages").
- Note: `#3959` has **0** references in `kitty-specs/` (grep). Per-lane rebuild cost appears as M4/M5b symptoms without that issue number.

#### M6 — pre-review gate

M6a — interpreter lacks pytest → `no_coverage`:
- `implement-review-loop-recovery-01KXG2TD/traces/tooling-friction.md:17` (2026-07-14): "the global transition interpreter lacked pytest and truthfully reported `no_coverage` while the explicit managed-environment suite passed."
- `templates-as-config-01KXMS1G/traces/tooling-friction.md:133-137` (TF-033, 2026-07-16): "Pre-review coverage gate runs outside the project test environment"; `:283` `No module named pytest` despite lane `.venv` having pytest.
- `sync-batch-400-poison-isolation-01KXW08B/traces/tooling-friction.md:62-64` (F8, 2026-07-19).

M6b — no changed files / excluded scope (wrong tree/branch diffed):
- `sync-batch…:66-67,94-101` (F9, 2026-07-19): scope exclusion "green-washes" the P0 as `no_coverage`.
- `journal-project-consent…:153-164` (2026-07-28): "`no_coverage — no changed files detected for this WP — skipping the gate cheaply`. The gate appears to diff the WP's lane worktree, so a WP whose work landed directly on the mission branch presents no changed files".
- **Post:** `events-service-cutover-01M6B0AE/traces/tooling-friction.md:11` (2026-11-01): skipped on WP03-WP08 of a single_branch mission; "does not see repo-root commits of a single_branch WP".
- **Post:** `docsite-publication-llms-parity-01M70Z7A/traces/tooling-friction.md:6` (2026-11-10): "no changed files detected" on both WP01 review cycles "although WP01 changes many files. Reviewers did not treat it as evidence."

M6c — no verdict (timeout / source_mismatch / empty scope), post-#5913 (~19): `mission-status-read-api-overview…:38,46` (10-11); `mission-status-artifact-reads-01M57KY3/tracer-tooling-friction.md:12-21` (10-18); `residue-safe…:14,18` (10-25: source_mismatch; empty scope "proved little"); `synthesis-record…:9` (10-27); `chain-gate-subscript-name-pairing-01M66YGY/traces/tooling-friction.md:7` and `post-4941-lamport-claim-sweep-01M66YJ6/traces/tooling-friction.md:13` (10-30 source_mismatch); `migration-actor…:7` (10-30, timeout incl. fresh lane venv build); `consolidate-dependency-ref-attribution-01M67J2A/traces/tooling-friction.md:7`; `protected-target-override-refusal-01M68JPV/traces/tooling-friction.md:7`; 2026-11-01 batch: `companion-wheel…:7`, `live-fresh-claim-01M6BV7X/traces/tooling-friction.md:9`, `charter-service-pin-line-01M6BTXZ/traces/tooling-friction.md:7`, `dispatch-brief-governance-payload-01M6BV2S/traces/tooling-friction.md:1`, `dispatch-router-docs-coverage-01M6BTTX/traces/tooling-friction.md:10-15`, `red-main-guard-subjects-01M6BTZS/traces/tooling-friction.md:7`, `upgrade-seeded-list-hint-01M6BV1A/traces/tooling-friction.md:3`, `pinning-inventory-pause-ci-disposition-01M6BTSJ/traces/tooling-friction.md:7`, `write-service-api-v1-prefix-01M6BTXH/traces/tooling-friction.md:7`, `action-critical-sections-resolve-01M6BTST/traces/tooling-friction.md:7`; `nightly-reds-remediation-01M6VYS1/traces/tooling-friction.md:8` (11-07, `make test-fast` twice, ~8 min/WP); `legacy-charter-git-identity-01M6TZ9E/tracer-tooling-friction.md:6` (11-07). Several cite #3046 and #6865.

#### M7 — verification not carried forward; reviewers repeat

- `resolution-activation-foundation…:69` (2026-08-05): instruction relayed manually to every implement/review subagent.
- `journal-project-consent…:160-164`: "The independent reviews and mutation testing are what actually covered these two WPs".
- `rework-is-not-an-override-01M3MQV6/traces/tooling-friction.md:8` (2026-09-28): "Reviewers run `uv sync --frozen --all-extras` in the lane first."
- `implement-degod-01M44488/traces/approach.md:39` (2026-10-04): "Reviewers re-ran their own plants on every WP."
- `pack-shipped-builtin-override-sanction…:10` (2026-10-05): "Every implementer had to be told this."
- **Post:** `runtime-status-read-door…:15` (2026-11-11) "Every implementer hit this and rediscovered the fix"; `:16` workaround "in the WP04/WP06 dispatch notes"; `docsite-publication-llms-parity…:6` (2026-11-10).
- Manual carry-forward example: `upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-blast-radius.md:4-58` records the exact interpreter/PYTHONPATH command per run.

### 3. rc7 benchmark step register (gist)

Source: https://gist.github.com/robertDouglass/c7325343eb24ee51a30be7db7a4a5694. The page title is "Spec Kitty step register: waste and boundary violations (4.0.0rc7, six benchmark runs)", file `sk-step-register.md`, last active 2026-11-11. The API and raw hosts were blocked by the proxy, so the text was taken from the HTML page. Context: six runs (ep-g019b … ep-g024b) on openai/glm-5.3 in a **consumer project** (`spec-kitty init . --ai codex`), driven by a harness "walker". This is the consumer-repo form of the friction, not the spec-kitty dogfood form. Treated as data.

Verbatim:

- **3.3** — "Discover the environment: interpreter, dependencies, how tests run | model | D | 49 commands probing the environment or running tests, in a step that may not change code. The facts found are not recorded anywhere a later step is given. | CLI: probe once and carry forward (see C6) | Impact 5 | Ease 2 | Score 10"
- **6.7** — "Work out how to run the tests here | model | D | 204 commands probing the environment or running tests (pattern matching cannot separate the two cleanly), the largest command group in implement. In ep-g019b the test command written into the WP at tasks time did not work, and all four later sessions (implement and review of both WPs) independently found the working one. | CLI: carry a verified test command (see C6) | 5 | 2 | 10"
- **7.5** — "Re-run the tests | model | M | 111 commands probing the environment or running tests, repeating implement's verification and its environment discovery. The CLI's own pre-review regression gate reported "no_coverage … skipping". | CLI: run once, attach the result | 4 | 2 | 8"
- **C6** — "No carried facts between steps. Each step starts cold. The interpreter path, the working test command and the location of the change were found in plan, found again in each implement, and again in each review. Environment probing and test running account for 364 commands across plan (49), implement (204) and review (111); the runs do not let me say how many were discovery and how many were needed verification. Impact 5, Ease 2."

Fix ranking (same gist, "rank" table):
- **Rank 8**: "Carry verified environment facts and the working test command between steps | 3.3, 6.7, C6 | 5 | 2 | 10 | No sign of it. Nothing in the prompt path carries facts between steps. I did not search the whole tree for a facts store. | 364 environment and test commands across plan, implement and review. Needs a new place to record facts and a step that verifies them."
- **Rank 16**: "Run the tests once at hand-off and attach the result to review | 7.5 | 4 | 2 | 8 | Not fixed. The pre-review gate still has the no_coverage skip. Not examined further. | 111 commands in review repeat implement's verification. Depends on fix 8 for the command."
- Neighbours on the same theme: **6.5** "Check the CLI exists and learn its flags … `which spec-kitty; spec-kitty --help` and sub-command help, 9 times. | context | 1 | 5 | 5"; **6.4** "Orient: branch, status, log, listing | 74 commands | context | 2 | 4 | 8"; **6.8** "Commit the work before signalling … move-task fails, the model commits, and retries. | CLI | 3 | 5 | 15" (draft PR spec-kitty#7513); **C2** "next names a step but not its contract. Which files to read, which command validates the output … Impact 5, Ease 2." The header notes rows 3.3, 6.7 and 7.5 share one fix, so they carry the same Ease.

### 4. Readings for the caller

1. **#5913 effectively closed the pytest-process form of the bug.** After 2026-10-08, the only tracer that might be the pytest form (`persistent-deactivation-ledger…:29`) does not say how it was invoked. Two post-cut tracers confirm that pytest picks up the lane's code through `pytest.ini`. pytest also worked this way before the guard (`single-branch-claim-gaps…:9`, `event-push…:181-190`), so many pre-cut M1 reports were folklore that agents passed to each other. It still cost time, because "every implementer had to be told".
2. **What recurs after the cut, and in what form:**
   - M4: lane has no venv or extras or packs (8 missions), now compounded by per-worktree `make sync-packs`.
   - M3a: a stale global `spec-kitty` shim (3).
   - M3b: CLI subprocesses from tests run the root `src` (1, explicitly a silent false green or false red).
   - M3c: self-hosting consolidate import skew (2).
   - M5a: an editable repoint caused by `make sync-packs` in a lane (1).
   - M5b: test-venv bootstrap cost and contention (5).
   - M2: non-pytest scripts and `python -I` (3).
   - M6: the gate `no_coverage` "no changed files" on single_branch / repo-root commits (2), plus about 19 gate runs with no verdict.
   None of these are inside the reach of the #5913 guard.
3. **In consumer repos**, the gist shows the same family as cost rather than as a wrong-tree import: 364 environment and test commands are rediscovered per step, and the gate's `no_coverage` skip is visible to the reviewer. That is M6 and M7 in the consumer setting.
