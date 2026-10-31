# Contract: declared-command failure identity and verdict evidence (#6751)

This mission changes two internal contracts of the pre-review regression gate. Both
are behavioural; neither adds a public CLI flag, config key or artifact schema that
a consumer must opt into.

## 1. Failure identity (`review/baseline.py`, `review/scope_source.py`)

The gate compares a candidate run against a baseline captured on the base commit.
A record in either set is a `BaselineFailure`.

| Shape | Identity used by `diff_baseline` |
|---|---|
| Named (`FAIL <name>: <message>`, JUnit `classname.name`) | The test **name**. A baseline name that reappears is pre-existing, even if its message changed (unchanged behaviour). |
| Opaque (`OPAQUE_FAILURE_TEST_ID`, produced only by `_whole_run_failure` when the declared command exited nonzero with no parseable failure line) | `(exit_code, output_digest)`. `error` is display text, not identity. |

Rules:

1. A named and an opaque record never match, in either direction.
2. Two opaque records match only when `exit_code` and `output_digest` are both
   present and equal. `output_digest` is a digest of the run's full output tail
   (stderr if non-empty, else stdout; `\r\n` canonicalised, stripped).
3. A record written before this change loads with `opaque` inferred from the
   placeholder name and with `exit_code`/`output_digest` absent, so it can never
   verify-equal a candidate whose identity is known (fail-closed).
4. A candidate opaque failure with no matching baseline opaque record is a **new
   failure**. There is no path by which an unparseable nonzero result is treated
   as a pass on the strength of the placeholder name.
5. `baseline.failed == -1` (uncomputable baseline) is unchanged: every current
   failure is surfaced as unverified.

## 2. Verdict evidence (`review/pre_review_gate.py`, transition hook)

`GateVerdict` carries `candidate_exit_code` when the injected `ScopeSource` path
classified a completed run (including `UNVERIFIED_BASELINE`). It is `None` for
verdicts reached before a completed run and for the legacy JUnit branch.

A `NO_NEW_FAILURES` verdict reached with a known exit status carries a
baseline-relative `reason`:

```
baseline-relative: candidate declared command exited <n>; <p> pre-existing failure(s), 0 new[ — this verdict does not assert a clean candidate exit][; the opaque whole-run failure matches the baseline exactly (exit <n>/digest <d>)]
```

The `does not assert a clean candidate exit` clause is present only for a nonzero
run; the opaque clause only when an opaque failure was matched.

Constraints that hold this contract in place:

- No metadata key is added (`_mt_pre_review_gate_metadata` is unchanged), because
  `tests/review/test_transition_gate_parity.py` asserts exact metadata equality
  against base-captured fixtures. The reason rides on the existing `reason` field.
- The console line for a verdict with no reason stays byte-identical:
  `[dim]Pre-review regression gate: no new failures[/dim]`.
- The opt-in block predicate (`block_enabled AND any(NEW_FAILURES) AND not force`)
  and the terminal precedence are untouched: an exit status alone never blocks.
