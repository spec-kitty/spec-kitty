# Helper Contracts — extracted CI helpers

Function-level contracts for the two modules this mission extracts. These are the RED-first pins.

## `scripts/ci/reconcile_shards.py` (#4360-B)

```
reconcile(
    registry_shards: Sequence[RegistryShard],
    selected: Optional[Set[str]],        # module names the matrix selected; None = full mode
    current_fresh: Set[Tuple[str, int]], # (module, shard_index) present in this run
    previous_available: Set[Tuple[str, int]],  # backfillable from a prior eligible run
) -> CompletenessResult                  # {complete: bool, missing: list[RegistryShard]}
```

Contract:
1. **C-recon-1 (RED today)**: `selected={"M"}`, current_fresh has all of M's shards, `previous_available`
   empty → `complete=True, missing=[]`. (Today: `complete=False, missing=[<the other 36>]`.)
2. **C-recon-2 (false-green guard, must_be_fresh)**: `selected={"M"}`, M's shard NOT in current_fresh
   (even if in `previous_available`) → M's shard ∈ `missing`, `complete=False`.
3. **C-recon-3 (legacy)**: `selected=None` → every registry shard required; original all-registry
   backfill behaviour unchanged.
4. **C-recon-4 (unselected optional)**: `selected={"M"}`, an unselected module U absent from both
   current and previous → U NOT in `missing`, does not affect `complete`.

The `ci-aggregate.yml` step imports and calls `reconcile(...)`; the fail-closed guard
(`ci-aggregate.yml:376-381`) still fires on a non-empty `missing`.

## `scripts/ci/router_gate.py` (#4208)

```
classify(conclusions: Mapping[str, str]) -> GateDecision   # {blocking: dict, blocks: bool}
```

Contract:
1. **C-gate-1 (RED today)**: `classify({"tests-cli": "timed_out", "tests-e2e": "failure"})` reports
   `tests-cli` labelled `timed_out` (distinct from `cancelled`) AND `blocks=True`.
2. **C-gate-2 (blocking policy unchanged)**: `classify({"tests-cli": "cancelled", "tests-e2e": "cancelled"})`
   → `blocks=True` (byte-identical verdict to baseline).
3. **C-gate-3**: `classify({...all success...})` → `blocks=False`.
4. **C-gate-4**: a merely-`skipped` dependency is not blocking (preserves existing
   `test_dual_mode_contract.py` behaviour).

The router-gate step populates `conclusions` from the Actions jobs API (the `needs` context cannot
carry `timed_out`), then calls `classify(...)`.

## Adversarial-evidence contract

`contracts/adversarial-evidence-contract.md` (repo convention): every contested design finding from
the research squad is recorded in `research.md` with disposition `accepted | changed |
deferred_with_rationale`. Satisfied — see research.md §"Adversarial Evidence".
