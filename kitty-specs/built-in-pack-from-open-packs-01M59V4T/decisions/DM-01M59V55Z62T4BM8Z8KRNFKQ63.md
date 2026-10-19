# Decision Moment `01M59V55Z62T4BM8Z8KRNFKQ63`

- **Mission:** `built-in-pack-from-open-packs-01M59V4T`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.offline-dev`
- **Input key:** `offline_dev_fallback`
- **Status:** `resolved`
- **Created:** `2026-10-19T10:26:15.654051+00:00`
- **Resolved:** `2026-10-19T10:29:28.904868+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a git-checkout contributor or CI has no network and no fetched pack, what should happen?

## Options

- Fail loudly with run-X message; reuse a local cache dir if pinned SHA already fetched
- Fail loudly, no cache
- Other

## Final answer

Fail loudly with run-X message; reuse a local cache dir if pinned SHA already fetched

## Rationale

_(none)_

## Change log

- `2026-10-19T10:26:15.654051+00:00` — opened
- `2026-10-19T10:29:28.904868+00:00` — resolved (final_answer="Fail loudly with run-X message; reuse a local cache dir if pinned SHA already fetched")
