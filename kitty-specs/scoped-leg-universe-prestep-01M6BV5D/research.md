# Discovery findings — scoped leg universe pre-step (#7001)

Mission: `scoped-leg-universe-prestep-01M6BV5D`. Recorded before the spec, from issue
#7001 (a follow-up of #6994 / PR #6996) plus a reproduction on `main` at `287a226cfe`.

## Decisions

- **D-01 — The intersection is the decision's input, not the collection's.**
  The universe (`tests/architectural/_gate_coverage.collect_universe`) is defined as
  every test in `tests/`, and its two consumers
  (`test_fast_tier_marker_completeness.py`, `test_same_tier_uniqueness.py`) compare
  across the whole suite. Narrowing the *collected list* to a leg's selected gates
  would hand those tests a partial universe and turn a green gate red-on-nothing (or
  worse, green on nothing). So the pre-step is intersected where the question is
  asked — "does any of *my* selected gates need the universe?" — and a leg that does
  collect still collects the whole tree.
- **D-02 — The gates file is the leg's own selection, read through one parser.**
  `battery_partition_plugin.read_gates_file` already owns the `SK_BATTERY_GATES_FILE`
  semantics for the running leg. The decision must resolve the same file to the same
  set, or the pre-step and the leg can disagree about which gates run. The format
  (one gate path per line, blank lines ignored) will live in `scripts/ci/battery_scope.py`
  next to the writer, and both readers will call it.
- **D-03 — Fail closed when the named file cannot be read.** The plug-in already fails
  closed on a missing named file; the decision must too, so a broken scope selection
  reds the job instead of silently skipping a collection a selected gate needs.
- **D-04 — No gates file means today's answer.** Whole-leg runs (`mode=full`), the
  nightly/backstop paths and any doubt keep the current whole-part answer. This keeps
  the change inside the scoped path (#6994) that introduced the file.

## Evidence

- **Reproduction on `main`.** For a docs-only diff, `select_battery_gates` selects
  `dead_builtin_doc_paths`, `no_config_key_spelled_as_module_path`,
  `no_dead_src_path_literals` (leg 1/2) and
  `adr_hygiene_convergence_retirement`, `no_deprecated_doctrine_command_in_guidance`,
  `no_stale_charter_path_literals`, `retired_charter_vocabulary` (leg 2/2, for a
  `docs/adr/**` change). None of them calls `collect_universe()`. Yet
  `python -m scripts.ci.collect_universe_prestep consumers --battery-part 1/2` and
  `...-part 2/2` both print `true` (1.8 s / 1.5 s), because the partition also holds
  `tests/architectural/test_fast_tier_marker_completeness.py` (1/2) and
  `tests/architectural/test_same_tier_uniqueness.py` (2/2) — gates this diff did not
  select.
- **Cost of the unnecessary chain, measured on the development host** (clean checkout,
  `SK_GATE_REUSE_REPORT` set):
  `key --with-commit` 0.57 s; `collect` cold **396.7 s** (`{"outcome": "collected",
  "reason": "no-record", "seconds": 396.651}`); `collect` warm 0.82 s
  (`{"outcome": "reused", "seconds": 0.546}`). The cold path is the common case in CI:
  the cache key is `universe-<key>-<commit>`, and a new PR head is always a cache miss.
  The published CI range for a first collection is 89–233 s
  (`docs/development/reference/ci-gate-mechanics.md`, "Stored test-universe
  collection"), so the ordering holds on CI even though this host is slower.
- **The docs' partition claim is stale.** `ci-gate-mechanics.md` says "leg 2/2 holds no
  collecting test and skips the step"; today the partition holds one consumer per leg
  (verified by intersecting `battery_part_files("1/2"/"2/2")` with
  `universe_consumers()`). The docs sentence needs correcting as part of this change.
- **The shape is pinned by tests.** `tests/ci/test_ci_workflow_prestep_shape.py` pins the
  `select -> key -> restore -> collect -> save -> pytest -> check` order, the guards, the
  `consumers --battery-part` call and the no-`||` rule; any wiring change has to update
  that test and its mutation cases deliberately, not accidentally.

## Open questions (for plan/tasks)

- Whether the decision takes the gates file as an explicit `--gates-file` option or reads
  `SK_BATTERY_GATES_FILE` from the environment. Decision taken in the plan: an explicit
  option, defaulting to the environment variable, so the CI step stays readable and a
  local reproduction can pass a file without exporting a variable.
- Whether the workflow should also skip `sync-packs` or the `uv sync` extras for a scoped
  leg. Out of scope here (C-002/C-003); recorded as a further cheap win in the PR.
