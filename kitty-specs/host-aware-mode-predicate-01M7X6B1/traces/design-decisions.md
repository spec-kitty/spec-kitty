# Design decisions — host-aware-mode-predicate-01M7X6B1

- **[2026-11-20][plan] Windows semantics (operator ruling 2026-11-20).** Directories and symlinks compare kind only; files compare the owner write bit; POSIX compares exactly. This replaces 6269777dc's "ignore every Windows file mode" for project skills.
- **[2026-11-20][plan] The validator is host-aware (research R-3).** A missed raw-chmod planner now raises on Windows instead of re-planning forever. The gate makes such a miss a CI failure. The alternative, a tolerant validator, was rejected because it would leave the class silently alive.
- **[2026-11-20][implement] Execute-bit twin.** No packaged asset is executable, so the POSIX exec-bit twin pins drift in the other direction: an exec bit gained on a planned read-only skill file is repaired.
