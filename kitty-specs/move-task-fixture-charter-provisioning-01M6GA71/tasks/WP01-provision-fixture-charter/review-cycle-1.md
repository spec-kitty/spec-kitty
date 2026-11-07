# Review cycle 1 — WP01 (reviewer-renata)

Diff reviewed: lane `kitty/mission-move-task-fixture-charter-provisioning-01M6GA71-lane-a` @ `749564b742`
against `origin/main` @ `d18c4f1d58` (test module + changelog fragment only).

## Verdict: APPROVE

## What was checked

1. **Subject, not assertion.** `git diff origin/main...HEAD -- tests/tasks/test_move_task_git_validation_unit.py`
   is +50/-0: three imports, one provisioning call in `git_repo_with_worktree`, one appended test class. No
   existing assertion, node, decorator or marker is touched; `grep -nE "^\+.*(skip|xfail|pytest.mark|--force|deselect)"`
   over the diff returns nothing. `git diff origin/main..HEAD -- src/` is empty.
2. **Red first.** With the provisioning call replaced by `pass`, both new tests fail on the same HEAD:
   `test_fixture_mission_type_resolves_to_the_curated_profile` with
   `UnknownMissionTypeError: Unknown mission type 'software-dev'. No registered mission types are available.`
   (the issue's exact error) and `test_fixture_capability_read_does_not_fall_back` with the captured record
   `code_producing resolution failed for mission type 'software-dev'; using the built-in default`. Restored and
   re-run: both pass. The pin is therefore not no-op passable.
3. **Non-vacuity of the pin.** `code_producing_for` returns `True` both before and after the fix, so the boolean
   alone would be vacuous; the test asserts (a) the *resolved bundle* (`mission_type` plus a non-empty curated
   `action_sequence`, which a neutral/fallback bundle does not carry) and (b) the *absence* of the
   `charter.activation.mission_type_profiles` WARNING record, captured with `caplog.at_level(...)` on that
   logger. The red run proves the capture sees the record when it is emitted.
4. **Provisioning is the production one.** `provision_test_charter` is the documented thin wrapper over
   `specify_cli.provisioning.default_charter.provision_default_mission_type_activations`; no hand-written
   `mission_type_activations` key, no second seeder (C-003). It writes the activation ledger
   (`.kittify/charter/activation.yaml`), which is the fresh-project authority (ADR `2026-10-19-1`), not
   `config.yaml`.
5. **Commit shape preserved.** Provisioning runs after `.kittify/config.yaml` is written and before the fixture's
   `git add .` / `Initial commit`, so the ledger lands inside the first commit and no extra commit appears. The
   nodes that assert commit history and the `Add implementation` head subject behave exactly as on the base
   (verified below under item 7).
6. **No behaviour drift for the 15 existing nodes.** Base: 8 failed / 7 passed; branch: the *same* 8 nodes fail
   with the same `IMPLEMENTATION_MISSING` message (issues #7057 / PR #7100 own that gate refusal) and 9 pass.
   `--collect-only` reports 17 nodes (15 + the 2 new pins); no existing id changed.
7. **Independence from PR #7100.** Applying #7100's fixture re-pin (`owned_files`, owned lane commit, `--agent
   reviewer-renata`) on top of this branch and running the module gives **17 passed**, so the two changes are
   complementary rather than overlapping. `git apply` of #7100's hunks applies cleanly (no textual collision):
   this mission edits the `.kittify/config.yaml` write region and appends a class; #7100 edits the WP01
   frontmatter, the lane commit and one invocation's flags.
8. **Order independence.** A default (`pytest-randomly`) run reproduces the same 8 failed / 9 passed as
   `-p no:randomly`.
9. **Gates.** `ruff check` and `ruff format --check` clean; `mypy` reports the same 16 pre-existing
   `no-untyped-def` diagnostics on base and branch (0 new, and the new tests are annotated);
   `check_changelog_style` 0 errors (86 pre-existing warnings, none on the new fragment);
   `check_spelling --pass unreleased` 0 findings. `make test-fast` 2822 passed / 6 skipped.
10. **Blast radius.** `git grep -n "git_repo_with_worktree" -- tests` finds only this module and a private
    fixture of the same name in `tests/scripts/test_activate_isolated_env.py` (different helper).

## Findings

- None blocking.
- Non-blocking note (recorded, not actioned): the pin lives in `tests/tasks/`, an `out_of_matrix` directory, so
  no per-PR job runs it; the nightly shard is the automated backstop. This is the same coverage gap #7057's PR
  records as deferred, and closing it is a module-registry decision for the maintainers.

## Evidence commands

```
uv run --frozen --no-sync pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py
uv run --frozen --no-sync pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py -k TestFixtureCharterProvisioning
uv run --frozen --no-sync pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py   # + PR #7100 hunks applied
uv run --frozen --no-sync pytest -q -n0 tests/tasks/test_move_task_git_validation_unit.py                 # random order
uv run --frozen --no-sync pytest -q -p no:randomly -n0 tests/agent/test_review_validation_unit.py tests/specify_cli/cli/commands/test_init_provisioning.py tests/specify_cli/cli/commands/test_init_writes_ledger.py tests/charter/test_mission_type_activations_seed_read_parity.py tests/_factories/
make test-fast
```
