# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-agent-e · Chose grep -I (skip binaries) over git grep: keeps the one-subprocess model (NFR-002) and works in fixture repos the tests build; -I judges text regardless of tracking state, matching the invariant's intent. Evidence fallback reads stderr on exit-0-with-empty-stdout so a binary-only match is named instead of blank.
