# Code grounding: approved claim bound (#5668)

Pre-spec grounding for mission `approved-claim-bound-01M444QR`. Five read-only,
profile-loaded lenses ran on 2026-10-04 against `main` at `9adc68803f` (CLI
4.0.0rc6): reproducer and root-cause tracer (`debugger-debbie`), related-issue
researcher (`researcher-robbie`), architect (`architect-alphonso`) and
test-suite (`reviewer-renata`). Paths are relative to the repository root;
source paths without a prefix are under `src/specify_cli/`.

## 1. Reproduction

The reproducer script in the issue body was run unchanged through the checkout's
own CLI, each run in an empty directory with a throwaway `HOME`.

| Topology / strategy | `consolidate` exit | `src/alpha/late.py` on `main` | Verdict |
|---|---|---|---|
| lanes / squash | 0 | `UNREVIEWED = True` | reproduces |
| lanes / merge | 0 | `UNREVIEWED = True` | reproduces |
| coord / squash | 0 | `UNREVIEWED = True` | reproduces |
| coord / merge | 0 | `UNREVIEWED = True` | reproduces |

Banner printed in each run:

- squash: `✓ Reconciliation verified: approved-WP claim integrity and squash content attribution verified (no un-attributable content on the target); per-SHA approved-reachability deferred under squash strategy.`
- merge: `✓ Reconciliation verified: approved-WP commit reachability on the target (no excluded commit reachable).`

Event-log evidence (lanes / squash, WP01):

| Transition | `policy_metadata.lane_head` |
|---|---|
| `in_progress -> for_review` | `d0d8b2c6` (the reviewed commit) |
| `for_review -> in_review` | `d0d8b2c6` |
| `in_review -> approved` | `d0d8b2c6` |
| `approved -> done` (actor `merge`) | `8fc7fb8c` (the late, unreviewed commit) |

The lane tip before `consolidate` was `8fc7fb8c`, whose parent is `d0d8b2c6`.
The approval stamp exists and names the reviewed commit; the gate did not read it.

The only signal at commit time is a warn-only guard line
(`ACTIVE_WP_CONTEXT_AMBIGUOUS`), which does not stop the commit.

## 2. Root cause

The claim builder asks the status snapshot only "is this WP approved or done?"
and then reads the live lane branch.

| What | Where |
|---|---|
| Claim builder; docstring "lane-branch git tips ... never status rows" | `consolidation/reconciliation.py:1372`, `:1388-1389` |
| Approved SHAs = `commits_in_range(coord_base_ref, <lane branch>)` | `:2103-2121` (`_collect_approved_shas`), `:2083` (`_lane_tip_commits`) |
| Authored spine, blobs, deletions, patch ids, `approved_lane_content` from `base..branch` | `:2562-2641` (`_collect_authored`), `:2420` (`_lane_first_parent_spine`), `:2408` |
| Membership lanes `{approved, done}` | `:95` |
| Physical lane merge uses the branch name | `consolidation/phase_advance.py:190-241`, `lanes/consolidation.py:279-313` |

A post-approval commit is therefore approved authorship on every axis.

Why the closed world (FR-013 of the mixed-lane mission) does not catch it:
`_resolve_mixed_lane_canceled_content` returns early at
`reconciliation.py:1638-1640` when no lane mixes an approved and a canceled WP,
so no work window is ever built for a lane without a canceled WP.

### The stamp

- Written on every persisted transition of a lane-mapped WP:
  `status/transition_pipeline.py:178-216`, probe `status/lane_head.py:61-157`.
  The probe is best-effort and returns `None` for planning lanes (`:142`).
- Read only by `consolidation/wp_attribution.py::_stamp_of` (`:235`) and, inline,
  by `consolidation/canceled_attestation.py::attestation_stamps` (`:100-117`).
- The stamp shipped in commit `7976350705` (2026-09-29), first tagged
  `v4.0.0rc5`. Approvals recorded by earlier releases carry none.
