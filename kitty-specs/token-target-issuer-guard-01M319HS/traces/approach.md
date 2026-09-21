# Tracer: Approach

The path taken through the mission — what was tried, what worked, course corrections. Seeded at planning.

## Grounding (pre-spec)
- Ran a 3-lens opus grounding squad (alignment/supersession, related-foldable-issues, seam/parallel-authority).
- Verdict: #4755 real on main @1a98c236cd, not superseded, closes #4755 only.
- Confirmed all four leak sites and both consequences by code reading (no exploit executed).

## Design direction (frozen at spec)
- ONE canonical helper `resolve_token_endpoint(session)` in the auth package; unify the two pre-existing
  guards + collapse duplicate normalizers rather than adding parallel copies.
- Non-vacuous arch fence on `get_saas_base_url()` with an explicit non-token-caller allowlist.
- Per-flow refusal adapters, with the refresh refusal typed so the `saas_client` bare-`except` cannot
  demote it into sending the held token.
- Structural close (operator steer): fold #4053 + #4265 as same-seam campsite work.

## (append during implement)
