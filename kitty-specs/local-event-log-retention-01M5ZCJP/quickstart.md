# Quickstart: clean up local event logs

```bash
# 1. See what retention would remove (changes nothing)
spec-kitty doctor event-logs

# 2. Machine-readable preview
spec-kitty doctor event-logs --json

# 3. Delete exactly the listed candidates
spec-kitty doctor event-logs --apply
```

Tune the limits in `.kittify/config.yaml`:

```yaml
ledger:
  retention:
    keep_runs: 50
    max_age_days: 90
```

Never removed: committed ledgers (`status.events.jsonl`, `decisions.events.jsonl`, Op records), the Op index (`kitty-ops/ops-index.jsonl`), the run index file, lock files, runs whose Mission is not merged and that did not finish, logs of an open Mission, items of a Mission this checkout cannot find, and anything whose lock another process holds.
