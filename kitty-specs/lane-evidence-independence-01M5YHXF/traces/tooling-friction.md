# Tooling friction

Tooling this mission touches: `spec-kitty` CLI (move-task, accept, consolidate, orchestrator-api), git, pytest, Cucumber-JVM on JDK 25 (`acceptance-jvm/`).

- **[2026-10-27][setup] Cloud image has JDK 21; acceptance-jvm needs 25.** Installed Temurin 25 per `acceptance-jvm/README.md`; `cloud-session-setup.sh` only writes env when `CLAUDE_ENV_FILE` is set, so it was pointed at a scratchpad env file and sourced. Workaround.
- **[2026-10-27][specify] `mission create` on a topic branch resolved to `coord`, not `lanes`.** Matches the documented caveat (no `origin/HEAD` locally); fine here since coord is the bug's topology. No action.
- **[2026-10-27][tasks] `finalize-tasks` failed twice with `.git/index.lock: File exists` on the first run after a file edit; no other git process was running and the retry succeeded.** Looks like a race inside the command's own git calls. Candidate gap: file once reproduced.
- **[2026-10-27][tasks] Re-running `finalize-tasks` keeps existing frontmatter `dependencies`; a fix to the `Depends on` prose in tasks.md is ignored.** Edited the WP frontmatter instead. Candidate gap (docs say dependencies are parsed from tasks.md).
- **[2026-10-27][implement] With auto-commit off, review verdicts and claim metadata are written but not committed.** Each move left `status.events.jsonl`/`status.json`/`review-cycle-N.md` dirty in the coordination worktree and claim metadata staged in the root checkout; the orchestrator committed them by hand. Workaround.
- **[2026-10-27][implement] The first WP01 implementer reported all suites green while two of its own new tests failed.** It had not re-run a file after changing its fixture. Disposition: the orchestrator now reruns the claimed files before every review.
