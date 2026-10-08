# Implementation Plan: Nightly red: test seams after origin freshness

**Branch**: `issue-5888-nightly-test-seam-drift` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/nightly-origin-seam-drift-01M4D8HH/spec.md`

The planning questions are answered by `research.md`: every group is reproduced, has a bisected culprit, and the verdict in each case is that the test is wrong.

## Summary

Re-pin four test seams that PR #5845 (#5780) left stale. The product behaviour is intended in every case, so nothing under `src/` changes:

- the doctrine git-source subprocess recorder;
- the consolidate flag golden;
- the accept decomposition harness;
- the owned-checkout accept integration tests.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest, typer/click `CliRunner`
**Storage**: N/A
**Testing**: Red first: the exact failing node ids fail on the merge base and pass on the branch. Then the full test file for each change, plus `make test-fast`.
**Target Platform**: Linux CI nightly shards (out-of-matrix shards 3 and 5, `integration`)
**Project Type**: single
**Performance Goals**: N/A
**Constraints**: no `src/` change; no skip, xfail or retry; #5891 out of scope
**Scale/Scope**: 4 test files, about 60 lines

## Charter Check

- **Test remediation discipline (SO #4).** The verdict is "judge the test": each product change was intended (ADR `2026-10-06-3`, PR #5845), so the stale seam is re-pinned and the product is not patched. Red first on the exact node ids.
- **Red-main discipline (SO #9).** These reds are cleared at the root, not green-washed. No skip or xfail.
- **Canonical sources (SO #6).** The mission runs through the CLI. The golden update cites the PR that introduced the flag.
- **Campsite (SO #2).** The recorder's empty-script fallback returned `str` to a bytes caller, a latent bug in the touched helper. It is fixed in place.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-origin-seam-drift-01M4D8HH/
├── spec.md
├── plan.md
├── research.md
├── issue-matrix.md
├── tracer-*.md
└── tasks/
```

### Source Code (repository root)

```
tests/specify_cli/doctrine/test_sources.py
tests/specify_cli/cli/commands/test_merge_cli_golden.py
tests/specify_cli/cli/commands/test_accept_decomposition.py
tests/integration/test_explicit_checkout_commands.py
```

## Implementation Concern Map

### IC-01 — Test seams that drifted with origin freshness

- **Purpose**: Make the four test seams model the post-#5845 product faithfully, so the nightly reports only real defects.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004
- **Affected surfaces**: the four test files above
- **Sequencing/depends-on**: none
- **Risks**: Over-filtering in the recorder could hide a real extra git contact. Mitigation: the filter matches only `config … core.sshCommand` reads, and every other call is still recorded and scripted.
