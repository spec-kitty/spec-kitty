# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · s7-agent · New migration id instead of editing 2.0.7_fix_stale_overrides: DIRECTIVE_044 freezes shipped migration bodies (the ledger drift audit exists to make an edit visible), and a project that already settled 2.0.7 is never re-selected by ledger-diff, so an in-place matcher fix would not reach the projects this issue is about.

2026-10-31 · s7-agent · Differing overrides are preserved and named, never moved back to .kittify/missions/. The issue offers move-back or a doctor finding; #4961 rules out mutating bytes the package cannot prove it owns, and a move into the legacy tree would rewrite operator bytes under a name a lower tier reads. Exact-byte identity (no CRLF folding) matches classify_asset's filecmp beside it and the guard's canonical prover.

2026-10-31 · s7-agent · detect() is true for a differing candidate too. A not-needed step prints nothing, and the operator's only signal that their override shadows the shipped file is the warning — because a successful apply() records the step as settled, that naming happens once per project rather than on every upgrade.
