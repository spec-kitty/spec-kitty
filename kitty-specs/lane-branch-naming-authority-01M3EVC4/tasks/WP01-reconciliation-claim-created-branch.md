---
work_package_id: WP01
title: Reconciliation claim uses the created lane branch
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-012
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Merge integrity (wave 1)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/merge/reconciliation.py
- tests/merge/_divergent_shapes.py
- tests/merge/test_reconciliation_divergent.py
- tests/merge/test_reconciliation.py
authoritative_surface: src/specify_cli/merge/reconciliation.py
create_intent:
- tests/merge/_divergent_shapes.py
- tests/merge/test_reconciliation_divergent.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP01 – Reconciliation claim uses the created lane branch

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This WP fixes the reported #5108 defect at its core. The reconciliation claim is the stage that refuses a legitimate merge with "no approved lane resolved any commits".

Success means:

1. `merge/reconciliation.py::_lane_branch_for` returns the lane's **created** branch. That is the name composed from `(LanesManifest.mission_slug, lane_id)` alone, and never from `mission_id`.
2. Every claim consumer uses that one helper: `_collect_approved_shas`, `_collect_excluded` and `_collect_authored`. This covers approved-commit attribution, the canceled-lane exclusion and the authored-blob spine.
3. `build_approved_wp_set` refuses by name when an approved, non-planning, non-canceled lane's created branch does not exist in git. The refusal text looks like `approved lane lane-a: created branch 'kitty/mission-057-foo-lane-a' does not exist …`. An empty commit set that later surfaces as the generic refusal is no longer possible (US1 AS3).
4. A shared, real-allocator **divergent-shape fixture** (`tests/merge/_divergent_shapes.py`) exists and is reused by WP02 and WP03.
5. Red-first tests prove the claim now attributes commits for all 4 divergent shapes, and for canceled plus survivor (US1 AS1–AS3). Each test fails on HEAD first.

## Context & Constraints

- **Spec**: `kitty-specs/lane-branch-naming-authority-01M3EVC4/spec.md`.
  - US1 scenarios AS1–AS3.
  - FR-001, FR-003 and FR-012.
  - Edge cases: an invalid identity at ≥ 8 characters and at < 8 characters.
  - SC-001 (the end-to-end proof lands in WP03).
- **Plan**: `plan.md`.
  - PD-2: the slug key is `LanesManifest.mission_slug`.
  - PD-5: the FR-003 refusal.
  - PD-14: the invalid identity < 8 characters fixture records `mission_branch`.
  - Complexity Tracking: `build_approved_wp_set` is CC2 and must stay ≤ 5.
- **Research**:
  - Part A §1.2 lists `merge/reconciliation.py:855 _lane_branch_for` as a divergent site.
  - Part A §3 "FR-003" gives the per-site change list.
  - Part A §2 covers which slug to use.
- **Data model**: `data-model.md` "ApprovedWpCommitSet" defines the new refusal arm and invariants I-1 and I-2.
- **Charter**: ATDD-first / red-first (DIRECTIVE_034, DIRECTIVE_041), close the class by construction (DIRECTIVE_043), C901 ≤ 15, no new suppressions.
- **Constraints**:
  - C-002: no lanes-manifest schema change.
  - C-004: no probing. Never test several candidate names for existence; compose the created name and check it.
- **Signature fact (verified at HEAD)**:
  - `lane_branch_name(mission_slug, lane_id, planning_base_branch=None, *, mission_id=None)` has an **optional** `mission_id`, so you can drop the keyword here now.
  - `worktree_dir_name` and `worktree_path` take `mission_id` as a **required** keyword. Do not call them without it before WP07. Prefer `predict_lane_worktree` in tests.

