# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-12 · stijn-dejongh · Fixture fidelity pitfalls found during grounding: (1) a legacy feature_slug event key sends the audit down a slug-resolution path that pulls in kernel/resolution.py (absent from the real corpus) — modern mission_id-only events avoid it; (2) the reducer (SNAPSHOT_DRIFT / #6058 surface) only runs when a status.json exists and the event log is not corrupt, and the bundled audit fixtures ship none — the fixture must include a reducer-generated status.json. gh GraphQL is blocked in this environment; use gh api REST for issue ops.
