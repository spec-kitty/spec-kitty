---
work_package_id: WP04
title: Operator release and truthful --abort (#5687 deadlock)
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-009
- SC-002
planning_base_branch: issue-5686-rollback-anchor
merge_target_branch: issue-5686-rollback-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-5686-rollback-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5686-rollback-anchor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rollback-anchor-authority-01M45VSA
base_commit: 22fb364234b934d77b1efba895bd1dc5e3d1c9bb
created_at: '2026-10-05T12:27:19.647789+00:00'
subtasks:
- T016
- T017
- T018
phase: Phase 2 - Operator surface
history:
- at: '2026-10-05T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/consolidate.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/consolidate.py
- tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py
- tests/specify_cli/cli/commands/test_merge_cli_golden.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Operator release and truthful --abort (#5687 deadlock)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile show python-pedro`) to load the agent profile in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also run `spec-kitty charter context --action implement --json` and apply it.

---

## Objectives & Success Criteria

Some branches can stay `NOT restored` forever: an unprovable kill-left move, or a foreign commit sitting on top of this run's landing. Today `--abort` refuses every time in that state (#5687). This WP adds an explicit, non-destructive operator release:

```
spec-kitty consolidate --abort --release-branch <b> [--release-branch <b2> ...] --release-reason "<text>"
```

The release keeps `<b>` at its live tip. The report shows the branch as `kept` by the operator, never as `restored`. The record clears once every other branch has been restored. The success line names the kept branches and never claims that everything was restored.

Done when the US3 acceptance scenarios AS1–AS4 in `spec.md` pass as CLI tests.

## Context & Constraints

- WP02 provides `rollback.release_branch(state, branch, live_sha, reason)`, `rollback.run_movable_branches(state)` and the `BranchOutcomeKind.KEPT_BY_OPERATOR` outcome. The authority applies a release only where the outcome would otherwise be NOT_RESTORED and the branch's live tip equals the released SHA.
- Abort flow: `_abort_lock_restore_clear` → `_abort_restore_or_keep_record` → `rollback_to_snapshot`. The AST pin requires that `_abort_restore_or_keep_record` stays the only caller of `rollback_to_snapshot` in this module. Record releases *before* that call, under the lock that `_abort_hold_global_lock_or_exit` takes. Read the live SHA under that lock as well.
- Validation, refusing with `RELEASE_BRANCH_INVALID` and exit 2 while changing nothing. Refuse when:
  - `--release-branch` is given without `--abort`;
  - `--release-reason` is missing or blank;
  - a named branch is not in `run_movable_branches(state)` (lane branches and unknown names are refused);
  - a named branch does not currently resolve (no live SHA).
- Option names use the Mission terminology canon. Help text must explain that the release keeps the branch's current commits, including this consolidation's unverified changes. It must not print a destructive recipe (C-002).
- `--release-reason` is printed in the report line, so it is auditable in the console output. The record is cleared afterwards.

## Branch Strategy

- **Strategy**: lanes. Use the workspace `spec-kitty implement WP04` prints.
- **Planning base / merge target**: `issue-5686-rollback-anchor`

## Subtasks & Detailed Guidance

Red first: commit the failing CLI tests of T018 before the implementation.

### Subtask T016 – Option, validation, persistence

- Add typer options to the consolidate command next to `--abort`. Find the `abort` option definition and its dispatch (`_dispatch_abort` / `_abort_lock_restore_clear`). Thread the values into the abort path.
- Persist the release via `rollback.release_branch` and `save_state` before the rollback, so a partially failed abort keeps the release bound to its SHA.

### Subtask T017 – Truthful text

- `_abort_success_line`: when the report has KEPT_BY_OPERATOR outcomes, write:
  `Aborted consolidation for <m>. Branches restored to their pre-consolidation commits, except <b> (kept at <sha> by operator release); state and workspace cleaned up.`
  When every branch was kept or already at its target, adapt the wording so it never says "restored" for a branch that was not restored. Have `_abort_restore_or_keep_record` return what the line needs (e.g. the report), keeping the AST-pinned call site.

### Subtask T018 – CLI tests (`tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`)

Follow the existing patterns in that file (real git, `begin_attempt` / `record_post_mutation_tips` set-up).
- AS1: the target is NOT_RESTORED (a foreign commit on top of the recorded post). Running `--abort` alone exits 1 and keeps the record (red/positive control on the same fixture). `--abort --release-branch main --release-reason "keep teammate"` exits 0, the target is unchanged, the foreign commit is present, the output has the `kept` line with the reason, the success line names `main` as kept, and the record is cleared.
- AS2: each invalid usage gives exit 2 and `RELEASE_BRANCH_INVALID`, with the record and branches unchanged.
- AS3: releasing a restorable branch (at its recorded post) restores it anyway; the output has a `restored` line and no `kept` line.
- AS4: after the release, the branch moves and `--abort` runs again: the release no longer applies (NOT restored, exit 1).

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py tests/specify_cli/cli/commands -k "consolidate or abort" -q -n auto --dist loadfile
uv run --frozen pytest tests/consolidation/test_single_rollback_authority.py tests/terminus/test_abort_restores_snapshot.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check --force-exclude <changed>
uv run --frozen mypy src/specify_cli/cli/commands/consolidate.py
```

## Risks & Mitigations

- `tests/specify_cli/cli/commands/test_merge_cli_golden.py` pins the exact set of long flags, so update it in this WP (owned). The reason flag is `--release-reason`, which sits next to the existing `--attest-reason`.

## Review Guidance

- No message says "restored" for a kept branch.
- Validation refuses before any state write.
- The AST pin is still green.

## Activity Log

- 2026-10-05T12:00:00Z – system – Prompt created.
- 2026-10-05T13:05:00Z – claude – T018 red-first: committed the failing US3 pins 56c64386 BEFORE the implementation. Red run (uv run --frozen pytest tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py tests/specify_cli/cli/commands/test_merge_cli_golden.py -q -p no:randomly): 12 failed, 29 passed — every AS1 release / AS2 refusal / AS3 / AS4 / help pin red, plus the golden flag pin; the AS1 positive control (plain --abort exits 1 and keeps the record) passed on the same fixture, proving the fixture reaches the deadlock rather than failing for setup reasons.
- 2026-10-05T13:05:05Z – claude – T016/T017 green (2d42d5bf): `_validated_release_flags` (CLI-boundary shape: --release-branch without --abort, missing/blank --release-reason) and `_check_release_targets` (not in run_movable_branches(state) — lane or unknown) refuse with a message ending `Error code: RELEASE_BRANCH_INVALID.` and exit 2 before any write; `_record_releases` reads the live tips through `movable_branch_tips` under the abort's global lock, refuses an unresolvable branch, then `release_branch` + `save_state` BEFORE the single rollback call. `_abort_restore_or_keep_record` now returns `(proceed, report)` and stays the only caller of `rollback_to_snapshot` in the module (AST pin green). `_abort_success_line` names every KEPT_BY_OPERATOR branch ("except <b> (kept at <sha> by operator release)"), and drops to "No branch was restored; <kept>" when nothing was restored.
- 2026-10-05T13:05:10Z – claude – Design notes: (a) the release is validated in two places by intent — flag shape at the CLI boundary (before the mission is even resolved, so `--release-branch` without `--abort` never touches a record) and membership right after the record is loaded, both before the lock and any write; (b) the live SHA is read under the lock the abort holds, so the bound SHA cannot drift between validation and persistence; (c) help text states that the released branch keeps its current commits including this consolidation's unverified changes, and carries no destructive git recipe (C-002); (d) `--release-reason` alone warns and is inert, mirroring `--note` / `--attest-reason`.
- 2026-10-05T13:05:15Z – claude – Green runs: pytest test_consolidate_abort_rollback.py test_merge_cli_golden.py test_single_rollback_authority.py test_abort_restores_snapshot.py test_no_legacy_terminology.py -q -> 157 passed (and 159 passed with tests/consolidation/test_consolidate_options.py added, -n auto --dist loadfile). Blast radius: pytest tests/specify_cli/cli/commands -k "consolidate or abort or merge" -n auto --dist loadfile -> 293 passed; pytest tests/integration/test_merge_abort_scope.py tests/consolidation/test_merge_state_authority.py tests/specify_cli/cli/commands/agent/test_wrapper_delegation.py tests/missions/test_feature_lifecycle_unit.py tests/consolidation/test_merge_preflight_mission_branch.py tests/architectural/test_destructive_op_routing.py -> 106 passed. ruff check + ruff format --check --force-exclude clean on the three changed files; ruff C901 (max 15) clean; mypy on consolidate.py: 5 errors, all pre-existing env noise (platformdirs/typer/rich stubs missing and their two downstream no-any-return/untyped-decorator), base 22fb3642 shows the same set.
