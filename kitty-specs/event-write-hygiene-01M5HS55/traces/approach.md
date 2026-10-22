# Approach

- **[2026-10-22][specify] Delete rather than replace.** Every door in #6614 and the builder holding the private import in #6607 have no `src/` caller. Deletion, plus gates against reintroduction, is the smallest change that closes G-11, G-16 and G-18 without pre-empting the EventBridge port (#6603).
- **[2026-10-22][specify] Test seeding moves to a helper over the atomic primitive.** About 195 test files seeded through the non-atomic door. They move to `tests/_support`, so tests exercise the write path production actually uses.
