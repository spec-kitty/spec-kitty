# IC-05 — Contract round-trip relocation map (WP05)

Materialized at closeout from WP05's reported evidence (scratchpad `wp05_evidence.md`), the
reviewer's cycle-1 feedback (`tasks/WP05-.../review-cycle-1.md`), which rejected cycle 1 on
one blocking issue (a surviving mutant) and one non-blocking recommendation, and the
reviewer's full cycle-2 approval note (`status.events.jsonl`,
`review_ref: auto-approval:WP05:20260930`); both cycle-1 findings were addressed in cycle 2.

## Baseline / after

- Baseline: `uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs` -> `19 passed, 10 skipped in 48.43s` (10 skips: missing-module imports for `doctrine.drg.models`/`.org_pack_config`, `charter.schemas`, `charter.scope`, `specify_cli.next._internal_runtime.workflow_schema`).
- Cycle 1 after: `32 passed in 33.29s` (0 skipped) = 29 round-trip cases + 3 map self-tests.
- Cycle 2 after (post-fix, +2 new unit tests): `34 passed in 0.82s` (0 skipped) = 29 round-trip cases + 5 self/unit tests.
- NFR-001: 34 >= 19 + 10 = 29 (holds; +5 self/unit tests on top).

## MG-16 Plant 1 — Break #11: delete the `doctrine.drg` row

```yaml
id: EV-IC05-01
item: MG-16 (Plant 1 / Break #11)
kind: FIX
planted_break:
  target: "tests/contract/_module_relocations.py::HISTORICAL_TO_CANONICAL"
  description: 'delete the "doctrine.drg": "charter.offering.drg" row'
  reverted: true   # file is new/untracked; manually restored, content verified identical to the original Write
command: 'uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs -k "pack-validator-advisory or config-schema-delta or module_relocation"'
results:
  old_form_under_break: "SKIPPED (equivalent pre-WP baseline state, same effective missing-module condition, x4)"
  new_form_under_break: >
    FAIL — 4 failed, 2 passed, 26 deselected: "pydantic_model module is not importable:
    ``doctrine.drg.models`` is not importable and no relocation row matches in
    ``tests/contract/_module_relocations.py``: No module named 'doctrine'" (and the same for
    org_pack_config). test_module_relocation_keys_are_referenced_by_an_archived_contract
    stayed PASSED under this break (it only iterates existing rows), exactly as predicted.
  clean_tree: "32 passed in 0.99s"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: false
notes: "Naming clarified in cycle-1 review: the failure names both distinct HISTORICAL module names affected (doctrine.drg.models, doctrine.drg.org_pack_config), not a historical+canonical pair for one case — that latter shape is EV-IC05-05's 'neither X nor canonical Y' branch."
```

## MG-16 Plant 2 — dead row self-test

```yaml
id: EV-IC05-02
item: MG-16 (Plant 2, dead row)
kind: FIX
planted_break:
  target: "tests/contract/_module_relocations.py::HISTORICAL_TO_CANONICAL"
  description: 'add a "nonexistent.module": "charter.offering.drg" row referenced by no archived contract'
  reverted: true
command: 'uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs -k "test_module_relocation_keys_are_referenced_by_an_archived_contract"'
results:
  old_form_under_break: "n/a — the self-test and the map are new in this WP"
  new_form_under_break: "FAIL — 1 failed, 31 deselected: AssertionError: relocation row 'nonexistent.module' is a dead row: no archived contract references it"
  clean_tree: "32 passed in 0.78s"
reviewer_rerun: false
```

## MG-16 Plant 3 — product break: rename `DRGEdge.source` to `DRGEdge.source_urn`

