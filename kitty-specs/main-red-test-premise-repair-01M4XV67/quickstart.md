# Quickstart: verify the mission

```bash
.venv/bin/python -m pytest -n0 -q tests/specify_cli/test_requirement_id_lint.py
.venv/bin/python -m pytest -n0 -q tests/upgrade/test_mission_corpus_recovery.py -k full_corpus_audit
.venv/bin/python -m pytest -n0 -q tests/architectural/test_upgrade_recovery_preservation.py tests/architectural/test_archive_root_byte_identical.py
.venv/bin/python -m pytest -n0 -q tests/ci/test_fanout_derivation.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_workflow_coherence.py tests/architectural/test_consumer_census_routing.py
```

Expected: all green. The first two commands are red at base dcbabeb3ff.
