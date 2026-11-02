# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · Grounding cost was the bulk of this mission: the file is green on main, so the red had to be witnessed twice — at the reporter's commit c5747c2c21 (worktree + make sync-packs, 1 failed / 75 passed) and in-process by clearing GIT_CEILING_DIRECTORIES (the issue's error string verbatim). Also: `make sync-packs` in a 1095-commit-old worktree needed its own pin refetch, and reusing a newer pack tree fails the digest check.

2026-11-02 · python-pedro · Pre-existing red found while running the blast radius: tests/specify_cli/migration/test_runtime_state_cutover_placement.py::test_mismatched_feature_dir_fails_closed_without_writing fails identically on pristine origin/main 9aed3a8012 (1 failed, 8 passed, 340s). Already tracked as #7055; cited in the PR's Deferred section, no new issue filed.
