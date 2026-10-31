# Data model: opaque failure identity (#6751)

No new persistence format. Two existing in-memory records gain defaulted fields; the on-disk `baseline-tests.json` schema is extended additively and stays loadable in both directions.

## `BaselineFailure` (`review/baseline.py`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `test` | `str` | required | Fully qualified test name, or `OPAQUE_FAILURE_TEST_ID` when the run failed without a parseable per-failure identity. |
| `error` | `str` | required | One-line summary (max 200 chars). For an opaque failure this is the comparable part of its identity, so it is stored verbatim (the last non-empty line of stderr, else stdout). |
| `file` | `str` | required | `file:line`, or `"unknown"`. |
| `opaque` | `bool` | `False` | True only for the synthetic whole-run placeholder. Marks that `test` is not an identity of its own. |
| `exit_code` | `int \| None` | `None` | The declared command's observed exit status; set for opaque failures, `None` for named failures and for pre-change artifacts. |
| `output_digest` | `str \| None` | `None` | Opaque failures only: a 16-hex digest of the run's FULL output tail (newlines canonicalised). The one-line `error` is display text, not identity — unrelated failures routinely share a generic last line (`make: *** [Makefile:1: all] Error 1`), so the digest is what binds. `None` for named failures and pre-change artifacts; an opaque entry without one never matches. |

### Identity rules used by `diff_baseline`

| Baseline | Candidate | Same failure? | Why |
|---|---|---|---|
| named `x` | named `x` | yes | The name is the identity (unchanged behaviour). |
| named `x` | named `y` | no | Names differ (unchanged). |
| named `x` | opaque | no | An opaque placeholder can never stand in for a named test. |
| opaque `(2, digest A)` | opaque `(2, digest A)` | **yes** | Exact bound identity. |
| opaque `(2, digest A)` | opaque `(1, digest B)` | **no** | Different exit status and output → new failure. |
| opaque `(2, digest A)` | opaque `(2, digest B)` | **no** | Same exit status, different output → new failure (the `make`-style shared-tail case). |
| opaque `(1, digest A)` | opaque `(1, digest A)` | **yes** | Same exit status and same full output → pre-existing. |
| opaque `(None, None)` (legacy artifact) | opaque `(2, digest A)` | **no** | Unknown identity cannot be verified equal (fail-closed). |

Two opaque failures never match a named one; duplicates of a named test keep the incumbent name-set behaviour (a name present in the baseline is pre-existing no matter how many candidate entries carry it).

### Serialization

`to_dict` emits `opaque`, `exit_code` and `output_digest` only when they carry information, so a pre-change NAMED record round-trips byte-identically (a legacy opaque record is upgraded in place with its inferred `opaque` marker on its next save, and still has no exit status or digest, so it can never verify-equal a candidate). `from_dict` reads them with `data.get(...)`; when `opaque` is absent it is inferred from `test == OPAQUE_FAILURE_TEST_ID`, so a legacy artifact written before this change cannot silently regain the name-only collision.

## `OPAQUE_FAILURE_TEST_ID`

Moves to `review/baseline.py` beside `BaselineFailure` (the data model that owns the identity) as the single canonical constant; `scope_source.py` imports it lazily next to `BaselineFailure`, exactly as it already does for the type. No second sentinel literal remains.

## `GateVerdict` (`review/pre_review_gate.py`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `candidate_exit_code` | `int \| None` | `None` | The candidate command's observed exit status when the classifier had one (declared-command path). `None` for verdicts reached before a run (no coverage, skipped, oversized, uncomputable baseline, source mismatch) and for the legacy JUnit branch. |

### Verdict surface

- `NO_NEW_FAILURES` with a known exit status gains a `reason`:
  `"baseline-relative: candidate declared command exited <n>; <p> pre-existing failure(s), 0 new — this verdict does not assert a clean candidate exit"`, plus, when the run failed opaquely and matched, a clause naming the matched opaque identity.
- The renderer appends that reason to the existing dim line only when it is present; the fixture verdict (`reason: null`) renders the base string unchanged.
- No new metadata key: `_mt_pre_review_gate_metadata` already records `reason`, and the parity oracle asserts exact metadata equality (research: "Constraint discovered").
- `NEW_FAILURES`, the opt-in block predicate, `UNVERIFIED_BASELINE` and `SOURCE_MISMATCH` carry no new reason text.
