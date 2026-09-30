# review-c: #5353 slice-3 follow-up C (reviewer-renata)

Branch `issue-5353-c-followup` @ 0109b37a (base f764d38c, 35 behind origin/main 74373ec9; no drift on touched files).
Diff: test-only, `tests/charter/test_bundle_validate_cli.py` +47 plus Op evidence. `git diff origin/main...HEAD -- src/` is empty.

## Verdict: APPROVE-WITH-NITS

## Findings
1. MEDIUM (naming vs. behaviour). The guard `test_validate_fails_on_provenance_yaml_error_when_nothing_else_is_broken`
   (tests/charter/test_bundle_validate_cli.py:690) writes `":\n"`. ruamel safe-load parses that to `{None: None}`,
   so the guard exercises the ProvenanceEntry *schema-validation* branch (charter_bundle.py:286-289), not the YAML
   *parse* branch (charter_bundle.py:276-280). Planted break B3 (swallow the parse exception) survives the whole
   charter-bundle set (55 passed). Fix: write genuinely unparseable YAML, e.g. `"key: [unclosed\n"`. Verified: the
   guard stays green on clean src and goes red under B3 (line 698, `AssertionError: []`). Better still, parametrize
   the input over both `":\n"` (schema) and `"key: [unclosed\n"` (parse). The same misnaming affects the
   pre-existing `test_validate_reports_provenance_yaml_parse_error`.
2. LOW (duplication). `_build_otherwise_clean_v2_bundle` repeats the three-call build inlined in
   `test_validate_passes_complete_v2_bundle` (:619), and the new positive pair is close to that test: under break B4,
   both fail identically. Fix: make the existing test use the helper and fold the one extra assertion
   (`bundle_compliant is True`) into it, or drop the positive pair and name the existing test as the pair.
3. NIT (format). The new `assert any(...)` at :698-700 is not ruff-format clean (it would collapse to one line). The
   file is still in `[tool.ruff.format].exclude` and is unformatted overall, so the ratchet entry correctly stays.
4. NIT (trailer). Commits 8a3f1147 and f5364f48 carry a `Claude Sonnet 5.5` Co-Authored-By trailer. The session
   attribution trailer is present on all three commits.

## Planted breaks (each reverted, git status clean afterwards)
The runner selected 4 tests: old parse_error, positive pair, guard, and complete_v2.
- B1 (implementer's): remove `and not sidecar_errors` (:446). Guard red at :701 `assert True is False`. Old test green. 1F/3P.
- B2a: `provenance_error_strings = []` (collected but not reported). Guard red at :698 `AssertionError: []`. Old test green. 1F/3P.
- B2b: `sidecar_errors = []` (not collected). Guard red at :698. Old test green. 1F/3P.
- B3 (own): YAML parse `except` swallows the error (:279). Guard GREEN. 4P, and 55P across the 4 charter-bundle files. See Finding 1.
- B4 (positive-pair non-vacuity): `if not isinstance(raw, dict)` inverted (:281), so valid sidecars are rejected. Positive pair red at :677 (exit_code). complete_v2 also red at :635. 2F/2P.

## Tests
- `tests/charter/test_bundle_validate_cli.py`: 24 passed.
- The same file plus `tests/cli/commands/test_charter_bundle_coverage.py`, `tests/charter/test_bundle_contract.py`,
  `tests/cli/commands/test_charter_json_error_contract.py`, `tests/charter/test_presence_gate_bundle_authority.py`,
  `tests/architectural/test_ruff_pytest_style_baseline.py` and `tests/architectural/test_ruff_format_exclude_ratchet.py`:
  73 passed, 1 failed.
- The 1 failure is `test_presence_gate_bundle_authority.py::TestFR006JsonPresentSignalFlip::test_cli_context_json_present_survives_charter_md_deletion`
  ("Refusing charter write from linked git worktree"). It fails identically on origin/main 74373ec9 in this linked
  worktree, so it is ENVIRONMENTAL and not caused by this diff.
- ruff check: clean. ruff format --check: would reformat (file is excluded; expected).
