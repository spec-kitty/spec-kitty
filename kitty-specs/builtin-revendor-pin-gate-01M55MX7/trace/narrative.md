# Narrative — builtin-revendor-pin-gate (#3504)

Follows the live-drift fix (open-packs PR #38 re-seed + `v0.1.0` tag). That fix was
manual; this mission makes it systematic: a pin + vendor command + drift gate so
`packs/built-in/` can never silently diverge from its open-packs provenance again.

- §0 grounded on skupstream/main 83ca247ebc.
- §1 three-lens opus grounding squad (architect / brownfield / alignment) caught the
  ADR conflict and confirmed Shape A; mapped the seam blast-radius and related tickets.
- §2 claimed + assigned #3504 to stijn-dejongh.
- §3 spec authored (Shape A), committed 813f73e.

Delivered. Five WPs shipped: WP01 pin model (`packs/built-in.source.yaml`), WP02 the
`charter pack vendor [--check]` command, WP03 the per-PR drift gate, WP04 the
release-time re-verify, WP05 docs and changelog. SC-002 was discharged by a real
vendor round-trip against open-packs, with `v0.1.0` as the pinned ref. Drift now reds
CI with a remedy (bump the pin via `vendor`), so `packs/built-in/` cannot silently
diverge from its provenance again.
