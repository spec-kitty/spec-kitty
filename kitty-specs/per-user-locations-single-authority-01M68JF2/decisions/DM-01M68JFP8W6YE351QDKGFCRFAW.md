# Decision Moment `01M68JFP8W6YE351QDKGFCRFAW`

- **Mission:** `per-user-locations-single-authority-01M68JF2`
- **Origin flow:** `specify`
- **Step id:** `specify.intent`
- **Input key:** `intent_summary`
- **Status:** `resolved`
- **Created:** `2026-10-31T08:51:10.236274+00:00`
- **Resolved:** `2026-10-31T08:51:15.370908+00:00`
- **Resolved by:** `Ivan-Melck`
- **Opened by:** `python-pedro`
- **Other answer:** `false`

## Question

Confirm the Mission intent for #6488: platformdirs semantics win for per-user cache, state and config; kernel.user_dirs is the single authority and every caller routes through it; old locations are discarded; macOS/Windows branches pinned by faked-platform tests.

## Options

- Confirm scope as written
- Narrow to cache only
- Widen to include #2904

## Final answer

Confirm scope as written

## Rationale

Operator triage on #6488 (2026-10-19) names the rule, the scope list, the dead fallbacks and the cleanup; the brief's mission boundary is one issue to one PR, so #2904 stays out.

## Change log

- `2026-10-31T08:51:10.236274+00:00` — opened
- `2026-10-31T08:51:15.370908+00:00` — resolved (final_answer="Confirm scope as written")
