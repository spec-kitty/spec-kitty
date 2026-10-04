---
work_package_id: WP01
title: Collection key and store
dependencies: []
requirement_refs:
- C-002
- C-003
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-010
- FR-012
- NFR-004
- SC-003
- SC-007
planning_base_branch: issue-5559-shared-collection-and-shard-recapture
merge_target_branch: issue-5559-shared-collection-and-shard-recapture
branch_strategy: Planning artifacts for this mission were generated on issue-5559-shared-collection-and-shard-recapture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5559-shared-collection-and-shard-recapture unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-shared-collection-and-shard-recapture-01M42V58
base_commit: 21dd7b048b043f361a5b85c19ea2f9fe03c84cd1
created_at: '2026-10-04T07:29:39.390321+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Collection reuse
history:
- at: '2026-10-04T07:27:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/_universe_store.py
- tests/architectural/test_universe_store.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/architectural/_gate_coverage.py
- tests/architectural/_universe_store.py
- tests/architectural/test_universe_store.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Collection key and store

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

`tests/architectural/_gate_coverage.py::collect_universe()` gains a keyed on-disk store. A call reuses a stored universe **only** when it was produced from the same committed tree and the same collecting environment; on any doubt it collects afresh (C-003). Every call reports what it did.

Done when:

- `collect_universe()` keeps its signature and return value; for identical inputs the reused list equals a fresh one element for element.
- The behaviour table in `contracts/collection-store.md` holds row for row, each row pinned by a test.
- `uv run --no-sync pytest tests/architectural/test_universe_store.py -q` passes, and no test in that file performs a real collection.
- Requirements covered: FR-001..FR-007, FR-010 (report line), FR-012, NFR-004, C-002, C-003, SC-003, SC-007.

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
- `collect_universe()` is at `tests/architectural/_gate_coverage.py:1952-2012`; constants `_COLLECT_PLUGIN` (:141) and `_COLLECT_OK_CODES` (:150). `_COLLECT_OK_CODES` is also used by `collect_job_nodeids` (:2064); do not change either constant.
- Callers, all with no arguments: `test_same_tier_uniqueness.py:144`, `test_fast_tier_marker_completeness.py:27`, `tests/ci/test_corpus_blocking_home.py:243`, `_live_uniqueness.py:344`. Nobody monkeypatches `collect_universe`. Do not edit the callers.
- `_gate_coverage.py` is 2,917 lines and on the ruff-format exclude ratchet (`pyproject.toml`, `tests/architectural/test_ruff_format_exclude_ratchet.py`). Keep additions there minimal; put logic in the new module.
- A real collection returns 54,723 records, about 10.7 MB as JSON, in 22–95 s on a workstation (`evidence/two-pass-collection.md`).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; work only in the workspace path that `spec-kitty agent action implement WP01 --agent claude` prints.


## Subtasks & Detailed Guidance

### Subtask T001 – Campsite: split `collect_universe()` into helpers

- **Purpose**: make the fresh-collection path callable on its own so the store can wrap it, without changing behaviour. This is a distinct, behaviour-preserving commit that precedes the functional change.
- **Steps**:
  1. Extract the subprocess run and dump parsing into a private function, for example `_collect_universe_fresh(repo: Path) -> list[TestRecord]`, containing today's body unchanged (environment, command line, exit-code and dump check, `RuntimeError` text, node-id prefix normalisation).
  2. `collect_universe(repo_root=None)` becomes a thin wrapper that resolves `repo` and calls the helper.
  3. Do not reformat the file. Check your hunk only: `git diff --stat` must show `_gate_coverage.py` alone.
- **Files**: `tests/architectural/_gate_coverage.py`.
- **Validation**: `uv run --no-sync pytest tests/architectural/test_ci_collection_completeness.py -q` still passes (it references `gc.collect_universe()` in a fixture string). Commit as `refactor(gates): extract the fresh-collection path of collect_universe`.

### Subtask T002 – Red-first tests

