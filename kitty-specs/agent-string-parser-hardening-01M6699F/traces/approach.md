# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-3 · Plan: fix all three rows inside parse_agent_boundary_string only (strip, blank-after-strip is None/empty-tool error, >4 segments raises ValueError). No call-site changes: explicit --agent paths already convert ValueError into the Invalid --agent value refusal; lenient paths pre-check the count or catch ValueError and store whole (#6400). One WP, red-first tests in the two owning test files.