**Implementation command**: `spec-kitty agent action implement WP01 --agent <name>`. The dependency list is empty.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json` (written by `finalize-tasks`). Enter the workspace that `spec-kitty agent action implement` resolves; never reconstruct the path yourself.

## Subtasks & Detailed Guidance

### Subtask T001 – Build the shared real-allocator divergent-shape fixture

- **Purpose**: A single fixture builder produces every divergent shape from US1 through the **real lane-creation path**. WP02 and WP03 import it. It must never compose a lane name with a Mission identity; that is exactly the defect under test.
- **File**: `tests/merge/_divergent_shapes.py` (new, private helper module with a leading underscore, so pytest does not collect it).
- **Steps**:
  1. Build a tmp git repo with a target branch (`main`). Configure `user.name` and `user.email` locally. Follow the existing real-git merge fixtures in `tests/merge/test_reconciliation.py` and `tests/integration/test_merge_lane_planning_data_loss.py`, and reuse their helpers where they exist (canonical sources).
  2. Write `kitty-specs/<slug>/meta.json` and `lanes.json` for each shape. Each `LanesManifest` records `mission_slug`, `mission_id`, `mission_branch`, `target_branch` and lanes with `wp_ids`.
     - Write `lanes.json` through the canonical writer (`lanes/persistence.write_lanes_json`), not raw JSON.
     - Always **record `mission_branch`** (PD-14). Set it to the branch today's first finalize would have produced, and let the allocator create it.
  3. Create each lane by calling `allocate_lane_worktree(repo_root, mission_slug, wp_id, lanes_manifest)` (`lanes/worktree_allocator.py`). Keep the returned `(worktree_path, branch)` in the fixture result.
  4. Make at least one commit per approved lane inside its worktree, touching a WP-owned path, so the claim has commits to attribute.
  5. Emit status events so the snapshot marks WPs `approved` or `canceled`. Use the canonical emitter (`specify_cli.status.emit.emit_status_transition`) through the legal lane path (planned → claimed → in_progress → for_review → in_review → approved). Do not hand-write JSONL.
  6. Expose a frozen dataclass, for example `DivergentMission(repo_root, feature_dir, slug, mission_id, manifest, lanes: dict[str, tuple[Path, str]])`, plus one builder per shape:
     - `shape_backfilled_legacy()`: slug `057-foo`, with a valid ULID whose mid8 is **not** in the slug.
     - `shape_mismatched_mid8()`: slug `foo-01KV6510`, with an identity whose mid8 differs (for example a ULID starting `01M3AAAA`).
     - `shape_invalid_identity_long()`: `mission_id="not-a-valid-ulid"` (≥ 8 characters, not Crockford).
     - `shape_invalid_identity_short()`: `mission_id="abc"` (< 8 characters).
  7. Add variant knobs:
     - `with_canceled_lane=True`: two lanes; lane-a approved, lane-b canceled.
     - `delete_created_branch_of="lane-a"`: remove that lane's worktree (`git worktree remove`) and branch (`git branch -D`) **after** the approved commit, to reproduce US1 AS3.
- **Edge cases / notes**:
  - If a shape **cannot be built at HEAD** because the allocator raises for that identity (for example `_mid8` on the short identity via `resolve_mid8`), do **not** hand-compose names. Stop, record the traceback in the Activity Log, and report it to the orchestrator: it is a finding (plan Risk 1 / PD-14).
  - Keep the fixture deterministic: fixed ULIDs, fixed commit messages, `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` pinned if other fixtures do so.
  - A planning-artifact lane (`lane-planning`) must be supported for WP02's exemption tests. Add a `with_planning_lane=True` knob if cheap.
- **Validation**:
  - [ ] Each builder returns lanes whose branch equals what the allocator created (assert `git rev-parse --verify refs/heads/<branch>` succeeds).
  - [ ] No occurrence of `mission_id=` inside a lane-naming call in the fixture (grep).
  - [ ] Builders run in < 2 s each.

### Subtask T002 – Red-first claim tests over the divergent shapes

- **Purpose**: Prove the #5108 defect through the pre-existing entry point `build_approved_wp_set(repo_root, feature_dir, lanes_manifest, *, coord_base_ref, excluded_canceled_wp_ids=(), excluded_window_base=None)`, before fixing it.
- **File**: `tests/merge/test_reconciliation_divergent.py` (new). Markers: follow neighbouring merge tests (for example `git_repo`, `integration`), as `pytest.ini` declares them.
- **Tests** (parametrize over the 4 shapes where applicable):
  1. `test_claim_attributes_each_approved_lane[shape]`: `claim.refusal is None` and the approved SHAs include each lane's commit (US1 AS1). **Must fail on HEAD** (the approved set is empty, or the shape raises for the short identity).
  2. `test_canceled_lane_excluded_survivor_attributed[shape]`: pass `excluded_canceled_wp_ids={lane-b's WPs}`. The survivor is attributed and the canceled lane is excluded (US1 AS2).
  3. `test_missing_created_branch_refuses_by_name[shape]`: `claim.refusal` contains the lane id **and** the created branch name. Take that name from the fixture's recorded allocator output; never recompose it (US1 AS3).
  4. `test_authored_blobs_present_for_divergent_shape`: `claim.authored_blobs` is non-empty for the approved lane. This covers the spine consumer `_collect_authored`.
- **Red-first protocol**: write the tests, run them on the unmodified code, and record the failing output (counts plus one representative message) in the Activity Log. Then implement T003–T004.
- **Validation**:
  - [ ] Red on HEAD for tests 1, 3 and 4 (at minimum shapes a/b/c; shape d may crash on HEAD, which also counts as red).
  - [ ] Green after T003–T004.

### Subtask T003 – Route `_lane_branch_for` to the created name

- **Purpose**: A single helper yields the created branch for every claim consumer (FR-001, FR-003).
- **File**: `src/specify_cli/merge/reconciliation.py`, function `_lane_branch_for(lanes_manifest, lane_id)`. Around L853 at HEAD; the function name is the durable anchor.
- **Steps**:
  1. Drop `mission_id=lanes_manifest.mission_id`. Keep `planning_base_branch=lanes_manifest.target_branch`, so `lane-planning` still resolves to the planning base (I-3).
  2. Fix the docstring: "Resolve a lane's **created** branch name from the creation input (slug + lane id); the Mission identity is not an input (I-1)".
  3. Confirm `_collect_approved_shas`, `_collect_excluded` and `_collect_authored` all obtain the branch only through `_lane_branch_for`. If any composes its own name, route it through the helper.
- **Validation**:
  - [ ] `grep -n "mission_id" src/specify_cli/merge/reconciliation.py` shows no lane-naming use. Post-fix marker paths and lock keys keep using `mission_id`; that is correct.

### Subtask T004 – Named refusal for a missing created branch (PD-5)

- **Purpose**: An approved lane whose created branch does not resolve must produce a **named** refusal, not a silently empty commit set.
- **File**: `src/specify_cli/merge/reconciliation.py`.
- **Steps**:
  1. Add `_unresolvable_approved_lane_branches(repo_root: Path, lanes_manifest: LanesManifest, work_packages: Mapping[str, Any], excluded_canceled_wp_ids: frozenset[str]) -> list[tuple[str, str]]`. It returns `(lane_id, branch)` for every lane that meets all of these conditions:
     - the lane is not `lane-planning` (use `lanes.compute.is_planning_lane` if it accepts the lane object, since that is the single seam);
     - at least one of its WPs is approved (reuse the existing approval predicate used by `_collect_approved_shas`, for example `_lane_is_approved`);
     - the lane is not fully canceled;
     - `lanes/_git.branch_exists(repo_root, branch)` is False.
  2. In `build_approved_wp_set`, after the snapshot is materialized and before the collectors run, call the helper. If it returns entries, return an `ApprovedWpCommitSet` with `surface_resolved=True` and `refusal="approved lane <id>: created branch '<branch>' does not exist in git; the lane's work cannot be attributed. …"`, plus `manifest_wp_ids`, `mission_slug` and `planning_prefix`, mirroring the existing refusal construction. Join multiple lanes deterministically, sorted by lane id.
  3. Strict vs tolerant probes. `_lane_tip_commits` and `_lane_first_parent_spine` swallow `GitProbeError` → `[]`. Keep that tolerance **only** for the canceled axis (`_collect_excluded`). For approved lanes whose branch passed the existence check, a `GitProbeError` must become a named refusal. Implement this with a keyword-only `tolerate: bool = True` parameter, or a strict sibling helper, whichever keeps each function ≤ CC 5. Surface it by having `build_approved_wp_set` catch a small private exception and translate it into the refusal. Do not let a raw traceback escape.
  4. Keep `build_approved_wp_set` ≤ CC 5 (it is CC2 now). If needed, extract `_refusal_claim(lanes_manifest, planning_prefix, message)`.
- **Edge cases**:
  - A canceled lane with no branch: never a refusal (US1 AS2).
  - `lane-planning`: never checked.
  - Resume: after a prior attempt consolidated a lane, is its branch still present? Check `_phase_cleanup_worktrees_and_branches` ordering: cleanup runs after verification, so lane branches exist during a resume. If you find a path where approved lane branches are deleted before the claim is re-derived, stop and report it; do not paper over it with tolerance.
- **Validation**:
  - [ ] `.venv/bin/ruff check --select C901 src/specify_cli/merge/reconciliation.py` passes. Every touched function is ≤ 15; the target is ≤ 5.
  - [ ] T002 tests are green.

### Subtask T005 – Migrate `tests/merge/test_reconciliation.py`

- **Purpose**: The file holds about 15 lane-naming calls that pass a non-None `mission_id` (AST count at HEAD). After T003 they no longer describe what the claim reads, and WP07 will remove the keyword.
- **Rule (FR-012)**: fixtures that *create* branches under identity-composed names must move to allocator-built lanes: `allocate_lane_worktree`, or `predict_lane_worktree(repo_root, slug, lane_id)` for the name and path. Deleting the keyword alone is not enough.
  - Where a test only needs the branch string of a lane it created itself, read it back from the allocator output.
  - Where a test deliberately pins the old identity form, decide which it is:
    - it pins the defect → re-express it as a created-name assertion;
    - it pins something still true → keep the behaviour and drop only the identity.
  - Record each such decision in the Activity Log.
- **Validation**:
  - [ ] The alias-aware AST scan (below) reports 0 identity-passing lane-naming calls in the file.
  - [ ] Every test in the file passes.

```python
# Quick AST re-count helper (run ad hoc; do not commit)
import ast, pathlib
p = pathlib.Path("tests/merge/test_reconciliation.py"); t = ast.parse(p.read_text())
names = {"lane_branch_name", "worktree_dir_name", "worktree_path"}
for n in ast.walk(t):
    if isinstance(n, ast.ImportFrom) and n.module and "branch_naming" in n.module:
        names |= {a.asname for a in n.names if a.name in names and a.asname}
hits = [n.lineno for n in ast.walk(t) if isinstance(n, ast.Call)
        and getattr(n.func, "id", getattr(n.func, "attr", None)) in names
        and any(k.arg == "mission_id" for k in n.keywords)]
print(hits)
```

### Subtask T006 – Quality gates and blast radius

- Observe (do not edit) `tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget`. It is red on HEAD (2 failed: "no approved lane resolved any commits"). Record whether it is green after WP01 alone. WP03 owns the "green unedited" assertion.
- Run the commands in the Test Strategy. Record the exact commands and pass/fail counts in the Activity Log.

## Test Strategy

- **Red-first**: T002 tests must fail on the pre-change code through `build_approved_wp_set`. Record the red run.
- **Real git**: tmp repos only. There are no git mocks for red-first cases (plan Technical Context).
- **Divergent shapes**: always built through `allocate_lane_worktree`. Never compose a lane name with an identity.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/merge/test_reconciliation_divergent.py tests/merge/test_reconciliation.py -q
.venv/bin/python -m pytest tests/merge/ -q
.venv/bin/python -m pytest "tests/integration/test_merge_lane_planning_data_loss.py" -q   # observe
.venv/bin/python -m pytest $(grep -rl "reconciliation" tests --include=*.py | tr '\n' ' ') -q
make test-fast
```

- **NFR gates**:

```bash
.venv/bin/ruff check src/specify_cli/merge/reconciliation.py tests/merge/_divergent_shapes.py tests/merge/test_reconciliation_divergent.py tests/merge/test_reconciliation.py
.venv/bin/ruff check --select C901 src/specify_cli/merge/reconciliation.py
.venv/bin/ruff format --check src/specify_cli/merge/reconciliation.py tests/merge/
.venv/bin/mypy src/specify_cli/merge/reconciliation.py tests/merge/_divergent_shapes.py tests/merge/test_reconciliation_divergent.py
```

- Diff coverage on changed lines must be ≥ 90% (NFR-004). Every new helper branch needs a test: missing branch, canceled, planning, and the strict probe error.

## Definition of Done

- [ ] T001–T006 done; each subtask marked with `spec-kitty agent tasks mark-status`.
- [ ] Red-first evidence recorded (the run on HEAD fails, the run after passes).
- [ ] 4/4 shapes attribute commits at claim level, canceled plus survivor passes, and a missing created branch produces a named refusal.
- [ ] 0 identity-passing lane-naming calls in owned files.
- [ ] ruff, ruff format, mypy and C901 are clean on touched files, with no new suppressions.
- [ ] `make test-fast` and `tests/merge/` are green, with baseline-red failures classified per CLAUDE.md.

## Risks & Mitigations

- **Over-strict refusal**: gate it on approved, non-planning, non-canceled lanes only, and cover each exemption with a test.
- **Shape (d) may crash inside the allocator at HEAD**: that is a finding. Report it; do not work around it.
- **Fixture drift into composing names**: reviewers grep the fixture for `mission_id=` inside naming calls and for f-strings with `-lane-`.

## Review Guidance

- Confirm the red run was recorded and that it goes through `build_approved_wp_set`.
- Confirm the fixture creates lanes only via `allocate_lane_worktree`.
- Confirm the refusal text names both the lane id and the created branch.
- Confirm `_lane_branch_for` has no `mission_id` and every consumer uses it.
- Confirm the compiler/typecheck (`mypy`) was run in addition to pytest.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
