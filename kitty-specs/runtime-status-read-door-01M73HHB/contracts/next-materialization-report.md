# CLI output contract: advancing `next` reports its coordination-worktree materialization

**Status**: new in this Mission (FR-003, FR-004). Supersedes the dropped `next --auto-remediate` contract (Decision Moment `01M73J4X57HKNF5RK7WVN8QHC5`, 2026-11-11).

## When it applies

An advancing `spec-kitty next` (with `--result`) whose bootstrap materialized or restored the Mission's coordination worktree. That is, the door's declared source before bootstrap was the committed coordination branch (worktree not checked out, or checked out but empty), and after bootstrap the worktree holds the Mission directory.

## Output

| Mode | Output added |
|---|---|
| human | one line before the decision text: `Materialized the coordination worktree for <mission> at <path>.` |
| `--json` | `"remediation": {"kind": "materialized_coordination_worktree", "path": "<path>"}` in the decision envelope |

## Never reported

- the coordination worktree was already materialized;
- query mode (no `--result`), which never materializes;
- a coordination branch deleted without landing (flatten guidance unchanged, nothing materialized);
- a Mission without coordination topology.

When `remediation` is absent the envelope is byte-identical to today's. No new flag is added.
