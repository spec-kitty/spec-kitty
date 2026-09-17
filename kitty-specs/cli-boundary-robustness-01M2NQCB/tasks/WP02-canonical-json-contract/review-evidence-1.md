# WP02 independent review evidence

Reviewer: codex:gpt-6:reviewer-renata:reviewer. Reviewed HEAD `105ef7167c85378d091918beaac0a611b54b3eda` against `25f33493ca755f339d90984a3dc91c93cae286f7`. Official invocation `f9452a63092241858c2807dd51efd1bb`; full generated prompt read. No implementation changes made by reviewer.

No actionable defects found. Canonical verdict is recorded separately through move-task; this document is evidence, not event authority.

## Independent verification

`PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_cli_boundary_json_seam.py tests/specify_cli/cli/test_helpers.py tests/specify_cli/cli/commands/test_doctor_json_not_in_project.py tests/specify_cli/cli/commands/test_doctor_shared.py tests/specify_cli/cli/commands/test_doctor_shim_reexports.py -q`: **125 passed in 2.32s**. Raw output retained at workspace-parent/WP02-review-focused.log.

Diff and live call sites inspected. New builder/guard is imported by CLI helpers and doctor shared module; all19 relevant registered doctor commands delegate through the shared resolver. Resolver injection preserves patch seams, mission-state allow_none preserves fixture precedence, and individual exits1/2 remain unchanged. Canonical error goes to stdout through existing CliConsole.emit_json; success payloads and human diagnostics unchanged. Coordination preserves stable error code and handle metadata. Warning/logging state restoration retains existing semantics.

FR005 canonical shape: git failure/frozen doctor equality assertions and guard aliases. FR007 stream purity: separate stdout JSON/stderr assertions for helper/git/doctor. FR008 missing-root boundary: opt-in helper, success path identity and 19-command raised/None matrix. C001/C006 compatibility: frozen tests unchanged, old positional helper calls preserved. C003 tests-first: commits60c420d0d anddf7010627 precede implementation105ef7167; red logs show actual old output failures. NFR004/NFR006 supported by narrow shared authority and recorded strict typing/lint/format checks.

## Required anti-pattern checklist

1. **Dead code: PASS.** json_contract imported by helpers and doctor shared; promoted guard has production callers across all six doctor-owned surfaces.
2. **Synthetic-fixture test: PASS.** Tests call actual helper and registered doctor commands; only root lookup is controlled. Removing seam breaks output/delegation assertions.
3. **Silent empty return: PASS.** Only new allow_none return preserves documented mission-state fixture behavior; raised resolver errors remain loud with exit code.
4. **FR coverage: PASS.** FR005/007/008 assertions mapped above; frozen contract and success identity retained.
5. **Frozen surface: PASS.** git log25f33493..HEAD for test_doctor_json_not_in_project.py empty; file unchanged.
6. **Locked decision: PASS.** No successful-shape changes, parser flag expansion, new serializer authority, dependency/version/SaaS override, or forbidden mission alias added.
7. **Shared-file ownership: PASS.** Nine owned files plus two existing tests explicitly authorized by orchestrator; no sibling source overlaps.
8. **Production fragility: PASS.** New raises preserve preexisting missing-root failure exits; documented allow_none exception avoids breaking fixture-only mode.

## Validation limits and baseline debt

Implementer broad CLI result:4170 passed,10 skipped,2 xfailed,4 failed. All four failures reproduced unchanged original-root source atbe490214 in6.29s (completion manifest #4479, two org-cascade assertions #4668, decision command shape #4669). This is not an all-green broad suite. Long help enumeration was interrupted, not passed; independent baseline sample269 leaves at9.4885sec median predicts42.54min and supports known #4636/#4516 attribution. Supplemental suite844 passed,7 skipped,one timeout; same unchanged node subsequently passed in347.63s under reduced load. These limitations are preserved, not relabeled green.

Reviewed implementation typing/lint/format logs: strict mypy clean on11 changed files; inherited diagnostics fixed locally without suppressions. Existing formatter-excluded modules retain narrow edits; no exemption expansion. Red evidence and scope rationale retained in implementation handoff. No additional broad test rerun warranted for this bounded independent check.

Issue matrix stays in-mission; this WP review does not declare other WPs or mission terminally complete.
