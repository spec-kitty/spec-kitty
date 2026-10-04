---
work_package_id: WP03
title: Pre-test step in the consuming workflows
dependencies:
- WP02
requirement_refs:
- C-010
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-5559-shared-collection-and-shard-recapture
merge_target_branch: issue-5559-shared-collection-and-shard-recapture
branch_strategy: Planning artifacts for this mission were generated on issue-5559-shared-collection-and-shard-recapture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5559-shared-collection-and-shard-recapture unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-shared-collection-and-shard-recapture-01M42V58
base_commit: a5e0555ae5790d6025df5003dc938e4153a6f0e2
created_at: '2026-10-04T08:44:53.348616+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Collection reuse
history:
- at: '2026-10-04T07:27:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_ci_workflow_prestep_shape.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-router.yml
- .github/workflows/module-tests.yml
- .github/workflows/ci-nightly.yml
- tests/ci/test_ci_workflow_prestep_shape.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Pre-test step in the consuming workflows

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

The two heavy battery legs (`ci-router.yml`, job `architectural-heavy`) and the module shard that runs `tests/ci/test_corpus_blocking_home.py` (`module-tests.yml`) collect the test universe in a step before pytest, restore it on re-runs, and fail when a test silently fell back. A nightly job proves a reused universe equals a fresh one.

Done when `tests/ci/test_ci_workflow_prestep_shape.py` passes, every gate file listed under "Test Strategy" is green, and each job's pytest command line is byte-identical to before. Requirements: FR-008, FR-009, NFR-001, NFR-002, NFR-003, C-010.

## Context & Constraints

- Mission documents: `kitty-specs/shared-collection-and-shard-recapture-01M42V58/spec.md`, `plan.md`, `research.md` (decisions D-01..D-15, brownfield findings B-01..B-09), `data-model.md`, `contracts/`, `quickstart.md`.
- Charter: `.kittify/charter/charter.md`. Load action doctrine with `spec-kitty charter context --action implement`.
- **ATDD-first (binding)**: the failing test is committed before the implementation, as its own commit.
- **No heavy suites**: run only the files named under "Test Strategy". Never run `tests/architectural/` or `tests/ci/` as a whole directory, `make test-fast` or `make test-full`.
- Run tools as `uv run --no-sync <cmd>` (a bare `uv run` rewrites `uv.lock` on this machine; if `uv.lock` shows as modified, `git checkout uv.lock`).
- Formatting: check with `uv run --no-sync ruff format --check --force-exclude <files>`; never format a file on the ruff-format exclude list by explicit path without `--force-exclude`.
- Complexity ceiling is 15 per function. No `# noqa`, no `# type: ignore`, no new allowlist or baseline entry (C-006).
- Use `kernel.clock` for timestamps in `scripts/` (clock-door gate); in tests use `monkeypatch`, never direct `os.environ` / `sys.argv` / cwd mutation (global-state gate).
- Terminology: "Mission" (never "feature"), "primary branch (`main`)", "repository root checkout".
- Tracer notes: the mission's tracer files live on the coordination branch, not in your lane. Put any tooling friction or design choice in your final hand-back under a heading `Tracer notes`; the orchestrator records them.
- Step order per consuming job (`contracts/collection-store.md`): compute key → restore store → `collect` → save store → pytest (unchanged) → `check` with `if: always()`.
- `actions/cache` pin to reuse: `actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0` (`.github/actions/warmup/action.yml:103`). Use `actions/cache/restore` and `actions/cache/save` from the same commit if you split restore and save; every `uses:` must be SHA-pinned with a version comment (DIR-051).
- The cache key is the output of `python -m scripts.ci.collect_universe_prestep key`, prefixed with a fixed string such as `universe-`. It already contains the interpreter, so the two workflows never collide (C-010). No `restore-keys` fallback: only an exact key may restore.
- The store directory is the one `_universe_store.store_dir` returns; print it from the script rather than repeating the path in YAML if the script offers it (add a `store-dir` command in the script only if needed, recorded as an out-of-map edit).
- Set `SK_GATE_REUSE_REPORT: ${{ runner.temp }}/universe-reuse.jsonl` for the pre-step, pytest and check steps.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; work only in the workspace path that `spec-kitty agent action implement WP03 --agent claude` prints.


