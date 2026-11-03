# Discovery: test harness temp ceiling (#7076)

## Where this comes from

#7022 (PR #7058, merged) taught `pytest_configure` to list the run's basetemp and the worker's
isolated home in `GIT_CEILING_DIRECTORIES` (`tests/_support/git_ceiling.py`,
`tests/conftest.py:294`), and #7056 (PR #7082, **still open, not merged**) moved every root walk
in `src/` onto one ceiling-aware walker at `src/kernel/ancestor_walk.py`. #7076 is the harness
half #7056 deliberately left out (its `C-005`): the `TMPDIR` escape, the from-scratch child
environments, and the `stop=` decision.

## Reproduced on this host (current `main`, 2026-11-03)

A single probe test printed, inside a real `uv run pytest`:

```
GETTEMPDIR:   /tmp
MKDTEMP:      /tmp/tmp5jhtcy8a
BASETEMP:     /tmp/spec-kitty-pytest-tmp/run-2877447
CEILINGS:     /tmp/spec-kitty-pytest-tmp/run-2877447:/tmp/spec-kitty-test-homes/serial-2877447/master
tempfile.tempdir: /tmp
```

`tempfile`'s root is `/tmp`, which is **above** every listed ceiling, so nothing `tempfile`
creates is bounded by the harness at all — 59 test modules use it. This host is exactly the
hostile case the issue describes: `/tmp/.git` exists (left by parallel missions; it holds only
`hooks/` and `spec-kitty-locks/`, no `HEAD`), so any walk that accepts a bare `.git` directory
as a boundary answers differently inside a `tempfile` directory than it would in a clean tree.

## Census of the code touched

| Surface | Count | Note |
| --- | --- | --- |
| `tempfile.TemporaryDirectory` / `mkdtemp` / `NamedTemporaryFile` users | 59 modules | all escape the ceiling today |
| from-scratch (allowlisted) child environments | 5 | `tests/upgrade/preview_support/process.py::child_environment`, `tests/scripts/test_activate_isolated_env.py::_clean_env`, `tests/charter_offering/conftest_pack_remote.py::_env`, `tests/kernel/git/test_remote_fetch_commit_subtree.py::_env`, `tests/cross_cutting/packaging/test_sdist_offline_wheel.py::_offline_env` |
| fixtures that strip `GIT_*` | 1 | `tests/consolidation/test_bake_commit_scope_meta_only.py::_hermetic_env` |
| `stop=` callers of `locate_project_root` / `find_repo_root` in `src/` | 1 | `task_utils/support.py:75` forwards it; **no production caller passes it** |
| `stop=` callers in tests of those two walks | 3 | `charter_preflight/test_cli.py:106`, `cli/commands/test_cli_boundary_mission_types.py:119`, `status/test_lock_fallback_never_mints_marker.py:61` |
| `session_start._find_project_root` `stop=` callers | 4 | a **third**, `.kittify`-only walk that does not read the ceiling |

## Decisions

1. **`TMPDIR`/`TEMP`/`TMP` point under the run's basetemp.** `<basetemp>/tmp` is below the
   harness ceiling `#7022` installs, is wiped/reaped by `run_basetemp` with the run's own tmp
   tree (no second reaper, `C-004`), and is per-run and per-worker by construction.
   Windows `TEMP` follows: `tempfile._candidate_tempdir_list` reads `TMPDIR` first on every
   platform, but git and other child tools read `TEMP`/`TMP` on Windows, so all three agree.
2. **The temp root is created after pytest's basetemp reset.** `TempPathFactory.getbasetemp`
   removes and recreates a given basetemp on first use (`_pytest/tmpdir.py`, pytest 9.0.3), so a
   directory created in `pytest_configure` is deleted before the first test. The install creates
   it eagerly (covers import-time use) and a session-scoped autouse hook re-creates it after
   `getbasetemp()` has resolved, which is the only wipe.
3. **From-scratch children inherit the ceiling, not the caller's whole environment.** A new
   `tests/_support/temp_root.py` helper exposes the harness-owned variables
   (`GIT_CEILING_DIRECTORIES` and the temp-root trio) so each site merges one dict instead of
   re-deriving the policy. `GIT_CEILING_DIRECTORIES` is a discovery boundary, not git
   config/auth, so restoring it after a `GIT_*` strip does not re-open what those strips close.
4. **`stop=` goes.** `locate_project_root` and `find_repo_root` already honour the ceiling, so
   `stop=` is a second boundary mechanism with no production caller and no coverage `git`'s
   ceiling does not already give (the ceiling also bounds child processes). Its three test
   callers switch to the per-test `GIT_CEILING_DIRECTORIES` narrowing — the same narrower local
   control the ~9 other modules use, which `C-001`/issue item 3 keeps.
5. **`session_start._find_project_root`'s `stop=` stays, out of scope.** That walk does not read
   `GIT_CEILING_DIRECTORIES` at all, so deleting its only bound would make its four callers
   non-hermetic. Giving it the ceiling is a `src/` walk migration, which belongs with #7056's
   migration (its gate does not catch the `while True:` shape). Deferred, named in the PR.

## Evidence for the ordering rule

`_pytest/tmpdir.py::TempPathFactory.getbasetemp` (pytest 9.0.3), verified in the installed venv:

```python
if self._given_basetemp is not None:
    basetemp = self._given_basetemp
    if basetemp.exists():
        rm_rf(basetemp)
    basetemp.mkdir(mode=0o700)
```

`install_run_basetemp` sets `config.option.basetemp`, so every run takes this `_given_basetemp`
branch — the eager directory is removed once, and only once.

## Open questions resolved during plan

- Does moving `tempfile` under the basetemp change `_worker_home_base`? No: it is computed from
  `tempfile.gettempdir()` **before** the temp root is installed, so the isolated home stays under
  the platform temp root (and stays an explicit ceiling entry). Deliberate: it keeps this diff
  off the home-isolation machinery.
- Does anything assert on the platform temp root's identity? Only tests that monkeypatch
  `tempfile.gettempdir` themselves (`test_session_reaper`, `test_prompt_retention`,
  `test_resolve_lanes_dir`) — unaffected, they patch the function, not the env.
