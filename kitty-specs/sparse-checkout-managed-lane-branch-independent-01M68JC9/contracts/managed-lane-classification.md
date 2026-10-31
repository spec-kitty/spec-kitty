# Contract: managed-lane classification and the sparse-checkout preflight

Scope: `src/specify_cli/git/sparse_checkout.py` — `scan_repo`, `require_no_sparse_checkout`,
`SparseCheckoutScanReport`, and the two consumers that decide on their output
(`implement_sparse_checkout_preflight`, `_sparse_checkout_doctor.run_sparse_checkout`).

This mission does not change any signature here. It changes **where one input is read from**, so
the contract below states the invariant the change must preserve, and the one property it must add.

## 1. Verdict vocabulary (unchanged)

| `sparse_checkout_kind` | `is_blocking` | Meaning |
|---|---|---|
| `MANAGED_LANE` | `false` | spec-kitty wrote this state itself (lane policy); never refuse, never remediate |
| `UNKNOWN` | `true` | a lane policy matched but a guard failed (wrong branch, pattern drift, not a registered worktree) |
| `LEGACY_USER` | `true` | default: state is active and no lane policy was found for it |

`is_active` is `git config core.sparseCheckout == true` at that path; `is_blocking` is
`is_active and not is_managed_lane`. A path with `is_active == false` is never blocking, whatever
its kind.

## 2. Managed-lane admission (unchanged)

A worktree is `MANAGED_LANE` only when **all** of the following hold:

1. `core.sparseCheckout` is `true` in that worktree;
2. exactly one candidate policy matches its directory name (recomposition via
   `lane_id_for_worktree_dir`, so `057-foobar-lane-a` is not `057-foo`'s);
3. the worktree is on `code_lane_branch_name(<mission_slug>, <lane_id>)` — never the planning
   lane, never a foreign branch;
4. git lists it as a registered worktree of the repository;
5. its pattern file exists and is a **superset** of
   `lane_sparse_checkout_patterns(<mission_slug>, <mid8>)`.

A policy exists for a Mission only when its `meta.json` carries a non-empty `coordination_branch`,
a non-empty `mission_slug`, and a `mission_id` of at least 8 characters. **Both** policy sources
(the repository-root checkout's `kitty-specs/`, and a lane worktree's own tree) go through the same
gate, so this contract is unchanged by the mission.

## 3. Policy source (added)

The candidate policy for a worktree at `<repo_root>/.worktrees/<dir>` is:

- the policies derived from `<repo_root>/kitty-specs/*/meta.json` **if one of them matches `<dir>`**;
- otherwise the policy derived from `<repo_root>/.worktrees/<dir>/kitty-specs/<mission-dir>/meta.json`,
  where `<mission-dir>` is the slug half of `<dir>`, joined with the root-derived policies only when
  no root-derived policy matched.

Consequences, each pinned by a test:

- the classification is a pure function of the lane worktree's own state and git's registration
  list — **not** of the repository-root checkout's current branch;
- the lane-local read happens only for a worktree whose `is_active` is true, and at most once per
  worktree;
- a lane whose own tree carries no readable `meta.json` (missing, malformed, or non-UTF-8) yields
  no policy and therefore the `LEGACY_USER` verdict (§1) — fail closed, never managed by shape
  alone;
- no read failure escapes `scan_repo`; `warn_if_sparse_once` may rely on that.

## 4. Preflight and remediation (unchanged)

`require_no_sparse_checkout` raises `SparseCheckoutPreflightError` iff `report.any_blocking`, with
the message, the `affected_paths` list, the `doctor sparse-checkout --fix` remedy and the
`--allow-sparse-checkout` hint unchanged. `--allow-sparse-checkout` logs the structured override
record and returns. `doctor sparse-checkout` and its `--fix` plan iterate the same `is_blocking`
predicate, so a `MANAGED_LANE` path is never reported and never offered for remediation.

## 5. Non-goals

- No change to `lane_sparse_checkout_patterns`, `register_lane_sparse_checkout`, the lane branch
  grammar, the lane allocator or the coordination topology.
- No new flag, config key, environment variable or dependency.
- No mutation of git configuration or sparse state anywhere in `scan_*`.
