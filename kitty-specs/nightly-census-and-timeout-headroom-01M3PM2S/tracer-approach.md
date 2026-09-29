# Tracer — approach

Mission: `nightly-census-and-timeout-headroom-01M3PM2S` (#5367, #5378)

- Phase 1 was read-only root-causing, posted to both issues before any code change.
- #5367: judged per DIRECTIVE_041 — the census is valid; 6/7 new entries are product drift (bare-id
  toolguide references, inert at the extractor, forbidden by ADR 2026-07-26-1); 1/7 is legitimate raw
  material. Fix product + re-pin to 20.
- #5378: measured five runs of job durations (jobs API + logs) instead of trusting one sample; runner
  variance ~2x dominates, test-count growth +1-2%.
