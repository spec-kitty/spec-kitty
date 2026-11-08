---
work_package_id: WP18
title: Resume reads one frozen anchor set
dependencies:
- WP17
requirement_refs:
- FR-015
- NFR-002
- NFR-010
- SC-004
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T091
- T092
- T093
- T094
- T095
- T096
phase: Phase 4 - Behaviour changes, red-first
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/reconciliation_kernel.py
create_intent:
- src/specify_cli/consolidation/reconciliation_kernel.py
- src/specify_cli/consolidation/reconciliation_closed_world.py
- src/specify_cli/consolidation/reconciliation_bound.py
- src/specify_cli/consolidation/reconciliation_canceled.py
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/claim_inputs.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization_support.py
- tests/consolidation/characterization/verdict_corpus.json
- tests/consolidation/test_resume_frozen_anchors.py
- tests/consolidation/resume_frozen_anchors_support.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_kernel.py
- src/specify_cli/consolidation/reconciliation_closed_world.py
- src/specify_cli/consolidation/reconciliation_bound.py
- src/specify_cli/consolidation/reconciliation_canceled.py
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/approved_attestation.py
- src/specify_cli/consolidation/claim_inputs.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/phase_gate.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/run_state.py
- tests/consolidation/test_resume_frozen_anchors.py
- tests/consolidation/resume_frozen_anchors_support.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization_support.py
- tests/consolidation/characterization/verdict_corpus.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP18 – Resume reads one frozen anchor set

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP18 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`_closed_world_anchors` returns, for a lane, the **branch names** of its dependency lanes (less planning and fully-canceled lanes) plus the target's pre-consolidation tip. Branch names are read live. On `consolidate --resume`, a dependency lane that gained a commit after the interruption therefore widens what is exempt (spec US4 (b)). The fresh run already froze those tips into `state.json` (`ConsolidationState.pre_interrupt_lane_tips`, keyed by created lane branch); the resume does not read them for the anchors.

Operator ruling (Decision Moment `01M6YAFZVZAYR4G20Q2X4PN0FT`, research R-17, FR-015): on `--resume`, **one** frozen claim-time anchor set, built from `ClaimInputs` (`SAVED`), feeds **all four** consumers of `_closed_world_anchors`:

| # | Consumer (pre-split location) | After Phase 3 (find by symbol) | NFR-002 cell |
|---|---|---|---|
| 1 | mixed-lane resolver `_resolve_mixed_lane` (`reconciliation.py:2103-2118`) | `reconciliation_canceled.py` | **(e)** closed world |
| 2 | approved bound `_approved_bound_verdict` / per-lane scope (`reconciliation.py:2268`) | `reconciliation_bound.py` | **(f)** approved bound |
| 3 | fully-canceled lane's own commits `_fully_canceled_lane_own_commits` (`reconciliation.py:2516-2531`) | `reconciliation_canceled.py` | **(g)** fully-canceled lane |
| 4 | approved-reviewed attestation `_refuse_moved_reattestations` (`approved_attestation.py:157-211`, call at `:198`) | unchanged module | no named cell (see T095) |

Done means:

1. On a resume, every consumer replaces a dependency lane's live branch name by its frozen tip from `pre_interrupt_lane_tips`; a dependency lane with **no** frozen tip keeps today's live read (a *degraded anchor*, named in the ADR: pre-upgrade record, or a status surface that did not resolve at capture, H1). The planning-lane and fully-canceled-lane exclusions stay exactly as they are.
2. A fresh run and a forecast keep their verdicts (their anchors are unchanged; golden fresh/forecast cells byte-identical).
3. Three red-first tests, one per NFR-002 flip **(e)**, **(f)**, **(g)**, drive `consolidate --resume` in process from a state reached with the **SIGKILL harness**, each committed failing before the fix (NFR-010). (g) may instead be a cell that records the flip is unreachable, with the reason (NFR-002 (g)).
4. The attestation consumer gets its own red-first entry-point test too.
5. The (e), (f), (g) intended-verdict pins (WP05) lose their strict `xfail` marker in the fix commit; only their golden cells change.

