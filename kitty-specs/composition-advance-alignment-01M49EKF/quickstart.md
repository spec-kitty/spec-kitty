# Quickstart: verify composition-advance-alignment

```bash
# acceptance (twin-run parity with the engine path)
.venv/bin/python -m pytest tests/runtime/test_composition_advance_alignment.py -q
# adapter + engine + bridge surface
.venv/bin/python -m pytest tests/runtime tests/next tests/specify_cli/next -q
# gates
.venv/bin/python -m pytest tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_no_compat_delegates.py tests/architectural/test_runtime_emitter_seam.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py -q
uv run --frozen ruff check src/runtime/next tests/runtime tests/next
uv run --frozen mypy src/runtime/next   # 21 pre-existing errors on the base, add none
```
