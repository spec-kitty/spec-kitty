# Research: Deep ROI pass over the large tests/charter suites

## Baseline (2026-10-19, branch tip 65d004b, stacked on PR #6483)

Command:
`PWHEADLESS=1 .venv/bin/python -m pytest tests/charter tests/charter_offering -n auto --dist loadfile -q -p no:cacheprovider --cov=src/charter --durations=0`

- Result: 8503 passed, 29 skipped in 243.10 s (wall clock, xdist).
- `src/charter` line coverage: **95.93%**. NFR-002 floor: 94.93%.

Heaviest `tests/charter` files by summed test time (seconds, call + setup):

| File | s | In #6485 list |
|------|---|---------------|
| test_compiler_charter_yaml.py | 171 | no → WP06 |
| test_context_unknown_language.py | 142 | no → WP06 |
| test_regenerate_rederives_languages.py | 135 | no → WP06 |
| packs/test_pack_validator.py | 129 | yes (WP03) |
| test_progressive_disclosure.py | 120 | no → WP06 |
| test_every_load_delivery.py | 104 | no → WP06 |
| test_active_languages_idempotency.py | 88 | no → WP06 |
| test_retrospective_governance_emit.py | 47 | no → WP06 |
| test_activation_preserves_effective_4253.py | 35 | no → WP06 |
| activation/test_effective_set.py | 35 | yes (WP04) |

## Decisions

- **Deletion bar**: consolidate. Delete with a named covering test, or merge/parametrize near-duplicates. Rationale: operator ruling at specify. Alternative (strict delete-only) rejected: it leaves near-duplicate pairs in place.
- **Coverage**: a slight drop is allowed for low-ROI removals; budget 1.0 pp. Rationale: operator steer ("little point in keeping a clunky/flaky/heavy test for a marginal coverage improvement").
- **Heavy tests**: added as WP06 (operator decision at plan). Rationale: the slowest tests sit outside the issue's list.
- **Slicing**: six WPs on disjoint file sets → parallel lanes, no merge conflicts between them.