## Subtasks & Detailed Guidance

### Subtask T011 – Red-first workflow-shape tests

- **Purpose**: pin the shape so a later edit cannot drop the check or reorder the steps. Commit failing first.
- **Steps**: create `tests/ci/test_ci_workflow_prestep_shape.py` (`pytestmark = pytest.mark.fast`), parsing the YAML with the loader the neighbouring workflow tests use (see `tests/ci/test_ci_module_wiring.py`). Assert, for `architectural-heavy` and for the module-test job:
  1. A step runs `python -m scripts.ci.collect_universe_prestep collect` **before** the step containing `-m pytest`.
  2. A step runs `... check` **after** it, with `if: always()` (module shard: combined with the same selection condition).
  3. The pre-step, pytest and check steps all see `SK_GATE_REUSE_REPORT`.
  4. A cache restore step precedes the pre-step, uses the pinned action, keys on the `key` command's output, declares no `restore-keys`, and is guarded on a non-empty key. The cache save step sits between the pre-step and the pytest step and does not depend on pytest's outcome.
  5. The pytest `run` text is unchanged: compare against the command the existing wiring tests already assert, or assert the absence of new flags.
  6. In `module-tests.yml`, the shard list file is not written inside the checkout (no bare `shard_tests.txt` relative path).
  7. `ci-nightly.yml` has a job that runs `... compare`, carries the fork-guard `if:`, and is in `nightly-summary.needs`.
- **Self-mutation**: for assertions 1, 2 and 4, add a test that feeds a mutated copy of the parsed workflow (step removed or moved) into the same checking function and expects failure.

### Subtask T012 – Heavy battery legs

- **Purpose**: FR-008 and FR-009 for the two legs.
- **Steps**:
  1. `ci-router.yml:758-773` runs `uv sync --frozen --all-extras` and pytest in one `run:` block. Split it: a setup step (`uv sync`), then cache restore, pre-step, the pytest step (same command text, same flags, same order), check, cache save.
  2. The memory sampler steps and the junit upload keep their relative order around the pytest step: `tests/ci/test_ci_module_wiring.py:538-556` finds the first step containing `-m pytest` and checks sampler order and `if: always()`.
  3. The pre-step must not contain the substring `-m pytest`; invoke it as `uv run --frozen python -m scripts.ci.collect_universe_prestep collect`.
  4. `tests/architectural/test_no_duplicate_suite_execution.py:240,911` expects one suite invocation per leg; `gc.suite_invocations` does not parse `python -m` steps, so the pre-step is invisible to it. Confirm by running that file.
  5. Save the cache **directly after the pre-step**, before pytest, guarded on the pre-step having succeeded and the restore step not having hit. A job that later fails is exactly the one that gets re-run, so the save must not depend on pytest passing.
  6. `key` exits 2 on a dirty checkout and prints nothing. Capture the key into a step output and guard restore, pre-step save and check-expectation on it being non-empty; an empty cache key must never reach `actions/cache`.
  7. Before the pre-step, run `git status --porcelain` and fail the step with the listed paths if it is non-empty: on a heavy leg the checkout must be clean at that point (`.venv` and `out` are git-ignored), and a dirty checkout would disable reuse for the whole job.
- **Files**: `.github/workflows/ci-router.yml`.

### Subtask T013 – Module shard

