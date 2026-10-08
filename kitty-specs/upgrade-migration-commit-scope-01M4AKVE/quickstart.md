# Quickstart

```bash
cd <repo checkout>
# P0 reproduction (red before WP01's fix)
SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest <WP01 test module> -q
# Gates after code/prose edits
.venv/bin/python -m pytest tests/architectural/test_commit_scope_owner.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_completion_manifest_freshness.py -q
PYTHONPATH=. .venv/bin/python -m scripts.docs.check_changelog_style
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci
```
