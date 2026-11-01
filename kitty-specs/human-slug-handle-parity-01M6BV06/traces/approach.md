# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · Reproduced #6278 on main (287a226cfe) with the issue recipe: mission create smoke-test -> smoke-test-01M6BTQX; agent tasks status --mission smoke-test resolves; implement WP01 --mission smoke-test exits 2 with 'No mission found'. Scope fixed: widen the identity resolver's human-slug rung rather than refuse the handle everywhere.