```yaml
id: EV-IC05-03
item: MG-16 (Plant 3, product break simulation)
kind: FIX
planted_break:
  target: "src/charter/offering/drg/models.py::DRGEdge"
  description: >
    rename field "source" -> "source_urn". Direct on-disk Edit/Write was denied by the
    sandbox's permission classifier ("Modify Shared Resources" — multiple lanes editing
    src/ concurrently). Per harness rules, NOT worked around with a different tool/host.
    Instead demonstrated in-process, with ZERO on-disk mutation, via
    unittest.mock.patch.object swapping in a structurally-renamed stand-in class for
    charter.offering.drg.models.DRGEdge for the duration of one Python process, calling the
    REAL, unmodified test_contract_example_round_trip function against the real
    archived-contract payload.
  reverted: true   # no repo file ever changed; git diff --stat src/ confirmed empty throughout
command: "PYTHONPATH=. uv run --frozen python <scratchpad>/wp05_product_break_probe.py ; PYTHONPATH=. uv run --frozen python <scratchpad>/wp05_product_break_probe2.py"
results:
  old_form_under_break: "n/a — this plant targets the NEW import_contract_module/model_validate path this WP wires up"
  new_form_under_break: >
    FAIL — the real, unmodified test function raised pytest.fail():
    "2 validation errors for DRGEdgeRenamed: source_urn Field required [...]; source Extra
    inputs are not permitted [...]"
  clean_tree: "32 passed in 0.83s (unaffected real suite)"
reviewer_rerun: false
notes: >
  Accepted by the reviewer in cycle 1 as sound C-011 evidence ("the stand-in only drops
  provenance and the URN validator, which makes it less strict, so it cannot manufacture a
  red"). The reviewer additionally built their OWN independent control (subclassing the real
  DRGEdge, keeping its validator, renaming source via validation_alias) and confirmed the real
  test function went RED on model_validate, GREEN with no patch and again after patch exit —
  see EV-IC05-04 below, where this independent reviewer verification is recorded against
  Plant 4 (the cycle-2 blocker fix), the item the reviewer actually reran end-to-end.
```

## Cycle 2 — Plant 4: the reviewer's mutant (blocking issue, fixed)

```yaml
id: EV-IC05-04
item: MG-16 (Plant 4, cycle-2 blocker fix)
kind: FIX
planted_break:
  target: "tests/contract/_module_relocations.py::canonical_module_name"
  description: >
    sorted(HISTORICAL_TO_CANONICAL, key=lambda k: k.count("."), reverse=True) -> reverse=False.
    Cycle-1 form of test_canonical_module_name_prefers_longest_prefix monkeypatched BOTH
    HISTORICAL_TO_CANONICAL and a separate _SORTED_HISTORICAL_KEYS module constant, recomputing
    the sort itself — so production's own sort expression was never executed by any committed
    test, and this mutant survived under cycle-1's form (32 passed).
  reverted: true   # file sha256 before/after plant: 200f10a39d102f1862dcb7a22eeaf5335f6a42b2b62303384208a90d51bd71ab (byte-identical)
command: "uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -p no:randomly"
results:
  old_form_under_break: "GREEN (mutant SURVIVED) — reviewer-verified independently in cycle 1: 32 passed"
  new_form_under_break: >
    RED (cycle-2 fix applied: _SORTED_HISTORICAL_KEYS dropped entirely; the sort is now
    computed inline in canonical_module_name on every call, from HISTORICAL_TO_CANONICAL
    directly, so the test necessarily runs the real production sort) —
    1 failed, 33 passed: AssertionError: assert 'canonical.coarse.c.d' == 'canonical.fine.d'
  clean_tree: "34 passed in 0.82s, 0 skipped"
reviewer_rerun: true
notes: >
  Reviewer re-run, cycle 1 (tasks/WP05-.../review-cycle-1.md): "Reviewer plant, which I ran
  and restored byte-exact (sha256 3b3df919...dfab before and after) ... Result: 32 passed. The
  mutant survives." Reviewer re-run, cycle 2 (approval note, auto-approval:WP05:20260930):
  "Mutant reverse=True->False in canonical_module_name: 1 failed / 33 passed (AssertionError
  'canonical.coarse.c.d' == 'canonical.fine.d'); after restore, 34 passed" — the same mutant,
  now reproduced a second time against the FIXED form (RED as expected), byte-exact revert
  reconfirmed (sha256 200f10a3...71ab). Tallied in evidence/README.md.
```

