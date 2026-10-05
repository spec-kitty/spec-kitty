---
work_package_id: WP06
title: Git plumbing — advance-intent sink and lagging-checkout restore
dependencies: []
requirement_refs:
- FR-006
- FR-012
- C-006
planning_base_branch: issue-5686-rollback-anchor
merge_target_branch: issue-5686-rollback-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-5686-rollback-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5686-rollback-anchor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rollback-anchor-authority-01M45VSA
base_commit: 22fb364234b934d77b1efba895bd1dc5e3d1c9bb
created_at: '2026-10-05T11:38:01.220885+00:00'
subtasks:
- T011
phase: Phase 1 - Git plumbing
history:
- at: '2026-10-05T12:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (split out of WP03 by the post-tasks squad)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/ref_advance.py
create_intent:
- tests/git/test_ref_advance_intent_sink.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/git/ref_advance.py
- tests/git/test_ref_advance_intent_sink.py
- tests/git/test_restore_branch_ref_resync.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Git plumbing: advance-intent sink and lagging-checkout restore

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile show python-pedro`) to load the agent profile named in the frontmatter, then follow its guidance before reading the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also run `spec-kitty charter context --action implement --json` and apply it.

---

## Objectives & Success Criteria

`src/specify_cli/git/ref_advance.py` is git plumbing (C-006: it must never import consolidation). This WP adds two capabilities that later work packages wire up:

1. **Advance-intent sink (FR-006).** Add a module-level `ContextVar[Callable[[str, str, str], None] | None]` and a public context manager, for example `reporting_advance_intents(sink)`, exported where the module's public API is listed.
   - `advance_branch_ref` calls `sink(branch, old_sha, new_sha)` after its fast-forward, checkout and dirty checks, immediately before `_update_branch_ref_cas`. `old_sha` is the CAS old value actually passed to git.
   - `advance_branch_ref_for_commit` does the same before its CAS write.
   - If the sink raises, the exception propagates and the ref does not move (fail closed).
   - `restore_branch_ref` never calls the sink.
2. **Restore over a lagging checkout (FR-012).** `restore_branch_ref(resync_checkouts=True)` accepts a checkout whose index and worktree already equal the restore target. This is the state a kill leaves between `update-ref` and `_resync_checkouts`: HEAD at the landing, index and worktree at the old content. Implement it as a restore-only keyword on `_checkouts_ready_for` (e.g. `accept_at_target=True`). When `git diff --quiet <restored_sha>` and `git diff --cached --quiet <restored_sha>` both succeed in that worktree, skip the TRACKED verdicts but keep the untracked-obstruction check. `advance_branch_ref` behaviour is byte-unchanged.

Done when the tests below are green, each was committed red first, and `tests/git` stays green.

## Branch Strategy

- **Strategy**: lanes. Use the workspace `spec-kitty implement WP06` prints.
- **Planning base / merge target**: `issue-5686-rollback-anchor`

## Subtask T011 – Detailed guidance

Tests in the new `tests/git/test_ref_advance_intent_sink.py` (real temp git repos):
- The sink is called once with (branch, old, new). Inside the sink, assert the ref is still at old.
- A raising sink leaves the ref and the checkout unmoved.
- With no sink installed, behaviour is unchanged.
- A dirty-checkout refusal happens before the sink, so the sink is not called.
- A CAS mismatch: the sink is called and git refuses. Document this. The intent then exists without a move, which is why the authority requires `live == intent` before adopting.
- `restore_branch_ref` does not call the sink.
- `advance_branch_ref_for_commit` calls the sink.
- The ContextVar resets after the context manager exits, including on an exception.

Tests in `tests/git/test_restore_branch_ref_resync.py`:
- **Lagging checkout:** a worktree has branch B checked out at A. Run `git update-ref refs/heads/B C` directly, so HEAD = C while index and worktree are still A. Then `restore_branch_ref(B, A, expected_current_sha=C, resync_checkouts=True)` succeeds, and the checkout is clean at A.
- **Positive control, same fixture:** additionally edit a tracked file in the worktree. The restore refuses with `RefAdvanceDirtyWorktreeError` and nothing moves.

```bash
uv run --frozen pytest tests/git -q -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_destructive_op_routing.py -q
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check --force-exclude <changed>
uv run --frozen mypy src/specify_cli/git/ref_advance.py
```

## Review Guidance

- No import of consolidation in `ref_advance.py`. The sink is called strictly before the CAS write.
- The lagging-checkout acceptance applies to the restore path only and keeps the obstruction check.

## Activity Log

- 2026-10-05T12:30:00Z – system – Prompt created.
- 2026-10-05T11:47:30Z – claude – shell_pid=8059 – RED a4155fb6: pytest tests/git/test_ref_advance_intent_sink.py tests/git/test_restore_branch_ref_resync.py -> collection ImportError (reporting_advance_intents missing); resync file alone: 1 failed (lagging checkout refused), 9 passed. GREEN 1f74feb7: pytest tests/git -n auto --dist loadfile -> 245 passed, 2 skipped, 2 failed (test_protection_config_honoring x2, also red with base 22fb3642 ref_advance.py: pre-existing, not WP06); tests/architectural/test_layer_rules.py + test_destructive_op_routing.py + tests/consolidation/test_rollback_authority.py + tests/terminus/test_rollback_door.py -> 157 passed; ruff check + ruff format --check --force-exclude + C901 clean; mypy ref_advance.py: only pre-existing platformdirs import-not-found in src/kernel/paths.py (env).
