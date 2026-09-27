---
work_package_id: WP03
title: Golden characterisation of the six merge drivers (#5119)
dependencies: []
requirement_refs:
- NFR-001
planning_base_branch: issue-5119-merge-seam-test-isolation
merge_target_branch: issue-5119-merge-seam-test-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5119-merge-seam-test-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5119-merge-seam-test-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-seam-test-isolation-campsite-01M3F61E
base_commit: b13598b529bc62490ce65dc7cb53e609ce914944
created_at: '2026-09-26T16:56:52.295559+00:00'
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 1 - Foundations
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/merge/
create_intent:
- tests/merge/test_merge_driver_goldens.py
- tests/merge/merge_driver_goldens/__init__.py
- tests/merge/merge_driver_goldens/_capture.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/merge/merge_driver_goldens/**
- tests/merge/test_merge_driver_goldens.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Golden characterisation of the six merge drivers (#5119)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (read `packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also read `.kittify/charter/charter.md` (standing order 4: characterise before you change; live evidence over "looks fixed").

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

Issue **#5119**. WP04 will move the file-level bodies of all six registered merge drivers out of `src/specify_cli/cli/commands/merge_driver.py` into `src/specify_cli/merge/drivers.py`. This WP pins today's behavior **before** that move so WP04 can prove byte-identity (NFR-001, SC-006).

Done when, on today's (pre-move) code:

1. Golden cases exist for **all six** registered drivers: `merge-driver-event-log`, `merge-driver-meta`, `merge-driver-traces`, `merge-driver-issue-matrix`, `merge-driver-acceptance-matrix`, `merge-driver-review-cycle` — ≥3 behavior cases each **plus** 1 path-injection case each.
2. Each case stores the three inputs, the expected written `ours` bytes, and `case.json` with exit code, stdout, stderr (temp dir normalized to `<TMP>`), and absent-file flags.
3. `tests/merge/test_merge_driver_goldens.py` passes with two legs:
   - **subprocess leg** — runs the registered command exactly as git would (`python -m specify_cli merge-driver-X O A B`) and compares bytes + exit code + stdout + stderr;
   - **in-process leg** — resolves the driver through the replay seam `specify_cli.merge.git_probes._resolve_registered_driver_callable(config_key)` and compares the written bytes on success / "raised" on failure. This leg must work **both before and after** WP04's move (write it against the seam, not against `cli.commands.merge_driver`).
4. An **all-six-resolve** test proves every `_MERGE_DRIVERS` config key resolves in replay (today only traces is exercised, by `tests/merge/test_bookkeeping_projection_seam.py:202-318`).
5. Re-running the capture helper on the unchanged code reproduces the committed goldens exactly (deterministic).

Requirement refs: **NFR-001**, SC-006, NFR-006.

- **No manual global-state mutation in new/changed tests** (the census gate is not in this lane until consolidation): no hand writes to `os.environ` / cwd / `sys.path` / `sys.modules` / `sys.argv` — use `monkeypatch.*` / `contextlib.chdir` / `mock.patch.*`. Verify zero sites for your changed test files: `.venv/bin/python kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/research/global_state_scan_prototype.py | grep -E '<your test files>'` (expect no output) — record it in the Activity Log.

## Context & Constraints

- Research: `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/research.md` **R2** (per-driver table) and **R5** (harness design). Contract: `contracts/merge-driver-body.md`.
- Registry: `src/specify_cli/lanes/merge.py:59-122` `_MERGE_DRIVERS` — 7 specs, 6 distinct commands (event-log has two patterns, `status.events.jsonl` and `decisions.events.jsonl`, under one `config_key="spec-kitty-event-log"`). Config keys: `spec-kitty-event-log`, `spec-kitty-meta`, `spec-kitty-traces`, `spec-kitty-acceptance-matrix`, `spec-kitty-issue-matrix`, `spec-kitty-review-cycle`.
- Replay seam today: `git_probes.py:657-679` `_resolve_registered_driver_callable(config_key)` returns a callable taking `(base, ours, theirs)` path strings. Today it returns the Typer function (return `None`, raises `typer.Exit` on failure); after WP04 it returns the body (returns `MergeDriverOutcome`, raises `MergeDriverError`). Your in-process leg must therefore: call `driver(str(O), str(A), str(B))`, ignore the return value, treat **any** exception as "raised", and on success compare `A`'s bytes.
- The review-cycle driver prints a stdout notice on collision; after WP04 **only the subprocess entrypoint** prints it (replay does not). So: assert stdout only in the subprocess leg; the in-process leg compares bytes only.
- Existing coverage to mine for realistic inputs (read, don't edit): `tests/merge/test_merge_driver_wrappers_2709.py` (event-log, meta, traces), `tests/merge/test_traces_driver_section_union_4894.py`, `tests/merge/test_gate_artifact_merge_drivers_2804.py` + `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py` (issue/acceptance matrix incl. verdict-divergence exit 1 and path injection), `tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py` (fast path + collision stdout, pinned at ~L475), `tests/merge/test_merge_driver_meta_diagnosability.py` (malformed meta). These files are owned by WP04 — do NOT edit them.
- This WP adds tests only; it must be green on today's code. Do not touch `src/`.
- Placement in `tests/merge` is deliberate: the per-PR merge CI shard (`.github/ci-module-registry.yml` ~L13-32) runs `tests/merge`, not `tests/specify_cli/cli`, which gives WP04 diff-cover on the moved lines.

## Branch Strategy

- **Strategy**: lane-based execution from `lanes.json`.
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- Prepare the workspace ONLY via `.venv/bin/spec-kitty agent action implement WP03 --agent claude`; work inside the printed lane worktree.

## Subtasks & Detailed Guidance

### Subtask T010 – Golden case fixtures for all six drivers

- **Purpose**: Realistic, minimal inputs that exercise each driver's distinct branches.
- **Layout**:

  ```
  tests/merge/merge_driver_goldens/
  ├── __init__.py
  ├── _capture.py                      # T011
  └── <command>/<case>/                # e.g. merge-driver-meta/field-union/
      ├── O  A  B                      # base / ours / theirs inputs (omit a file + flag it absent when the case needs it)
      ├── expected_A                   # bytes of `ours` after the driver ran (subprocess leg)
      └── case.json                    # {"exit_code": 0, "stdout": "...", "stderr": "...", "absent": ["O"], "argv": ["O", "A", "sub/B"], "note": "why this case exists"}
                                       # "argv" (optional) overrides the O/A/B argument paths relative to the case temp root
  ```

- **Minimum cases** (≥3 + 1 path-injection per driver; derive inputs from the existing tests listed above):
  - `event-log`: disjoint appends union; overlapping identical events dedup; malformed JSONL line → exit 1 with the `EventLogMergeError` message.
  - `meta`: independent field edits both kept; identical sides; malformed JSON on one side → exit 1 (`JSONDecodeError` text); base absent.
  - `traces`: disjoint section union; stale theirs trace block dropped (`_drop_stale_theirs_trace_blocks`); identical sides.
  - `issue-matrix`: disjoint row union (`indent=2, sort_keys=True` + `"\n"`); verdict divergence on one row → exit 1 (`RowMatrixMergeError`); unparsable doc → exit 1 (`AcceptanceMatrixParseError`).
  - `acceptance-matrix`: filled-side wins; divergence → exit 1; **key-order case proving no `sort_keys`** (the acceptance/issue asymmetry must be pinned).
  - `review-cycle`: identical sides fast path (exit 0, no stdout); collision → conflict markers joined with `"\n"` written to `ours` + stdout notice, exit 0.
  - path injection (each driver): the real invariant (`cli/commands/merge_driver.py:109-133` `_resolve_merge_driver_paths`) is that the **three resolved paths must share one parent directory** — it is *not* "outside the working directory / `..`". Build the case with sibling subdirectories under the normalized temp root and an `argv` override, e.g. `"argv": ["O", "A", "sub/B"]` (with `sub/B` present) → exit 1 with the `MergeDriverPathError` message. Never point outside the temp root (a platform-dependent path would leak into stderr).
- **No uncaught-exception cases**: never capture a case whose expected outcome is an uncaught exception (e.g. traces' `UnicodeDecodeError`) — its stderr is a traceback whose file paths/line numbers change with WP04's move, which would force editing the goldens. Those paths are pinned by WP04's focused unit tests instead.
- **Notes**: keep inputs tiny (a few lines each). Use realistic mission bookkeeping content (real field names from the existing tests), never lorem ipsum. Store text with explicit trailing-newline intent.

### Subtask T011 – Capture helper

- **Purpose**: Produce `expected_A` + `case.json` deterministically from today's code; re-runnable to prove determinism.
- **Steps**:
  1. `tests/merge/merge_driver_goldens/_capture.py` with a `capture_case(case_dir: Path) -> CaseResult` and a `main()` that walks every case dir and (re)writes `expected_A`/`case.json`. Guard with `if __name__ == "__main__":` — it must never run on import (pytest collects `tests/merge/**`; the module name starts with `_` and has no `test_` functions).
  2. For each case: copy `O`/`A`/`B` into a fresh temp dir; run `[sys.executable, "-m", "specify_cli", "<command>", O, A, B]` with `cwd=<tempdir>` and an **explicit minimal `env`** — never a copy of `os.environ` (ambient variables would make goldens machine-dependent): `{"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "<repo>/src", "HOME": "<fresh temp home>", "SPEC_KITTY_HOME": "<temp home>/.spec-kitty", "SPEC_KITTY_NO_UPGRADE_CHECK": "1", "LC_ALL": "C.UTF-8"}` (startup writes agent directories into HOME — never touch the real one; reading `PATH` is not a mutation); `capture_output=True`, `text=False`, `check=False`, a timeout.
  3. Normalize the temp dir path (and its `realpath`) in stdout/stderr to `<TMP>`; store decoded UTF-8.
  4. Build env/paths with `pathlib` and pass `env=` explicitly — do NOT mutate `os.environ`/cwd (this mission's own census gate would flag it).
  5. Run it once on today's code to produce the committed goldens; run it a second time and confirm `git status` shows no change (determinism) — record in the Activity Log.
- **Notes**: Use `python -m specify_cli`, never the `spec-kitty` on PATH (stale-install hazard). Confirm `src/specify_cli/__main__.py` dispatches hidden `merge-driver-*` commands.

### Subtask T012 – `tests/merge/test_merge_driver_goldens.py` (two legs)

- **Purpose**: The regression net WP04 must keep green, unchanged.
- **Steps**:
  1. Discover cases by walking `merge_driver_goldens/<command>/<case>/`; parametrize with ids `"<command>/<case>"`. Assert the discovered set is non-empty and covers all six commands (a vacuity guard: `assert {c.command for c in cases} == SIX_COMMANDS`).
  2. **Subprocess leg** (`@pytest.mark.integration`; it spawns a process): reuse `_capture.capture_case` logic (import the function, don't duplicate), then assert `A` bytes == `expected_A`, and exit code/stdout/stderr == `case.json`.
  3. **In-process leg** (`@pytest.mark.unit` if it only touches `tmp_path`): map command → config key via `_MERGE_DRIVERS` (`spec.command` contains the command name); `driver = _resolve_registered_driver_callable(config_key)`; copy inputs into `tmp_path`; `try: driver(str(O), str(A), str(B))` → on success assert `A.read_bytes() == expected_A`; on `Exception` assert `case.json["exit_code"] != 0`; if the case expects exit 0, an exception is a failure. Never inspect stdout here.
  4. The in-process leg must not import `specify_cli.cli.commands.merge_driver` (it must survive WP04 unchanged).
- **Notes**: Keep helpers small (complexity ≤15). Type-annotate; mypy-clean.

### Subtask T013 – All-six-resolve replay test

- **Purpose**: Today only traces is exercised through replay; WP04's resolver rewrite must resolve every registered kind.
- **Steps**:
  1. Parametrize over the **distinct** `config_key`s in `specify_cli.lanes.merge._MERGE_DRIVERS` (6), assert `callable(_resolve_registered_driver_callable(key))`.
  2. Assert an unknown config key raises `GitProbeError` (fail-closed branch).
  3. Assert the distinct set size is 6 and equals the six commands derived from `spec.command` via `git_probes._DRIVER_COMMAND_PATTERN` (so adding a 7th driver without goldens trips this test — include a clear message: "add goldens for the new driver").
- **Files**: `tests/merge/test_merge_driver_goldens.py`.
- **Parallel?**: Yes, independent of T010–T012 once the file exists.

- **Tracer**: **Tracer append**: add dated 1–3 sentence entries, as they occur, to the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` (`kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/`); do not commit them from the lane — the orchestrator commits them in the lifecycle trail.

## Test Strategy

```bash
.venv/bin/python tests/merge/merge_driver_goldens/_capture.py && git status --porcelain tests/merge/merge_driver_goldens   # expect empty on 2nd run
.venv/bin/python -m pytest tests/merge/test_merge_driver_goldens.py -q
.venv/bin/python -m pytest tests/merge -q -n auto --dist loadfile
make test-fast
uv run --frozen ruff check tests/merge/test_merge_driver_goldens.py tests/merge/merge_driver_goldens
uv run --frozen ruff format --check tests/merge/test_merge_driver_goldens.py tests/merge/merge_driver_goldens
.venv/bin/python -m mypy tests/merge/test_merge_driver_goldens.py tests/merge/merge_driver_goldens/_capture.py
```

Also run the new file once under `-p no:randomly` and once with xdist to prove order independence. Record counts in the Activity Log.

## Risks & Mitigations

- **Non-determinism** (timestamps, dict order, temp paths in messages) → `<TMP>` normalization; if a driver embeds a timestamp, pin the case to inputs that avoid it and document.
- **Real HOME pollution** → explicit temp `HOME` in the subprocess env.
- **Goldens encoding today's bugs** → that is intended (characterisation); note any surprising behavior in the Activity Log instead of "fixing" it.
- **Leg coupling to the CLI module** → in-process leg goes only through the replay seam.
- **CI shard slowness** → ~24–30 subprocess cases; if the leg exceeds ~20 s, keep cases minimal rather than dropping drivers.

## Review Guidance

- Six commands covered, ≥3 behavior + 1 injection case each; the acceptance-matrix no-sort_keys asymmetry and the review-cycle notice are pinned.
- Capture helper is deterministic (second run produces no diff) and never touches real HOME/cwd/env.
- In-process leg imports nothing from `specify_cli.cli`.
- ruff, ruff format, **mypy** clean; markers honest (`integration` for subprocess, `unit` for tmp-only).
- No `src/` change.
- **Tracer append** evidence: dated 1–3 sentence entries in the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` for anything non-obvious (the orchestrator commits them in the lifecycle trail).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END**
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T16:40:00Z – system – Prompt created.
- 2026-09-26T17:33:30Z – claude – Implemented WP03 in lane `merge-seam-test-isolation-campsite-01M3F61E-lane-c`. 25 golden cases across all six drivers (event-log ×4, meta ×5, traces ×4, issue-matrix ×4, acceptance-matrix ×4, review-cycle ×4), `tests/merge/merge_driver_goldens/_capture.py`, and `tests/merge/test_merge_driver_goldens.py` (subprocess leg + in-process leg via `git_probes._resolve_registered_driver_callable`, never `cli.commands.merge_driver` + T013 all-six-resolve/unknown-key/count guards). Perf finding: a fresh subprocess `HOME` pays a one-time ~13.3s cold-install bootstrap (seeds all 12 agent command/skill dirs); reusing the SAME `HOME` across cases drops each subsequent case to ~1.16s warm. Fixed by threading an optional `home_dir` through `capture_case`, sharing one `tempfile.TemporaryDirectory` across `_capture.main()`'s loop, and adding a session-scoped `_shared_capture_home` fixture (`tmp_path_factory.mktemp`, no `os.environ` mutation) to the subprocess leg — whole-file runtime dropped from ~359s to ~42s serial / ~46s under `-n auto --dist loadfile` (single file stays on one xdist worker under `loadfile`, so no parallel win expected or observed). `pytest-randomly` is not installed in this venv (`ModuleNotFoundError`), so the requested `-p no:randomly` order-independence leg could not be executed — recorded as an environment gap, not skipped silently. Determinism: `_capture.py` re-run 3× total (1 pre-commit, 2 post-commit) — `git status --porcelain tests/merge/merge_driver_goldens` empty every time. Global-state scan (`global_state_scan_prototype.py`) on both new `.py` files: zero hits. `tests/merge -q -x --ignore=tests/merge/test_merge_driver_goldens.py`: 775 passed, 1 failed (`test_profile_charter_e2e.py::test_local_support_declarations_end_to_end`) — confirmed pre-existing/environmental, not caused by this diff: it fails identically in isolation with `"Refusing charter write from linked git worktree ... use a repository-root checkout"`, i.e. it refuses to run from inside this lane's worktree at all, and passes cleanly on `$MAIN`'s repo-root checkout of the same branch. No collision with the new golden test file. 59/59 golden tests green on every run (serial and xdist). Committed as `test(merge): pin golden characterisation of the six merge drivers (#5119)`.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP03 --to <status>` to change WP status.
