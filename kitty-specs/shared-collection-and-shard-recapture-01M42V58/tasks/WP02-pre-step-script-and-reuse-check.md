---
work_package_id: WP02
title: Pre-step script and reuse check
dependencies:
- WP01
requirement_refs:
- FR-010
- FR-011
- NFR-005
planning_base_branch: issue-5559-shared-collection-and-shard-recapture
merge_target_branch: issue-5559-shared-collection-and-shard-recapture
branch_strategy: Planning artifacts for this mission were generated on issue-5559-shared-collection-and-shard-recapture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5559-shared-collection-and-shard-recapture unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-shared-collection-and-shard-recapture-01M42V58
base_commit: d7cd52fdc6e0766437b9a3656a257b47d91431f7
created_at: '2026-10-04T08:20:23.404418+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 1 - Collection reuse
history:
- at: '2026-10-04T07:27:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/collect_universe_prestep.py
- tests/ci/test_collect_universe_prestep.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/collect_universe_prestep.py
- tests/ci/test_collect_universe_prestep.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Pre-step script and reuse check

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

One command-line entry point, `python -m scripts.ci.collect_universe_prestep <command>`, used by CI steps and by maintainers. It holds no key or store logic of its own; it calls `tests.architectural._universe_store` and `tests.architectural._gate_coverage` (WP01).

Done when the command table in `contracts/collection-store.md` holds and `uv run --no-sync pytest tests/ci/test_collect_universe_prestep.py -q` passes. Requirements: FR-010 (job summary), FR-011, NFR-005 (`compare`).

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
- `scripts/ci` importing `tests.*` has no precedent in this repository, but `python -m` from the repository root resolves `tests.architectural` (it has `__init__.py`). Report this choice in your hand-back under `Tracer notes`. The alternative, copying key logic into the script, is a parallel authority and is not acceptable.
- `scripts/**` is under ruff's security rules (only `TID251` is ignored there): subprocess calls need fixed executables and argument lists.
- `tests/ci` convention: `pytestmark = pytest.mark.fast`.
- Workflows must invoke the script as `python -m scripts.ci.collect_universe_prestep`, never as a bare path (`tests/ci/test_workflow_script_import_guard.py`).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; work only in the workspace path that `spec-kitty agent action implement WP02 --agent claude` prints.


## Subtasks & Detailed Guidance

### Subtask T007 – Red-first tests

- **Purpose**: pin the four commands through the real `main(argv)` entry point. Commit failing, before T008.
- **Cases**:
  1. `key` prints the same key `_universe_store.collection_key` returns and exits 0; exits 2 on a dirty checkout and prints nothing to stdout.
  2. `collect` calls `collect_universe` exactly once (patched) and exits 0; when it raises, the exit status is non-zero and the error text reaches stderr.
  3. `collect` writes a first report line whose `caller` is `prestep`.
  4. `check`: report file with pre-step `collected` then two `reused` → exit 0. With a later `collected` → exit 1. With a later `bypassed`/`dirty-checkout` → exit 1 (research D-14). With a later `bypassed`/`root-override` → exit 0. **Paired control**: the all-`reused` file on the same fixture builder exits 0.
  5. `check` when the pre-step line is absent or itself `bypassed` → exit 0 with a summary note "pre-test step did not store a collection; reuse not expected" (the job is in fallback mode and must not fail for that).
  6. `check` writes a Markdown table to the file named by `GITHUB_STEP_SUMMARY` when set, and to stdout otherwise.
  7. `compare`: stored equals fresh → exit 0; one differing record → exit 1 and the first differences are printed; no stored record → exit 1.
- **Files**: `tests/ci/test_collect_universe_prestep.py` (new). Use `monkeypatch` for environment and for patching the collector; never a real collection.

### Subtask T008 – `key` and `collect`

- **Steps**: `argparse` with subcommands; `main(argv: list[str] | None = None) -> int`; `if __name__ == "__main__": raise SystemExit(main())`. `collect` sets the report `caller` to `prestep` (pass it through a parameter or an environment variable that WP01's report code reads; if WP01 did not expose one, add a keyword-only parameter there and record the out-of-map edit with a one-line rationale).
- **Files**: `scripts/ci/collect_universe_prestep.py` (new).

### Subtask T009 – `check`

- **Steps**:
  1. Read the report file line by line; ignore blank lines; a malformed line is itself a failure (exit 1, named in the summary), because a corrupt report must not pass silently.
  2. The first line with `caller == "prestep"` decides the mode. `reused` or `collected` → reuse expected for every later repository-root request. Otherwise fallback mode.
  3. Summary table columns: caller, outcome, reason, seconds. One line under the table states the verdict in plain words.
  4. Keep the decision in a pure function `verdict(lines) -> tuple[int, str]` and test it directly as well as through `main`.
- **Edge cases**: no report file at all → exit 0 in fallback mode with a note; empty file → same.

### Subtask T010 – `compare`

- **Steps**: obtain the stored record through `_universe_store.load_record` for the current key; obtain a fresh universe by calling the fresh-collection helper directly (store bypassed); compare as sorted `(nodeid, relpath, tuple(markers))`; print counts and up to 20 differing node ids; exit 1 on any difference or when nothing is stored.
- **Notes**: this is what the nightly job runs (WP03). It performs one real collection, so it has no test that runs it for real; its logic is tested with a patched collector.

## Test Strategy

```bash
uv run --no-sync pytest tests/ci/test_collect_universe_prestep.py tests/ci/test_workflow_script_import_guard.py -q
uv run --no-sync ruff check scripts/ci/collect_universe_prestep.py tests/ci/test_collect_universe_prestep.py
uv run --no-sync ruff format --check --force-exclude scripts/ci/collect_universe_prestep.py tests/ci/test_collect_universe_prestep.py
uv run --no-sync python -m scripts.ci.collect_universe_prestep key
```

## Risks & Mitigations

- A `check` that passes when the report is missing could hide a broken report path. Case 5 keeps that exit 0 only in fallback mode; WP03's shape test pins that the report variable is set for the pytest step.
- Importing `tests.architectural._gate_coverage` is slow-ish (large module). Import inside the command functions, not at module import, so `--help` stays fast.

## Review Guidance

- Confirm the script contains no key, dirty-check or record-validation logic of its own.
- Confirm exit codes match the contract table exactly.
- Verify red→green on the T007 commit.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T07:27:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
