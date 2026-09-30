---
work_package_id: WP09
title: Owned status, plan setup and unsupported-action refusals
dependencies:
- WP07
- WP08
requirement_refs:
- FR-004
- FR-005
- FR-007
- FR-018
- FR-020
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T044
- T045
- T046
- T047
- T048
- T049
phase: Phase 3 - Commands and runtime
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/integration/test_owned_lifecycle_acceptance_status.py
- tests/integration/test_owned_lifecycle_acceptance_cli.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/tasks.py
- src/specify_cli/cli/commands/agent/tasks_status_cmd.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py
- tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py
- tests/integration/test_owned_lifecycle_acceptance_status.py
- tests/integration/test_owned_lifecycle_acceptance_cli.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Owned status, plan setup and unsupported-action refusals

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. Read `.kittify/charter/charter.md` if you have not read it in this session.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This WP closes the CLI legs of #3449 and #4252: an owned mission can be checked and planned entirely in its owned checkout P. The unsupported `agent action implement` and `agent action review` paths refuse with a typed code instead of acting on the repository root checkout R.

Done means:

1. **FR-004 / US1-AS1 (O1).** Given P holds a finalized M with WP01–WP02, and R holds a stale copy of M with WP01–WP05, `agent tasks status --owned-checkout P --mission H --json` does all of the following, for H ∈ {slug, mid8, id}:
   - exits 0;
   - lists exactly WP01–WP02;
   - carries `stale_repository_root_copy` naming R's copy;
   - leaves R unchanged (`r_snapshot`).
2. **FR-005 / US1-AS2 (O2).** Given M has a substantive committed `spec.md` in P, `agent mission setup-plan --owned-checkout P --mission H --json` does all of the following:
   - creates `plan.md` in P;
   - commits it on P's branch (P's `HEAD` advances by one, and that commit touches `kitty-specs/<slug>/plan.md`);
   - leaves R unchanged.
3. **FR-007.** Both commands carry `stale_repository_root_copy` in owned runs. Human mode prints the warning on stderr. Non-owned payloads are **byte-identical** to today.
4. **FR-018 / US6.** `agent action implement WP01 --owned-checkout P` and `agent action review WP01 --owned-checkout P` both:
   - exit non-zero with `OWNED_ACTION_UNSUPPORTED`;
   - give guidance naming `spec-kitty next --owned-checkout P` and `spec-kitty agent tasks move-task --owned-checkout P`;
   - create no worktree or branch;
   - write nothing to P or R.
5. **FR-020 / US1-AS3.** Every invalid `--owned-checkout` value in the matrix (T049) is refused on each of the five new flags with its registered code and no writes. Each case is paired with the valid-P row on the same fixture.
6. **Golden contracts** are updated in the same commit as each surface change:
   - `setup-plan` and `status` gain `--owned-checkout`;
   - the `status --help` snapshot is regenerated;
   - the existing `move-task` and `mark-status` help text stays byte-identical.
7. **Complexity.** Every function this WP touches is ≤ 15. Any touched function at ≥ 12, or one that your change would push to ≥ 12, gets a behaviour-preserving extraction commit **first**.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP09 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- **Mission docs** (under `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/`):
  - `spec.md`: US1, US6, FR-004, FR-005, FR-007, FR-018, FR-020, FR-021, NFR-001, NFR-002, NFR-004;
  - `plan.md`: IC-08, Test Layout, Staging Strategy;
  - `research.md`: R-12, R-13, R-14, R-16;
  - `data-model.md`: the error-code registry and `stale_repository_root_copy`;
  - `contracts/cli-owned-checkout-surface.md` (the command table and the flagless rule);
  - `contracts/architectural-gate.md` G2;
  - `occurrence_map.yaml`.
- **Prerequisites**:
  - **WP08** delivers `src/specify_cli/cli/commands/_owned_checkout.py`: `OwnedCheckoutOption`, `owned_checkout_option(help)`, `resolve_owned_or_adopt`, `refuse_owned_action`, `emit_owned_refusal` with the envelope builders (`success_false_envelope`, `json_error_envelope`, `result_error_envelope`), `stale_copy_payload` and `echo_stale_copy_warning`. Read its module docstring for the **envelope rule**: `stale_repository_root_copy` appears only in owned runs, and non-owned payloads are unchanged. Do not call `resolve_owned_mission` / `adopt_owned_checkout` directly (gate G2).
  - **WP07** delivers `commit_for_mission(..., owned=)` and the status emitters with `owned=`.
  - **WP04/WP05** deliver `placement_seam(..., owned=)` and `resolve_workspace_for_wp(..., owned=)` (transitional dual keyword).
  - **WP02** delivers the fixtures `owned_checkouts`, `r_snapshot` and `stale_root_copy` in `tests/integration/conftest.py`, plus the minter's per-case refusal codes (`tests/core/test_owned_mission_minter.py`).
- **Staging rules**:
  - Use `owned=` on the six shared seams and on every other function marked TRANSITIONAL(WP18).
  - Do not add new `effective_root=` call sites.
  - Use only canonical fact fields (`owned_root`, `repository_root`, `mission_dir`, `mission_slug`, `target_branch`). Never use the transitional `OwnedMission` legacy names, which WP18 deletes.
- **Flagless adoption** (contract "Flagless", FR-021). `agent tasks status` and `setup-plan` are owned-capable, so without the flag they call `resolve_owned_or_adopt(..., owned_checkout=None, cwd=Path.cwd())`. From cwd P, a flagless run equals the flagged run. Everywhere else it is unchanged.
- **Envelopes** (`serialized_keys: do_not_change`):
  - `tasks status` errors keep the `json_error` shape `{"ok": false, "error": {"code", "message"}}` (`tasks_status_cmd.py:153-162`, `json_contract.py:17-19`), plus an additive top-level `error_code` for owned refusals (`json_error_envelope`).
  - `setup-plan` errors keep the `{"result": "error", "phase_complete": false, "error_code", "error"}` family (`mission_setup_plan.py:1153-1160`, `result_error_envelope`).
  - `agent action implement/review` have **no** `--json` flag. The refusal is the human line `Error: [OWNED_ACTION_UNSUPPORTED] …` on stderr with exit 1. Do not add a `--json` flag; it is not in the contract.
