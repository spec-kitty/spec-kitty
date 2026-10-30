# Implementation Plan: Review feedback draft retirement

**Branch**: `issue-6632-review-feedback-draft-retirement` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/review-feedback-draft-retirement-01M66YR3/spec.md`
**Input**: Mission specification from `kitty-specs/review-feedback-draft-retirement-01M66YR3/spec.md`
**Issue**: spec-kitty/spec-kitty#6632

## Summary

A rejection currently records `review-cycle-N.md` and leaves the reviewer's advertised
`review-feedback-N.md` behind, untracked, in the mission directory. The next
`move-task --to for_review` (and `accept`'s `git_dirty` check) then refuses on the tool's own
output. The fix retires that draft — once, in the writer that already knows both the source file and
the durability outcome (`review/cycle.py::create_rejected_review_cycle`) — after the record's commit
has been verified durable, and only when the file is this mission's, untracked, and still holds the
bytes that were recorded. The review prompt stops claiming the draft is committed and says what
actually happens to it.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor), executed on 3.11 in CI and 3.13 locally
**Primary Dependencies**: typer (CLI), pytest, `kernel.git.listing` (`is_tracked`), the existing
`mission_runtime` placement seam and `OwnedCheckout`; no new dependency
**Storage**: Git working tree + `kitty-specs/<mission>/tasks/<wp-dir>/` files; no database
**Testing**: pytest — targeted files for the touched modules
(`tests/specify_cli/review/`, `tests/specify_cli/cli/commands/agent/`), plus one end-to-end
regression through the real `move-task` app; no full/heavy suite locally
(`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: Linux, macOS, Windows 10+ (path handling must stay cross-platform;
`to_posix`/`Path.is_relative_to` only, no string prefix checks)
**Project Type**: single CLI project (`src/specify_cli/`, `tests/` mirrors it)
**Performance Goals**: a rejection adds at most two git invocations (`ls-files` tracked probe, none
when the file is not in the mission directory) and stays under the CLI's 2 second budget
**Constraints**: never commit the draft anywhere; never fail a rejection whose record is already
durable; no change to the recorded artifact bytes; keep the typed feedback-file errors unchanged
**Scale/Scope**: one helper in `review/cycle.py`, one outcome field on
`CreatedRejectedReviewCycle`, three prompt strings in `workflow_executor.py`, a stderr note in
`tasks_verdict_persistence.py`, one new regression test module, one guide page, one changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | The retirement lives in the one module that writes the record; no caller re-implements it. The advertised filename stays owned by `review_feedback_source_path`. |
| Architectural alignment | Uses the existing durable-persistence proof (`VerdictPersistenceOutcome.verdict_durably_persisted`) and the existing git listing API (`kernel.git.listing.is_tracked`) rather than a second mechanism. |
| ATDD-First (C-011) | The regression test is written first, through the real CLI, and is red on the lane's planning base before the fix commit. |
| Locality of change (DIRECTIVE_024) | One seam + prompt strings + docs; no refactor of the writer, the classifier, or the move-task gate. |
| No fake green | The test asserts the real gate (`_validate_research_artifacts`) by *not* stubbing it — the existing sibling test stubs it, which is why this bug was invisible. |
| Terminology canon | "Mission", "work package", "repository root checkout" — no "feature". |
| Documentation standards | Guide page + `[Unreleased]` changelog entry with impact-first lead and the `(#6632)` reference. |

No violations, so `## Complexity Tracking` is not populated.

## Project Structure

### Documentation (this mission)

```
kitty-specs/review-feedback-draft-retirement-01M66YR3/
├── plan.md              # this file
├── research.md          # discovery + Phase 0 (decisions D-1..D-5)
├── data-model.md        # Phase 1: draft/record entities and invariants
├── research/            # reproduction script and transcript
└── tasks.md             # Phase 2 (/spec-kitty.tasks)
```

`contracts/` is intentionally absent: this mission changes no CLI flag, no JSON document, no
protocol and no event schema. `meta.json` records `"contracts": "none"` with a rationale so strict
`spec-kitty accept` waives the directory.

### Source Code (repository root)

```
src/specify_cli/review/cycle.py                     # the retirement seam (+ outcome field)
src/specify_cli/cli/commands/agent/workflow_executor.py  # review-prompt rejection wording
src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py  # stderr notice for a kept draft
tests/specify_cli/cli/commands/agent/test_review_feedback_draft_retirement.py  # new regression
docs/guides/how-to/missions/review-work-package.md  # user-facing how-to
docs/changelog/CHANGELOG.md                         # [Unreleased] entry
```

