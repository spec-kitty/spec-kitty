---
affected_files: []
cycle_number: 1
mission_slug: close-stale-lifecycle-records-01M72B89
reproduction_command:
reviewed_at: '2026-11-10T10:31:55Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (cycle 1): changes requested

Reviewer: claude (reviewer-renata). Verdict: **reject**, one blocking defect; everything else is sound.

## Blocking

### B1 (high): the cross-checkout dedupe counts only *unpaired* occurrences, so a second sweep is not idempotent and a record paired in one checkout is abandoned in another (NFR-002, analysis finding I1)

`src/specify_cli/doctor/ops.py`, `_sweep_lifecycle_checkout` (the `held` counter and `seen |= held`): `held` counts a key only when the checkout returns it from `unpaired_started`. A checkout that holds the same `started` record **paired** contributes nothing to `seen`, so a later checkout that still shows it open closes it again.

Both cases reproduced on this branch's tip with the WP's own test helpers (`_repo`, `checkout_issue_branch`, `_started`, `_commit_all`):

1. **Second sweep, record on a shared branch** (the I1 fixture, `test_a_record_held_by_two_checkouts_is_closed_once`, then run the sweep a second time):
   - first run: `[('closed_abandoned', 'committed')]` in the repository root checkout;
   - second run: `[('closed_abandoned', 'committed')]` again, now in the linked worktree; `_abandoned(repo) == ['implement::shared']` and `_abandoned(worktree) == ['implement::shared']`.
   The second sweep writes and commits a new record (NFR-002 says 0), and once the lane branch meets the issue branch the group has two completions for one `started` record: the over-completion I1 asked to prevent, which can mask a later orphan of the same action. In this repository, where `kitty-ops/lifecycle/` is tracked on `main` and every lane worktree holds all records, running the sweep twice writes the 123 closures again in the first lane worktree.
2. **Closure or completion in one checkout, record still open in another**: `started` committed on the issue branch, worktree created, then `write_paired_completion(repo, ...)` committed in the root checkout; one sweep writes an `abandoned` record in the worktree (`root [] wt ['implement::shared']`). Same over-completion after the merge.

The SC-001 run used a scratch clone with no linked worktrees, so it could not show this.

**Required change.** Count every `started` occurrence a checkout holds, paired or not, as handled; a later checkout closes only unpaired occurrences beyond what earlier checkouts held. For example, build `held` from all `started` records of the checkout (by the same key) and close an unpaired occurrence only when its running index exceeds `seen[key]`; keep `seen |= held`. This keeps the twins case (both closed in the one checkout that holds both) and the record-only-in-a-worktree case (closed there), and makes both scenarios above write nothing. Update the docstring and the trail-model bullet ("reported once, even when several checkouts hold it") to say the record is handled by the first checkout that holds it, paired or not.

**Required tests** in `tests/specify_cli/invocation/test_doctor_ops_lifecycle_7346.py`, red before the fix:
- the I1 fixture swept twice: the second run returns `[]` and writes nothing in either checkout;
- the record completed (or abandoned) and committed in the root checkout while the worktree still shows it open: no `abandoned` record in the worktree.

## Non-blocking (fold if cheap)

- **L1 (low)** `src/specify_cli/invocation/executor.py`, `_op_commit_skip_reason`: a probe failure for lifecycle records still says "...whether to commit the Op record"; and the log lines in `_commit_record_paths` say "Op record auto-commit for lifecycle closures". Consider naming `kind.label`. The Op wording must stay byte-identical.
- **L2 (low)** `tests/specify_cli/invocation/test_op_commit_policy.py`: the WP prompt (T007) asked for direct tests of the lifecycle pattern (`LIFECYCLE_RECORD_PATH_RE`, `probe_primary_tracking(repo, LIFECYCLE_RECORDS)` true/false and the skip wording, including the unresolved-primary message). It is covered only indirectly through the sweep tests today.
- **L3 (low)** `_sweep_lifecycle_checkout` catches `OSError`/`UnicodeDecodeError` from `read_lifecycle_records` and only logs; the prompt asked to reuse the `unreadable_checkouts` stderr reporting. `read_lifecycle_records` already tolerates bad files, so this is rarely reachable; reporting it would match the Op half.

## Verified sound (no action)

- Executor refactor is behavior-preserving for Op closes: same path/message choice, same refusal mapping (`not a git worktree`, `detached HEAD`, `InvalidCoAuthor`, `protected branch '<b>'`, `repr(exc)`), `_op_commit_kwargs(*paths)` still shared with the admission probe in `op_write_refusal`; per-kind tracking cache correct. The deviation from `trail_commit.py` is sound (one commit implementation; existing patches of `executor.safe_commit` keep covering it).
- `RecordKind`: Op skip messages byte-identical (`Op records`, `kitty-ops/`); lifecycle pattern correct.
- C-003 (Op keys unchanged, `lifecycle_records` additive), exit-code rule, C-005 (no override; refusal reported), FR-004 test non-vacuous (seeds `meta.json` and `status.events.jsonl`, asserts the only change is the closure), red-first commit order, WP01 L1/L2 folded, docs and changelog accurate, terminology clean.
- Complexity <= 15, ruff, format and mypy clean on the touched files.
