# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · The byte-frozen agent tasks --help fixtures stay untouched: mark-status already documents --wp, so documenting the flag was never the gap. Fix the emitters instead of the docs. Subtask-id namespacing (WP02.T001) is explicitly out of scope (C-001): ids stay mission-scoped T###, no frontmatter migration, no event-schema change. The renderer lives in specify_cli.core rather than specify_cli.cli because the runtime layer may not import the CLI; it is pure text so the I/O-free move-task decision core can use it.
