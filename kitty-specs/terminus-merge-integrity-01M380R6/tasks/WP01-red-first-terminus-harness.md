---
work_package_id: WP01
title: Red-first terminus test harness (Tier-0 property + 12 per-child repros)
dependencies: []
requirement_refs:
- FR-014
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-merge-integrity-01M380R6
base_commit: 5c8a52b8f25db873ce3096f897d263da2e0aafe0
created_at: '2026-09-23T21:59:09.558217+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Red-first reproduction
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: debugger-debbie
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/conftest.py
- tests/terminus/test_terminus_reconciliation_property.py
- tests/terminus/test_repro_4945.py
- tests/terminus/test_repro_4969.py
- tests/terminus/test_repro_4970.py
- tests/terminus/test_repro_4973.py
- tests/terminus/test_repro_4977.py
- tests/terminus/test_repro_4978.py
- tests/terminus/test_repro_4981.py
- tests/terminus/test_repro_4982.py
- tests/terminus/test_repro_4985.py
- tests/terminus/test_repro_4991.py
- tests/terminus/test_repro_4996.py
- tests/terminus/test_repro_4997.py
execution_mode: code_change
owned_files:
- tests/terminus/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first terminus test harness

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before
parsing the rest of this prompt, and behave according to its guidance.

- **Profile**: `debugger-debbie`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Apply the resolved initialization, boundaries, directives, and tactics. State which you applied,
then continue. If the profile cannot be resolved, run `spec-kitty agent profile list` and select the
closest match for a red-first structural-reproduction task.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in fenced code blocks:
` ```python `, ` ```bash `.

---

## Objectives & Success Criteria

This WP lands the **red-first evidence** for the whole mission (FR-014, NFR-001, DIRECTIVE_041/034).
It creates the `tests/terminus/` tree and nothing else — it owns no `src/` surface, so it can (and
must) land while the fixes are still absent. Success:

- A **Tier-0 property test** asserting the epic invariant across terminus commands is RED against
  pre-fix behavior and (later, after WP06+companions land) GREEN.
- **12 per-child reproductions** (one file per in-scope child) are RED on the mission base, each
  driving its **real CLI entry point** — `_run_git`/`subprocess` is NOT mocked, so the tests
  exercise `git/ref_advance.py`'s CAS argv for real (contract §"Property test").
- The excluded-commit assertion is **non-vacuous even when the canceled set is empty** — a canceled
  commit is planted and the test proves the check fires.
- Approved commit SHAs in every assertion come from **lane-branch git tips**, never status rows /
  derived envelopes (forbids the vacuous `_assert_merged_wps_done_on_target` pattern; RN-Q3).

**These tests land RED.** Do not weaken an assertion to make it pass — that is the exact failure
this harness exists to prevent. A red result here is the deliverable.

## Context & Constraints

- Spec: [../spec.md](../spec.md) — US1–US5, FR-014, NFR-001/002/005, C-003.
- Contract: [../contracts/terminus-reconciliation.md](../contracts/terminus-reconciliation.md) — the
  pre/post-conditions the property test asserts, the 6 terminus entry points, and the "no `_run_git`
  mocking" rule.
- Grounding: [../../../work/epic-5001-research/DEBRIEF.md](../../../work/epic-5001-research/DEBRIEF.md)
  §4 (per-child → seam map) and §7 (repro strategy) — the per-child mechanisms + entry points.
- Charter: `.kittify/charter/charter.md` (ATDD-first, red-first discipline). Land these as a commit
  BEFORE any fix commit; the reviewer verifies red-on-base.
- **Terminus entry points** (drive the real ones): `merge`, `merge --resume`, `merge --abort`,
  `upgrade`, `agent issue-verdict`, `doctor coordination --fix`.
- Existing sibling fixtures to reuse (import, do NOT edit): the coord-mission builders under
  `tests/coordination/` and `tests/merge/` (e.g. the `_build_coord_mission_*` helpers) and the git
  scaffolding helpers under `tests/git/`. Grep before writing your own.

