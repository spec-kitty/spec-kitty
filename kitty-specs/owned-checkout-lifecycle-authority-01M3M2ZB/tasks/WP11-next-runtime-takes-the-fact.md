---
work_package_id: WP11
title: next runtime takes the fact
dependencies:
- WP05
- WP07
- WP08
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-012
- FR-023
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T057
- T058
- T060
- T061
- T062
- T063
- T066
- T067
phase: Phase 3 - Commands and runtime
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-28T16:00:00Z'
  actor: system
  action: Split — the next CLI entry (next_cmd.py and its test files) moved to WP19
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/integration/test_owned_next_runtime.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_engine.py
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_composition.py
- src/runtime/next/decision.py
- src/runtime/next/next_invocation_lifecycle.py
- src/specify_cli/coordination/workspace.py
- tests/next/test_runtime_bridge_unit.py
- tests/integration/test_owned_next_runtime.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – next runtime takes the fact

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter, and follow its guidance before you read the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the charter (`.kittify/charter/charter.md`) and the action context: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check `review_ref` in the event log (`spec-kitty agent tasks status --mission owned-checkout-lifecycle-authority-01M3M2ZB`) or the Activity Log below.
- **Address every item** before moving back to `for_review`, and log each fix in the Activity Log.

---

## Review Feedback

