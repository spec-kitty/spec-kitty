# Tooling friction — drg-orphan-residual-live-record-01M68ZV0 (#6513)

## `spec-kitty agent tracer-append` refuses from the coordination worktree (pi, 2026-10-31)

Running `spec-kitty agent tracer-append --mission drg-orphan-residual-live-record ...` from
`.worktrees/drg-orphan-residual-live-record-01M68ZV0-coord` (checked out on
`kitty/mission-drg-orphan-residual-live-record-01M68ZV0`) is refused with

```
Planning artifacts must be committed from the coordination worktree, not the primary repo root.
```

even though the coordinating worktree is exactly where the command is run and its mission directory
is tracked on that branch. The same refusal came from the primary checkout. Consequence: the three
tracer files were authored directly instead of through the CLI. Not fixed here (out of scope for
#6513); worth a separate issue if it reproduces for other missions.

## `npx` is absent on this host (pi, 2026-10-31)

The markdown lint gate is `npx --yes markdownlint-cli2 "**/*.md"`, which is advisory in CI
(`|| true`) and cannot run locally here (no node). The docs gates that actually block
(`check_docs_freshness --ci`, page inventory, retrieval index, changelog style) were run and are
green.

## Shared global CLI asset cache races between agents (pi, 2026-10-31)

`spec-kitty safe-commit` failed once with `Global asset input changed:
~/.kittify/cache/agent-commands-freshness.lock`; the retry a few seconds later succeeded. Expected
contention on a host running many agents; no action needed beyond the retry.
