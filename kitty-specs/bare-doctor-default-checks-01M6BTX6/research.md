# Discovery — bare `spec-kitty doctor` default run (#6969)

Captured before `specify`/`plan`. Facts, decisions and open questions gathered from the
issue, the code and the history of the guard it reverses.

## Evidence

- **Reproduced on current `main`** (`4.0.0rc8`, this clone, 2026-11-01):
  `spec-kitty doctor` prints the full group help, then
  `Error: no diagnostic ran. ...` on stderr, and exits **2**. The subcommands
  (`doctor command-files`, `doctor state-roots`, `doctor ops`) all run and exit 0 in
  this project.
- **The guard is deliberate, not an accident.** `git log -S "no diagnostic ran"` finds
  exactly one commit, `6743b5c78d` ("fix(doctor): exit 2 on a bare `spec-kitty doctor`
  instead of reading as a passing check", #4678). Its changelog entry
  (`docs/changelog/CHANGELOG.md` line 889) states the rationale: exit 0 with no
  diagnostic executed reads as a passing health check.
- **Not superseded.** No later commit touches `_doctor_group`; issue #6969 is the
  maintainer decision to reverse #4678's remedy — run real diagnostics instead of
  refusing.
- **The primitives already exist and are pure.** Each default check has a data-returning
  function behind the printing subcommand, so a default run can aggregate them without
  shelling out, capturing stdout, or re-implementing a check:
  - `specify_cli.runtime.doctor.check_command_file_health(project_path) -> list[dict[str, str]]`
    (empty list = healthy; `doctor command-files` renders the list and exits 1 when non-empty).
  - `specify_cli.state.doctor.check_state_roots(repo_root) -> StateRootsReport`
    (`.healthy` bool; `doctor state-roots` exits 0/1 from it).
  - `specify_cli.doctor.ops.list_orphan_ops(repo_root) -> list[Path]`
    (empty list = healthy; `doctor ops` exits 0/1 from it).
- **`doctor.py` is a shim by doctrine.** The module header (#2059) forbids new
  responsibilities there: new subcommand logic belongs in a `_*_doctor` sibling. The
  `@app.callback` shell has to stay in `doctor.py`, so only the delegation belongs there.
- **The group help string is recorded in `docs/api/cli-commands.md`**, and
  `scripts/docs/check_cli_reference_freshness.py` reports `HELP-DRIFT` when the recorded
  summary/help body differs from live. Changing the help string therefore requires a
  targeted edit of that one section (not a full regeneration — the repo's guidance is to
  regenerate only the surface the diff changes).
- **Existing tests that pin the current guard** (all must be updated, not deleted):
  - `tests/cli/test_top_level_group_empty_invocation.py::test_empty_doctor_invocation_is_not_a_passing_check`
    (asserts exit 2 and "no diagnostic ran").
  - `tests/architectural/test_cli_placeholder_output.py`
    (`CALLBACK_PATHS` includes `doctor`; the parametrised callback test runs the bare
    invocation in a `tmp_path` and asserts non-empty output and no Typer reprs).

## Decisions

1. **Default set = `command-files`, `state-roots`, `ops`.** The issue names these three
   and says "topology/identity where cheap". `identity`/`topology` walk every mission in
   `kitty-specs/` (≈690 here), so they are not cheap enough to run on every bare
   invocation; they keep their explicit subcommands. This keeps NFR-001 honest.
2. **Exit codes: 0 healthy, 1 any finding, and 1 for not-in-project.** Never 2. Exit 2
   was exactly what made wrappers read the command as a usage error; the default run has
   a definite verdict, so it uses the ordinary health codes its subcommands already use.
3. **Aggregate over the data primitives, not over the subcommands.** Each check returns
   its findings as data; the default run renders one line per check. This avoids
   capturing Rich output, avoids duplicating check logic, and makes a failing check
   catchable per-check (FR-005).
4. **A raising check is a finding, not a crash.** Each check is wrapped; the exception
   message becomes that check's finding line and the run continues (FR-005).
5. **New module `_default_run_doctor.py`** with a data table of checks and a `run(...)`
   entry point; `doctor.py`'s `@app.callback` resolves the project root and delegates.
   This respects the #2059 shim rule (C-001).
6. **No group-level `--json` in this Mission.** The issue's automation motivation is the
   exit code, and every subcommand already offers `--json` for the detail. Adding a
   group-level JSON envelope would widen the contract beyond what the issue asks for;
   recorded as a possible follow-up, not built here (smallest-viable-diff tactic).

## Open questions

- None blocking. The one judgement call — whether `skills` or `identity` belong in the
  default set — is settled by the cost rule above (they do not) and recorded in
  Decisions 1.
