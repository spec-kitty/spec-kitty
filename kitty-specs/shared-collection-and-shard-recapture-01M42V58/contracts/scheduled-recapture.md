# Contract: generalised scheduled recapture

## `python -m scripts.ci.recapture_shard_timings`

| Option | Meaning |
|---|---|
| `--module NAME` (repeatable) | restrict to these registry modules; default is every registry module |
| `--budget-seconds N` | stop starting captures once N seconds have elapsed |
| `--write` | write refreshed data through the canonical producer; without it, report only |

Behaviour, in order:

1. Count-only pass: collect each candidate module's test count without running tests.
2. A module is **drifted** when its collected count differs from the committed count, or its provenance record is missing or not valid.
3. For each drifted module, longest-untouched first, while budget remains: run the canonical producer for that module in its own subprocess.
4. A capture is **valid** when its exit status is 0 or 1 and it recorded at least one duration (the shared predicate). An invalid capture leaves that module's committed data byte-identical.
5. Shard counts are not touched by the script; the existing skew check reports a count that no longer fits.
6. Print a machine-readable result (`drifted`, `captured`, `failed`, `deferred`) and a job-summary table.

Exit status: 0 when nothing failed (including "nothing drifted"); 1 when any capture failed.

## Workflow

- Triggers and the primary-branch gate are unchanged.
- A rejected push exits non-zero with a message naming the missing repository permission and the secret that supplies the token.
- Publication: no drift → no proposal. Drift and no open proposal → push the fixed proposal branch and open a pull request. Drift and an open proposal → add a follow-up commit on that branch (never a forced push).
- The strict agreement check stays in the same workflow as an independent job (no ordering between it and the recapture job, as before).

## Provenance completeness (`tests/architectural/test_shard_capture_provenance.py`)

- Every module in `.github/ci-module-registry.yml` has a valid provenance record; a failure names the module.
- Self-mutation: removing one module's provenance, and replacing it with an invalid record, each make the check fail on the same data.
- Shard counts are covered by the existing skew check in `tests/architectural/test_module_shard_registry.py`; this mission adds no second check.