- **Purpose**: pin the contract before the code exists. Commit this file alone, failing, before T003.
- **Steps**: create `tests/architectural/test_universe_store.py` with `pytestmark = [pytest.mark.architectural, pytest.mark.fast]` (confirm both markers are registered in `pytest.ini`; if `fast` is not accepted alongside `architectural` by a marker gate, keep `architectural` only and say so in the trace file). Use `tmp_path` git repositories built with `subprocess.run(["git", ...])` and a **fake collector** injected through a parameter or `monkeypatch.setattr` on the fresh-collection helper; count its calls.
- **Cases to write** (each named after the row it pins):
  1. Key changes when the committed tree changes (commit a file anywhere in the repository, including outside `tests/`).
  2. Key changes with a different interpreter version tuple, platform string, installed-distribution digest, and a new `SPEC_KITTY_*` variable or a changed `PYTEST_ADDOPTS`.
  3. Key does **not** change for `PYTEST_CURRENT_TEST`, `PYTEST_XDIST_WORKER`, `PYTEST_XDIST_WORKER_COUNT`, `SK_GATE_DUMP`, `SK_GATE_REPO`, `HOME`.
  4. Clean checkout: first call `collected`/`no-record`, second call `reused`, collector called once, results equal.
  5. Dirty checkout (modified tracked file; and separately an untracked file): store neither read nor written, outcome `bypassed`/`dirty-checkout`. **Paired control on the same fixture**: after committing the change, the next call reuses or stores.
  6. `repo_root` override: `bypassed`/`root-override`; a record already stored for the real root is not returned and is not replaced. **Paired control**: the same fixture without the override reuses the record.
  7. Invalid records, one case each: unreadable JSON, wrong `schema`, `count` not equal to `len(records)`, empty records, fewer than the sanity floor → `collected`/`invalid-record` and the file is replaced. **Paired control**: a valid record on the same fixture is reused.
  8. Origin mismatch: file named for the right key but `commit` or `tree` differs → `collected`/`origin-mismatch`. **Paired control**: matching origin is reused.
  9. Failed collection (fake collector raises the same `RuntimeError`): the error propagates unchanged and no file is written. **Paired control**: a successful collection writes one.
  10. Writing a record removes other key files in the store directory (FR-012).
  11. Concurrency: two **processes** (`multiprocessing` with the `spawn` context; threads do not exercise a file lock) request with nothing stored, with a fake collector that sleeps briefly and appends to a call-count file; the count file ends with exactly one entry and both processes return equal records. **Paired control**: with the lock call patched to non-blocking the count is two, proving the lock is what serialises them.
  12. Key computation takes under 1 s on the real repository (NFR-004): call the key function against the real `REPO_ROOT`, assert elapsed below 1.0 s.
  13. **Pre-step and test agree on the key** (the case that decides whether reuse can ever happen): inside this real pytest test, compute the environment-family part of the key from `os.environ`, then run `subprocess.run([sys.executable, "-c", ...])` with the environment a CI pre-step has (the test's environment minus every variable the excluded-names constant lists and minus `PYTEST_*`) and compute it there; assert the two are equal. Then assert the stronger form: for every `SPEC_KITTY_*` name present in the test process but absent from `os.environ` as pytest was launched (use the copy conftest keeps, or diff against a fresh subprocess running `pytest --co -q` on one tiny file that prints its environment names), the name is in the exclusion constant. This test must fail if someone adds a new session-set `SPEC_KITTY_*` variable without excluding it.
- **Files**: `tests/architectural/test_universe_store.py` (new).
- **Notes**: the sanity floor is 1,000 records (research D-15). Fake universes for the "valid" cases must therefore have at least 1,000 synthetic records; build them with a small helper.

### Subtask T003 – Implement `_universe_store.py`

- **Purpose**: all key and record logic in one pure, unit-tested module (single authority; the pre-step script in WP02 imports it).
- **Steps**:
  1. `collection_key(repo: Path, *, environ: Mapping[str, str] | None = None) -> str | None` returns `None` when the checkout is dirty or `git` fails. Inputs per `data-model.md`: `git rev-parse HEAD^{tree}`; `sys.version_info[:3]` and `sys.implementation.name`; `sys.platform`; a digest over sorted `name==version` from `importlib.metadata.distributions()`; sorted `NAME=value` for the environment family.
  2. Environment family as **one** constant pair: included prefixes `("SPEC_KITTY_",)` plus the exact name `PYTEST_ADDOPTS`; excluded exact names and prefixes for per-process variables **and for variables the test session itself sets** (research D-02). `tests/conftest.py` `pytest_configure` writes `SPEC_KITTY_REAL_HOME_FOR_TESTS` (:233) and `SPEC_KITTY_ENABLE_SAAS_SYNC` (:252) into every pytest process, and the per-worker home isolation sets more; a plain `python -m` pre-step has none of them. Read `tests/conftest.py` and `tests/_support/` for every `os.environ` write under a `SPEC_KITTY_` name and exclude each by name, with a comment saying where it is set. Keep both constants in this module only.
  3. Dirty test: `git status --porcelain` output non-empty means dirty. Untracked files count (an untracked test file changes collection).
  4. `load_record(store_dir, key, *, commit, tree) -> tuple[list | None, str]` returns the records or `None` with a reason from `data-model.md` (`no-record`, `invalid-record`, `origin-mismatch`).
  5. `write_record(store_dir, key, *, commit, tree, records)` writes to a temporary file in the same directory and `os.replace`s it, then removes every other `*.json` record in the directory.
  6. `store_dir(repo) -> Path` returns one git-ignored location. Use a directory under `.pytest_cache/` (already ignored); confirm with `git check-ignore`. Resolve it in this one helper only.
  7. `SANITY_FLOOR = 1000`, `SCHEMA = 1`.
- **Files**: `tests/architectural/_universe_store.py` (new, target under 250 lines).
- **Notes**: every function takes its inputs as parameters so tests need no global patching. Subprocess calls use argument lists and `check=False` with explicit return-code handling.

### Subtask T004 – Wire the store into `collect_universe()`

- **Purpose**: the production path.
- **Steps**:
  1. Order of decisions, as in the plan's flowchart: `repo_root` override → bypass; unsupported platform (not Linux or macOS, or lock unavailable) → bypass; key is `None` → bypass `dirty-checkout`; otherwise take the lock, try `load_record`, else collect fresh, then `write_record`.
  2. Lock: `kernel.locks.machine_file_lock(lock_path, *, blocking=False, timeout_s=None, reentrant=False)` (`src/kernel/locks.py:748`). The default is **non-blocking**; call it with `blocking=True` and `timeout_s` above the 900 s collection timeout (for example 1200), or every waiting worker falls straight through and collects for itself. Use **one fixed lock file** in the store directory, not one per key: per-key lock files would escape the eviction in FR-012.
  3. A failed fresh collection raises exactly today's `RuntimeError` and leaves the store untouched.
  4. Any unexpected error from the store layer (permission error, lock timeout) falls back to a fresh collection and reports `bypassed` with a reason; it never raises in place of returning a universe. Do not write an effect-free `except`: record the reason in the report line.
- **Files**: `tests/architectural/_gate_coverage.py`.
- **Notes**: keep the wrapper under complexity 15 by delegating to small helpers in `_universe_store.py`.

### Subtask T005 – Reuse report line

- **Purpose**: FR-010; WP02's `check` reads these lines.
- **Steps**:
  1. After every call, when the environment variable `SK_GATE_REUSE_REPORT` names a file, append one JSON line with the fields in `data-model.md` (`outcome`, `reason`, `key`, `caller`, `seconds`). No variable, no file, no output. For `bypassed`/`dirty-checkout`, add `dirty_paths`: the first five paths `git status --porcelain` reported, so a red job says which file made the checkout dirty.
  2. Append with a single `write` of one line opened in append mode so parallel workers do not interleave partial lines.
  3. `caller` is the calling test file when it can be found cheaply (`PYTEST_CURRENT_TEST` when set, else `"direct"`).
  4. `SK_GATE_REUSE_REPORT` must be in the key's exclusion list.
- **Files**: `tests/architectural/_universe_store.py`, `tests/architectural/_gate_coverage.py`, tests in `test_universe_store.py`.

### Subtask T006 – Non-vacuity pins

- **Purpose**: prove the guards can fail (tactic `acceptance-criteria-non-vacuity`).
- **Steps**:
  1. For each refusal case in T002 confirm the paired positive control is in the same test or uses the same fixture function.
  2. Half-by-half: temporarily revert each independent guard (dirty check, origin check, floor check, override bypass) and confirm at least one test goes red each time. Report the four results in your hand-back under `Tracer notes`. Restore the code.
  3. Add one test that calls the real `gc.collect_universe` wrapper (not only the helper module) with the fresh-collection helper patched, proving the production wiring.
  4. **Planted violation on both paths (SC-007)**: build a synthetic universe that violates one consuming gate's rule (for example two records that make the same-tier uniqueness check fail, or a record with no tier marker for the fast-tier completeness check; read `test_same_tier_uniqueness.py` and `test_fast_tier_marker_completeness.py` for the checker functions they call on the universe). Feed it through `gc.collect_universe` twice, once so the result is `collected` and once so it is `reused`, and pass each result to that gate's checker function. The checker must report the violation both times. Use the checker functions the gates already expose; do not copy their logic.

## Test Strategy

```bash
uv run --no-sync pytest tests/architectural/test_universe_store.py -q
uv run --no-sync pytest tests/architectural/test_ci_collection_completeness.py tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_no_manual_global_state_mutation.py -q
uv run --no-sync ruff check tests/architectural/_universe_store.py tests/architectural/test_universe_store.py tests/architectural/_gate_coverage.py
uv run --no-sync ruff format --check --force-exclude tests/architectural/_universe_store.py tests/architectural/test_universe_store.py tests/architectural/_gate_coverage.py
```

Optional single real run (about 2 minutes) on a clean checkout: call `gc.collect_universe()` twice with `SK_GATE_REUSE_REPORT` set and confirm `collected` then `reused`. Do not add this as a test.

## Risks & Mitigations

- A per-process variable inside the key means no two workers ever match. Case 3 pins the exclusions.
- The lock primitive may refuse long waits or behave differently on macOS. Read it before using it; on any lock failure fall back to a fresh collection with a reported reason.
- New tests change the collected count of the architectural tree. That is expected; WP05 recaptures last.

## Review Guidance

- Verify red→green: the T002 commit fails on the planning base and passes on the final commit.
- Check each contract row has a test and each refusal has a same-fixture positive control.
- Confirm `collect_universe()` returns an equal list on the reuse and fresh paths, and that its failure message is unchanged.
- Confirm no second copy of the key logic exists outside `_universe_store.py`.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T07:27:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
