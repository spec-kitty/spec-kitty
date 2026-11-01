# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Red-first through the pre-existing entry points: the CLI-surface ratchet in tests/cli/test_mission_agnostic_flag.py and the new sibling-Mission isolation module both failed on the untouched tree (the three commands still exited 2 with the #5294 reject), then went green after the CLI parameter and the three discovery narrowings landed. No post-hoc filter of a full-corpus walk was used anywhere: backfill-provenance narrows its mission loop before the placement_seam read, charter-encoding drops the global glob for a scoped run, and rebaseline filters the existing glob by path-derived identity only.
