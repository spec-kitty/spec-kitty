# Design decisions

- **Branch, not checkout.** The verdict compares the invoking checkout's branch with the
  seam's write ref, not the checkout path with `write_dir(...).surface_root`. A settled
  Mission whose coordination worktree was removed then reports the honest `false`. This is
  the residual the #7633 comment records for the earlier attempt.
- **Settled Mission, repository root checkout: `false`.** After settlement, the planning
  partition still writes to the topic branch held by the coordination worktree. Both
  commands report `false` from the root checkout and `true` from the coordination worktree.
  This is the honest seam answer. It means re-running the tasks step from the root checkout
  after settlement stops, naming the topic branch.
- **Owned runs keep the fact.** No git read is added: the pinned owned git-call budget
  (`test_owned_checkout_git_calls.py`) is unchanged.
- **Cross-repository invocation.** When the invoking checkout belongs to another
  repository than the located project root, the project root's HEAD is used, as in the
  `branch-context` command.
- **Fixture realism.** `test_setup_plan_branch_match.py`'s seed now records
  `topology: single_branch` beside a minted `mission_branch`, as `agent mission create`
  always does (#5100 WP08). Asserted expectations are unchanged.
