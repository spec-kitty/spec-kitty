# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · claude · Grounding found the guard ran in NO CI lane: tests/audit is out_of_matrix_test_dirs and ci-nightly interpreter-matrix-shard-5 selects tests/audit under -m 'fast or unit', which deselects all 8 integration-marked tests (0 collected). The new lane therefore carries no marker expression; that is a correctness requirement, not a style choice.
