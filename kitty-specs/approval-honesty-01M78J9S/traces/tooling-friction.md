# Tooling friction

Mission touches: `spec-kitty agent tasks move-task` (approval path), `review/cycle.py`, `agent action review`, `spec-kitty next` hints.

- **[2026-11-12][specify] `agent decision open` needs `--slot-key` even outside the interview.** Recording pre-spec operator rulings failed with `DECISION_MISSING_STEP_OR_SLOT` until a slot key was passed; the flag reads optional in `--help`. Workaround; candidate doc gap.
- **[2026-11-12][specify] `--pr-bound` on a non-primary fix branch asks for branch-strategy confirmation in `--json` mode.** The mission targets `fix/3044-approval-honesty` and the PR goes from there, so `--pr-bound` was dropped. Workaround.
- **[2026-11-12][research] Shallow clone (50 commits) hides history.** `git log -S` cannot show whether the git-user fallback was reintroduced after #4670; the conclusion rests on code reading. Disposition: noted as inference.
- [2026-11-12][WP01 implement] Mandated --reviewer help text change (T006) also requires the golden help fixture tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help (not in WP01 owned_files); updated it in WP01 since the contract test pins the help bytes.
