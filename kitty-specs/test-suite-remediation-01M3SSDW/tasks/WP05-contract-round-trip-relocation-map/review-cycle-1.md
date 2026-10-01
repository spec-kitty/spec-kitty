---
affected_files: []
cycle_number: 1
mission_slug: test-suite-remediation-01M3SSDW
reproduction_command:
reviewed_at: '2026-09-30T21:48:55Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback (reviewer-renata), cycle 1

The WP is very close. Diff scope, the four map rows, the fail-loud import path, the dead-row self-test, the counts (32 passed, 0 skipped; baseline 19 passed / 10 skipped re-confirmed), ruff, format, mypy, skip hygiene, ratchet baselines (42 passed) and `make test-fast` (2169 passed, 0 failed) all check out. The in-process product-break substitute (probe2) is accepted as sound C-011 evidence; see the note at the end.

One blocking issue, one small recommendation.

## Issue 1 (BLOCKING): the longest-prefix unit test does not pin the production sort (surviving mutant)

`test_canonical_module_name_prefers_longest_prefix` monkeypatches **both** `HISTORICAL_TO_CANONICAL` **and** `_SORTED_HISTORICAL_KEYS`. It recomputes the sorted tuple itself:

```python
monkeypatch.setattr(
    _module_relocations,
    "_SORTED_HISTORICAL_KEYS",
    tuple(sorted(synthetic, key=lambda key: key.count("."), reverse=True)),
)
```

So the production ordering expression in `_module_relocations.py:42` is never executed by any test. Reviewer plant, which I ran and restored byte-exact (sha256 `3b3df919...dfab` before and after):

- Mutation: `tests/contract/_module_relocations.py::_SORTED_HISTORICAL_KEYS::reverse=True -> reverse=False`.
- Command: `uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -p no:randomly`.
- Result: **32 passed**. The mutant survives.

The test's docstring says it pins "the tie-breaking … directly", and the WP Risks section says "The unit test pins this". It does not: the tie-break is decided entirely by the sort, and the test supplies its own sort. The live map has no overlapping keys today, so the full round-trip cannot catch it either. This mission remediates tests that do not test what they claim, so the new test must hold its claimed pin.

**Fix (small):** make the production code derive the order from the map, so the test only needs to patch the map. Any one of these works:

- (a) Compute the order inside `canonical_module_name`, e.g. `for key in sorted(HISTORICAL_TO_CANONICAL, key=lambda k: k.count("."), reverse=True):`. Then drop `_SORTED_HISTORICAL_KEYS`; no caching is needed per the WP.
- (b) Give `canonical_module_name` an optional `mapping: Mapping[str, str] = HISTORICAL_TO_CANONICAL` parameter that sorts internally, and have the test pass the synthetic map with no monkeypatch at all.
- (c) Extract `_sorted_keys(mapping)` and have the module constant and the test both call it; the test then patches only `HISTORICAL_TO_CANONICAL` and recomputes through the production helper.

Then re-run the mutation above and record it as a fourth plant: `reverse=False` must turn `test_canonical_module_name_prefers_longest_prefix` RED (`"a.b.c.d"` would resolve to `canonical.coarse.c.d`), and it must be GREEN after the revert. Keep the synthetic keys `a.b` / `a.b.c`; they are a good discriminating pair.

## Recommendation (non-blocking): direct tests for the two `import_contract_module` error branches

Both `ImportError` branches (`no relocation row matches`; `neither X nor canonical Y`) are exercised today only by planted breaks, not by the committed suite. CLAUDE.md asks that every new branch/helper gets a test in the same PR. Coverage is `src/`-scoped, so this does not affect the diff-cover gate. Two tiny tests would pin the fail-loud messages the WP exists to guarantee:

- an unmapped missing module (e.g. `"nonexistent_pkg_xyz.mod"`): `pytest.raises(ImportError, match="no relocation row matches")`;
- a mapped key whose canonical target is missing (use a synthetic map via the Issue 1 fix): `match="neither .* nor canonical"`.

(I verified the second branch by a scratch plant: redirecting `doctrine.drg` to `charter.offering.drg_moved_away` gives 4 round-trip FAILs reading `neither ``doctrine.drg.models`` nor canonical ``charter.offering.drg_moved_away.models`` is importable`, plus the targets-importable self-test red. The behavior is right; it is just not pinned by a committed test.)

## Notes (no action required)

- **Break #11 wording.** With the row deleted, the message names the historical module plus "no relocation row matches"; it cannot name a canonical module that the map no longer knows. That follows T021 step 4 exactly. The Review Guidance line "names both module names" is a spec-internal inconsistency, not an implementation defect; the "both names" branch is the broken-target case above.
- **Product-break substitute (C-011).** Accepted. `wp05_product_break_probe2.py` drives the REAL, unmodified `test_contract_example_round_trip` with the real `_ALL_CASES` entry (the real archived payload) through the real `import_contract_module` -> `getattr(module, class_name)` path. Patching the module attribute is exactly the seam the test reads at runtime. The stand-in only drops `provenance` and the URN validator, which makes it less strict, so it cannot manufacture a red. My control subclassed the real `DRGEdge`, keeping its validator, and renamed `source` via `validation_alias`. The real test fn went RED on `model_validate`, and was GREEN with no patch and again after patch exit. `probe.py` (probe1) needs `PYTHONPATH=.` as the evidence says; standalone it raises `ModuleNotFoundError: tests`.
- The evidence records do not mention `make test-fast` (T023 step 7). I ran it: 2169 passed, 5 skipped, 0 failed. Please include your own run in the next for_review note.
