---
work_package_id: WP02
title: Owned-checkout canceled read and honest move-task detail
dependencies: []
requirement_refs:
- FR-006
- FR-007
- NFR-002
- NFR-003
- C-003
- SC-003
planning_base_branch: fix/7149-ownership-unresolved
merge_target_branch: fix/7149-ownership-unresolved
branch_strategy: Planning artifacts for this mission were generated on fix/7149-ownership-unresolved. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7149-ownership-unresolved unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-files-unresolved-fail-closed-01M6HAHF
base_commit: f159605386af9e0e4fcacb7e982b52016822774c
created_at: '2026-11-03T18:58:12.297530+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 1 - Same-class folds
history:
- at: '2026-11-03T18:31:15Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/integration/test_owned_accept_canceled_work_package.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/done_bookkeeping.py
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py
- tests/integration/test_owned_accept_canceled_work_package.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Owned-checkout canceled read and honest move-task detail

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

Two same-class folds from the #7149 pre-spec squad:

1. **FR-006**: `spec-kitty accept --owned-checkout <path>` reads the operator-canceled work packages (`acceptably_canceled_wp_ids`) from the **owned checkout**, not the repository root. Today `accept.py` calls `acceptably_canceled_wp_ids(run.repo_root, run.mission_slug)` at two sites (~:1194 and ~:1242). That resolves `resolve_status_surface(repo_root, slug)`, which for a Mission that exists only in the owned checkout returns nothing (fail-open: an empty set), so canceled work packages are not excluded. The same Mission checked out in the repository root behaves correctly.
2. **FR-007**: the owned review-ward `move-task` (`tasks_move_task._mt_require_owned_implementation`, ~:917-940) refuses a work package that declares `owned_files: []` with the generic "Owned review requires a committed change matching WP owned_files." The work package file was already read there, so empty patterns mean an **authored empty declaration**, not an unreadable one. Keep the code `OWNED_IMPLEMENTATION_MISSING`, but give that branch its own detail: it declares no `owned_files`, and the task file path.

Success: both behaviours are proven red-first through their production entry points; every other `acceptably_canceled_wp_ids` caller is unchanged; `ruff` / `mypy` clean (NFR-003).

## Context & Constraints

- Spec: FR-006, FR-007, C-003. Plan: IC-03, IC-04. Research F4, F5.
- The owned-aware route already exists: `accept._evidence_status_dir(run)` resolves `placement_seam(run.repo_root, run.mission_slug, owned=run.owned).read_dir(MissionArtifactKind.STATUS_STATE)`. Reuse that seam; do not invent a path.
- **Do not** change the other callers: `orchestrator_api/consolidation.py` (:539, :579, :669), `done_bookkeeping.py:783`, `consolidation/preflight.py:1237`. `consolidate` / `orchestrator-api` have no owned-checkout support (out of scope, C-003).
- Open PR #7146 also edits `tasks_move_task.py`: touch only the `not patterns` branch of `_mt_require_owned_implementation`.
- Charter: red-first (Standing Order 4, DIRECTIVE_041). Run `spec-kitty charter context --action implement --json` first.

### ⚠️ Test economy (read before writing any test)

Every test you add is vetted at closeout under DIRECTIVE_041 and the KEEP / RETIRE / SPLIT-BY-KIND rubric (`packs/built-in/procedures/development-assist-test-cleanup.procedure.yaml`). Add a test only when it guards real behaviour through the production entry point (the `spec-kitty accept` / `spec-kitty agent tasks move-task` CLI through the existing owned-checkout fixtures), with realistic data, and fails on a real regression. No duplicate assertions, no redundant planted controls, no shape pins. Prefer strengthening an existing test; at most one focused test per behaviour. Red-first evidence that is not worth keeping goes in your report (command + failing output). **In your hand-off, include a table of every test you added or changed: test, regression it catches, existing coverage it relates to.**

## Branch Strategy

- **Planning/base branch**: `fix/7149-ownership-unresolved`
- **Final consolidation target**: `fix/7149-ownership-unresolved` (reaches `main` through a pull request)
- Execution worktrees are allocated per computed lane from `lanes.json`:

```bash
spec-kitty agent action implement WP02 --agent claude --mission owned-files-unresolved-fail-closed-01M6HAHF
```

## Subtasks & Detailed Guidance

### Subtask T009 – Red-first owned-accept canceled test (write first)

**Purpose**: prove the canceled read is from the repository root on an owned checkout.

