---
work_package_id: WP01
title: One raising planning write-branch reader
dependencies: []
requirement_refs:
- FR-005
- NFR-002
- C-004
- FR-008
- C-006
- NFR-003
planning_base_branch: fix/7860-planning-evidence-window
merge_target_branch: fix/7860-planning-evidence-window
branch_strategy: Planning artifacts for this mission were generated on fix/7860-planning-evidence-window. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7860-planning-evidence-window unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundation
history:
- at: '2026-11-25T21:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- tests/mission_runtime/test_planning_write_ref.py
- tests/coordination/test_planning_lane_target.py
execution_mode: code_change
owned_files:
- src/mission_runtime/resolution.py
- src/specify_cli/coordination/planning_commit.py
- tests/mission_runtime/test_planning_write_ref.py
- tests/coordination/test_planning_lane_target.py
- docs/adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One raising planning write-branch reader

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action doctrine: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission planning-lane-write-branch-01M8A725`).
- Address every feedback item before your work is complete, and record each with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Give the codebase **one** answer to two questions:

1. Which branch does this Mission's planning lane write to?
2. Which checkout holds that branch?

Both answers must **refuse** rather than guess when they cannot be computed.

Done when:
- `planning_write_ref(repo_root, mission_slug, target_branch) -> str` exists in `src/mission_runtime/resolution.py` and:
  - returns `meta.mission_branch` for a default Mission (`topology_source: default`) that has not landed;
  - returns today's write ref for every other Mission (`resolve_single_branch_write_ref` semantics: the minted `mission_branch` for a stored `single_branch` Mission, else the target);
  - **raises** on an unreadable or malformed PRIMARY `meta.json` (NFR-002).
- A planning-lane write target (branch + checkout) helper exists next to `primary_partition_checkout` in `src/specify_cli/coordination/planning_commit.py`:
  - it returns the checkout that holds the Mission branch (the coordination worktree) when the write ref is the Mission branch;
  - it returns the repository root checkout otherwise;
  - it raises a named error when the write ref is the Mission branch but no checkout holds it.
- Placement (`resolution.py` around :2075–2079, `_default_mission_facts`) behaves exactly as before. Its non-raising wrapper stays for placement.
- ADR 2026-11-06-3 carries a **Proposed** amendment for #7860.
- Unit tests cover every branch; ruff, format and mypy are clean; complexity is ≤ 15.

Requirements: FR-005, NFR-002, C-004, FR-008 (ADR 2026-11-06-3 part).

## Context & Constraints

- Spec: `kitty-specs/planning-lane-write-branch-01M8A725/spec.md`. Plan: `plan.md` IC-01. Data model: `data-model.md` (PlanningWriteRef, PlanningWorkspace). Research: `research.md` R-02.
- Charter: single canonical authority (C-004). Add **no** third resolver: compose `default_mission_primary_ref` (resolution.py:1087), `resolve_single_branch_write_ref` and `mission_runtime.landing.mission_has_landed`.
- Layering: `mission_runtime` sits below `specify_cli`. `_default_mission_facts` already lazily imports `specify_cli.core.paths`; keep any new import lazy and inside the function, and add no new top-level outbound import (see `tests/architectural/test_layer_rules.py`, `mission_runtime` outbound ledger: shrink-only).
- Do **not** add the new name to `src/mission_runtime/__init__.py` unless the module already re-exports its siblings there. Callers can import from `mission_runtime.resolution`. If you must touch `__init__.py`, follow the `__all__` convention (charter C-007).
- **C-001**: do not edit `src/specify_cli/review/wp_range.py`, `src/specify_cli/status/lane_head.py` or `src/specify_cli/status/wp_window_selector.py`. The review range keeps its own read (it passes `landed=False`); record that drift in the ADR amendment.
- Concurrent Mission #5604 confirmed it does not touch `resolution.py` or `planning_commit.py`.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `fix/7860-planning-evidence-window`
- **Merge target branch**: `fix/7860-planning-evidence-window`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement WP01 --agent claude --mission planning-lane-write-branch-01M8A725` prints; never construct a `.worktrees/` path yourself.

## Subtasks & Detailed Guidance

### Subtask T001 – Red unit tests for the raising planning write-branch reader