- `approved -> done` is emitted before the gate
  (`consolidation/executor.py:363-371`, inferred from phase order) and is
  stamped with the live tip. The newest stamp of a WP is therefore not the
  approval stamp once consolidation has started, and on every `--resume`.

### Banner, refusal rendering, rollback

- Banner: `consolidation/phase_gate.py:155-176` (`_reconciliation_pass_message`),
  printed at `:126` and `:133`. It reflects `VerifyStatus.PASS` against the
  live-tip claim.
- Refusal rendering: `VerifyResult.recovery_guidance`
  (`reconciliation.py:425-442`), printed at `phase_gate.py:136`. The claim-time
  variant is at `consolidation/phase_claim.py:525-541`.
- Claim-time refusal exits before the first mutation:
  `claim_integrity_refusal` (`reconciliation.py:1975`), called at
  `phase_claim.py:494`, ahead of `_capture_snapshot_and_begin_attempt` (`:500`).
- Rollback: the single `try` at `executor.py:361-390` calls
  `rollback.rollback_to_snapshot`. `phase_gate.py:151` still also calls
  `_rollback_target_after_failed_reconciliation` (a known second restore path).

### Attestation model

- CLI flag `--attest-canceled-superseded <WP>` with `--attest-reason`:
  `cli/commands/consolidate.py:921-936`, validated at `:999` and `:1186`,
  recorded in `executor.py:142-188`.
- Record: a forced operator `canceled -> canceled` transition with
  `policy_metadata.attestation`; a later non-migration transition of the WP
  voids it (`canceled_attestation.py:100-117`).
- `validate_attestation_request` requires a canceled WP (`:139`), so the flag
  cannot be reused for an approved WP.
- Template for an unstamped WP: `_unstamped_carried_refusal`
  (`reconciliation.py:1821-1859`) with `lacks_lane_head_stamps`
  (`wp_attribution.py:748`); it refuses by name and is lifted per attested WP.

### Other entry points

- `orchestrator-api consolidate-mission`: the architect lens reads it as
  calling `_run_lane_based_consolidation` (`orchestrator_api/consolidation.py:185`),
  so it inherits a claim-time check; the root-cause lens reads `:447-460` as
  merging live lane branches with no claim. **The two lenses disagree; the plan
  phase must settle it from the source.**
