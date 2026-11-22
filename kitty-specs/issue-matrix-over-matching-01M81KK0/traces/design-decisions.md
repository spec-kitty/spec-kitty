# Design decisions

- **[2026-11-22][plan] "Cited" maps to the existing context-only class.** No new GatingClass value, so the persisted vocabulary and scaffold verdicts stay unchanged (C-001).
- **[2026-11-22][plan] Scope travels on the occurrence.** A defaulted `in_gating_scope` flag set by discovery and read only by the classifier keeps one gating authority. A basename cannot tell `tasks/` from `contracts/`.
- **[2026-11-22][plan] Closing keyword first.** A non-negated close/fix/resolve that leads into a citation gates in any artefact and wins over every demoting rule, the commit-SHA rule included.
- **[2026-11-22][plan] Colour filter on declaration form only.** Per the #7808 hand-off: a keyword-anywhere filter would drop real 4-digit references.
