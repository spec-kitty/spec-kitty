---
title: Owned-checkout lifecycle resolution repair
description: How mission creation and next-step work package lookup retain the validated checkout, with regression evidence and explicit qualification limits.
doc_status: reference
updated: 2026-09-24
---

# Owned-checkout lifecycle resolution repair

An explicitly validated `--owned-checkout` selects the mission write surface.
Mission activation, mission-type context and specification template resolution
must read that same checkout. Previously those three reads used the primary
checkout, rejecting an activated feature checkout when primary was inactive,
or accepting primary activation when the owned checkout was inactive.

The repair keeps ownership validation and the inactive-charter refusal intact.
The existing `effective_root` is the single configuration root after validation;
without an owned checkout it remains the primary root.

The same scope must survive task finalization into implementation. Runtime
decisions now retain `effective_root` through composition advancement, WP
metadata, prompts and lane membership reads. Metadata caches are keyed by the
selected read checkout. Explicit single-branch missions execute in their
existing owned checkout; Git identity and primary-only charter authoring policy
remain separate from this read scope.

Status reads also carry explicit owned-checkout authority. A validated
single-branch checkout can live under the repository's `.worktrees` directory
without becoming a coordination checkout. The reader validates the canonical
primary root, owned checkout, mission directory, topology and target branch
before reading events. Existing primary and coordination contract guards remain
unchanged for callers that have not supplied that explicit authority.

## Evidence and implementation log

- Regression reproduced both incorrect outcomes before the implementation:
  two failing cases in `tests/core/test_mission_creation_owned_charter.py`.
- After repair, owned-charter, unborn-HEAD and topology tests: 15 passed.
- Required `make test-fast`: 2,043 passed, 5 skipped, 4 failed. All four
  failures reproduce with the changed source restored to upstream `d6533ea41`:
  retired ignored cache directories and three charter JSON tests that reject
  execution from a linked checkout. Baseline rerun: 8 passed, same 4 failed.
- Explicit checkout CLI successfully created Filament mission
  `01M38TT2CK60FXADS9WXBT6TKF` in its owned worktree while primary remained
  inactive. No global installed package was changed.
- User experience finding: the old error recommended activating a charter that
  was already active in the caller's explicitly selected checkout.
- Decision: resolve all three configuration/template reads consistently; do not
  weaken the guard, mirror configuration into primary or patch installed tools.
- Limitation: this is source qualification, not a released CLI installation.
- Follow-up regression: finalized owned-only WP lookup and same-slug metadata
  isolation both failed before repair (test-first commit `edaa9cd83`).
- Integration and workspace regression run: 120 passed. The owned mission has
  no primary counterpart; the next decision mapper emits a real WP prompt and
  the existing checkout path without creating another lane.
- Real Filament run `36da1c14fa454bdab888f1d1a837c8f6` now emits
  `kind=step`, `action=implement`, `wp_id=WP01` in its existing owned checkout.
  This is workflow qualification, not implementation or production acceptance.
- Runtime bridge, blocked-path and prompt regression tests: 144 passed, 1 skipped.
- Independent review found remaining composition-policy and review-base scope
  leaks. Test-first `1be5352ee` reproduced both; `b1a1693bf` fixes them. Six
  focused composition/review tests pass, including a real changed-file diff
  against a claim commit with divergent primary metadata. Missing claim proof
  is explicitly unavailable, never a primary-base or branch-to-itself fallback.
- In-repository owned task finalization reproduced a status contract refusal
  because path shape overrode validated ownership. Test-first `4ff6ff0c0`
  reproduced it alongside the missing explicit contract (3 failed, 2 passed).
  The fix carries owned scope into both event and complete-stream readers;
  the five regression cases pass, including invalid roots and coordination
  rejection. Source qualification does not change the global CLI installation.

Workspace: reused the clean review-thread-closure checkout, preserving its two
unmerged commits on its prior branch. Primary has unrelated dirty changes and
the redact-operation-request checkout retains unmerged work. No checkout was
added. This repair owns the temporary fourth active branch exception until
2026-10-01; after operator merge, audit and retire its branch and release the
reused workspace when dependencies permit. No storage-recovery claim is made.
