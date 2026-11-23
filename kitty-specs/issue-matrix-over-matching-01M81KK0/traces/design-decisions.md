# Design decisions

- **[2026-11-22][plan] "Cited" maps to the existing context-only class.** No new GatingClass value, so the persisted vocabulary and scaffold verdicts stay unchanged (C-001).
- **[2026-11-22][plan] Scope travels on the occurrence.** A defaulted `in_gating_scope` flag set by discovery and read only by the classifier keeps one gating authority. A basename cannot tell `tasks/` from `contracts/`.
- **[2026-11-22][plan] Closing keyword first.** A non-negated close/fix/resolve that leads into a citation gates in any artefact and wins over every demoting rule, the commit-SHA rule included.
- **[2026-11-22][plan] Colour filter on declaration form only.** Per the #7808 hand-off: a keyword-anywhere filter would drop real 4-digit references.
- **[2026-11-22][implement] Squad fold: the colour filter needs a whole-token property and a terminator.** All three squad lenses found the substring property match dropped `Backfill: #N` and `tasks-outline: #N` in the gating scope. The filter now takes an explicit lower-case property list anchored at a token start, plus a declaration terminator. Disposition: fixed.
- **[2026-11-22][implement] Squad fold: wrapped closing-keyword forms gate.** `**Closes** #N`, ``Fixes `#N` ``, `[#N](url)` and an issue URL are now closing statements out of scope too. Narrowings from routing labels through the canonical detector (`#N-fix`, `Fixes:#N`, keyword and number split across lines) are accepted and recorded in the ADR amendment. Disposition: fixed or accepted.
- **[2026-11-22][implement] Squad findings deferred.** The duplicated evidence-handle check `#\d+` (`review/_issue_matrix.py`, `issue_matrix_migration.py`) is matrix-evidence parsing, outside the owned files. Disposition: follow-up candidate for a campsite pass.
