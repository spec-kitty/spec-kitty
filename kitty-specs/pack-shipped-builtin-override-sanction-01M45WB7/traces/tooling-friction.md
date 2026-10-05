# Tooling friction: pack-shipped-builtin-override-sanction-01M45WB7

Tooling this mission touches: `spec-kitty doctor doctrine`, `doctrine fetch`, `doctrine pack validate` / `pack assemble`, the GitHub REST API (no GraphQL or search), and a shallow clone.

- 2026-10-05: The clone is shallow (51 commits), so `git log -S` and `git log --grep` return nothing. History had to be traced through the REST commits API.
- 2026-10-05: `spec-commit` refuses a directory argument (`decisions/`). Every file has to be listed explicitly.
- 2026-10-05: The session-level `spawn_task` tool was unavailable. The two pre-existing gaps found by the squad were filed as #5769 and #5770 instead.
- 2026-10-05: spec-kitty commits status, issue-matrix and `spec-commit` changes with `git -c commit.gpgsign=false` (`src/specify_cli/git/commit_helpers.py:869`, `lanes/consolidation.py:825,994`). In a signing-required environment, about 40 mission commits came out unsigned, and they have to be re-signed at closeout.
- 2026-10-05: Running tests from a scratch worktree outside the repo gives false reds. `test_doctrine_asset` expects the internal pack at the worktree root, but config resolves it to the main checkout. `test_interview_mapping_mission_alias` shells out to `uv run --no-sync`, which needs a `.venv` inside the worktree. Both pass in the main checkout.
- 2026-10-05: A lane worktree imports the main checkout's `src/` through the shared editable venv unless `PYTHONPATH=$PWD/src` is set. Every implementer had to be told this.
