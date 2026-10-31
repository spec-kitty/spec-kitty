# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude · Grounding: reproduced the defect by counting load_pack_registry calls during _collect_org_layer_data on the example-org fixture — 3 reads (1 in load_org_drg + 1 per wrapper). Fix target is 1. doctor refusals were exercised first so the pinned behaviour is known before touching signatures.
