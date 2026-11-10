---
affected_files: []
cycle_number: 2
mission_slug: close-stale-lifecycle-records-01M72B89
reproduction_command:
reviewed_at: '2026-11-10T10:49:36Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (cycle 2): changes requested

Reviewer: claude (reviewer-renata). Verdict: **reject**, one remaining dedupe hole (the mirror image of B1 scenario 2). L1 and L2 are done; the L3 deferral is accepted.

## Verified fixed

- B1 scenario 1 (second sweep) and scenario 2 (paired in the root checkout, open in a stale worktree): fixed by counting every `started` occurrence into `held`. Both red-first tests (`48bd4658` before `ed24a1e8`) are present and green. The twins case and the worktree-only record still close.
- L1: log lines say "Record auto-commit"; the probe-failure skip names the lifecycle records, and the Op wording is unchanged.
- L2: `test_lifecycle_record_pattern` and `test_lifecycle_tracking_is_judged_on_lifecycle_records_only` cover the pattern, the probe and the skip wording.

## Blocking

### B2 (medium): a record that is open in an earlier checkout but paired in a later one is still closed (`src/specify_cli/doctor/ops.py`, `_sweep_lifecycle_checkout`)

Ownership goes to the first checkout that holds the record, in `_checkouts` order. When that checkout holds an **open** copy and a later checkout holds the **paired** copy, the first checkout writes and commits an `abandoned` record. Once the branches meet, that `started` record has two completions: the same over-completion B1 was about, in the other direction.

Reproduced on `5b8d5b09` with the WP's helpers in a temporary test file that I deleted:
1. `started` written and committed on the issue branch in the repository root checkout.
2. A linked worktree is created from it.
3. `write_paired_completion(worktree, started=s, phase="completed")` is committed in the worktree.
4. One sweep: `entries [('closed_abandoned', 'committed')]`, `root ['implement::shared'] wt []`.

This is how a lanes Mission can look when `next` issued the action from the root checkout and the result was reported from a lane worktree.

**Required change.** A started record whose completion any checkout holds is already closed, so the sweep must not close it anywhere. Read every checkout first. For each record identity, take the largest number of paired occurrences that any single checkout holds. A checkout closes an unpaired occurrence only when its running index is above both that number and `seen[key]`. Keep the per-checkout write and commit as they are. Any equivalent rule is fine if it keeps the existing tests green and passes the new one.

**Required test** (red before the fix): the scenario above. The sweep returns `[]` (or no `closed_abandoned` entry) and writes no `abandoned` record in either checkout. Adjust the trail-model bullet and the docstring if the rule's wording changes ("belongs to the first one, paired or not" becomes "closed nowhere if any checkout holds its completion; otherwise closed once, in the first checkout that holds it").

## Checks run

- Complexity <= 15, ruff, `ruff format --check --force-exclude` and mypy are clean on the touched files.
- The targeted suite (invocation, golden, next seam, doctor default run, event-log, JSON-contract, docs-parity and dead-symbol gates): 1068 passed, 5 skipped.
