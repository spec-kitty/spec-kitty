# Tracer: Approach — user-content-preservation-01M3549Q

Records the chosen approach and pivots.

- Extend the EXISTING `asset_preservation.guard_destructive_removal` + provers (from #4859/#4861/#4862) to the removal flows (#4907, #2691) — do NOT fork a second authority.
- Overwrite flows (#4895 hook, #4910 intake) are OUT of the removal census (that's #4901): targeted per-site ownership-check-+-backup reusing `asset_preservation/backup.py`.
- Bespoke sub-shapes: #4896 (transcode-only-what's-wrong), #4890 (validate-the-graph-you-persist), #4888 (never-touch-operator-index) — NOT forced through the guard.
- Hybrid overwrite contract (operator DM): refuse+--force where user-driven (intake); backup+warn where workflow-internal (implement hook).

## WP07 / #4888 — `safe_commit` root fix + T026 caller audit

**Root fix (T024):** rewrote `safe_commit` (`src/specify_cli/git/commit_helpers.py`) to
stage EXACTLY `paths` into the real index (`git add --force -- <path>`, unchanged from
before) and commit via `git commit --only -m <message> -- <paths>` instead of
`git commit -m <message>`. `--only` structurally "disregard[s] any contents that have
been staged for other paths" (git-commit(1)), so the `git stash push --staged` /
`git stash pop --index` dance that used to hide-then-restore the operator's UNRELATED
staged content is gone entirely from the happy path — unrelated content (including a
file that is only *partially* staged, the exact shape that made `git stash pop --index`
fail deterministically) is never read, moved, or mutated. A failed commit (e.g. a
rejecting pre-commit hook) now restores ONLY `normalized_files` to their pre-call staged
state, via a narrow pre-mutation patch snapshot (`_staged_patch_for_paths` /
`_restore_staged_patch`, scoped to `paths` alone — never a whole-index stash). The
whole-index `assert_staging_area_matches_expected` backstop (Priivacy-ai/spec-kitty#588)
stays in the module, independently tested, but is no longer called from `safe_commit`
itself: an unscoped whole-index scan is structurally incompatible with leaving unrelated
staged content in place. Verified with a manual scratch-repo repro (`git read-tree` /
`git add --force` / `git commit --only` sequence) before writing it into the function.

**T025 (defense-in-depth):** `upgrade/autocommit.py`'s `commit_touched_checkout` now
re-raises `SafeCommitRecoveryFailed` instead of flattening it into
`UPGRADE_COMMIT_SKIP_WARNING`. `cli/commands/upgrade.py`'s `_finalizer_step_commit_churn`
catches it, renders the orphaned stash ref (if any) + landed SHA
(`_render_safe_commit_recovery_failed`), sets `outcome.result.success = False`, and
appends the message to `outcome.result.errors` — flipping the exit code non-zero on BOTH
the migrations and no-migrations human-render paths (the latter previously only rendered
`activation_errors`, not `result.errors`; fixed alongside). `cli/commands/implement.py`'s
generic `except Exception` handler for workspace-allocation failures now tracks a
`workspace_created` flag: when `_start_wp_implementation_status` fails AFTER
`create_lane_workspace` already succeeded (e.g. `SafeCommitRecoveryFailed` with
`commit_sha` set, surfacing after the status commit already landed), the printed message
says the WP's status commit may already have landed instead of the generic "Workspace
allocation failed" (which would contradict a WP already `claimed`/`in_progress`).

**T026 caller audit — every `safe_commit(` call site in `src/` (15 distinct sites, each
grepped and read in context):**

`invocation/executor.py:1029`, `core/mission_creation.py:269`,
`coordination/write_seam.py:393`, `coordination/transaction.py:829`,
`coordination/status_transition.py:346`, `coordination/commit_router.py:432`,
`upgrade/autocommit.py:423`, `cli/commands/safe_commit_cmd.py:478`,
`cli/commands/implement.py:1523`, `cli/commands/next_cmd.py:403`,
`cli/commands/agent/workflow_executor.py:1276` (`w.safe_commit`, same re-exported
symbol as `workflow.py`), `cli/commands/agent/tasks_verdict_persistence.py:447`,
`cli/commands/agent/workflow.py:726` (+ `_commit_via_legacy_safe_commit` wrapper at
`:674`, itself calling `safe_commit`), `cli/commands/agent/tasks_move_task.py:932`,
`git/bookkeeping_commit.py:167`, `events/decision_log.py:250`.

Every call site passes an explicit, fully-enumerated `paths=` tuple of exact files it
intends to commit — never a directory, glob, or "whatever is currently staged." None
relies on `safe_commit` sweeping in additional staged content beyond `paths`: the
pre-existing whole-index backstop (`SafeCommitBackstopError`) already made that reliance
structurally impossible before this fix (any extra staged path would have aborted the
commit), so no caller could have depended on it. The `--only` pathspec limits the commit
to exactly `paths` — the same guarantee, enforced a different (correct) way. Several call
sites already catch `SafeCommitRecoveryFailed` (`transaction.py`, `status_transition.py`,
`merge/executor.py` via `exc.commit_sha`) or the empty-changeset `RuntimeError`
(`write_seam.py`, `commit_router.py`, `next_cmd.py`) — both remain reachable and
unchanged in shape after the fix. No caller needed a code change beyond the three files
already listed as owned (`commit_helpers.py`, `upgrade/autocommit.py`,
`cli/commands/upgrade.py`) plus the `implement.py` message fix.