## Cycle 2 — two new direct unit tests (non-blocking recommendation, addressed)

```yaml
id: EV-IC05-05
item: "test_import_contract_module_names_no_relocation_row_when_unmapped"
kind: FIX
command: "uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs"
results:
  clean_tree: "pass (part of the 34 passed run)"
reviewer_rerun: true
notes: >
  pytest.raises(ImportError, match='no relocation row matches') on
  import_contract_module('nonexistent_pkg_xyz.mod') — pins the canonical is None branch
  directly (previously only exercised by Plant 1). Reviewer re-run, cycle 2 (approval note):
  "Mutant swapping both import_contract_module error messages: 2 failed / 32 passed, i.e.
  both new unit tests (no-relocation-row and neither/nor-canonical) hit the real branches;
  after restore, 34 passed" — this record's test is the "no-relocation-row" half of that
  pair, independently confirmed to hit its real branch.
```

```yaml
id: EV-IC05-06
item: "test_import_contract_module_names_both_modules_when_canonical_also_missing"
kind: FIX
planted_break:
  target: "scratch: HISTORICAL_TO_CANONICAL monkeypatched to {'doctrine.drg': 'charter.offering.drg_moved_away'}"
  description: "redirects a historical module to a canonical target that is itself missing"
  reverted: true
command: "uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs"
results:
  new_form_under_break: "pytest.raises(ImportError, match=r'neither .* nor canonical .* is importable') on import_contract_module('doctrine.drg.models') — pins the 'neither X nor canonical Y' branch directly"
  clean_tree: "pass (part of the 34 passed run)"
reviewer_rerun: true
notes: >
  Reviewer re-run, cycle 1: "I verified the second branch by a scratch plant: redirecting
  doctrine.drg to charter.offering.drg_moved_away gives 4 round-trip FAILs reading 'neither
  ``doctrine.drg.models`` nor canonical ``charter.offering.drg_moved_away.models`` is
  importable', plus the targets-importable self-test red. The behavior is right; it is just
  not pinned by a committed test." The implementer formalized this exact scratch plant as the
  committed unit test above in cycle 2. Reviewer re-run, cycle 2 (approval note): "Mutant
  swapping both import_contract_module error messages: 2 failed / 32 passed, i.e. both new
  unit tests (no-relocation-row and neither/nor-canonical) hit the real branches; after
  restore, 34 passed" — this record's test is the "neither/nor-canonical" half of that pair,
  re-confirmed a second time against the committed test. Tallied in evidence/README.md.
```

## Quality gates / cross-checks

- `ruff check tests/contract/test_example_round_trip.py tests/contract/_module_relocations.py` -> All checks passed!
- `ruff format --check tests/contract/_module_relocations.py` -> 1 file already formatted (`test_example_round_trip.py` is format-excluded).
- `mypy tests/contract/_module_relocations.py` -> Success: no issues found in 1 source file.
- Skip hygiene (NFR-004): 0 matches for skip/xfail/importorskip markers in either file.
- `tests/architectural/test_ratchet_baselines.py` -> 42 passed (cycle 1 and cycle 2, including `test_fast_collection_does_not_import_round_trip_corpus`).
- `make test-fast` -> cycle 2: `2169 passed, 5 skipped, 4 warnings in 265.92s (0:04:25)`, exit 0; matches the reviewer's own independent cycle-1 run (2169 passed, 5 skipped, 0 failed).
- `git diff --stat src/` -> empty, confirmed multiple times including after both product-break plants (Plant 3 and Plant 4).
