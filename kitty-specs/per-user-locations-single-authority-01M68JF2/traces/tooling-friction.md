# Tooling friction

- `spec-kitty specify` was run before a topic branch existed, which left the mission's
  `target_branch` on protected `main`; `spec-commit` then refused. The documented remedy
  (`mission create <slug> --start-branch ...`) minted a *second* mission instead of
  retargeting the first, so the first scaffold was removed (nothing had been committed to
  it) and the authored spec/research were moved to the new mission `01M68JF2`. Reported in
  the PR's `## Deferred` as a tooling observation, not fixed here.
