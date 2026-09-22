---
work_package_id: WP02
title: '#4868 — issue-verdict coord legacy-Markdown migration preserves existing verdicts'
dependencies: []
requirement_refs:
- FR-010
- FR-011
- FR-012
- FR-013
- FR-014
- FR-018
planning_base_branch: fix/verdict-matrix-rmw-preservation
merge_target_branch: fix/verdict-matrix-rmw-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/verdict-matrix-rmw-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/verdict-matrix-rmw-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-verdict-matrix-rmw-preservation-01M32M9G
base_commit: e4658fc2a0780f6733dc0cf6d005e93678a85041
created_at: '2026-09-21T19:33:57.087249+00:00'
subtasks:
- T007
- T008
- T009
- T010
history:
- Created by /spec-kitty.tasks 2026-09-21
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/issue_verdict.py
create_intent:
- tests/integration/test_issue_verdict_coord_legacy_md_preservation.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/issue_verdict.py
- src/specify_cli/tasks/issue_matrix_migration.py
- tests/integration/test_issue_verdict_coord_legacy_md_preservation.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load implementer-ivan
```

Apply the resolved initialization, boundaries, directives, and tactics. State which you applied, then continue.

## Objective

Fix #4868 (P1): on a coordination mission with a legacy `issue-matrix.md` on its authoritative
coord branch, recording a **different** issue via `issue-verdict` silently drops existing verdicts
because the first-JSON migration reads the **wrong source directory** (primary `feature_dir`
instead of the coord-aware `read_dir`). Make the migration read the authoritative surface and
preserve existing rows; keep the write staged on primary so the write-seam still materializes
coord and cleans residue.

**Charter gates**: ATDD red-first (C-011) — failing repro is a SEPARATE commit BEFORE the fix;
no `--feature` surface (C-004); write staging must NOT move to coord (C-011); no
`src/specify_cli/__init__.py` change (C-009).

Read first: `../spec.md` (US4/US5, FR-010..FR-014, FR-018, C-011), `../research.md`,
`../contracts/verdict-matrix-preservation-contract.md`, `../research/grounding-4868.md`.

## Grounded facts (verified on baseline)

- `issue_verdict.py::_migrate_if_needed` (**L138-176**): coord-aware `read_dir` resolved at
  **L161**; JSON existence check correct at **L162**; **BUG at L166** passes primary `feature_dir`
  to `migrate_issue_matrix_to_json`. `do_issue_verdict` (**L211**) is the pure core.
- `migrate_issue_matrix_to_json` (`tasks/issue_matrix_migration.py:219-271`) reads legacy from its
  `feature_dir` arg (**L240/242/248**); signature already `*`-separated; only callers
  (`_migrate_if_needed:166`, `_migrate_one_mission:~300`, 2 unit tests) pass keyword args after
  `feature_dir` → adding `read_dir` is backward-compatible.
- `write_issue_matrix` (`tasks/issue_matrix.py:327-378`) is a full-object overwrite; the write is
  staged on primary and routed through the write-seam (materializes coord + cleans residue).
- `coord_read_dir_for` (`src/mission_runtime/resolution.py:2131`) returns the coord dir only when
  topology routes there AND the worktree is materialized, else `None`.

## Subtasks

### T007 — Red-first: integration repro (coord legacy .md) [ATDD, commit FIRST]
Create `tests/integration/test_issue_verdict_coord_legacy_md_preservation.py` (integration, real
git + real write-seam — a faked `write_artifact` won't materialize the coord JSON and would mask
the fix). Reuse `_build_coord_mission_for_matrix` (import from
`tests/integration/test_accept_matrix_coord_partition.py`; do NOT edit it). Steps:
1. Build the coord mission; seed a legacy `issue-matrix.md` on the COORD surface (mkdir the lazily-
   materialized coord feature dir; commit on the coord branch) with issue **#A** `fixed` + evidence.
2. Assert the canonical reader (`load_issue_matrix` via `coord_read_dir_for(..., ISSUE_MATRIX)`)
   sees **#A before** the call.
3. Run `do_issue_verdict(mission=slug, issue="#B", verdict="fixed", actor="claude",
   evidence_ref=..., repo_root=tmp_path)` (chdir repo root as the accept-matrix test does).
Assertions (US4 S1/S2): `ok`, `migrated is True`, committed coord `issue-matrix.json` (resolved
via `coord_read_dir_for`, never a hand-rolled `-coord` path) AND `load_issue_matrix` return BOTH
#A (with evidence) and #B. RED on base (only #B).
Commit as `test(#4868): failing coord legacy-md issue-verdict preservation repro`.

### T008 — Red-first: mutation-killing write-staging spy + idempotency + malformed guard [same test commit]
Still before the fix, add (US4 S2/S3, FR-018):
- **Write-staging spy (C-011, mutation-tested)**: assert the migration's `write_issue_matrix`
  received `feature_dir == `primary (NOT `read_dir`/coord). A "no primary residue" check alone is
  insufficient (the untouched main write cleans residue for the wrong fix too). Demonstrate this
  assertion is RED against BOTH the base AND a `read_dir`-as-write-`feature_dir` mutant.
- **2nd-call idempotency**: record issue #C after the coord JSON exists → `migrated is False`, all
  of #A/#B/#C survive, no primary residue.
- **Malformed `.md`**: a malformed coord `.md` yields a structured `IssueVerdictError`/result
  (caught by the command), NOT a raw traceback.

### T009 — Fix: coord-aware migration read source + structured malformed error
1. `migrate_issue_matrix_to_json(feature_dir, *, read_dir: Path | None = None, ...)`: set
   `source_dir = read_dir or feature_dir` and use it for the legacy existence check + Markdown
   read (`L240/242/248`). Keep `write_issue_matrix(feature_dir=feature_dir)` unchanged (C-011).
2. `_migrate_if_needed` (`issue_verdict.py:166`): pass `read_dir=read_dir`.
3. Translate a malformed-`.md` validation failure into a structured `IssueVerdictError`
   (so `issue_verdict_command`'s `except IssueVerdictError` handles it — no raw traceback).

### T010 — Verify red→green + blast radius + lint
Confirm RED on base, GREEN on fix. Run the shared baseline `make test-fast` **plus** the targeted
surface:
`.venv/bin/python -m pytest tests/integration/test_issue_verdict_coord_legacy_md_preservation.py tests/specify_cli/cli/commands/agent/test_issue_verdict_command.py tests/specify_cli/tasks/ tests/architectural/test_issue_matrix_json_migration_completeness.py -q`.
Confirm the flat control `test_issue_verdict_command.py::TestMigrateOnWrite.test_legacy_markdown_mission_migrates_on_first_write` stays green (cite, don't rewrite). **Paste actual terminal
output** (not hand-typed counts); the reviewer RE-RUNS these rather than trusting recorded counts.
`uv run --frozen ruff check`/`ruff format --check` the touched files;
`uv run --frozen mypy src/specify_cli/cli/commands/agent/issue_verdict.py src/specify_cli/tasks/issue_matrix_migration.py` clean.

## Definition of Done
- FR-010, FR-011, FR-012, FR-013 (issue), FR-014, FR-018 acceptance criteria pass.
- Red-first commit precedes the fix; write-staging spy kills the `read_dir`-as-write mutant.
- Flat control still green; no `__init__.py` change; ruff + mypy clean.

## Risks / reviewer guidance
- **Insufficient guard**: a bare "no primary residue" assertion does NOT kill the wrong fix —
  verify the `feature_dir == primary` spy (T008) and its mutation-test evidence.
- **Precondition**: the coord-aware read only helps once the coord worktree is materialized (normal
  post-`finalize-tasks` state) — the degradation-to-primary path is documented, not a new bug.
- **Backward-compat**: `read_dir` is keyword-only/defaulted; confirm bulk `_migrate_one_mission`
  and unit callers unaffected.
