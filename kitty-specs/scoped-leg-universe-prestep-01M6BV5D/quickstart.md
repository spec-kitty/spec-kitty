# Quickstart — reproduce and verify #7001 locally

All commands run from the repository root of a clean checkout.

## 1. See today's waste (before the fix)

```bash
# A docs-only diff selects a handful of gates, none of which reads the universe.
uv run --frozen python - <<'PY'
from scripts.ci.gate_selection import select_battery_gates
print(sorted(select_battery_gates(["docs/adr/3.x/example.md"]) or []))
PY

# …yet the leg's decision answers "yes" for its whole partition:
uv run --frozen python -m scripts.ci.collect_universe_prestep consumers --battery-part 1/2
uv run --frozen python -m scripts.ci.collect_universe_prestep consumers --battery-part 2/2
```

Both print `true` on `main`, so each leg runs the key/restore/collect/save/check chain
and pays a cold collection (measured 396.7 s on the development host; 89–233 s on CI).

## 2. Write a selected-gates file by hand

```bash
out="${TMPDIR:-/tmp}/battery-scope-gates.txt"
printf '%s\n' tests/architectural/test_dead_builtin_doc_paths.py > "$out"
uv run --frozen python -m scripts.ci.collect_universe_prestep consumers --battery-part 1/2 --gates-file "$out"
# -> false: the selected gate does not call collect_universe()
```

Add a consumer and the answer flips:

```bash
printf '%s\n' tests/architectural/test_fast_tier_marker_completeness.py > "$out"
uv run --frozen python -m scripts.ci.collect_universe_prestep consumers --battery-part 1/2 --gates-file "$out"
# -> true (that file is in leg 1/2 and calls collect_universe())
```

## 3. The environment form the plug-in also reads

```bash
SK_BATTERY_GATES_FILE="$out" uv run --frozen python -m scripts.ci.collect_universe_prestep consumers --battery-part 1/2
```

Equivalent to passing `--gates-file`. Unset (or empty) means the whole part, which is
today's behaviour.

## 4. Fail closed

```bash
uv run --frozen python -m scripts.ci.collect_universe_prestep consumers --battery-part 1/2 --gates-file /nonexistent
# exit 1, nothing on stdout, a message naming the file on stderr
```

## 5. Targeted tests (never the full heavy suite)

```bash
uv run --frozen pytest -q \
  tests/ci/test_collect_universe_prestep.py \
  tests/ci/test_battery_scope.py \
  tests/ci/test_battery_partition_plugin.py \
  tests/ci/test_ci_workflow_prestep_shape.py
uv run --frozen pytest -q tests/architectural/test_battery_partition_plugin.py
```

## 6. Docs freshness

```bash
uv run --frozen python -m scripts.docs.check_docs_freshness --ci   # expect errors=0
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
```
