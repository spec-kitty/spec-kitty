# Contract: `spec-kitty mission close --target <branch>` (#7201)

The one externally visible surface this mission adds. Everything else is internal
plumbing (the terminus bookkeeping commit learns a destination it is given).

## Option

| | |
|---|---|
| Command | `spec-kitty mission close` (and its `mission-type close` alias) |
| Option | `--target <str>`, default `None` |
| Applies to | the close leg and the `--discard` abandonment leg |
| Effect | the destination of the terminus retrospective bookkeeping commit (the `chore(<slug>): capture mission retrospective` commit that persists `kitty-specs/<slug>/retrospective.yaml` and its `status.events.jsonl` append) |

## Guarantees

1. **Omitted** (`--target` absent): destination resolution is unchanged —
   placement-port resolution from the Mission's `meta.json` `target_branch`, then
   the existing degrade path. No other behaviour of `mission close` changes.
2. **Supplied**: the named branch is the commit destination. `safe_commit`'s
   HEAD-must-match-destination refusal still runs; a `--target` that is not the
   checkout's branch is refused exactly as an unresolved destination was, and the
   terminus stays fail-open (warns, returns no commit, never aborts the close).
3. **Not a branch creator**: `--target` never creates, checks out, or moves a
   branch. It is a destination declaration, like `consolidate --target`.
4. **Provenance unchanged**: `--discard` still stamps `runtime_abandoned`; the
   close leg still stamps `runtime_post_completion`.
5. **Non-durable by design**: the resolved target of a `consolidate --target` run
   is not persisted (`clear_state()` removes `state.json`; the override is not
   written back to `meta.json`/`lanes.json`), so the option exists rather than a
   lookup. The terminus's refusal warning prints this command with the right
   `--target` when it knows one.

## Not covered by this contract

- `spec-kitty consolidate --target` itself (pre-existing).
- Any durable record of the resolved landing target (see the PR's `## Deferred`).
