# Quickstart — reproduce the measurement and the guards (#6777)

Everything below runs in a checkout of this branch. The host used for the recorded numbers
was shared by ~20 concurrent missions (load average 11–145 during the work), so **use the
interleaved protocol, never a single absolute wall clock**.

## 1. The case, as CI runs it (single 240 s backstop, no override)

```bash
uv run --frozen pytest "tests/charter/activation/test_stored_spelling_6527.py::test_writer_stores_stems_only" \
  -q --durations=0
```

Expect: `10 passed`, with `[cascade]` the slowest case (~65 s here, 87 s for the whole
selection). Before #6777 the same case cost 70.9–95.2 s and crossed 240 s on a slower
runner.

## 2. The deterministic evidence (load-independent)

```bash
uv run --frozen pytest tests/charter/activation/test_cascade_stem_resolution_6777.py \
  tests/charter/activation/test_stored_spelling_6527.py -q -k "resolution_pass or precedes or timeout or mark_probe"
```

Expect: 4 passed. These assert the pass count and marker state, never seconds.

## 3. The parse counts

```python
# in a scratch script: count charter.activation.kind_vocabulary._parse_id calls around
from tests.charter.activation.test_stored_spelling_6527 import _project, _cascade
```

Expected for a full `--cascade all` walk: **240** `_parse_id` calls after the fix, **5028**
before it. `ResolutionPass` instances for the whole process fall 122 → 10 (the other nine
are the render pass and the call-local passes other charter helpers create; the guard pins
*the batch's own lookups* to exactly one). Reverting `_cascade_target_refs` to the
per-target lookup restores the old numbers.

## 4. The interleaved A/B (the only honest wall-clock form here)

Run both arms in one process, alternating fresh fixtures, and compare medians: the fixed
arm must be ≤0.8× the pre-fix arm. Recorded: 0.62× (load ≈21) and 0.70× (load 44–91). The
protocol lives in `research.md`; the rationale is
`decisions/measurement-evidence-integrity.md`.
