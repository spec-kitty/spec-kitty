# Implementation Plan: Recoverable stale-lane refusal after a halted in-run auto-rebase

**Branch**: `kitty/mission-stale-lane-sibling-recovery-01M7X1QS` → `fix/7755-stale-lane-auto-rebase-recovery` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)
**Input**: [spec.md](spec.md), [research/code-grounding.md](research/code-grounding.md)

## Summary

The stale-lane refusal at `consolidate` loses the only facts that make it recoverable: the in-run auto-rebase halt reason, and which sibling lane the overlap came from. After the run's rollback restores the Mission branch, the remedy's "incorporate changes from the Mission branch" brings in nothing (#7755), and its first command, `agent action implement`, refuses the approved work package (#7754). The fix keeps rollback untouched and makes the refusal accurate: surface the halt reason, name the sibling lane branch (which the rollback never moves), and prescribe a route valid for an approved work package. The route was verified end to end before planning (see grounding).

## Options (Decision needed — recommendation: A)

| Option | What changes | Rollback semantics | Verdict |
|---|---|---|---|
| **A. Diagnose and redirect the remedy** | Carry `halt_reason` from `_try_auto_rebase_if_stale`; identify sibling lanes whose consolidated change overlaps the stale files; the remedy names the sibling branch to merge in the lane checkout, preceded by the reopen step (`move-task <WP> --to planned --review-feedback-file <file>`, re-review cost) and followed by re-review and re-running `consolidate`. No-sibling case keeps the `implement` auto-rebase refresh, after the reopen step. | Unchanged | **Recommended.** Smallest change; verified to land in the next run; no new restore path. |
| B. Keep a ref to the in-run Mission tip | Write `refs/spec-kitty/…` to the in-run tip before rollback and teach the sync point to merge it. | A new ref written by the rollback path; new sync-point source | Rejected: adds state to the rollback span the AST pin guards, and the in-run tip also carries unrelated in-run work. |
| C. Retain the consolidated sibling on the Mission branch for this refusal class | Rollback skips restoring the Mission branch when the exit is a stale refusal. | **Changes** rollback (ADR 2026-09-19-1) | Rejected: changes rollback semantics; a partially consolidated Mission branch is exactly what the single rollback authority prevents. Would need an operator ruling. |
| D. A consolidate-owned lane refresh command | New CLI that merges a sibling into an approved lane. | Unchanged | Rejected for this P0: new surface; still needs a re-review (an unreviewed merge with own content fails reconciliation, #5604). |

Option A amends one documented rule: FR-091 / #7311 say the stale remedy never prints a `git merge` recipe. That rule was written when the remedy merged the Mission branch (a no-op after rollback). No CLI command incorporates a *sibling* lane, and the conflict must be resolved by hand anyway (the current text already says "resolve it in the lane checkout … commit there"), so the sibling case names `git merge <sibling lane branch>` in the checkout `implement` names. It never names a `.worktrees/` path or the Mission branch. CLAUDE.md's sentence is updated to match.

## Technical Context

**Language/Version**: Python 3.11+ · **Primary Dependencies**: typer, rich, `kernel.git` helpers · **Testing**: pytest (real git repositories, real CLI via the terminus harness) · **Target**: `spec-kitty consolidate` lane-consolidation phase · **Constraints**: C-001..C-003; complexity ≤ 15; no subprocess calls added to `lanes/consolidation.py` (AC-F1 ratchet).

## Charter Check

- Single canonical authority: the remedy stays in one builder (`stale_check._stale_remediation`); no second remedy renderer. PASS.
- Architectural alignment: no rollback change; sibling identification lives in `lanes/stale_check.py` using `kernel.git` probes. PASS.
- ATDD / red-first (SO-4): the `p0_repro` test is un-marked and must be red on pre-fix sources; a new red-first CLI test through `spec-kitty consolidate` proves recovery. PASS.
- Terminology: Mission (never feature); `consolidate` is local; "merge" here is a git merge into a lane checkout (named as such). PASS.

## Design

1. `StaleCheckResult` gains `auto_rebase_halt: str | None` and `sibling_lanes: tuple[SiblingLane, ...]` (default empty; existing callers unchanged).
2. `stale_check.find_sibling_lanes(repo_root, lane_branch, mission_branch, candidates, stale_files)` returns the candidates whose branch tip the Mission branch reaches and whose commits missing from the lane (`lane..sibling`) touch a stale file. Probes: `merge-base --is-ancestor` and `log_paths` from `kernel.git` (≤ 2 per candidate, stale path only — NFR-001). A failed probe drops that candidate (the generic remedy still applies).
3. `stale_check.refine_stale_result(result, lane, lane_branch, mission_branch, *, mission_slug, halt_reason, siblings)` rebuilds the remediation through `_stale_remediation` with the new facts.
4. `_stale_remediation` (code lane): `[halt sentence] [sibling sentence] reopen step → implement step → (sibling: git merge <branch> in that checkout, resolve, commit | no sibling: auto-rebase refresh, resolve on stop) → review + approve → re-run consolidate`. Planning lane unchanged.
5. `lanes/consolidation._try_auto_rebase_if_stale` returns `(stale, halt_reason)`; `consolidate_lane_into_mission` computes sibling candidates from the manifest via `lane_branch_name` and refines the result before rendering.

## Test strategy

- Un-mark `tests/consolidation/test_p0_repro_7755_auto_rebase_halt_reason.py` (red on pre-fix, green after).
- New red-first CLI test (`tests/consolidation/test_7755_stale_sibling_lane_recovery.py`): real coordination Mission, `spec-kitty consolidate` refuses; parse the printed remedy, follow it (reopen, re-enter checkout, `git merge <named branch>`, resolve, commit, review + approve), re-run; assert lane-b passes and the Mission lands. Plus a no-worktree variant asserting the sibling is still named.
- Unit tests for `find_sibling_lanes`, `refine_stale_result`, and the remedy text (#7754: reopen step first, approved WP), updating the pinned texts in `tests/lanes/test_stale_remediation_cli_command.py`, `tests/lanes/test_stale_check.py` and `tests/integration/test_consolidate_upgraded_mission_recovery.py`.
- Gates: `tests/consolidation/test_single_rollback_authority.py`, `tests/architectural/test_merge_pipeline_ratchets.py`, `test_no_worktree_name_guess.py`, `test_marker_job_completeness.py`, `test_issue_named_test_census.py`, `test_no_legacy_terminology.py`.

## Project Structure

```text
src/specify_cli/lanes/stale_check.py        # result fields, sibling probe, remedy text
src/specify_cli/lanes/consolidation.py      # carry halt reason, refine the stale result
tests/consolidation/                        # repro un-marked, CLI recovery test, fixture
tests/lanes/                                # remedy/unit tests
tests/integration/test_consolidate_upgraded_mission_recovery.py  # pinned text
CLAUDE.md, docs/changelog/unreleased/       # canon sentence, changelog fragment
```

**Structure Decision**: single project; changes stay inside `lanes/` plus tests and docs.

## Implementation Concern Map

### IC-01 — Accurate, recoverable stale refusal

- **Purpose**: surface the halt reason and sibling lanes and print a remedy valid for approved work packages.
- **Relevant requirements**: FR-001..FR-006, NFR-001, NFR-002, C-001..C-003
- **Affected surfaces**: `lanes/stale_check.py`, `lanes/consolidation.py`, the tests above, CLAUDE.md, changelog fragment
- **Sequencing/depends-on**: none
- **Risks**: pinned remedy texts across three test files; terminal wrapping in CLI output (tests normalise whitespace).