*[Empty until this WP is returned from review.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`spec-kitty next --owned-checkout P` is the canonical owned control loop (decision `01M3M4GZ…`). The work is split in two:

- **This WP (runtime core)** makes `runtime/next` carry the `OwnedCheckout` fact end to end: `DecideNextContext.owned`, the board authority, composition policy, git cwd, the lifecycle store, `decision.py`, and the typed #4867 refusal. It proves every row **at the runtime entry points** (`decide_next`, `decide_next_via_runtime`, `query_current_state`, `answer_decision_via_runtime`), with facts minted by the real validator.
- **WP19 (CLI entry)** makes `next_cmd.py` validate once through the sole minter and hand the fact to these entry points, and proves the same rows through the real `next` command.

| Row | Outcome at the runtime level | Proof (red on base → green here) |
|---|---|---|
| FR-008 / O5 | `decide_next_via_runtime(..., result="success", owned=fact)` at tasks→implement raises no `ValueError`. The WP workspace is resolved **before** the advance is persisted; the run is not wedged. `decision._state_to_action` takes the fact (T067). | runtime test + byte-identical run-snapshot oracle |
| FR-009 | Composition policy, task-board resolution and the git-log working directory are read from P. | runtime composition test + board test |
| FR-007 (board) | With a stale copy of M in R, the board authority never consults R: no workspace path is under R. | runtime test with the `stale_root_copy` fixture |
| FR-012 / O8 | A failing coordination-workspace probe produces a `blocked` decision with `error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`, never a `commondir` fatal. The transient-lock retry is kept. | two deterministic injections |
| FR-023 (runtime) | A `lanes_with_coord` owned fact is accepted by the runtime (`NEXT_OWNED_TOPOLOGIES`), and the runtime decision is non-error. | runtime-level `lanes_with_coord` twin |

**Out of scope here (WP19):** `next_cmd.py`, the O9 protected-target refusal through the CLI, the `stale_repository_root_copy` payload key, flagless adoption for `next`, handle-less `next`, the CLI-level FR-003 count, and the carried #5009 commits edaa9cd83 / 1be5352ee (WP19 T101). Do not edit `next_cmd.py`, `tests/integration/test_explicit_checkout_commands.py`, `tests/specify_cli/cli/commands/test_next_answer_effective_root.py` or `tests/integration/test_owned_lifecycle_acceptance_next.py`.

**Done when:**
- every row above has a red-first test **committed before** its fix commit (the red commit precedes the fix commit in `git log`; reviewers verify the order);
- all targeted files are green, and ruff, format and mypy are clean;
- the runtime modules owned here contain no `effective_root` except the **exactly six** `TRANSITIONAL(WP18)`-marked lines listed in T063 (`grep -c "TRANSITIONAL(WP18)"` summed over the owned `src/` files is **6**; see T063 for the per-file counts);
- `grep -rn "bridging: WP11" src` is empty; the only bridging markers this WP leaves are `# bridging: WP12 converts` on the `prompt_builder.build_prompt` call sites (T067);
- `make test-fast` is green.

## Context & Constraints

- **Read first:**
  - `spec.md`: US3, O5, O8, FR-007/008/009/012/022/023.
  - `plan.md`: Staging Strategy, Test Layout, IC-05, IC-13.
  - `research.md`: R-02, R-06, R-08, R-11, R-12, R-15, R-16.
  - `data-model.md`: registry codes.
  - `contracts/owned-checkout-carrier.md` §2 and §7.
  - `occurrence_map.yaml`.
- **What the dependencies provide.** Read their merged code, not the plan, before you start.
  - **WP01**: `mission_runtime.OwnedCheckout` and the `OwnedRefusalCode` `StrEnum` (import codes from it; never repeat a code literal, Sonar S1192).
  - **WP02**: `resolve_owned_mission(..., allowed_topologies)` and `NEXT_OWNED_TOPOLOGIES`; the shared fixtures `owned_checkouts` / `make_owned_checkouts`, `r_snapshot` and `stale_root_copy` in `tests/integration/conftest.py`.
  - **WP04/WP05**: `placement_seam`, `mission_context_for`, `resolve_action_context`, `resolve_workspace_for_wp` and `locate_work_package` accept `owned=` (dual keyword until WP18). Workspace caches are keyed on the resolved tasks dir (FR-019). **No fallback:** if WP05's owned cache-isolation API is missing, this WP is **blocked**; file it against WP05 and stop. Do not work around it here.
  - **WP07**: `TransitionRequest.owned`.
- **Root discipline (the core rule of this WP).** The runtime receives `repo_root = owned.repository_root` (R) plus `owned`. Inside the runtime, when `owned` is set:
  - owned-aware consumers (contract §7: `placement_seam`, `mission_context_for`, `resolve_workspace_for_wp`, `locate_work_package`, `DecideNextContext`) receive `owned=`;
  - callees that are not yet owned-aware receive `owned.owned_root` in the root argument they already have: the run store (`get_or_start_run`), the lifecycle store, `PackContext`/composition, and git cwd. This preserves today's owned behaviour, because today `next_cmd` passes `repo_root` = P (`next_cmd.py:176-178`);
  - `repo_root` (R) is used only for repository-root-only concerns and never for mission-state reads or writes.

  Consequence: the run state, the lifecycle record and the coordination worktree stay where they live today for owned missions, which is under P.
- **Staging (bottom-up for this split, with a marked legacy entry).** `next_cmd.py` (WP19) still calls the runtime with the legacy `effective_root=` keyword until WP19 lands. So the five runtime entry points that `next_cmd` calls keep a legacy keyword, and **only** those:
  - `decision.decide_next`;
  - `runtime_bridge.query_current_state`;
  - `next_invocation_lifecycle.pair_previous_lifecycle_record`, `write_issuance_lifecycle_record`, `emit_mission_next_invoked`.

  Each keeps `effective_root: Path | None = None  # TRANSITIONAL(WP18): next_cmd legacy caller until WP19 T105`. Its arm obtains the fact **once** through one helper, `_transitional_owned_from_legacy(effective_root, mission_slug)` in `runtime_bridge.py`, marked `# TRANSITIONAL(WP18): legacy next_cmd arm; deleted with the keyword`. The helper calls `resolve_owned_mission(get_main_repo_root(effective_root), effective_root, mission_slug, allowed_topologies=NEXT_OWNED_TOPOLOGIES)` and returns the fact; the entry point then continues on the `owned` path with `repo_root = fact.repository_root`. No other runtime function keeps `effective_root`. (It is a transitional G2 call site; WP18 deletes it with the keywords, and WP19 leaves it without callers.)
  - Callees in the file owned by **WP12** (`src/runtime/next/prompt_builder.py`) are not converted here. They receive the bridging value that preserves today's behaviour: `owned.owned_root if owned else repo_root` as their existing `repo_root` argument, each call marked `# bridging: WP12 converts`.
  - Do not remove `effective_root=` from the six shared seams (WP18 does).
- **Campsite first.** Before changing their signatures, extract these functions (behaviour-preserving, in their own commit):
  - `query_current_state` (`runtime_bridge.py:2661`, complexity 15), T058;
  - `_state_to_action` (`decision.py:394`, complexity 14), T066.

  `next_step` and `_print_standard_human` are WP19's campsites (T103). `_run_bootstrap_loop` is WP13's (T071). `_build_wp_prompt` is WP12's (T068). Check with `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' <file>`.
- **Terminology.** Use "repository root checkout" and "owned checkout" in code, messages and tests. Rename test locals `primary` to `repository_root` in any test you touch. Do not use `feature` aliases.
- **Error contract.** Refusals always carry `error_code` from `OwnedRefusalCode` (NFR-004). Tests assert on `error_code` only, never on git's stderr wording.

## Branch Strategy

- **Strategy:** the planning artifacts were generated on `claude/sleepy-hamilton-5lelee`, and completed changes merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch:** `claude/sleepy-hamilton-5lelee`
- **Merge target branch:** `claude/sleepy-hamilton-5lelee`
- **Execution lane:** assigned by `finalize-tasks` in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json`. Start with `spec-kitty implement WP11` and use the workspace it resolves. Never reconstruct the path yourself.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T057 – Red-first runtime acceptance: O5, O8 (both injections), composition, stale-copy board, lanes_with_coord twin

- **Purpose:** C-007. Every row gets a reproduction at the **runtime entry points**, committed **before** any `src/` fix. (T056 and T059 moved to WP19 as T101/T103; their ids are retired.)
- **Steps:**
  1. Create `tests/integration/test_owned_next_runtime.py` with `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`. It lives under `tests/integration/` so it can use WP02's shared fixtures (do not import fixtures from test modules):
     - `make_owned_checkouts(*, topology=…, placement="sibling"|"under_worktrees", wp_ids=…)`. It is **not** finalized: run `agent mission finalize-tasks --owned-checkout P --mission H` in setup (it exists on the base);
     - `r_snapshot` (`before = r_snapshot.take()` … `r_snapshot.assert_unchanged(before, r_snapshot.take())`);
     - `stale_root_copy`.

     Mint every fact with the real validator: `resolve_owned_mission(repository_root, owned_root, slug, allowed_topologies=NEXT_OWNED_TOPOLOGIES)`. Never construct `OwnedCheckout` directly.
  2. **O5 / FR-008.** On a finalized owned mission, call `decision.decide_next("claude", slug, "success", repository_root, owned=fact)`. Assert:
     - no `ValueError` and no traceback;
     - the decision is not `blocked` for a workspace-resolution reason;
     - `workspace_path == str(fact.owned_root)`, `action == "implement"`, `wp_id == "WP01"`;
     - a following `runtime_bridge.query_current_state("claude", slug, repository_root, owned=fact)` does **not** return the same unadvanced decision.

     On the base this is red (`TypeError` for `owned=`, and the fold to R behind it; record both reasons).
  3. **Pre-finalize fallback pin (T067).** `_state_to_action("implement", slug, owned_root / "kitty-specs" / slug, repository_root, "software-dev", owned=fact)` returns `("implement", "WP01", str(fact.owned_root))`; and through the board authority `runtime_bridge._wp_iteration_action_and_state("implement", slug, "software-dev", owned_root / "kitty-specs" / slug, repository_root, owned=fact)` resolves P.
  4. **FR-009 composition.** A runtime-level reproduction of 1be5352ee's composition row: a `DecideNextContext` with `repo_root=repository_root, owned=fact`; stub `_advance_run_state_after_composition` to assert `kwargs["owned"] is fact` and `kwargs["repo_root"] == repository_root`, and stub `_composition._composition_dispatch_inputs` / `_dispatch_via_composition` to assert `repo_root == fact.owned_root`. Red on the base.
  5. **O8 / FR-012, two deterministic injections.** Assert only on `decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` with `kind == "blocked"`.
     - **(a) Zero-byte `commondir`.** Build an owned `lanes_with_coord` mission (`make_owned_checkouts(topology="lanes_with_coord")`). Remove its coordination worktree directory. Add a sibling registered worktree with `git worktree add`, then truncate `<common-dir>/worktrees/<name>/commondir` to **zero bytes**. Pre-assert that `subprocess.run(["git", "-C", R, "worktree", "list", "--porcelain"]).returncode != 0`, and fail loudly with `pytest.fail` (never `skip`) if git tolerates it. R-16: a missing file or a lone newline gives rc 0.
     - **(b) Subprocess seam.** Monkeypatch `specify_cli.coordination.workspace.subprocess.run` (the probe after T062; on the base patch `check_output`, the probe at `coordination/workspace.py:163`) with a wrapper that fails with exit 128 **only** when `argv` contains `"worktree", "list"`, and delegates to the real function otherwise.

     On the base, both are red: `DecisionGitLogUnavailable` escapes from `runtime_bridge.py:389`.
  6. **FR-023 runtime twin.** With `make_owned_checkouts(topology="lanes_with_coord")` finalized, call `query_current_state(..., owned=fact)`. Expect a non-error decision. Red on the base only because `owned=` is not accepted (record it); the legacy-keyword control (`effective_root=owned_root`) is green on the base, which proves the scenario itself is sound.
  7. **Stale-copy board (FR-007).** With `stale_root_copy` (R holds a copy of M with a different lane map or WP set), call `decide_next(..., "success", repository_root, owned=fact)`. Assert that `workspace_path` is not under R (`Path.is_relative_to`, excluding P's subtree when P lives under R) and that the WP set is P's. The `stale_repository_root_copy` payload key is WP19's (T104), not asserted here.
  8. **NFR-001.** Wrap each scenario in `r_snapshot` and assert 0 differences.
  9. **Non-vacuity.** Each row has a same-fixture control: a non-owned lane mission through the same entry point stays green before and after.
  10. Commit: `test(next): red-first owned runtime acceptance (O5, O8, FR-007/009/023)`.
- **Files:** `tests/integration/test_owned_next_runtime.py` (new).
- **Validation checklist:**
  - [ ] Every row is red on the planning base for the stated reason, recorded in the Activity Log; the red commit precedes every fix commit.
  - [ ] No assertion reads git stderr text; codes come from `OwnedRefusalCode`.

### Subtask T058 – Campsite: `query_current_state`

- **Purpose:** Standing Order 2. Functions at complexity ≥ 12 whose signature this WP changes are extracted first, without behaviour change.
- **Steps:**
  1. **`query_current_state`** (`runtime_bridge.py:2661-2855`, complexity 15). Extract:
     - `_query_resolve_mission_context(repo_root, mission_slug, **owned_kw)`, which holds the try/except `ActionContextError` → read-path pass-through / `MissionNotFoundError` mapping (`:2698-2720`);
     - `_query_read_runtime_plan(run_ref, mission_slug, mission_type, repo_root)`, which holds the nested try around the ephemeral run and the planner (`:2754-2777`) and returns `(run_ref, ephemeral_run_store, snapshot, runtime_decision)`;
     - `_query_dispatch_decision(...)`, which holds the finalized-override / initial / decision-required / runtime branch ladder.

     Keep the `finally` rmtree of the ephemeral store in the outer function.
  2. Commit: `refactor(next): campsite extraction of query_current_state (C901)`.
- **Files:** `src/runtime/next/runtime_bridge.py`.
- **Validation checklist:**
  - [ ] `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' src/runtime/next/runtime_bridge.py` no longer lists `query_current_state` above 11.
  - [ ] `tests/next/` is green and unchanged.
  - [ ] No monkeypatch target used by existing tests has moved. Grep `tests/` for `runtime_bridge.<name>` patch strings before renaming anything.
- **Edge cases:** `query_current_state` is monkeypatched by name in many tests. Keep the public name and its signature (plus the new `owned` keyword in T060).

### Subtask T060 – `DecideNextContext.owned`, the `_dn_*` phases, composition policy and git cwd

- **Purpose:** FR-009 / R-11. The runtime carries the fact, not a bare root, and reads composition policy from P.
- **Steps:**
  1. Add `owned: OwnedCheckout | None = None` to `DecideNextContext` (`runtime_bridge.py:1561-1588`). Do not add an `effective_root` field.
  2. `decide_next_via_runtime` (`:2447`) and `_dn_bootstrap` (`:1591`) take `owned` instead of `effective_root`. In `_dn_bootstrap`, replace `mission_context_for(repo_root, slug, effective_root=…)` (`:1610-1622`) with `mission_context_for(repo_root, slug, owned=owned)`. Apply the root discipline:
     - `get_or_start_run` (`:1702`) → `owned.owned_root if owned else repo_root`;
     - `_build_operational_context_for_decision` → the same;
     - `resolve_mission_path(mission_type, …)` → the same.
  3. `_dn_composition_dispatch` (`:2020-2138`): let `config_root = ctx.owned.owned_root if ctx.owned else ctx.repo_root` (the re-expression of b1a1693bf's runtime half). Use it for `_should_dispatch_via_composition(..., repo_root=config_root)`, `_composition._composition_dispatch_inputs(repo_root=config_root)` and `_dispatch_via_composition(repo_root=config_root)`. Pass `owned=ctx.owned` to `_advance_run_state_after_composition` (`:1314`), which forwards to `runtime_bridge_engine.advance_run_state_after_composition` (`runtime_bridge_engine.py:318`). There, `_emit_terminal` uses the owned root for retrospective policy (`:249`).
  4. `_wrap_with_decision_git_log` (`:293`) and `_mission_routes_through_coordination` (`:240`) take `owned`. Every git cwd, and the `CoordinationWorkspace.resolve` root for an owned coordination mission, uses `owned.owned_root`, which is today's behaviour. The file `DecisionGitLog(repo_root=…)` uses the same root.
  5. `_dn_decision_materialize` (`:2242`) and `_map_runtime_decision` (`:3478`) thread `owned` down to the WP-iteration builders (T061).
  6. `next_invocation_lifecycle.py`: `pair_previous_lifecycle_record` (`:127`), `write_issuance_lifecycle_record` (`:225`) and `emit_mission_next_invoked` (`:316`) take `owned` and call `mission_context_for(..., owned=owned)` instead of the `effective_root` forks (`:167-178`, `:265-276`, `:341-352`). Each keeps the marked legacy keyword (Staging) for `next_cmd` until WP19.
  7. `runtime_bridge_io.py:1155`: the artifact-presence probe builds a second seam with `effective_root=repo_root`, which guesses at owned placement (R-16). Thread `owned` from `gather_artifact_presence` (`:1292`) callers (`runtime_bridge.py:907`, `runtime_bridge_composition.py:543`) into `_artifact_presence_seam` and build the owned seam with `owned=owned`. Remove the guess.
     - `runtime_bridge_composition.py`: thread `owned` into the presence-probe call site (`:543`) and make its composition-policy reads (`resolve_mission_type_context(repo_root, …)` `:189`, `:353`; `resolve_org_dirs(repo_root, …)` `:292`; `StepContractExecutor(repo_root=…)` `:654`) use `config_root` when owned. Keep its public names stable (tests patch them).
  8. `answer_decision_via_runtime` (`:2858`) gains `owned: OwnedCheckout | None = None`: its `resolve_action_context(repo_root, …)` becomes `resolve_action_context(repo_root, …, owned=owned)`, and `get_or_start_run` uses the owned root. `next_cmd._handle_answer` starts passing it in WP19; it needs no legacy keyword because it has no `effective_root` today.
- **Files:** `src/runtime/next/runtime_bridge.py`, `runtime_bridge_engine.py`, `runtime_bridge_io.py`, `runtime_bridge_composition.py`, `next_invocation_lifecycle.py`.
- **Validation checklist:**
  - [ ] T057's composition row is green.
  - [ ] Every existing `tests/next/test_runtime_bridge_unit.py` owned-threading test (`:1775-1990`) is re-pointed to `owned=` (facts from the real validator or WP02's fixture helper) and green, including the `_resolve_owned_coordination_workspace` retry tests at `:1789-1930`, which stay unchanged in behaviour.
- **Edge cases:** the `_owned_mission_*` helpers in `runtime_bridge.py` that exist only to re-derive ownership from a bare root become dead once the fact flows; delete them rather than keep them.

### Subtask T061 – Board authority with the fact; resolve before persisting the advance

- **Purpose:** FR-008 / O5 / R-06. Today `_dn_decision_materialize` persists the advance through `runtime_next_step(...)` (`runtime_bridge.py:2288`). The WP workspace is resolved **afterwards**, in `_map_runtime_decision` → `_build_wp_iteration_decision` (`:3204`) → `_wp_iteration_action_and_state` (`:3172`). On an owned mission:
  - `_resolve_wp_board_action(repo_root=P)` reads the repository root checkout through `placement_seam(P, …)`;
  - it declines on `ActionContextError`;
  - it falls back to `_state_to_action`, which folds to R and raises `ValueError`;
  - the run is left at `implement` (the wedge).
- **Steps:**
  1. `_resolve_wp_board_action(*, mission_slug, repo_root, owned=None)` (`:3081`) builds `placement_seam(repo_root, slug, owned=owned)` and `mission_context_for(repo_root, slug, owned=owned)`. `_resolve_wp_board_implement_action` (`:3032`) and `_resolve_wp_board_review_action` (`:3058`) call `resolve_workspace_for_wp(repo_root, slug, wp, owned=owned)`.
  2. `_wp_iteration_action_and_state` (`:3172`) and `_build_wp_iteration_decision` (`:3204`) take `owned`. The `decision.py` calls (`_state_to_action` fallback `:3200`; `_build_prompt_or_error` `:3264`, `:3388`, `:3446`; the sites at `:1913`, `:1923`, `:1978`, `:1986`) pass `repo_root=repo_root, owned=owned` (T067).
  3. **Resolve before persisting.** In `_dn_decision_materialize`, before calling `runtime_next_step`:
     - preview the next step read-only with `_engine_adapter.plan_next(snapshot, template, policy, live_template_path=…)`, exactly as `query_current_state` does;
     - if the previewed step is a WP-iteration step (`_is_wp_iteration_step`, `:657`), run `_wp_iteration_action_and_state(..., owned=ctx.owned)` **first**;
     - if it raises, the exception propagates **before** any state is persisted, as a typed error carrying `error_code`;
     - on success, persist the advance and pass the pre-resolved action into mapping, so the workspace is not resolved twice.

     **Do not** catch the resolution error into a `blocked` decision. FR-008 says wrapping into `blocked` fails the row.
  4. Keep the NFR-003 fail-closed arms (`CoordinationWorktreeUnmaterialized` / `CoordinationBranchDeleted`, `:3121-3143`) exactly as they are.
- **Files:** `src/runtime/next/runtime_bridge.py`.
- **Validation checklist:**
  - [ ] T057's O5 row is green: no traceback, workspace P, WP01 implement, and the run advances exactly once.
  - [ ] A unit test in `tests/next/test_runtime_bridge_unit.py` forces the pre-resolution to raise and asserts that the run snapshot (`state.json` / `run.events.jsonl` in the run dir) is **byte-identical** before and after. This is the "never persisted" oracle.
  - [ ] The lane-mission and coordination-mission board tests in `tests/next/` stay green (positive control for the non-owned arm).
- **Edge cases:** a pre-finalize owned mission (no finalized board) takes the `_state_to_action(owned=)` fallback (T067), which reads from P.

### Subtask T062 – #4867: `CoordinationWorkspaceUnavailable` → blocked `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`

- **Purpose:** FR-012 / R-08. `_has_stale_worktree_registration` (`coordination/workspace.py:161-184`) runs `subprocess.check_output([... "worktree", "list", "--porcelain"], text=True)` with stderr **not captured**. Exit 128 then escapes as `CalledProcessError`. `_wrap_with_decision_git_log`'s `except Exception` (`runtime_bridge.py:387-398`) re-raises it as `DecisionGitLogUnavailable`, which nothing catches, so the output is `fatal: … commondir: Success`.
- **Steps:**
  1. In `coordination/workspace.py`, add `class CoordinationWorkspaceUnavailable(subprocess.CalledProcessError)` with `error_code = OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`. It **must** subclass `CalledProcessError`: that is how `_resolve_owned_coordination_workspace` (`runtime_bridge.py:402-430`) keeps retrying transient lock contention through `_is_transient_git_worktree_contention` (`:433-456`), which reads `returncode` and `stderr`.
  2. Run the probe with `subprocess.run([...], capture_output=True, text=True, check=False)`. On a non-zero exit, raise `CoordinationWorkspaceUnavailable(returncode, argv, output=stdout, stderr=stderr)`. Apply the same wrapping to the `git worktree add` call in `resolve` (`:293-299`, already `capture_output=True`, `check=True`).
     - This file is formatter-excluded (`pyproject.toml` `[tool.ruff.format] exclude`). Do **not** reformat it wholesale. Keep your edit locally formatted.
  3. In `_wrap_with_decision_git_log`, let `CoordinationWorkspaceUnavailable` propagate **unwrapped** when `owned` is set.
  4. In `_dn_bootstrap` (where the wrap is called, `:1674-1682`), catch `CoordinationWorkspaceUnavailable` when `owned` is set and return a `blocked` Decision whose `reason` names the remediation (for example `git worktree prune` / `spec-kitty doctor coordination --fix`). Add `error_code: str | None = None` to the `Decision` dataclass (`decision.py:93`) and set it from the typed attribute; include it in the decision's serialization only when non-null, so non-owned payloads stay byte-identical. WP19 verifies the CLI JSON carries it; do not scrape the reason text anywhere.
     - The transient-lock path still retries first, so only a durable failure reaches this arm.
  5. Keep the non-owned behaviour unchanged: a non-owned coordination mission still raises `DecisionGitLogUnavailable` as today. Pin this with a unit test.
- **Files:** `src/specify_cli/coordination/workspace.py`, `src/runtime/next/runtime_bridge.py`, `src/runtime/next/decision.py`.
- **Validation checklist:**
  - [ ] Both T057 injections turn green and assert on `error_code` only.
  - [ ] `tests/next/test_runtime_bridge_unit.py::…_resolve_owned_coordination_workspace…` (`:1789-1930`) is green: transient contention still retries, and permanent failure still raises after the window.
  - [ ] A new unit test shows that `CoordinationWorkspaceUnavailable` is a `CalledProcessError` and is recognised by `_is_transient_git_worktree_contention` when its stderr carries the lock text.
- **Edge cases:**
  - `CoordinationWorkspace.teardown` (`:302-331`) also calls the probe. It is a subclass, so existing `except CalledProcessError` callers are unaffected.
  - Grep: `grep -rn "_has_stale_worktree_registration\|CoordinationWorkspace.teardown" src/`.

### Subtask T063 – Remaining conversions in the `runtime/next` bridge modules (runtime part)

- **Purpose:** leave the WP11-owned files free of bare owned roots and prepare for WP18's gate (G4/G5). The `next_cmd.py` part of the former T063 moved to WP19 T105.
- **Steps:**
  1. Convert the remaining `effective_root` sites. Current counts on HEAD: `runtime_bridge.py` 22, `next_invocation_lifecycle.py` 9, `runtime_bridge_io.py` 1 (plus `decision.py`, T067). Parameters and fields become `owned: OwnedCheckout | None`. Keyword arguments into the six seams become `owned=`. Arguments into WP12-owned `prompt_builder.py` become the bridging expression.
  2. Add the legacy arm (Staging) to the five `next_cmd`-facing entry points and the one helper. The **complete** `TRANSITIONAL(WP18)` list this WP adds (6 markers):

     | File | Marker(s) | `grep -c "TRANSITIONAL(WP18)" <file>` delta |
     |---|---|---|
     | `src/runtime/next/decision.py` | `decide_next(effective_root=)` | +1 |
     | `src/runtime/next/runtime_bridge.py` | `query_current_state(effective_root=)`, `_transitional_owned_from_legacy` | +2 |
     | `src/runtime/next/next_invocation_lifecycle.py` | the three lifecycle entry points' `effective_root=` | +3 |

     Record the before/after `grep -c` per file in the Activity Log. WP18 T096 fails on any marker not listed in some WP's DoD.
  3. Commit the conversions separately from the functional fixes, so review can read them as mechanical.
- **Files:** `src/runtime/next/runtime_bridge.py`, `runtime_bridge_io.py`, `runtime_bridge_composition.py`, `next_invocation_lifecycle.py`, `tests/next/test_runtime_bridge_unit.py`.
- **Validation checklist:**
  - [ ] `grep -n "effective_root" src/runtime/next/runtime_bridge.py src/runtime/next/runtime_bridge_io.py src/runtime/next/runtime_bridge_composition.py src/runtime/next/next_invocation_lifecycle.py src/runtime/next/runtime_bridge_engine.py src/runtime/next/decision.py` lists only the six marked lines above (and the helper's body, which uses the parameter it receives).
  - [ ] A unit test pins the legacy arm: `query_current_state(agent, slug, P, effective_root=P)` still returns today's decision (the existing `tests/specify_cli/cli/commands/test_next*` tests through `next_cmd` stay green unchanged).
  - [ ] `grep -rn "bridging: WP11" src` is empty.

### Subtask T066 – Campsite: `_state_to_action` (decision.py)

- **Purpose:** Standing Order 2. `_state_to_action` (`decision.py:394-493`, complexity 14) changes signature in T067, so it is extracted first.
- **Steps:**
  1. Extract:
     - `_implement_state_action(mission_slug, feature_dir, repo_root)` for the `state == "implement"` block (`:408-435`);
     - `_review_state_action(...)` for the review block (`:440-444`);
     - `_template_state_action(state, repo_root, mission_name)` for the generic template + `_ALIASES` resolution (`:451-493`).

     The outer function becomes a 4-way dispatch.
  2. Commit: `refactor(next): campsite extraction of decision._state_to_action (C901)`. No behaviour change; existing tests stay green unmodified.
- **Files:** `src/runtime/next/decision.py`.
- **Validation checklist:**
  - [ ] `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' src/runtime/next/decision.py` no longer reports `_state_to_action`.
  - [ ] `tests/next/` is green and unchanged. Grep `tests/` for the monkeypatch string `decision._state_to_action` and keep the name.
- **Edge cases:** `_state_to_action` is imported by name in `runtime_bridge.py` and in the carried #5009 test (WP19 T101). Keep the name and positional order. The in_review / for_review arbitration rules (FR-012a comments) survive unchanged.

### Subtask T067 – `decision.py` takes the fact

- **Purpose:** FR-008/FR-009. The pre-finalize fallback and the `decide_next` bridge in `decision.py` stop folding to the repository root checkout (#5009 e6923bc97 is re-expressed here, with a `Co-authored-by: Samuel Goff <samuel@defpix.com>` trailer).
- **Steps:**
  1. `decide_next` (`:313-341`): accept `owned: OwnedCheckout | None = None` and forward `owned=owned` to `decide_next_via_runtime`. Its `effective_root` keyword stays as the marked legacy arm (T063).
  2. `_state_to_action(state, mission_slug, feature_dir, repo_root, mission_name, *, owned: OwnedCheckout | None = None)`. Each `resolve_workspace_for_wp(repo_root, mission_slug, wp)` (`:425`, `:434`, `:443`) becomes `resolve_workspace_for_wp(repo_root, mission_slug, wp, owned=owned)`. `resolve_command(f"{state}.md", …)` and the alias variant use `owned.owned_root if owned else repo_root`, because a command template is a P-local governance read (e6923bc97).
  3. `_build_prompt_safe` (`:496`) and `_build_prompt_or_error` (`:524`) take `owned`. The composed-action probe `resolve_mission_type_context(repo_root, …)` (`:559`) uses the owned root. Their calls into `prompt_builder.build_prompt` (WP12) pass `repo_root=owned.owned_root if owned else repo_root`, each marked `# bridging: WP12 converts`.
  4. **Typed refusal mapping (prepares WP12).** `_build_prompt_or_error` catches `ActionContextError` raised by `build_prompt` and returns `(None, message)` while carrying the error's `code` on `Decision.error_code` (T062), so `next`'s JSON gets `error_code` without parsing reason text. Pin it with a unit test that stubs `build_prompt` to raise `ActionContextError(OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE, "x")`.
  5. `_with_guard_failure_paths(decision, repo_root)` (`:344`): if guard paths must name owned artifacts, pass the owned root. Otherwise leave it unchanged and say why in the Activity Log.
  6. Convert every `runtime_bridge.py` call site into `decision.py` (`:1913`, `:1923`, `:1978`, `:1986`, `:3200`, `:3264`, `:3388`, `:3436`, `:3446`) to `repo_root=repo_root, owned=…` (see T061).
- **Files:** `src/runtime/next/decision.py`, `src/runtime/next/runtime_bridge.py`.
- **Validation checklist:**
  - [ ] `grep -n "effective_root" src/runtime/next/decision.py` lists only the marked `decide_next` legacy keyword and its arm.
  - [ ] `grep -n "bridging: WP12" src/runtime/next/decision.py` lists only the `build_prompt` calls (record the count; WP12's DoD asserts it reaches 0).
  - [ ] The non-owned behaviour of `tests/next/` (lane and coordination missions) is unchanged.

## Test Strategy

Red-first order (each red is a **commit** that precedes its fix commit; no Activity-Log-only or stash-based proofs):
1. T057 reds (commit before any `src/` edit).
2. T058 and T066 campsites (green).
3. T060–T062 and T067 fixes (reds turn green).
4. T063 conversion.

Record exact commands and counts under *Tests run*:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/integration/test_owned_next_runtime.py \
  tests/next/test_runtime_bridge_unit.py
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/next/            # owning subsystem
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/specify_cli/cli/commands/ -k next   # the legacy next_cmd caller stays green
grep -rl "runtime_bridge\|runtime.next.decision\|next_invocation_lifecycle\|coordination.workspace\|CoordinationWorkspace" tests/ --include="*.py"  # run each hit not already covered (excluding e2e/slow)
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/specify_cli/coordination/ tests/runtime/
make test-fast
.venv/bin/ruff check src/runtime/next/ src/specify_cli/coordination/workspace.py tests/integration/test_owned_next_runtime.py tests/next/test_runtime_bridge_unit.py
.venv/bin/ruff format --check src/runtime/next/runtime_bridge.py src/runtime/next/runtime_bridge_io.py src/runtime/next/runtime_bridge_composition.py src/runtime/next/decision.py src/runtime/next/next_invocation_lifecycle.py tests/integration/test_owned_next_runtime.py tests/next/test_runtime_bridge_unit.py
.venv/bin/mypy --strict src/runtime/next/runtime_bridge.py src/runtime/next/runtime_bridge_engine.py src/runtime/next/runtime_bridge_io.py src/runtime/next/runtime_bridge_composition.py src/runtime/next/decision.py src/runtime/next/prompt_builder.py src/runtime/next/next_invocation_lifecycle.py src/specify_cli/cli/commands/next_cmd.py src/specify_cli/coordination/workspace.py src/specify_cli/core/owned_mission.py src/mission_runtime/owned_checkout.py
.venv/bin/python -m pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_mission_runtime_surface.py tests/architectural/test_cold_import_status_boundary.py  # the specific gates this WP implicates
```

- **mypy discipline (plan: Staging Strategy).** Never drop `--strict`, and always list callers and callees in the **same** invocation (`follow_imports = "skip"` for `specify_cli.*`; `next_cmd.py` is listed because it calls the changed entry points). If the base already has errors in these files, record the pre-existing count on the planning base (same command) and show the count did not grow; never narrow the file list to hide them.
- `ruff format --check` deliberately omits the formatter-excluded `runtime_bridge_engine.py` and `coordination/workspace.py`.
- Do **not** run `make test-full` or the bare `tests/architectural/` directory.

## Risks & Mitigations

- **FR-008's prompt half is owned by WP12.** `prompt_builder._build_wp_prompt` has no owned arm (`prompt_builder.py:162-170`). This WP proves the runtime half (no wedge, workspace P, advance, `decision.py` on the fact). WP19 commits the full US3-AS1 CLI row as a strict xfail, and WP12 removes it.
- **Legacy arm window.** Between this WP and WP19, `next_cmd` validates claim-only and the runtime's legacy arm validates fully (FR-003's count of exactly 1 is asserted by WP19 once the arm has no caller). If an existing test pins legacy acceptance of a checkout the full validator now refuses, stop and escalate to the orchestrator; do not weaken the validator.
- **Coordination worktree placement.** For owned coordination-topology missions, the coordination worktree is created under the root passed to `CoordinationWorkspace.resolve`. Today that is P. The root discipline keeps it at P; passing R changes R's `.worktrees/`, and NFR-001 reddens.
- **Monkeypatch churn.** Many tests patch `runtime_bridge.*` names. Keep names stable; change only keyword parameters.
- **Transient lock retry.** If `CoordinationWorkspaceUnavailable` does not subclass `CalledProcessError`, concurrent owned creates regress. The unit test in T062 pins the subclass.

## Review Guidance

- Verify the red-first commit order in `git log` (T057 red commit before every fix commit) and the recorded red reasons.
- Verify that both #4867 injections exist, that injection (a) pre-asserts git failure with `pytest.fail` (never `skip`), and that no assertion reads git stderr.
- Verify that no `effective_root` survives in WP11-owned modules except the six listed `TRANSITIONAL(WP18)` lines, that `grep -rn "bridging: WP11" src` is empty, and that the only bridging left is `# bridging: WP12 converts`.
- Verify that `next_cmd.py` and the WP19 test files are untouched.
- Verify the campsite commits (T058, T066) precede the signature changes.
- Verify that resolution happens before `runtime_next_step` persists, and that the byte-identical snapshot oracle exists.
- Verify mypy ran with `--strict` over callers and callees in one invocation.

## Activity Log

> Append entries at the END in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-28T15:00:00Z – system – Prompt created.
- 2026-09-28T16:00:00Z – system – Split: T056/T059 and the next_cmd part of T058/T063 moved to WP19 (T101–T105).

---

### Updating Status

Use `spec-kitty agent tasks move-task WP11 --to <status> --mission owned-checkout-lifecycle-authority-01M3M2ZB` and `spec-kitty agent tasks mark-status T057 … --status done`.
- 2026-09-29T08:34:52Z – claude – shell_pid=8682 – WP11 complete. Commits: 5db5af729 (T058 campsite), cb71f5ffb (T066 campsite), ea6057b67 (T057 red: 5/7 TypeError on owned= at cb71f5ffb via detached scratch worktree), 988990eb9 (T060-T063/T067 fix), e32201737 (mechanical test adaptation), 77d844547 (wip checkpoint), f0139e154 (T061 step 3 red: assert ['persist','resolve'] == ['resolve'] / ['resolve','persist']), 2e11096dd (T061 step 3 fix). TRANSITIONAL(WP18) grep -c: decision.py 0->1, runtime_bridge.py 0->2, next_invocation_lifecycle.py 0->3 (total 6). bridging: WP12 x1 (decision.py build_prompt); grep 'bridging: WP11' src empty. _with_guard_failure_paths left unchanged: guard paths name artifacts read via the repo_root the caller passes; no owned artifact path is reported there. mypy --strict over 12 files: 24 errors on lane base bb67d7982 and on head, identical error set (0 new). test_layer_rules.py 74 passed, runtime->specify_cli ledger unchanged (subpackage set unchanged). Out-of-map edits: 17 pre-existing test files under tests/next, tests/runtime, tests/specify_cli/next (mechanical owned=/3-tuple/patch-target adaptation). Known unrelated red: tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported lists only symbols in files WP11 did not touch (OwnedCheckoutPathRefused, _owned_checkout helpers, OwnedMission).
- 2026-09-29T10:40:40Z – claude – Fix cycle 1 (review-cycle-1.md). Commits: 72add9106/d1ac571f6/a15984c02 red tests; 60c39fdd8 engine plan/commit split (plan_advance, apply_result; engine.py declared out-of-map, formatter-excluded); 47da41819 ctx.owned populated + resolve-before-persist on BOTH advance paths via ONE _resolve_planned_wp_workspace + DecisionGitLog anchored at P + WP04 ActionContextError mapped + owned run identity/adoption; 0b5eb16e3 lifecycle legacy arms mint once + P store + owned guard paths + bridging marker on call line; 50991c2a1 real-engine tests; d5d5ad2b0 O8 per-seam tests; 8c8e75bae composition commit back in _dn_composition_dispatch (emitter-seam gate) + identity via PRIMARY seam (FR-007 identity gate). RED PROOFS at 60c39fdd8 (scratch worktree, tests copied in): 14 failed = walk (ValueError WP01 not found under R), resolution-failure DID NOT RAISE, composition seams owned is None, FR-007 stale copy (RunIdentityMigrationRequired via R identity), DecisionGitLog anchor R!=P, WP04 mapping, run identity x2, guard paths, bridging marker, lifecycle store+legacy mint x4; 13 passed (controls, O8, pin, real-engine ordering tests). T057 step-3 pin red on pre-WP11 base bb67d7982: TypeError _state_to_action() unexpected keyword 'owned'. MUTATION (scratch worktree, all killed): M1 preview plans with 'failed'; M2 reuse pre-resolution without step_id equality; M3 apply_result->identity; M4 preview disabled; M5 resolver never resolves ahead; M6 plan_advance drops significance LOW re-plan; M7 worktree-list probe swallows non-zero (first SURVIVED on the removed-worktree fixture because worktree add raised the same typed error - fixed with a never-materialized fixture + per-seam injections, then killed); M8 worktree-add swallows non-zero; M9 bootstrap does not map the typed refusal. TESTS (targeted files): tests/next/ + 11 tests/runtime files + 3 tests/specify_cli/next + 7 CLI/integration next files = 1111 passed 1 skipped; earlier batch 1069 passed; test_owned_next_runtime + architectural gates + layer_rules 232 passed 1 failed (test_no_dead_symbols: OwnedCheckoutPathRefused, _owned_checkout helpers, OwnedMission - files WP11 never touched, baseline red). mypy --strict 13 files: 24 errors base bb67d7982, 24 head, identical set. ruff clean; runtime->specify_cli ledger unchanged (test_layer_rules 74 passed). MARKERS: TRANSITIONAL(WP18) 6 (decision.py 1, runtime_bridge.py 2, next_invocation_lifecycle.py 3); bridging: WP12 x1 on the build_prompt( call line; bridging: WP11 none. Notes: composition advance keeps its pre-existing no-significance planning (adapter-owned); _merged_mission_short_circuit/committed_authority and prompt_builder still read R for an owned mission (out of map: committed_authority.py, runtime_bridge_identity.py, prompt_builder.py=WP12); the walk asserts prompt-only blocks as WP12's boundary.
- 2026-09-29T12:07:41Z – unknown – Cycle 2 fixes: (1) merged short-circuit anchored on owned P (committed_authority.py out-of-map edit; primary_surface_dir); (2) one strict unbound-run predicate shared by guard+adoption; (3) engine commit_advance + StaleAdvancePlan, legacy path plans once; (4) adapter fallback dropped (plan required, WP plan without wp_resolution refused pre-write). Red-first commits 4692a1641, 930e21bb3; fixes 1d931a23e, 238c595a7. Mutations M1-M5 (loose predicate, R-reading short-circuit, no staleness guard, re-plan, adapter fallback) each killed. 2183 passed in targeted run, ruff clean, mypy 24=24 on 14 files, markers 6.
