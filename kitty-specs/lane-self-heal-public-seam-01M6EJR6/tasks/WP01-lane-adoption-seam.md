---
work_package_id: WP01
title: 'Adoption seam: one allocator entry point, callers migrated, defect-class gate'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6898-lane-self-heal-public-seam
merge_target_branch: issue-6898-lane-self-heal-public-seam
branch_strategy: Planning artifacts for this mission were generated on issue-6898-lane-self-heal-public-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6898-lane-self-heal-public-seam unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-self-heal-public-seam-01M6EJR6
base_commit: 2fc85c611584741f5d234c05196ffbd91a680f90
created_at: '2026-11-02T16:58:56.337789+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Lane allocator seam
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/architectural/test_lane_adoption_single_seam.py
- tests/lanes/test_lane_adoption_seam.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/implement_support.py
- tests/architectural/test_lane_adoption_single_seam.py
- tests/lanes/test_lane_adoption_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Adoption seam: one allocator entry point, callers migrated, defect-class gate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter
(`python-pedro`, role `implementer`) and behave according to it before the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Read the `review_ref` field in the status event log (`spec-kitty agent tasks status`) before
starting if this work package was returned from review; every feedback item is a TODO. Record
what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

Close issue #6898: `implement_support.reenter_lane_self_heal` must stop importing
`_merge_recorded_planning_commit`, `_merge_dependency_lane_tips` and `_validate_worktree_clean`
from `worktree_allocator.py`. The allocator gains ONE public seam, `adopt_lane_ancestry()`, that
owns "make this reused lane worktree current", with the clean-worktree policy as an explicit,
documented parameter; the allocator's own routes and the self-heal re-entry both go through it;
a red-first structural gate keeps the defect class closed.

Done means:

- `adopt_lane_ancestry(...)` exists in `src/specify_cli/lanes/worktree_allocator.py` with
  `clean_worktree_policy` keyword-only and **no default** (`Literal["refuse-dirty",
  "allow-dirty"]`), `target_tip: str | None = None` captured from
  `lanes_manifest.target_branch` when `None`, and the fixed order recorded planning commit →
  dependency lane tips.
- `grep -rn "_merge_recorded_planning_commit\|_merge_dependency_lane_tips\|_validate_worktree_clean"
  src/` shows **no** call site outside `worktree_allocator.py`.
- Behaviour is unchanged: code-lane re-entry still tolerates uncommitted WIP; planning-lane
  re-entry still refuses a dirty or protected repository-root checkout; the second call on an
  already-current workspace is a no-op; a legacy/non-lane mission still returns `None`.
- `tests/architectural/test_lane_adoption_single_seam.py` is red on `origin/main` and green on
  this WP's head, with self-mutation fixtures proving it fires.

## Context & Constraints

Read before coding:

- `kitty-specs/lane-self-heal-public-seam-01M6EJR6/spec.md` (FR-001..FR-006, NFR-001..003, C-001..C-005)
- `kitty-specs/lane-self-heal-public-seam-01M6EJR6/plan.md` (seam signature, call-site policy table, risks)
- `kitty-specs/lane-self-heal-public-seam-01M6EJR6/research.md` (D1..D4: why a `Literal` policy, why the
  seam captures the tip, why behaviour is frozen, why the gate is scoped to the adoption trio)
