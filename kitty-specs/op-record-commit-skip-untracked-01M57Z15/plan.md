# Implementation Plan: Op record auto-commit skips repos that do not track kitty-ops

**Branch**: `issue-6410-op-record-commit-target` (plans and lands here; it reaches `main` through a PR) | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/op-record-commit-skip-untracked-01M57Z15/spec.md`

## Summary

Before the Op executor's best-effort auto-commit runs `safe_commit`, it asks two
questions.

1. Is the exact path about to be committed gitignored? This uses `git check-ignore --no-index`.
2. Does the primary branch track any Op-record-shaped file? The primary branch is resolved without current-branch bias, and the answer is cached per executor.

Either "ignored" or "not tracked" yields a skip. The record stays on disk, and
`last_op_commit` carries a `skipped` reason distinct from a refusal. The CLI `complete` and `doctor ops` human output render the skip, and their refusal text drops
the forbidden hatch advice and the false "will not survive a checkout or reset" claim.
Repositories that track Op records, this one included, keep today's current-branch
commit.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git CLI (subprocess); no new package dependency
**Storage**: files (`kitty-ops/*.jsonl`)
**Testing**: pytest. A red-first regression test goes through the CLI `complete` entry point. It is converted to focused unit tests for the new policy module, and existing executor, doctor and e2e fixtures are reworked to track one ULID record on `main`.
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single
**Performance Goals**: NFR-001: at most 12 extra git calls for the first close per executor, then 1 per close
**Constraints**: C-001 (the `complete --json` payload is frozen), C-002 (no new ref, config key or transport), complexity ≤15, ruff/mypy clean
**Scale/Scope**: about 5 source files, about 6 test files, 2 docs plus the changelog

Supply chain: no dependency decision, so DIRECTIVE_051 controls are not triggered.

## Charter Check

- **Single canonical authority.** The commit-or-skip decision lives in one new module, `src/specify_cli/invocation/op_commit_policy.py`. The executor is its only caller, and the Op-record regex is reused, not re-invented. The existing pattern lives inline in `coordination/coherence.py`, so the policy module exposes its own named constant and a test pins that both agree. Status: pass.
- **ATDD/red-first.** An issue-pinned `@pytest.mark.regression` repro goes RED before the fix, then is converted. Status: pass.
- **Terminology.** "branch-target routing", Mission. Status: pass.
- **No full heavy suites.** Targeted runs only. Status: pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/op-record-commit-skip-untracked-01M57Z15/
├── spec.md
├── plan.md
├── traces/
└── tasks.md / tasks/   (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/invocation/op_commit_policy.py   # NEW: resolve primary refs, tracked + ignored probes, skip decision
src/specify_cli/invocation/executor.py           # OpCommitOutcome.skipped; _commit_op_record consults policy (cached)
src/specify_cli/cli/commands/profile_invocation.py  # skip line; corrected refusal warning
src/specify_cli/doctor/ops.py                    # skipped:<reason> sweep entry value
src/specify_cli/cli/commands/doctor.py           # skip line; corrected refusal text
src/specify_cli/state/contract.py                # note: commit is conditional
docs/architecture/trail-model.md                 # describe skip + durability truthfully
docs/changelog/CHANGELOG.md                      # [Unreleased] Fixed entry

tests/specify_cli/invocation/test_op_commit_policy.py  # NEW focused unit tests
tests/specify_cli/invocation/test_executor.py           # fixture rework + skip tests
tests/specify_cli/invocation/cli/test_complete.py       # rendering
tests/specify_cli/invocation/test_doctor_ops.py         # fixture rework + skipped value
tests/specify_cli/invocation/cli/test_doctor_ops_cli.py # rendering
tests/specify_cli/invocation/test_invocation_e2e.py     # fixture rework
```

**Structure Decision**: single project. All behaviour changes stay inside the `invocation` package plus its two CLI renderers.

## Design

- `resolve_primary_refs(repo_root) -> tuple[str, ...]`:
  - Resolution order: `git symbolic-ref --quiet --short refs/remotes/origin/HEAD` (strip the `origin/` prefix), then the first of `main`, `master`, `develop` that exists as a local or `origin/` ref.
  - Returns the existing refs among `<primary>` and `origin/<primary>`.
  - If nothing resolves, returns an empty tuple. It never falls back to the current branch (FR-006).
- `primary_tracks_op_records(repo_root, refs) -> bool`:
  - Runs `git ls-tree -r --name-only <ref> -- kitty-ops/` for each ref and returns True on the first path matching `OP_RECORD_PATH_RE`.
  - Probe failures raise `OpCommitProbeError`.
- `is_path_ignored(repo_root, rel_path) -> bool`: `git check-ignore -q --no-index -- <path>`. Exit 0 → True, exit 1 → False, anything else raises `OpCommitProbeError`.
- `op_commit_skip_reason(repo_root, rel_path, *, tracked: bool | None) -> str | None`:
  - Checks ignore first, because one call is cheap, then the tracked decision supplied by the caller.
  - Returns a human-readable reason or None.
- Executor:
  - `_ops_tracked_on_primary: bool | None` is computed lazily once per instance.
  - `_commit_op_record` computes the skip reason after the current-branch check.
  - A probe error becomes a skip whose reason names the probe failure (spec edge case: best-effort, never raises).
  - On a skip it returns `OpCommitOutcome(committed=False, skipped=<reason>)` and does not call `safe_commit`.
  - `OpCommitOutcome` gains `skipped: str | None = None`.
- CLI `complete`:
  - A skip prints a dim note: `Op record kept on disk at kitty-ops/<id>.jsonl, not committed: <reason>.`
  - A refusal prints a corrected warning: the record is on disk and uncommitted, and the operator should commit it on a branch where it belongs. The hatch is no longer mentioned.
- Doctor:
  - The entry value is `skipped:<reason>`.
  - Human output gets a separate "kept on disk, not committed (repository does not track Op records)" line.
  - The refusal line drops the false checkout/reset claim.

## Risks

- **Fixture churn hides a real regression.** Mitigation: the reworked fixtures keep the original commit assertions, and new tests cover the skip branch on the same fixture with one change (positive control).
- **Pinned qualname.** `tests/architectural/test_no_worktree_name_guess.py` pins the `_commit_op_record` qualname. Keep the name and run that gate file.

## Implementation Concern Map

- **IC-01 Op commit policy**: the new module, executor integration and outcome type (FR-001, FR-002, FR-003, FR-006, NFR-001, NFR-002).
- **IC-02 Operator-facing reporting**: CLI and doctor rendering, plus the doctor entry value (FR-004, FR-005, C-001).
- **IC-03 Docs/contract truth**: trail-model doc, state contract note and changelog.
