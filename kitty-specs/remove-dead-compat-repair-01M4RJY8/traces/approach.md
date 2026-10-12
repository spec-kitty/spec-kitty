# Tracer: approach — remove-dead-compat-repair (#6095)

- **[2026-10-12][plan] Tidy-first behaviour-preserving removal, not a bugfix.** The #2985
  compatibility-repair path is provably dead under events 10.4.4 (`repairs == []` witnessed
  for both `at_encoding` shapes of the birth-cutover mixed mission). Approach: follow the
  dead-reference chain and delete only symbols whose every caller is repair code; keep the
  live seed-tolerance (`_legacy_contract_carriers`) and the fail-closed parity guards
  (`_verify_claim_slot_witnesses`). Fold the two live call sites (`_backfill_runtime_state_locked`,
  `verify_backfill`) that call the planner/verifier, since the planner always returns `([],[])`.
- **[2026-10-12][plan] Gates kept green by removal, not loosening.** The repair symbols are
  not allowlisted (they live via internal refs), so a clean removal passes the dead-symbol
  gate without an allowlist edit. No new size/length/ratchet gates (operator ruling).
