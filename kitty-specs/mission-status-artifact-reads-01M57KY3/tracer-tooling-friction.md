# Tracer: tooling friction

Append during implementation; assess at close.

- 2026-10-18: The Gradle tests need `LC_ALL=C.UTF-8` in a container whose default locale is POSIX. Without it, two baseline
  tests (`ListingTest`, `FilesystemMissionEventSourceTest`) fail with `InvalidPathException` on non-ASCII names. This comes
  from the environment, not the code.
- 2026-10-18: The JDK 25 toolchain is not auto-provisioned (there is no foojay resolver). A local run needs GraalVM CE
  25.0.2 on `JAVA_HOME`, as CI pins. The contract bundle has to be built first and passed through `CONTRACT_BUNDLE` and
  `CONTRACT_BUNDLE_SHA256`.
- 2026-10-18: `spec-kitty agent mission create --pr-bound --json` refuses without `--branch-strategy already-confirmed`.
- 2026-10-18 (incident, cause not found): while `spec-kitty agent tasks move-task WP01 --to for_review` ran its pre-review
  regression gate (`make test-fast` in the repository root checkout of this `single_branch` Mission) and a Gradle `test` run
  went on alongside it, three working-tree files disappeared. They were one tracked, modified test
  (`OutOfScopeRoutesTest.java`, left as deleted) and two untracked new files (`ArtifactQueryServiceTest.java` and
  `tests/contract/_mission_status_artifact_goldens.py`). Their directory was last modified at 14:13:27 UTC, the minute the gate
  hit its 300 s timeout ("Pre-review regression gate timed_out; transition not applied"). Other untracked files in the same
  directories survived. No Gradle test touches the original tree (the nested-build tests work on copies). All three files were
  recreated from this session's own content. Mitigation used afterwards: commit everything before any `move-task`, and run
  nothing else alongside the gate. Reported to the operator in the PR for triage.
- 2026-10-18: the pre-review gate's `make test-fast` timed out at 300 s while the Gradle suite shared the machine, so the
  transition was not applied.
- 2026-10-18: commits made through spec-kitty (`safe-commit`, `spec-commit`, and the auto-commits of `implement`,
  `move-task`, `issue-verdict` and `review`) carry no signature, although the environment sets `commit.gpgsign=true`; a plain
  `git commit` signs. The branch was re-signed with
  `git rebase --exec "git commit --amend --no-edit --reset-author" origin/main` before the PR.
- 2026-10-18: committing WP02–WP04's code inside WP01's claim window (a single_branch Mission, implemented in one pass) left
  their claims with no implementation commit. Their `for_review` moves were forced, with the commit SHAs in the note
  (operator decision).
- 2026-10-18: actor recording is inconsistent across write paths (bare string against structured, role missing, profile
  always null). Filed as #6400.
