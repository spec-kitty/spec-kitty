# Contract: the stale lane-base report (#6753)

**Status**: implemented by this Mission (WP01, WP02).
**Owner surface**: `specify_cli.lanes.worktree_allocator._stale_base_warning`,
`specify_cli.cli.commands.agent.workflow.implement` (`--base`).

The contract three callers depend on — the CLI, the orchestrator API and an agent
reading its own output — stated so a later change to any of them is a contract
change, not a refactor.

## 1. The probe

At a **fresh** coordination-topology lane allocation, and only there, the allocator
answers one question: *does the ref this lane is about to be cut from contain the
target branch tip?*

| Inputs | Answer | Effect |
| --- | --- | --- |
| `parent_ref` contains `target_tip` | **current** | nothing is printed |
| `parent_ref` does not contain `target_tip` | **stale** | one report is printed |
| `target_tip` is unresolvable (`capture_branch_tip` returned `None`) | **unknown** | nothing is printed |
| `git merge-base --is-ancestor` exits ≥ 2, times out (10 s) or raises `OSError` | **unknown** | nothing is printed |
| any non-fresh route (reuse, crash recovery, legacy topology, repository-root planning lane) | not asked | no probe, no subprocess |

`unknown` is never treated as `current`: an unanswerable probe neither invents a
warning nor issues a clean bill of health, and it never changes the allocation's
outcome.

## 2. The report

Exactly one line, on **stderr**, carrying all four of:

1. the ref the lane is actually cut from (`decision.parent_ref`, which may be an
   explicit `--base`, an `origin/<branch>` ref, or the coordination branch);
2. the target branch name;
3. the first 8 characters of the target tip the base does not contain;
4. a runnable remedy carrying the work-package id:
   `spec-kitty agent action implement <WP> --agent <name> --base <target>`.

It cites `(#6753)`. It is a report: the allocator never re-parents, merges,
rebases, fast-forwards or refuses because of it.

**Why stderr, not stdout**: `spec-kitty implement --json` keeps stdout for its
machine-readable payload, and `_json_safe_output` captures only the rich console.
A stdout report here would prepend a line to that payload on the common stale-coord
cut. The template spec's C-004 was amended accordingly.

## 3. Parentage (unchanged, asserted)

A fresh lane with no explicit `base` still parents on the coordination branch —
`_resolve_lane_parent` is untouched. The report describes that decision; it never
replaces it. A lane re-cut from the target tip requires an explicit `--base`.

## 4. The remedy's reachability

`spec-kitty agent action implement <WP> --base <ref>` accepts the explicit base the
internal `spec-kitty implement --base` accepts, and carries it, unresolved, to the
same allocator seam. The honour/refuse decisions stay in
`resolve_lane_base_or_refuse`:

| Route | `--base` supplied |
| --- | --- |
| fresh, no dependency lane, base shares ancestry with the recorded planning commit | honoured (base alone replaces the topology parent) |
| lane worktree already exists | refused: `UnhonorableBaseError(route="reuse")`, plus the discard-and-re-cut step |
| branch exists, worktree gone (crash recovery) | refused: `route="crash_recovery"` |
| lane has `depends_on_lanes` | refused: `route="dependency_lane"` |
| base shares no ancestor with the planning commit | refused: `route="detached_base"` |
| repository-root / owned-checkout resolution | ignored with a warning, and the run proceeds |

No route accepts `--base` and then silently drops it.
