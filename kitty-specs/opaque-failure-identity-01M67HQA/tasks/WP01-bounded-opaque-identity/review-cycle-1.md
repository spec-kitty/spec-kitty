---
affected_files:
- src/specify_cli/review/baseline.py
- src/specify_cli/review/scope_source.py
- tests/review/test_opaque_failure_identity.py
- tests/review/test_scope_source.py
cycle_number: 1
mission_slug: opaque-failure-identity-01M67HQA
reproduction_command: ../../.venv/bin/python -m pytest tests/review/test_opaque_failure_identity.py tests/review/test_scope_source.py tests/review/test_baseline.py -q
reviewed_at: '2026-10-30T23:58:00Z'
reviewer_agent: reviewer-renata
verdict: approved
wp_id: WP01
---

## Review Verdict: APPROVED (with one should-fix folded in cycle 1)

**Reviewer:** `reviewer-renata` (independent reviewer model, `tokenfactory/glm-5.3`).
**Diff reviewed:** `df790bd99a..31cd26f452` plus the fold commit `d3a000cff*` (digest
identity). Red-first commit: `df790bd99a`.

### Verified

- The identity rule in `_matches_baseline_failure` keeps named↔named matching
  name-only (incumbent), forbids named↔opaque in both directions, and requires
  opaque↔opaque to match on the bound identity.
- Duplicate names still use per-name candidate lists, so the incumbent
  duplicate-name pre-existing behaviour is unchanged.
- `failed == -1` (sentinel/uncomputable) still short-circuits to "everything new"
  and never reaches the opaque comparison.
- The repro (`test_differing_opaque_candidate_failure_is_a_new_failure`) is a
  genuine behavioural red: it builds failures through
  `DeclaredCommandScopeSource.parse_results`, so on the base tree it classifies
  `no_new_failures`.
- Back-compat: all `BaselineFailure` construction sites use keyword arguments; the
  new fields are trailing defaults; a pre-change NAMED payload round-trips
  unchanged; a pre-change opaque record is inferred opaque and has no exit status
  or digest, so it can never verify-equal a known candidate.
- No gate weakened: the opaque comparison is strictly narrower than before, and a
  nonzero unparseable exit still always yields a failure entry.

### Finding 1 (should-fix, folded in this cycle): the last-line summary is not an identity

**Severity:** should-fix. **File:** `baseline.py::_matches_baseline_failure`,
`scope_source.py::_whole_run_failure`.

The one-line `error` is only the last line of the output. Unrelated failures
routinely share a generic last line — `make` ends any recipe failure with
`make: *** [Makefile:1: all] Error 1` — so binding the identity to exit status +
summary still let a real regression through whenever the wrapper normalises the
tail (reviewer's probe: two different `real bug A/B` messages, same exit, same
`make` tail → classified pre-existing).

**Resolution:** the failure now records `output_digest` (a digest of the run's FULL
output tail, newline-canonicalised) and the comparator requires exit status AND
digest to match. `error` stays display text. An opaque entry without a digest
(legacy artifact) never matches, so the fail-closed direction is preserved.
Regression test: `test_shared_generic_last_line_is_not_an_identity`.

### Finding 2 (nit, fixed): `to_dict` byte-identical comment

The comment claimed a pre-change record round-trips byte-identically, which is
false for a legacy opaque record (its `opaque` marker is re-derived on load and
written on the next save). The comment now says exactly that, and the behaviour
stays safe (no exit status, no digest → never an identity match).

### Finding 3 (nit, documented): the `fixed` list stays name-based

The sole caller (`_classify_current_failures`) discards `_fixed`, so there is no
behaviour change. The docstring now states that an opaque placeholder leaving the
current set is the honest entry to report.

### Finding 4 (nit, accepted as designed): red-commit construction errors

Two red-commit tests fail pre-fix on `TypeError`/`AttributeError` (they construct
the new fields), not behaviourally. The behavioural red is the counterexample
test above; the field-shape assertions are deliberate coverage of the new data
model, not the primary repro.

### Validation run in this cycle

- `tests/review/test_opaque_failure_identity.py` — 11 passed.
- `tests/review/test_scope_source.py`, `test_baseline.py`,
  `test_baseline_lifecycle.py`, `test_pre_review_gate_engine.py`,
  `test_transition_gate_parity.py`, `test_baseline_head_parity.py` — 151 passed,
  1 skipped.
- `ruff check` clean on the four touched files; `ruff format --check
  --force-exclude` clean (`baseline.py` is a pre-existing formatter-ratchet entry
  and is deliberately left unformatted).
- mypy: the two errors the files report (`scope_source.py:340`,
  `baseline.py:603`) are pre-existing on `main` (same code, same messages); no new
  error is introduced.
