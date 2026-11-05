# Implementation Plan: doctor workspaces --remote

**Branch**: `issue-7214-doctor-workspaces-remote` | **Date**: 2026-11-05 | **Spec**: `kitty-specs/doctor-workspaces-remote-01M6P9ZF/spec.md`
**Input**: GitHub issue #7214 (found by the landing review of PR #7196 / issue #7173)

## Summary

Give `spec-kitty doctor workspaces` an explicit `--remote <name>` (default
`origin`) that selects which remote's tracking refs prove a landing: the primary
branch name is resolved from `refs/remotes/<remote>/HEAD` (falling back to the
existing resolver), and the absorption proof reads
`refs/remotes/<remote>/<primary>`. The option threads through the report and
through `--prune`, including the pre-removal re-assessment, so the two can never
use different remotes. An unconfigured remote is refused before any verdict.

The proof is not weakened: exactly one named remote's primary ref is read, never
"any remote that happens to contain the tip". Nothing is fetched (NFR-001).

## Technical Context

**Language/Version**: Python 3.11 (repo `.python-version`), `from __future__ import annotations`
**Primary Dependencies**: `kernel.git` (`run_git`, `decode_path`), `kernel.git.remote` (`configured_remotes`, `tracking_ref`), `specify_cli.git.destructive_guard`, `specify_cli.core.git_ops.resolve_primary_branch` / `COMMON_PRIMARY_BRANCHES`, Typer for the CLI surface
**Storage**: N/A (reads git refs only)
**Testing**: pytest; real repositories with bare remotes (`pytest.mark.integration`, `pytest.mark.git_repo`), process probe injected with an empty fake `/proc`
**Target Platform**: Linux (the prune's process probe is `/proc`-based; the assessment is portable)
**Project Type**: single library + CLI
**Performance Goals**: no per-worktree git call added; the remote decision is resolved once per assessment (`_context`) and once per prune run
**Constraints**: zero network contact; default (`origin`) behaviour unchanged; verdict/reason enums and their documented first-match order unchanged
**Scale/Scope**: two source modules plus the CLI shell, one rendering module, two new test files, three doc surfaces

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|------|---------|
| Single canonical authority | PASS — the absorption proof keeps one authority (`is_absorbed`); this Mission only chooses which ref feeds it, and reads remote facts through `kernel.git.remote`. No second "landed" predicate is introduced. |
| ATDD-first / red-first | PASS — the fork-clone reproduction is a failing test through `assess_worktrees` / `run_workspaces` before the fix (DIRECTIVE_034). |
| Locality of change (DIRECTIVE_024) | PASS — the remote name is threaded through the existing seam; no new module, no new reason code, enums untouched. |
| Smallest viable diff / Boy Scout (DIRECTIVE_025) | PASS — the `unproven` details that named `origin` unconditionally are corrected in place rather than left to a follow-up. |
| No weakened safety | PASS — the destructive guard and `LANDED_INTENT` path are untouched (C-003); a remote mismatch between report and prune fails closed. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctor-workspaces-remote-01M6P9ZF/
├── plan.md              # this file
├── spec.md              # mission specification
├── research.md          # discovery findings and the decisions behind them
├── contracts/
│   └── doctor-workspaces-remote.md   # the option's contract (flags, JSON, messages)
└── tasks.md             # work packages (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── workspace/landed_worktrees.py          # remote-aware context, primary resolution, fail-fast
└── cli/commands/
    ├── doctor.py                          # the `workspaces` command shell gains --remote
    ├── _workspace_husk_doctor.py          # run_workspaces threads the remote
    └── _landed_worktree_doctor.py         # rendering, JSON payload, prune hints

tests/specify_cli/
├── workspace/test_landed_worktrees_remote.py      # new: assessment/prune on a fork clone
└── cli/commands/test_doctor_workspaces_remote.py  # new: the option through the CLI
```

**Structure Decision**: keep the decision logic in
`specify_cli.workspace.landed_worktrees` (where the landed check already lives)
and the rendering in `_landed_worktree_doctor`. New tests go in their own files
so the sibling issues on the same pruner seam (#7211, #7212) edit disjoint test
files; the source edits are additive and land in functions they do not touch
(`_prune_one`, `_delete_landed_branch`).

## Complexity Tracking

*No charter violations; table intentionally empty.*

## Implementation Concern Map

### IC-01 — Remote-aware landed proof

- **Purpose**: make the primary ref the proof reads a function of a named remote instead of the hardcoded `origin`.
- **Relevant requirements**: FR-001, FR-005, NFR-001, NFR-003, C-001
- **Affected surfaces**: `src/specify_cli/workspace/landed_worktrees.py` (`_context`, `_primary_resolved`, a new `_remote_head_branch` / `_primary_for` pair, `_absorption` detail, `assess_worktrees`, `prune_landed`, `WorktreeAssessment`)
- **Sequencing/depends-on**: none
- **Risks**: `resolve_primary_branch` is `origin`-biased; the remote's own `HEAD` must win when present, and the "only a guess" refusal must keep refusing a fallback name that no remote head vouches for.

### IC-02 — Option surface, fail-fast and messages

- **Purpose**: expose the remote on `doctor workspaces`, refuse an unconfigured one before any verdict, and keep every printed command runnable.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-006
- **Affected surfaces**: `src/specify_cli/cli/commands/doctor.py`, `_workspace_husk_doctor.py`, `_landed_worktree_doctor.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the prune hint printed per landed worktree hardcodes `spec-kitty doctor workspaces --prune`; with a non-`origin` remote it must carry `--remote` or the copy-pasted command silently does nothing.

### IC-03 — Docs and changelog

- **Purpose**: the runbook's removal step and the generated CLI reference must state the option, and the changelog fragment must record it.
- **Relevant requirements**: FR-001, FR-004, FR-006
- **Affected surfaces**: `docs/development/how-to/pr-landing.md` (step 12), `docs/api/cli-commands.md` (`doctor workspaces` section), `docs/changelog/unreleased/<pr>.fixed.md`
- **Sequencing/depends-on**: IC-02 (the option's final help text)
- **Risks**: `docs/api/cli-commands.md` is generated; regenerate the `doctor workspaces` rows only and verify with the freshness checker rather than trusting a full rebuild on a shared host.
