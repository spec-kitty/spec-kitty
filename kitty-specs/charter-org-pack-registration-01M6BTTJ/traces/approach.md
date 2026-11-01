# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi/deepseek-v4.1-flash-1017 · Grounding: `charter org` exposes only init/validate; no command or PR registers a pack. Owner module is src/specify_cli/cli/commands/charter/org.py; the read authority for charter_packs.org.packs is src/charter/offering/drg/org_pack_config.py (OrgPackConfig/PackRegistry/load_pack_registry). Plan: add add/remove there plus a write seam in the same offering module, keeping one schema authority.
