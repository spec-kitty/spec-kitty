---
work_package_id: WP12
title: 'End-to-end route: support module, two-lane route and controls'
dependencies:
- WP03
- WP05
- WP06
- WP07
- WP08
- WP09
- WP10
- WP11
requirement_refs:
- FR-008
- SC-001
- SC-002
- SC-003
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
subtasks:
- T047
- T048
- T049
- T050
phase: Phase 3 - Surfaces and proof
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/approved_lane_route_support.py
- tests/terminus/test_approved_lane_resolution_route.py
execution_mode: code_change
model: ''
owned_files:
- tests/terminus/approved_lane_route_support.py
- tests/terminus/test_approved_lane_resolution_route.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 – End-to-end route: support module, two-lane route and controls

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Prove the re-review route end to end through the **real CLI** (FR-008, US2), with real lifecycle transitions by **distinct** implementer and reviewer identities, under both the default squash strategy and `--strategy merge`:

1. consolidate refuses lane-b as stale and prints the route (WP07);
2. the operator runs the printed commands: send WP02 back, `implement --incorporate lane-a` (WP08) stops on the conflict, the operator resolves and commits, `move-task --to for_review`;
3. an independent reviewer claims the review (the review context lists the resolution merge, WP10) and approves, unforced;
4. consolidate exits 0 and the target holds the resolved content.

Negative controls on the same fixture (SC-002, C-004):

- **N1**: an unreviewed hand resolution on an approved lane is refused, whatever the resolution contains (a hand conflict resolution is always own content, so the novel line is not what N1 proves) → `RESOLUTION_MERGE_UNREVIEWED`, before any branch moves.
- **N2**: a second merge made **after** the re-approval → refused (`RESOLUTION_MERGE_UNREVIEWED`).
- **N3**: the re-approval is forced, or is made by the implementer's own identity → it does not restamp (or is refused at the move), and consolidate refuses.

Plus SC-003 (zero branch moves on the unreviewed refusal, proven by reflog lengths and "no snapshot written", not by final SHAs) and the **residual control** of spec.md Edge Cases ("Residual by design"): the route is followed, the resolution adds a novel line from neither side, an independent reviewer approves → exit 0 and the novel line lands. This pins that the review is the only guard (no silent mechanical filter).

Out of scope here, in **WP14** (which depends on this WP): SC-004 (the next run after a rolled-back run), the three-lane variants, and the remaining topology/strategy cells. This WP's support module provides what WP14 needs (T047).

This WP adds **tests only**.

**No xfail exit.** A strict `xfail` or a `skip` on any happy-path step (T048) or on the residual control (T050) BLOCKS approval of this WP; it is never an approved end state. If a step of the route fails because of a gap in the CLI or the lifecycle: do not patch `src/` here, and do not mark the step xfail. Stop, record the failing step with `spec-kitty agent tasks add-history WP12 --note "route gap: <step>, <exact command>, <exit code>, <output excerpt>"`, and report to the runner, who reopens the WP owning the failing surface (for example WP07 for the remedy text, WP08 for `--incorporate`, WP05 for the claim refusal, WP10 for the review context). Spec assumption: "if it fails, the gap is fixed in this Mission".

## Context & Constraints

