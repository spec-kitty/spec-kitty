---
work_package_id: WP05
title: Full recapture, provenance check and allowlist removal
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP06
requirement_refs:
- C-004
- C-006
- C-007
- FR-013
- FR-014
- FR-015
- FR-016
- NFR-006
- SC-004
- SC-005
planning_base_branch: issue-5559-shared-collection-and-shard-recapture
merge_target_branch: issue-5559-shared-collection-and-shard-recapture
branch_strategy: Planning artifacts for this mission were generated on issue-5559-shared-collection-and-shard-recapture. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5559-shared-collection-and-shard-recapture unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-shared-collection-and-shard-recapture-01M42V58
base_commit: 18ab90fa443f830a234b643374844dc49284abc5
created_at: '2026-10-04T09:25:36.012741+00:00'
subtasks:
- T023
- T024
- T025
- T026
- T027
phase: Phase 2 - Shard-timing provenance
history:
- at: '2026-10-04T07:27:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_shard_capture_provenance.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/ci-shard-timings.json
- .github/ci-module-registry.yml
- tests/architectural/test_module_length_agreement.py
- tests/architectural/test_shard_capture_provenance.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Full recapture, provenance check and allowlist removal

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

Every registry module carries measured timings and a valid provenance record; the mismatch allowlist, its baseline and its shape tests are gone; strict agreement holds at the capture commit.

Done when this passes:

```bash
SPEC_KITTY_STRICT_SHARD_TIMINGS=1 uv run --no-sync pytest tests/architectural/test_module_length_agreement.py tests/architectural/test_shard_capture_provenance.py tests/architectural/test_module_shard_registry.py -q
```

Requirements: FR-013, FR-014, FR-015, FR-016, NFR-006, C-004, C-006, C-007.

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
- **Order**: T023, T026, T024, T025, T027. **Who does what**: an implementer writes T023 and T026 (both change which tests exist, so they come before the capture). **The orchestrator runs T024, T025 and T027** (measured, serial, long-running; C-005). If you are an implementer, do T023 and T026 and hand back.
- This package runs **after WP06**, so no later package changes test counts after the capture.
- `tests/architectural/test_module_length_agreement.py`: `_MISMATCH_ALLOWLIST` (:118-139, 17 entries), `_BASELINE_ALLOWLIST_COUNT = 17` (:147), strict switch `_STRICT_ENV_VAR` (:157). Tests: live and slow (:311, :337, :361); allowlist-dependent (:383, :422, :432, :440, :489; :311 is passed the allowlist); self-mutation proof (:466 with :479); strict/warn behaviour (:499-513, :532-604); loaders (:397, :403, :615, :632). Re-read the file: line numbers shift.
- Modules to capture: the 17 allowlisted (missions, post_merge, release, status, review, next, lanes, upgrade, cli, kernel, glossary, execution_context, core_misc, unit, specify_cli_runtime, ci, auth) plus every other registry module the count-only pass reports as drifted or lacking valid provenance (expected: charter, agent, consolidation).
- Shard counts are declared in `.github/ci-module-registry.yml` and validated by `tests/architectural/test_module_shard_registry.py:274` (`_lpt_bin_pack` :116, `_MAX_SKEW` :59). There is no derivation tool and none is added (research B-01).
- The valid-capture predicate is `scripts.ci.recapture_shard_timings.is_valid_capture` (WP04). Import it; do not restate the rule.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; work only in the workspace path that `spec-kitty agent action implement WP05 --agent claude` prints.


## Subtasks & Detailed Guidance

### Subtask T023 – Red-first provenance-completeness test

- **Purpose**: FR-015. Commit failing first; it stays red until T024 lands the data.
- **Steps**: create `tests/architectural/test_shard_capture_provenance.py` with `pytestmark = [pytest.mark.architectural]` (add `fast` if the file reads only the two data files, which it should).
  1. `test_every_registry_module_has_valid_capture_provenance`: load the registry module names and `module_capture_provenance`; collect the modules whose record is missing or fails `is_valid_capture`; assert the list is empty, with a message naming each module and the capture command.
  2. Self-mutation, same data: copy the loaded provenance, delete one module's record → the checking function returns that module; replace one record with exit status 2 → returned; zero measured tests → returned. Put the check in one helper function used by both the real test and the mutation tests.
  3. Floor: assert the registry yields at least the number of modules it has today (read it, then pin the count as a literal with a comment), so an empty registry load cannot pass vacuously.
- **Expected red**: 11 or more modules lack provenance before T024.

### Subtask T024 – Measured capture (orchestrator)

