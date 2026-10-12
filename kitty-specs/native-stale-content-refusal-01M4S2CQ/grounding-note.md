# Mission grounding note — `native-stale-content-refusal` (issue #5879)

> Pre-spec grounding for a governed Spec Kitty mission. Folds two read-only
> investigation squads (code-grounding `paula-patterns`; tickets-discovery
> `planner-priti`) plus orchestrator verification. Committed before any implementation.
> Date: 2026-10-12. Mission branch: `issue-5879-native-stale-content-refusal`.

## 1. Problem (from #5879 + ADR `2026-10-07-2`)

For an **API-authored** Mission, PR #5851 added a marker-gated stale/unfinished-content
refusal (`validate_stage`) that today runs **only** on the orchestrator-api path
(`orchestrator_api/runtime_next.py::_completion_gate` and the `finalization_scope` on the
api `tasks` verb). Native completion paths skip it, so an API-authored Mission can still be
completed with stale/dirty/unfinished content via:
- `spec-kitty next --result success`
- the `agent` lifecycle completion commands (`agent mission finalize-tasks`, `agent tasks finalize-tasks`).

ADR `2026-10-07-2` records two residuals: (1) native paths do not run `validate_stage`;
(2) `authoring_lock` is cooperative and native status writes / native finalize-tasks do not
take it, so `require_unfinalized` can race a native finalize.

Operator directive on the issue (2026-10-08): *"Both completion surfaces must enforce the same
marker-gated `validate_stage` before GA … the `next` completion path goes through the runtime
bridge composition advance, which #5844 changed (it now commits through the engine's
`plan_advance`/`commit_advance`). Build on that seam."*

## 2. Tickets-discovery squad (planner-priti) — VERDICT: GREEN, no STOP

- **No open issue or PR owns this.** #5879 is open, assigned to stijn-dejongh, milestone
  "4.0.0 release scope", P2. No PR on the mission branch; branch is 404 (never pushed). No open
  PR mentions validate_stage/authoring_lock/native-completion enforcement. The `authoring_lock`
  race has no separate issue/PR anywhere reachable — #5879 is its only home.
- **Epic #5231 children** (#2340, #3859, #3860, #5156) are all orchestrator-api-surface concerns
  (refactor hygiene, flag unification, new verbs, error-envelope fidelity) — **none overlap**
  native-completion enforcement. #5879 is the opposite direction (porting an api-only refusal
  *onto* the native path).
- **#5851 deferred list** confirms #5879 is THE sole native-enforcement follow-up. Sibling
  deferred items #5532/#5631 (Status **Read** API/port), #5735 (shared **implement** service),
  #5776 (status read-contract slice) are all **read/implement path** — respect the read/write
  seam split: our refusal belongs on the **completion/write** path, never the status read port.
- **Merge-coordination risk (ownership-separate, likely conflict zone):** open PR **#5907**
  (`[#3546]`, edits `runtime_bridge_cores.py`, `runtime_bridge_guards.py`, `mission_finalize*`)
  and **#5945** (`[#2642]`, runtime-bridge outline/finalize guards + `tasks.md` finalize gate).
  Keep our diff small and rebase late.
- **Caveat:** the GitHub search endpoint is blocked for this session (repo-scoped endpoints only),
  so a keyword-only sibling buried in closed issues cannot be 100% ruled out; confidence on the
  "nothing open owns this" verdict is nonetheless high (repo-scoped cross-refs + open-PR scan).

## 3. Code-grounding squad (paula-patterns) + orchestrator verification

### Native completion surfaces
- **`spec-kitty next --result success`**: `next_cmd.py::next_step` (L243) → `_dispatch_advancing_mode`
  (L380) → `decide_next(...)` (L404) → `runtime/next/decision.py::decide_next` → `runtime_bridge.py::
  decide_next_via_runtime` → engine `_internal_runtime/engine.py::next_step` (L596) → `plan_advance`
  then `_commit_advance` (L628-630) where completion lands (`_record_step_completed`, `_write_snapshot`
  of the new `issued_step_id`). **No `validate_stage`/`authoring_lock`/`api_authoring_enabled` anywhere
  on this path.** VERIFIED.
- **The orchestrator-api `next` verb re-uses this exact entry**: `runtime_next.py::_run_native` (L35)
  imports `next_cmd.next_step` and calls it in-process (L42), wrapped by `_completion_gate` (L48-73).
  The api path's native leg **is** `next_cmd.next_step`; the gate is bolted on *above* it in the api
  layer only. VERIFIED.
