# Tasks: Op record auto-commit skips repos that do not track kitty-ops

Mission: `op-record-commit-skip-untracked-01M57Z15` · Branch: `issue-6410-op-record-commit-target` (plans and lands here; it reaches `main` through a PR) · Topology: `single_branch` (WPs run in sequence in the write checkout)

## WP01 — Op commit policy and operator-facing reporting (code_change)

Prompt: [tasks/WP01-op-commit-policy.md](tasks/WP01-op-commit-policy.md) · Requirements: FR-001..FR-006, NFR-001, NFR-002, C-001, C-002

- T001 Red-first: issue-pinned `@pytest.mark.regression` repro. It runs `complete` through the CLI on an issue branch, in a repository whose `main` tracks no Op record, and asserts the branch's commit list is unchanged. It must be RED on the base.
- T002 Add `src/specify_cli/invocation/op_commit_policy.py`: unbiased primary refs, the ULID-record tracked probe, the `check-ignore --no-index` probe and the skip reason.
- T003 Wire it into `ProfileInvocationExecutor._commit_op_record` with a per-executor cache. Add `OpCommitOutcome.skipped`. A probe error becomes a skip.
- T004 Render it: the CLI `complete` skip line and a corrected refusal warning; the doctor sweep's `skipped:<reason>` value and the doctor human output; the `state/contract.py` note; the executor comment.
- T005 Tests: focused unit tests for the policy module, covering positive controls for every predicate, `trunk`-only origin-less, special files, stale local ref and the ignore of a tracked spine. Rework the existing executor, doctor and e2e fixtures to track one ULID record on `main`. Convert the regression repro into focused tests.

## WP02 — Docs and changelog (planning_artifact)

Prompt: [tasks/WP02-docs-changelog.md](tasks/WP02-docs-changelog.md) · Depends on WP01 · Requirements: FR-004, FR-005

- T006 `docs/architecture/trail-model.md`: describe the conditional commit and the skip, and state durability truthfully.
- T007 `docs/changelog/CHANGELOG.md` `[Unreleased]` → Fixed entry (#6410), impact-first, before → after.