**NFR-002 flips covered: (e), (f), (g)** (FR-015). SC-004 (second half).

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — US4 (b) and acceptance 3-5, FR-015, NFR-002 (e)(f)(g), NFR-010, C-004, SC-004.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-15 (Purpose and Risks: read them twice), "Routing hint" (review together with WP02's resume runner).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-11, R-17 (coverage of `pre_interrupt_lane_tips`, holes H1-H4).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` section 6 (`dependency_anchors` row, CI-3, CI-5).
- The ADR `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` (WP01): frozen anchor set on resume, degraded anchors.
- Code (pre-split lines; after WP15 locate each symbol by name — `reconciliation.py` is a re-exporting facade):
  - `_closed_world_anchors` (`reconciliation.py:2455-2484`, now `reconciliation_kernel.py`): returns `_lane_branch_for(...)` names for dependency lanes that are neither planning nor fully canceled, plus `target_base`.
  - `phase_claim.py:321-345` `_resolve_pre_mutation_coord_sha`: persists `pre_mutation_coord_sha`, `pre_mutation_coord_ref` and `pre_interrupt_lane_tips` once, then `save_state(...)` (`:344-345`). `_capture_pre_interrupt_lane_tips` (`:296-318`) keys tips by **created branch**, skips `lane-planning` and fully-canceled lanes.
  - `phase_claim.py:372-395` `_refuse_unanchored_resume` (H5) and `:398-445` `_enforce_resume_anchor_integrity` (H4, H5, H3 via `state.lane_tip_cas_ok`, which accepts a **descendant** tip: an advanced dependency lane passes H3).
  - `phase_claim.py:485-558` `_capture_reconciliation_claim`: H-checks, then the base, then the claim (now through `claim_inputs`/`build_claim`, WP09), then `run.bound_anchor_shas = _bound_anchor_shas(run, coord_base)` (frozen SHAs for the gate re-check; keep consistent, do not change).
  - `executor.py:455-473`: `excluded_canceled_wp_ids`, `_refuse_unexplained_branch_moves`, then `_record_operator_attestations` (`:463`) — **before** the record is loaded at `:491` (`_load_or_create_merge_state`) and before the claim at `:577`. `_phase_merge_lanes` runs at `:614`.
  - `approved_attestation.py:125-155` `plan_approved_attestations` → `_refuse_moved_reattestations` → `check_lane(..., anchors=[*_closed_world_anchors(lanes_manifest, lane, None, ...), *stamp_anchors])`.
  - `claim_inputs.py` (WP09/WP17): `ClaimInputs.dependency_anchors` ("computed for completeness ... WP18 consumes it"), the `SAVED` resolver, `build_claim`.
- Test infrastructure:
  - `tests/consolidation/characterization_support.py` (WP02): `interrupt_after_claim(mission)`, `run_in_process`, `build_shape`, `regenerate_cells`. Read WP02's docstring/tracer entry for the SIGKILL hook point it chose.
  - `tests/terminus/rollback_harness.py`: `state_path`, `ref_shas`, `reflog_shas`, `run_hard_killed` (pattern), `flat`.
  - `tests/terminus/approved_content_support.py`: `InterruptedConsolidate` (`operator_clears_stale_locks` pattern for the global merge lock `.kittify/runtime/merge/__global_merge__/lock`).
  - `tests/terminus/post_approval_support.py`: `build_post_approval_mission(tmp_path, "coord")`, `lane_worktree`, `add_post_approval_commit`. `tests/terminus/canceled_dependency_support.py`: `build_canceled_dependency_mission`. `tests/terminus/conftest.py`: `build_coord_mission`, `plant_canceled_commit`, `restamp_approvals_at_lane_tips`.
  - WP05 pins in `tests/consolidation/test_reconciliation_intended_verdicts.py`: `test_resume_closed_world_reads_frozen_anchors` (e), `test_resume_approved_bound_reads_frozen_anchors` (f), `test_resume_fully_canceled_lane_reads_frozen_anchors` (g), with their `require(...)` precondition helper and fixtures. **Read WP05's history**: it may already record (g) as unreachable.
- Cross-cutting: C-009 (no rollback or branch-restore caller outside `rollback.py`; this WP adds none), C-013, C-014, NFR-004 (complexity <= 15: thread a value, do not add branches to already-dense functions; extract a helper), NFR-005, NFR-009, C-004, CI-4 (`ClaimInputs` never writes the event log or the rollback snapshot; **no new `ConsolidationState` field** — `pre_interrupt_lane_tips` is the source, R-05).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP18 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Commit plan (red first)

1. `test(consolidation): SIGKILL resume fixtures for frozen anchors (WP18)` — T091 (support module; fixture self-tests pass).
2. `test(consolidation): red-first resume closed world reads live dependency tips (NFR-002 e, WP18)` — T092, red.
3. `test(consolidation): red-first resume approved bound reads live dependency tips (NFR-002 f, WP18)` — T093, red.
4. `test(consolidation): red-first resume fully-canceled lane / attestation read live dependency tips (NFR-002 g, WP18)` — T094 and the attestation test, red (or the (g) unreachable record, green, with its reason).
5. `fix(consolidation): resume reads one frozen anchor set for all four anchor consumers (FR-015, WP18)` — T095 + T096.

Record each red SHA with its failing summary line in the history note.

## Subtasks & Detailed Guidance

### Subtask T091 – SIGKILL resume fixture

- **Purpose**: A resume test is only meaningful if it reaches a real interrupted state that holds frozen tips. An exception exit does **not**: a pre-mutation exit clears a fresh record, and a full-restore rollback re-baselines it and drops the tips on LANES / `single_branch` (#6770). Either turns the resume into a fresh run and the red test into a vacuous one (plan IC-15 Risks, renata F-07, H2).
- **File**: `tests/consolidation/resume_frozen_anchors_support.py` (new). Move the (e)/(f)/(g) fixture builders out of WP05's intended-verdict module into it, so the pins and the red tests share one fixture each (update the pins' imports; behaviour unchanged).
- **Steps**:
  1. Reuse `characterization_support.interrupt_after_claim(mission)`. Verify its kill point is **after** `_capture_reconciliation_claim` has persisted the anchors (`phase_claim.py` `save_state` at `:344-345`) and **before** `_phase_merge_lanes` (`executor.py:614`). Patching `executor._phase_merge_lanes` in the child to `os.kill(os.getpid(), signal.SIGKILL)` is the cleanest hook. If WP02 chose a different point that is earlier than the anchor `save_state` or later than the first lane merge, fix `interrupt_after_claim` (you own `characterization_support.py` for this) and re-run `tests/consolidation/test_reconciliation_characterization.py` (resume cells must not change; if they do, stop and ask).
  2. Add `frozen_resume_state(mission, dependency_branch) -> str` that, after the kill, checks with `require(...)` (raises `FixturePrecondition(RuntimeError)`, never `assert`): `state_path(mission)` exists; the JSON's `pre_interrupt_lane_tips[dependency_branch]` equals the dependency lane's tip read **before** the kill; `pre_mutation_coord_sha` is set; `completed_wps == []`; the target ref and its reflog are unchanged. Then remove the stale global merge lock. Return the frozen tip.
  3. Add `advance_dependency_lane(mission, dep_lane, *, merge_into: str | None) -> str`: one commit `D` on the dependency lane in its worktree (`lane_worktree`), touching a non-bookkeeping path no WP owns; when `merge_into` is given, merge the dependency lane into that lane in its worktree (`git merge --no-edit <dep branch>`). Returns `D`'s SHA. Afterwards `require` that `state.lane_tip_cas_ok` accepts every lane (the advanced lanes are descendants), so the resume reaches the claim instead of refusing at H3.
  4. Fixtures (coordination topology — frozen tips are captured only when the status surface ref resolves, `_resolve_pre_mutation_coord_sha`; confirm which topologies freeze tips and record it in the tracer):
     - `build_mixed_lane_with_dependency(tmp_path)` for (e): lane B holds an approved WP and a WP canceled with operator provenance (mixed), and depends on lane A (approved).
     - `build_bound_lane_with_dependency(tmp_path)` for (f): lane B (not mixed, approved) depends on lane A (approved).
     - `build_fully_canceled_dependency(tmp_path)` for (g): a fully-canceled lane C whose own dependency lane A is approved (C's anchors are A's tip plus the target base).
  5. Fixture self-tests (green, committed in commit 1): `test_fixture_reaches_frozen_state_for_<e|f|g>` asserting the preconditions above hold and that a resume **without** `advance_dependency_lane` reaches the fresh run's verdict on a copy (US4-4).
- **Do not**: write or edit `state.json` by hand (NFR-010: 0 hand-written records); use an exception exit to interrupt; run the resume through a subprocess (seeded mutations and patches must reach it).

### Subtask T092 – Red: closed world (NFR-002 e)

- **File**: `tests/consolidation/test_resume_frozen_anchors.py` (new; `pytest.mark.integration`, `pytest.mark.git_repo`).
- **Test `test_resume_closed_world_does_not_exempt_a_post_interrupt_dependency_commit`**:
  1. `build_mixed_lane_with_dependency`; `interrupt_after_claim`; `frozen = frozen_resume_state(mission, lane_a_branch)`; `D = advance_dependency_lane(mission, "lane-a", merge_into="lane-b")`.
  2. `before = ref_shas(mission)`; `result = run_in_process(mission, ["consolidate", "--mission", slug, "--resume", "--yes"])`.
  3. Assert: exit 1; the output carries the mixed-lane closed-world refusal for lane B with reason `commit_outside_windows` (`UnattributableReason.COMMIT_OUTSIDE_WINDOWS`) naming `D` (short SHA as rendered); no branch moved (`ref_shas` and the target/coordination reflogs unchanged).
  4. The fixed output may also carry the approved bound's refusal for the same commit after `This Mission also has:` (`_compound_refusal`); assert the closed-world part is present, do not assert it is alone.
- **Red on the parent**: lane A's live tip reaches `D`, so `D` is exempt and the closed world passes. Read the failure before committing.

### Subtask T093 – Red: approved bound (NFR-002 f)

- **Test `test_resume_approved_bound_refuses_a_post_interrupt_dependency_commit`**:
  1. `build_bound_lane_with_dependency`; interrupt; `frozen_resume_state(mission, lane_a_branch)`; `D = advance_dependency_lane(mission, "lane-a", merge_into="lane-b")`.
  2. Resume in process.
  3. Assert: exit 1; `LANE_MOVED_AFTER_APPROVAL` for lane B naming `D` (the merge commit is dropped by `content_commits`, so `D` is the named commit); no branch moved (spec US4-5).
- **Red on the parent**: `D` is reachable from lane A's live branch name, an anchor, so it is exempt.
- **Control `test_fresh_run_on_the_same_fixture_keeps_its_verdict`**: a fresh `consolidate` on a copy of the fixture **before** the kill and without the advance: its verdict equals the golden fresh cell for this shape (unchanged by the fix).

### Subtask T094 – Red: fully-canceled lane (NFR-002 g) and the attestation consumer

- **(g) `test_resume_fully_canceled_lane_is_judged_against_the_frozen_dependency_tip`**: `build_fully_canceled_dependency`; interrupt; `frozen_resume_state(mission, lane_a_branch)`; advance lane A **and merge the canceled lane's tip into lane A** after the interruption (the only way a dependency advance can shrink C's "own commits": anchors that reach C's commits remove them from `lane_own_commits`). Resume. Intended: C's canceled commits stay C's own (judged against the frozen tip), so the canceled-dependency content axis still subtracts them / refuses as the fresh run would (`CANCELED_REACHABLE_VIA_DEPENDENCY` or the `canceled_lane_content` refusal, whichever the fresh run reports on the same shape — read the golden fresh cell).
  - If you find the flip **unreachable** (e.g. H3 refuses the merge as divergence, or the axis that consumes C's own commits never runs on a resume of this shape), keep a test named `test_resume_fully_canceled_lane_flip_is_unreachable` that asserts the reachable consequence, with the reason in its docstring, and convert WP05's (g) pin accordingly (NFR-002 (g) allows this). Stop and tell the orchestrator before writing the fix; record the reason in the tracer.
- **Attestation `test_resume_attestation_check_reads_the_frozen_dependency_tip`** (consumer 4; no NFR-002 cell, no golden cell — the corpus has no attestation cells, so nothing in the golden may change for it):
  1. Fixture: lane B (approved, depends on lane A) whose WP was attested `approved_reviewed` with a stamp (use `consolidate --attest-approved-reviewed <WP> --attest-reason ...` on the first run, or the recording helper `approved_attestation.record_approved_reviewed_attestation` in the fixture), then interrupted with the SIGKILL harness.
  2. After the kill: advance lane A and merge it into lane B. Resume with `--attest-approved-reviewed <WP> --attest-reason "again"`.
  3. Intended: refused, `cannot be repeated for <WP>` (`_refuse_moved_reattestations`), nothing recorded (event log bytes unchanged, `rollback_harness.event_log_bytes`). Today: `D` is exempt through lane A's live name, the repeat is accepted.
  4. If the attestation path cannot be reached on a resume (for example because the executor refuses the flag combination earlier), record that, keep a test that pins the reachable behaviour, and tell the orchestrator.

### Subtask T095 – Thread the frozen anchor set into all four consumers

- **Design** (keep the change a threaded value, not new branching):
  1. `_closed_world_anchors(lanes_manifest, lane, target_base, *, excluded_canceled_wp_ids, frozen_tips: Mapping[str, str] | None = None)`: for each surviving dependency lane, `branch = _lane_branch_for(...)`; append `frozen_tips[branch]` when `frozen_tips` holds that key, else `branch` (degraded / fresh: today's live read). Filters unchanged. Document the degraded-anchor rule in the docstring with the ADR slug.
  2. `build_approved_wp_set(..., frozen_dependency_tips: Mapping[str, str] | None = None)` (now in `reconciliation_claim.py`) threads it into the mixed-lane scope (`_MixedLaneScope` gains one field), the approved-bound verdict and `_fully_canceled_lane_own_commits` / `_fully_canceled_lane_commits`. Default `None` = today's behaviour, so the orchestrator-api door `approved_bound_refusal` and every other caller are unchanged.
  3. `claim_inputs.build_claim` passes `frozen_dependency_tips` from `inputs.dependency_anchors` **only for `SAVED`** (resume); `LIVE` and `LIVE_THEN_SAVED` pass `None`, so the forecast and the fresh run keep byte-identical verdicts. `dependency_anchors` already has the shape this needs (WP09 fixed it: `Mapping[str, str]`, created dependency-lane branch -> tip SHA, the key space of `pre_interrupt_lane_tips`); pass it through unchanged. If it does not fit, **stop and ask the orchestrator**: do not reshape a field WP09 owns (its parity test is not in your owned files). `SAVED` reads only the persisted record (CI-3: never a live fallback for a saved value).
  4. `phase_gate.py` defensive rebuild (only when no claim was captured): pass the same inputs the run used. `run.bound_anchor_shas` (gate lane re-check) stays as is; confirm in a comment that it already uses frozen SHAs.
  5. Attestation (consumer 4): `plan_approved_attestations(..., frozen_dependency_tips=None)` → `_refuse_moved_reattestations` → `_closed_world_anchors(..., frozen_tips=...)`. In `executor.py`, when the run is a `--resume` and a record exists, read it read-only with `load_state(main_repo, canonical_id)` **before** `_record_operator_attestations` and pass `state.pre_interrupt_lane_tips` (the same record `_load_or_create_merge_state` loads at `:491`; do not reorder `_refuse_unexplained_branch_moves`, which must stay first). On a fresh run pass `None` (live tips equal what the claim then freezes, CI-5). A missing key keeps the live read; H5 refuses a partial record moments later anyway.
- **Must stay true**: no new `ConsolidationState` field; the planning-lane and fully-canceled exclusions unchanged; H3/H4/H5 order unchanged; no restore or rollback call added (C-009).
- **Unit tests** (in `test_resume_frozen_anchors.py`, fix commit): `test_closed_world_anchors_substitute_frozen_tips`, `test_closed_world_anchors_keep_live_name_without_a_frozen_tip` (degraded anchor), `test_closed_world_anchors_without_frozen_tips_are_unchanged` (`None`, compare with today's output). Keep `tests/consolidation/test_reconciliation.py::test_closed_world_anchors_are_transitive_dependency_tips_plus_target_base` green unchanged.

### Subtask T096 – Flip the (e), (f), (g) pins and regenerate only their golden cells

- **Steps**:
  1. Remove the strict `xfail` markers from `test_resume_closed_world_reads_frozen_anchors`, `test_resume_approved_bound_reads_frozen_anchors` and `test_resume_fully_canceled_lane_reads_frozen_anchors` (or the converted unreachable-(g) test). They must pass. `test_parallel_claims_window_is_not_over_wide` and the WP19/WP20 pins stay XFAIL.
  2. List the (e)/(f)/(g) golden keys (resume cells with a dependency-lane advance after the interruption) and record them:
     ```bash
     uv run --frozen python -c "import json;d=json.load(open('tests/consolidation/characterization/verdict_corpus.json'));c=d.get('cells',d);print([k for k in c if k.startswith('resume|') and ('advance' in k or 'frozen' in k)])"
     ```
     Adjust the filter to WP02's actual variant suffix.
  3. Regenerate only those keys (`regenerate_cells(names)`), then check the subset against the WP17 tip (the parent of commit 1):
     ```bash
     BASE=$(git rev-parse <commit-1>^)   # parent of the red commit (WP02 helper, post-tasks squad R-03)
     uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; c = changed_cells('$BASE'); print(c); assert all(k.startswith('resume|') for k in c), 'a non-resume cell changed: C-004 violation'"
     ```
     The changed set must equal the (e)/(f)/(g) keys. Any other change (a resume cell without an advance, any fresh or forecast cell) means the fix leaked: fix the code, never the golden.

## Test Strategy

Red-first through `consolidate --resume` on the SIGKILL harness, one test per flip, preconditions asserted on `state.json` before resuming; unit tests alongside, never instead (NFR-010).

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_resume_frozen_anchors.py
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_claim_inputs_parity.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_approved_bound.py tests/consolidation/test_approved_bound_residuals.py tests/consolidation/test_approved_attestation.py tests/consolidation/test_canceled_dependency_lane.py tests/consolidation/test_canceled_dependency_attribution.py tests/consolidation/test_rollback_anchor_kill_window.py tests/consolidation/test_resume_coord_lag.py
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen pytest -q -n auto --dist loadfile tests/consolidation/
uv run --frozen pytest -q tests/terminus/test_post_approval_resume.py tests/terminus/test_unstamped_approval_attestation.py tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py tests/terminus/test_canceled_dependency_fast_forward_verdicts.py
uv run --frozen pytest -q tests/terminus/ -k "resume or attest or canceled"
uv run --frozen pytest -q tests/architectural/test_layer_rules.py
uv run --frozen ruff check src/specify_cli/consolidation/ tests/consolidation/test_resume_frozen_anchors.py tests/consolidation/resume_frozen_anchors_support.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation_kernel.py src/specify_cli/consolidation/reconciliation_bound.py src/specify_cli/consolidation/reconciliation_canceled.py src/specify_cli/consolidation/reconciliation_claim.py src/specify_cli/consolidation/approved_attestation.py src/specify_cli/consolidation/claim_inputs.py src/specify_cli/consolidation/executor.py tests/consolidation/test_resume_frozen_anchors.py tests/consolidation/resume_frozen_anchors_support.py
uv run --frozen mypy src/specify_cli/consolidation/reconciliation_kernel.py src/specify_cli/consolidation/reconciliation_bound.py src/specify_cli/consolidation/reconciliation_canceled.py src/specify_cli/consolidation/reconciliation_claim.py src/specify_cli/consolidation/approved_attestation.py src/specify_cli/consolidation/claim_inputs.py
make test-fast
```

(Format/mypy: add any other owned module you changed, e.g. `phase_claim.py`, `phase_gate.py`, `run_state.py`, `reconciliation_closed_world.py`.)

- [ ] Red evidence: commits 2-4 each have their SHA and failing summary line in the history note (and later the PR's *Tests run*); every red test asserted the `state.json` precondition before resuming. **Because lane SHAs can become unreachable after a squash consolidation with cleanup** (post-tasks squad R-14), also paste, for each red test, its full test id and the assertion message pytest printed (`uv run --frozen pytest -q -rf <test>` at the red SHA), so the PR and the post-merge mission review can check the red without checking out the SHA.
- [ ] 0 hand-written `state.json` records (`grep -n "state.json" tests/consolidation/test_resume_frozen_anchors.py tests/consolidation/resume_frozen_anchors_support.py` shows reads only).
- [ ] `-rxX`: (d), (e), (f), (g), (h) pins pass; the WP19/WP20 pins and the parallel-claims residual still XFAIL; zero XPASS.
- [ ] Golden diff = the (e)/(f)/(g) resume keys only (T096 step 3), keys recorded.
- [ ] All four consumers receive the same frozen set on a resume; fresh run and forecast pass `None`.
- [ ] No new `ConsolidationState` field, no new rollback/restore caller, no new `# noqa` / `# type: ignore`; touched functions <= 15 complexity (`uv run --frozen ruff check --select C901 src/specify_cli/consolidation`).
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP18" --entry "<summary>. <detail>"` for SIGKILL hook point confirmed or moved, topologies that freeze tips, (g) reachability, attestation reachability; and the one-sentence operator-visible Before/After of the fix, which WP21 turns into the `7403-resume-frozen-anchors.fixed.md` fragment (so this WP's reviewer checks the claim); `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Vacuous resume** (record cleared or re-baselined, so the resume is a fresh run): SIGKILL only, plus the `state.json` precondition before every resume.
- **H3 refuses the advance**: a merged-forward lane is a descendant, which `lane_tip_cas_ok` accepts; the fixture asserts it.
- **Fresh/forecast verdict drift**: `None` for non-`SAVED` sources; the T096 subset check fails on any non-resume cell.
- **Attestation runs before the record is loaded**: read it read-only with `load_state` at the attestation site; do not move the attestation after the claim.
- **Gate inconsistency**: `run.bound_anchor_shas` already freezes SHAs; leave it and note it.
- **Holes stay named, not fixed**: H1 (no capture when the status surface does not resolve: live read kept), H2 (full-restore re-baseline: next resume is a fresh capture by design), H4 (canceled set changed between capture and resume: refuses or drops anchors, safe).

## Review Guidance

- Reviewer profile: `reviewer-renata`; review together with WP02's resume runner (routing hint).
- **Model tier: top** (soundness of the resume path; four consumers; SIGKILL fixtures).
- Check out each red commit: the stated test fails because the live dependency tip exempts `D`, not because of a fixture error.
- Grep every call of `_closed_world_anchors` (expect four production callers plus tests) and confirm each receives the frozen set on a resume.
- Confirm the golden diff is resume-only and limited to (e)/(f)/(g).

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP18 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP18 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
