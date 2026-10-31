# Quickstart: verify the decisions lock is keyed on the event log

For a reviewer who wants to see the change work, in three checks.

## 1. The keying is the log's, not the ledger dir's

```bash
uv run pytest tests/specify_cli/decisions/test_decisions_lock_log_anchor.py -q
```

Expected: the module passes. The keying test asserts, on one fixture, that

- two checkouts resolving the **same** `status.events.jsonl` produce **one** lock path,
  even though their `decisions/` ledger directories differ, and
- two checkouts resolving **different** logs produce **different** lock paths
  (the same-fixture positive control: the probe can distinguish the two cases).

## 2. The open critical section does not overlap across checkouts

Same module, `-k overlap`: two concurrent `open_decision` calls are driven from two repo
roots that share a log, with the critical section instrumented; the recorded intervals do
not overlap. On the pre-fix code (or with the anchor lock removed) they do.

## 3. Nothing changed for the ledger-dir sidecar

```bash
uv run pytest tests/specify_cli/decisions/ tests/decisions/test_decisions_reconciler.py \
  tests/integration/test_owned_decision_runtime_lock.py \
  tests/specify_cli/orchestrator_api/test_decision_verbs.py -q
```

These are the #4848/#5925/#6628 ratchets: the sidecar file, its ignore provisioning, the
reconciler and the repair command keep their contract. `git status --porcelain` stays
empty after a decision write (the anchor lock lives under the git common dir).

## By hand, in a scratch repo

```bash
# after a decision open in any project:
git -C <repo> rev-parse --git-common-dir           # → the common dir
ls "$(git -C <repo> rev-parse --git-common-dir)/spec-kitty-locks/event-logs/"
# one <digest>.lock per event log a decision write has touched
git -C <repo> status --porcelain                   # empty: the lock is outside the tree
```
