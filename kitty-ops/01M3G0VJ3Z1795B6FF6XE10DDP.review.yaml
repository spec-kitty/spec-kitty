# review-findings/v1 — canonical format for lens-session and fresh-sweep output.
schema: review-findings/v1
complete: true
phase: op
lens_group: review
mission: op-4986
findings:
  - id: op-review-001
    lens: code-review-incremental
    severity: 1
    title: Docstring narrates issue history that belongs in the commit message
    evidence:
      - code: "tests/specify_cli/cli/commands/test_review_git_baseline.py:296-303"
    claim: >-
      The rewritten docstring for test_review_post_merge_requires_issue_matrix
      includes "Prior to #4986, this fixture used the non-gating phrasing
      \"See #1234 for background.\", which #3469 demoted to context_only --
      making this test assert a pre-#3469 contract the product no longer
      implements." This is a change-history narrative (what the fixture used
      to say and why it was wrong), not a description of the current
      contract the test enforces. The commit message already carries this
      history in full ("test_review_post_merge_requires_issue_matrix failed
      on main because its spec.md fixture used ..."), so the docstring
      duplicates it. This is a stylistic nit, not a correctness problem: the
      surrounding module already has one precedent for this pattern
      (tests/specify_cli/cli/commands/review/test_zero_reference_not_applicable.py's
      "NOTE (#3469 / landing fold for #4820): prior to this fold, ..."
      block), so the addition is consistent with local convention rather
      than a novel deviation.
    remediation: >-
      Optional: trim the "Prior to #4986, this fixture used ..." sentence
      from the docstring and leave that provenance in the commit message
      only, keeping the docstring focused on describing the current
      gating-based contract (which the rest of the docstring already does
      well).
# Overall assessment (non-blocking, recorded for the record):
#
# Coverage claim (independently verified, TRUE): grepped every test file
# referencing issue-matrix / gating / ISSUE_MATRIX across tests/ (policy,
# tasks, specify_cli/cli/commands/review, specify_cli/cli/commands) for any
# full-CLI (`runner.invoke` / `CliRunner`) exercise of "gating reference
# present, issue-matrix artifact entirely missing -> spec-kitty review
# --mode post-merge exits nonzero":
#   - tests/specify_cli/cli/commands/review/test_zero_reference_not_applicable.py
#     ::test_references_present_and_matrix_missing_is_fail_closed calls
#     `_evaluate_issue_matrix` directly (unit level, no CLI, no git baseline,
#     no report writer).
#   - tests/specify_cli/cli/commands/test_review.py
#     ::test_issue_matrix_violation_is_hard_failure calls
#     `write_review_report` directly with hand-built findings (no discovery/
#     classification, no CLI).
#   - tests/policy/test_merge_gates.py
#     ::test_reference_in_spec_md_with_no_matrix_fails_closed_blocking exercises
#     a DIFFERENT gate (`evaluate_merge_gates` / merge-time "approval
#     blocker"), not the `spec-kitty review --mode post-merge` CLI path.
#   - tests/specify_cli/cli/commands/test_issue_matrix_not_applicable.py and
#     tests/tasks/test_issue_reference_classification.py cover the
#     IssueMatrixVerdict enum and the classifier unit contract respectively,
#     not the full review CLI.
#   - tests/specify_cli/cli/commands/review/test_dead_code_baseline_git.py
#     ::test_real_post_merge_cli_uses_git_as_only_path_executable is the only
#     other full-CLI post-merge test, but its fixture SHIPS a populated
#     issue-matrix.md (it is testing the git/grep executable-spy contract,
#     not the missing-matrix fail-closed branch).
# No test other than the one under review exercises "gating reference
# present + issue-matrix entirely missing" through the real CLI (real git
# baseline, mission resolution, report writer). The implementer's claim is
# TRUE, and deviating from the maintainer's literal "retire" instruction is
# justified by this evidence -- retiring the test as originally directed
# would have silently dropped the only full-pipeline regression guard for
# this fail-closed branch.
#
# Genuine fail-closed exercise (empirically verified): temporarily changed
# the `if not issue_matrix_artifact_present(...)` branch in
# `_evaluate_issue_matrix` (src/specify_cli/cli/commands/review/__init__.py)
# to return "not_applicable" instead of False/appending the finding-driving
# early return, re-ran the single test, confirmed it goes red
# (AssertionError on `issue_matrix_present: false` no longer present in the
# report), then restored the file exactly and confirmed
# `git status --porcelain -uno` is empty. The fixture text "Fix the
# pagination bug in #1234." does not match `_PR_OR_COMMIT_PATTERN` or
# `_CONTEXT_MARKER_PATTERN` in
# src/specify_cli/tasks/issue_reference_discovery.py, so
# `classify_occurrence` correctly returns IMPLEMENTATION_TARGET (gating) --
# the test is not vacuous.
#
# Commit message: conventional-commit form (`test(review): ...`), accurate
# subject, references #4986 and #3469, and documents the independent
# verification performed before deviating from the maintainer's "retire"
# suggestion. No charter/scope violation, no private detail, no dependency
# touched (051 not applicable). ruff check and ruff format --check both pass
# on the touched file (ruff 0.15.12, pinned in uv.lock).