- **`agent … finalize-tasks`** (two commands): `agent mission finalize-tasks` → `mission_finalize.py`;
  `agent tasks finalize-tasks` → `tasks_finalize.py::_do_finalize_tasks`. These write status **directly**
  (`_ft_emit_status_events` → `bootstrap_canonical_state` seeds genesis→planned + writes `lanes.json`),
  flipping `tasks_are_finalized` true, with **no** `validate_stage`, **no** `authoring_lock`, **no**
  marker check. They do **not** traverse `next_step`. The api `tasks` verb DOES guard the same
  `finalize_tasks` via `finalization_scope` (`design_phase.py` L365 — takes `authoring_lock` +
  `validate_stage("tasks")`).

### THE SHARED SEAM (reconciling the operator hint with the layer boundary)
- **For the `next` surface: `specify_cli/cli/commands/next_cmd.py::next_step`.** It is the one function
  reached by BOTH native `next --result success` AND the orchestrator-api `next` verb (api calls it
  in-process). It lives in the TOP layer (`specify_cli.cli.commands`), so it may freely import
  `specify_cli.design.validation.validate_stage`, `specify_cli.design.receipts.authoring_lock` /
  `api_authoring_enabled`, and `runtime.next.runtime_bridge_query.issued_step_id_for_mission`.