## Branch Strategy

- **Strategy**: file-isolated parallel-fan head — start immediately.
- **Planning base branch**: `fix/terminus-merge-integrity`
- **Merge target branch**: `fix/terminus-merge-integrity`

## Subtasks & Detailed Guidance

### T001 – `tests/terminus/conftest.py`: real-CLI-entry harness + helpers
- **Purpose**: give every repro + the property test a shared, mock-free scaffold that builds a coord
  mission, runs a real terminus command, and reads approved SHAs from lane-branch git tips.
- **Steps**:
  1. Create `tests/terminus/__init__.py` (empty) and `tests/terminus/conftest.py`.
  2. Add a `build_coord_mission(tmp_path, wps=...)` fixture that materializes a real git repo with a
     coordination branch (`kitty/mission-<slug>`), a `meta.json` with `topology: coord`, `lanes.json`,
     and per-WP lane branches. Prefer wrapping an existing `tests/coordination`/`tests/merge` coord
     builder over hand-rolling; only add what those lack.
  3. Add `approved_shas_from_lane_tips(repo, wp_ids) -> dict[str, list[str]]` that resolves each
     approved WP's commit SHAs from `git rev-parse <lane-branch>` / the lane tip — **never** from
     `status.events.jsonl` rows. This is the claim the assertions compare against.
  4. Add `plant_canceled_commit(repo, wp_id) -> str` that creates a canceled/removed WP's commit
     reachable only through a dependent lane's history (mirrors the #4977/#4945 mechanism) and
     returns its SHA + patch-id, so the excluded-check has a real target to fire on.
  5. Add `run_terminus(cmd: list[str], repo) -> CompletedProcess`: invoke the **real** CLI
     (`spec-kitty merge …` etc.) via the installed entry point / `subprocess`, capturing exit code
     and stderr. Do NOT patch `_run_git` or any `subprocess` seam — the whole point is to exercise
     `git/ref_advance.py`'s real `update-ref` argv (contract §"Property test").
- **Files**: `tests/terminus/conftest.py`, `tests/terminus/__init__.py`.
- **Parallel?**: Yes — foundation for T002–T005.
- **Notes**: keep fixtures O(#WPs), not O(repo history) (NFR-003). If a needed builder already
  exists in a sibling test module, import it rather than duplicate.

### T002 – Tier-0 property test
- **Purpose**: encode the epic invariant as one reusable post-condition (contract §"Property test").
- **Steps**: create `tests/terminus/test_terminus_reconciliation_property.py`. For each terminus
  command that exits 0, assert: (a) every approved WP's approved commits (from
  `approved_shas_from_lane_tips`) are reachable from the resolved target ref; (b) no excluded
  (canceled/removed) commit is reachable — match by **patch-id equivalence**, not SHA alone, so
  cherry-picked/re-lettered copies are caught. On a divergent construction, assert the command
  exits **non-zero**, tears down nothing, and names the divergence.
- **Files**: `tests/terminus/test_terminus_reconciliation_property.py`.
- **Notes**: this file must be RED for #4945/#4969/#4977/#4981/#4982/#4991/#4996/#4997 on base and
  GREEN after WP06 + companions. Scope the success message check to **"approved-WP commit
  reachability"** only — do NOT assert verdict-integrity (#4990 is out of scope; FR-013).

