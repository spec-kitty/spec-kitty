# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-3 · Decision: refuse >4 segments at the parser, not per command. One authority, no second segment-count source; every caller surveyed in research.md either refuses (explicit paths), pre-checks (actor_from_option) or falls back whole (actor_full_identity, _actor_key). A whitespace-only tool is refused as an empty tool, matching the existing error semantics.
