# CLI contract: `spec-kitty next --auto-remediate`

**Status**: new in this Mission (FR-003, FR-004)

## Synopsis

```
spec-kitty next --agent <name> --mission <handle> [--result <r>] [--auto-remediate] [--json]
```

## Behaviour

| Situation | Without the flag | With `--auto-remediate` |
|---|---|---|
| Advancing `next`, coordination worktree **not checked out** (branch exists) | blocked: today's reason text and remedy, today's exit code | materializes the coordination worktree through the canonical materializer (the one `spec-kitty doctor coordination --fix` uses), prints one line `Materialized the coordination worktree for <mission> at <path>.`, then returns the decision a materialized Mission gives |
| Advancing `next`, coordination worktree materialized or empty | normal decision | identical (flag is a no-op) |
| Coordination branch **deleted** without landing | flatten guidance | identical: nothing is remediated |
| Query mode (no `--result`) | query decision | identical: the flag is ignored and nothing is materialized |
| Materialization fails | — | today's block, plus one line naming the failure; exit code as for the block; nothing reported as success |

## JSON

With `--json`, a remediated run adds `"remediation": {"kind": "materialized_coordination_worktree", "path": "<path>"}` to the decision envelope. Runs without remediation carry no `remediation` key (the envelope is unchanged).

## Non-goals

No other block is remediated, and no other command gains the flag.