**Steps**:
1. Study the owned-checkout integration fixtures: `tests/integration/test_owned_acceptance_authority_6023.py` (its scenario table and helpers) and the `pr_bound_checkouts` / `checkouts` fixtures (`tests/integration/test_owned_pr_bound_finalization.py`, `tests/integration/test_explicit_checkout_commands.py`). Reuse them through imports or fixtures; do not copy them.
2. In `tests/integration/test_owned_accept_canceled_work_package.py` (declare `pytestmark` like its siblings), build an owned-checkout Mission that is **absent from the repository root** (root on `main`), with two work packages: one approved with an owned change and independent review, one **canceled with operator provenance** (`move-task --to canceled` the way an operator does; check how `has_operator_provenance` is satisfied).
3. Run `spec-kitty accept --owned-checkout <path> --mission <slug> --diagnose` (or the exact invocation the 6023 tests use). Assert that the canceled work package is excluded: the evidence verdict and the done/canceled handling match a repository-root run of the same Mission. Pick the assertion that actually differs today. Find the observable: e.g. the canceled work package must not be reported by the evidence or done-state checks. Verify on the unchanged code that it fails, and record why.
4. If no observable difference exists on `accept` today (the evidence `_approved_wp_ids` may already filter canceled lanes, which the squad called "near zero evidence impact"), say so in your report with the evidence. Then keep only a unit-level test through `acceptably_canceled_wp_ids(repo_root, slug, owned=...)` with an owned fixture, plus its non-owned control. Do not add an integration test that cannot fail.

### Subtask T007 – `acceptably_canceled_wp_ids` takes the owned fact

**Steps**:
1. Add a keyword-only `owned: OwnedCheckout | None = None` (TYPE_CHECKING import from `mission_runtime`, as other modules do).
2. When `owned` is given, read the status events from `placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.STATUS_STATE)`. When it is `None`, keep exactly today's `resolve_status_surface(repo_root, mission_slug)` path. Keep the fail-open `except (FileNotFoundError, StoreError)` semantics and the docstring's contract, and extend the docstring with the owned route.
3. Keep complexity at or below 15 (Sonar S3776); extract a tiny `_status_dir(...)` helper if needed.

### Subtask T008 – `accept` passes `run.owned`

Pass `owned=run.owned` at both `acceptably_canceled_wp_ids(...)` call sites in `accept.py`. No other change in `accept.py`.

### Subtask T010 – Owned move-task empty-declaration detail

In `_mt_require_owned_implementation`, split `if not patterns or not any(...)` into:
- `if not patterns:` raise `ActionContextError("OWNED_IMPLEMENTATION_MISSING", <detail>)`, where the detail says the work package declares no `owned_files` in `<task file path>` (`st.wp.path`), so no committed change can be matched, and to declare its `owned_files` or move it as a planning work package. Keep it one or two sentences.
- `if not any(...)`: the existing message, unchanged.

The code string stays `OWNED_IMPLEMENTATION_MISSING` (registered; do not mint a new code).

### Subtask T011 – Strengthen the owned move-task test

In `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py`, find the test asserting the `OWNED_IMPLEMENTATION_MISSING` refusal. Strengthen it, or add a parametrized row on the **same fixture**, so that:
- authored `owned_files: []` → the new detail naming the task file (red before T010);
- declared files with no matching change → the existing message (control).

Do not add a second test function if a parametrize row covers it.

## Test Strategy

- Run: `uv run --frozen pytest -q -p no:randomly tests/integration/test_owned_accept_canceled_work_package.py tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py tests/specify_cli/cli/commands/test_accept_evidence_preflight.py tests/orchestrator_api/test_consolidate_mission_canceled_lane_5814.py tests/integration/test_owned_acceptance_authority_6023.py`, then `tests/consolidation -k "canceled or bookkeeping"`. Plus `ruff check`, `ruff format --check --force-exclude` and `mypy` on the changed source files.
- Non-vacuity: revert T007/T008 alone and confirm T009's test goes red; revert T010 alone and confirm T011's row goes red. Report both.
- Note: `tests/specify_cli/cli/commands` is an out-of-matrix directory (nightly-only), so your local run is the per-change evidence; record it in your hand-off.

## Risks & Mitigations

- **No observable on accept** (see T009 step 4): do not ship a vacuous integration test; fall back to the unit-level contract test.
- **Other callers drift**: `owned` defaults to `None`; verify `test_consolidate_mission_canceled_lane_5814.py` stays green.
- **Collision with PR #7146** in `tasks_move_task.py`: minimal edit.

## Review Guidance

- The owned route goes through `placement_seam(..., owned=...)`, with no hand-built path.
- Non-owned callers are byte-identical in behaviour.
- The move-task code string is unchanged; only the empty-declaration detail is new.
- Red-first and half-by-half evidence is present; the test table follows the test-economy rules.

## Progress & Status

Record progress with `spec-kitty agent tasks mark-status T0xx --status done --mission owned-files-unresolved-fail-closed-01M6HAHF` and notes with `spec-kitty agent tasks add-history WP02 --note "..."`.
