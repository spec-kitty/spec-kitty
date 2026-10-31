# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · Grounded first: both legacy shapes reproduce on main 35318ef51c — get_agent_dirs_for_project() returns all 12 AGENT_DIRS entries for a project with .kittify/ and no config.yaml, and for one with 'vcs: {type: git}' (no agents section). #6494 (0356bbdcb7) already owns the explicit empty list and the corrupt-config refusal; neither is touched.
