# Research: Frozen lanes for started work packages

Phase 0 research for this mission is the pre-spec grounding squad
([research/code-grounding.md](research/code-grounding.md)) plus the post-specify squad
([research/squad-post-specify.md](research/squad-post-specify.md)). This file records the plan-level questions those
reports left open, and how the plan answers them.

| # | Question | Decision | Rationale | Alternatives rejected |
|---|---|---|---|---|
| R1 | Where does the invariant live? | A constraint input of the pure `compute_lanes`, re-checked at the `compute_and_write_lanes` chokepoint | One decision site. The #5573 reproduction becomes a preserving success. Compute stays pure (C-002). | A post-hoc diff in finalize: it would refuse the repro, and the heuristic would stay the authority. Freezing all lanes: it breaks supported amendments of unstarted WPs. Compute reading status/git: it breaks purity. |
| R2 | How is "started" decided? | History-based: any event with `to_lane ∉ {planned, blocked, canceled}`, plus lane-work-tip fallback evidence for lanes with no history-started member | The FSM resets (`in_progress/in_review/approved → planned`) and forced or `blocked → in_progress` moves would otherwise unfreeze committed work | Current-state `lane != planned` (the planning-pin predicate): misses resets, and counts `planned → canceled` |
| R3 | How are lane tips read without N git calls? | `recorded_tip_branches(repo_root)`: one `git for-each-ref --format=%(refname) refs/spec-kitty/lane-tip/` | NFR-001 (≤ 200 ms for 30 WPs) | One `read_tip` call per lane |
| R4 | When does the refusal fire? | A read-only preflight after the ownership gates and before `_emit_tasks_started` (the first status write) | No status commit to undo (#5641). Finalize's write-scope restore covers frontmatter and `tasks.md` (SC-003). Validate-only gets the same check (FR-009). | Inside the commit pipeline only: it fires after the status writes and relies on restore |
| R5 | Absent vs unreadable status log | Absent → no history-started WPs (proceed). Malformed (`StoreError`) or an unresolvable surface → refuse `status_unreadable` | A legacy `agent tasks finalize-tasks` writes `lanes.json` before seeding status (`tasks_finalize.py:308-330`) | Refuse whenever no log exists |
| R6 | Started lane-mates split by an amendment | Pre-union them in the union-find with a `frozen_lane_membership` collapse event | Both WPs' commits live on the same branch; preservation beats refusal | Refuse the split |
| R7 | Which lane ids are reserved from minting? | The recorded lane ids of every started WP, including started WPs excluded by the #3713 cancellation projection | An orphaned id whose branch holds commits must not be handed to new work (FR-004) | Reserve every previous id: it changes unstarted-only re-letter behaviour without need (SC-004) |
| R8 | Property testing without hypothesis | `pytest.mark.parametrize` over `itertools.product` / `combinations` | Supply-chain tactic, C-006; precedent `tests/terminus/test_terminus_reconciliation_property.py` | Adding hypothesis |
| R9 | Error-code shape | `LaneMembershipFrozenError(LaneComputationError)` with `error_code: ClassVar = "LANE_MEMBERSHIP_FROZEN"`, structured conflicts, rendered by the existing terminal renderer | Mirrors `LaneDependencyCycleError` (`compute.py:218`) and its rendering branch (`mission_finalize_commit.py:922-972`) | A `StructuredError` subclass (another family) |

No dependency is added, removed or upgraded, so the supply-chain section does not apply (DIRECTIVE_051 not triggered).
