# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · spec-kitty agent tracer-append / record-analysis failed repeatedly with 'global_assets: Global asset input changed: ~/.kittify/cache/global_skills-assets.json' — another fleet agent on this host rewrites the shared global asset cache concurrently. Retrying with a short sleep succeeded. Matches the MISSION-BRIEF warning about the shared global asset cache being unsafe to race.
