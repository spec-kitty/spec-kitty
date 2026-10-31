# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Chose issue option 1 (mark the pre-3.1.2 project-command writers superseded) over option 2 (backfill-side settlement) and option 3 (extend the floor). Options 2 and 3 only act at adoption and cannot repair a ledger already adopted without the floor, which is the defect shape; the supersession table (#6589) is the existing single declaration for 'a later migration replaced what this older one wrote', and a shipped module stays byte-identical (DIRECTIVE_044) so content_hash and recorded history stay stable.
