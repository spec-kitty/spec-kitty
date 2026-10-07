# Data model

## Cut-over verdict (existing, `CutOverVerdict`)
- `cut_over: bool`, `reasons: tuple[str, ...]`.
- **Change**: a PASS may now carry one reason, the pre-accept note. Consumers must treat `cut_over` as the decision and `reasons` as explanation in both states.

## Pre-accept exemption (new, derived — not stored)
Holds iff all of:
1. `meta.json` readable, `mission_id` present;
2. event-log runtime evidence present;
3. `status_phase` absent or a well-formed integer `< 1`;
4. no terminal evidence: `accepted_at`, `merged_at`, `accept_commit`, `merged_commit`, `acceptance_history` empty/absent and `mission_number` is null/absent (a non-string `accepted_at`/`merged_at` is malformed and declines);
5. every WP's legacy record reads without error and `has_legacy_claim_runtime()` is false.
Any read error → not exempt.

## Verdict transitions
| State | Before | After |
|---|---|---|
| evidence, no stamp, pre-accept, no legacy frontmatter runtime | FAIL | PASS + note |
| any other state | unchanged | unchanged (reason text more specific) |
