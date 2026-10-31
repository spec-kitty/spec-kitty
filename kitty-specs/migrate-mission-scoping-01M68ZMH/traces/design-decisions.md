# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · D-02 confirmed in code: handle resolution stays in the CLI (_scoped_mission_slug delegating to resolve_mission_handle), so the three backends keep a plain mission_slug parameter and never re-parse mid8/mission_id. Consequence: migrate backfill-mission-type's documented SLUG-only limitation is NOT inherited here, which is why its _MISSION_TYPE_MISSION_HELP/_MISSION_TYPE_MISSION_METAVAR constants were deliberately not reused (they advertise a narrower contract than these commands honour).
