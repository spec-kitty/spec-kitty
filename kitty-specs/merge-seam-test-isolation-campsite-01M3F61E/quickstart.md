# Quickstart: verifying this mission

Run from the repository root with the synced dev env (`.venv/bin/python`). Never use a bare `uv run` (it re-syncs a hand-built `.venv`), and never rely on the `spec-kitty` on PATH (use `.venv/bin/spec-kitty`).

## #5119 merge seam

```bash
# Rule: merge must not import the CLI command layer (red before WP-C's move, green after)
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py -q -k "MergeCli"
# Goldens: subprocess + in-process legs for all six drivers; all six resolve in replay
.venv/bin/python -m pytest tests/merge/test_merge_driver_goldens.py -q
# Goldens unchanged by the move
git diff --stat <pre-move-commit> -- tests/merge/merge_driver_goldens/   # expect empty
# Existing merge + driver suites
.venv/bin/python -m pytest tests/merge tests/specify_cli/cli/commands/test_row_aware_merge_driver.py tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py tests/terminus -q
```

## #5118 census gate

```bash
.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q
# Per sweep WP: behavior preservation for the shard's files
.venv/bin/python -m pytest <shard files> -q --junitxml=/tmp/before.xml   # on the WP's base
.venv/bin/python -m pytest <shard files> -q --junitxml=/tmp/after.xml    # after conversion
.venv/bin/python -m pytest <shard files> -q -n auto --dist loadfile
```

A planted `os.chdir("/")` inside any test function must make the gate fail with a message naming the file, function, kind and `monkeypatch.chdir` / `contextlib.chdir`.

## #5117 model slot

```bash
.venv/bin/python scripts/generate_schemas.py --check
.venv/bin/python -m pytest tests/doctrine/test_agent_profile_model_field.py tests/doctrine/test_schema_generation_integrity.py -q
```

## Mission-wide

```bash
make test-fast
.venv/bin/python -m pytest tests/architectural/ -q -p no:randomly   # WP-C, WP01, S8, Seal
uv run --frozen ruff check . && uv run --frozen ruff format --check .
.venv/bin/python -m mypy src/specify_cli/merge/drivers.py src/specify_cli/merge/git_probes.py src/specify_cli/cli/commands/merge_driver.py
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```
