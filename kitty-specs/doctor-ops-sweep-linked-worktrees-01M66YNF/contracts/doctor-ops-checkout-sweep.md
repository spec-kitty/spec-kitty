# Contract: `spec-kitty doctor ops` across every checkout (#6661)

The observable contract of the repository-wide Op sweep. It is a **narrowing of
scope, not a shape change**: the command's JSON payloads, value vocabulary and exit
codes stay exactly as they were before #6661.

## Listing

`spec-kitty doctor ops [--json]`

- Enumerates the checkouts `git worktree list --porcelain` reports for the project's
  repository (the shared enumeration in `specify_cli/invocation/op_custody.py`), with
  the project root checkout first, then `git worktree list` order, and file-name order
  inside a checkout. De-duplicated by resolved checkout path.
- An Op is open in a checkout when its `kitty-ops/<invocation_id>.jsonl` has no
  `completed` event and that checkout's `kitty-ops/op-closures.jsonl` holds no closure
  for the id.
- `--json` prints `[{"path": "<path relative to the project root>"}]`. A record in the
  root checkout keeps `kitty-ops/<id>.jsonl`; a record in a linked worktree is
  `../<worktree>/kitty-ops/<id>.jsonl`. No key is added or removed.
- Exit `1` when at least one open Op is listed, `0` when none is.
- A checkout whose Op store cannot be read is named on **stderr**; it contributes no
  records, so one broken worktree cannot hide the others. Stdout stays the payload.

## Sweep

`spec-kitty doctor ops --close-stale [--threshold <hours>] [--json]`

- Sweeps the Ops the listing would report, from every checkout.
- Each close goes through `ProfileInvocationExecutor.complete_invocation` with
  `outcome="abandoned"` and `closed_by="doctor_sweep"`, on an executor whose
  `record_root` is the checkout that owns the record. The closure is appended to that
  checkout's `kitty-ops/op-closures.jsonl` and auto-committed on that checkout's
  branch, under the existing #6410 skip rules. A per-record `kitty-ops/<id>.jsonl` is
  never mutated (archive freeze, #4397).
- The `--json` report keeps `open_ops`, `swept`, `skipped_fresh`, `threshold_hours`,
  `closure_spine` and the per-entry keys, with the existing `commit` value vocabulary
  (`committed`, `not_committed:<refusal>`, `skipped:<reason>`).
- Exit `1` on a per-op error or when fresh open Ops remain, `0` otherwise. A race with a
  concurrent manual close is `already_closed`, not an error.

## Out of scope

- The session-start/stop Open-Ops reminder (`specify_cli.session_presence.open_ops`)
  remains a single-checkout, git-free scan of the project root, under its own latency
  budget. It reports no other checkout's Ops, by design.
