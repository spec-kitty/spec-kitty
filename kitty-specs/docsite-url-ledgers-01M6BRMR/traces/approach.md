# Approach

- **[2026-11-01][plan] Two ledgers plus one derived map.** `site/moves.yaml` is the only hand-edited move record; `scripts/docs/redirect_map.yaml` (what DocFX reads) is derived from it with chain collapse; `site/url-baseline.txt` is seeded once from a real DocFX walk unioned with the derived map's keys. One module, `scripts/docs/moves_ledger.py`, owns reading and validating both.
- **[2026-11-01][plan] ATDD per slice.** Each WP commits its failing acceptance test first: ledger containment and derivation (WP01), no Mission-scoped defaults (WP02), one index per folder (WP03).
- **[2026-11-01][implement] The seed is 970 routes, not 835 + 124.** The 11 follow-up entries (archived or re-moved destinations) are ledger `from`s too, so they are redirect keys and join the baseline: 672 walk pages + 298 keys. Local DocFX coverage: 970/970, and a one-key mutant drops to 969/970.