- `.kittify/charter/charter.md` — single canonical authority, ATDD-first, architectural gate discipline
  (Standing Order #5), `NO_FULL_HEAVY_SUITES_IN_MISSION`.
- `tests/architectural/test_lane_allocation_single_seam.py` — the AST-guard shape this WP's gate mirrors.
- `docs/adr/3.x/2026-07-29-1-lane-base-recorded-planning-commit.md` — why the planning commit is merged first.

Hard constraints:

- **No behaviour change** (C-001). Moving the decision is the whole point; changing the policy is a defect.
- **Single authority** (C-002): ordering and the clean-worktree decision live in the allocator.
- Keep the repo's `Literal`/`Path`/docstring style; `mypy --strict` must pass.
- Only run the targeted test files (C-003); no full `tests/architectural/` sweep, no `make test-full`.

## Branch Strategy

- **Strategy**: mission lane worktree, branch cut from the mission planning branch
- **Planning base branch**: `issue-6898-lane-self-heal-public-seam`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T001 – Red-first: the structural gate

- **Purpose**: Prove the defect exists before fixing it, and keep it closed afterwards.
- **Steps**: Create `tests/architectural/test_lane_adoption_single_seam.py` with
  `pytestmark = pytest.mark.architectural` and a `_REPO_ROOT = Path(__file__).resolve().parents[2]`
  anchor. Assert, by AST over `src/`:
  1. `adopt_lane_ancestry` is defined in `worktree_allocator.py`, and its `clean_worktree_policy`
     parameter is keyword-only with **no default** and annotates `Literal["refuse-dirty",
     "allow-dirty"]` (accept the annotation's source text via `ast.unparse`);
  2. the allocator calls the seam at **at least three** sites (REUSE / CRASH_RECOVERY / FRESH) and
     `implement_support.py` calls it at least once;
  3. **no module under `src/` other than `worktree_allocator.py` imports** any of
     `_merge_recorded_planning_commit`, `_merge_dependency_lane_tips`, `_validate_worktree_clean`
     from `specify_cli.lanes.worktree_allocator` — cover `ast.ImportFrom` (with `asname`), relative
     import levels, and `from specify_cli.lanes import worktree_allocator` + `worktree_allocator._x`
     attribute use only if that is cheap and exact; at minimum every `ImportFrom` and `Import` form.
- **Files**: `tests/architectural/test_lane_adoption_single_seam.py` (new).
- **Parallel?**: No — it must be the first commit.
- **Notes**: Add self-mutation fixtures: a synthetic source string importing
  `_merge_dependency_lane_tips` from another module must be flagged; a synthetic clean module must
  not be. Add a concrete floor assertion (`wp_count >= 1`, `route_sites >= 3`) so the checker cannot
  pass vacuously. Run it now: it MUST fail on this base (seam missing, import present). Record the
  failing run in the commit message body.

### T002 – The seam

- **Purpose**: One public entry point that owns adoption.
- **Steps**: In `src/specify_cli/lanes/worktree_allocator.py`, add

  ```python
  def adopt_lane_ancestry(
      repo_root: Path,
      worktree_path: Path,
      mission_slug: str,
      lane: ExecutionLane,
      lanes_manifest: LanesManifest,
      *,
      clean_worktree_policy: Literal["refuse-dirty", "allow-dirty"],
      target_tip: str | None = None,
  ) -> None:
  ```

  Behaviour: `refuse-dirty` → `_validate_worktree_clean(worktree_path, lane.lane_id)` before any
  merge; `allow-dirty` → skip it (docstring must state why: a re-entry for the SAME in-flight WP
  has legitimate WIP, and git's own merge machinery refuses a merge that would clobber dirty
  paths). Then, if `target_tip is None`, capture it with
  `capture_branch_tip(repo_root, lanes_manifest.target_branch)` (document that a lane HEAD is never
  a valid target tip, #4827/C-006). Then `_merge_recorded_planning_commit(...)` and
  `_merge_dependency_lane_tips(...)`. Any other policy value raises `ValueError`.
- **Files**: `src/specify_cli/lanes/worktree_allocator.py`.
- **Notes**: Public docstring is required (charter, Code Review Checklist). Do not add a default to
  the policy parameter.

### T003 – The allocator's own routes adopt the seam

- **Purpose**: Remove the three inline copies so ordering cannot drift (FR-004).
- **Steps**: Replace the two-merge pairs at REUSE (`~:1123`), CRASH_RECOVERY (`~:1189`) and FRESH
  (`~:1319`) with one `adopt_lane_ancestry(..., target_tip=target_tip)` call. REUSE and
  CRASH_RECOVERY pass `"refuse-dirty"` and drop their own `_validate_worktree_clean` call (the seam
  applies that same policy, once, before the merges); FRESH passes `"allow-dirty"` — the worktree was
  created by this call, so there is no user state to protect and a clean check would only add a new
  refusal on repositories that are dirty by construction. Keep the FRESH conflict handler
  (`_remove_lane_worktree` on `PlanningCommitMergeConflictError`) intact. Pass the `target_tip`
  already captured at the top of `allocate_lane_worktree` (NFR-001: no second capture).
- **Files**: `src/specify_cli/lanes/worktree_allocator.py`.
- **Notes**: The FRESH route's post-merge `record_tip` and `_backfill_context_if_missing` stay
  where they are — the seam merges, it does not record.

### T004 – `reenter_lane_self_heal` delegates and loses the private import

- **Purpose**: Close the issue at its own call site (FR-003 partial, FR-006).
- **Steps**: Replace the private-name import block (and the now-unused
  `capture_branch_tip` / `_validate_worktree_clean` uses in that function) with one
  `adopt_lane_ancestry(...)` call: code lane → `clean_worktree_policy="allow-dirty"` (let the seam
  capture the target tip); planning lane → `clean_worktree_policy="refuse-dirty"`, keeping
  `assert_not_protected_branch` and the `replace(lane, depends_on_lanes=...)` filtered lane before
  the call. Keep every other step (manifest read, `lane_for_wp`, `create_planning_workspace`, the
  ancestry short-circuit, the `workspace_path.exists()` guard, `record_tip` for code lanes) and
  keep the returned-value contract (`Path | None`). Update the function docstring: it must name the
  seam as the owner of the merge order and the policy, and drop the "calls these two private
  helpers DIRECTLY" justification — the rationale moves into the seam's docstring (C-002).
- **Files**: `src/specify_cli/lanes/implement_support.py`.
- **Notes**: `_read_coordination_branch` stays imported (out of scope, C-005) — do not touch it.
  Check `grep` for unused imports afterwards.

### T005 – Behavioural tests

- **Purpose**: Pin the policy and ordering at the seam, and the frozen self-heal contract.
- **Steps**: Create `tests/lanes/test_lane_adoption_seam.py` (`pytestmark = [pytest.mark.fast,
  pytest.mark.git_repo]`, following the real-git fixture style of
  `tests/lanes/test_planning_claim_self_heal.py`, reusing `_init_repo`/`_write_meta_and_lanes`-style
  helpers where possible):
  1. `refuse-dirty` + an uncommitted file → `DirtyWorktreeError`, and the recorded planning commit
     is **not** merged (no mutation);
  2. `allow-dirty` + an uncommitted file → the planning commit becomes an ancestor and the dirty
     file is untouched;
  3. ordering: a lane with both a recorded planning commit and an approved dependency tip → both
     become ancestors, and the order is observable: `git rev-list --parents -n 1` on the
     dependency-tip merge commit shows the pre-merge lane HEAD as one parent and the dependency
     tip as the other, and `git merge-base --is-ancestor <planning-sha> <post-merge HEAD>` holds —
     so the planning commit was merged first and the dependency tip on top of it;
  4. `target_tip=None` captures from `lanes_manifest.target_branch` (assert an orphaned/foreign pin
     classification path is taken, i.e. the seam does not fall back to a lane HEAD);
  5. an invalid policy string → `ValueError`.
  Also add one case to the same file: a **code-lane** `reenter_lane_self_heal` on a dirty worktree
  still merges the recorded planning commit and preserves the dirty file (SC-004) — the direct
  proof that `allow-dirty` is still what the code lane gets.
- **Files**: `tests/lanes/test_lane_adoption_seam.py` (new).
- **Notes**: The existing files must stay green **unmodified** (SC-003): do not edit
  `tests/lanes/test_planning_claim_self_heal.py` or `tests/lanes/test_lane_tip_record_points.py`.

### T006 – Verify, document, and keep the gate honest

- **Purpose**: Evidence for review, and the gate's own non-vacuity proof.
- **Steps**: Run the verification set below; confirm the gate was red on the base commit (paste the
  red output into `spec-kitty agent tasks add-history WP01 --note ...` or the commit body). Confirm
  `git stash`-free tree, `ruff` and `mypy --strict` clean on the two source modules. Append to the
  mission tracer files (approach + design-decisions) via
  `spec-kitty agent tracer-append --mission lane-self-heal-public-seam-01M6EJR6 --category approach
  --entry "..."` when a decision was made while implementing.
- **Files**: none (verification), plus tracer appends outside `owned_files` (allowed: tracer files
  are mission state, not code ownership).

### T007 – Changelog fragment and the named verification set

- **Purpose**: Satisfy C-003 and C-004 explicitly instead of leaving them to close-out.
- **Steps**: Add `docs/changelog/unreleased/6898-lane-self-heal-public-seam.internal.md` with one
  entry in the fragment style (`docs/changelog/unreleased/README.md`): a bold impact-first lead, the
  `(#6898)` reference and before/after prose under 1,200 characters, saying that the lane adoption
  step now has one public owner and that `implement_support` no longer imports allocator internals.
  Rename the file to `<pr>.internal.md` once the pull request number exists, and do not edit
  `docs/changelog/CHANGELOG.md`. Then run the verification set below verbatim and record the counts
  with `spec-kitty agent tasks add-history WP01 --note ...`.
  Verify the fragment with `uv run --frozen python -m scripts.docs.check_changelog_style`.
- **Files**: `docs/changelog/unreleased/6898-lane-self-heal-public-seam.internal.md`.
- **Notes**: `check_changelog_style` rejects the old `[Unreleased]`-entry shape; a fragment is the
  only accepted form.

## Test Strategy

```bash
uv run pytest tests/architectural/test_lane_adoption_single_seam.py -q
uv run pytest tests/lanes/test_lane_adoption_seam.py -q
uv run pytest tests/lanes/test_planning_claim_self_heal.py tests/lanes/test_lane_tip_record_points.py tests/agent/test_agent_action_lane_context_refresh.py -q
uv run pytest tests/lanes -q
uv run pytest tests/architectural/test_lane_allocation_single_seam.py tests/architectural/test_no_dead_symbols.py -q
uv run ruff check src/specify_cli/lanes tests/architectural/test_lane_adoption_single_seam.py tests/lanes/test_lane_adoption_seam.py
uv run mypy src/specify_cli/lanes/worktree_allocator.py src/specify_cli/lanes/implement_support.py
```

The red-first proof is the gate failing on the base commit; record the command and the failing
assertion in the PR's `## Tests run` section later.

## Risks & Mitigations

- **A code-lane caller silently getting `refuse-dirty`** → the parameter has no default and the
  dirty-code-lane test (T005.6) pins the permissive branch.
- **Double clean check on allocator routes** → accepted (documented in plan Risks); do not "optimise"
  by adding a second policy value.
- **The gate passing vacuously** → concrete floor (`route_sites >= 3`) plus self-mutation fixtures.
- **FRESH route losing its conflict cleanup** → keep the `try/except PlanningCommitMergeConflictError`
  around the seam call exactly as before.

## Review Guidance

- Confirm `grep` shows zero external uses of the three private helpers.
- Confirm no default on `clean_worktree_policy` and that both policies are exercised by tests.
- Confirm the existing self-heal tests are unmodified (diff on those files must be empty).
- Confirm `adopt_lane_ancestry`'s docstring states the ordering and both policies.
- Confirm the gate is non-vacuous: read the self-mutation test and the floor assertion.
- Confirm behaviour freeze: the code lane is `allow-dirty`, the planning lane `refuse-dirty`.

## Progress & Status

Progress lives in the status event log — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
