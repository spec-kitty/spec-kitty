# Final pre-PR verification

2026-10-11. Issue #5924, owner Ivan-Melck. PR only; no merge/consolidation/main push/auto-merge.

## Independent review

Initial independent correctness review rejected two witnessed P2 paths: malformed transition identity AttributeError and unguarded later canonical reads. Initial test/delivery review requested a paired healthy ReviewerSelfApproval control. All were folded. Expanded tests exposed an empty-snapshot permission failure hidden by the dependency runtime overlay; the approved two-line authored-only reader selection removes irrelevant status reads while preserving dependency semantics.

Final independent Reviewer Renata correctness and test/delivery agents reviewed product HEAD 4deddae418f7db09f3f3d8c1fc34562b9cb095e8 against main 4395fea493. Both returned no blockers/no additional findings; all applicable eight review checklist items PASS, shared-file ownership N/A (one WP). Correctness reviewer independently probed both schema/snapshot variants, late read failures, restoration, strict raw reading and authored dependency callers. Neither ran pytest, changed files or recorded status. Parent corrected the lagging WP owned-files declaration/T003 sentence afterward and refreshed current READY analysis at 51ab3360; product/tests unchanged.

## Parent-run final checks on rebased product

- `make test-fast`: 2638 passed, 5 skipped, 1 warning.
- `.venv/bin/python -m pytest tests/status -m '(fast or unit) and not slow and not e2e and not integration and not regression and not distribution and not live_adapter and not stress and not timing and not windows_ci and not platform_darwin' --cov=specify_cli.status --cov-report=xml:<coverage.xml> -q`: 1387 passed, 5 skipped, 293 deselected.
- `.venv/bin/diff-cover <coverage.xml> --compare-branch=origin/main --fail-under=90`: 36/36 changed production executable lines, 100%.
- `.venv/bin/python -m pytest tests/architectural/test_status_module_boundary.py tests/mission_runtime/test_issue_matrix_content_source.py tests/policy/test_issue_matrix_cross_site_consistency.py tests/specify_cli/cli/commands/test_coordination_remedy_5113.py tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py tests/specify_cli/lanes/test_lane_match_sites.py tests/architectural/test_no_legacy_terminology.py tests/docs/test_changelog_style.py -q`: 325 passed.
- `make format-check`: 3624 files already formatted.
- `.venv/bin/ruff check src/specify_cli/status/doctor.py src/specify_cli/status/store.py src/specify_cli/status/uninitialized_hint.py tests/status/test_doctor_log_errors.py tests/status/test_store.py`: passed.
- `.venv/bin/mypy --strict src/specify_cli/status/doctor.py tests/status/test_doctor_log_errors.py`: passed, two targets.
- `.venv/bin/mypy --strict --follow-imports=silent src/specify_cli/status/doctor.py src/specify_cli/status/uninitialized_hint.py src/specify_cli/core/dependency_graph.py tests/status/test_doctor_log_errors.py`: passed, four targets. The cyclic helper's already-typed dependency callee must be an explicit target; a three-target run without it reports unchanged helper line73 no-any-return. No suppression/cast/source typing changes.
- `.venv/bin/python -m scripts.docs.check_docs_freshness --ci`: exit0, no errors, one existing spec-commit help-drift warning.
- `.venv/bin/python -m scripts.docs.check_spelling`: no findings; 685 typo files, 133 US-spelling files, 113 Unreleased lines scanned.
- `.venv/bin/python -m scripts.docs.check_changelog_style`: no errors, five baseline length warnings.
- `npx --yes @commitlint/cli@19.8.1 --config commitlint.config.cjs --from origin/main --to HEAD --verbose`: no problems/warnings on compressed/rebased history before final metadata commits.
- `git diff --check`: passed.

## RED, scope and preservation

Original RED41930fe8f39ac91091108128c75b177a90035ea4: 62 failed/5 passed before production cc721e3372. Review RED324defbc45209c44cdb505cbcdfa8803c52c3538: 44 failed/2 passed before 4edee4a02c; the retained expanded-matrix failure preceded helper812d3647d4. Original lineage preserved locally as backup/issue5924-pre-pr-original. Five existing semantic boundary trees were rebuilt via commit-tree; compressed tip27f12edc605b9d7f17426af33ce8afe0bacdc764 and original e4a90f0070dc1cc037587ddb278e33355d70e473 have identical trees. Then rebased onto main4395fea493; only changelog conflicts, retaining both entries. Product, tests and architecture doc verified byte-identical to backup afterward. All 288 existing local evidence-file hashes unchanged; 56 untracked evidence files did not collide with upstream. Preserved historical user stash is not part of PR changes.

No heavy full architectural/e2e/performance suite run. Automatic pre-review gate had timed out/skipped; parent make test-fast is the actual broad evidence, not a claim that the automatic gate passed. Baseline strict store no-any-return remains tracked in #6051; stale retired bytecode environmental finding is #6050. No unrelated parser, model, reducer, CLI, dependency/version or decision-doctor changes.
