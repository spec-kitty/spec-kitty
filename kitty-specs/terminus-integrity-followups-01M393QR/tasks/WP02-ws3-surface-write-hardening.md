---
work_package_id: WP02
title: WS3 surface-write self-materialization hardening
dependencies: []
requirement_refs:
- FR-006
- FR-007
planning_base_branch: fix/terminus-integrity-followups
merge_target_branch: fix/terminus-integrity-followups
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-integrity-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-integrity-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-integrity-followups-01M393QR
base_commit: f17114642a5b9984d96b16e5b0f9d68d353ac7a0
created_at: '2026-09-24T07:59:26.534318+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Parallel fan (file-isolated)
history:
- at: '2026-09-24T07:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/write_target_degrade.py
create_intent:
- tests/mission_runtime/test_write_target_degrade_selfmat.py
- tests/integration/test_issue_verdict_selfmat_hardening.py
execution_mode: code_change
owned_files:
- src/mission_runtime/write_target_degrade.py
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/cli/commands/agent/issue_verdict.py
- tests/mission_runtime/test_write_target_degrade_selfmat.py
- tests/integration/test_issue_verdict_selfmat_hardening.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – WS3 surface-write self-materialization hardening

## ⚡ Do This First: Load Agent Profile
Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before
reading further. State what you applied, then continue.

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objectives & Success Criteria

Close #4970: the coordination write gate must **refuse** a self-materialization write onto a stale
local-head coord branch that already carries committed matrix content, and `issue-verdict` writes must
resolve through the **fail-closed** write resolver, not the degrading read resolver. Success (FR-006, FR-007):

- `assert_coord_write_materialized` allows self-materialization ONLY when the coord branch carries NO
  committed artifact-of-this-kind; otherwise REFUSE (the existing raise + remediation).
- The committed-content probe derives its path from the **placement authority** that produced
  `resolved.ref` (or `git ls-tree`s the whole `<coord>:kitty-specs/<slug>/` subtree) so a **path-drifted**
  committed matrix is never read as "absent" (post-plan F2). Unreadable git (not path-absent) ⇒ treat as
  **present** (fail-closed).
- `do_issue_verdict` calls `resolve_for_write(root, slug, ISSUE_MATRIX)` up-front (fail-closed), translating
  `ActionContextError` → the command's error type.

**Read first**: `work/epic-5001-research/followup-paula.md`, `contracts/invariants.md` (INV-3), and the
current `src/mission_runtime/write_target_degrade.py` (esp. the self-materialization arm ~lines 213-214),
`coordination/surface_resolver.py` (`_coord_branch_is_local_head`, `resolve_for_write`), and
`cli/commands/agent/issue_verdict.py` (`do_issue_verdict`, `_resolve_read_dir`). Verify line anchors — they
may have drifted.

## Subtasks

### T006 — committed-content probe (coordination/surface_resolver.py)
- Add a helper beside `_coord_branch_is_local_head` (which `assert_coord_write_materialized` already
  lazy-imports, so no new module edge — post-plan boundary check): e.g.
  `coord_branch_has_committed_artifact(repo_root, coord_branch, mission_slug, kind) -> bool`.
- Derive the probed path(s) from the same placement authority that resolves the artifact home (do NOT
  hardcode `kitty-specs/<slug>/issue-matrix.{json,md}`); alternatively `git ls-tree -r --name-only
  <coord_branch>:kitty-specs/<slug>/` and check for the matrix artifact(s). Both `issue-matrix.json` and
  `issue-matrix.md` map to ISSUE_MATRIX.
- Fail-closed: a **git error** (unreadable ref/tree) ⇒ return True (present). A clean "path absent" from a
  correctly-derived path ⇒ False. A path-drift must NOT read as absent (that is the F2 hole).

### T007 — refuse predicate (mission_runtime/write_target_degrade.py)
- Augment the self-materialization arm to the 3-part predicate: `UNMATERIALIZED AND local-head AND NOT
  committed-artifact-present` ⇒ return (allow); else fall through to the existing REFUSE raise + remediation
  message (unchanged).
- Call the T006 helper via the existing lazy import from `coordination`. Do NOT add a new first-level
  subpackage import edge or grow `tests/architectural/_baselines.yaml` caps.

### T008 — reroute do_issue_verdict (cli/commands/agent/issue_verdict.py)
- Insert a fail-closed `resolve_for_write(root, mission_slug, ISSUE_MATRIX)` near the top of
  `do_issue_verdict` (after arg validation, before the current degrading read-dir resolution / migration),
  translating `ActionContextError` → the command's error type (e.g. `IssueVerdictError`). After it passes,
  the existing read path returns the materialized coord dir so reads MERGE instead of clobber.
- Do NOT flip any other writer to `terminus_write` (post-plan C-003): status_transition / decision_log /
  bookkeeping / retrospective stay as-is.

### T009 — unit tests (red-first, mock-free)
- `tests/mission_runtime/test_write_target_degrade_selfmat.py`: (a) stale local-head + committed matrix ⇒
  REFUSE; (b) genuine first-write, no committed content ⇒ ALLOW (no false-refusal, NFR-003); (c) path-drift
  (committed matrix under a non-default derived path) ⇒ still detected ⇒ REFUSE; (d) unreadable-git ⇒
  REFUSE (fail-closed). Build the on-disk coord shape with real git (reuse `tests/terminus/conftest` style
  or a local fixture).
- `tests/integration/test_issue_verdict_selfmat_hardening.py`: (e) second `issue-verdict` on a stale
  local-head-with-rows ⇒ committed rows survive; (f) a normal materialized-coord verdict still succeeds
  (no false-refuse); (g) a flat / no-coord mission does not false-refuse (meta+no-coord no-ops the gate;
  post-plan F12).
- Write these RED first, then implement T006/T007/T008 to green.
- **Do NOT edit `tests/integration/conftest.py`** (it exists and is unowned — post-tasks paula M1); build fixtures locally inside `test_issue_verdict_selfmat_hardening.py`.

### T010 — F11 blast-radius record
- Run `PWHEADLESS=1 .venv/bin/python -m pytest tests/coordination tests/status tests/cli
  tests/specify_cli/tasks -o addopts="" -q` (issue_matrix scaffold surface) and record the result in
  `work/epic-5001-research/wp02-f11-blastradius.md`. If ANY legitimate flow commits an **empty-rows** matrix
  to the COORD branch as a first-write (which the file-existence check would false-refuse), switch T006/T007
  to a **row-emptiness** check instead of file-existence. Otherwise keep file/tree-existence and record why
  it is safe (`scaffold_issue_matrix` targets the PRIMARY dir, so empty-scaffold-on-coord is not a live flow).

## Definition of Done
- FR-006 + FR-007 implemented; `test_repro_4970` will go green at integration (do not touch it here).
- All T009 tests green; each REFUSE branch has a direct error-injection test (NFR-001).
- F11 blast-radius recorded; file-existence-vs-row-level decision justified.
- No new layer edge / baseline growth; `ruff`/`mypy`/`ruff format --check` clean on touched files.

## Risks / reviewer guidance
- Reviewer: verify path-drift is genuinely covered (test (c) uses a non-default path) and that unreadable-git
  fails CLOSED. Confirm the issue-verdict reroute does not false-refuse flat/no-coord missions. Confirm no
  blanket `terminus_write` flip crept in. Confirm the boundary: helper lives in `coordination`, reached via
  the existing lazy import.
