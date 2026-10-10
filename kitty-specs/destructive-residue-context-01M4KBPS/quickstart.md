# Quickstart: verify the fix

```bash
# Reproductions (red on main, green after the fix)
PWHEADLESS=1 .venv/bin/python -m pytest tests/consolidation -k "5965 or 5966" -q
# Guard and classifier unit tests
.venv/bin/python -m pytest tests/specify_cli/git/test_destructive_guard.py tests/git/test_ref_advance_resync_to_tip.py -q
# Routing gate (widened, empty allowlist)
.venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py -q
```

Manual: on a coordination Mission, reject a WP with `spec-kitty agent tasks move-task WP01 --to planned --no-auto-commit`, write a note under `kitty-specs/<mission>/traces/`, run `spec-kitty consolidate`. Expect exit with `COORD_TEARDOWN_KEPT_ONLY_COPY`, the files intact, the target landed, and the coordination branch present. Move the files out and run `spec-kitty consolidate --resume`: teardown completes.
