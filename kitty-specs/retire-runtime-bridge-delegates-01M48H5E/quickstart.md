# Quickstart: verify the mission locally

```bash
# 1. The acceptance gate (static) — every seam row passes, no xfail left
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py -q

# 2. No delegate docstrings, no bridge-qualified references to removed names
grep -c "Thin compat delegate" src/runtime/next/runtime_bridge.py   # expect 0

# 3. The runtime_bridge test surface (on a clean tree)
FILES=$(git grep -l runtime_bridge -- 'tests/*.py'); \
  .venv/bin/python -m pytest $FILES tests/runtime tests/next tests/specify_cli/next -q -p no:cacheprovider

# 4. Named architectural gates
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_bridge_cores_import_boundary.py tests/architectural/test_runtime_emitter_seam.py -q

# 5. Static checks
.venv/bin/ruff check src/runtime/next && .venv/bin/mypy src/runtime/next | tail -1   # <= 21 errors (main baseline)
```
