# Design decisions

- **[2026-10-22][specify] Delete the dead hosted builder (operator ruling).** The alternatives were the public `validate_event` with its unknown-type `ValueError`, or a local explicit type set. Deleting removes the private import and the latent 11.1.0 `actor_id` strictness break together.
- **[2026-10-22][specify] No compatibility aliases (operator ruling).** `spec-kitty/event-router` is frozen and considered dead, so no old names are kept for it. The timeout env var `SPEC_KITTY_SAAS_FANOUT_TIMEOUT` goes too.
