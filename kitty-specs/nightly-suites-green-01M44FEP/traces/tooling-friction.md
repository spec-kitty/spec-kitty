# Tooling friction: nightly-suites-green-01M44FEP

Running log of tool and process friction. Append dated entries of one to three sentences at the moment they occur; assess at mission close.

## Tooling this mission touches

- `spec-kitty` planning and lane commands (`agent mission finalize-tasks`, `agent action implement`, `agent tasks move-task`, `consolidate`), run from the repository root checkout; product behaviour in a lane worktree is exercised with `PYTHONPATH=$(pwd)/src` and the repository root checkout's `.venv`, never the global binary.
- pytest with named files only, at most `-n 4`; the `performance` lane needs `SPEC_KITTY_RUN_PERFORMANCE=1` and `-n0`.
- CI job selection through `scripts/ci/gate_selection.py` (`select_gates`, `select_modules`); no workflow or registry edit.
- Docs tooling for the closing work package: `scripts/docs/freshen_adr_inventory.py`, `scripts/docs/docs_index.py --write`, `scripts/docs/check_docs_freshness.py --ci`, `scripts/docs/check_changelog_style.py`.
- CodeGraph for reading seams before writing guidance.

## Entries

- 2026-10-05 (tasks): The canonical tasks step ships in two shapes: the combined `tasks/prompt.md` (author `tasks.md` by hand) and the split `tasks-outline` / `tasks-packages` / `tasks-finalize` steps (author `wps.yaml`, `tasks.md` is generated). The tasks phase here followed the combined step; `finalize-tasks` reported `tasks_md_stale: false` and accepted it.
- 2026-10-05 (tasks): `finalize-tasks` leaves `agent_profile`, `role`, `agent` and `model` empty, so they are set by hand afterwards and committed separately with `spec-commit`.
- 2026-10-05 (tasks): Several line numbers in `research/code-grounding.md` point at an inner statement, not the `def` line, and four had drifted (`coord_seed.py` `_run_merge_and_commit` 751 not 783, `establish_coord_write_location` 1107 not 1220; `resolution.py` `write_dir` 2426 not 2499; `entry_preflight._resolve_run_status_dir` 433 not 452). The work-package prompts cite re-verified lines.
- 2026-10-05 (tasks): A `planning_artifact` work package (WP08) that depends on code lanes is placed on `lane-planning`; whether its checkout holds the dependency lanes' content before consolidation is unverified and is flagged in the WP08 prompt as a stop-and-report precondition.
- 2026-10-05 (implement): `spec-kitty implement` stamps the work-package frontmatter and `meta.json`; the next `implement` refuses until that is committed, so each allocation needs its own `spec-commit`.
- 2026-10-05 (implement): approval is refused while any cited issue has no issue-matrix row. A planning amendment that cites a new issue (here #2934) blocks an unrelated work package's approval until the row exists.
- 2026-10-05 (implement): any edit to `spec.md`, `plan.md` or `tasks.md` after `record-analysis` makes the analysis report stale and `implement` refuses; the report had to be re-recorded three times.
- 2026-10-05 (implement): `record-analysis`, `accept` and `consolidate` refuse on unrelated untracked files in the checkout (other missions' matrices, local config). Worked around by listing them in `.git/info/exclude` for the duration of the command.
- 2026-10-05 (implement): a `planning_artifact` work package that depends on code lanes never sees their content; WP08 had to become a `code_change` package in its own lane.
- 2026-10-05 (implement): zsh does not word-split a plain variable, so `ruff $FILES` fails with E902; three implementers hit this. `pkill -f` also matched an implementer's own shell twice.
- 2026-10-05 (implement): the first pytest run in a fresh worktree builds a test venv (35 to 50 s per worker), which dominates short named-file runs.
- 2026-10-05 (closeout): `accept` blocks on a missing `contracts/` directory even when the plan states the mission has none; `--lenient` was needed.
- 2026-10-05 (closeout): `consolidate` refuses when ANOTHER mission's lane worktrees use legacy sparse checkout; `--allow-sparse-checkout` was needed although this mission's lanes were not sparse.
- 2026-10-05 (closeout): the mainline moved 137 commits during the run and closed one of the mission's issues with a minimal fix; the history rebuild hit three conflicts (a moved test file, the ADR index, the changelog) and one test that pinned wording the mainline had reworded.
