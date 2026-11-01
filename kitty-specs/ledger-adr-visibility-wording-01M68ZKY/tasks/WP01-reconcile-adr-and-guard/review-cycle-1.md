---
affected_files: []
cycle_number: 1
mission_slug: ledger-adr-visibility-wording-01M68ZKY
reproduction_command:
reviewed_at: '2026-10-31T12:59:57Z'
reviewer_agent: user
wp_id: WP01
---

# Review round 1 — WP01

Verdict: **changes requested** (1 finding; the rest passes).

## What I verified

- `git diff origin/main..HEAD --stat` touches only the ADR, the regenerated retrieval index and
  the new docs guard. No `src/` change (C-002), no alias added (C-001).
- Red-first proof reproduces: on `0b3582f9` (guard added, ADR unedited) both guard tests fail with
  `['doctor migrations']` named as unregistered; on `75578502` they pass.
- ADR §5 and #E name `spec-kitty migrate ledger` (`--json`) and the single pending source
  `VersionDetector.applicable_migrations`; the §5 heading now says "one read surface".
- §5's partition/pending/drift statements match `migrate_cmd.py` (`_STATE_IN_PLACE`,
  `_STATE_RECORDED_ELSEWHERE`, `_STATE_PENDING`, `_DRIFT_HUMAN`, "never re-applied").
- `check_docs_freshness --ci` → errors=0; `tests/docs` ADR suite → 139 passed.
- Anti-pattern checklist: 1 N/A (no new production code), 2 PASS (the guard reads the real ADR and
  the live Typer app; deleting the fix reds it), 3 PASS (no swallow paths), 4 **FAIL (see F1)**,
  5 PASS (no frozen surface touched), 6 PASS (`spec.md` C-001/C-002 honoured), 7 PASS (single WP
  touches these files), 8 PASS (no new `raise` in production code).

## F1 (medium) — FR-003 is not asserted by the guard

FR-003 requires the original `doctor migrations` / `upgrade --list-applied` proposal to be
*retained and explicitly marked historical*. The guard only proves two things: the shipped surface
is named, and no unregistered path is named. A future edit that deletes the historical paragraph
would pass both assertions, silently losing the decision trail, and a future edit that removes the
"historical" label but keeps the bare names would also pass.

Please extend `tests/docs/test_migration_ledger_adr_visibility.py` with an assertion over §5 that:

1. the retired spellings are still present (`doctor migrations` and `upgrade --list-applied`), and
2. the paragraph carrying them says it is historical (e.g. a case-insensitive "historical" /
   "not built" marker within §5), rather than presenting them as current.

Keep the scan on §5 (the #E bullet may summarise without repeating the marker). Do not assert
exact sentences — check the presence of the two names plus the historical marker, so the wording
can still be edited.

## Note (no action)

The §5 heading rename forces the `docs-retrieval-index.yaml` anchor change; that regeneration is
correctly scoped to the one line.