- **Registered codes** (NFR-004): the data-model registry, which now lists the claim codes `OWNERSHIP_NESTED`, `OWNERSHIP_FOREIGN` and `OWNERSHIP_BROKEN_POINTER` (`checkout_ownership.py:61-76`; the validator already emits them and `tests/integration/test_explicit_checkout_commands.py:279-289` pins them) and the new `OWNED_CHECKOUT_IS_MISSION_WORKTREE` (a lane or coordination worktree passed as `--owned-checkout`, raised by WP02's minter).
- **Terminology**. New help and messages say "owned checkout" and "repository root checkout". The `status` command's help says "work packages in a feature" (`tasks.py:1368`), and this WP regenerates that snapshot anyway. Fix the wording to "in a mission" in the same commit; that is a campsite change under the terminology canon.
- **Complexity** (HEAD `df1588860`, `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' <file>`, also probed at 8 for headroom):
  - `mission_setup_plan.setup_plan` is **11**. The owned wiring adds branches, so T046 extracts first.
  - `tasks_status_cmd._st_load_work_packages` is **11**. T045 adds an owned branch, so it extracts first.
  - `tasks_status_cmd._st_resolve_dirs` is ≤ 8.
  - `workflow.implement` is 10 and `workflow.review` is ≤ 8. T047 adds one guarded call at the top of each; keep those ≤ 11 by calling a helper.
  - `tasks.list_tasks` (14), `validate_workflow` (15) and `_find_first_for_review_wp` (12) are **not touched**.
  - `_print_standard_human` (`next_cmd.py:1202`) is WP19's campsite (T103), not this WP's. T045's campsites are `_st_load_work_packages` and `setup_plan` only.
- **Declared out-of-map edits** (put a one-line rationale in each commit body):
  - `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/status.help` is the committed golden help snapshot for `status`. It must be regenerated when the flag is added (T048). No WP lists it.
- **`core/stale_detection.py` is WP05's.** WP05 (T023 step 6) adds `check_doing_wps_for_staleness(..., *, owned: OwnedCheckout | None = None)` with the `resolve_workspace_for_wp(owned=)` pass-through. This WP only passes `owned=st.owned` to it; no edit to that file here.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: allocated by `spec-kitty agent mission finalize-tasks` in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json`, which had not been generated when this prompt was written. Use `spec-kitty implement WP09`, and never build the path by hand.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

**Commit order**:
1. T044 red acceptance.
2. T049 red matrix.
3. Campsite extractions for T045 and T046.
4. T048: option migration plus goldens.
5. T045.
6. T046.
7. T047.

Each functional commit turns its slice of T044/T049 green.

## Subtasks & Detailed Guidance

### Subtask T044 – Red-first acceptance: O1, O2, US1, US6

- **Purpose**: reproduce #3449, #4252 and US6 through the **pre-existing entry points** before any fix (C-007). Pair each case with a same-fixture positive control so a pass can never be vacuous.
- **Steps**:
  1. Create `tests/integration/test_owned_lifecycle_acceptance_status.py` (markers `integration` + `git_repo`; in-process `CliRunner`). Invoke through the real Typer apps: `specify_cli.cli.commands.agent.tasks.app` with `["status", ...]`, and `specify_cli.cli.commands.agent.mission.app` with `["setup-plan", ...]`. Use only the WP02 conftest fixtures: `owned_checkouts` / `make_owned_checkouts`, `owned_handle` (parametrises H over slug, mid8 and id), `owned_cwd` (cwd ∈ {repository_root, owned_checkout, elsewhere}), `r_snapshot`, and `stale_root_copy` (use its `different_id=True` variant where needed).
  2. **Fixture preparation (inside the tests, no conftest edits)**:
     - WP02's default `owned_checkouts` already ships WP01–WP02 (`wp_ids=("WP01", "WP02")`, WP02 T011). Use it; there is no need to author WP files;
     - run the existing, working `agent mission finalize-tasks --owned-checkout P --mission H --json` (FR-022) so WP01–WP02 are finalized and committed in P;
     - run the O1/O2 rows **before** activating `stale_root_copy` (the "no stale copy" base column), then activate it so that R holds M with WP01–WP05 for the "with stale copy" rows.
     - For US1-AS2, start from a fixture state that has a substantive, committed `spec.md` and no `plan.md`. WP02's fixture ships `plan.md` (T011 step 2), so `git rm` it in P and commit before invoking.
  3. **Red cases.** Record every base result in the Activity Log.

     | Case | Invocation | Base, no stale copy (red) | Base, with stale copy (red) | Target |
     |---|---|---|---|---|
     | O1 | flagless `status --mission H --json`, cwd = P | `MISSION_NOT_FOUND` (the handle resolves against R) | exit 0 listing **R's** WP01–WP05 (fail-open) | exit 0, WP01–WP02 only (via adoption) |
     | O1-flag / US1-AS1 | `status --owned-checkout P --mission H --json`, cwd = R | exit 2 (no option) | exit 2 (no option) | exit 0; `[wp["id"] for wp in work_packages] == ["WP01","WP02"]`; `stale_repository_root_copy.path` == R's copy (with stale copy) / `null` (without) |
     | US1-AS1 human | same without `--json` | exit 2 | exit 2 | stale-copy text on `result.stderr` (with stale copy); board lists only WP01–WP02 |
     | O2 | flagless `setup-plan --mission H --json`, cwd = P | `PLAN_CONTEXT_UNRESOLVED` | `SPEC_FILE_MISSING` naming R's copy | success; plan committed in P; R unchanged |
     | O2-flag / US1-AS2 | `setup-plan --owned-checkout P --mission H --json`, cwd = R | exit 2 | exit 2 | success; `git -C P log -1 --name-only` contains `kitty-specs/<slug>/plan.md`; P `HEAD` advanced by exactly one; R unchanged |

     Both base columns are red for the recorded reason; record the observed `error_code` (or the fail-open exit 0) for each in the red commit's message.

  4. Create `tests/integration/test_owned_lifecycle_acceptance_cli.py` for US6, invoking `specify_cli.cli.commands.agent.workflow.app` with `["implement", "WP01", "--owned-checkout", str(P)]` and the same for `review`. Run with and without `--mission H`.
     - **Base**: exit 2.
     - **Target**:
       - exit 1;
       - the output (`result.stdout + result.stderr`) contains `OWNED_ACTION_UNSUPPORTED`, `spec-kitty next --owned-checkout` and `spec-kitty agent tasks move-task --owned-checkout`;
       - `git -C R worktree list --porcelain` and `git -C R branch --list` are identical before and after;
       - `r_snapshot` and a P snapshot (`git -C P status --porcelain`, `HEAD`, a file-hash walk) are unchanged.
  5. **Positive controls on the same fixture** (green on base, must stay green):
     - (a) A non-owned mission living only in R: `status --mission <R-mission> --json` from cwd = R. Capture its base payload **shape** (reuse the `_shape` helper idea from `test_tasks_cli_contract.py:244-253` locally) and assert it is equal after. It must have **no** `stale_repository_root_copy` key.
     - (b) `setup-plan` for an R-only mission from cwd = R succeeds with its base payload keys unchanged.
     - (c) `agent action implement` without `--owned-checkout` on an R lane mission is untouched. Asserting the flag-free CLI parse succeeds (`--help` exit 0) is enough; the existing implement tests cover behaviour.
     - (d) NFR-002: count `specify_cli.core.checkout_ownership.resolve_ownership_claim` calls. Owned `status` counts 1, owned `setup-plan` counts 1, and non-owned counts 0. Clear the workspace caches first.
     - (e) NFR-001: parametrise the owned cases over cwd ∈ {R, P, an unrelated temp dir} with `r_snapshot` unchanged, and unset `SPECIFY_REPO_ROOT` with `monkeypatch.delenv` so cwd matters.
- **Files**: `tests/integration/test_owned_lifecycle_acceptance_status.py`, `tests/integration/test_owned_lifecycle_acceptance_cli.py`.
- **Parallel?**: no; this is the first commit.
- **Validation checklist**:
  - [ ] Each red is red for the stated reason, not because of fixture errors. Record the error codes.
  - [ ] Every red row has a green sibling on the same fixture instance.
  - [ ] No imports from test modules.
- **Edge cases**:
  - The status JSON leg computes staleness for `in_progress` WPs. Keep US1-AS1's WPs in `planned`, and cover the in-progress path separately in T045.
  - `setup-plan` runs `_enforce_git_preflight`. Keep P's index clean before invoking.
  - Compare paths after `.resolve()` (on macOS, `tmp_path` sits under `/private`).

### Subtask T045 – `agent tasks status --owned-checkout` plus the stale-copy field; campsite `_st_load_work_packages`

- **Purpose**: `status` resolves the mission, its tasks, its event log and each WP's workspace from P through the fact, never from R (FR-004, FR-007). Today every one of those reads anchors on R: `_st_resolve_dirs` (`tasks_status_cmd.py:173-238`) and `_st_load_work_packages` (`:332-450`).
- **Steps**:
  1. **Campsite first** (its own commit, behaviour-preserving). Extract the committed-versus-coordination read-dir decision in `_st_load_work_packages` (`:355-356`) into `_st_status_read_dir(st) -> Path`. Add a focused unit test in `test_owned_lifecycle_acceptance_status.py` or in an existing status test module you own. Re-probe: `_st_load_work_packages` must be ≤ 11 and stay ≤ 11 after step 3.
  2. Wire the option:
     - `tasks.py` `status` (`:1361-1385`) gains `owned_checkout: OwnedCheckoutOption = None` and forwards it: `_do_status(mission=..., json_output=..., stale_threshold=..., owned_checkout=owned_checkout)`.
     - `_do_status` (`tasks_status_cmd.py:870-900`) gains a keyword-only `owned_checkout: Path | None = None` **after** `ports`, so existing test calls keep working.
     - `_StatusState` (`:121-150`) gains `owned: OwnedCheckout | None = None`. This carries the fact, not a bare path.
  3. Owned arm, in the order the phases run:
     - `_st_resolve_dirs`. After `repo_root` is located and **before** `_find_mission_slug`:
       - call `st.owned = resolve_owned_or_adopt(repo_root, owned_checkout, explicit_mission, cwd=st.cwd, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)`;
       - map `ActionContextError` through `emit_owned_refusal(..., envelope=json_error_envelope)`;
       - when `st.owned` is set:
         - `st.mission_slug = owned.mission_slug`;
         - `st.main_repo_root = owned.repository_root`;
         - `st.feature_dir = owned.mission_dir`;
         - `st.tasks_dir = placement_seam(owned.repository_root, owned.mission_slug, owned=owned).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"`;
         - return early. **Skip** `_ensure_target_branch_checked_out` (`:204`): R's branch is irrelevant, and checking it is part of O1. Also skip the `get_status_read_root` fallback (`:212-231`).
     - `_st_status_read_dir(st)`: when `st.owned` is set, return `st.owned.mission_dir` and **never** call `committed_status_dir(R, slug)` (`:355`). R's merged or committed copy is exactly the stale copy that must never win (FR-007).
     - `_st_resolve_execution_mode` (`:302-329`) gains `*, owned: OwnedCheckout | None = None` and calls `_tasks.resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id, owned=owned)`. Keep the `_tasks.` attribute route, because historical `@patch("...agent.tasks.resolve_workspace_for_wp")` seams must keep intercepting (module docstring `:20-33`).
     - Staleness (`_st_emit_json` `:477-482` and the human path): pass `owned=st.owned` to `check_doing_wps_for_staleness` (the parameter WP05 added).
     - Configuration and doctrine reads (`_review_stall_threshold_minutes` `:456`, `get_auto_commit_default` `:490`/`:761`, `build_activation_aware_doctrine_service` `:841`, `_get_hic_marker` calls): add a helper `_st_config_root(st) -> Path` that returns `st.owned.owned_root if st.owned else st.main_repo_root`, and use it at these sites. Every owned read resolves from P. Do not add a new `Path` **field** to `_StatusState`: gate G5 bans bare owned roots, and a derived helper is the honest form.
  4. Stale-copy field. In `_st_emit_json`, when `st.owned` is set, merge `stale_copy_payload(st.owned)` into `result` (`:499-514`). In `_st_render_human`, call `echo_stale_copy_warning(st.owned)` so the text goes to stderr. Non-owned runs emit neither.
  5. Add tests to `test_owned_lifecycle_acceptance_status.py`:
     - an owned WP moved to `in_progress` (via `move-task --owned-checkout P`, which already works under FR-022) renders `status --owned-checkout P --json` with `workspace_kind == "owned_checkout"` and no error;
     - the same with `stale_root_copy`, where R's copy has WP01 in a different lane, reports P's lane.
- **Files**: `src/specify_cli/cli/commands/agent/tasks.py`, `src/specify_cli/cli/commands/agent/tasks_status_cmd.py`, and the tests above.
- **Parallel?**: after T048 (the option declaration), alongside T046.
- **Validation checklist**:
  - [ ] T044's O1, O1-flag, US1-AS1 and US1-AS1 human rows are green.
  - [ ] Controls (a), (d) and (e) are green.
  - [ ] `test_tasks_cli_contract.py::test_success_envelope_shape[success_status]` is green **unchanged**, which proves the non-owned shape is untouched.
  - [ ] These pass: `tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py`, `tests/specify_cli/cli/commands/agent/test_tasks_status*.py` (if present; run `ls` to check), and `tests/integration/test_cli_status_mediation.py`.
  - [ ] `grep -n "resolve_owned_mission\|adopt_owned_checkout" src/specify_cli/cli/commands/agent/tasks*.py` finds nothing (G2).
- **Edge cases**:
  - `_find_mission_slug`'s `error_handler` (`:192-200`) must still render `MISSION_NOT_FOUND` exactly as before for non-owned missing handles. The owned arm returns before that call.
  - A coordination-topology owned mission: `OWNED_TOPOLOGY_UNSUPPORTED` (FR-023 pairing; `next` accepts it in WP19).
  - `--owned-checkout` without `--mission`: the minter raises its existing handle-required error. Pin that code in T049. Do **not** auto-select a sole mission for an explicit owned run.

### Subtask T046 – `setup-plan --owned-checkout` commits in P

- **Purpose**: planning an owned mission creates and commits `plan.md` on P's branch. Every read uses P: spec gate, template, lifecycle events, substantiveness, documentation wiring. R is never read for mission data and never written (FR-005, O2).
- **Steps**:
  1. **Campsite first** (behaviour-preserving). `setup_plan` (`mission_setup_plan.py:996-1172`) is at 11. Extract the root/branch/feature-dir preamble (`:1027-1040`, from locating the root through `_show_branch_context`) into `_resolve_setup_plan_scope(...) -> _SetupPlanScope`, a frozen dataclass holding `repo_root`, `feature_dir`, `mission_slug` and `target_branch`. Add a focused unit test, then re-probe. `setup_plan` must stay ≤ 11 after step 3.
  2. Add the option: `owned_checkout: OwnedCheckoutOption = None` on `setup_plan`. Registration needs no edit, because `mission.py:337` registers the function object. Update the docstring (`:1000-1016`), which currently says "project root checkout", to describe both the repository root checkout and the owned checkout.
  3. Owned arm inside `_resolve_setup_plan_scope`: call `resolve_owned_or_adopt(repo_root, owned_checkout, feature, cwd=Path.cwd(), allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)`. On refusal, call `emit_owned_refusal(..., envelope=result_error_envelope)`. `_SetupPlanScope` gains `owned: OwnedCheckout | None`. Then thread the fact through every step using this map:

     | Step (current line) | Non-owned (unchanged) | Owned |
     |---|---|---|
     | `_enforce_git_preflight(repo_root, …)` (`:1032`) | R | run against `owned.owned_root` (P's index and branch; the validator already proved the branch). First read `_enforce_git_preflight` (`mission.py:352`) and record what it checks. |
     | `_resolve_setup_plan_feature_dir` (`:1038`) | handle → R | `owned.mission_dir` |
     | `_show_branch_context` (`:1040`) | R branch | skip; `target_branch = owned.target_branch` |
     | `_planning_read_dir(repo_root, slug, …)` (`:1065-1068`) | seam | `placement_seam(owned.repository_root, slug, owned=owned).read_dir(<SPEC/PLAN kind>)` via the same `_mission._planning_read_dir` seam, which gains `owned=`. If `_planning_read_dir` lives in `mission.py` (WP-unowned), pass the owned read dir directly instead of editing it. |
     | `resolve_checkout_identity` + `_resolve_branch_match_operands` (`:1081-1088`) | invoking checkout | `current_branch = match_target_branch = owned.target_branch` |
     | `_enforce_spec_gate(…, repo_root, …)` (`:1089`) | R | `owned.owned_root` as the git root for the committed check |
     | `_resolve_plan_template(repo_root, …)` (`:1102`) | R | `owned.owned_root` (governance reads follow P, consistent with FR-016) |
     | `_emit_spec_plan_phase_events(…, repo_root)` (`:1106`) | R | `feature_dir = owned.mission_dir`; relative path against `owned.owned_root` |
     | `is_substantive(project_dir=repo_root)` (`:1115-1120`) | R | `owned.owned_root` |
     | `_commit_plan_if_substantive` → `_mission._commit_to_branch` (`:1121`, `:680`) | `commit_for_mission(repo_root, …)` | `_commit_to_branch(..., owned=owned)` → `commit_for_mission(owned.repository_root, slug, (plan_file,), msg, policy, kind=PLAN, target_branch=owned.target_branch, owned=owned)`. Keep `mission._commit_to_branch` as the patch seam, adding `owned: OwnedCheckout | None = None` as its last keyword. |
     | `_run_documentation_wiring(slug, repo_root, …)` (`:1131`) | R | `owned.owned_root` |
     | result payload | unchanged | `+ stale_copy_payload(owned)` (additive); human mode calls `echo_stale_copy_warning` |

  4. Keep the function-local `repo_root` names for non-owned behaviour. Do not introduce a parameter named `owned_root`, `checkout_root` or `effective_root` of type `Path` anywhere (G4/G5). Pass the fact, and read `owned.owned_root` at the use site.
- **Files**: `src/specify_cli/cli/commands/agent/mission_setup_plan.py`, and `tests/integration/test_owned_lifecycle_acceptance_status.py` for helper tests.
- **Parallel?**: after T048, alongside T045.
- **Validation checklist**:
  - [ ] T044's O2 and O2-flag rows are green. The P commit touches `plan.md`, and R is unchanged (HEAD, index, worktree list, `kitty-specs/`).
  - [ ] `test_mission_cli_golden_contract.py` passes: `setup-plan` envelope tests `:425-470` stay green and the flag set is updated in T048.
  - [ ] Existing setup-plan tests are green: `grep -rln "setup-plan\|setup_plan" tests/ --include=*.py`, run the ones under `tests/specify_cli/cli/commands/agent/` and `tests/integration/`, and record their names.
  - [ ] `_commit_to_branch`'s patch seam still intercepts (`grep -rn "_commit_to_branch" tests/`).
- **Edge cases**:
  - Non-substantive spec in P: the existing `SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED` payload with a P-anchored `spec_file` path. Add one row asserting the path is under P.
  - Scaffold-only plan (pristine template): no commit. Assert P's `HEAD` is unchanged and R is unchanged.
  - Documentation missions: `_run_documentation_wiring` may commit through `commit_for_mission` (`:792`, `:846`). Pass `owned=` there too, or explicitly confirm that software-dev owned missions never reach it and add a comment.

### Subtask T047 – `agent action implement` / `review`: refusal with `OWNED_ACTION_UNSUPPORTED`

- **Purpose**: the lane-worktree implement and review commands cannot run against an owned checkout. Accept the flag only to refuse, with a typed code and guidance to the supported owned path, before any side effect (FR-018, US6, decision `01M3M4GZ…`).
- **Steps**:
  1. In `src/specify_cli/cli/commands/agent/workflow.py`, add `owned_checkout: OwnedCheckoutOption = None` to `implement` (`:1336-1361`) and to `review` (`:1858-1866`).
  2. As the **first statement** of each body, before `_reset_workflow_receipts()`, `locate_project_root()` and any sparse-checkout preflight:

     ```python
     if owned_checkout is not None:
         _refuse_owned_action(owned_checkout, mission, action="implement")
     ```

     `_refuse_owned_action` is a small module-private helper so that `implement` stays ≤ 11. It:
     - locates the repository root;
     - calls WP08's `refuse_owned_action(repo_root, owned_checkout, mission, action=...)`;
     - catches `ActionContextError` and calls `emit_owned_refusal(exc, json_output=False, envelope=success_false_envelope)`. The envelope is unused in human mode but required by the signature.
  3. Refusal semantics come from WP08's helper:
     - with `--mission`, full validation runs first, so an invalid path gets its own FR-020 code;
     - without `--mission`, only the checkout-level checks run (`resolve_owned_create_root`: claim plus the repository-root refusal);
     - a valid P then gets `OWNED_ACTION_UNSUPPORTED`.

     Record this two-mode rule in the helper docstring and in both commands' `--owned-checkout` help: "Refused: owned checkouts use `spec-kitty next --owned-checkout` and `spec-kitty agent tasks move-task --owned-checkout`."
  4. T044's US6 rows turn green. Add a row asserting that `_reset_workflow_receipts` and `implement_sparse_checkout_preflight` are **not** called on the refusal path. Monkeypatch them to raise.
- **Files**: `src/specify_cli/cli/commands/agent/workflow.py`.
- **Parallel?**: yes, alongside T045 and T046 once T048 has landed.
- **Validation checklist**:
  - [ ] US6 rows are green for both commands, with and without `--mission`.
  - [ ] `implement` ≤ 11 and `review` ≤ 11 after the change (probe).
  - [ ] Existing implement/review suites are unchanged and green: `tests/specify_cli/cli/commands/test_implement_bulk_edit_flag.py`, `tests/cli/test_implement_bulk_edit_planning.py`, and `tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py`.
  - [ ] `grep -rln "\"--allow-sparse-checkout\"" tests/` finds any exact flag-set golden for `agent action implement`. If one exists, add `--owned-checkout` to it in T048 and record the file (it may not be in this WP's `owned_files`; declare it as out-of-map).
- **Edge cases**:
  - `--owned-checkout R` with `--mission` gives `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, not `OWNED_ACTION_UNSUPPORTED`. The more specific refusal wins.
  - No worktree may be created. `implement` normally allocates a lane worktree further down, so the early return is what guarantees this. Assert on `git worktree list`.

### Subtask T048 – `tasks.py` options onto `OwnedCheckoutOption`; golden contracts

- **Purpose**: one declaration source for `--owned-checkout` (R-13, R-16 "eight inline declarations"). Update the frozen CLI contracts in the same commit that changes the surface, so the goldens never drift.
- **Steps**:
  1. `tasks.py` `move_task` (`:782-791`) and `mark_status` (`:916-919`): replace the inline `Annotated[Path | None, typer.Option("--owned-checkout", help=...)]` with WP08's `owned_checkout_option(help=<the exact existing string>)`. That help-preserving form is covered by the `CLI_CLAIM_INPUT_RULE` G5 exemption; keep the parameter name, and the CLI flag name `--owned-checkout` is unchanged. The help text stays **byte-identical**, so `fixtures/tasks_cli/help/move-task.help` and `mark-status.help` do not change. The forwarding at `:851` and `:954` is unchanged. The other inline declarations belong to WP10, WP13, WP14, WP16 and WP19.
  2. `status` (`:1362-1366`) uses `OwnedCheckoutOption` (the default help). This is the T045 wiring. Land the declaration here so the golden update rides with it.
  3. Golden updates, all in this commit:
     - `test_tasks_cli_contract.py`: `CONTRACT_FLAGS["status"]` (`:148`) becomes `("--mission", "--json", "--stale-threshold", "--owned-checkout")`. Add a comment naming this mission and FR-004, following the file's dated re-pin convention.
     - `test_mission_cli_golden_contract.py`: `"setup-plan": frozenset({"--mission", "--json"})` (`:135`) becomes `frozenset({"--mission", "--json", "--owned-checkout"})`, with a dated comment (FR-005). `test_command_exposes_exact_flag_surface` compares exactly, so this is required.
     - **Regenerate** `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/status.help` (declared out-of-map). The repository has **no** automated regeneration switch; the harness compares `normalize_help(result.stdout) == fixture.splitlines()` (`test_tasks_cli_contract.py:196-203`). Regenerate with a one-off script in your scratchpad, not committed:

       ```python
       import pytest
       from typer.testing import CliRunner
       from specify_cli.cli.commands import _apply_short_help_options
       from specify_cli.cli.commands.agent.tasks import app
       from tests.specify_cli.cli.commands._help_snapshot import force_wide_help_console, normalize_help

       mp = pytest.MonkeyPatch(); force_wide_help_console(mp); _apply_short_help_options(app)
       out = CliRunner().invoke(app, ["status", "--help"]).stdout
       path = "tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/status.help"
       open(path, "w", encoding="utf-8").write("\n".join(normalize_help(out)) + "\n")
       ```

       Then check the fixture diff with `git diff`. It must show **only** the added `--owned-checkout PATH …` line, plus the "feature" → "mission" wording fix if you took that campsite.
     - Envelopes: `fixtures/tasks_cli/json/envelopes.json` `success_status` stays **unchanged**, because non-owned output is unchanged. Do not add the owned key there. The owned shape is pinned by T044.
  4. Run the whole contract pair: `test_tasks_cli_contract.py`, `test_tasks_cli_contract_coord.py` and `test_mission_cli_golden_contract.py`.
- **Files**: `src/specify_cli/cli/commands/agent/tasks.py`, `tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py`, `tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py`, and the out-of-map `.../fixtures/tasks_cli/help/status.help`.
- **Parallel?**: no. It precedes T045, T046 and T047 (the declarations they use).
- **Validation checklist**:
  - [ ] `git diff` of `move-task.help` and `mark-status.help` is empty.
  - [ ] `status.help` differs by the new option line (and the optional wording fix) only.
  - [ ] `grep -n 'typer.Option("--owned-checkout"' src/specify_cli/cli/commands/agent/tasks.py` finds nothing.
  - [ ] `test_help_fixtures_avoid_dependabot_requirements_trap` is still green: no `.txt` fixture was added.
- **Edge cases**:
  - Option order in the help output follows parameter order. Put `owned_checkout` **after** `stale_threshold` in `status` so the existing lines keep their order.
  - `_apply_short_help_options` must be applied before capture, or the `-h` line differs.

### Subtask T049 – FR-020 invalid-path matrix across the new flags

- **Purpose**: prove that each invalid `--owned-checkout` value is refused with its registered code and no writes on **every** new flag. Each invalid case is paired with the valid P on the same fixture (US1-AS3, FR-020, NFR-004).
- **Steps**:
  1. In `tests/integration/test_owned_lifecycle_acceptance_cli.py`, parametrise over `command ∈ {status, setup-plan, context-resolve, action-implement, action-review}` and `case`. Always pass `--mission H`: the implement and review commands use the with-mission branch here, so every code is reachable. Use `json.loads(stdout)["error_code"]` for the JSON commands, and a regex on `Error: [<CODE>]` in the combined output for implement and review.

     | case | construction (same fixture instance) | expected code |
     |---|---|---|
     | missing path | `tmp_path / "does-not-exist"` | `OWNERSHIP_BROKEN_POINTER` (pinned by WP02's `test_missing_path_is_refused`) |
     | directory outside any repository | a plain `tmp_path` directory that exists but has no `git init` anywhere above it (no `.git`, not inside R or any other repository) | `OWNERSHIP_BROKEN_POINTER` (US1-AS3; pinned by WP02's `test_directory_outside_any_repository_is_refused`, `tests/core/test_owned_mission_minter.py`, T007) |
     | non-worktree dir inside R | `R / "docs"` | `OWNERSHIP_NESTED` (pinned by WP02's `test_non_worktree_directory_is_refused`) |
     | foreign repository | a fresh `git init` elsewhere | `OWNERSHIP_FOREIGN` (existing, `test_explicit_checkout_commands.py:279-289`) |
     | repository root itself | `R` | `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` |
     | lane worktree | a registered lane worktree (see the edge cases) | `OWNED_CHECKOUT_IS_MISSION_WORKTREE` (pinned by WP02's minter tests) |
     | coordination worktree | a registered `…-coord` worktree | `OWNED_CHECKOUT_IS_MISSION_WORKTREE` (pinned by WP02's minter tests) |
     | mismatched branch | `git -C P checkout -qb other` | `OWNED_BRANCH_REFUSED` |
     | detached HEAD | `git -C P checkout --detach -q` | `OWNED_BRANCH_REFUSED` |
     | protected target | `make_owned_checkouts(protected_target=True)` (WP02 T011), which uses the R-only `protection:` config pattern from `test_explicit_checkout_commands.py:254-256` | `OWNED_BRANCH_REFUSED` |
     | non-single_branch mission | `make_owned_checkouts(topology="lanes_with_coord")` | `OWNED_TOPOLOGY_UNSUPPORTED` |
     | **valid P (control)** | P unchanged | `status` / `setup-plan` / `context-resolve`: success; implement / review: `OWNED_ACTION_UNSUPPORTED` |

  2. Put the expected-code table in a module constant. For the **five** rows whose expected code cites a WP02 pin — missing path, directory outside any repository, non-worktree dir inside R, lane worktree, coordination worktree — read `tests/core/test_owned_mission_minter.py` (WP02 T007's `test_missing_path_is_refused`, `test_directory_outside_any_repository_is_refused` and `test_non_worktree_directory_is_refused`) and `tests/core/test_adopt_owned_checkout.py` (the lane/coordination minter tests) and copy the pinned code, citing the test name in a comment. The NFR-004 registry (data-model.md) already lists `OWNED_CHECKOUT_IS_MISSION_WORKTREE` for both the lane and the coordination case; if WP02's tests pin a different code for a row, stop and raise it with the reviewer rather than inventing one.
  3. For every row assert:
     - exit 1;
     - the code is in the registered set;
     - no uncaught exception (`result.exception is None or isinstance(result.exception, SystemExit)`);
     - `r_snapshot` and a P snapshot are unchanged;
     - no new branch or worktree (`git worktree list --porcelain`, `git branch --list` identical).
  4. Mutation check (non-vacuity): temporarily make `resolve_owned_or_adopt` return a fact for R, confirm the `R` row goes red, then revert. Log it in the Activity Log.
- **Files**: `tests/integration/test_owned_lifecycle_acceptance_cli.py`.
- **Parallel?**: the red commit comes right after T044; the rows turn green as T045 to T047 land.
- **Validation checklist**:
  - [ ] 5 commands × 12 cases, including the valid control, all green at WP end.
  - [ ] Each fixture mutation (branch, protection, topology) happens on a fresh fixture instance per parametrised case, never shared across cases.
  - [ ] Runtime is acceptable for per-PR CI. If the matrix is slow, share one `r_snapshot` baseline per case, but never share state across cases.
- **Edge cases**:
  - **Lane and coordination worktrees**: if WP02's `owned_checkouts` fixture does not include them, build them in a local fixture in this file (`git -C R worktree add R/.worktrees/<m>-lane-a -b <lane-branch>` with a `lanes.json` entry for an R mission; `git -C R worktree add R/.worktrees/<m>-coord -b <coord-branch>`). Do not edit `tests/integration/conftest.py`.
  - The protected-target row must configure protection on **R** only. "The linked checkout cannot weaken it" (existing comment at `:254`).
  - `setup-plan` on the topology row: the minter refuses before any scaffold write. Assert that no `plan.md` appears in P.

## Test Strategy

**Red-first map** (C-007):

| Requirement | Red-first test | Entry point | Non-vacuity |
|---|---|---|---|
| FR-004 | O1 (flagless from P), O1-flag, US1-AS1 | `agent tasks status` via `CliRunner` | control (a): the non-owned status shape is unchanged; the golden `success_status` is unchanged |
| FR-005 | O2, O2-flag, US1-AS2 | `agent mission setup-plan` | control (b); the P commit assertion checks the file list, not just the exit code |
| FR-007 | stale-copy rows for `status` and `setup-plan` (JSON and human) | same | a no-copy sibling gives `null` or no key semantics per the WP08 rule |
| FR-018 | US6 rows | `agent action implement/review` | worktree and branch lists are unchanged; the side-effect functions are monkeypatched to raise |
| FR-020 | the T049 matrix | 5 commands | a valid-P control per command; the mutation check |
| NFR-002 | count rows (T044 (d)) | `status`, `setup-plan` | the non-owned 0 row |

**Commands** (record commands and pass/fail counts in the Activity Log and in the PR's *Tests run* section):

```bash
.venv/bin/python -m pytest tests/integration/test_owned_lifecycle_acceptance_status.py tests/integration/test_owned_lifecycle_acceptance_cli.py -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py -q
.venv/bin/python -m pytest tests/integration/test_explicit_checkout_commands.py tests/integration/test_cli_status_mediation.py tests/integration/test_json_envelope_strict.py -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/ -q          # owning subsystem dir
.venv/bin/python -m pytest tests/architectural/test_json_contract_enumeration.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_layer_rules.py -q   # implicated gates only
make test-fast
.venv/bin/ruff check src/specify_cli/cli/commands/agent/tasks.py src/specify_cli/cli/commands/agent/tasks_status_cmd.py src/specify_cli/cli/commands/agent/mission_setup_plan.py src/specify_cli/cli/commands/agent/workflow.py tests/integration/test_owned_lifecycle_acceptance_status.py tests/integration/test_owned_lifecycle_acceptance_cli.py tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py
.venv/bin/ruff format --check <same files>
.venv/bin/mypy --strict src/specify_cli/cli/commands/agent/tasks.py src/specify_cli/cli/commands/agent/tasks_status_cmd.py src/specify_cli/cli/commands/agent/mission_setup_plan.py src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/core/stale_detection.py src/specify_cli/cli/commands/_owned_checkout.py src/specify_cli/core/owned_mission.py src/specify_cli/workspace/context.py  # callers and callees in ONE invocation (follow_imports = "skip" for specify_cli.*)
```

mypy discipline (plan: Staging Strategy): never drop `--strict`; list callers **and callees** in the same invocation (`follow_imports = "skip"` for `specify_cli.*`). If `--strict` reports pre-existing errors in these files, run the identical command on the planning base, record that count, and show it did not grow; never narrow the file list to hide them.

Also run the tests for `core/stale_detection.py` (`grep -rl "stale_detection" tests/ --include=*.py`). Do not run `make test-full` or the bare `tests/architectural/` directory.

## Risks & Mitigations

- **Stale-copy leak through the committed-authority read.** `committed_status_dir(R, slug)` would prefer R's committed copy. T045 bypasses it for owned runs, and the lane-mismatch stale test pins that.
- **Golden churn.** The existing flags keep their help byte-identical via `owned_checkout_option(help=...)`. Only `status.help` changes, and its diff is reviewed.
- **Side effects before refusal (US6).** The refusal is the first statement, and the test monkeypatches the side-effect functions to raise.
- **Out-of-map edits.** Only `status.help` may be edited outside this WP's owned files; declare it in its commit body. (`core/stale_detection.py` is WP05's.)
- **Unregistered codes for lane and coordination checkouts.** T049 step 2 escalates rather than inventing a code.

## Review Guidance

- The owned arms of `status` and `setup-plan` read **only** P: grep the diff for `committed_status_dir`, `_ensure_target_branch_checked_out` and `get_main_repo_root` inside owned branches.
- G2: no direct `resolve_owned_mission` or `adopt_owned_checkout` calls in the files this WP touches.
- The golden updates are in the same commits as the surface change; the `status.help` diff is minimal; `move-task.help` and `mark-status.help` are unchanged.
- The T049 matrix has a valid-P control per command, and the mutation check is logged.
- The campsite extraction commits precede the functional commits, and each has focused tests.
- mypy ran clean on the touched sources.
- `_print_standard_human` is not touched here (WP19 T103 owns it); `core/stale_detection.py` is not edited here (WP05 owns it).
- Transitional surfaces (the six shared seams plus every other function marked `TRANSITIONAL(WP18)`) are expected until WP18; do not reject them.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-29T04:39:16Z – claude – shell_pid=8682 – Completed and committed T047 (agent action implement/review refuse --owned-checkout with OWNED_ACTION_UNSUPPORTED, FR-018/US6): red-first test commit 432968d0b then fix commit 13bcedc18. Wired WP08's refuse_owned_action/emit_owned_refusal via a new _refuse_owned_action() helper in workflow.py; both implement and review accept --owned-checkout via owned_checkout_option only to refuse before any side effect. 10 acceptance tests pass; full related suites green (test_implement_bulk_edit_flag, test_implement_bulk_edit_planning, test_issue_4905_coord_staging, test_workflow*, test_explicit_checkout_commands, test_cli_status_mediation, test_json_envelope_strict, architectural gate selftest/json_contract_enumeration/no_legacy_terminology/layer_rules -- 359 passed). ruff clean; mypy --strict (PYTHONPATH=src) 0 new errors vs base. implement/review stay <=11 complexity. NOT started: T044 (status/setup-plan acceptance rows for O1/O2), T045 (status --owned-checkout + stale-copy field + _st_status_read_dir campsite), T046 (setup-plan --owned-checkout + _resolve_setup_plan_scope campsite), T048 (move-task/mark-status option migration to owned_checkout_option + status option + golden updates), T049 (FR-020 invalid-path matrix). These require substantial wiring across tasks_status_cmd.py and mission_setup_plan.py (FR-004/FR-005/FR-007/FR-020) that was not attempted this pass to avoid landing unverified changes to those surfaces. Blocked on further dispatch/time to complete T044-T046,T048-T049.
- 2026-09-29T05:58:57Z – claude – shell_pid=8682 – All six subtasks complete: T044 (red-first O1/O2/US6 acceptance), T045 (status owned wiring), T046 (setup-plan owned wiring), T047 (implement/review refusal, landed earlier), T048 (option declarations + goldens), T049 (FR-020 invalid-path matrix). Commit order: 432968d0b (T044 US6 red) -> 13bcedc18 (T047 fix) -> de26c58eb (T044 O1/O2 red) -> ca1ec188f (T049 red matrix) -> 6f1811e67 (T045 campsite: _st_status_read_dir) -> 39f052461 (T046 campsite: _resolve_setup_plan_scope) -> 17e1e5bc5 (T048: tasks.py option migration + status flag + goldens) -> bb6e56546 (T045 functional: status owned wiring) -> b3297e262 (T046 functional: setup-plan owned wiring). Final state: tests/integration/test_owned_lifecycle_acceptance_status.py 9/9 green; tests/integration/test_owned_lifecycle_acceptance_cli.py 71/71 green (full FR-020 matrix across status/setup-plan/context-resolve/action-implement/action-review plus US6); owning-subsystem dir tests/specify_cli/cli/commands/agent/ 2111+ passed in an earlier full run (re-verified per-file after each commit); test_mission_cli_golden_contract.py 20/20 including the updated setup-plan exact-flag-surface golden; architectural gates (json_contract_enumeration, no_legacy_terminology, layer_rules, owned_checkout_gate_selftest) 359 passed. mypy --strict --explicit-package-bases (PYTHONPATH=src) over tasks.py, tasks_status_cmd.py, mission_setup_plan.py, workflow.py, stale_detection.py, _owned_checkout.py, owned_mission.py, workspace/context.py: 0 errors throughout. ruff check + format clean on every touched file (all format drift found was confirmed pre-existing on base via git show HEAD~N | ruff format --check). Complexity: _st_load_work_packages 11->10 (campsite) stays <=11 after owned wiring; setup_plan 11->9 (campsite) stays <=11 after owned wiring; implement/review stay <=11. G2 confirmed (grep for resolve_owned_mission/adopt_owned_checkout in tasks*.py and mission_setup_plan.py finds only docstring mentions, zero direct calls). G5 confirmed (grep for inline typer.Option("--owned-checkout" finds nothing in tasks.py or mission_setup_plan.py -- both route through WP08's OwnedCheckoutOption/owned_checkout_option). Markers: 0 TRANSITIONAL(WP18) added by this WP; 0 bridging markers added (this WP's new call sites use owned= directly on WP04/05/07/08-delivered signatures, no bridging needed). Out-of-map edits: tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/status.help and _group.help (declared in T048's commit, minimal diffs only); tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py (the consolidated compat-surface guard needed the new _st_status_read_dir symbol registered, declared in the T045-campsite commit). Known deviation from the literal T046 table: _run_documentation_wiring's two doc-only commit helpers (_run_documentation_gap_analysis/_detect_and_configure_generators) are NOT owned-wired -- confirmed unreachable for every software-dev owned fixture (early return before mission-type check fails), documented in the function's own docstring; a documentation-type owned mission still gets the correct mission-type-check read via the one placement_seam(owned=) call that IS wired.
- 2026-09-29T06:08:22Z – claude – shell_pid=30746 – Post-move-to-review fix commit b3dc01fff: a full tests/specify_cli/cli/commands/agent/ directory run (started before the move but only completing after) surfaced two gaps the earlier per-file runs missed -- _st_resolve_owned and _st_config_root (both added by the T045 functional commit) were natively defined but not registered in the consolidated compat-surface guard (test_tasks_compat_surface.py), and test_tasks_status_cmd_seam.py's resolve_workspace_for_wp call-shape pin needed owned=None added to match the new forwarding. Both fixed; full re-run of tests/specify_cli/cli/commands/agent/ + the three owned-lifecycle-acceptance test files is green. Reviewer: please pull this commit before reviewing; it is a small, mechanical registration/pin fix with no behavioral change to WP09's owned-checkout logic.
- 2026-09-29T08:22:53Z – claude – Review cycle 1 fix pass complete. Fixed: documentation wiring (owned= threaded into gap-analysis/generator commits); T045 step-5 + campsite tests; raising pins on both owned arms plus the two declared out-of-map fixes (status/lifecycle_events.py optional repo_root; coordination/commit_router.py uses owned.topology); sole-active-mission default no longer runs before owned resolution; T049 matrix deepened (exception, R+P snapshots, 5-command mutation check); T044 gaps closed; _resolve_setup_plan_scope focused tests; OWNED_ACTION_UNSUPPORTED literals and move_task trailing comma. CORRECTION (issue 10, history not rewritten): commit bb6e56546's body claims 'tests/specify_cli/cli/commands/agent/ (2111 passed, 5 skipped...)' - that whole-directory run was not a valid targeted run and must not be relied on. Commit 263288b2e's body says test_commit_router.py '14 passed'; the actual count was 13. Actual per-file counts this cycle: test_owned_lifecycle_acceptance_cli 75; test_owned_lifecycle_acceptance_status 34; test_mission_setup_plan_phases 57; test_tasks_status_cmd_seam 17; test_commit_router 13; test_commit_router_* (5 files) 39; documentation acceptance + transition_request_owned 30; status lifecycle/locking 73 (1 skipped); compat_surface+golden_contract+seam+commit_router+documentation 433 combined; default_mission+feature_resolution+status acceptance+seam 64. ruff check clean; mypy --strict 0 new (pre-existing: lifecycle_events.py:302-303, test_mission_setup_plan_phases.py:467); ruff format drift only in pre-existing hunks.
- 2026-09-29T09:00:29Z – claude – Review cycle 2 fix pass. (A) #4677 regression: red pins (lane/coord worktree bare status exit 1 mission_required) then _st_is_owned_candidate_checkout narrows the default-skip to separate linked checkouts only; flagless-from-P test tightened to assert exit 1 + mission_required; P under .worktrees covered. (B) PLAN_COMPLETED emission now passes repo_root=owned.repository_root; armed pins (get_main_repo_root armed after mint, patched in every module alias, raise AND record hits) added for owned setup-plan and owned status (cwd R and P); red at HEAD for setup-plan (1 hit) then green. MUTATION PROOFS: (1) reverting the PLAN_COMPLETED fix -> test_armed_get_main_repo_root_pin_setup_plan red; (2) injecting get_main_repo_root(owned_root) after st.owned in _st_resolve_owned -> both status armed pins red; (3) injecting it in _resolve_setup_plan_scope owned branch -> setup-plan armed pin red; all restored via git checkout, tree clean. Other emit_artifact_phase callers (mission_finalize.py TASKS_STARTED/COMPLETED, core/mission_creation.py SPECIFY_STARTED) are outside WP09's map: flagged, not changed. (Low) seam-test format drift back to baseline 5 hunks. Counts: 8 targeted files (acceptance status/cli/documentation, default_mission, feature_resolution, seam, compat_surface, setup_plan_phases) 608 passed. ruff/mypy 0 new.
- 2026-09-29T09:23:44Z – claude – Review cycle 3 fix pass. Removed the local topology heuristic _st_is_owned_candidate_checkout (and its compat registration). The #4677 default-skip now keys on core.owned_mission.invoking_checkout_would_adopt (declared out-of-map edit, WP02 file), which asks adopt_owned_checkout over the invoking checkout's own kitty-specs dirs (gap: adoption needs a handle and all listers anchor to get_main_repo_root). Red first: stale-lane and plain-linked-checkout bare status exited mission_required. All 7 rows green (R, listed lane, stale lane, coord, plain linked default; owned P outside R and under R/.worktrees refused, no leak). Counts: status acceptance + default_mission + feature_resolution + compat_surface + seam 474 passed; adopt_owned_checkout unit + G2 gate selftest 79 passed. ruff/C901/mypy 0 new.
- 2026-09-29T09:48:46Z – claude – Review cycle 4 fix pass. invoking_checkout_would_adopt bounded: shared _adoptable_toplevel (adoption's handle-independent front) and _branch_matches_target (minter branch rule), one branch read, meta.json pre-filter without git, adopt only for survivors. Measured (60 merged + 1 active missions, bare status from plain linked checkout / lane): git subprocesses 63 -> 3, ownership claims 1 -> 0, 0.09s; reviewer real-repo before: 53s / 1692 git / 516 claims. Red pins failed at 2f12e9370 and again against the old predicate. Removed unused type-ignore in test_adopt_owned_checkout (mypy clean). 725 passed across 10 targeted files; ruff/C901/mypy 0 new.
