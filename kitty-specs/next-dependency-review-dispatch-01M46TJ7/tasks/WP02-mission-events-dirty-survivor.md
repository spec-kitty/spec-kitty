---
work_package_id: WP02
title: Scoped dirty-gate survivor for mission-events.jsonl
dependencies: []
requirement_refs:
- FR-006
- FR-007
- C-002
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 1 - Dirty gate
history:
- at: '2026-10-05T20:11:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/review/test_mission_events_dirty_survivor_5669.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/dirty_classifier.py
- tests/review/test_dirty_classifier.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Scoped dirty-gate survivor for `mission-events.jsonl`

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (resolver-backed) and follow its discipline before parsing the rest.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

`next` appends `kitty-specs/<slug>/mission-events.jsonl` (its own tracked, write-only
observability log) and leaves it uncommitted. The move-task dirty gate
(`_validate_ready_for_review` → `_validate_research_artifacts` → `classify_dirty_paths` →
`_is_benign`) then refuses `move-task --to approved` (and `for_review`/`done`) on lanes with
"Blocking: N uncommitted file(s)". Fix it with a **scoped** survivor classification.

**Done when**: with only `mission-events.jsonl` dirty, `move-task <wp> --to approved` is not
refused over that file; with an operator-owned dirty file also present, it still blocks; and
the global churn owner is unchanged (SC-004; FR-006, FR-007; C-002).

## Context & Constraints

- Spec: `../spec.md`; grounding: `../research/code-grounding.md`.
- **C-002 / critical boundary**: do NOT add `mission-events.jsonl` to the global owner
  `coordination/coherence.py::is_self_bookkeeping_churn` (or `is_toolchain_generated_churn`).
  That owner feeds ~41 consumers including destructive `consolidate`/`accept`/`merge` gates,
  and `mission-events.jsonl` has LIVE correctness readers (`runtime_bridge_composition.py`
  research-gate primitives) plus an explicit keep-local ruling in `implement_cores.py:318-332`.
  The fix is the per-gate survivor list ONLY.
- **FR-007 anchor**: match exactly `kitty-specs/<slug>/mission-events.jsonl` (any mission
  slug segment) so a user file named `mission-events.jsonl` elsewhere still blocks.
- Mirror the file's **function-local literal** pattern (not a module-level collection) so the
  R-014 exemption-registry scan (`tests/architectural/test_exemption_registry_ratchet.py`)
  does not require a new per-gate registry row — the existing survivors in
  `_is_review_handoff_survivor_path` already do this.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first: the dirty gate refuses over `mission-events.jsonl`
- **Purpose**: Pin the refusal (and the negative control) before the fix.
- **Steps**: In `tests/review/test_mission_events_dirty_survivor_5669.py` add `@pytest.mark.regression` (issue 5669) tests asserting (a) `classify_dirty_paths(["kitty-specs/<slug>/mission-events.jsonl"], wp_id, slug)` classifies it BENIGN (currently blocking → RED); (b) NEGATIVE control: an operator file (e.g. `kitty-specs/<slug>/mission-events.jsonl` imposter like `src/app/mission-events.jsonl`, and a genuinely-owned source path) stays BLOCKING. RED on merge-base for (a).
- **Files**: `tests/review/test_mission_events_dirty_survivor_5669.py` (new).
- **Parallel?**: Yes.

### Subtask T007 – Fix: add the anchored survivor
- **Purpose**: Classify the exact path benign in the scoped gate only.
- **Steps**: In `_is_review_handoff_survivor_path` add a function-local, exact-anchored match for `kitty-specs/<slug>/mission-events.jsonl` (regex `^kitty-specs/[^/]+/mission-events\.jsonl$` after `to_posix`, mirroring the `wp_task_pattern`/`root_tasks_md_pattern` siblings). Turn T006(a) GREEN; keep (b) blocking.
- **Files**: `src/specify_cli/review/dirty_classifier.py`.
- **Parallel?**: No (after T006).

### Subtask T008 – Assert the global owner is unchanged (C-002 guard)
- **Purpose**: Prove the fix did not widen the destructive-gate owner.
- **Steps**: Add an assertion (in the new test file or `tests/review/test_dirty_classifier.py`) that `coordination.coherence.is_self_bookkeeping_churn("kitty-specs/<slug>/mission-events.jsonl")` and `is_toolchain_generated_churn(...)` both return `False` (i.e. the global owner still treats it as real dirt for consolidate/accept/merge).
- **Files**: `tests/review/test_mission_events_dirty_survivor_5669.py` or `tests/review/test_dirty_classifier.py`.
- **Parallel?**: No.

## Test Strategy

- Targeted only. Run `tests/review/test_mission_events_dirty_survivor_5669.py` and `tests/review/test_dirty_classifier.py`.
- Red→green witnessed; negative control + global-owner-unchanged assertions GREEN.
- `mypy`/`ruff` clean on the changed file (no new suppressions).

## Risks & Mitigations

- Over-broad match (the #1 risk this gate already warns about): anchor with `^...$` and `[^/]+` so only a mission-root `mission-events.jsonl` matches; keep the operator-file negative control.
- Accidentally editing the global owner: the C-002 guard test (T008) catches it.

## Review Guidance

- Red→green witnessed; exact-anchored match; negative control + C-002 guard GREEN; global owner untouched; function-local literal (R-014); mypy/ruff clean.

## Activity Log

- 2026-10-05T20:11:52Z – system – Prompt created.
- 2026-10-05 – python-pedro (claude) – Implemented T006/T007/T008. Red-first:
  added `tests/review/test_mission_events_dirty_survivor_5669.py`
  (`@pytest.mark.regression`, issue 5669) — 2 positive survivor assertions RED on
  HEAD (`mission-events.jsonl` classified blocking), 4 controls/guards green
  (look-alike outside `kitty-specs/`, one-level-too-deep, real source edit, and the
  C-002 global-owner guard). Committed red test (8f906b2). Fix: function-local,
  `fullmatch`-anchored `re.compile(r"kitty-specs/[^/]+/mission-events\.jsonl$")`
  survivor added to `dirty_classifier.py::_is_review_handoff_survivor_path`
  (mirrors `wp_task_pattern`/`root_tasks_md_pattern`; module-level collections
  untouched → no R-014 registry row) + docstring bullet 4. All green:
  `tests/review/` 32/32, `test_agent_git_paths.py` 34/34. C-002 boundary held —
  `coordination/coherence.py` NOT edited; `is_self_bookkeeping_churn` /
  `is_toolchain_generated_churn` still return False for the log. ruff + `ruff
  format --check` + mypy clean on both changed files, no new suppressions. Fix
  commit e89420f. Did NOT run `move-task --to for_review` — handing back to the
  orchestrator for the review handoff.
