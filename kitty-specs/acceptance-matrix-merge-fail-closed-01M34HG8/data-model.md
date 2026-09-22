# Data Model: Fail-closed acceptance-matrix merge driver (#4880)

No new entities. This mission hardens an invariant on an existing one.

## AcceptanceMatrix (existing — `src/specify_cli/acceptance/matrix.py`)

- **criteria**: list of `AcceptanceCriterion`; each has `pass_fail ∈ {pass, fail, pending}` (`CRITERION_VERDICTS`).
- **negative_invariants**: list of `NegativeInvariant`; each has `result ∈ NEGATIVE_INVARIANT_RESULTS`.
- **overall_verdict** (*computed on read*): any `pass_fail`/`result` outside its enumeration ⇒ `"fail"`.

### Invariant introduced/enforced by this mission

- **INV-1**: No field of a matrix produced by the merge driver may contain a git
  conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`). Enforced at the write side
  by fail-closed reconciliation (IC-1) and at the read side by `from_dict`
  rejection (IC-3).
- **INV-2 (unchanged, clarified)**: `overall_verdict` is only trustworthy when
  every enumerated field holds an *authored* enumerated value. A marker string
  is not an authored value; INV-1 guarantees it never reaches recompute via the
  driver, and INV-2's existing fail-to-`fail` behavior for genuinely-authored
  out-of-domain tokens is retained (the `test_a4` control).

### State transition (merge reconciliation)

```
field diverged on both sides (add/add)?
  ├─ no  → auto-resolve (one-sided or identical) → valid matrix
  └─ yes → RAISE RowMatrixMergeError → Exit(1) → git leaves conflict → merge aborts (human resolves)
           (was: embed conflict-marker string as the value → exit 0 → silent corruption)
```
