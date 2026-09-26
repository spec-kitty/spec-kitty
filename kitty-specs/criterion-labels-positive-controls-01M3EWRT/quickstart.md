# Quickstart: verifying the mission

```bash
source .venv/bin/activate
spec-kitty doctrine regenerate-graph --check
pytest tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py -q
pytest tests/specify_cli/test_requirement_mapping.py tests/specify_cli/missions/test_substantive_gate_formats.py -q
pytest tests/doctrine tests/charter -q -n auto --dist loadfile
pytest tests/architectural/test_no_legacy_terminology.py -q
spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity
```