- Read: `.kittify/charter/charter.md`; mission `spec.md` (US2, US3, US6, FR-008, SC-001..SC-004, Edge Cases), `plan.md` IC-08, `research.md` R-01..R-05, `contracts/stale-remedy.md`, `contracts/refusal-codes.md`, `contracts/review-context-merges.md`, `data-model.md` (state transitions), `quickstart.md` (the operator walkthrough this test mirrors), `tasks.md`.
- Squad evidence: reviewer-renata FR-008 finding (`squad2/reviewer-renata.md`): positive path must not reuse `_restamp_approvals`, `--force` or the same actor; assert the approval's `lane_head` descends from the resolution merge; fix the re-entry mode (a fresh run after the full-restore re-baseline).
- **Integrity invariants** the test pins: C-001 (no unreviewed resolution lands), C-002 (no attestation flag appears anywhere in the route), C-003 (the gate's unreviewed-merge rule stays), C-004 (only an unforced independent approval restamps), fail closed (any refusal must name a code; an exit 0 without the "Reconciliation verified" banner is a failure of the test, not a pass).
- Upstream WPs you depend on, and what you rely on:
  - WP07: the stale refusal text and the printed commands (`contracts/stale-remedy.md`).
  - WP08: `agent action implement <WP> --mission <m> --incorporate <lane>`, its conflict behaviour (WP08 chose exit 0 on a conflict with the merge left in progress; read WP08's history note and its module constant before asserting the exit code).
  - WP05: `RESOLUTION_MERGE_UNREVIEWED` at claim time, before mutation.
  - WP03: rollback restores the run's own auto-rebase lane moves.
  - WP10: the review context lists `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <sha>`.
- `tests/terminus/post_approval_support.py` is FROZEN (its docstring, `:34-35`): import from it, never edit it. Same for `canceled_dependency_support.py`, `mixed_lane_support.py`, `rollback_harness.py`, `conftest.py` (not owned).
- Terminology in test names and messages: Mission, consolidate, incorporate, re-review. Never "feature", never "sync".

## Branch Strategy

- **Strategy**: set by finalize-tasks
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP12 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Harness at HEAD (read before writing)

- `tests/terminus/conftest.py`: `run_terminus` (`:1514-1542`, real `python -m specify_cli` subprocess with isolated `HOME`, `timeout=180`), `CoordMission` (`:334`), `git_rev` (`:93`), `sha_reachable` (`:305`), `blob_present_at` (`:249`), `_git` (`:85`).
- `tests/terminus/post_approval_support.py`: `build_post_approval_coord_mission` (`:103-106`) and `build_post_approval_lanes_mission` (`:109-151`) build two independent approved lanes (WP01 on lane-a, WP02 on lane-b) through the production status shell; `lane_worktree` (`:161-165`); `_lane_manifest` (`:76-96`, `write_scope=("src/pkg",)`). Its docstring (`:29-31`) states the known gap you close: "no harness drives `implement` and the review transitions through the CLI end to end".
- `tests/terminus/canceled_dependency_support.py`: `ACTOR`/`REVIEWER` (`:42-45`), `_bootstrap_coord_mission` (`:104`), `_commit_in` (`:123`), `_approve` (`:132`), `merge_commits` (`:242`).
- `tests/terminus/mixed_lane_support.py`: `transition`, `collapse` (output flattening used by every terminus assertion).
- `tests/terminus/rollback_harness.py`: `ref_shas` (`:43`), `reflog_shas` (`:51`), `full_snapshot` (`:74`; SHAs, bookkeeping and event-log bytes, NOT reflog lengths), `state_path` (`:24`), `flat` (`:91`).
- **How "no branch moves" is proven (SC-003), everywhere in this WP**: end-state SHAs are not enough, because a land-then-rollback also ends with identical `ref_shas`. Assert that `len(reflog_shas(mission, b))` is unchanged for the target, the Mission/coordination branch and every lane branch, and that no pre-mutation snapshot was written (`state_path(mission)` is `None`, or its record has no `pre_mutation_refs`; WP05 pinned which one a claim-time refusal leaves: use the same). Put this in one support helper, `assert_no_branch_moved(mission, before)` with `before = branch_reflog_lengths(mission)`.
- `tests/terminus/test_rollback_record_rebaseline.py`: `_consolidate` in-process (`:69-80`) and `_one_shot_gate_fail` (`:83-101`), the pattern for a gate FAIL that happens after lanes landed.
- `tests/consolidation/test_approved_bound_residuals.py:59-73`: the strict xfail WP05 converts; do not duplicate it.
- CLI verbs used by the route: `agent tasks move-task <WP> --to <lane> --mission <m> [--agent ...] [--reviewer ...] [--approval-ref ...]` (`src/specify_cli/cli/commands/agent/tasks.py:738-814`), `agent action implement`, `agent action review` (`workflow.py:2616`), `consolidate --mission <m> --yes [--strategy merge]`. How an independent approval is recorded through the CLI today: read `tests/integration/review/test_approve_without_force.py` and `tests/integration/test_6715_squad_identity_and_evidence.py` for working argument sets and identity formats before writing the steps.

## Subtasks & Detailed Guidance

### Subtask T047 – Support module: adjacent-hunk lanes, three-lane builder, route driver

- **Purpose**: one fixture builder for every scenario, with its preconditions asserted inside the builder so no test can pass on a mis-built fixture.
- **File**: `tests/terminus/approved_lane_route_support.py` (new).
- **Steps**:
  1. `build_conflicting_lanes_mission(tmp_path, topology: Topology, *, mid8: str) -> RouteMission`: the shape of `post_approval_support` (both topologies), but both WPs edit **adjacent lines** of one shared file `src/pkg/shared.py` seeded on the target before the lanes are cut (lane-a changes line 3, lane-b changes line 4). Approve both through the production shell with distinct actors (`ACTOR` implements, `REVIEWER` approves).
  2. Preconditions asserted in the builder:
     - `kernel.git.listing.merge_tree(repo, lane_b_branch, lane_a_branch).conflicted == ("src/pkg/shared.py",)` (git merge-tree exits 1);
     - each WP's newest approval stamp (`specify_cli.consolidation.approved_bound.approval_stamp` over the status events) equals its lane tip;
     - both WPs are `approved`.
  3. `RouteMission` dataclass: the `CoordMission`, `implementer` and `reviewer` identity strings (distinct, full segments, in the format the #6715 tests use), the lane checkouts, the shared path, and the two side texts.
  4. `add_dependent_and_control_lanes(mission) -> RouteMission` for WP14's three-lane variants (the workable shape, fixed here): lane-c (WP03) declared to depend on lane-b and editing a line of `src/pkg/shared.py` adjacent to lane-b's change, so lane-c conflicts once lane-b's resolution lands; plus an independent lane-d (WP04) that edits an unrelated file `src/pkg/other.py` (the exact-set control: it overlaps nothing, so it is never named as a sibling). The exact lines lane-c edits are the builder author's choice (record it in the module docstring and in history), as long as lane-c's approved content overlaps lane-b's on `src/pkg/shared.py`. Both approved through the production shell by distinct identities; it rebuilds `lanes.json`, the WP files and the lane worktrees (with `allocate_lane_worktree`). Preconditions asserted inside the builder: lane-c's dependency on lane-b is recorded in the manifest; lane-d shares no path with any other lane; every WP's newest approval stamp equals its lane tip. One smoke test in this WP's test module builds it and checks those preconditions (WP14 writes the scenarios).
  5. `run_route(mission, *, lane: str, wp_id: str, sibling: str, strategy: str, novel_line: bool = False) -> RouteOutcome`: drives T048 steps 1-5 for one conflicting lane (consolidate refusal, the printed commands, the hand resolution, the independent review and approval) and returns the refusal output, the resolution merge SHA and the approval event, so WP14 reuses the exact same route for the lanes topology and lane-c without copying steps.
  6. `branch_reflog_lengths(mission) -> dict[str, int]` and `assert_no_branch_moved(mission, before)` (Harness, SC-003); `consolidate_in_process(mission, strategy)` and `one_shot_gate_fail(monkeypatch)`, copied from the pattern of `tests/terminus/test_rollback_record_rebaseline.py:69-101` (never import a test module's private helper), used by T050's control and by WP14's SC-004 test.
  7. Small CLI helpers: `cli(mission, *args) -> CompletedProcess` (wraps `run_terminus`), `consolidate(mission, strategy) -> tuple[int, str]` (collapsed output), `printed_commands(output) -> list[list[str]]` (lines starting with `spec-kitty `, shlex-split, leading `spec-kitty` dropped), `resolve_conflict(checkout, text, *, novel_line=False)` (writes the resolved file, `git add`, `git commit --no-edit`), `approval_event(mission, wp_id)` (newest approval from the status events).
- **Notes**: the module docstring states it is FROZEN once this WP is approved (house rule of the other terminus support modules). WP14 imports it and must not edit it; anything WP14 needs beyond it lives in WP14's own test module.

### Subtask T048 – Happy path under squash and under `--strategy merge`

- **Purpose**: FR-008 / SC-001: the printed route, plus the two human acts, lands the Mission with exit 0.
- **Test**: `test_route_lands_after_independent_re_review[squash|merge]` on the coordination topology in `tests/terminus/test_approved_lane_resolution_route.py` (both strategies are REQUIRED here: FR-008 says "under both squash and merge strategies"). The lanes-topology cells are WP14's (T058).
- **Steps**:
  1. `consolidate(mission, strategy)` → exit 1; the output names `lane-a` as the sibling, the halt reason `conflict` and `src/pkg/shared.py`, and contains every line of `contracts/stale-remedy.md` in order. Record `ref_shas(mission)` before and after: the refusal comes from the stale check during lane consolidation, so the rollback must leave every branch as before (and, after WP03, lane-b too).
  2. Run the printed commands in order with `cli(...)`, passing `--agent <implementer>` where the command takes an agent. Assert none exits with an approved-WP refusal (SC-001: "zero printed commands refused for an approved work package").
  3. After `--incorporate`: `MERGE_HEAD` in lane-b's checkout equals lane-a's approval stamp. Resolve by keeping both changes (`resolve_conflict(...)`), commit.
  4. `move-task WP02 --to for_review` (implementer). Then the reviewer, a different identity: `agent action review WP02 --agent <reviewer> --mission <m>`; assert its output contains `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <merge sha>` (WP10). Then the reviewer approves WP02, unforced, through the CLI.
  5. Assert the approval event: `force is False`; actor (and reviewer) differ from the implementer; `policy_metadata["lane_head"]` is a descendant of (or equal to) the resolution merge SHA (`sha_reachable`).
  6. `consolidate(mission, strategy)` → exit 0, "Reconciliation verified" in the output, and `blob_present_at(target, "src/pkg/shared.py")` holds the resolved text (both sides' lines).
  7. Fresh run, not `--resume` (the full-restore re-baseline leaves no record; reviewer-renata: fix the re-entry mode). Assert `state_path(mission)` is `None` or carries no snapshot before the final run.
- **Edge**: the steps live in `run_route` (T047 step 5); the test is a thin wrapper per strategy. Record the runtime of each cell in history.

### Subtask T049 – Negative controls N1, N2, N3

- **Purpose**: SC-002 and C-004; prove the gate and claim stay closed on the same fixture.
- **Tests**:
  1. `test_n1_unreviewed_hand_resolution_is_refused_whatever_it_contains`: the shape the old remedy produced. WP02 stays `approved` (no send-back, so no re-approval can follow); the operator makes the hand merge directly in lane-b's checkout, with lane-a's stamp as second parent. Parametrise the resolution: `keep_both` (only the two sides' lines) and `novel_line` (an extra line from neither side). Any hand conflict resolution is own content, so BOTH refuse; the test proves the refusal does not depend on a novel line. The merge is on an approved lane and none of lane-b's own stamps reach it. Consolidate → exit 1, `RESOLUTION_MERGE_UNREVIEWED` naming the merge SHA, lane-b and WP02, and printing the re-review route; no branch moved (`assert_no_branch_moved`, reflog lengths and no snapshot). Under both strategies.
  2. `test_n2_merge_after_re_approval_is_refused`: complete the happy path up to the independent approval, then make a second hand merge on lane-b (for example merge lane-a's stamp again after an extra harmless lane-a re-approval, or merge the target's tip with a hand-edited resolution). Consolidate → exit 1, `RESOLUTION_MERGE_UNREVIEWED` naming the **second** merge; `assert_no_branch_moved`.
  3. `test_n3_forced_re_approval_does_not_restamp`: route up to `for_review`, then `move-task WP02 --to approved --force --note ...`. Assert the forced event carries no review result and that `approval_stamp(events, "WP02")` is still the old stamp; consolidate → exit 1 with `RESOLUTION_MERGE_UNREVIEWED`; `assert_no_branch_moved`.
  4. `test_n3_self_re_approval_is_refused`: route up to `for_review`, then the implementer's own identity claims and approves. Either the move is refused (`REVIEW_NOT_INDEPENDENT`, #6955) and WP02 is not approved, or it is recorded and consolidate refuses. Assert whichever the CLI does today, and in both cases assert consolidate does not exit 0 and does not land `src/pkg/shared.py`'s resolution.
- **Anti-vacuity**: every negative test also asserts the positive precondition of its fixture (the merge exists on lane-b, its own content is non-empty: `git show --remerge-diff --name-only <sha>` lists `src/pkg/shared.py`), and asserts the specific code, never just "exit != 0".

### Subtask T050 – SC-003 no-mutation proof and the residual control

- **Purpose**: pin "refused with zero branch moves, before any lane is consolidated" with an assertion that tells claim time from gate time, and pin the documented residual so nobody adds a silent mechanical filter.
- **Tests**:
  1. `test_unreviewed_merge_refuses_before_any_branch_moves` (SC-003): N1's fixture (`keep_both`), under squash and merge. Record `branch_reflog_lengths(mission)` before the run; after the refusal assert `assert_no_branch_moved` (reflog length of every branch unchanged, no pre-mutation snapshot written). Control in the same test, proving the assertion discriminates: on a shape that legitimately lands lanes and then fails at the gate (reuse `_one_shot_gate_fail`'s pattern, copied into the support module, not imported from a test module), the reflog lengths DO change although the final SHAs come back. Without this control the SC-003 assertion could be vacuous.
  2. `test_reviewed_resolution_with_a_novel_line_lands` (the residual control, spec Edge Cases "Residual by design"): follow the route with `run_route(..., novel_line=True)`: the resolution adds a line from neither side, the independent reviewer approves unforced. Consolidate → exit 0, "Reconciliation verified" in the output, and the target's `src/pkg/shared.py` contains the novel line. This is the documented residual: the review is the guard (FR-007 shows the resolution to the reviewer). If this test fails because something refuses the novel line, that is a silent mechanical filter beyond the spec: stop and report (no xfail).
- **No xfail exit**: test 2 is part of the proof; a strict xfail or skip on it blocks approval (Objectives).

## Binding DoD items: review-context command wiring (WP10 review, reviewer-accepted recorded leeway)

Accepted by the reviewer on 2026-11-20. These are blocking checks in WP12's review and in the final aggregate review. WP12's lane holds both WP01 and WP10, so edit `src/specify_cli/review/context_block.py` (and `review/wp_range.py` if needed) as recorded leeway, with a one-line rationale in history:
- (a) Print a version-gated "cannot neutralise attributes" line on git < 2.40, using WP01's `check_attr_source_available()` probe. The existing note stays only as the explanation.
- (b) Shape the printed resolution command with WP01's shared pinned-config helper (`merge_probe_env` / `MERGE_PROBE_CONFIG_PINS`: renormalize, directoryRenames, renames, diff.algorithm, conflictStyle), rendered as `-c` flags, so it cannot drift from the guard. The printed command also carries `--no-ext-diff --no-textconv`, because a `diff=<driver>` textconv or a `-diff` attribute can change or hide the bytes the reviewer sees (reviewer, WP01 cycle 2). The pins include `merge.renormalize=false`.
- (c) The attribute source is the one WP01's guard uses: the PRE-RUN TARGET TIP, not the range base. Red test: a real-git fixture where `merge=union` is committed on the lane before the window base; the printed command must list the path.
- (d) When `merges_unlisted` is true and remerge-diff is unavailable (git < 2.36), print the cannot-show form, not a `show --remerge-diff` instruction. Add a test.

## Binding addition (WP06 review 1, 2026-11-25)

- The real-git end-to-end test also covers the partial shape: a dropped hand merge explains part of a gate FAIL, and foreign content explains the rest. Assert that the gate hint gives the re-review route for the covering merge first, followed by `For the remaining content (<n> item(s) no dropped merge explains): ...` with the `--dependency-ref` hint appearing exactly once.

## Test Strategy

This WP is the test. Keep the module's wall time reasonable: build each fixture once per test (no module-scoped mutation sharing), parametrize narrowly. Marks: `pytest.mark.integration`, `pytest.mark.git_repo`, `pytest.mark.regression`. Unset harness variables per test where behaviour depends on them (`monkeypatch.delenv("SPEC_KITTY_NO_NAG", raising=False)`, `SPEC_KITTY_NON_INTERACTIVE`).

```bash
uv run --frozen pytest -q tests/terminus/test_approved_lane_resolution_route.py
# integrated regression run: this lane is the first that holds WP05, WP06, WP09 and WP11 together
uv run --frozen pytest -q tests/consolidation/test_resolution_merge_unreviewed.py tests/consolidation/test_unreviewed_merge_hint.py tests/consolidation/test_canceled_via_reapproved_dependency_7497.py tests/orchestrator_api/test_consolidate_mission_resolution_merge.py tests/lanes/test_approved_lane_stale_remedy.py tests/consolidation/test_rollback_own_lane_moves.py
uv run --frozen pytest -q tests/terminus/test_post_approval_commit_refused.py tests/terminus/test_lifecycle_closure_on_approved_lane_7346.py tests/terminus/test_rollback_record_rebaseline.py tests/terminus/test_forced_approval_restamp.py
uv run --frozen pytest -q tests/consolidation/test_approved_bound_residuals.py tests/consolidation/test_dependency_merge_attribution_7307.py
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
make test-fast
```

Before the upstream WPs are merged into your lane, the module is red: record that red run (which step fails, with which output) in the WP history. Once they are merged, every test is green with no `xfail` and no `skip` (Objectives: no xfail exit). Do not run `make test-full` or the whole `tests/terminus/` directory.

Quality gates (tests are typed code too):

```bash
uv run --frozen ruff check tests/terminus/approved_lane_route_support.py tests/terminus/test_approved_lane_resolution_route.py
uv run --frozen ruff format --check --force-exclude tests/terminus/approved_lane_route_support.py tests/terminus/test_approved_lane_resolution_route.py
uv run --frozen mypy tests/terminus/approved_lane_route_support.py tests/terminus/test_approved_lane_resolution_route.py
```

Complexity ≤ 15 per function; no suppressions.

## Tracer notes

Record with `spec-kitty agent tasks add-history WP12 --note "<trace: ...> ..."` (for `traces/tooling-friction.md`, `approach.md`, `design-decisions.md`): every CLI friction met while driving the route (exact command, output, issue filed), the approval command set that worked for an unforced independent approval, the chosen strategy/topology matrix and its runtime, and any lane-checkout sparse-exclusion friction during the hand merge (#5965).

## Risks & Mitigations

- **Route gap found late** (the spec assumption that `approved -> in_progress -> for_review -> in_review -> approved` works unforced with the window and ownership guards). Mitigation: write the happy path first and run it as soon as your lane holds the dependencies. A gap is never an xfail: stop, record the failing step with `add-history`, and report to the runner, who reopens the WP owning the failing surface.
- **Session size.** This WP is the two-lane route only; SC-004, the three-lane variants and the lanes-topology cells are WP14.
- **Vacuous negative controls.** Mitigation: assert specific codes, assert fixture preconditions (merge exists, own content non-empty), assert zero branch moves by full snapshot.
- **Synthetic approvals.** Never use `restamp_approvals_at_lane_tips`, `_restamp_approvals`, `--force` on the positive path, or the same identity for implementer and reviewer.
- **Runtime.** Each CLI call is a subprocess (up to 180 s timeout). Keep the matrix explicit and justified.
- **Frozen modules.** Import, never edit, the existing support modules.

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md`, FR-008 finding):

- The positive path uses only CLI commands plus the two human acts; no in-process restamp helper; no `--force`; distinct implementer and reviewer identities.
- The approval event's `lane_head` descends from the resolution merge (asserted).
- Re-entry is a fresh run, fixed in the test, not "whichever passes".
- N1, N2, N3 each assert the named code and no branch moved by reflog lengths and "no snapshot" (not by final SHAs). N1's name and parametrisation show it refuses with and without a novel line.
- The SC-003 test carries the discriminating control (a land-then-rollback changes reflog lengths).
- The residual control lands the reviewed novel line with exit 0.
- Squash AND `--strategy merge` happy paths are both present and green.
- No `xfail` and no `skip` anywhere in the module (grep it). A route gap was reported through history and the runner, not marked.
- The fixture asserts `merge-tree` reports the conflict; the three-lane builder asserts its preconditions (smoke test).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP12 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP12 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
