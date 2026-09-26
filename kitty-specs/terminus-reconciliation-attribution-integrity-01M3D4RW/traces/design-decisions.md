# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-25 · claude · Fix granularity, NOT gate strictness (C-001): #5018's excluded set must SUBTRACT approved first-parent authored SHAs/patch-ids, not adopt 'approved wins' (that reopens #4977). #5022 authored-deletion authority reuses _final_authored_blobs' existing deletion detection (blob_id_at raises on the newest touching commit → record as authored deletion). Both rest on the disjoint-write-scope invariant (C-004); the 3-way case is that invariant's known boundary and stays xfail.
