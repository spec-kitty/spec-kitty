# Squad 3: post-tasks anti-laziness and ownership (2026-11-20)

Lenses: claude::reviewer-renata (anti-laziness), claude::planner-priti (ownership and dependencies), claude::implementer-ivan (feasibility). Verdict from all three: ready after fixes. Fixes were applied by claude::planner-priti; the runner adjudicated each one.

| Finding | Disposition | Evidence |
|---|---|---|
| WP12 could close with the route xfailed (FR-008 / SC-001 not closed) | accepted | WP12 and WP14: a happy-path xfail or skip blocks approval. A route gap is reported to the runner, who reopens the owning WP. WP13 depends on WP12 and WP14 |
| WP12 too large for one session | changed | Split into WP12 and WP14 (T055-T058) |
| WP03 "next run not harmed" assertion always passes | accepted | WP03 test 2 runs on the clean shape and the fallback is dropped |
| WP03 fixture builder creates no lane worktrees, so no auto-rebase happens | accepted | The WP03 local builder uses `allocate_lane_worktree` |
| WP03 failed-after-merge test was optional | accepted | Now mandatory (test 4, one-shot failure injection) |
| "Zero branch moves" proven only by final SHAs | accepted | WP05, WP12 and WP14 also check reflog lengths and that no snapshot was written. Corrected squad claim: `full_snapshot` does not record reflogs, so `reflog_shas` is used |
| Claim/gate agreement test is circular | accepted | WP05 T023#7 takes the gate side from `claim.unreviewed_merges` |
| No claim-level FR-010 attack; the advisory field or memo could swallow refusals | accepted | WP05 T023#10 is a real-CLI `merge=union` attack. The verdict comes only from the raising probe |
| NFR-001 git-version cache unassigned | accepted | WP01 T004 step 5 plus a count test |
| Double probe between WP04 and WP05; memo had no owner | accepted | WP05 owns the memo, with a passing-claim count test. WP04 has no memo |
| WP09 bumps a version a test it does not own hard-codes | accepted | WP09 owns and re-pins `test_contract_version.py` |
| WP09 owns docs but its body said "do not edit" | accepted | T046 doc edits required, plus a doc-version test |
| WP04 stale "stop and ask" text | accepted | Deleted |
| WP01 leeway edit to WP07's file while running in parallel | accepted | WP07 depends on WP01 |
| WP07 sibling helper signature unspecified | accepted | Public `sibling_candidates_before(...)` and `render_stale_remediation(...)` |
| WP07 merge-in-progress probed after the attempt, which risks wiping operator bytes | accepted | Probe before the attempt; test 6b checks bytes survive; test 6c covers the guarded-abort cause |
| WP12 depends on too little for an integrated proof | accepted | WP12 also depends on WP06, WP09 and WP11, plus an integrated regression run |
| WP11 may need `wp_attribution.py`; `_lane_first_parent_spine` must stay stable | accepted | WP11 owns `wp_attribution.py` (leeway); change to the spine forbidden |
| Stale `is_legitimate_merge_resolution` docstring has no owner | accepted | WP06 T030 step 6; WP06 depends on WP01 |
| WP02 grep check conflicts with WP05's claim-time read | accepted | Narrowed to the gate modules |
| WP02 tests green at HEAD labelled red | accepted | Labelled as controls |
| WP02 undo must re-record the lane-tip ref | accepted | T008 uses `lane_tip.record_tip` |
| WP08 "unchanged" test too weak | accepted | Golden output recorded at the base |
| WP05 leeway unbounded; prompt contradicted tasks.md | accepted | Bounded to the validation list, each change with a rationale in history |
| WP04 goldens could be flaky | accepted | Build-twice determinism precondition |
| `check-attr --source` still reads info/attributes (corrected squad premise) | changed | WP01 adds an empty-tree `check-attr --source` read that must be `unspecified` |
| MVP serialization WP08 → WP07 (T036) | deferred_with_rationale | Kept: T036 is the executed-route check the anti-laziness lens asked for. Moving it would weaken WP07's DoD |
| Editor's extra choices: WP06 passes `attributes_source`; WP05 memo pass-through via WP04 files; WP03 injection mechanism; WP12 integrated regression run | accepted | Runner confirmed |
