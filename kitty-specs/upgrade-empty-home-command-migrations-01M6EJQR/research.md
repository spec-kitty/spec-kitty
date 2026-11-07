# Discovery — upgrade: three migrations read the operator's home directly (#6954)

Mission: `upgrade-empty-home-command-migrations-01M6EJQR`
Date: 2026-11-02

## Issue being grounded

GitHub issue #6954 (labels `reliability`, `domain:upgrade`) asks for **one regression
test, not a speculative refactor**: converge a project, re-run `upgrade --project` with
`SPEC_KITTY_HOME` pointed at an empty directory, and assert no tracked change and no
auto-commit — the shape #6946 added for `0.6.7_ensure_missions` and
`0.12.0_documentation_mission`. If the test finds one of the three named migrations taking
a home-dependent path, fix it the way #6946 fixed the predicate: read the project's own
state first, and keep the home check only for shapes that genuinely have no project stamp.

Named sites in the issue:

| File | Line range in the issue | What actually reads the home |
| --- | --- | --- |
| `src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py` | 106–118 | `_get_runtime_command_templates_dir()` final fallback: `get_kittify_home() / "missions" / "software-dev" / "command-templates"` |
| `src/specify_cli/upgrade/migrations/m_2_1_4_enforce_command_file_state.py` | 146–156 | same helper, same fallback |
| `src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py` | 32–77 | `_global_runtime_present()` reads `get_kittify_home() / "missions"`; `_global_command_file_present()` reads `Path.home() / <agent_root> / <subdir> / <file>` |

## Grounding finding 1 — the issue's premise about #6946 does not hold on current `main`

`gh pr view 6946` reports `state: OPEN`, `mergedAt: null`; `gh issue view 6551` reports
`OPEN`; `tests/upgrade/test_upgrade_empty_home_noop.py` does not exist on `main`
(`git log --oneline -- src/specify_cli/upgrade/compat.py` shows no #6946 commit). So
`uses_centralized_runtime()` on `main` still gates on
`~/.kittify/cache/version.lock` **before** it reads `metadata.yaml`.

**Decision**: this mission stands alone. It does not wait for #6946, does not edit
`compat.py`, and does not create the file #6946 creates
(`tests/upgrade/test_upgrade_empty_home_noop.py`) — a separate module name avoids a
guaranteed conflict whichever lands first. The dependency is recorded in the PR's
`## Deferred` section.

## Grounding finding 2 — reproduction, measured

A copy of #6946's fixture (its own branch, run locally on `main`) reproduces the reported
defect at the real entry point: after converging a project with a bootstrapped home, an
un-bootstrapped home moves `HEAD`
(from the temporary reproduction base to its auto-commit; those throwaway SHAs were not
retained), and the auto-commit adds exactly the 23 files the
issue describes — the three packaged missions plus 2 ledger rows for
`0.6.7_ensure_missions` and `0.12.0_documentation_mission`. That is the #6551 path,
still unfixed here, and **not** one of the three sites this mission owns.

## Grounding finding 3 — on a converged project the three are never re-evaluated

Measured with a probe (all records `success` after convergence):

- `2.1.3_restore_prompt_commands` = `success`, `2.1.4_enforce_command_file_state` =
  `success`, `3.1.2_globalize_commands` = `success`.
- `success` settles a migration; only `skipped` is re-evaluated
  (`MigrationRegistry.get_applicable`, ADR `2026-10-17-1` §3). So on a genuinely converged
  project the ledger never calls `detect()` on any of the three, and the issue's test as
  literally specified cannot measure them.

**Decision**: the regression fixture seeds the three migrations as `skipped` — the state
in which the ledger *does* re-evaluate them — and keeps every other record `success`. That
is the measurement the issue asks for, without inventing a new ledger shape.

## Grounding finding 4 — which of the three is actually home-dependent

- **`m_2_1_3` / `m_2_1_4` — not home-dependent in observable behaviour.** Both resolve
  templates in this order: (1) `MissionTemplateRepository.default_missions_root() /
  "mission-steps" / "software-dev"` (packaged doctrine), (2) legacy packaged
  `command-templates`, (3) `~/.kittify/missions/…`. With an installed CLI the first tier
  matches, so the home is never consulted and the rendered files are identical. The
  correct response is a **pin**, not a refactor.
- **`m_3_1_2` — genuinely home-dependent.** `_classify()` returns `keep` when
  `_global_runtime_present()` is false, and `keep` when the exact global replacement is
  absent from `Path.home()`. Measured: a project stamped at the running CLI version,
  carrying one version-marked project-local command file and a `skipped` 3.1.2 record,
  keeps the file under a bootstrapped-but-not-populated home (records `success`, so the
  decision is frozen). Under an empty home the same project also keeps it — for a
  different reason, and with the reverse outcome available on a machine that does have
  the global tree. Same commit, two machines, two answers: exactly the ADR §3 breakage.
  `_global_command_file_present()` additionally re-derives the global command directory
  from `Path.home() / agent_root / subdir`, duplicating
  `specify_cli.runtime.agent_commands.get_global_command_dir()` — a second source of
  truth the canonical-sources rule forbids (it misses `opencode`, `llxprt` and `copilot`'s
  documented global roots).

## Decision — the fix shape

Make `_SafeGlobalizeCommandsBase` classify from the project's stamp first:

- a project stamped `>= self.target_version` is past the command-globalization boundary,
  so a **version-marked** project-local file is ours and removable without asking the
  home (the CLI installs the global copies at the next command);
- a project with no readable stamp, or one below the boundary, keeps today's home checks
  unchanged (legacy repair);
- the `hold` rule for files with no marker is untouched in both cases.

Trade-off accepted and to be stated in the changelog: on a machine that only ever runs
`upgrade`, the stamped path removes the project-local copies even though that machine has
no global copies *yet*; the next spec-kitty command recreates them.

## Open questions

- None blocking. Whether #6946's `compat.py` change lands before or after this PR only
  changes which of the two makes the *converged-project* assertion pass; both are needed
  for the issue's full ask and neither depends on the other's file.
