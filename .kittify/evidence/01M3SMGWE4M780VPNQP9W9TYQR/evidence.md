# red-proofs-c
Break: src/specify_cli/cli/commands/charter_bundle.py:446, delete `and not sidecar_errors` from overall_passed.
- old test_validate_reports_provenance_yaml_parse_error: PASSED (stays green)
- new test_validate_fails_on_provenance_yaml_error_when_nothing_else_is_broken: FAILED
  `assert payload["passed"] is False` -> `assert True is False`
- paired positive test_validate_passes_when_only_provenance_sidecar_is_valid: PASSED (fixture otherwise clean)
Result: 1 failed, 2 passed. Reverted via git checkout -- src/; diff --stat src/ empty.
