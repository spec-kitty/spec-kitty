# WP02 review feedback (cycle 1) — reviewer-renata

## Issue 1 (blocking): the reuse guard also fires on a checkout-root (planning) lane

`_reenter_self_heal` refuses whenever `request.base is not None`. `_ensure_workspace_materialized`
calls that closure whenever `workspace.exists` is true — which includes a **`repo_root` /
`owned_checkout` resolution** (`ResolvedWorkspace.runs_in_checkout_root`), i.e. every planning WP
and every single_branch repo-root code WP. For those the top-level `spec-kitty implement --base`
does *not* refuse: `_resolve_effective_base` prints `--base is ignored for repository-root planning
work` and proceeds (`implement_phases.py`, FR-007). So the new option changes a long-standing
"warn and proceed" into a hard refusal on exactly the surface where `--base` is meaningless —
a regression in the class #2017 catalogues (a guard that blocks a legitimate action), and it
breaks the C-003 parity the spec asked for.

**Fix**: scope the refusal to a real lane worktree (`not workspace.runs_in_checkout_root`) and, on a
checkout-root resolution, print the same "ignored" line the top-level command prints so an operator
passing `--base` there still learns why it did nothing. Pin both: a checkout-root workspace plus
`--base` must NOT produce the refusal and MUST produce the ignored-warning, while the existing
lane-workspace test still pins the refusal.

## Nit 1 (non-blocking, fixed in the same commit): the refusal prints two lines

`print(f"Error: {UnhonorableBaseError(...)}")` followed by a separate remedy line duplicates what
`Error:` readers grep for. Acceptable as-is once the "Drop --base to resume" sentence is kept —
reviewer has no objection to the two-line shape.

## Verified OK (no change requested)

- `--base` is carried unresolved: the option is added to the Typer surface, stored on
  `ImplementRequest`, and passed unchanged into `top_level_implement(...)`; `implement.py`'s
  `_resolve_effective_base` remains the single validator (no second authority).
- `base=None` is the default on `ImplementRequest`, so no other constructor breaks; the two
  `test_wrapper_delegation` expectations were updated to pin the widened contract (base=None),
  which is the correct way to record a widened delegation contract.
- Red-first is real: 3 of the 4 new tests failed with Typer exit 2 / `No such option: --base`
  before the option existed, and the fourth is the same-fixture "absent --base carries None"
  control that proves the capture observes both arms.
- Help-surface test normalises the rich box border before matching, so it is not pinned to a
  terminal width.
- Suites: `tests/specify_cli/cli/commands/agent` + `tests/agent` → 4271 passed, 33 skipped,
  2 xfailed, and 0 failures after the `test_wrapper_delegation` update (re-run scoped to
  that file: 5 passed).
- The allocator keeps every refusal (reuse / crash recovery / dependency lane / detached base):
  this WP only feeds it the operator's value.
