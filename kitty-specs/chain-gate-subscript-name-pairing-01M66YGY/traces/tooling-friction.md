# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · move-task --to for_review reported 'Pre-review regression gate: source_mismatch — baseline captured under DeclaredCommandScopeSource/text; head ran under DeclaredCommandScopeSource/junit_xml — failure identities are not comparable'. The transition still succeeded, but the gate compared a text baseline against a junit_xml head run, so its comparison is void on this path.
