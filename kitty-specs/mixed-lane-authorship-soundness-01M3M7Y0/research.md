# Research — Mixed-lane authorship soundness

Grounded on `origin/main` `dccf6aa7` by profile-loaded agents (debugger-debbie code-truth, planner-priti tracker, python-pedro campsite, architect-alphonso design ×2, reviewer-renata post-spec, researcher-robbie capture seam, debugger-debbie fixture). Citations are `file:line` at that SHA.

## R-1 The hole is strategy-independent
- **Decision**: fix the gate's *claim*, not a strategy axis (C-003).
- **Rationale**: `_lane_is_approved` is `any()` (`consolidation/reconciliation.py:1185`); `_collect_authored` walks the whole first-parent spine of such a lane (`:1369-1382`); `_collect_excluded` subtracts that authorship (`:1177-1182`). Squash passes via `authored_blobs`; merge/rebase via the SHA subtraction + closed-world (`_unattributable_content`, `:523-556`).
- **Alternatives**: squash-only patch — rejected (merge leaks identically).

## R-2 Where attribution lives (C-001/C-002)
- **Decision**: `policy_metadata["lane_head"]` on status events.
- **Rationale**: `StatusEvent.policy_metadata: dict[str, Any] | None` (`status/models.py:363`, serialized `:385`, parsed `:432`) is already a free-form sidecar (claim metadata, `status/emit.py:255`); `spec_kitty_events.diary` declares it `dict[str, Any]`; the `extra='forbid'` `StatusTransitionPayload` never carries it and the Zeitgeist bridge drops it (`status/zeitgeist_bridge.py:161-193`). The event log is already the canonical lifecycle authority.
- **Alternatives rejected**: WP frontmatter `base_commit` (fresh-lane only, `lanes/implement_support.py:219-235`; frontmatter state retired); workspace context (`.kittify/workspaces/` gitignored); `lanes.json` (static); commit trailers (hooks retired, `m_2_0_0_retire_git_hooks`); commit-guard `owned_files` (lanes collapse *by* overlapping write scope — ambiguous by construction).

## R-3 Capture seam
- **Decision**: inject `lane_head_probe` into `status/transition_pipeline.prepare_transition` (`:177`), stamp before `build_status_event` (`:313-331`); default probe in new `status/lane_head.py`.
- **Rationale**: all four persisting call sites (`status/emit.py:944,1051`, `coordination/status_transition.py:1528,1836`) go through it; the funnel is enforced by `tests/architectural/test_no_legacy_status_emit_callers.py`. The pipeline is pure with injected readers (`infer_implementation_evidence`, `:171-173`) and pinned free of `subprocess` (`tests/status/test_transition_pipeline.py:369-380`).
- **Alternatives**: stamping in each emitter (implement, move-task, orchestrator, verdicts, recovery, bootstrap, aggregate) — rejected (convention every caller must remember; DIRECTIVE_043).

## R-4 Lane branch resolution at transition time
- **Decision**: reuse the `lanes/for_review_gate.py:82 _resolve_lane` pattern — lanes.json from the PRIMARY partition via the placement seam, `manifest.lane_for_wp` (`lanes/models.py:155`), `lane_created_branch` (`lanes/compute.py:65`), `git rev-parse --verify refs/heads/<branch>`.
- **Rationale**: branch refs are shared across worktrees; `feature_dir` is the coord worktree under coord topology. `read_lanes_json` returns `None` pre-finalize and raises `CorruptLanesError` on corruption (`lanes/persistence.py:81`) → no stamp. The planning lane (`is_planning_lane`) is never stamped. Import function-locally (`test_cold_import_status_boundary.py`).

