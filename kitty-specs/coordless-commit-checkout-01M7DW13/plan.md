# Implementation Plan: Coordination-less status commits take their checkout from the placement seam

**Branch**: `kitty/mission-coordless-commit-checkout-01M7DW13` (lands on `fix/7633-7637-7648-coordless-commit-checkout`) | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/coordless-commit-checkout-01M7DW13/spec.md`

## Summary

Three bug fixes in the bookkeeping-commit path, one runner (#7633, #7637, #7648). The
coordination-less arm of `BookkeepingTransaction.acquire` takes its checkout from the placement
seam and refuses up front, with `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH`, when that checkout
is not on the write branch (operator ruling Q8). The review claim commits only its status pair.
`commit_idempotent` treats the typed "staged tree unchanged" signal as its no-op. The legacy
commit leaf's pre-check asks the checkout the commit runs in. Grounding:
`docs/plans/engineering-notes/2026-11-14-7633-7637-7648-coordless-commit-checkout.md`
(reproductions, invariants, gates, discovery squads).

## Engineering Alignment

- **Seam answer (FR-001):** checkout = `placement_seam(repo_root, slug, owned=owned).write_dir(STATUS_STATE).surface_root`
  when the caller's destination ref equals `write_target(STATUS_STATE).ref`; otherwise the
  repository root checkout (the fallback #7633 proposes). Coordination-less topologies declare
  every kind PRIMARY, so `write_dir` has no side effects here.
- **Hold check (FR-002):** the chosen checkout's symbolic HEAD must be the destination ref, else
  `BookkeepingPolicyRefused(Refused(error_code=STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH, ...))`
  before any write (callers already render `BookkeepingPolicyRefused`). The remedy names the
  checkout and the ref; it does not probe the holder.
- **PRIMARY arm (FR-003):** `_primary_partition_holder` becomes the PRIMARY-kind seam answer
  (`write_dir(WORK_PACKAGE_TASK).surface_root` when the ref is that kind's `write_target` ref,
  else the repository root checkout). No new refusal on that arm (out of the rulings' scope;
  `safe_commit`'s HEAD assertion keeps guarding it). `_write_branch_holder` is deleted.
- **Review claim (FR-004):** `review_claim_transition` passes
  `claim_status_pair_paths(_collect_status_artifacts(feature_dir))`, as the implement claim does.
- **Idempotent commit (FR-005):** `commit()` gains a keyword-only internal flag used only by
  `commit_idempotent`: on `SafeCommitStagedTreeUnchanged` it returns `_noop_commit_receipt()`
  without rollback. The strict path is untouched.
- **Legacy pre-check (FR-006):** pre-check root = `repo_root`; short-cut only when every path's
  containing checkout (`kernel.git_anchor.checkout_root_in_spelling`) is `repo_root`. Delete
  `_resolve_legacy_porcelain_root`.
- **Gate entry (FR-007):** repoint the `checkout_branch_or_fallback` allowlist entry from #2453
  to #1878.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); no dependency change, so no supply-chain check applies
**Storage**: git repository files (`status.events.jsonl`, `status.json`)
**Testing**: pytest; real git repositories through the Mission-create core (`tests/coordination/test_coordless_status_commit_checkout.py`), the review-range acceptance tests, `tests/specify_cli/coordination/test_transaction.py`, legacy-leaf tests; blast radius per CLAUDE.md
**Target Platform**: Linux, macOS, Windows 10+ (CLI)
**Project Type**: single
**Performance Goals**: one extra seam construction and one `git symbolic-ref` per coordination-less acquire (NFR-002)
**Constraints**: no write before a refusal (NFR-001); strict commit unchanged (C-002); no root fallback for shape (b) (C-003)
**Scale/Scope**: 4 source files (`coordination/transaction.py`, `coordination/types.py`, `cli/commands/agent/workflow_executor.py`, `cli/commands/agent/workflow.py`), one docstring in `git/commit_helpers.py`, one gate allowlist entry

## Charter Check

- **Single canonical authority / C-001:** passes — the arm consumes the seam; a raw probe is removed, none added.
- **Red first (Standing Order 4, C-004):** passes — all three reds are reproduced on `d7cedd7e` (grounding note).
- **Architectural gate discipline (Standing Order 5):** passes — no allowlist growth; one stale citation repointed.
- **Pause-and-escalate:** shape (a) refusal is Decision Moment `01M7DW21P5D4WNVCGC6ARASAV3`, raised to the operator; the T004 legacy-leaf test replacement (an asserted-expectation edit) is raised too. Both proceed on the recommended option unless overruled.
- **No full heavy suites:** targeted files and named gate files only.

## Project Structure

### Documentation (this mission)

```
kitty-specs/coordless-commit-checkout-01M7DW13/
├── plan.md
├── research.md
├── spec.md
├── checklists/requirements.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/coordination/transaction.py        # FR-001..003, FR-005
src/specify_cli/coordination/types.py              # FR-002 error code
src/specify_cli/cli/commands/agent/workflow_executor.py  # FR-004
src/specify_cli/cli/commands/agent/workflow.py     # FR-006
src/specify_cli/git/commit_helpers.py              # docstring only (#7633)
tests/coordination/test_coordless_status_commit_checkout.py   # new matrix
tests/specify_cli/coordination/test_transaction.py            # FR-005
tests/integration/review/test_review_range_acceptance_action.py  # FR-004 (lift removed)
tests/specify_cli/cli/commands/agent/test_coord_commit_integrity_e2e.py  # FR-006
tests/architectural/test_no_write_side_rederivation.py        # FR-007
docs/changelog/unreleased/                                     # fragments
```

**Structure Decision**: single project; edits stay in the modules that own the behaviour.

## Implementation Concern Map

### IC-01 — Seam-owned coordination-less commit checkout

- **Purpose**: the coordination-less and PRIMARY arms of the transaction take their checkout from the seam and refuse when it is not on the write branch.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-007, NFR-001, NFR-002
- **Affected surfaces**: `coordination/transaction.py`, `coordination/types.py`, `git/commit_helpers.py` (docstring), `tests/coordination/test_coordless_status_commit_checkout.py`, `tests/architectural/test_no_write_side_rederivation.py`
- **Sequencing/depends-on**: IC-02 (shares `transaction.py`; the smaller fix lands first)
- **Risks**: existing transaction tests that build Missions whose root is not on the destination ref would now refuse; each such test is classified (stale shape vs real regression) and surfaced, never edited silently.

### IC-02 — Follow-up commits never fail on unchanged content

- **Purpose**: the review claim commits only what it wrote, the idempotent commit treats an unchanged tree as a no-op, and the legacy leaf's pre-check asks its own checkout.
- **Relevant requirements**: FR-004, FR-005, FR-006
- **Affected surfaces**: `coordination/transaction.py` (`commit_idempotent`), `cli/commands/agent/workflow_executor.py`, `cli/commands/agent/workflow.py`, their tests
- **Sequencing/depends-on**: none
- **Risks**: the T004 tests pin the deleted helper; they are replaced by behaviour tests (operator informed).
