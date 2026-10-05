---
affected_files: []
cycle_number: 2
mission_slug: nightly-suites-green-01M44FEP
reproduction_command:
reviewed_at: '2026-10-05T06:46:42Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# WP02 review cycle 2: changes requested

Reviewer: reviewer-renata. One required change; the two cycle-1 changes are otherwise done.

1. **The mid8 shape check re-creates the original failure** (`src/specify_cli/missions/_read_path_resolver.py:952-959`, `:1008`, import at `:34`). No writer normalises case or checks shape: the seed names the directory verbatim from the recorded identity (`coordination/coord_seed.py:1195-1201`). For a recorded `mid8` of `01m5651a` or `01COORD0` the seed writes `foo-01m5651a` / `foo-01COORD0` and `mission_dir_aliases` returns no alias, so the seed commit is misrouted again (reproduced with the reproduction's Mission id lowercased: `MERGE_UNSAFE_WORKTREE_DIRTY`). The synthetic-slug shape check also accepts a value with a trailing newline. Delete `_is_canonical_mid8` and the `mid8_from_slug` import; gate on a non-empty mid8 plus a safe single segment for the composed name, so the alias equals what the composer writes. Flip the lowercase, single-character and 26-character unit cases to expect the composed alias, and add a test asserting the alias equals `coord_feature_dir(...).name` for lowercase and non-Crockford identities.

Note: the shape rule was added on the orchestrator's cycle-1 instruction, which was wrong on this point.

Verified: never raises on unsafe slugs; characterization green on the base and red at the alias commit; 269 behavioural and 398 gate tests pass; the uppercase reproduction still fails at the reconciliation gate with the seed committed.
