# Decision Moment `01M4XV6HM7WHEB2B8QG67N29HT`

- **Mission:** `main-red-test-premise-repair-01M4XV67`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.dependency-bump-shard-selection`
- **Input key:** `dependency_bump_shard_selection`
- **Status:** `resolved`
- **Created:** `2026-10-14T18:36:07.175610+00:00`
- **Resolved:** `2026-10-14T18:38:01.848711+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

Should this mission also make a dependency bump (pyproject.toml / uv.lock) select the upgrade and status module shards in ci-router, or leave that CI-cost decision out of scope?

## Options

- Out of scope; name it in the PR (recommended)
- Fold in: uv.lock + pyproject.toml fan out to upgrade + status
- Fold in narrowly: only .kittify/release/shared-package-compatibility.json
- Other

## Final answer

Fold in: uv.lock changes select the upgrade and status module shards; pyproject.toml does not (a rename / non-version pyproject change must not trigger the upgrade shards)

## Rationale

_(none)_

## Change log

- `2026-10-14T18:36:07.175610+00:00` — opened
- `2026-10-14T18:38:01.848711+00:00` — resolved (final_answer="Fold in: uv.lock changes select the upgrade and status module shards; pyproject.toml does not (a rename / non-version pyproject change must not trigger the upgrade shards)")
