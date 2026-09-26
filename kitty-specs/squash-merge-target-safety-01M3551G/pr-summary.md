# PR Summary: Fail Closed on Ordinary Squash Conflicts

## Summary

- Remove the default squash strategy's global `-X theirs` preference.
- Fail closed on ordinary source conflicts before target-ref advancement or
  lifecycle cleanup.
- Make dry-run simulate the same squash integration and emit a stable
  `TARGET_BRANCH_CONTENT_CONFLICT` blocker.
- Preserve registered artifact drivers and both directions of the established
  PRIMARY planning-artifact recency policy.

## Compatibility

- Clean squash merges and disjoint same-file edits remain successful.
- Clean dry-run JSON retains its existing key set.
- Explicit `merge` and `rebase` strategies are unchanged.
- No migration or dependency change is required.

## Validation

- 43 focused merge/forecast/planning tests passed.
- 1,941 fast tests passed (5 skipped).
- 246 contract tests passed (10 skipped).
- 2,808 architectural tests passed (4 skipped, 2 expected xfails).
- Ruff, focused MyPy, issue-matrix policy tests, and `git diff --check` passed.

## Review notes

Reviewer cycle 1 rejected a planning-recency regression. The second
implementation restored source-newer behavior through the existing policy
authority, added a regression test, and was approved in cycle 2.

The external issue-716 consumer scenario remains blocked before merge execution
by the known #3281 lane-allocation failure; a fresh reproduction is linked from
the mission review.

Fixes #4892.