- **The runtime-bridge composition-advance (the operator's literal "build on that seam") is
  layer-DISQUALIFIED for hosting the design-layer check.** VERIFIED against
  `tests/architectural/test_layer_rules.py`: `_RUNTIME_ALLOWED_SPECIFY_CLI` (L178-203) does **not**
  contain `design`; `specify_cli.cli`/`specify_cli.next` are hard-forbidden in the runtime layer by
  `TestRuntimeBoundary` (comment L172-175) and the ledger is shrink-only (growth fails
  `test_ratchet_baselines.py` + `_baselines.yaml`). Importing `specify_cli.design` validators into
  `src/runtime/` would red the gate. `issued_step_id_for_mission` is already runtime-local
  (`runtime_bridge_query.py` L294), so only the three `specify_cli.design` symbols are the blocker —
  and they are fatal for the bridge option.
- **Reconciliation:** placing the read-only gate at the top of `next_step`'s advancing (`--result success`)
  path — *before* `decide_next` applies completion (before L404) — functionally guards the same
  composition-advance seam the operator named (completion cannot proceed if `validate_stage` raises),
  from the only layer that is allowed to import the design validators. This honours the operator's
  intent ("both surfaces enforce the same marker-gated check before GA") while respecting the
  architectural boundary the operator's hint did not account for. **This divergence from the literal
  hint will be called out explicitly in the spec and PR body.**
- **`finalize-tasks` is NOT covered by `next_step`** — it is a disjoint native path. It needs its own
  co-located enforcement: wrap the native finalize body in `finalization_scope` (authoring_lock +
  `validate_stage("tasks")` + success-gated receipt re-stamp), exactly mirroring the api `tasks` verb.
  The deeper common status-pipeline seam (`bootstrap_canonical_state`) is too broad (fires on every
  status write, not just completion) — enforcing the marker gate there would over-reach; NOT recommended.

### Invariants to preserve (enforcing location)
- `validate_stage` stays **read-only** (`validation.py` L177-194, returns `validation_only: True`;
  pinned by `test_design_authoring.py::test_submit_commits_content_and_validate_is_read_only`).
- **API path must not be double-enforced/double-locked.** Moving the gate into `next_step` means the
  api `_completion_gate` (`runtime_next.py` L48-73) becomes redundant → must be removed/neutered
  (single canonical authority; also avoids leaving dead private symbols for the dead-symbol gate).
  `authoring_lock` is `reentrant=True` (`receipts.py` L90) so no deadlock, but double work + dead code.
- **Non-API-authored (no-marker) missions keep byte-identical native behavior** — gate only fires when
  `api_authoring_enabled(root, slug)` (marker `.enabled` exists; `receipts.py` L56).
- **Single-JSON-document stdout** (`runtime_next.py::_decode` L21-32) — a `DesignError` raised inside
  `next_step` must surface as the structured JSON error envelope / `_fail`, not stray stdout text
  (native notices already go to stderr).
- **Exit-code + reason mapping**: a native refusal must land so the api still classifies it
  `RUNTIME_NEXT_FAILED` with `data.reason == DesignError.code` (journey test asserts
  `reason == "DESIGN_PREREQUISITES_FAILED"`). Native CLI should exit non-zero with the structured error.
- **Parallel-authority / canonical-source (CLAUDE.md)**: the native persisted `issued_step_id` is the
  authority (never a caller-supplied stage); `validate_stage` remains a prerequisite proof, never an
  alternate completion; the status event log stays the sole status authority — the design seam must not
  become a second status writer.

### The `authoring_lock` / `require_unfinalized` race (residual #2)
- Root cause: native finalize-tasks flips `tasks_are_finalized` **without taking `authoring_lock`**;
  the api `plan` verb's `require_unfinalized` read (`design_phase.py` L272-274) is also outside any lock.
  So a native finalize can race an in-flight api `plan` edit that already read `finalized == False`.
- **In-scope by consequence:** WP-B (wrapping native finalize-tasks in `finalization_scope`) makes the
  native finalize cooperatively take `authoring_lock` — closing the *writer-takes-no-lock* half of the
  race, which is the half #5879 names ("Native status writes and `finalize-tasks` do not take it").
- **Residual after WP-B:** pulling the api `plan`'s `require_unfinalized` read under the lock is an
  api-path change; non-goal says "don't change the api-path behavior." Treat as a tracked follow-up
  noted in the PR body unless it proves behavior-preserving and trivial. Native `move-task`/status
  writes taking the lock is likewise out of this mission's completion-focused scope → follow-up note.

### Tests that pin this surface (targeted blast radius)
- Red-first home: `tests/specify_cli/orchestrator_api/test_planning_client_journey.py` — build an
  API-authored mission exactly as `test_public_next_completes_real_design_actions` (L253) does
  (so `.enabled` marker + receipts exist), then drive the **native** CLI app (`specify_cli.cli` /
  `next_cmd.next_step`) `next --result success` at a stale/dirty stage → assert refusal
  (`DESIGN_PREREQUISITES_FAILED` / `DESIGN_FINALIZED`). Today native passes → RED. Sibling case for
  native `agent … finalize-tasks` on an API-authored mission with stale parents.
- Must stay green / update: `tests/specify_cli/orchestrator_api/test_runtime_next.py` (patches
  `next_cmd.next_step`; reflects the gate relocation), `test_design_authoring.py` (unit home for
  validate_stage/require_unfinalized/receipts — add read-only + marker-gate assertions),
  `test_specify_plan_tasks_verbs.py`, `test_design_status.py`, `tests/contract/test_orchestrator_api.py`.
- Native next CLI: `tests/specify_cli/cli/commands/test_next_*` ; native finalize:
  `tests/cli/test_tasks_finalize_lanes_minting.py`, `tests/agent/test_finalize_tasks_owned_files_validation.py`,
  `tests/agent/test_agent_feature.py`, `tests/agent/test_commands.py`.
- Architectural gates implicated (run the SPECIFIC files, never the bare dir):
  `tests/architectural/test_layer_rules.py` (decisive — confirms seam placement),
  `test_ratchet_baselines.py`, dead-symbol gates (`test_no_dead_symbols.py`,
  `dead_symbol_allowlist.yaml`) if `_completion_gate` is removed,
  `test_no_legacy_terminology.py`, `test_no_retired_subsystems.py`,
  `test_status_events_writes_gate.py` (only if the race fix touches the status-write path).

## 4. Mission scope (ATDD red-first)

- **WP-A — `next` shared gate:** move the marker-gated `validate_stage` into `next_cmd.next_step`
  (advancing `--result success`, under `authoring_lock`, gated by `api_authoring_enabled` +
  `issued_step_id_for_mission` for issued ∈ {specify,plan,tasks}); remove the now-redundant api
  `_completion_gate`; preserve stdout/exit/reason mapping. Covers native + api `next`.
- **WP-B — native finalize gate:** wrap native `agent mission finalize-tasks` and
  `agent tasks finalize-tasks` (when `api_authoring_enabled`) in `finalization_scope`, mirroring the
  api `tasks` verb. Covers the agent-lifecycle surface AND makes native finalize cooperatively take
  `authoring_lock` (closes the named half of the race).
- **Red-first tests** in `test_planning_client_journey.py` (native `next` + native finalize cases),
  RED on `origin/main`, GREEN on the fix; plus unit assertions in `test_design_authoring.py`.
- **NON-GOALS (binding):** no change to orchestrator-api path *behavior* (removing the redundant
  gate is a single-authority refactor, not a behavior change — same refusals/codes); no widening
  beyond the shared-seam enforcement; no suppressions. Remaining api-plan-read-under-lock and native
  move-task lock adoption → follow-up note, not folded.

## 5. Risks / watch-items
- Root resolution inside `next_step`: receipts/marker live in the git common dir; owned-checkout
  native `next` uses a different `repo_root` than the api path's `_get_main_repo_root()`. Resolve the
  gate's root the same way the rest of `next_step` resolves the mission, and pin with tests.
- Rebase late onto `main`; coordinate with open PRs #5907 / #5945 on the finalize/runtime-bridge
  guard surface (ownership-separate, conflict-prone).