**Structure Decision**: single project; the change follows the existing module boundaries — the
writer stays in `review/cycle.py`, the CLI-facing notice stays in the move-task persistence module,
the prompt text stays where the prompt is rendered.

## Implementation Concern Map

### IC-01 — Retire the consumed draft at the durable-write seam

- **Purpose**: make the tree clean after the printed rejection command, without ever destroying
  feedback.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, NFR-001,
  NFR-002, NFR-003, SC-001, SC-002, SC-003
- **Affected surfaces**:
  - `src/specify_cli/review/cycle.py`: `_resolve_review_body` returns the raw source text alongside
    the composed body; a new `_retire_consumed_feedback_source(...)` helper applies the five
    predicates (durable, inside `kitty-specs/<mission>/` of the primary/owned/surface checkout,
    untracked via `kernel.git.listing.is_tracked`, bytes unchanged, unlink best-effort);
    `CreatedRejectedReviewCycle` gains `retired_feedback_source: Path | None = None` and carries
    refusal reasons in its existing `warnings` tuple.
  - `src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py`: print each warning to stderr
    (the `_warn_feedback_file_not_recorded` idiom) so a kept draft is visible without changing
    `--json` stdout.
- **Sequencing/depends-on**: none
- **Risks**: deleting a file the reviewer wanted (mitigated by the four safety predicates and one
  test each); a second read of the draft (compare-then-unlink) is deliberate TOCTOU closure, not
  duplication; `is_tracked` raises `GitCommandError` outside a repository — that must degrade to
  "keep the file", never to an exception.

### IC-02 — Prompt wording, docs, changelog

- **Purpose**: stop telling reviewers the draft is committed, and document the contract.
- **Relevant requirements**: FR-007, SC-004
- **Affected surfaces**:
  - `src/specify_cli/cli/commands/agent/workflow_executor.py`: the two rejection blocks
    (`_build_review_prompt_lines` ~2318 and ~2366) and the closing "handles all file updates
    automatically" line (~2376).
  - `docs/guides/how-to/missions/review-work-package.md`: state that the advertised draft is
    retired when the record is committed, and that a file outside the mission directory is left
    alone.
  - `docs/changelog/CHANGELOG.md` `[Unreleased]` → `### Fixed`: impact-first lead with `(#6632)`.
- **Sequencing/depends-on**: none (independent of IC-01), but lands in the same PR
- **Risks**: the CLI `--review-feedback-file` help text and its fixture
  (`tests/specify_cli/.../fixtures/tasks_cli/help/move-task.help`) plus the generated
  `docs/api/agent-subcommands.md` are deliberately left unchanged: the help stays accurate for a
  path outside the mission directory, and touching it forces a generated-docs regeneration whose
  drift gate is not worth the blast radius for a P2 wording improvement.

## Design: the retirement predicate

```text
retire(feedback_source, recorded_source_text, persistence, mission_dirs):
    1. persistence.verdict_durably_persisted is True           else keep
    2. resolved source is inside one of mission_dirs           else keep (silently: not ours)
    3. is_tracked(source) is False                             else keep (committed: tree already clean)
    4. current text == recorded_source_text                    else keep + warn (edited after recording)
    5. unlink() succeeds                                       else warn (kept)
```

`mission_dirs` = `kitty-specs/<mission_slug>` under each of: `main_repo_root` (the repository root
checkout that `move-task`'s Check 1 reads), the write `surface_root` (coordination worktree in a
coord topology), and `owned.owned_root` when the mission runs in an owned checkout.

## Phase 0 — Research outcome

Already recorded in `research.md` (D-1 reproduction, D-2 code map, D-3 decision, D-4 safety
predicates, D-5 prompt/docs). No `NEEDS CLARIFICATION` remains, and the mission adds no dependency,
so the supply-chain section requires no check.

## Phase 1 — Design output

- `data-model.md` — the two entities (draft, record), their invariants and the retirement
  transition table.
- `contracts/` — none; recorded in `meta.json` as `"contracts": "none"` with a rationale.
- `quickstart.md` — not produced: the mission has no runnable surface beyond the existing CLI, and
  the reproduction script in `research/` already documents how to observe it.

## Review posture

Small, single-seam fix with a destructive operation in it, so review gets two lenses rather than a
full adversarial squad: correctness/durability of the delete, and blast radius (does any other
caller of `create_rejected_review_cycle` change behaviour). Both are answered in the PR's
`## Tests run` block.
