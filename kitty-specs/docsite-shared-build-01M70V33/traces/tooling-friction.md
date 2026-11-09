# Tooling friction trace: docsite-shared-build-01M70V33

Append-only, newest last.

- 2026-11-09 — **CLI commits are unsigned.** Every commit the `spec-kitty` CLI makes itself (create scaffold, `spec-commit`, `finalize-tasks`, status transitions, `safe-commit`, `record-analysis`, Op records) carries no signature although the repository config has `commit.gpgsign=true`; only direct `git commit` calls were signed. GitHub shows them Unverified. Workaround: the landing branch was compacted into signed commits. Candidate gap: the CLI's git invocation should honour `commit.gpgsign`.
- 2026-11-09 — `move-task` and `agent action review` leave the trailing annotation event and `review-cycle-N.md` / `review-feedback-N.md` uncommitted ("--no-auto-commit" printed without the flag being passed); each had to be committed by hand with `safe-commit`.
- 2026-11-09 — Re-claiming a rejected WP with `agent action implement` resets its subtasks to undone, so the next `move-task --to for_review` refuses until `mark-status` is run again.
- 2026-11-09 — `move-task --to approved` refused while issue-matrix rows auto-created for context citations (#6932, #6936, #6938) were `unknown` (same as docsite-scaffold-01M6DGT1).
- 2026-11-09 — `make docs-site-bump` behind this sandbox's proxy wrote the SSH form of the doc-kitty lockfile entry again (#7480); `test_the_lockfile_fetches_doc_kitty_over_https_with_no_ssh_key` caught it, as the earlier trace predicted.
- 2026-11-09 — pytest's default traceback rendering on a failing test that holds the parsed ci-router YAML took minutes (looked like a hang); `--tb=line` made the red run take 4 s.
- 2026-11-09 — Environment: service-pin tests in `tests/ci` need `make sync-services ARGS=--extras-only` (11 reds before); `tests/cross_cutting/packaging/test_package_bundling.py::test_wheel_bundles_templates_correctly` errored under `-n auto` and passed alone.