- **Purpose**: pin the rule before writing it (red-first, Standing Order #4).
- **Files**: `tests/mission_runtime/test_planning_write_ref.py` (new).
- **Steps**:
  1. Build a minimal Mission directory fixture in `tmp_path`, as other `tests/mission_runtime/` tests do (find one with `grep -rl "_default_mission_facts\|default_mission_primary_ref" tests/`). The fixture needs a PRIMARY `kitty-specs/<slug>/meta.json` in a real `git init` repo, so the placement seam resolves.
  2. Cases (parametrize where natural):
     - default, not landed, `mission_branch: kitty/mission-x` → returns `kitty/mission-x`;
     - default, landed (record the landing the way `mission_has_landed` reads it: inspect `src/mission_runtime/landing.py`) → returns the target;
     - explicit topology (`topology_source` absent or `"explicit"`) → returns what `resolve_single_branch_write_ref` returns (the target for `lanes_with_coord`; the minted `mission_branch` for a stored `single_branch` with `mission_branch`);
     - default, not landed, `mission_branch` missing or empty → target (today's `default_mission_primary_ref` fallback);
     - malformed `meta.json` (invalid JSON) → raises (assert the exception type you introduce, or `MissionMetaReadError`);
     - missing `meta.json` → decide and document. Recommended: raise, because a planning lane with no PRIMARY meta is not a state this reader may guess about. If an existing caller requires the old fallback, keep it only in the non-raising wrapper.
  3. Add a test that the non-raising placement path (`_default_mission_facts`) is unchanged for a malformed meta (still returns `(None, None, False)`). This is the regression guard.
- **Validation**: the tests fail (import error or assertion) before T002.

### Subtask T002 – `planning_write_ref` in `mission_runtime/resolution.py` (raising)

- **Purpose**: the single branch authority for the planning lane (FR-005).
- **Steps**:
  1. Add a raising facts reader beside `_default_mission_facts` (resolution.py:1104). It returns `(topology_source, mission_branch, landed)` and lets `MissionMetaReadError` (or a new, named `PlanningWriteRefUnavailable`) propagate. Better still, make `_default_mission_facts` a thin non-raising wrapper over it, so there is one parser.
  2. Add `planning_write_ref(repo_root: Path, mission_slug: str, target_branch: str, *, resolver: MissionResolver | None = None) -> str`:
     ```python
     topology_source, mission_branch, landed = _default_mission_facts_strict(get_main_repo_root(repo_root), mission_slug, resolver=resolver)
     fallback = resolve_single_branch_write_ref(repo_root, mission_slug, target_branch)  # today's rule
     return default_mission_primary_ref(topology_source, mission_branch, landed, fallback)
     ```
     Check the signature and semantics of `resolve_single_branch_write_ref` in the same module before composing. It must not swallow errors the strict reader wants to surface; if it does, document that it is the fallback only.
  3. Docstring: say it is the planning lane's write branch (FR-061 extended to the planning lane, #7860), that it raises, and that placement uses the non-raising path.
  4. Keep complexity ≤ 15. Add the name to the module's `__all__` if the module declares one.
- **Validation**: T001 passes, and `tests/mission_runtime/` stays green.

### Subtask T003 – Planning-lane write target (branch + checkout) on `primary_partition_checkout`

- **Purpose**: the single checkout authority, so WP02/WP03 do not re-derive it.
- **Files**: `src/specify_cli/coordination/planning_commit.py`, `tests/coordination/test_planning_lane_target.py` (new).
- **Steps**:
  1. Add a frozen dataclass, for example `PlanningLaneTarget(branch: str, checkout: Path, on_mission_branch: bool)`, and `planning_lane_target(repo_root: Path, mission_slug: str, target_branch: str) -> PlanningLaneTarget`:
     - `branch = planning_write_ref(...)`.
     - If `branch` is the Mission branch of a default, not-yet-landed Mission (compare with the target and with the stored-`single_branch` ref, or have `planning_write_ref`'s helpers tell you), then `checkout = primary_partition_checkout(repo_root, slug)`.
     - When that returns `None` but the Mission is on its Mission branch:
       - the repository root checkout itself holds the Mission branch (a default `single_branch` Mission, or a Mission not yet settled): `checkout = main repo root`;
       - otherwise raise a named error (for example `PlanningCheckoutMissing`) whose message names the Mission branch and the remedy. Look at how the coordination worktree is re-materialized today (`grep -rn "def ensure_coordination_worktree\|materialize.*coord" src/specify_cli/coordination`) and name that command.
     - Otherwise `checkout = main repo root` (unchanged shapes).
  2. Owned checkouts (`OwnedCheckout`) are resolved by their own arm in `workspace/context.py` and never reach this helper. Document that in the docstring.
  3. Tests on real git (use `git worktree add` to simulate the coordination worktree on `kitty/mission-x`):
     - default, not landed, worktree present → that worktree path, `on_mission_branch=True`;
     - default `single_branch` (root on the Mission branch) → repo root;
     - explicit `lanes_with_coord` → repo root and target;
     - default, not landed, worktree absent → raises the named error.
- **Validation**: tests green; mypy clean.

### Subtask T004 – Proposed amendment to ADR 2026-11-06-3

- **File**: `docs/adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize.md`.
- **Steps**:
  1. Append after the last amendment, using the form of the 2026-11-22 amendment at about :214 (heading, italic acceptance line, Gap/Decision bullets, ending "Nothing else in this record changes."):
     `## Amendment 2026-11-25 (Proposed): a default Mission's planning lane writes to its Mission branch until it lands (#7860)`
     - Italic line: *Proposed. The operator accepts or amends it on the pull request.*
     - **Gap**: Amendment 2026-11-22 kept `lane-planning` on the target branch. A default `lanes_with_coord` Mission's PRIMARY partition is on its Mission branch (Decision 5, FR-061), so planning work, its status and its review range sat on different branches. #7860 shows planning work on the Mission branch being refused; #7759 shows the reverse shape.
     - **Decision**: before the landing, a default Mission's planning lane writes to the Mission branch, in the checkout that holds it (the coordination worktree once settled). `implement`, the claim base and the implementation-evidence window (ADR 2026-10-04-5, Amendment 2026-11-25) all read one rule (`planning_write_ref`, `planning_lane_target`). After the landing, and for every explicit topology, the planning lane writes to the target, as before.
     - **#7759**: work committed on the target before the landing under the old guidance is no longer the work package's evidence. The refusal names those commits and the remedies (operator ruling "guidance only"); there is no migration.
     - **Recorded drift risk**: the review range (`review/wp_range.py`) reads the same rule with "not landed" assumed. Folding it onto `planning_write_ref` waits for #5604 (operator ruling).
  2. Update the `**Status:**` line at the top to list "Amendment 2026-11-25 proposed" (pattern: `docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md:12`).
  3. Run the docs checks for ADRs if the repo has them (`ls scripts/docs/`; for example `uv run --frozen python -m scripts.docs.check_spelling` on the file).
- **Parallel?** Yes, independent of T001–T003.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/mission_runtime tests/coordination -q -p no:cacheprovider
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_layer_rules.py -q
make test-fast
.venv/bin/ruff check <changed files> && .venv/bin/ruff format --check --force-exclude <changed files>
.venv/bin/mypy <changed .py files>
```

Record commands and pass/fail counts with `spec-kitty agent tasks add-history WP01`.

## Risks & Mitigations

- **Placement regression**: placement callers must not start raising. Keep `_default_mission_facts` non-raising and test it.
- **Layer rule**: keep imports lazy and inside functions.
- **Attribution**: commit only your owned files. Do not edit `review/wp_range.py`.

## Standing rules (from the dispatch)

- Signed commits only (`git cat-file commit HEAD | grep gpgsig`). No model names anywhere. `Co-Authored-By: Claude <noreply@anthropic.com>`.
- ruff, `ruff format --check --force-exclude` and mypy at zero findings, with no suppressions; complexity ≤ 15.
- No `make test-full`. Never retry to green; attribute every red (CLAUDE.md "baseline-red gotcha").

## Review Guidance

- Is there really one reader? `grep -n "def planning_write_ref\|def planning_lane_target" -r src` must find exactly one of each.
- Does the strict reader raise, and does placement not?
- Are all six T001 cases present, and do they fail without T002?
- Is the ADR amendment marked Proposed, does it answer #7759, and does it record the review-range drift?

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks mark-status T001 --status done --mission planning-lane-write-branch-01M8A725`
- `spec-kitty agent tasks move-task WP01 --to for_review --mission planning-lane-write-branch-01M8A725 --note "Ready for review"`
