# Work Packages: Root-vacuous chmod tests + TestOrdering isolation

## Work Package WP01: Make the denied-write and ordering tests bite (#5654, #5186)

**Dependencies**: None

Requirement refs: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, SC-001, SC-002, SC-003

- [x] T001 Planted-break proof for the three read-only `.gitignore` sites and the two seam-injected sites (no test change)
- [x] T002 Seam-inject `TestStoreUnreachable` at the history-db open; prove it red against two planted breaks
- [x] T003 Delete `GitignoreManager._atomic_write`; retarget its two tests to `write_gitignore_text`; fix the read-only test docstring
- [x] T004 `TestOrdering` class-scoped autouse `auto_discover_migrations()` fixture; reproduce red first
- [x] T005 File the follow-up issue listing the remaining root-skipped chmod tests
