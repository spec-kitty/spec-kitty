# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · One reader (mission_metadata.read_tracked_meta) and one notice module, consulted by every upgrade seam that can write meta.json: the 2.0.6 successor, the 3.2.0a4 normalization, the 3.2.6rc1 runtime-state cutover, and backfill_mission. The cutover's one-key meta.json stub was found by the post-tasks review squad and proven on main.
