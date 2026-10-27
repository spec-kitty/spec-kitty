---
work_package_id: WP02
title: Retention limits and engine (#6610)
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-013
- NFR-001
- C-001
- C-002
- SC-002
- SC-003
planning_base_branch: issue-6610-local-event-log-retention
merge_target_branch: issue-6610-local-event-log-retention
branch_strategy: Planning artifacts for this mission were generated on issue-6610-local-event-log-retention. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6610-local-event-log-retention unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-local-event-log-retention-01M5ZCJP
base_commit: d1abfb0a7a5aaf4b1b8485f03a03b6176dee9541
created_at: '2026-10-27T20:10:40.647586+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Engine
history:
- at: '2026-10-27T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/state/retention.py
create_intent:
- src/specify_cli/core/ledger_retention.py
- src/specify_cli/state/retention.py
- tests/core/test_ledger_retention.py
- tests/core/test_event_log_retention.py
- tests/runtime/test_run_lock_try.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/ledger_retention.py
- src/specify_cli/state/retention.py
- src/runtime/next/run_lock.py
- src/kernel/event_log_append.py
- tests/core/test_ledger_retention.py
- tests/core/test_event_log_retention.py
- tests/runtime/test_run_lock_try.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Retention limits and engine (#6610)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address every item; record with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

A pure, testable engine that (1) reads `ledger.retention` limits, (2) scans ONLY the surfaces the registry policy marks `ledger_retention` or `rebuildable` (from WP01), (3) gives every item a verdict with a reason, and (4) on apply deletes candidates under the right locks, keeping the run index consistent. No CLI here (WP03).

Done when the ADR 2026-10-13-2 Confirmation holds on a fixture: "run against a fixture with open and closed Missions, deletes only eligible local runs and logs, removes their `feature-runs.json` entries, keeps every log of a Mission with an unfinished step, and never changes a tracked file."

## Context & Constraints

- Spec FR-005, FR-007..FR-011, FR-013, NFR-001, C-001, C-002. Data model: `data-model.md` (RetentionLimits, RetentionItem, reasons). Contract: `contracts/doctor-event-logs.md` (JSON shape the CLI will emit — design the engine's result dataclasses to serialize to it). Research §1, §7 (decisions: mtime age, lock order, kernel-primitive lock probe, lazy memoized completion).
- **C-001: never call `event_log_lock`, `append_event_log_lines` or `append_event`** (frozen in `tests/architectural/test_event_log_writes_gate.py::EXPECTED_DOOR_CALLERS`). Probe/hold locks with `kernel.locks.machine_file_lock(path, blocking=False)`; it raises `kernel.locks.LockNotAcquired` when contended.
- **Never delete a lock file on its own** (kernel/locks.py guarantee G3). A run directory is removed whole only while its run-cursor lock is held.
- Import direction: `specify_cli` → `runtime`, `kernel` is allowed; `runtime`/`kernel` must not import `specify_cli`.
- Test placement: `tests/core/` (per-PR `core_misc`) and `tests/runtime/` (per-PR `execution_context`). Not `tests/specify_cli/` root (nightly only).
- Use `kernel` clock helpers if the codebase has a `Clock` seam (`status/lifecycle.py` uses `DEFAULT_CLOCK`); inject `now` for tests rather than freezing time globally.

## Branch Strategy

- **Planning base branch**: `issue-6610-local-event-log-retention`
- **Merge target branch**: `issue-6610-local-event-log-retention`

Implement with `spec-kitty agent action implement WP02 --agent claude --mission local-event-log-retention-01M5ZCJP`.

## Subtasks & Detailed Guidance

### Subtask T005 – Tidy-first accessors (behaviour-preserving, own commit)

- `src/kernel/event_log_append.py`: add `"event_log_lock_path"` to `__all__` (the function exists at ~`:153`). Its new caller in `src/` (T009) satisfies `tests/architectural/test_no_dead_symbols.py`.
- `src/runtime/next/run_lock.py`: add
  ```python
  def try_run_cursor_lock(run_dir: Path) -> SyncMachineFileLock:
      """Non-blocking run-cursor lock: raises LockNotAcquired at once when another holder has it."""
      return machine_file_lock(_run_cursor_lock_path(run_dir), blocking=False)
  ```
  and add it to `__all__`. Docstring: used by retention cleanup to delete a run only while no advance is in flight.
- Test `tests/runtime/test_run_lock_try.py`: acquiring `try_run_cursor_lock` succeeds on a free run dir; while `run_cursor_lock` is held (in-process holder via a thread, or a second `machine_file_lock` on the same path — note fcntl locks conflict across distinct open file descriptions even in one process, per `run_lock.py`'s docstring), `try_run_cursor_lock(...).__enter__()` raises `LockNotAcquired`.
- Commit: `refactor(runtime): expose a non-blocking run-cursor lock and the event-log lock path`.
- Run `tests/architectural/test_lock_primitive_ban.py` and `tests/architectural/test_no_dead_symbols.py`.

### Subtask T006 – Red-first ATDD tests (own commit)

`tests/core/test_ledger_retention.py`:
- defaults when `.kittify/config.yaml` is absent / has no `ledger` / no `retention` → `(20, 30)`, `source == "default"`.
- explicit values read → `source == ".kittify/config.yaml"`.
- invalid → `RetentionConfigError`: negative, string, float, `true`/`false` (bool is an int subclass — reject explicitly), unknown key under `retention`, `retention` not a mapping, unparseable YAML.

`tests/core/test_event_log_retention.py` — build a fixture project in `tmp_path` (initialise git with `git init` so `event_log_lock_path` resolves a common dir; look for an existing helper in `tests/_factories` or `tests/conftest.py` that creates a minimal Spec Kitty project before writing one):
- Missions under `kitty-specs/<slug>/meta.json` with `mission_id`: one **completed** (`merged_at` set in meta), one **open** (no `merged_at`, no status events → derives active).
- Runs under `.kittify/runtime/runs/<hex>/` each with `state.json` (`{"mission_slug": ..., "mission_id": ...}` plus whatever the snapshot reader needs — the engine should read only those two keys tolerantly), `run.events.jsonl`, `mission_template_frozen.yaml`; ages set with `os.utime`.
- `.kittify/runtime/feature-runs.json` entries pointing at some runs (use `run_index.save_index`).
- Glossary logs `.kittify/events/glossary/<sanitized mission_id>.events.jsonl` for both Missions, an unknown mission id, and `_cli.events.jsonl`.
- `.kittify/derived/<slug>/lifecycle.json`, `kitty-ops/ops-index.jsonl`, and a tracked-looking `kitty-specs/<slug>/status.events.jsonl` + `kitty-ops/<op>.jsonl` (must never be touched).

Scenarios (one test each; `now` injected):
1. 25 completed-Mission runs all 40 days old → newest 20 kept `within keep_runs`, 5 candidates `past retention; Mission completed`.
2. 25 runs, 5 oldest only 10 days old → kept `younger than max_age_days` (BOTH limits needed).
3. Old run of the open Mission outside keep_runs → kept `Mission is open`.
4. Run whose Mission slug/id resolves nowhere → kept `Mission not found`.
5. Glossary log of the completed Mission past both limits → candidate; of the open Mission → kept; unknown id → `Mission not found`; `_cli.events.jsonl` → never listed at all.
6. Derived views + ops-index → candidates `rebuildable cache` regardless of age.
7. Preview (`plan` only) changes nothing: hash the whole tree before/after.
8. Apply: candidates gone; their `feature-runs.json` entries gone; other entries intact; tracked files byte-identical; no `*.lock` deleted except as part of a removed run directory.
9. Lock held on a candidate run (`run_cursor_lock` held during apply) → reported kept `lock held`, directory intact, index entry intact.
10. Lock held on ops-index's event-log lock path → kept `lock held`.
11. A deletion that raises `OSError` (monkeypatch the delete helper) → recorded in `failed` with the error text; the rest proceed.
12. FR-013: monkeypatch the registry selector so `glossary_fallback_events` is `MANUAL` → its logs are no longer scanned. And a surface marked `LEDGER_RETENTION` with no collector raises a clear error (registry/engine drift guard).
Commit: `test(retention): pin local event-log retention behaviour (#6610)`.

### Subtask T007 – `src/specify_cli/core/ledger_retention.py`

```python
@dataclass(frozen=True)
class RetentionLimits:
    keep_runs: int = 20
    max_age_days: int = 30
    source: str = "default"

class RetentionConfigError(ValueError): ...

def load_retention_limits(repo_root: Path) -> RetentionLimits: ...
```
- Read `repo_root / ".kittify" / "config.yaml"` with ruamel `YAML(typ="safe")` like `core/ledger_posture.py::_read_repo_ledger_key`, but **fail closed** (raise) on invalid values — a destructive command must not guess (`consolidation/config.py` precedent).
- Constants `DEFAULT_KEEP_RUNS = 20`, `DEFAULT_MAX_AGE_DAYS = 30`. Error messages name the key, the bad value and the fix.
- `__all__`.

### Subtask T008 – Scan (`src/specify_cli/state/retention.py`)

Shape (adjust names freely, keep functions ≤ complexity 15):
- `@dataclass(frozen=True) class RetentionItem: surface, kind, path (Path), mission (str|None), age_days (float), verdict ("candidate"|"kept"), reason (str)`; `to_dict(repo_root)` → repo-relative POSIX path.
- `@dataclass class RetentionPlan: limits, items` with `candidates` / `kept` properties.
- Collectors keyed by surface name, each yielding raw items for one *unit*:
  - run family (`runtime_run_snapshot`/`runtime_run_event_log`/`runtime_frozen_template`): one unit per directory under `run_index.runs_root(repo_root)`; the unit is selected when ALL three surfaces are `LEDGER_RETENTION` (assert consistency, raise on a partial selection).
  - `glossary_fallback_events`: `.kittify/events/glossary/*.events.jsonl` excluding names starting with `_`.
  - `derived_mission_views`: each `.kittify/derived/<slug>/` directory.
  - `op_invocation_index`: `kitty-ops/ops-index.jsonl` if present.
- Selection: iterate `get_surfaces_by_retention(LEDGER_RETENTION)` and `(REBUILDABLE)` from WP01; look up the collector; missing collector → `RuntimeError` naming the surface (FR-013 drift guard).
- Age: `max(st_mtime)` over the unit's files (directory: `os.scandir` walk; file: its own `st_mtime`); `age_days = (now - mtime)/86400`.
- Verdict for `ledger_retention` units, in this order (first match wins; report one reason):
  1. rank within its kind by age (newest first) `< keep_runs` → `within keep_runs`
  2. `age_days <= max_age_days` → `younger than max_age_days`
  3. Mission unresolved → `Mission not found`
  4. `not is_mission_completed(feature_dir)` → `Mission is open`
  5. lock probe fails → `lock held`
  6. else candidate `past retention; Mission completed`
- Rebuildable units: lock probe fails → `lock held`; else candidate `rebuildable cache`.
- Mission resolution: build once `{slug → feature_dir}` and `{sanitized mission_id → feature_dir}` from `kitty-specs/*/meta.json` (use the glossary's `_sanitize_mission_id` rule — prefer importing a public helper; if only private, replicate the one-line regex with a comment naming the source and add a test pinning equality on a sample id). Run: read `state.json` tolerantly (`json` errors → unresolved). Memoize `is_mission_completed` per feature_dir.
- Lock probes (non-mutating in preview): run → `try_run_cursor_lock(run_dir)` enter/exit; glossary log and ops-index → `machine_file_lock(event_log_lock_path(path), blocking=False)` enter/exit. Note: entering a machine lock writes a holder record into the lock file — that is lock bookkeeping, not a tracked change; but do NOT create lock files for logs that never had one if avoidable: if the lock file path does not exist, nobody holds it → treat as free without acquiring.
- Keep the module free of Rich/typer.

### Subtask T009 – Apply

`apply_plan(repo_root, plan) -> RetentionResult(deleted, failed, removed_index_entries, kept_at_apply)`:
- Run unit: `with try_run_cursor_lock(run_dir):` (on `LockNotAcquired` → kept `lock held`) → `with run_index.index_lock(repo_root):` read index, drop entries whose `resolve_run_dir(entry["run_dir"])` equals this run dir (skip entries raising `RunDirOutsideRepoError`), `save_index` only if changed → `shutil.rmtree(run_dir)`. Comment the lock order (run → index; one-way, cannot deadlock because no path holds the index lock while waiting on a run lock — `run_lock.py` C-002).
- Glossary log / ops-index: `with machine_file_lock(event_log_lock_path(path), blocking=False):` → `path.unlink()`. Leave the lock file and any `<log>.lock` / `.torn` sidecar (research §7).
- Derived dir: `shutil.rmtree`.
- Per-unit `try/except OSError` → `failed` (path + `str(exc)`); never abort the loop. No bare/empty except.
- Re-verify the item is still a candidate is NOT required beyond the lock re-check (preview/apply run in one invocation).
- Assert, before deleting, that the path is inside the repo root and not git-tracked? Cheap guard: refuse any path not under `.kittify/runtime/runs/`, `.kittify/events/`, `.kittify/derived/` or equal to `kitty-ops/ops-index.jsonl` (C-002 defence in depth). Add a unit test for the guard.

### Subtask T010 – Preview performance

- Test generating 1,000 run directories (completed Mission, mixed ages) and asserting `scan` < 2 s. Mark it with the repo's `timing` marker (check `pytest.ini` markers; timing tests run in their own serial pass) so it never runs co-scheduled.

## Test Strategy

```bash
uv run --frozen pytest tests/core/test_ledger_retention.py tests/core/test_event_log_retention.py tests/runtime/test_run_lock_try.py -q
uv run --frozen pytest tests/core/test_state_cleanup_policy.py tests/runtime -q -m "not timing"
uv run --frozen pytest tests/architectural/test_event_log_writes_gate.py tests/architectural/test_lock_primitive_ban.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_run_index_single_reader.py -q
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy src/specify_cli/core/ledger_retention.py src/specify_cli/state/retention.py src/runtime/next/run_lock.py src/kernel/event_log_append.py
```
Note `tests/architectural/test_run_index_single_reader.py`: it may restrict who reads `feature-runs.json`. If it flags the engine, use the sanctioned reader API it names (do not add an allowlist entry without surfacing it to the operator).

## Risks & Mitigations

- Run-index single-reader gate (above).
- Windows: `rmtree` with an open handle fails → `failed`, exit 1 at CLI level.
- A coordination-topology Mission whose status log is not on this checkout derives as open → kept (fail-safe).

## Review Guidance

- Two RED commits (T006) before implementation; T005 is behaviour-preserving.
- No call to any event-log door (grep the diff for `event_log_lock(`, `append_event_log_lines`, `append_event(`).
- Every kept reason in `data-model.md` is produced by some test.
- Complexity ≤ 15 per function (`ruff --select C901`).

## Progress & Status

`spec-kitty agent tasks add-history WP02 --note "..."`; `spec-kitty agent tasks mark-status T005 --status done`.
