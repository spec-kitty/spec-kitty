# Quickstart / Verification — Doctor mission-state legacy repair & report fidelity

## Reproduce the defects (pre-fix)
```bash
# Seed a mission whose meta.json has change_mode: regular, then:
PYTHONPATH=src spec-kitty doctor mission-state --fix          # aborts that mission: errors=N, "Invalid change_mode 'regular'"
PYTHONPATH=src spec-kitty doctor mission-state --teamspace-dry-run   # "N validation errors." with no detail
```

## Verify the fix
```bash
# 1. Legacy change_mode is repaired (US1 / FR-001..003, FR-011)
PYTHONPATH=src spec-kitty doctor mission-state --fix
#   → legacy mission counted as updated; stored change_mode gone; exit 0; action normalized_change_mode recorded.

# 2. Idempotent (NFR-002)
PYTHONPATH=src spec-kitty doctor mission-state --fix          # → zero further changes for that mission.

# 3. Per-mission detail in terminal + json (US2 / FR-005,006)
PYTHONPATH=src spec-kitty doctor mission-state --fix --json | jq '.missions[] | select(.status!="unchanged")'

# 4. Dry-run parity + detail (US3 / FR-007,008,009)
PYTHONPATH=src spec-kitty doctor mission-state --teamspace-dry-run          # names each affected mission + reason
PYTHONPATH=src spec-kitty doctor mission-state --teamspace-dry-run --json | jq '.errors'

# 5. Audit and fix agree (US4 / FR-010)
PYTHONPATH=src spec-kitty doctor mission-state --audit --json   # legacy change_mode not flagged fatal-in-one/valid-in-other
```

## Test commands (ATDD)
```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/test_mission_metadata_change_mode.py \
  tests/unit/migration/ tests/integration/migration/ \
  tests/cli/commands/test_doctor_mission_state.py \
  tests/audit/ tests/status/ -q
make test-fast    # baseline
```

## Done when
- SC-001 (all legacy-`change_mode` missions repaired, exit 0), SC-002 (triage from terminal/json alone), SC-003 (dry-run parity), SC-004 (audit/fix agree), SC-005 (idempotent), SC-006 (behavior-preservation test green).
