# Research — consolidation-claim-rollback-integrity-01M3PD1T

Grounded on main `e4a1a55c` by a four-lens squad (code-truth with real-CLI repros, similar-issues, campsite, architecture) and a post-spec sizing lens. Findings dispositions below.

## D1 — Where to act on a claim-time refusal (#5338)
- **Decision**: at the end of `_capture_reconciliation_claim`, inside `_clear_fresh_record_on_pre_mutation_exit`, through a new pure `claim_integrity_refusal(claim)` in `reconciliation.py` (same checks as gate steps 1–3). Exempt `_resume_reconciliation_already_passed`.
- **Rationale**: no phase reordering (frozen-order pin), fresh record auto-cleared, one predicate for claim and gate (single authority). `verify()` is rewired to the predicate only after #5359 lands (it is #5359-owned).
- **Alternatives**: a new phase before `_phase_merge_lanes` (rejected: breaks the frozen phase list, edits a #5359 function); duplicating `_refusal_reason` (rejected: second authority).
- **Evidence**: code-truth repro B — main builds a REFUSE claim on `--resume` after a lane branch is deleted, nothing acts on it, and the gate REFUSE leaves the target at the done-bookkeeping commit.

## D2 — Rollback mechanism (#5318) — operator DM 01M3PD3VP1YTQ4D17HT96JA0T2
- **Decision**: CAS ref restore of every snapshotted branch via one authority (`consolidation/rollback.py`), supersedes AC-B3 revert-only on this path; amend ADR 2026-09-19-1.
- **Rationale**: a forward `git revert` leaves lane tips ancestors of the mission/coordination branch, so the next run's first-parent authored range stays empty and #5318 persists (campsite finding 4). CAS restore returns the branch to the exact pre-run commit.
- **Alternatives**: revert + durable anchor surviving `--abort` (rejected by operator).

## D3 — CAS expected value (post-spec finding 2; post-plan split-brain fold)
- **Decision**: persist `post_mutation_refs` after every mutating phase and immediately before the gate; that is the CAS expected value for both the in-process rollback and a later `--abort`. A branch with no recorded post tip that differs from its snapshot is NOT_RESTORED — never guessed.
- **Rejected**: "snapshot is-ancestor-of current" fallback — it accepts a third party's later commit (e.g. an operator's own commit on the target between the failed run and `--abort`) and overwrites it.
- **Rationale**: reading the live tip as "expected" (today's `_rollback_target_after_failed_reconciliation`) makes CAS vacuous against a concurrent move (SC-005 would pass without testing anything).

## D4 — Verified-landing guard (post-spec finding 3) — FR-011
- **Decision**: the authority refuses (retains everything) when `reconciliation_passed_target_sha` equals the current target tip, or any snapshotted branch no longer resolves.
- **Rationale**: `--abort` after a crash mid-teardown, or a projection refusal on the resume short-circuit, would otherwise revert a verified landing whose lane branches may already be deleted — destroying the only copy of approved work. This replaces FOLD-5's blanket "never roll back a projection refusal" with a precise guard.

## D5 — Hook point for the gate phase (post-spec finding 5)
- **Decision**: wrap the single `_phase_reconcile_before_teardown(run)` call in the driver (`except typer.Exit` with non-zero code → rollback → re-raise). One call-site edit in a #5359-touched function; the gate body is not edited.
- **Alternatives**: replace the rollback call inside the gate body (squad proposal; rejected for main: the gate body is #5359-rewritten and on main a REFUSE never reaches that call); a context manager around the whole mutation span (rejected: re-indents a #5359 function, widens the invariant to exits that already have rollbacks — R3).
- **Consequence**: WP work does not wait on #5359 merging; expect one textual rebase conflict.

## D6 — #5296 direction — operator DM 01M3PJWGGKTRT9W03MJHFV44Q2 (supersedes DM 01M3PD41NQ6J6EX8V2HYDDRGPZ)
- **Decision**: skip the code-lane merge and waive code-lane ancestry when the planning lane's worktree is the repository root checkout on the target branch.
- **Rationale**: refusing deadlocks — `_assert_mission_terminal_ready` (executor.py:501-550) requires every WP (incl. the planning WP) approved before consolidation, and there is no per-lane consolidate (post-spec finding 1).
- **Alternatives**: refuse at finalize-tasks (strands existing missions); gate attributes pre-landed content (green-washes a bypass of the attribution window).

## D7 — Scope boundary (post-spec finding 4)
- In scope: claim refusal, gate FAIL/REFUSE, projection refusal, `--abort`. Out: post-PASS exits (push, teardown — resumable) and the other in-phase exits with their own rollbacks (residual R3, follow-up under #5001). Residuals R1/R2 (PR #5285/#5305) out.

## Deferred (named, not ticketed)
- Fold `_reset_coord_to_checkpoint` (revert), `_revert_orphan_target_bake_commit`, byte restores and the target-only `_rollback_target_after_failed_reconciliation` into the single authority; retire the live `run.pre_mutation_coord_*` twin.

## D8 — Post-plan squad folds
- Single capture: `capture_pre_mutation_snapshot` is the only writer; legacy anchors are projections (split-brain fold).
- Census: `git/ref_advance.py` is qualname-keyed in `test_destructive_op_routing.py`, not blanket-exempt → extract `_resync_checkouts`, re-key the allowlist entry.
- Residue: resync passes `is_residue=is_toolchain_generated_churn`.
- `_dispatch_abort` complexity: extract a helper (local ruff ignores C901 for consolidate.py; Sonar does not).
- #5296 waiver lives only in `_approved_dependency_lane_refs`; discriminator is root-checkout HEAD == target branch (every planning lane resolves to repo_root).
- #5332 repro requires coordination topology (projection refusal unreachable in LANES).
- Citation fix: "AC-B3" is the no-raw-update-ref ratchet (honoured); the revert-only rule lives in ADR 2026-09-19-1 "unify, don't fork" and `_reset_coord_to_checkpoint`'s docstring.
- New residual (R3 family, filed as #5385): LANES mission targeting a protected branch — uncaught `BookkeepingPolicyRefused` after the squash leaves the target advanced.
- `--dry-run` never forecasts a claim refusal today; surfacing it needs a dry-run JSON contract change and overlaps #5329 → follow-up note only.
