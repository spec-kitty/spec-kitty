# WP01 review feedback (cycle 1) — reviewer-renata

Overall the design is right and most claims verified: red commit d5e94033 precedes green 4ddf39c9
(hosted_posture.py/toml_table.py absent at d5e94033; the green commit's test-file edits are
formatting-only); truth table rows all represented; R-1 holds (personal path is
`get_runtime_root().base / "config.toml"`, and `bootstrap/env_file.py` drops any `SPEC_KITTY_HOME`
line from `.kitty.env`); no caching; lazy ruamel import; D7 strict writer verified; root fixture
patches the module attribute and writes nothing under SPEC_KITTY_HOME; moments refactor is
behaviour-preserving (tests/zeitgeist_client 821 passed / 16 skipped on both base and lane);
dead-symbol reds are exactly the hosted_posture in-flight names. Three items must be fixed.

**Issue 1 (blocking) — real-reader tests are not hermetic against the env narrowers.**
With `SPEC_KITTY_NO_MOMENT_HANDLERS=1` in the ambient environment (the orchestrator in this very
programme runs with it), 6 tests fail:
`TestTruthTable::test_repo_true_personal_true_no_narrower_is_enabled`,
`test_repo_true_personal_off_or_absent_is_disabled[absent|false]`,
`test_repo_off_or_absent_is_disabled_regardless_of_personal[absent|false]`,
`TestRequireDrain::test_returns_none_when_enabled`
(repro: `SPEC_KITTY_NO_MOMENT_HANDLERS=1 PYTHONPATH=$PWD/src python -m pytest tests/specify_cli/core/test_hosted_posture.py`
→ 6 failed, 17 passed). The same applies to `SPEC_KITTY_SYNC_DISABLE` (kill switch) and
`SPEC_KITTY_SYNC_MINIMAL_IMPORT` values.
Fix: in `test_hosted_posture.py`, add a module-local autouse fixture that `monkeypatch.delenv`s every
name in `specify_cli.core.env.MOMENT_HANDLER_DISABLE_ENV_VARS` (raising=False). Also add one
narrower test that sets the REAL env var (`monkeypatch.setenv("SPEC_KITTY_NO_MOMENT_HANDLERS", "1")`)
rather than patching `moment_handlers_disabled_reason`, so the actual env→narrower integration is
pinned, not only the function seam.

**Issue 2 (blocking) — `set_repo_drain` is untested; ledger parse-error branch is untested.**
Coverage of `src/specify_cli/core/hosted_posture.py` from the WP's own tests is 82%
(missing 138, 155, 158, 174, 178, 184-186, 189, 221, 311-329) — below the ci-aggregate diff-cover
≥90% gate, and against the charter/CLAUDE.md rule "every new branch/helper needs tests in the same
PR". `set_repo_drain` is a WP01 deliverable (T003 step 8) with zero tests, and the DoD's
"parse errors … fail to the documented default for ledger (on), each with exactly one warning" has
no ledger parse-error test. Add at least:
- `set_repo_drain(root, True)` on an existing config.yaml with comments + other keys + an existing
  `hosted:` mapping → comments/keys survive, `hosted.drain: true` added; round-trip through
  `drain_posture` reads it back.
- `set_repo_drain` with no `config.yaml` (but `.kittify/` present) creates it.
- `set_repo_drain` where `hosted` is a non-mapping scalar → replaced by a mapping.
- `set_repo_drain` on unparseable YAML → raises, bytes unchanged (document this as intended
  fail-loud, mirroring D7).
- `ledger_posture` with malformed YAML → `enabled=True` and exactly one `UserWarning`.
- `drain_posture`/`ledger_posture` with `project_root=None` and no resolvable root (lines 138/174),
  and non-mapping YAML top-level / `hosted`/`ledger` sections (155/158/189/221).

**Issue 3 (minor, fix in same cycle) — new mypy error in owned file.**
The new `[[tool.mypy.overrides]] module = ["specify_cli.core.paths"]` makes `locate_project_root`
typed, so `mypy src/specify_cli/zeitgeist_client/moments.py` now reports
`moments.py:173: error: Redundant cast to "Path" [redundant-cast]` (clean on the base branch).
`moments.py` is WP01-owned; drop the `cast(Path, ...)` in `locate_repo_root` (and the `cast` import if
it becomes unused). The pyproject overrides themselves are fine (`test_pyproject_shape.py` 7 passed).

**Non-blocking suggestions**
- `_read_repo_drain_key` / `_read_repo_ledger_key` are near-duplicates (Sonar duplication); consider
  one `_read_repo_bool_key(repo_root, section, key, *, label)` helper.
- `warnings.warn(..., stacklevel=2)` inside private helpers points at `hosted_posture.py` itself;
  `stacklevel=3` would attribute to the caller of `drain_posture`/`ledger_posture`.
- `ledger_posture` reports `source="default"` even when the file was read but held an invalid value;
  consider keeping the path in `source` for operator diagnostics (WP08 `drain status`).

Out-of-map edits reviewed and accepted: `pyproject.toml` mypy overrides (precedent-matching,
shape test green) and `tests/architectural/test_home_owner_behaviour.py` frozen-list append
(explicitly sanctioned by its docstring regen recipe for a reviewed conftest change). Pre-existing
`ruff format --check` drift in `tests/conftest.py` and `test_home_owner_behaviour.py` exists on the
base branch too — not this WP's.
