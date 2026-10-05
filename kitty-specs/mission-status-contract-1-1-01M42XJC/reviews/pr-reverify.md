# W-4 fix round re-verify (spec-kitty#5625, bd922ecce..f8046d5b0, 12 commits)

VERDICT: clear. Anchored 9/9 fixed. No new finding above severity 1.

## A. Anchored (revert = temporary edit, then `git checkout -- <file>`; tree clean afterwards)
| Finding | Verdict | Evidence |
|---|---|---|
| PR-CONTRACT-001 (case-variant root records) | fixed | `path.casefold() in ROOT_STATUS_FILES`; contract text in getArtifactContent and ArtifactNotFound; case-variant unit and containment cases. Reverting casefold: test_only_the_root_status_records_are_excluded FAILS. |
| PR-READERS-001 (lane control) | fixed | lane_control_problems added to _examine_work_package, fixture rows added, two DETAIL_MUTANTS (subtask and dependency lanes nulled). Removing the call: test_a_defective_detail_reader_is_killed[subtask lanes nulled] and [dependency lanes nulled] both FAIL. |
| PR-CONTRACT-003 (unparseable example) | fixed | example now carries real pointer and path; new cycle-without-path example plus a test. Reverting the example to bd922ecce: new test FAILS. |
| PR-GATES-001 (router globs) | fixed | 31 src files derived by my own AST scan of tests/contract/*mission_status*.py: 0 missing, 0 extra globs (38-entry group parsed from YAML). Removing the review/cycle.py glob: the new tests/ci test FAILS. |
| PR-READERS-003 (4 MiB cap) | fixed | boundary test (cap -> 200, cap+1 -> 500). Loosening the cap to 16x: the cap+1 case FAILS. |
| PR-GATES-002 | fixed | exact len pins removed; per-kind loops kept plus a set-superset assertion. Deleting leak-scan-credential-in-title from the manifest: the test FAILS (by kind). |
| PR-GATES-004 | fixed | docstring says 34 (8+10+12+1 reference, +3 controls); KINDS is 34 (test_fixture_builder passes). |
| PR-SECURITY-007 | fixed | docstring names SKIPPED_DIRECTORIES; new test over git ls-files. Adding a real directory name (mission-status) to the skip set: the test FAILS. |
| PR-SECURITY-008 | fixed | _walk iterative, prunes at 512. Removing the prune (`if True`): the nested-without-end test never terminates (timeout 124), which is the behaviour the prune prevents. |

## B. Fresh sweep
- cycle-without-path example: validates against WorkPackageDetail schema (my own jsonschema run, 0 errors, unparseable-cycle also 0); registered in examples/_index.yaml, schema examples list and REQUIRED_EXAMPLES; example_check 75/75 validated; leak_scan clean.
- Iterative _walk: yield order differs from the old pre-order, but list_artifacts sorts by path_sort_key afterwards and the set is identical, so output is deterministic. Prune is off by one in the safe direction (a dir at 511 is entered, its children are ineligible).
- casefold: Unicode casefold is slightly wider than "without regard to case": U+017F (long s) folds to s, so a root file named with it is refused/hidden. Over-refusal only, never under-refusal; practically irrelevant. Severity 1, note only.
- SLICE_ALLOWED: one ScopeRule EXACT .github/workflows/ci-router.yml, MODIFIED only; the test pins that an Add of that path and a Modify of ci-nightly.yml are out_of_scope.
- ci-gate-mechanics.md: matches the contract_tools group (src modules spelled `**/<module path>`, group stays non-src).
- Severity 1 note: without the prune the new walk test hangs instead of failing cleanly (no per-test timeout).
- Router-test scope: only mission-status modules are covered by the derived list; other tests/contract modules import further src files (pre-existing, outside this finding).

## C. Gates (TMPDIR under scratchpad, venv first on PATH, oasdiff and vacuum on PATH, no JVM on host)
- Ten contract checks: all exit 0 (leak_scan files=1062; example_check 75/75).
- breaking_check vs origin/main contracts with baseline version lowered to 0.9.0: exit 0, breaking=0.
- run_negative_cases --exclude-tag jvm: cases=127 ran=124 skipped=3 (the three JVM cases; no java/gradle on host) passed=124 failed=0.
- pytest tests/contract: 2875 passed.
- Tool-job command (corpus and not windows_ci, three ignores, -n 4 --dist loadfile): 1776 passed, 37 skipped.
- pytest tests/ci: 1749 passed.
- ruff check, ruff format --check . (3108 files), ruff --select TID251: clean. cutover-guard against origin/main: 0 un-cut-over.
- mypy --strict: tests/ci/test_contracts_workflows.py and contracts/tools/*.py clean (26 files). The 11 errors in test_mission_status_detail.py and test_mission_status_reality.py are identical, line numbers aside, to bd922ecce (pre-existing, not introduced).