- **Purpose**: FR-013.
- **Steps**:
  1. Environment: `uv sync --frozen --all-extras` on the pinned interpreter (3.11). Then `git checkout uv.lock` if it changed. Confirm `git status --porcelain` is clean.
  2. `uv run --no-sync python -m scripts.ci.recapture_shard_timings` (report only) to list drifted modules. Record the list.
  3. Measure first: capture one small module (`kernel`) and one large (`core_misc`) and note the wall time, to forecast the total.
  4. Capture the rest serially with `--write`, one invocation per module or via the recapture script, with a run id such as `mission-01M42V58-recapture`. Capture `ci` **last** (the mission adds tests under `tests/ci`; `tests/architectural` is not a registry module).
  5. A module whose capture is invalid: stop, classify the failure (pre-existing red on the primary branch, or caused by this branch), report it under the charter's pre-existing-failure rule if it is pre-existing, and leave that module's data unchanged.
  6. Commit the data file on its own: `chore(ci): recapture shard timings for <n> modules`, listing per module the old and new counts and the exit status.
- **Notes**: nothing else may run on the machine during captures (durations feed the skew check). Record machine, interpreter and total time for WP07.

### Subtask T025 – Shard counts against the skew check (orchestrator)

- **Steps**: run `uv run --no-sync pytest tests/architectural/test_module_shard_registry.py -q`. **Do not reduce any `shard_count`.** Counts encode more than skew: for example `charter`'s 7 was chosen for the per-shard time cap (`.github/ci-module-registry.yml:173-199`), and the skew check passes trivially at 1. For a module that fails the skew check on the new durations, raise `shard_count` to the nearest higher count that passes, re-run, and record old → new with the measured skew. A module that would need a reduction is reported to the operator, not changed. Run `tests/ci/test_ci_module_wiring.py` and `tests/release/test_pinning_inventory_fresh.py`; regenerate the pinning inventory if it reports staleness.
- **Paired control (FR-016)**: in `tests/architectural/test_shard_capture_provenance.py` add a committed test that feeds a deliberately skewed synthetic duration set for a two-shard module to the same checker `test_module_shard_registry.py` uses (import its helper; do not copy it) and expects a failure. Skip adding it if that file already has an equivalent mutation test; say which one in the hand-back.

### Subtask T026 – Delete the allowlist

- **Purpose**: FR-014 (research D-12).
- **Steps**:
  1. Delete `_MISMATCH_ALLOWLIST`, `_BASELINE_ALLOWLIST_COUNT` and the comment block that documents them.
  2. Delete the tests that only police the allowlist's shape (baseline-is-tight, allowlist-not-above-baseline, entries-are-real-modules, allowlisted-modules-still-mismatch, and any other that has no meaning without an allowlist). For each, state in the commit message why it is deleted, not rewritten.
  3. The agreement tests that took the allowlist as an argument now check every registry module. Keep the self-mutation proof (:466/:479): it must still demonstrate that a wrong committed count is detected.
  4. Keep the strict/warn behaviour and its tests unchanged.
  5. `git grep -n "_MISMATCH_ALLOWLIST\|_BASELINE_ALLOWLIST_COUNT"` outside `kitty-specs/` must return nothing afterwards. Check `tests/architectural/_baselines.yaml` and `tests/architectural/global_state_allowlist/S6.yaml` for rows that refer to the deleted names or tests and remove or adjust them.

### Subtask T027 – Strict agreement at the capture commit (orchestrator)

- **Steps**: run the command under "Objectives" and the three live agreement tests. Record pass counts. If any module disagrees because a later commit on the lane changed its count, recapture that module and repeat.

## Test Strategy

```bash
uv run --no-sync pytest tests/architectural/test_shard_capture_provenance.py -q
SPEC_KITTY_STRICT_SHARD_TIMINGS=1 uv run --no-sync pytest tests/architectural/test_module_length_agreement.py -q
uv run --no-sync pytest tests/architectural/test_module_shard_registry.py tests/ci/test_ci_module_wiring.py tests/ci/test_capture_shard_timings.py -q
uv run --no-sync ruff check tests/architectural/test_module_length_agreement.py tests/architectural/test_shard_capture_provenance.py
uv run --no-sync ruff format --check --force-exclude tests/architectural/test_module_length_agreement.py tests/architectural/test_shard_capture_provenance.py
```

`test_module_length_agreement.py` contains live collection tests marked slow; run the file once at the end, in the foreground.

## Risks & Mitigations

- A rebase onto a newer primary branch after capture moves counts. After any rebase, run the count-only pass and recapture only the modules it lists.
- Workstation durations differ from CI durations. Shard counts depend on relative durations within a module; the first scheduled run on the primary branch corrects the absolute values.
- Deleting shape tests changes what is collected, which is why T026 precedes the capture.

## Review Guidance

- Confirm the data file changed only through the producer (provenance `producer` and `command` fields are present for every recaptured module).
- Confirm no allowlist, baseline constant or replacement excuse mechanism remains, and no new one was added (C-006).
- Confirm the self-mutation proof still fails on a wrong count.
- Confirm strict mode passes at the reviewed commit.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T07:27:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
