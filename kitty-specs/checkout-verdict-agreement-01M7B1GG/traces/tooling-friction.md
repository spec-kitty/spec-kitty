# Tooling friction

- `setup-plan` and `check-prerequisites` on this Mission showed the #7594 defect itself.
  From the repository root checkout on the minted topic branch, setup-plan reported
  `branch_matches_target: true` with the topic branch as `target_branch`;
  check-prerequisites reported `false`.
- `finalize-tasks` refuses a spec that declares a requirement ID for deferred scope
  (`unmapped_functional_requirements`). The slice-2 requirement had to move out of the FR
  table into a "Deferred scope" note until the Q8 ruling.
- `setup-plan` left its lifecycle events (`SpecifyCompleted`, `PlanStarted`) uncommitted in
  `status.events.jsonl` after scaffolding the plan template (related to #3933).
- The suggested commit trailer named a model; the brief forbids model names, so the
  first commit was amended before any push.
- `move-task --to for_review` skipped the pre-review regression gate with `no_coverage` on
  this `single_branch` Mission ("no changed files detected").
- `accept` refused on the software-dev `contracts/` path convention for a bugfix that has
  no contract artifact, so `--lenient` was needed.
- `consolidate` defaults to `squash`, which would fold the red-first test commit into the
  fix. `--strategy rebase` kept them apart. The post-fix bookkeeping (about 35 tool
  commits) was then compacted into one commit.
