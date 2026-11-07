# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · implementer-pedro · WP02: the 3.1.x classification threshold is the subclass's own target_version (3.1.2 vs 3.2.0a4), so the residue-safe sibling inherits the rule; an undatable stamp (missing/unparseable/numeric-float) keeps the legacy machine answer rather than being treated as modern. Home is still consulted only for shapes with no usable project stamp, and the exact-global-file question now goes through runtime.agent_commands.get_global_command_dir (the canonical owner), with the hand-built Path.home() shape kept only for roots with no agent key.
