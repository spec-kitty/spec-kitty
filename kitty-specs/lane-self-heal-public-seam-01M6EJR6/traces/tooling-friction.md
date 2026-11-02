# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · spec-kitty plan resolved planning_base_branch to the current checkout (the issue branch) while meta.json still said main; finalize-tasks then refused to commit to 'main' until --target-branch named the issue branch. Expected for a topic-branch mission, but two readings of 'target branch' worth naming in the report.

2026-11-02 · python-pedro · Pre-existing red in tests/lanes: test_refinalize_mission_branch.py::test_backfill_then_refinalize_keeps_mission_branch_byte_identical asserts refinalize action == 'wrote' but gets 'skip' on pristine main; filed as #7084. Also: test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported failed once under batch load and passed on immediate re-run (shared global-asset cache contention, per the brief).
