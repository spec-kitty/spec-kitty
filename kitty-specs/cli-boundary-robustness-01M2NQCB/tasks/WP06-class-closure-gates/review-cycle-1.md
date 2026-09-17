---
affected_files: []
cycle_number: 1
mission_slug: cli-boundary-robustness-01M2NQCB
reproduction_command:
reviewed_at: '2026-09-16T22:16:48Z'
reviewer_agent: user
wp_id: WP06
---

## Review verdict: rejected

### 1. The parse allow-list is vacuous outside the adopted subset

`_classification()` classifies all paths not present in `_ADOPTED_PATHS` as
`non-parseable-deferred`. On the reviewed tree this produces 9
`adopted-shape`, 0 `already-parseable`, and 162
`non-parseable-deferred` records. No one-time behavioral probing or triage was
performed for those 162 paths, and the only error-arm test drives the nine
adopted cases.

This violates T026/T027/T030, the enumeration-gate contract, Amendment B, and
NFR-001: the allow-list must be `adopted-shape` plus every command verified to
be already parseable; only commands actually shown to be non-parseable may be
deferred. A discovery fingerprint proves inventory stability, but it does not
prove behavior and cannot substitute for classification.

Fix this by replacing the catch-all classifier with explicit reviewed records
for all 171 discovered public paths. Give each deferred path its own rationale
and follow-up identity, add deterministic error drivers for all adopted and
verified-already-parseable paths, and parameterize the parse assertion over the
entire resulting allow-list. The classification/driver relationship must fail
if a path is missing a driver or if an unclassified path appears. Retain the
structural fingerprint as an additional drift guard.

### 2. The deferred evidence is neither explicit nor traceable

The test records a single `_DEFERRED_FOLLOW_UP = "#4646"`, but only asserts
that `events tail` is deferred. The other 161 excluded paths have no explicit
record, no behavioral evidence, and no per-path rationale. Several are plainly
unrelated to the OptionInfo-family tracker described by #4646, so this does not
satisfy the required classification record fields or T030's reviewability
requirement.

Make deferred membership an explicit immutable data set keyed by public path
and callback identity, with a concrete non-parseability rationale and the
appropriate parse-convergence follow-up for every excluded path. Do not use a
broad default-to-deferred rule.

## Verification evidence

- `PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_cli_boundary_contract_enumeration.py -q`: 16 passed.
- Direct evaluation of `_discover_json_contracts()` and `_classification()`:
  `Counter({'non-parseable-deferred': 162, 'adopted-shape': 9})`.
- The five callback cases execute and show no placeholder repr, and the empty
  status fixture is a production-path test. These portions are acceptable but
  cannot compensate for the missing class-wide parseability gate.

## WP anti-pattern checklist

1. Dead code: PASS (test-only public helpers are exercised within the gate).
2. Synthetic-fixture test: PASS (behavior tests invoke production Typer apps).
3. Silent empty return: PASS.
4. FR coverage: FAIL (FR-005/FR-007/NFR-001 class coverage is not exercised for 162 discovered paths).
5. Frozen surface: PASS (WP06 commit adds only its owned architectural test file).
6. Locked decision: FAIL (the required adopted + verified-parseable allow-list is reduced to adopted only).
7. Shared-file ownership: PASS (WP06's implementation commit touches only its owned file).
8. Production fragility: N/A (no production code changed).
