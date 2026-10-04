# `tests/regression/`

This directory holds only fixtures and baseline evidence now (`conftest.py`,
`baselines/`). It no longer holds a dedicated suite, and it is not where
regression tests live.

## What `regression` means

`@pytest.mark.regression` marks an issue-pinned guard for a bug that is already
**fixed**. It runs per PR, in the module shard that owns the test's path, like
any other test. A red `regression` test is a real failure in the change under
review.

Put such a test next to the code it covers, with the marks the functional suite
uses (see [`docs/context/testing-taxonomy.md`](../../docs/context/testing-taxonomy.md)).
Name the issue in the docstring and say that the defect is fixed.

## Open P0 reproductions are not `regression`

A red-first reproduction of an **open** P0 bug carries
`@pytest.mark.p0_repro(issue=N)`. It runs only in the nightly `p0-repro` job and
is deselected everywhere else, so pull requests land green while the nightly
and the release stay red until the fix. The fix PR removes the marker, and the
test then becomes an ordinary guard.

Rules, run instructions and failure banners:
[Red Main and Release Readiness](../../docs/development/reference/red-main-and-release-readiness.md#where-the-reproduction-runs-the-nightly-p0-repro-lane).
Governing decision:
[ADR 2026-07-17-1](../../docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md)
(Amendment 2026-10-04).

Never make a reproduction pass by weakening its assertion or adding a skip or
`xfail`. The product fix is separate work.
