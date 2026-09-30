# Workstream Q red proofs

Scanner fix (packs/internal/assets/test-quality-scan.py), AST-based skip-or-xfail and literal-source-scan.
Planted break = the pre-fix scanner (fix file removed via checkout, tests kept):
- tests/doctrine/assets/test_test_quality_scan.py::test_look_alike_is_not_flagged[test_drill_outcome_color]
  FAILED `assert 'skip-or-xfail' not in ['skip-or-xfail']` (parametrize id "skipped: drain off")
- ...[test_label_mentions_skip] FAILED same assertion (string literal 'pytest.skip(x) ...')
- ...[test_local_full_copy_source_absent_preserves_pre_existing_operator_templates] FAILED
  `assert 'literal-source-scan' not in ['literal-source-scan']` (comment naming src/ + fixture read_text)
Old scanner: 3 failed, 34 passed (true positives, posix skipif guard, fixture look-alikes green). Fixed: 37 passed.
Scan tests/cli --no-git: 116 flagged -> 114; only delta is the two slice-3 tests losing their flag.
