# Quickstart: prose-only down-route

## What changed

A PR whose entire Python diff is comments/docstrings (no code, no `# type:`
change, no `>>>` doctest edit) no longer runs the module-test matrix or the heavy
architectural battery. It runs the always-on lint/format/terminology lanes and —
now correctly — the docs/help-drift lane. Any other PR routes exactly as before.

## Verify locally

```bash
# Classifier unit tests (fast, in-memory)
PYTHONPATH="$PWD" .venv/bin/python -m pytest tests/ci/test_prose_only.py -q

# Wiring + golden lane-set
PYTHONPATH="$PWD" .venv/bin/python -m pytest tests/ci/test_ci_module_wiring.py -q

# Path-purity guards must stay green
PYTHONPATH="$PWD" .venv/bin/python -m pytest \
  tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_local_gate_parity.py \
  tests/architectural/test_ci_integrity_oracle_nonvacuous.py -q
```

## Manual sanity (optional)

```python
from scripts.ci.prose_only import is_prose_only
is_prose_only('def f():\n    """old."""\n    return 1\n',
              'def f():\n    """new."""\n    return 1\n')   # True
is_prose_only('def f():\n    return 1\n',
              'def f():\n    return 2\n')                   # False
```

## Fail-closed reminder

If anything is uncertain — a file will not parse, a base blob is missing, a
`# type:` or `>>>` doctest changed — the PR routes fully. The safe failure is
"run everything", identical to today.
