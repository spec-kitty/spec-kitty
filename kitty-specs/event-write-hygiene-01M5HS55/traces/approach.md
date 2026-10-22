# Approach

- **[2026-10-22][specify] Delete rather than replace.** Every door in #6614 and the builder holding the private import in #6607 have no `src/` caller. Deletion, plus gates against reintroduction, is the smallest change that closes G-11, G-16 and G-18 without pre-empting the EventBridge port (#6603).
- **[2026-10-22][specify] Test seeding moves to a helper over the atomic primitive.** About 195 test files seeded through the non-atomic door. They move to `tests/_support`, so tests exercise the write path production actually uses.
- **[2026-10-22][review WP02] Index census limits.**
  - Cheap to close: an `INDEX_PATH` alias. This is folded at pre-PR.
  - Out of scope: cross-module write helpers, nested-class methods and module-level code. These would need a cross-module call graph, so the test docstring is to name them as known limits.
- **[2026-10-22][review WP04] Pre-PR fold queue.** Two items: lower-case "Status fan-out" in the `adapters.py` docstrings, and close the `INDEX_PATH` alias gap in the index census (from the WP02 review).