- `--dry-run`: the forecast (`consolidation/forecast.py`) never builds the
  claim, so it will not report a new claim-time refusal (same gap as #5329).
- `--resume`: the claim is rebuilt (`phase_claim.py:479`); the resume lane-tip
  check (`consolidation/state.py:811-853`) accepts a descendant tip.

## 3. Design findings

**Authority.** Status owns the write and stays git-free. The readers already
live in `consolidation/wp_attribution.py` (`_stamp_of`, `_is_migration_event`,
`_windows`, `_lane_exempt_commits`). The reviewed-tip reader belongs next to
them, and the inline stamp read in `canceled_attestation.py:104` should fold
onto `_stamp_of` so there is one reader.

**Which stamp.** The last non-migration event with `to_lane == approved`, never
the newest event of the WP.

**Lane bound.** For a lane with several approved WPs, the bound is the
descendant-most approval stamp by ancestry. A stamp that is not an ancestor of
the lane tip (rewritten lane) refuses, as `STAMP_NOT_ANCESTOR_OF_LANE_TIP`
already does for canceled windows (`wp_attribution.py:346-349`).

**Predicate.** A lane moved after approval when the range `bound..lane_tip`
(full range, not first-parent only) holds a commit that is not a merge, is not
reachable from an anchor (dependency-lane tips, mission and coordination base,
target tip) and touches a non-bookkeeping path.

**Where it refuses.** At claim time, before the snapshot and before any branch
moves. Nothing is rolled back and the rollback caller set is unchanged. A
commit that lands between the claim and the lane merge is not seen by a
claim-time check alone.

### Hazards: lane movement after approval that must not refuse

| Movement | Treatment |
|---|---|
| `approved -> done` restamp carries the landed tip | read the stamp only from the `to_lane == approved` event |
| Coordination-to-lane sync merge (claim, liveness refresh, review claim; not at approve) | merge commit skipped; its content is bookkeeping |
| Consolidation-time auto-rebase merge (`lanes/consolidation.py:209-227`, `lanes/auto_rebase.py:905`, `:973`) | after the claim on a fresh run; on `--resume` a merge with an anchor-reachable parent, so skipped |
| Dependency lane fast-forwarded into a dependent lane | dependency-tip anchor; the dependency lane's own check catches its stragglers |
| Second WP on the same lane approved later | lane bound is the latest approval by ancestry |
| Bookkeeping-only side branch (#5333) | non-bookkeeping path filter passes it |
| Unreviewed side-branch merge | the full-range walk refuses its non-anchored non-merge commits |
| Content inside a merge commit itself ("evil merge") | residual; pin as strict `xfail` |
| Force-push or rewrite after approval | refuses as stamp-not-ancestor |

Rejected definitions of "landed equals approved":

- SHA equality of lane tip and stamp: refuses every multi-WP lane and every resume.
- Tree or blob equality: refuses any overlapped auto-merge (the #5013 "blob equal to neither parent" class).

### Limits found

- Planning lanes and `single_branch` missions are never stamped
  (`status/lane_head.py:143`). A fail-closed rule must exempt lanes with no lane
  branch, or every such mission refuses.
- A lane-level bound still admits a commit made between WP01's approval and
  WP02's claim on the same lane. Closing that needs the per-WP closed world on
  every lane, with all its anchor hazards (`reconciliation.py:1698-1720`).
- The stamp is the branch head when the `approved` event persists, not the tip
  the reviewer read. A commit made during review is inside the bound.
- Wall-clock ordering in the second reducer (#4941) could misorder `approved`
  events; the claim reads the Lamport-ordered log, so it is unaffected.

### Decision record needed

The change reverses two recorded decisions: "approved commit SHAs come from
lane-branch git tips (never status rows)" (`reconciliation.py:1389-1390`) and
ADR `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md` Decision 1
("applies only to mixed lanes"). A new ADR in `docs/adr/4.x/` with a forward
pointer from the 3.x ADR records it.

### Complexity and byte-identity

- No function to be touched is near the ceiling of 15. Highest:
  `_run_lane_based_consolidation` 12 (`executor.py:430`), `resolve_canceled_wp`
  11 (`wp_attribution.py:650`), `_window_commits` 11 (`:324`).
- `_DETAIL_TEMPLATES` (`wp_attribution.py:180-207`) is total over the reason
  enum and worded for canceled WPs. New reasons are added; existing texts are
  not reworded.

## 4. Test-suite findings

### Why the suite misses the bug

| Cause | Where |
|---|---|
| Fixtures write the approval log before any lane commit exists, with no `policy_metadata`; "after approval" cannot be expressed | `tests/terminus/conftest.py:341-342`, `:527-533`, `:548`; `tests/consolidation/test_reconciliation.py:696-718`, `:772-795` |
| The e2e oracle `approved_shas_from_lane_tips` reads the same live tip as the product ("Never consults status.events.jsonl"); used in 8 files | `tests/terminus/conftest.py:249-260` |
| A test asserts the claim equals `commits_in_range(coord_base, branch)` | `tests/consolidation/test_reconciliation.py:799-812` |
| A test compares the claim to the collectors it is built from | `:2675-2704` |
| A test pins "a non-mixed lane never reads events" | `:2510-2521` |
| The only post-approval straggler test passes because its lane is mixed | `tests/terminus/test_mixed_lane_closed_world.py:55` |

### Blast radius of failing closed on unstamped approvals

Static estimate, nothing was run: 150 to 200 test cases in about 45 files.

- `tests/terminus/`: about 89 test functions in 35 files, through four builders
  that share one helper: `build_coord_mission` (`conftest.py:491`),
  `build_coord_mission_mixed_lane` (`:592`), `build_coord_mission_shared_file`
  (`:680`), `lanes_fixture.build_lanes_mission` (`lanes_fixture.py:123`).
- `tests/consolidation/test_reconciliation.py`: 27 call sites of three builders
  over the unstamped `_event` (`:696`).
- Others: `_divergent_shapes.py`, `test_approved_content_presence.py`,
  `test_executor_phase_boundary.py`, `test_canceled_content_benchmark.py`.
- Not verified whether `test_executor_terminus_integrity.py`,
  `test_refuse_restores_target.py`, `test_claim_integrity_refusal.py`,
  `tests/integration/test_merge_cluster_coord_read.py` and
  `tests/cli/commands/test_merge_strategy.py` use a real or a stubbed claim.

Remediation: two central edits. Write the approval log after the lanes are cut
and stamp `lane_head` with the real tip in `tests/terminus/conftest.py` (the
already-stamped builders show the shape) and in
`test_reconciliation.py::_build_mission`. Keep
`canceled_dependency_support.strip_lane_head_stamps` as the one explicit way to
build a legacy mission. No product "test mode" and no default of the stamp to
the tip.

### Red-first e2e home

- Extend `tests/terminus/canceled_dependency_support.py` (`_commit_in`,
  `_approve`, builder). It uses the real lane allocator and the production
  transactional transition shell, so stamps come from the real probe, and
  `run_terminus` (`tests/terminus/conftest.py:1314`) drives
  `python -m specify_cli consolidate` as a subprocess.
- Model: `tests/terminus/test_canceled_dependency_fast_forward_verdicts.py:40,59-66`.
- LANES topology: `lanes_fixture.build_lanes_mission_canceled_dependency` (`:232`).
- Gap: no harness drives `implement` and the review transitions through the CLI
  end to end; stamps come from the in-process production shell.
- Markers: `integration`, `git_repo`, `regression`. The per-PR shards select
  `-m "not performance and not stress"`, so the test runs per PR; `make
  test-fast` deselects it, so it is named in the mission's targeted set. No
  `p0_repro` marker in the fix PR.

### Pins and gate files to run

- `tests/consolidation/test_single_rollback_authority.py` (allowed-caller pin)
- `tests/consolidation/test_refuse_restores_target.py`, `test_claim_integrity_refusal.py`
- `tests/consolidation/test_canceled_attestation.py`, `test_wp_attribution.py`,
  `test_canceled_dependency_lane.py`, `test_canceled_dependency_attribution.py`,
  `test_executor_phase_boundary.py`, `test_canceled_content_benchmark.py`
- `tests/specify_cli/cli/commands/test_merge_cli_golden.py` and
  `tests/architectural/test_docs_cli_reference_parity.py` (new flag)
- `tests/status/test_lane_head.py` (probe AST pin)
- `tests/architectural/test_status_module_boundary.py`,
  `test_cold_import_status_boundary.py`, `test_no_write_side_rederivation.py`,
  `test_layer_rules.py`, `test_exemption_registry_ratchet.py`,
  `test_coord_read_residuals_closeout.py`
- `tests/architectural/test_destructive_op_routing.py` only if `git_probes.py`,
  `resume_recovery.py` or the executor's reset sites shift
- `tests/architectural/test_ruff_format_enforcement.py`,
  `test_ruff_format_exclude_ratchet.py`, `test_no_legacy_terminology.py`

### The #5330 strict xfails (`tests/consolidation/test_canceled_content_residuals.py`)

| Test | Effect of the bound |
|---|---|
| `:209` hunk-level | stays xfail |
| `:279` other-lane-identical | stays xfail |
| `:513` sibling-never-entered | plausible XPASS if the new refusal fires first at claim time; depends on precedence |
| `:637` pre-claim commit | stays xfail under an upper-bound-only rule |

Collateral: `:378` and `:450` assert the "outside windows" wording; their stray
commits are also after approval, so a new refusal that takes precedence would
break the wording assertion. Precedence must be decided in the spec.

### Boy-scout candidates inside the touched files

- Retire or rewrite `test_reconciliation.py:799`, `:2510`, `:2675`.
- Replace `approved_shas_from_lane_tips` with a stamp-bounded oracle.
- Deduplicate the event builders only where the fix touches them.

## 5. Related issues

| Issue | State | Classification | Reason |
|---|---|---|---|
| #5668 | open, P1 | target | native sub-issue of #5001 |
| #5001 | open epic | parent | "every approved WP's approved commits are reachable and nothing else is" |
| #4977, #5569, #5613 | closed | cross-ref | canceled content shipping; source of the named-refusal pattern |
| #5046, #5013 | closed | cross-ref | introduced the stamp and windows, and the squash content axis |
| #5330 | open, P1 | cross-ref | canceled-content residual xfails; canceled axis |
| #5331 | open, P2 | cross-ref | for_review gate counts the shared lane's range; same stamp substrate, different gate |
| #5675 | open, P2 | out of scope | for_review gate on `single_branch`; path deny-list, no stamps |
| #3044 | open epic | cross-ref | verdict-loss invariant; not this defect |
| #4941 | open, P1 | cross-ref | wall-clock reducer ordering |
| #5333 | open, P3 | cross-ref | post-approval bookkeeping side branch; must not get worse |
| #5337 | open, P2 | cross-ref | two lane-spine walkers; do not add a third |
| #5329 | open, P2 | cross-ref | `--dry-run` forecast misses gate refusals |
| #5446 | open, P1 | cross-ref | `agent action implement` pulls a WP out of review; the remedy path depends on a legitimate move back |
| #5282, #5053, #5185 | open | cross-ref | same gate module, different defects |
| #5372, #5686, #5687, #5666, #5048 | open | out of scope | rollback and resume cluster; different mechanism |
| #5552 | closed | out of scope | squash false-refuse; branch `issue-5552-friction-remediation` touches the same module |
| #4996, #4990 | closed | out of scope | fixed |

No duplicate of #5668 and no open pull request touching this area were found.
Nothing else folds in; only #5668 is closed by this mission.

The for_review gate (`lanes/for_review_gate.py:243-247`, `lanes/_git.py:68-96`)
counts `rev-list --count <base>..HEAD` in the worktree. It shares the flaw class
(lane-level, not WP-level) but not the mechanism: different function, different
base, no events. It is cross-referenced, not folded in.

## 6. Decisions taken into the spec

| Question | Decision | Basis |
|---|---|---|
| Does an attestation lift a post-approval commit refusal? | No. Attestation lifts only the missing-stamp refusal; a later commit goes back for review | operator brief |
| Lane-level bound or per-WP closed world on every lane? | Lane-level bound; the between-approvals gap is a named residual | architect recommendation; smallest sound change |
| Claim time only, or also at the gate? | Both: refuse before mutation, and re-check at the gate so "verified" cannot print over a lane that moved during the run | operator brief ("verified is honest") |
| `single_branch` and planning lanes | Out of scope: no lane branch, no stamp; named residual with a follow-up issue | never stamped by design |
| Evil merge | Named residual pinned as strict `xfail` | architect recommendation |
| `--dry-run` reporting | Out of scope; tracked by #5329 | forecast never builds the claim |
| Precedence against "outside windows" | Existing mixed-lane refusals keep precedence on a mixed lane, so existing texts and the #5330 xfails keep their state | byte-identity constraint |

## 7. Post-spec adversarial review (2026-10-04)

One lens (`reviewer-renata`) asked whether the spec could be met while unreviewed
content still lands, or while refusing legitimate missions. Dispositions:

| Finding | Disposition | Where |
|---|---|---|
| F1 "bookkeeping files" undefined; the gate's predicate (`reconciliation.py:1166`, `:1237`, `:1241`) covers all of `.kittify/` and any `kitty-specs/<slug>/` segment | changed: the bound reuses the one existing predicate; its width is a named residual | spec FR-009, Known residuals |
| F2 `orchestrator-api consolidate-mission` has two paths: planning-only calls `_run_lane_based_consolidation` (`orchestrator_api/consolidation.py:413-423`, `:185`); code lanes are merged directly with no claim (`:447-460`). Both earlier lenses were right | accepted | spec FR-011, US1 scenario 6, SC-006 |
| F3 a WP can reach `done` with no `approved` event (`spec_kitty_events/status.py:551,553`, force at `:633`) | accepted | spec FR-005, US2 scenario 5 |
| F4 the run's own `approved -> done` would void an attestation; `to_lane` in `{approved, done}` requires evidence (`status.py:521`) | accepted; the transition shape is a plan decision | spec FR-006, Key Entities, US2 scenario 6 |
| F5 "lanes that have a lane branch" fails open for a deleted code-lane branch | accepted | spec C-005 |
| F6 the gate re-check had no acceptance scenario | accepted | spec US1 scenario 5 |
| F7 precedence on a mixed lane was ambiguous | accepted | spec FR-012, US1 scenario 7 |
| F8 dependency-lane anchors trust an unchecked lane | accepted | spec FR-009, Edge Cases |
| F9 FR-004 had no check of its own; NFR-001 not measurable | accepted | spec FR-004 (folded), NFR-001 |

Not verified by the lens, carried to the plan: whether any tool step after
approval adds a non-merge content commit to a lane branch, and where
`lanes`-topology status commits land.

## 8. Post-tasks adversarial review (2026-10-04)

One lens (`reviewer-renata`) asked whether seven implementers doing exactly what
their prompts say would meet the spec, and whether a work package could be
completed with a fake. Dispositions:

| Finding | Disposition | Where |
|---|---|---|
| Gate re-check vacuous: the live mission branch (an anchor) and, on LANES, the claim base reach every merged lane commit (`lanes/consolidation.py:1275`, `phase_claim.py:474`) | accepted: the gate compares live tips with claim-time validated tips, anchored on pre-mutation SHAs | plan D-3, research R-5, WP02 T009, WP03 T013 |
| Gate test fakeable by injecting after the lane merge; one topology hides the LANES hole | accepted | WP03 T012 |
| No integration check after the parallel lanes merge | accepted: new WP07 | tasks.md, WP07 |
| `approved_bound_refusal` added by two parallel work packages | accepted: defined once in WP02 with a pinned signature | WP02 T009, WP03, WP05 |
| Claim base and anchors not on run state; `run_state.py` unowned | accepted: WP02 owns `phase_claim.py` and `run_state.py` | WP02 frontmatter, T009 |
| `post_approval_support.py` extended by four packages | accepted: WP02 ships it complete, then frozen | WP02 T006 |
| Tracer files edited in parallel lanes | changed: lanes do not edit tracers; the orchestrator records them | every WP prompt |
| `ATTESTATION_KEY` not exported (`canceled_attestation.py:49`) | accepted | WP01 T002 |
| `_lane_exempt_commits` rename breaks `test_canceled_dependency_lane.py:33` | accepted: moved to WP01 | WP01 T001 |
| `events_unreadable` wording unusable for an approved lane; no test | accepted: new text, one test | WP02 T009, T010 |
| First-parent-only walk passes the tests | accepted: refusing case added | WP02 T008, T010 |
| Re-running an attestation is refused | accepted: an earlier attestation is re-recorded | WP04 T016, T018 |
| Shared `--attest-reason` messages name only the canceled flag | accepted | WP04 T017 |
| Orchestrator envelope key unspecified | accepted: `data["preflight_error_code"]` | WP05 T021, T022 |
| Resume refusing direction had an escape hatch | accepted: mandatory; passing direction dropped as duplicate | WP05 T023 |
| Coverage: US1.7, US3.4, FR-008 through the builder, NFR-004 tips, SC-005 | accepted (US1.7 reworded as subsumed by the existing refusal when it fires) | spec US1.7, WP02 T006, T010, WP07 T027 |
| WP02 T011.4 unbounded | accepted: capped at ten, remainder handed back | WP02 T011 |
| WP04 had no red-first ordering | accepted | WP04 |
| Duplicate tests (T019, T011.2) | accepted: removed | WP04 T019, WP02 T011 |

Carried into implementation as open checks: whether the in-process transition
shell works for a LANES mission with no coordination branch; whether the
attestation's evidence overwrites the review evidence the `done` record uses.
