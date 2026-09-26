---
work_package_id: WP05
title: Behind-HEAD recovery remedy (FR-011)
dependencies: []
requirement_refs:
- FR-011
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-merge-integrity-01M380R6
base_commit: 123a1fce075fc7f8f68756896e7dfdc55b5be3e9
created_at: '2026-09-23T22:19:55.656438+00:00'
subtasks:
- T021
- T022
- T023
- T024
phase: Phase 2 - Parallel fan (file-isolated)
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/preflight.py
create_intent:
- tests/merge/test_behind_head_remedy.py
execution_mode: code_change
owned_files:
- src/specify_cli/merge/preflight.py
- tests/merge/test_behind_head_remedy.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Behind-HEAD recovery remedy (FR-011)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (frontmatter) before parsing the rest of
this prompt, and behave according to its guidance.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Apply the resolved boundaries and TDD discipline. State what you applied, then continue.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use fenced code-block language identifiers.

---

## Objectives & Success Criteria

After an interrupted terminus, a checkout can be merely **behind its own HEAD** (the update-ref and
`reset --hard` are two unlinked steps). Success (FR-011; traces #4982 #4997):

- The resume/preflight classifier **distinguishes** a checkout behind its own HEAD from real local
  changes.
- It **never** advises a "Commit" remedy that would stage the lane's own already-merged files (which
  reverts the integrated merge).

## Context & Constraints

- Spec: [../spec.md](../spec.md) US5 scenario 2, FR-011. Research: DEBRIEF §2 R1, §4 (#4982/#4997) —
  "update-ref and `reset --hard` are two unlinked steps → checkout-behind-HEAD → resume 'Commit'
  remedy reverts the merge."
- **Grounded anchors** (verify in-tree; names are the durable anchors):
  - `merge/preflight.py` — the git-state / dirty-tree / remedy classifier consumed by the merge
    executor + `--dry-run` forecast.
  - `merge/git_probes.py:31-54` — ancestry-only integration check (`merge-base --is-ancestor`).
    **Read-only here** — this WP does NOT edit `git_probes.py` (WP06 owns it); consume its ancestry
    helper to detect "behind own HEAD" (target is an ancestor of the checkout's own recorded HEAD).
- Locality (C-004): only `merge/preflight.py` + the new test. Do NOT touch the executor.

## Branch Strategy

- **Strategy**: file-isolated parallel-fan — start immediately.
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T021 – Red: behind-own-HEAD distinguished from real local changes
- **Purpose**: reproduce #4982/#4997 (TDD red).
- **Steps**: create `tests/merge/test_behind_head_remedy.py`.
  1. Construct the behind-own-HEAD checkout deterministically in a temp repo: land a lane onto the
     target (`git update-ref`), then leave the working checkout at the pre-merge state so the merged
     files read as staged deletions / "behind" (the interrupted state where `update-ref` advanced but
     the `reset --hard` step never ran — DEBRIEF §2 R1). Capture the checkout's own recorded HEAD.
  2. Drive the preflight/resume remedy classifier over that state and assert:
     - it classifies the state as **behind-own-HEAD**, NOT as real local changes;
     - it does NOT emit a "Commit" remedy for the lane's already-merged files (RED on base: today it
       advises committing them, which reverts the merge).
  3. **Contrast case (no regression)**: a genuinely dirty working tree (an actual uncommitted edit to
     a tracked file unrelated to the merge) IS classified as real local changes and still warns.
  4. **Edge**: an `index.lock` present (a `reset --hard` blocked mid-transaction, per spec Edge Cases)
     must not be misread as clean — assert the classifier surfaces the blocked state, not a silent pass.
- **Files**: `tests/merge/test_behind_head_remedy.py`.
- **Notes**: keep the repo construction O(1) commits; do not mock `_run_git` — build a real repo so
  the ancestry probe runs for real (mirrors WP01's no-mock discipline).

### T022 – Fix: behind-HEAD classifier
- **Purpose**: separate the two states using the ancestry probe.
- **Steps**: in `preflight.py`, add a behind-HEAD sentinel: when the checkout's differences vs the
  target are explained by the target being **ahead of / an ancestor relationship with** the
  checkout's own recorded HEAD (via `git_probes`' ancestry-only check), classify as behind-own-HEAD
  rather than dirty. Keep O(1) ancestry probes (NFR-003).
- **Files**: `src/specify_cli/merge/preflight.py`.
- **Notes**: extract a small helper to keep the classifier `<=15` complexity (ruff C901 / Sonar
  S3776).

### T023 – Fix: never advise the merge-reverting "Commit"
- **Purpose**: the remedy must not stage the lane's own already-integrated files.
- **Steps**: when the state is behind-own-HEAD, the recovery guidance advises the safe remedy
  (e.g. re-run resume / fast-forward the checkout), never "Commit these changes". Ensure the message
  names the situation accurately (C-005 terminology — name the sense of the state).
- **Files**: `src/specify_cli/merge/preflight.py`.
- **Notes**: hoist repeated remedy strings to module constants if used `>=3` times (Sonar S1192).

### T024 – Verify red→green + gates
- **Steps**: confirm RED→GREEN; run `PWHEADLESS=1 .venv/bin/python -m pytest tests/merge/ -q` (own
  subsystem) and paste output. `ruff check` + `ruff format --check` + `mypy
  src/specify_cli/merge/preflight.py` clean.

## Test Strategy

- `tests/merge/` is the owning subsystem — run it in full plus the new remedy test:
  `PWHEADLESS=1 .venv/bin/python -m pytest tests/merge/ -q`.
- Also run the `tests/terminus/` behind-HEAD repros (`test_repro_4982.py` / `test_repro_4997.py`,
  authored by WP01) — they must flip RED→GREEN once this WP lands:
  `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus -k "4982 or 4997" -q`.
- Compiler gate: `mypy src/specify_cli/merge/preflight.py` in addition to the runner.

## Risks & Mitigations

- **Over-classifying** real dirty changes as behind-HEAD would suppress a legitimate warning — the
  contrast case (T021) guards it.
- **False-clean on `index.lock`** — the T021 edge case forbids a silent pass when `reset --hard` was
  blocked mid-transaction.
- **Editing `git_probes.py`** here would collide with WP06 (which owns it) — consume it read-only.
- **Complexity creep** in the classifier — extract a `_is_behind_own_head(...)` helper to keep the
  function `<=15` (ruff C901 / Sonar S3776).

## Definition of Done

- `test_behind_head_remedy.py` RED on the mission base, GREEN on the fix; WP01's #4982/#4997 repros
  flip GREEN.
- The behind-own-HEAD state is classified via the ancestry probe, never as real local changes.
- No remedy advises committing the lane's already-integrated files.
- The contrast (real dirty) and `index.lock` edge cases behave correctly.
- `ruff check` + `ruff format --check` + `mypy` clean; no new `# type: ignore`.

## Review Guidance

- Confirm behind-own-HEAD ≠ dirty via ancestry probe (not a heuristic on file names).
- Confirm no "Commit" remedy is advised for already-merged lane files.
- Confirm the contrast (real dirty) case still warns and `index.lock` is surfaced.
- Confirm `git_probes.py` was consumed read-only (no edit).

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP05 --to <lane>`.
