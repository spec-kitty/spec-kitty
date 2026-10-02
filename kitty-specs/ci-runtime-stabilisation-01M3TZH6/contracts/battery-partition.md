# Contract: architectural battery partition

**Requirements**: FR-001, FR-003, FR-004, FR-005, FR-013, C-010 · **Design**: research.md D-01…D-06, R1 §1 and §4

## Single sources

- **Registry** (`.github/ci-module-registry.yml` → `special_tiers.architectural`): base selection (paths, marker expression, whole-file deselects owned by other always-on lanes), worker count (4), fast-gate roster (path, budget seconds, reason), shard count (2), timings key. Nothing else declares these values; workflows carry literal arguments that pin tests assert equal to the registry. The nightly backstop's location is deliberately **not** a registry fact (D-26): it is pinned only by WP04's tests (`tests/ci/test_nightly_architectural_backstop.py`, `tests/ci/test_nightly_exit_code_honesty.py`), which keeps the nightly work package off the registry lane.
- **Timings** (`.github/ci-shard-timings.json`, battery per-file durations): input to the shared selector only.
- **Selector** (`scripts/ci/shard_select.py`): the only LPT implementation, used in test granularity by module rows and in file granularity by the battery.

## Partition semantics

Let **B** be the base selection: the node-ids collected from `tests/architectural` with the base marker expression and deselects. Let **F**, **S1**, **S2** be the node-ids executed under `--battery-part fast`, `1/2`, `2/2`.

1. **Completeness**: F ∪ S1 ∪ S2 = B.
2. **Disjointness**: F, S1, S2 are pairwise disjoint.
3. **File granularity**: every test-module file of B belongs to exactly one part; the plugin never ignores directories, `conftest.py` or `_*.py` helpers, so an enumeration gap appears as an overlap (caught), never as a silent loss.
4. **Balance**: S1/S2 are assigned by the selector from per-file timings; a file without timing gets the median weight. A timing-set mismatch emits a `::warning::` and a step-summary line and never silently falls back to uniform weights for the battery.
5. **Nightly**: the backstop executes B with no partition flag, so its correctness does not depend on the partition code.

## Proof obligations

- A static test evaluates the three literal `--battery-part` commands through `_gate_coverage` (partition field) and asserts (1)–(3).
- Positive control: a synthetic unassigned file (or a roster entry removed from the fast part without being added to a shard) makes the proof fail.
- The fast roster's Σ measured seconds ≤ registry `max_total_measured_seconds` and each entry ≤ its budget, checked statically against committed timings.
- Workflow-shape test: battery legs, fast job, backstop and Packs corpus pass the literal `-n 4`; a guard fails on `-n auto` for these jobs.
