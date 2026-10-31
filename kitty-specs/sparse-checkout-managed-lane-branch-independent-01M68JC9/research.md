# Research — managed lane classification must not depend on the repository-root checkout's branch

Mission: `sparse-checkout-managed-lane-branch-independent-01M68JC9`
Issue: [#6844](https://github.com/spec-kitty/spec-kitty/issues/6844)
Grounding base: `origin/main` @ `35318ef51c` (2026-10-31). Predecessor: #1413 (closed), which
taught the scanner to tell managed lanes from legacy state.

## 1. Reproduction (grounded, live, on current `main`)

A throwaway fixture in `/tmp` (script reproduced below verbatim in `research/repro-6844.py`)
builds exactly the issue's topology:

1. `git init -b main`, one base commit, then a `b-branch` created **before** Mission A exists.
2. Mission A's `kitty-specs/<A>/` (`spec.md`, `status.events.jsonl`, `status.json`, `meta.json`
   with `coordination_branch`) committed on `main`; `kitty/mission-<A>` branched.
3. `git worktree add` → `.worktrees/<A>-lane-a` on `kitty/mission-<A>-lane-a`, then
   `register_lane_sparse_checkout(lane, A, mid8)` (the production writer).
4. Probe with `scan_repo(root)` on `main`, then `git checkout b-branch` and probe again.

Observed on unmodified `main` @ `35318ef5`:

```
== primary on main (has mission A's kitty-specs) ==
  worktrees: [('mission-a-01J6XW9K-lane-a', 'managed_lane_sparse_checkout', False)]
  any_blocking: False
== switch primary to b-branch (no mission A kitty-specs) ==
  kitty-specs present: False
  worktrees: [('mission-a-01J6XW9K-lane-a', 'legacy_user_sparse_checkout', True)]
  any_blocking: True  affected: (.../.worktrees/mission-a-01J6XW9K-lane-a,)
```

**Decision:** the bug is live and exactly as reported — the *only* changed input between the two
runs is the repository-root checkout's branch. It is not superseded: `git log -S` over
`src/` shows the last changes to this module are #5100/#5108 (planning-lane crash, branch-name
keying) and #1413's original two commits (`aa330af93d`, `c1f5d38e72`); none addresses the
policy source.

## 2. The predicate (file:line)

`src/specify_cli/git/sparse_checkout.py`:

- `_load_managed_lane_policies(repo_root)` (l.336-380) globs `repo_root/kitty-specs/*/meta.json`
  and builds one `_ManagedLanePolicy` per Mission that declares a `coordination_branch`,
  a `mission_slug` and a `mission_id` of ≥ 8 chars. **This is the branch-dependent step**:
  `kitty-specs/` in the repository-root checkout is whatever the current branch has.
- `_classify_worktree_state(...)` (l.400-431): with no candidate policy for the path the state
  is returned untouched, and `SparseCheckoutState`'s default kind is `LEGACY_USER` (l.75).
  `is_blocking` = `is_active and not is_managed_lane` (l.96-99) → true → `any_blocking` → the
  preflight raises.
- `require_no_sparse_checkout(...)` (l.454-481): the refusal text, the affected paths and the
  `doctor sparse-checkout --fix` remedy; consumed by
  `src/specify_cli/cli/commands/agent/workflow_executor.py:implement_sparse_checkout_preflight`
  (the `agent action implement` entry point), `src/specify_cli/consolidation/executor.py:849`
  and by `src/specify_cli/cli/commands/_sparse_checkout_doctor.py:run_sparse_checkout`.

Every *other* guard already reads branch-independent state: `git config core.sparseCheckout`
(at the path), the pattern file contents, `git worktree list --porcelain`, and the lane's own
`git branch --show-current`. `_load_managed_lane_policies` is the sole branch-dependent input.

## 3. Decisions

**D1 — Add a lane-local policy source; do not rewrite the classifier.** For a worktree under
`.worktrees/` whose directory name parses to `(mission_dir, lane_id)`, read
`<lane>/kitty-specs/<mission_dir>/meta.json` — the lane's own tree, pinned to the lane's branch
— and build the policy through the *same* constructor the repository-root path uses. Rationale:
this is the authority #1413 already trusts (`meta.json`), and it keeps `expected_patterns`
byte-identical instead of inventing a second pattern grammar.

**D2 — Consult the lane-local source only when the repository-root source produced no candidate
for that path.** `_classify_worktree_state` treats *more than one* candidate policy as
`UNKNOWN` (l.405-406). Adding an identical second policy for the common case (branch contains
the Mission) would flip a correct `MANAGED_LANE` verdict into `UNKNOWN`. Ordering the sources and
de-duplicating per path preserves today's verdicts exactly.

**D3 — Same gating on the new evidence.** The lane-local `meta.json` passes through the identical
predicate (non-empty `coordination_branch` string, `mission_slug`, `mission_id` ≥ 8). A Mission
without coordination topology therefore cannot become "managed" by this change.

**D4 — Fail closed, silently.** A missing or unreadable lane-local `meta.json`, or a directory
name that does not parse as a lane worktree, yields no policy → the pre-#6844 verdict
(`UNKNOWN`/blocking) and the documented `--allow-sparse-checkout` escape. No new exception
path escapes `scan_repo` (it is also called from `warn_if_sparse_once`, which must never break
the calling command).

**D5 — Cost: one `meta.json` read per lane worktree, not a corpus scan.** The alternative
(glob `kitty-specs/*/meta.json` inside every lane worktree) would read ~660 files per lane on
this repository (a lane branch carries the whole corpus), on a path that runs before every
`implement`/`merge`/`consolidate`. The directory name already names the Mission, so the read is
targeted.

**D6 — The doctor surface needs no code change.** `_sparse_checkout_doctor.run_sparse_checkout`
and the remediation plan both filter on `is_blocking`, so a corrected classification also stops
`doctor sparse-checkout --fix` from offering to disable a managed lane (the second-order harm
the issue names). It gets a pinning test rather than new mechanism.

## 4. Rejected alternatives

- **Classify purely from the directory name's shape** (issue's second suggestion): the managed
  pattern set is `lane_sparse_checkout_patterns(mission_dir, mid8)`, and the directory name does
  not reliably carry a separable `mid8` for legacy `NNN-` slugs. Reconstructing it from the name
  alone would risk a *second* pattern grammar and could classify a hand-made look-alike worktree
  as managed without any Mission record behind it. Reading the lane's own `meta.json` keeps one
  grammar and one authority.
- **Read `meta.json` from the coordination branch via `git show`**: more subprocesses, and the
  lane's checked-out tree is the same content for the same commit; `load_meta` (the existing
  validator) reads from disk.
- **Drop the repository-root policy source entirely**: unnecessary risk — it is the twin of
  this one and the `read` ordering (D2) makes it harmless.

## 5. Open questions

- None blocking. The advisory review asked for the boundary that a lane with no `meta.json`
  anywhere in its own tree stays blocking (fail closed); that is now an explicit test rather
  than an accident.