## R-5 Window semantics
- **Decision**: implementation windows = intervals in `{claimed, in_progress}`; review windows (`for_review`/`in_review`) secondary; iterate events in append order.
- **Rationale**: `implement` creates the lane workspace and makes dependency/base merges (`cli/commands/implement.py:2106`) *before* emitting `claimed`+`in_progress` in one batch (`status/work_package_lifecycle.py:190-213`), so workflow merges fall outside every window. Rework re-enters `in_progress` from `in_review`/`approved`/`blocked` (`work_package_lifecycle.py:261`); rejection goes to `planned` (`tasks_move_task.py:3058`). Review fix-up commits would otherwise fall outside every window. Causal order, not wall-clock (issue 4941 caveat, see CLAUDE.md reducer duality).
- **Alternatives**: one window from first claim to cancel — rejected (swallows siblings' interleaved rework, false REFUSE).

## R-6 Fixture materialization abort (#5047)
- **Finding**: neither recorded limitation reproduces at `df94ef30`. `build_coord_mission_mixed_lane` consolidates under the default squash (exit 0, "squash content attribution verified"); post-build `commit-tree`+CAS `update-ref`, a throwaway `git worktree add`/remove, and a main-repo checkout+explicit-path commit all still consolidate. The only "unmaterialized" trigger is a missing coord worktree directory (`probe_coord_state`, `missions/_read_path_resolver.py` ~L313; control: `git worktree remove --force` on the coord worktree → abort). `git add .` at the fixture root stages `.worktrees/<coord>` as a gitlink and trips the dirty-target guard (`git/ref_advance.py:144`) — a fixture-authoring hazard, not a product bug.
- **Decision**: classify as fixture/harness artifact (not sibling-slice product work); the builder gets a `.worktrees/` ignore + explicit-path adds; FR-008 re-scoped to correct the record with a test.
- **Red-first evidence**: a prototype mixed-lane builder with WP02 canceled from `in_progress` after committing `src/pkg/wp02.py` consolidates under the default squash to **exit 0 / PASS with the canceled file on main** — the #5046 bug, observed live. Measured: `tests/terminus/test_repro_5018.py` body ~32 s, fixture setup ~39 s (issue text said ~14 s).

## R-7 Supersession
- **Decision**: path-level; the canceled final state is dropped when a later non-canceled first-parent commit touches the path or when it equals the state at `coord_base_ref`.
- **Rationale**: matches `_final_authored_walk` (`reconciliation.py:1207-1260`) newest-first semantics; hunk-level is out of scope (C-007) with the residual pinned (FR-009).

## R-8 Verdict wiring
- **Decision**: a new `Divergence.canceled_content` (FAIL, rendered by `describe()`), computed in a verifier step that runs for every strategy after the claim-integrity refusals; mixed-lane attribution failures surface as `ApprovedWpCommitSet.refusal` (REFUSE, existing path `reconciliation.py:489-493`).
- **Rationale**: FAIL and REFUSE both force non-zero exit and restore the target (`VerifyStatus` docstring, `:128-142`); only the rendered verdict distinguishes them, so tests assert the verdict text (post-spec BLOCKER 1). Leaving `authored_*` untouched removes the issue 5018 regression surface.

## R-9 Residual hunt (post-plan, debugger-debbie) — dispositions
| ID | Finding | Disposition |
|---|---|---|
| R1 | self-revert/deletion base was `coord_base_ref` → survivor's approved add/change undone by the canceled WP ships | **changed**: pre-state = lane content before the canceled WP's first change to the path (D-3/D-4, SC-007) |
| R2 | canceled hunk 3-way merged with an independent change: target blob ≠ canceled blob, merge closed-world passes | **changed**: T ∉ {canceled, pre, window-base} → REFUSE (D-4) |
| R3 | merge commits list both sides' paths; coord auto-rebase merges land inside windows | **changed**: merges never attribute or supersede; bookkeeping paths filtered (D-2/D-3) |
| R4 | identical state from elsewhere (target already had it / another approved lane authored it) | **changed** for target-already-had-it (W == canceled and the pre-state was inherited → no finding; if the pre-state was produced by a surviving lane commit → FAIL, since approved work was undone — post-tasks BLOCKER fold); another-lane-identical **deferred_with_rationale** (FAIL = safe direction; documented) |
| R5 | review-window fix-up for a queued sibling attributed to the canceled WP | **changed**: attribute only if no other WP holds a window over the commit; else REFUSE |
| R6 | blocked-state commits / post-cancel commits / detached-HEAD commits unattributed | **changed**: blocked counts as implementation; post-cancel **deferred_with_rationale** (documented limitation) |
| R7 | concurrent WPs in one lane → contested → REFUSE | **accepted** with actionable message + pinned test |
| R8 | stamp "on spine" test would reject the fork-point stamp | **changed**: validity = ancestor-or-equal of lane tip |

## R-10 Brownfield (post-plan, paula-patterns) — dispositions
- B1 probe default would break pipeline purity → **changed**: shells inject, `None` = no stamp, named pin.
- B2 second "canceled" definition → **changed**: mixed lane uses `excluded_canceled_wp_ids`.
- B3 tolerant spine helper would vacuously PASS → **changed**: direct `first_parent_commits_in_range`, error → refusal.
- B4 lane-sync merges inside windows → **changed** (with R3).
- B5 `cutover_eligibility` keyed on any `policy_metadata` → **changed** (campsite in IC-03).
- B6 no duplicate record exists; `_collect_excluded` docstring asserts the hole → **changed** (docstring corrected).
- B8 issue 5069 (commits by a never-claimed WP) → **deferred_with_rationale**: outside every window; documented next to FR-009. issue 5080 / issue 5151 → cited as REFUSE causes. for_review gate satisfied by a sibling's commits → follow-up issue.
- B9 sizing → **changed**: estimates raised; SC-006 time-boxed as its own concern.

## Adversarial evidence
No dependency added; supply-chain section not applicable.
