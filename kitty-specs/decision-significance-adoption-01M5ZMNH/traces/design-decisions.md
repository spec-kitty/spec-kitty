# Design decisions — decision-significance adoption

- 2026-10-27 — Split authoring and resolved RACI types (operator, Decision Moment `01M5ZMPA58JS7K7S4S40CH7H1M`). Why: templates omit `actor_id` on purpose so `resolve_raci` fills it from the runtime inputs; a sentinel in the authoring binding would skip that lookup. Alternative rejected: one package binding with the sentinel doubling as an "unset" marker.
- 2026-10-27 — #6446 left blocked (operator, Decision Moment `01M5ZMPFCN3BFSEQ8VTN6MT3HF`). Why: the EventBridge port has no door for run-log decision events, and no timeout trigger exists.
- 2026-10-27 — Floor raised to 11.3.0, not 11.2.0. Why: 11.2.x never reached PyPI, so a `>=11.2.0` floor would resolve only 11.3.0 anyway and would misstate what is installable.
