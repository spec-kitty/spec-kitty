# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-12 · planner-priti/claude · Chose option (a) explicit leading-alternation over option (b) Python post-filter: keeps the single git grep call as the gate mechanism and is the smallest honest change. Boundary rejects a preceding /, word char, . or - (per #6096). Blob-URL/nested-literal src/ coverage deliberately stays with test_no_dead_src_path_literals.py, not Gate D.

2026-10-12 · implementer-ivan/claude · Red->green->revert proven. New regression RED at 80fa4fcb (unanchored _MOVED_BUILTIN_DOC_RE over-matches nested_pack_tail/absolute_path_tail/blob_url_tail); GREEN at cfa57965 (left-boundary anchor). Non-vacuity: reverting ONLY the anchor in the working tree re-reds the test (1 failed), then restored. Gate D + 3 named siblings: 38 passed. ruff check / ruff format --check --force-exclude / mypy all clean on the changed file; helper+test complexity well under 15.
