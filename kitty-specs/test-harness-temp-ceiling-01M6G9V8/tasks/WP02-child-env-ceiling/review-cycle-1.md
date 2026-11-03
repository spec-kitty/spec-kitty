# WP02 review — cycle 1

Reviewer: reviewer-renata profile (review role). Base: mission branch → `43555cdfaa`.
Verdict: **approved**.

## Anti-pattern checklist

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Dead code | PASS | WP01's `harness_env` now has six live callers (the five helpers plus the bake fixture); the review of WP01 flagged it as callerless-until-WP02, and that is now discharged. |
| 2 | Synthetic-fixture test | PASS | `tests/unit/test_harness_child_env.py` calls each site's real helper (`_clean_env()`, `_env()`, `_offline_env()`, `child_environment()`) and asserts on the dict it returns — no literal fixture shaped to match. Red before the change: 5 failed, 3 passed. Deleting any one `env.update(harness_env())` reds exactly its own test. |
| 3 | Silent empty return | PASS | The only conditional is `preview_support.child_environment`'s `if ceiling is not None`, documented: the helper must work when it is called outside a harness (the isolated-env helper's own subprocess tests do exactly that), and the negative tests pin "no ceiling in, no ceiling invented". No `except: pass` added. |
| 4 | FR coverage | PASS | FR-004: five direct assertions + the in-module bake assertion (`_hermetic_env` is a module-level autouse fixture, so it is asserted where it lives — a fixture cannot be requested across modules; the task brief was corrected for this before analysis was recorded). |
| 5 | Frozen surface | PASS | The WP's own commit touches no frozen file: `tests/conftest.py` and `tests/_support/temp_root.py` appear in the review diff only because lane-b is stacked on lane-a, and `git show --stat 43555cdfaa` confirms neither is in WP02's commit. |
| 6 | Locked decision | PASS | The strips keep stripping: `test_isolated_env_shell_helper_carries_the_ceiling` asserts `[n for n in env if n.startswith("GIT_")] == ["GIT_CEILING_DIRECTORIES"]`, and `test_pack_remote_git_helper_carries_the_ceiling` still sees `GIT_CONFIG_NOSYSTEM`/`GIT_CONFIG_GLOBAL`. C-001 (per-test narrowings stay) is honoured: the fixture reads the *live* value, so a `monkeypatch.setenv` narrowing is what the child inherits. |
| 7 | Shared-file ownership | PASS | No file in another WP's `owned_files` was modified (see 5). `harness_env` is imported, not edited. |
| 8 | Production fragility | N/A | No production code. |

## Observations (no change requested)

- `child_environment` takes only the ceiling from `harness_env`, not the temp triple,
  because its provenance probes read `env["TMPDIR"]` and must see the sandbox root. The
  test pins that (`Path(env["TMPDIR"]) == sandbox.resolve() / "tmp"`), so a future
  "just merge the whole dict" edit reds instead of silently moving the measured temp root.

## Verified

- `tests/unit/test_harness_child_env.py` + `tests/consolidation/test_bake_commit_scope_meta_only.py` → 24 passed (after the change; 5 failed before).
- `tests/scripts/test_activate_isolated_env.py` + `tests/kernel/git/test_remote_fetch_commit_subtree.py` → 26 passed, 1 skipped.
- `tests/charter_offering -k "pack_fetch or pack_remote or remote"` → 34 passed.
- `tests/upgrade/test_preview_oracle.py` → 31 passed; `tests/upgrade/test_mission_corpus_recovery.py` → 9 passed (475 s, heavy e2e).
- Combined `test_preview_oracle.py + test_mission_corpus_recovery.py` → 40 passed on re-run. **One earlier combined run reported 1 failed / 5 errors at fixture setup; it did not reproduce** on two subsequent identical runs. Recorded as unexplained-transient (see the PR's Deferred section) rather than assumed benign.
- `tests/cross_cutting/packaging/test_sdist_offline_wheel.py` was not executed (it builds an sdist and a wheel, ~8 min, and needs the shared build artifacts); its helper is covered by `test_offline_sdist_env_carries_the_ceiling`.
- Ruff check + format clean on all six touched files.
