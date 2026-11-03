# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · claude-opus-4-5 · Rejected declaring deactivated_<kind> fields on CharterYaml: compiler.py builds the emitted charter.yaml from this model, so a declared None-defaulted field would be dumped and emitted into every regenerated charter, breaking consolidated-charter-bundle-01KXSYB9#NFR-005 byte stability. Refusal by prefix also keeps one deny vocabulary (activation_ledger.DENY_KEYS).
