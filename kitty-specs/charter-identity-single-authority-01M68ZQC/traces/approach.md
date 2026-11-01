# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Grounded #6433 before specifying: compile, consistency check, DRG filter, presets and the project layer are already routed (#6457 a8dd1812a6, #6749). The surviving work is the facade (kind_vocabulary.resolve_artifact_urn/resolve_config_id/resolve_selected_id_to_stem are still scan-and-match loops) plus four CLI cascade-source call sites. Confirmed through the shipped CLI, not just by reading code.
