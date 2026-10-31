# Tooling friction tracer — project-intent-deny-rename-01M68J6A

## Seed

- Nothing yet. The mission touches `spec-kitty specify/plan/tasks`, the upgrade migration and the
  charter activation seam.

## Close

- **[2026-10-31][implement] `specify` from the primary branch picks `coord` topology.** The first
  mission had to be re-created with `--topology single_branch` for a one-file fix; the scaffold,
  coordination branch and worktree were removed before anything was committed.
- **[2026-10-31][implement] `finalize-tasks` rewrote the target branch to `main`.** The mission was
  created on `main` and the bootstrap wanted `main` as planning base even after the mission branch
  existed; `--target-branch <mission-branch>` pinned it. Renaming the branch before finalize made
  bookkeeping refuse (`DESTINATION_REF_NOT_FOUND`) -- do the pin, not the rename.
- **[2026-10-31][implement] The acceptance gate asked for a `contracts/` deliverable** this mission
  type scopes by default; `accept --lenient` records it as a warning, as intended for a fix with no
  contract surface.
- **[2026-10-31][implement] One local batch run of `tests/acceptance/test_persistent_deactivation.py`
  failed once and passed twice on identical input.** Candidate flake, not attributable to the diff;
  recorded in the PR's Deferred rather than skipped or pinned.
