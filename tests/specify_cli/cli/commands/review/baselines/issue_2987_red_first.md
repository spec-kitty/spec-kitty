# Issue #2987 red-first evidence

## Tracker coordination

- Issue: https://github.com/Priivacy-ai/spec-kitty/issues/2987
- Assigned to the current Human-in-Charge (`stijn-dejongh`) before code changes.
- Existing mission claim: https://github.com/Priivacy-ai/spec-kitty/issues/2987#issuecomment-5091367887
- Reporter scope coordination:
  https://github.com/Priivacy-ai/spec-kitty/issues/2987#issuecomment-5092277027
- Coordination outcome at implementation start: the mission is proceeding with the pure-Python
  reference scan because `git grep` closes FR-014 but cannot close FR-015. The reporter was asked
  to link any active overlapping branch or pull request. The final pre-commit tracker check
  confirmed the assignment and found no reporter response or overlapping work.

The first sandboxed `gh` calls could not reach GitHub and `gh auth status` reported the default token
as invalid. Retrying the tracker commands through the approved network path succeeded; no tracker
link was inferred or fabricated.

## Ownership and campsite

- Pre-edit WP diff contained only runtime-owned status files and the WP prompt.
- The WP01-WP05 owned-file maps were disjoint from WP02.
- `ruff check` over the three originally owned Python surfaces passed before implementation.
- The owned review files had no domain-matched complexity or lint finding requiring a separate
  campsite commit.
- The orchestrator explicitly authorized adding `_report.py` to WP02 because otherwise the new
  structured undeterminable finding would be dropped from `mission-review-report.md`. No other WP
  owns that file.
- The orchestrator also authorized the narrow updates to
  `test_diagnostic_codes_documented.py` and `test_review.py`. The former had a hardcoded enum count;
  the latter had fake-clean non-Git fixtures and a subprocess fake that predated the explicit
  decoding contract. Both are direct regression-contract fallout with no other WP ownership.

## Red-first nodes

The first focused run completed with `5 failed, 5 passed`. The failures were:

- `test_non_git_repository_is_undeterminable`
- `test_missing_git_at_subprocess_boundary_is_undeterminable`
- `test_unsupported_non_python_change_is_undeterminable` (renamed 2026-09-29 to `test_unsupported_non_python_change_is_not_applicable`; see note below)
- `test_unreadable_python_corpus_is_undeterminable`
- `test_real_post_merge_cli_uses_git_as_only_path_executable`

The observed failures were the required pre-fix behaviors: two false-clean zeroes, one unhandled
`FileNotFoundError`, one unhandled `UnicodeDecodeError`, and one real CLI false-clean result.

## POSIX compatibility oracle

`test_supported_symbol_result_set_matches_posix_baseline` captures the pre-refactor result set:

```text
[{"type": "dead_code", "symbol": "PublicDead", "file": "src/module.py"}]
```

The post-refactor run must produce the same set.

It does: the final focused run completed with `17 passed`, and the compatibility node still reports
only `PublicDead`; a second public symbol referenced solely by an untracked `src/` file remains
classified as used. The real post-merge CLI node reports the deliberately unreferenced symbol,
emits no clean-zero output, and records `{"git"}` as the complete set of PATH-resolved subprocess
executables. The broader review-command suite completed with `28 passed` after its stale fixtures
were re-pinned to a real Git baseline and supported Python diff.

## Review cycle 2: mixed layouts

The cycle-1 reviewer found that `src_python_paths or ...` silently preferred the `src/` subset when
the same change set also contained supported Python outside `src/`. The finding was accepted from
`review-cycle-1.md` and reproduced before the repair with:

```text
2 failed
test_mixed_python_layout_discovers_every_supported_path
test_real_post_merge_cli_uses_git_as_only_path_executable
```

Both fixtures add `src/marker.py` and an unreferenced public symbol outside `src/`. Before the
repair, direct discovery returned only `src/marker.py` and the real post-merge command emitted a
clean zero. The repaired predicate retains every `src/` Python path for C-008 compatibility and
also retains every supported non-test Python path outside `src/`; the two-node rerun passed.

The final cycle-2 verification completed with:

- `126 passed` across the review command suites;
- `12 passed` with 95% statement coverage for `_dead_code.py`;
- zero findings from Ruff and mypy; and
- a clean `git diff --check`.

## Re-pin note (2026-09-29, mission tech-agnostic-language-fallback, #5283)

`test_unsupported_non_python_change_is_undeterminable` was renamed to
`test_unsupported_non_python_change_is_not_applicable`. A change set containing no file the
Python-only dead-code scan supports is now a non-failing `dead_code_not_applicable` note (gate
`skip`, verdict `pass_with_notes`) instead of a hard `DEAD_CODE_UNDETERMINABLE` failure. The
FR-015/FR-016 invariant is kept: that outcome never reports a false "0 unreferenced" clean zero.
Git-unavailable, git-diff-failure, unreadable-source and empty-corpus paths remain undeterminable.
