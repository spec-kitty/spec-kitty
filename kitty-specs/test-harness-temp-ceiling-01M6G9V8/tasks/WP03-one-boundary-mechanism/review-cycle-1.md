# WP03 review — cycle 1

Reviewer: reviewer-renata profile (review role). Base: mission branch → `b7e5ca65d7`.
Verdict: **approved**.

## Anti-pattern checklist

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Dead code | N/A (removal) | No new production surface. `boundary` and its `# type: ignore`-free break are gone from both walks; `inspect.signature` on the installed package shows `(start: Path \| None = None)` for both. |
| 2 | Synthetic-fixture test | PASS | `test_the_walk_takes_no_stop_parameter` reads the real signature of the real functions; `test_passing_stop_is_a_type_error` calls them; the behavioural test calls `locate_project_root`/`find_repo_root` against a real tree. Restoring `stop=` reds the first two (measured: 4 failed before the change). |
| 3 | Silent empty return | N/A | The change removes a guard; no new swallow, no new `raise`. |
| 4 | FR coverage | PASS | FR-005: both signature assertions + both `TypeError` assertions. FR-006: the three callers keep their verdicts (see below), and the same-fixture positive control proves the boundary is still the ceiling: below it → `None`/`TaskCliError`, at it → the project. |
| 5 | Frozen surface | PASS | `session_start._find_project_root` and `session_stop` are absent from the diff (`git diff --stat \| grep session` → none), which is C-002 exactly: that walk does not read the ceiling, so its `stop=` stays. |
| 6 | Locked decision | PASS | `session_start._find_project_root` keeps `stop=` and its four callers are untouched — the alternative (deleting its only bound) would have made them non-hermetic, which the mission forbids. |
| 7 | Shared-file ownership | PASS | `src/specify_cli/core/paths.py` and `task_utils/support.py` are WP03-only in `lanes.json` (lane-c); the three test modules likewise. No overlap with WP01/WP02. |
| 8 | Production fragility | PASS | The walks' only fail-loud path is unchanged (`TaskCliError` in `find_repo_root`'s fallback). Removing a keyword cannot introduce a transient-race failure. |

## Reviewer checks specific to an API removal

- **No caller left behind.** `grep -rn "locate_project_root([^)]*stop=\|find_repo_root([^)]*stop=\|partial(…, stop" tests/ src/` → empty.
- **Equivalence at the three sites.** `stop=X` and a ceiling of `X` are the same rule under
  #7022's shipped contract (a listed directory is examined, the walk stops after it), so the
  rewrites are behaviour-preserving, not a loosening. Each module keeps its own
  `monkeypatch.delenv("SPECIFY_REPO_ROOT")` and now narrows `GIT_CEILING_DIRECTORIES` to its
  own `tmp_path` — *narrower* than the run-wide harness ceiling, which is what keeps the
  "nothing here" verdicts deterministic.
- **Docstrings.** Both no longer document a parameter a caller cannot pass; the ceiling
  paragraph it already had is kept and the past-tense note explains why tests needed one.
- **Formatting.** `ruff format --check` reports both `src/` files as "would reformat" on the
  pristine base as well, so the WP deliberately did not reformat them — that drift is
  pre-existing and out of scope (no unrelated churn).

## Verified

- `tests/unit/test_root_walk_has_one_boundary.py`, `tests/specify_cli/charter_preflight/test_cli.py`,
  `tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py`,
  `tests/status/test_lock_fallback_never_mints_marker.py`, `tests/tasks/test_tasks_support.py`,
  `tests/specify_cli/core/test_paths.py` → 90 passed (with the pre-change red quoted in the commit).
- `uv run mypy src/specify_cli/core/paths.py src/specify_cli/task_utils/support.py` → clean.
- `uv run ruff check` on the five touched files → clean.
