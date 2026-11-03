# Discovery — #6957: the migrate group-flag acceptance module must own its git-discovery ceiling

**Mission**: `migrate-group-flags-test-own-git-ceiling-01M6EKQH`
**Issue**: spec-kitty/spec-kitty#6957
**Grounded on**: `origin/main` @ `9aed3a8012` (2026-11-02), clone `<worktree>`
**Host shape**: this VM has a stray `<tmp>/.git` (a repository enclosing the platform temp root) —
exactly the host shape the issue and #7022 describe.

## Decisions

### D1 — The mission is a test-isolation fix, not a product fix

Evidence:

- `uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q` on `origin/main` @ `9aed3a8012`
  → **76 passed in 143 s**. The issue's headline red does not reproduce with the harness as it stands
  today.
- It is masked, not cured, in this module. `tests/conftest.py:294` calls
  `install_git_ceilings(harness_git_ceilings(config, _worker_home_base(config)), os.environ)`, which
  puts the run basetemp in `GIT_CEILING_DIRECTORIES` (landed by `de5ea7a87d` for #7022/#5356 on
  2026-11-01 23:54Z — after the issue was filed 2026-10-31 22:27Z).
- In-process probe on `origin/main` (a throwaway test that clears `GIT_CEILING_DIRECTORIES` and runs
  the module's positive control) reproduces the reported failure **verbatim**:

  ```
  _flip_phase refuses to write status_phase for '042-demo': the placement port resolved its
  PRIMARY home to /tmp/kitty-specs/042-demo, which does not match the write target
  /tmp/spec-kitty-pytest-tmp/run-667151/test_positive_control_without_0/kitty-specs/042-demo
  (fail-closed, FR-001).
  ```

  So the module's greenness depends on one process-wide environment variable it does not set.
- Root cause chain (production code is correct and unchanged): the module poisons
  `specify_cli.cli.commands.migrate_cmd.locate_project_root` but nothing pins the *root walk*.
  `runtime_state_cutover._resolve_primary_home_or_degrade` calls `core.paths.resolve_canonical_root`,
  which ascends from the fixture to the first ancestor holding `.git` — here `/tmp` — and
  `resolve_artifact_surface` then reports `/tmp/kitty-specs/042-demo`, which `_flip_phase` refuses
  against the real write target. That refusal is the documented fail-close (FR-001) and is correct.

Decision: scope is **tests only** — pin the module's own ceiling in its autouse isolation fixture, the
way `tests/specify_cli/migration/test_runtime_state_cutover_placement.py:41` already does, and the way
`tests/_support/git_ceiling.py`'s docstring prescribes ("such a test sets the variable itself").

Rejected alternatives:

- *Edit `tests/conftest.py` / `tests/_support/git_ceiling.py`* — they are correct and already do the
  right thing harness-wide; a second change there widens blast radius (`pyproject`/conftest are
  cross-cutting) for no gain.
- *Change `resolve_canonical_root` or `_flip_phase`* — the fail-close is the safety property under
  test; weakening it would be green-washing a real placement mismatch (C-001, C-002).
- *Delete or xfail the positive control* — forbidden (no gate weakening).

### D2 — The ceiling must be appended, not assigned

`git_ceiling_dirs()` parses `GIT_CEILING_DIRECTORIES` as a `os.pathsep` list and `install_git_ceilings`
documents that an existing value is kept verbatim (a leading empty entry is meaningful to git). The
module fixture therefore appends `tmp_path` to whatever the harness installed, via `monkeypatch.setenv`
so teardown restores it (NFR-002). A repository created *inside* `tmp_path` stays discoverable because
it is below the ceiling (FR-005).

### D3 — Red-first shape

Two guards, because one of them is host-shape dependent:

1. **Standing invariant (always on, non-vacuous on every host)**: after the autouse fixture runs,
   `core.paths.git_ceiling_dirs()` contains the test's `tmp_path`. Red today on CI too — fails without
   the fixture change. Mirrors the repo's existing idiom
   (`tests/_support/test_git_ceiling.py::test_this_session_has_its_basetemp_as_a_ceiling`).
2. **Behavioural probe through the production entry point (host-shape dependent)**: with
   `GIT_CEILING_DIRECTORIES` cleared, the non-dry-run positive control must still flip
   `status_phase` (`_invoke(["backfill-runtime-state", "--json"])`, the real CLI seam). Red today on
   any host whose temp root is inside a repository; where there is no enclosing repository the probe
   **skips** with a reason instead of passing vacuously (acceptance-criteria-non-vacuity).

## Evidence

| Claim | How it was established |
| --- | --- |
| Module green on main | `uv run --frozen pytest tests/cli/test_migrate_group_flags_4964.py -q` → 76 passed |
| Red reproduces in-module without the harness ceiling | throwaway probe test clearing `GIT_CEILING_DIRECTORIES` → the issue's error string, byte for byte |
| Red reproduces at the reporter's commit `c5747c2c21` | worktree at that commit + `make sync-packs`, `pytest tests/cli/test_migrate_group_flags_4964.py` → 1 failed, 75 passed (the reported test) |
| `<tmp>/.git` is the enclosing repository | `ls -la <tmp>/.git` → directory; `resolve_canonical_root(<fixture>)` → `/tmp` |
| The resolver honours ceilings | `resolve_canonical_root` + `git_ceiling_dirs()` in `src/specify_cli/core/paths.py`; `#7022` commits `090d3b2000`, `59f82c860e` |
| The sibling module already pins its own ceiling | `tests/specify_cli/migration/test_runtime_state_cutover_placement.py:41` |

## Open questions

None blocking. For the reviewer:

- OQ-1 (not this mission): should the harness treat a stray `<tempdir>/.git` as an error? It is the
  host shape that produced #7022 and #5356; the harness ceiling is the accepted cure, and this module
  now pins its own. No new issue is warranted unless a maintainer wants that check.
