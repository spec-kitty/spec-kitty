# Quickstart: verify the exemption

```bash
# Targeted tests
.venv/bin/python -m pytest tests/status/test_cutover_eligibility.py tests/specify_cli/cli/commands/test_cutover_guard.py tests/specify_cli/migration/test_dogfood_corpus_backfilled.py -q

# Live guard on this PR's own Mission (in flight, claimed, unstamped) — must pass with the pre-accept note
spec-kitty cutover-guard --base-ref origin/main
```