- **Purpose**: FR-008 for the `ci` module shard without adding a collection to every other shard (research D-06, finding B-02).
- **Steps**:
  1. `module-tests.yml:195` writes `shard_tests.txt` into the checkout and `:273` reads it. Move the file to `${{ runner.temp }}` (or `"$RUNNER_TEMP"` in shell) in both places. An untracked file in the checkout makes the store report `dirty-checkout`.
  2. After the selection step, add an output or a shell test: the pre-step, restore, check and save steps run only when the selected list contains `tests/ci/test_corpus_blocking_home.py`.
  3. Keep the step names `Run pytest for this shard` and `Upload coverage + xunit artefacts` unchanged (`tests/architectural/test_dual_mode_contract.py:226-240`).
  4. Use the warm-up environment's interpreter for the pre-step, the same one the pytest step uses (`"$venv_python"`), so the key matches what the test computes.
  5. Check that nothing else in the job writes into the checkout before pytest (coverage files, report directories). `out/` and `.pytest_cache/` are git-ignored; anything else must move or the store will be bypassed. Verify with a local dry run of the selection step and `git status --porcelain`.
- **Files**: `.github/workflows/module-tests.yml`.

### Subtask T014 – Nightly equivalence job

- **Purpose**: NFR-005.
- **Steps**:
  1. Add one job to `ci-nightly.yml`: checkout, environment setup as the neighbouring jobs do, `collect`, then `compare`.
  2. It needs the fork-guard `if:` (`tests/ci/test_fork_guard.py:124`), and must be listed in `nightly-summary.needs` (`ci-nightly.yml:1307`).
  3. Let it fail directly (no call to `nightly_escalation.py`); then it needs no row in `_MARKER_LANES` / `_DIRECTORY_LANES` (`tests/ci/test_nightly_exit_code_honesty.py:58-76,268-302`). If the summary job requires every needed job to expose an exit variable, follow the pattern of the smallest existing lane and add the matching pin row.
  4. Give it a `timeout-minutes` with headroom (`tests/ci/test_nightly_timeout_headroom.py:162-174`).
- **Files**: `.github/workflows/ci-nightly.yml`.

### Subtask T015 – Re-run the workflow-shape gates

- **Purpose**: research B-06 lists every gate that reads these workflows. Run each file; where a pin legitimately moved (for example a step index), update the pin in the same commit as the workflow change and say why in the commit message. Do not loosen an assertion.
- **Out-of-map edits**: pins live in files this package does not own. A small, justified edit is allowed; record each in the Activity Log with one line of rationale.

## Test Strategy

```bash
uv run --no-sync pytest tests/ci/test_ci_workflow_prestep_shape.py -q
uv run --no-sync pytest tests/ci/test_ci_module_wiring.py tests/ci/test_xdist_worker_policy.py tests/ci/test_nightly_exit_code_honesty.py tests/ci/test_fork_guard.py tests/ci/test_nightly_timeout_headroom.py tests/ci/test_skip_if_green_wiring.py tests/ci/test_workflow_script_import_guard.py -q
uv run --no-sync pytest tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_module_tests_matrix.py tests/architectural/test_module_shard_registry.py tests/ci/test_nightly_architectural_backstop.py -q
uv run --no-sync pytest tests/release/test_pinning_inventory_fresh.py -q
```

Some of these files are slow (they parse every workflow); run them one group at a time, in the foreground. If any is red before your change, confirm on the planning base and report it as pre-existing rather than fixing it.

## Risks & Mitigations

- The real proof (three per-PR runs, NFR-001..003) is only available once the pull request is open; WP07 records it. This package delivers the shape and its pins.
- A first-run cache save from one leg can race the other leg's save of the same key; a "cache already exists" result is not an error. Do not fail the job on it.
- If `uv run --frozen` in the pre-step re-syncs and changes installed distributions between pre-step and pytest, the keys differ. Both steps must use the same environment invocation.

## Review Guidance

- Diff each job's pytest command against the base: it must be identical.
- Confirm the check step runs on failure too (`if: always()`), and that no `restore-keys` exists.
- Confirm nothing writes into the checkout before pytest in the module shard.
- Verify red→green on the T011 commit.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T07:27:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