### T003 – Per-child red repros: reconciliation/CAS family (#4945 #4977 #4981 #4991 #4996)
- **Purpose**: pin each defect's exit-0-over-divergence at its documented entry point.
- **Steps**: one file per child. Drive the real entry point and assert honest-failure is currently
  absent (RED on base):
  - `test_repro_4945.py` — re-lettered lane ships a removed WP's code; assert the removed WP's
    commit is NOT reachable from target (fails today: it lands + exit 0).
  - `test_repro_4977.py` — a canceled WP's code lands via a dependent lane's history; assert the
    gate refuses (fails today).
  - `test_repro_4981.py` — a coord-ref commit appended after the bookkeeping checkpoint; assert it
    is reachable from target after merge (fails today: dies in teardown).
  - `test_repro_4991.py` — `merge --target develop` then crash + `--resume`; assert it lands on
    `develop` (fails today: lands on meta's main).
  - `test_repro_4996.py` — non-CAS rewind: a target/coord ref changed since read; assert the advance
    fails closed (fails today). Second half: `--abort` one of two concurrent merges; assert the
    other's lock is untouched.
- **Files**: the five `test_repro_49xx.py` above.
- **Notes**: reference DEBRIEF §4 for the exact mechanism per child.

### T004 – Per-child red repros: surface/resume/behind-HEAD family (#4969 #4970 #4973 #4978 #4982 #4985 #4997)
- **Purpose**: cover the write-surface, target-authority, residue, and behind-HEAD defects.
- **Steps**: one file per child, real entry point:
  - `test_repro_4970.py` — `agent issue-verdict` from an unmaterialized coord worktree; assert it
    refuses instead of overwriting the committed coord surface (fails today: degrades to primary).
  - `test_repro_4969.py` — an approved lane exists only as `origin/<lane>`; assert `implement`'s
    base resolution consults the origin ref (fails today: cuts fresh from local main).
  - `test_repro_4973.py` — a heal/repair over the append-only status log; assert it reverts only
    recorded SHAs and never a third party's later event (fails today: range revert).
  - `test_repro_4978.py` — lanes/single_branch mission with dirty planning artifacts; assert dirty
    preflight does not `reset --hard` them as coord residue (fails today: topology-blind).
  - `test_repro_4982.py` / `test_repro_4997.py` — checkout behind its own HEAD after an interrupted
    merge; assert resume does NOT advise a "Commit" that reverts the already-merged lane (fails today).
  - `test_repro_4985.py` — explicit `--target` lost to stale meta across a crash; assert `--target`
    wins (fails today).
- **Files**: the seven `test_repro_49xx.py` above.
- **Notes**: #4982 and #4997 are primary-site siblings; keep both files but they may share a helper.

### T005 – Confirm RED on base + non-vacuous excluded-check
- **Purpose**: prove the harness is real, not vacuous (RN-Q3, NFR-005).
- **Steps**:
  1. Run the full `tests/terminus/` suite on the **mission base** and capture the RED output; paste
     the actual terminal output into the WP/PR *Tests run* section (do not hand-type counts).
  2. Add an explicit assertion (in the property test or a dedicated case) that
     `plant_canceled_commit`'s planted patch-id **is detected** by the excluded-check even when the
     canceled WP set is otherwise empty — proving no silent no-op.
  3. Confirm no test patches `_run_git`/`subprocess` (grep your own new files).
- **Files**: all `tests/terminus/**`.
- **Notes**: this is the DoD gate for red-first evidence.

## Test Strategy

- Runner: `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/ -q` (RED on base).
- Property-only: `... -k "terminus_reconciliation and property"`.
- Per-child: `... tests/terminus -k "repro and (4945 or 4969 or ... or 4997)"`.
- These files are Python sources: run `uv run --frozen ruff check tests/terminus/` and
  `uv run --frozen mypy tests/terminus/` clean (no new `# type: ignore`).

## Risks & Mitigations

- **Vacuous repro** (mocks `_run_git`): forbidden — drive the real CLI; grep confirms no mocking.
- **Excluded-check no-op** when canceled set empty: mitigated by the planted-canceled-commit assertion.
- **Approved SHAs from status rows**: forbidden — read from lane-branch tips only.

## Review Guidance

- Confirm every repro drives a real terminus entry point (no subprocess/`_run_git` patching).
- Confirm approved SHAs derive from lane-branch git tips, not status rows.
- Confirm the planted-canceled-commit assertion fires (non-vacuous excluded-check).
- Confirm the suite is RED on the mission base with pasted terminal output.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).
> Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`. Append to the END. Use current UTC time
> (`date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use
`spec-kitty agent tasks move-task WP01 --to <lane>` to change WP status.
