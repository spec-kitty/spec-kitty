---
work_package_id: WP18
title: Single-authority gate closure and end-to-end proof
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
- WP08
- WP09
- WP10
- WP11
- WP12
- WP13
- WP14
- WP15
- WP16
- WP17
- WP19
requirement_refs:
- FR-001
- NFR-001
- NFR-002
- NFR-003
- NFR-005
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T095
- T096
- T097
- T098
- T099
- T100
phase: Phase 5 - Closure
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_owned_checkout_single_authority.py
- tests/integration/test_owned_lifecycle_acceptance_e2e.py
- tests/performance/test_owned_checkout_perf.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_owned_checkout_single_authority.py
- tests/architectural/_baselines.yaml
- tests/integration/test_owned_lifecycle_acceptance_e2e.py
- tests/performance/test_owned_checkout_perf.py
- tests/architectural/test_ratchet_baselines.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP18 – Single-authority gate closure and end-to-end proof

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. The charter (`.kittify/charter/charter.md`) is binding; its "Architectural gate discipline" standing order (DIRECTIVE_043) governs T095–T097.

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
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This is IC-11, the closing WP. It turns the mission's promise into an enforced invariant and proves the lifecycle end to end.

Done means:

1. **Red first (T095).** The **first commit** of this WP adds `tests/architectural/test_owned_checkout_single_authority.py` with the G1–G6 assertions of `contracts/architectural-gate.md`, and they are **red** against the tree as it stands after WP01–WP17 and WP19 (the transitional surfaces still exist). The commit message records the offender count per gate.
2. **Transitional surfaces deleted (T096).** The transitional surfaces are the six shared seams plus every other function marked TRANSITIONAL(WP18). T096 deletes **exactly** everything `grep -rn "TRANSITIONAL(WP18)" src tests` finds: the legacy `effective_root=` keyword on the six shared seams, `effective_root_kwargs` / `_EffectiveRootKwargs`, the `OwnedMission` legacy factory function, `OwnedCheckout`'s transitional legacy properties, their pinning tests, and any other marked parameter or field a WP kept. Each deletion is declared as an out-of-map closure edit with a one-line rationale. T097 asserts the grep is empty.
3. **Green (T097, FR-001 / SC-004).** Every G1–G6 assertion passes with an **empty** allowlist; `grep -rn "TRANSITIONAL(WP18)" src tests` is empty (asserted by a test); `tests/architectural/_baselines.yaml` carries the section `test_owned_checkout_single_authority: {owned_root_bare_path_params: 0}`, and the ratchet meta-test (`tests/architectural/test_ratchet_baselines.py`, owned here) enforces it.
4. **End to end (T098, SC-001 / SC-003 / NFR-001).** `tests/integration/test_owned_lifecycle_acceptance_e2e.py` walks the `quickstart.md` flow through the real CLI (create → spec-commit → setup-plan → status → finalize → `next` to implement WP01 → move-task claimed → in_progress → for_review → `next` review prompt → context resolve), for cwd ∈ {repository root checkout R, owned checkout P, an unrelated directory}, with and without a stale copy of the mission in R, with 0 errors and 0 R-snapshot differences.
5. **Measurements (T099).** NFR-002 exactly-one validation per owned command (counted at `checkout_ownership.resolve_ownership_claim`) and 0 extra git subprocesses per owned status read, per PR; NFR-003 median-of-5 latency < 2 s for owned `agent tasks status`, `setup-plan` and `context resolve`, `performance`-marked (nightly).
6. **Closure hygiene (T100, NFR-005).** Terminology guard green, docs freshness green, the targeted gate list green, `make test-fast` green, ruff check/format and `mypy --strict` clean on every file this WP touched. Diff coverage ≥ 90%: the proof is CI's `diff-cover` job ("diff-cover PR gate (>=90% changed critical-path lines)") in `.github/workflows/ci-aggregate.yml`; T100 names it in the PR.
7. **Mission-tip invariants (T100).** `tests/architectural/test_no_dead_symbols.py` is **green at the mission tip** (the transient reds WP01/WP02 named — `OwnedCheckout` until WP02, `resolve_owned_create_root` until WP10, `adopt_owned_checkout` until WP08 — are gone); `grep -rn "# bridging:" src` is **empty**; every `TRANSITIONAL(WP18)` marker deleted was listed in some WP's DoD.
   - **Carry-forward (WP11 cycle-3 review, 2026-09-29):** `test_no_public_symbol_in_all_is_unimported` is red on the lanes and green on origin/main 8d24a5f8f. Flagged `__all__` symbols: `mission_runtime.owned_checkout::OwnedCheckoutPathRefused` (WP01 a1aa1babb), `specify_cli.core.owned_mission::OwnedMission` (WP02 d9487b1ea), and the WP08 `specify_cli.cli.commands._owned_checkout` exports `OWNED_CHECKOUT_HELP`, `STALE_COPY_WARNING`, `UnregisteredOwnedRefusalCode`, `json_error_envelope`, `owned_checkout_option`, `refuse_owned_action`, `result_error_envelope`, `stale_repository_root_copy` (54b87caa1). Re-run on the merged tip. Each symbol still flagged must gain a live importer or leave `__all__`, or be deleted if dead. No allowlist entries.
8. **SC-002 and SC-005 closed (T100).** An O1–O10 index maps each observed defect to its red-first test and WP, and each red commit is verified to precede its fix; and the SC-005 assertion-preservation check shows the existing owned-command, lane-topology, coordination-topology and charter-authoring test files gained only additions plus enumerated re-points.

## Context & Constraints

- **Authoritative contract**: `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/contracts/architectural-gate.md`. Read it in full before T095; this prompt restates it but the contract wins on any difference.
- **Other mission docs**: `spec.md` (FR-001, SC-001, SC-004, NFR-001..NFR-003, NFR-005, C-008), `plan.md` (Staging Strategy — the `TRANSITIONAL(WP18)` convention; "The G1–G6 assertions are committed red as the first commit of the closing WP"; the mypy invocation discipline; the dead-symbol gate judged at the mission tip, here; Test Layout and Markers; IC-11), `research.md` R-03 and R-16 (Gate, R-snapshot, Sizing), `contracts/owned-checkout-carrier.md` (§1 sole construction, §3 no bare owned roots, §7 the consumer list G6 pins), `quickstart.md` (the SC-001 script T098 automates), `data-model.md` (`stale_repository_root_copy` payload field; error-code registry), `occurrence_map.yaml` (note the `tests/architectural/_baselines.yaml` exception: "may only shrink or gain the new gate's zero cap; never loosen").
- **Prerequisite artefacts you build on** (all merged; read them first):
  - WP01 `tests/architectural/_owned_checkout_scan.py` — the AST scanner (reference forms, identifier ban, annotation forms, FQN exemption) — and its green self-mutation tests in `tests/architectural/test_owned_checkout_gate_selftest.py`. **Do not re-implement scanning.** The gate file composes the scanner's functions over `src/`; if a rule the contract needs is missing from the scanner, add it in the scanner as an out-of-map edit with a new self-mutation case in the self-test (rationale: "G<n> needs <rule>; scanner is WP01's single scanning authority").
  - WP02 fixtures in `tests/integration/conftest.py`: `owned_checkouts`, `r_snapshot`, `stale_root_copy` (self-tested in `tests/integration/test_owned_fixtures_selftest.py`). Use them; do not build parallel fixtures.
  - Per-concern acceptance files from WP08–WP13 (`tests/integration/test_owned_lifecycle_acceptance_{context,status,cli,next,review,finalize}.py`). The e2e file chains the steps they test individually; reuse their helpers by importing fixtures through `conftest.py`, never by importing test modules.
  - `tests/architectural/_ast_scan.py` (`parse_file`, `read_and_parse`, `qualname_by_line`) — the parser every gate uses; comments and docstrings never count as offenders.
- **Out-of-map closure edits.** T096/T097 edit files owned by earlier WPs. This is sanctioned by the plan's Staging Strategy and the WP ownership notes ("declared as out-of-map closure edits, each with a one-line rationale"). Every such edit is listed in the commit message and the Activity Log as `<path>: <one-line rationale>`. Keep each edit to the deletion or the re-point it names; no opportunistic refactors in other WPs' files. (`tests/architectural/test_ratchet_baselines.py` is owned by this WP, not out-of-map.)
- **No ledger, no allowlist.** Operator decision `01M3M65D…`: empty allowlists, no ratchet ledger. The only exemptions are the named rules the contract defines, each already pinned by a WP01 self-mutation pair: `ORG_PACK_MODULE_RULE` (the org-pack sense `OrgPackConfig.effective_root`, `src/charter/offering/drg/org_pack_config.py:374`; covering `src/charter/**`, `src/specify_cli/doctrine/**`, `src/specify_cli/cli/commands/_doctrine_collect.py`, `src/specify_cli/analysis_inputs.py`), the `OrgPackConfig.effective_root` method-call rule, the FQN rule for the fields of `mission_runtime.owned_checkout.OwnedCheckout`, `CLI_CLAIM_INPUT_RULE` (parameters annotated `OwnedCheckoutOption`), and `MIGRATIONS_CHECKOUT_ROOT_RULE` (the `checkout_root` name under `src/specify_cli/upgrade/migrations/**`). `charter_runtime/lint/checks/org_layer.py` is **not** exempt: its walrus local is renamed (T097). Adding any other exemption is out of scope and will be rejected.
- **Test policy (`NO_FULL_HEAVY_SUITES_IN_MISSION`)**: run the specific architectural gate files implicated (T100 lists them), never the bare `tests/architectural/` directory; the full sweep is CI's.
- **Terminology (C-008)**: "repository root checkout", "owned checkout", "coordination worktree", "lane worktree", "Mission"; never bare "primary" as a checkout alias, never "feature".

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: assigned in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json` by `spec-kitty agent mission finalize-tasks`. Start with `spec-kitty implement WP18` and use only the workspace path it prints. Every WP01–WP17 and WP19 lane must be merged into your lane base before you start (check `spec-kitty agent tasks status`).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T095 – Commit the G1–G6 gate assertions red (record offender counts)

- **Purpose**: DIRECTIVE_043 architectural-gate discipline and C-007 red-first: the gate must be demonstrably non-vacuous against a real tree before the fix that turns it green. The contract requires the G1–G6 assertions to be the **first commit** of this WP, red.
- **Steps**:
  1. Create `tests/architectural/test_owned_checkout_single_authority.py` with `pytestmark = [pytest.mark.architectural]`, a module docstring naming `contracts/architectural-gate.md`, and one test per gate. Compose WP01's scanner functions; do not parse or walk the AST yourself beyond what the scanner exposes.
  2. **G1** — `resolve_ownership_claim` is referenced only in `src/specify_cli/core/owned_mission.py`, plus its definition in `src/specify_cli/core/checkout_ownership.py` (`:190` on the planning base).
     - Every reference form counts: `ast.alias.name` (including `import … as x`), `Attribute.attr`, `Name.id`, and string `Constant`s used with `getattr` / `importlib`.
     - Planning-base floor: `cli/commands/next_cmd.py:167,170`; `core/mission_creation.py:33,848`.
  3. **G2** — `resolve_owned_mission(` / `adopt_owned_checkout(` are called only from `src/specify_cli/cli/commands/_owned_checkout.py` and `src/specify_cli/core/owned_mission.py`.
     - Planning-base floor: `coordination/status_transition.py:917`, `status/models.py:902`, `status/bootstrap.py:183`, `migration/backfill_runtime_state.py:1441`, `mission_runtime/resolution.py:1514`;
     - and the CLI commands `accept.py:342,732`, `tasks_mark_status.py:180`, `tasks_move_task.py:463`, `spec_commit_cmd.py:110`, `mission_check_prerequisites.py:599`, `mission_finalize.py:202`.
  4. **G3** — `OwnedCheckout._mint` is referenced only in `owned_mission.py`. WP01's self-mutation case covers the rule; here it runs over the real tree.
  5. **G4** — the identifier `effective_root` appears nowhere in `src/` outside the org-pack module rule: not as a parameter, field, local annotation, local binding (including a walrus target), keyword argument, TypedDict key, or string dict key `"effective_root"`. Exactly two exemptions, both WP01 scanner rules:
     - `ORG_PACK_MODULE_RULE`: `src/charter/**`, `src/specify_cli/doctrine/**`, `src/specify_cli/cli/commands/_doctrine_collect.py`, `src/specify_cli/analysis_inputs.py` (the org-pack root `OrgPackConfig.effective_root`, a different concept), with a written reason in the docstring;
     - the `OrgPackConfig.effective_root` method-call rule (`src/charter/offering/drg/org_pack_config.py:374`): an `Attribute` named `effective_root` that is the `func` of a `Call` (the owned sense is never a method). It keeps `charter_runtime/lint/checks/org_layer.py:330`'s call legal; that file's walrus **binding** is still an offender, renamed in T097.
  6. **G5** — no parameter or field carries an owned root as a path under any of `owned_root`, `owned_checkout`, `checkout_root`, `effective_root`, annotated `Path`, `pathlib.Path`, `Path | None`, `Optional[Path]`, `Union[Path, None]`, `os.PathLike`, or the string form of any of these.
     - Exemptions (WP01 scanner rules): the fields of `mission_runtime.owned_checkout.OwnedCheckout`, by fully qualified class name; `CLI_CLAIM_INPUT_RULE` (a parameter annotated with the CLI claim-input alias `OwnedCheckoutOption` or its help-preserving form `owned_checkout_option(help=...)`, which carries the raw, unvalidated `--owned-checkout` input to the minter); `MIGRATIONS_CHECKOUT_ROOT_RULE` (the `checkout_root` name under `src/specify_cli/upgrade/migrations/**`); and `ORG_PACK_MODULE_RULE`.
     - Planning-base floor: `tasks_mark_status.py:114`, `tasks_move_task.py:248`, `mission_creation.py:127`.
  7. **G6** — positive signature pin: each consumer in `contracts/owned-checkout-carrier.md` §7 declares a parameter or field `owned: OwnedCheckout | None`:
     - `mission_runtime.placement_seam`, `mission_runtime.mission_context_for`, `mission_runtime.resolve_action_context` (defined in `src/mission_runtime/resolution.py`);
     - `specify_cli.task_utils.support.locate_work_package`, `specify_cli.workspace.context.resolve_workspace_for_wp`;
     - `specify_cli.coordination.status_service.EventLogReadContract`, `specify_cli.status.models.TransitionRequest`, `runtime.next.runtime_bridge.DecideNextContext`;
     - the prompt-builder entry point in `src/runtime/next/prompt_builder.py` (pin the function WP12 converted; `build_prompt` at `:61` is the public entry on the planning base).

     The review-base helper `claim_commit_for_wp(mission_dir: Path, wp_id: str)` is topology-agnostic and is **not** a G6 consumer (contract §7).
     Check by parsing the defining module, not by importing it, so the gate stays AST-only.
  8. For each gate, assert on the full offender list and print it in the failure message as `path:line kind detail`, so the red commit is self-describing.
  9. Add a non-vacuity floor per gate. The scan floor is exact, not "≥ 1": the set of files G1/G2/G4/G5 scanned **equals** `{p for p in src.rglob("*.py")}` minus the named module-rule exemptions (`ORG_PACK_MODULE_RULE` paths; `MIGRATIONS_CHECKOUT_ROOT_RULE` for the `checkout_root` name only), compared as sets, so an emptied or narrowed scan root can never pass. G6 must find all nine definitions.
  9a. **Planning-base run (non-vacuity against real history).** `git worktree add <scratch> <planning-base-sha>` (the mission's planning base, `claude/sleepy-hamilton-5lelee` at the commit recorded in `meta.json`), copy the gate file and WP01's scanner into the scratch tree, and run the gate there. Record per-gate offender counts and assert they meet the contract's floors (`contracts/architectural-gate.md`: G1 includes `next_cmd.py:170` and `mission_creation.py:848`; G2 includes `status_transition.py:917`; G4 ≈ 400 sites; G5 includes `tasks_mark_status.py:114`, `tasks_move_task.py:248`, `mission_creation.py:127`; G6 red). Paste the counts into the T095 commit body. Remove the scratch worktree afterwards (`git worktree remove`).
  10. Expose the allowlist constant the ratchet reads in T097: `_OWNED_ROOT_BARE_PATH_ALLOWLIST: frozenset[str] = frozenset()`, and make G4/G5 fail on any offender not in it.
  11. Run the file; G1, G2, G4, G5 and G6 must be red, and G3 whatever the tree dictates. Commit **only this file**: `test(arch): owned-checkout single-authority gate G1–G6, committed red (WP18/T095)`, with a body line such as `Offenders at red: G1=<n> G2=<n> G3=<n> G4=<n> G5=<n> G6=<n missing pins>`.
- **Files**:
  - `tests/architectural/test_owned_checkout_single_authority.py` (new).
  - Read-only: `tests/architectural/_owned_checkout_scan.py`, `tests/architectural/test_owned_checkout_gate_selftest.py`, `tests/architectural/_ast_scan.py`.
- **Parallel?**: No; must be the first commit.
- **Validation checklist**:
  - [ ] The commit contains exactly one file, it is red, and the counts are in the message; paste the pytest summary into the Activity Log.
  - [ ] Comments and docstrings containing `effective_root` are not counted (check against `specify_cli/doctrine/snapshot.py:93`).
  - [ ] The org-pack paths are excluded by `ORG_PACK_MODULE_RULE` with a written reason; `org_layer.py` is not excluded.
- **Edge cases**:
  - String annotations (`"Path | None"`) and `from __future__ import annotations` both appear; rely on the scanner's annotation normaliser.
  - TypedDict keys are class-body `AnnAssign`s; `**{"effective_root": x}` splats are `Dict` keys inside a `Call`'s `**` keyword; a walrus binding is a `NamedExpr` target.

### Subtask T096 – Delete exactly everything marked `TRANSITIONAL(WP18)`

- **Purpose**: the plan's temporary scaffolding ends here. The transitional surfaces are the six shared seams plus every other function marked TRANSITIONAL(WP18); every WP marked each one with `# TRANSITIONAL(WP18): <reason>` (plan §Staging Strategy). These deletions are most of what turns G4/G5 green.
- **The inventory is the grep, not this list.** Run `grep -rn "TRANSITIONAL(WP18)" src tests` on your lane base and save the output in the Activity Log. Delete **exactly** what it finds, no more and no less. The items below are the expected contents; if the grep finds a marked surface not listed here, delete it too (and note it); if an item below is not marked, stop and ask the orchestrator rather than guessing.
- **Steps** (each numbered item is one out-of-map closure edit; list each in the commit message as `<path>: <rationale>`; line numbers are planning-base anchors, so re-locate them on your lane base):
  1. **`placement_seam` / `PlacementSeam`** — `src/mission_runtime/resolution.py:2491` (`placement_seam(repo_root, mission_slug, *, effective_root: Path | None = None)`) and the `PlacementSeam.effective_root` field (`:1981`). Delete the legacy keyword and field, and whatever WP04 added to reconcile them with `owned`. Rationale: "closing WP: dual keyword retired per Staging Strategy (WP04-owned)".
  2. **`mission_context_for`** — `resolution.py:1040-1046`. Same deletion, same rationale.
  3. **`resolve_action_context`** — `resolution.py:2507-2517`. Same.
  4. **`resolve_workspace_for_wp`** — `src/specify_cli/workspace/context.py:699`. The legacy keyword was added by WP05 (the planning-base signature has neither keyword). Rationale: "closing WP: dual keyword retired (WP05-owned)".
  5. **`locate_work_package`** — `src/specify_cli/task_utils/support.py`:
     - the legacy keyword at `:563-564`;
     - the `effective_root_kwargs` splat at `:587` and the `if effective_root is not None` at `:594`;
     - the import at `:15`.
     Rationale: "closing WP: dual keyword retired (WP04-owned)".
  6. **`TransitionRequest`** — `src/specify_cli/status/models.py`:
     - `effective_root: Path | None = None` (`:899`);
     - `owned_mission: OwnedMission | None` (`:908`), if WP07 kept it as part of the dual shape;
     - the `TYPE_CHECKING` import at `:24-26`.
     Rationale: "closing WP: dual field retired (WP07-owned)".
  7. **`effective_root_kwargs` / `_EffectiveRootKwargs`** — `src/specify_cli/core/owned_mission.py:41-47`. Rationale: "closing WP: bridging helper retired (WP02-owned)".
  8. **`OwnedMission` legacy factory function** — `src/specify_cli/core/owned_mission.py` (the `TRANSITIONAL(WP18)` factory WP02/T010 left at the former class site) and any re-export, plus its pinning test `tests/core/test_owned_mission_minter.py::test_transitional_factory_mints_the_fact` and `test_effective_root_kwargs_accepts_fact`. Rationale: "closing WP: rename complete, no alias (occurrence_map `code_symbols: rename`)". The unowned tests that still call `OwnedMission(...)` are re-pointed in T097 step 3.
  9. **`OwnedCheckout` transitional legacy properties** (`primary`, `root`, `directory`, `slug`, `target`) — `src/mission_runtime/owned_checkout.py` (WP01/T001), plus their single pinning test `tests/mission_runtime/test_owned_checkout.py::test_legacy_properties_mirror_canonical_fields`. Rationale: "closing WP: legacy attribute names retired (WP01-owned)". If WP01 listed them anywhere in the `mission_runtime` public surface (`_PUBLIC_SURFACE`, `tests/architectural/test_mission_runtime_surface.py`), remove them there too.
  9a. **Every other `TRANSITIONAL(WP18)` hit** — for example a legacy keyword WP07/WP13 kept on a non-seam function for a not-yet-converted caller, and WP11's six legacy `next` entry keywords plus `_transitional_owned_from_legacy` (callerless since WP19). Delete the legacy form and its marker. Rationale: "closing WP: TRANSITIONAL(WP18) surface retired (<owning WP>)".
  9b. **Marker budget check (S5).** Collect every `TRANSITIONAL(WP18)` marker list from the WP prompts' DoD sections (WP01 6, WP02 5, WP04 17, WP05 1, WP07 18, WP11 6, WP13 as amended, all others 0) and compare it with the grep output: **fail** (stop and escalate to the orchestrator) on any marker in the grep that no WP's DoD lists, and on any listed marker the grep does not find. Record the reconciliation table in the Activity Log.
  10. After each deletion, `grep -rn` for the removed name across `src/` **and** `tests/`, and collect the breakages for T097. Do not fix them inside this step, so the deletion commit stays reviewable.
  11. Commit the deletions together: `refactor(owned-checkout): retire every TRANSITIONAL(WP18) surface (WP18/T096)`. The tree may be red between T096 and T097 inside this WP; the WP as a whole ends green.
- **Files** (all out-of-map closure edits):
  - `src/mission_runtime/resolution.py`, `src/mission_runtime/owned_checkout.py`
  - `src/specify_cli/workspace/context.py`, `src/specify_cli/task_utils/support.py`
  - `src/specify_cli/status/models.py`, `src/specify_cli/core/owned_mission.py`
  - the pinning tests `tests/core/test_owned_mission_minter.py`, `tests/mission_runtime/test_owned_checkout.py`
  - every other file the `TRANSITIONAL(WP18)` grep names
- **Parallel?**: No; after T095.
- **Validation checklist**:
  - [ ] `grep -rnw "effective_root_kwargs\|_EffectiveRootKwargs\|OwnedMission" src/` prints nothing.
  - [ ] `grep -rn "TRANSITIONAL(WP18)" src tests` prints nothing except lines inside tests that T097 re-points (record them); T097 makes it fully empty.
  - [ ] `grep -rn "def placement_seam\|def mission_context_for\|def resolve_action_context\|def resolve_workspace_for_wp\|def locate_work_package" -A8 src | grep effective_root` prints nothing.
  - [ ] `tests/architectural/test_mission_runtime_surface.py` passes (MR-1/MR-2 surface unchanged apart from removed transitional names).
  - [ ] `tests/architectural/test_compat_shims.py` passes (no shim left behind).
  - [ ] `tests/architectural/test_layer_rules.py` passes (no new outbound edge).
- **Edge cases**:
  - `src/mission_runtime/resolution.py` is covered by the `mission_runtime` outbound ledger (`_baselines.yaml` `test_layer_rules.mission_runtime_allowed_specify_cli: 10`); deleting code must not add an import.
  - If any deletion leaves a function above complexity 15 (it should only reduce complexity), fix it in place.
  - `tests/architectural/test_no_dead_symbols.py` may flag a helper that only the dual keyword used; delete it rather than allowlisting it.

### Subtask T097 – Sweep leftovers → gate green; TRANSITIONAL grep empty; `_baselines.yaml` section cap 0

- **Purpose**: drive G1–G6 to green with an empty allowlist, keep every test green after the T096 deletions, and pin the zero with the ratchet meta-test.
- **Steps**:
  1. **Source offenders.** Run the gate and fix every remaining offender at its source, converting it to `owned: OwnedCheckout | None` (never by adding an exemption). Expected residue: the bridges earlier WPs logged (search the WP13–WP17 prompt Activity Logs for "bridge"), plus anything the scanner finds that mypy never did. Each fix in another WP's file is an out-of-map closure edit with a rationale line.
  2. **The org-pack local.** Rename the one org-pack **binding** G4 catches on the planning base: `src/specify_cli/charter_runtime/lint/checks/org_layer.py:327-330` binds `effective_root := pack.effective_root(repo_root)` in a comprehension. Rename the local (for example `pack_root`) and leave the method call intact. Rationale: "G4 bans the identifier as a binding; the org-pack method call stays under the symbol rule".
  3. **Tests broken by T096.** Tests are not scanned by G4, but they must stay green. Planning-base test files that use the retired names in the owned sense (27; confirm with `grep -rlnw "effective_root\|effective_root_kwargs\|OwnedMission" tests --include=*.py`):
     - architectural: `tests/architectural/test_git_topology_one_copy.py`, `test_read_surface_placement_guard.py` (`mission_context_for(..., effective_root=repo)` at `:447, 464, 480, 496`), `test_single_mission_surface_resolver.py`;
     - mission_runtime / runtime / next: `tests/mission_runtime/test_builder_fs_free_identity.py`, `test_coord_read_seam_callers.py`, `test_owned_single_branch_ssot.py`, `test_resolution_target_branch.py`, `test_status_surface_dir_deleted_arm.py`; `tests/runtime/test_artifact_presence_placement.py`; `tests/next/test_decision_unit.py`, `test_runtime_bridge_unit.py`;
     - CLI / status / coordination: `tests/agent/test_context_validation_unit.py`; `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py`, `test_tasks_mark_status_recovery.py` (`OwnedMission(...)` fixture), `test_tasks_move_task_pre_review_identity_read.py` (`OwnedMission(...)` at `:182`); `tests/specify_cli/cli/commands/test_next_answer_effective_root.py`, `test_next_owned_commit_guard.py`; `tests/specify_cli/coordination/test_status_transition.py`; `tests/specify_cli/core/test_must_not_flip_anchors.py`; `tests/specify_cli/next/test_next_invocation_lifecycle_seam.py`; `tests/status/test_bootstrap.py`, `test_transition_pipeline.py`;
     - others: `tests/consolidation/test_pr_merge_baseline.py`, `tests/integration/test_explicit_checkout_commands.py`, `tests/migration/test_runtime_feature_dir_threading.py` (`OwnedMission(...)`).
     Most will already have been re-pointed by their owning WPs. Fix only what is still red: re-point to `owned=` with a fact minted by the WP02 test helper, assertions unchanged, one rationale line each.
     **The `OwnedMission(...)` constructions** (six unowned tests; WP02/T010 recorded the full list in its Activity Log): `test_tasks_move_task_pre_review_identity_read.py:182`, `test_tasks_mark_status_recovery.py:41`, `tests/specify_cli/coordination/test_status_transition.py:1206`, `tests/status/test_bootstrap.py:542`, `tests/migration/test_runtime_feature_dir_threading.py:23`, plus any other hit of `grep -rn "OwnedMission(" tests`. Re-point each to a fact minted through the WP02 fixture helper (preferred; `OwnedCheckout._mint(...)` is allowed in tests because G3 scans `src/` only) with **valid** paths, assertions unchanged, one rationale line each: "WP18 deleted the TRANSITIONAL(WP18) `OwnedMission` factory; the test mints the fact". The org-pack-sense test files (`tests/charter/test_pack_context.py`, `tests/doctrine/test_org_pack_*.py`, `tests/specify_cli/doctrine/*`, `tests/specify_cli/cli/commands/test_doctrine_collect.py`) must not change.
  4. **Ratchet leaf.** Add to `tests/architectural/_baselines.yaml`, following its schema (top-level section = gate test-module name, integer leaf, `# justification:` comment):
     ```yaml
     # tests/architectural/test_owned_checkout_single_authority.py — owned-checkout
     # single-authority gate (mission owned-checkout-lifecycle-authority-01M3M2ZB,
     # FR-001/SC-004). Empty by operator decision 01M3M65D: no bare owned-root
     # path parameter or field anywhere in src/; growth is a gate evasion.
     test_owned_checkout_single_authority:
       owned_root_bare_path_params: 0  # justification: empty allowlist by construction; never grows.
     ```
     A top-level scalar is refused by `test_yaml_leaves_refuses_a_scalar_section`, so the section/leaf shape is mandatory.
  5. **Meta-test wiring (owned by this WP).** `tests/architectural/test_ratchet_baselines.py` fails any YAML leaf without a `_SIZE_RATCHETS` row (`test_every_baseline_leaf_is_enforced_by_a_size_ratchet`) and pins the section count (`test_size_ratchet_table_meets_floor`: `assert len(_REQUIRED_TOP_LEVEL_KEYS) == 14`).
     - Add the row `_SizeRatchet("test_owned_checkout_single_authority", "owned_root_bare_path_params", "tests.architectural.test_owned_checkout_single_authority", "_OWNED_ROOT_BARE_PATH_ALLOWLIST")`.
     - Bump the floor assertion to 15 and extend its comment.
     - This WP owns that file (frontmatter `owned_files`); record the rationale "register the new gate's zero cap with the ratchet meta-test, as every `_baselines.yaml` leaf must be" in the commit body.
  5a. **TRANSITIONAL grep is empty.** Add `test_no_transitional_wp18_markers_remain` to `tests/architectural/test_owned_checkout_single_authority.py`: it walks `src/` and `tests/` (text scan, skipping `__pycache__` and this test file's own literal) and asserts no line contains `TRANSITIONAL(WP18)`. Red-first: it belongs to the T095 commit's red set if you add it there, or commit it red before step 3's re-points.
  6. Run the gate and the ratchet meta-test until green. Commit: `fix(owned-checkout): sweep residual owned roots; single-authority gate green (WP18/T097)`.
- **Files**:
  - Owned: `tests/architectural/_baselines.yaml`, `tests/architectural/test_owned_checkout_single_authority.py`, `tests/architectural/test_ratchet_baselines.py`.
  - Out-of-map: `src/specify_cli/charter_runtime/lint/checks/org_layer.py` (walrus local renamed, never exempted), any residual source file from step 1, the still-red test files from step 3 (including the six `OwnedMission(...)` re-points).
- **Parallel?**: No; after T096.
- **Validation checklist**:
  - [ ] `uv run --frozen pytest tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_owned_checkout_gate_selftest.py -q` is green.
  - [ ] `_OWNED_ROOT_BARE_PATH_ALLOWLIST` is empty and the YAML leaf is 0.
  - [ ] `grep -rnw "effective_root" src --include=*.py | grep -v "^src/charter/\|^src/specify_cli/doctrine/\|_doctrine_collect.py\|analysis_inputs.py"` prints only org-pack method calls (`.effective_root(`) and docstrings/comments.
  - [ ] `grep -rn "TRANSITIONAL(WP18)" src tests` prints nothing (and `test_no_transitional_wp18_markers_remain` is green).
  - [ ] Every out-of-map edit appears in the commit message with its rationale.
- **Edge cases**:
  - `occurrence_map.yaml` marks `_baselines.yaml` `manual_review` ("may only shrink or gain the new gate's zero cap; never loosen"); touch no other leaf.
  - `mypy --strict` on the source files you edited is mandatory: `follow_imports = "skip"` means only files named on the command line are fully checked.

### Subtask T098 – SC-001 end-to-end walkthrough test (quickstart), incl. stale copy and cwd matrix

- **Purpose**: SC-001 and NFR-001: using only documented `--owned-checkout` commands, take an owned Mission from create to WP01's review prompt with 0 errors and 0 differences in the repository root checkout, wherever the operator stands.
- **Steps**:
  1. Create `tests/integration/test_owned_lifecycle_acceptance_e2e.py` with `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.
  2. Invoke commands in process with `typer.testing.CliRunner` against the root app: `from specify_cli import app` (exported in `specify_cli.__all__`; confirm it resolves to the assembled Typer, otherwise use the per-command sub-apps the WP08–WP13 acceptance files use). In-process keeps the test on the per-PR path (plan: Test Layout).
  3. Use the WP02 fixtures from `tests/integration/conftest.py`:
     - `owned_checkouts` — R plus a linked worktree P on its own branch;
     - `r_snapshot` — R's working tree including ignored files but excluding exactly P's resolved subtree, R's `HEAD` and index, the shared lock root `<common-dir>/spec-kitty-locks`, and an isolated `SPEC_KITTY_HOME`;
     - `stale_root_copy` — a stale copy of the mission under R.
  4. Script the `quickstart.md` sequence, asserting exit 0 and parsing `--json` output at each step (one helper function per step):
     1. `agent mission create demo --mission-type software-dev --owned-checkout P --target-branch <P's branch> --topology single_branch --json` → capture the mission handle.
     2. Write `spec.md` in P; `spec-commit --owned-checkout P --mission <slug> <spec.md> <meta.json>`.
     3. `agent mission setup-plan --owned-checkout P --mission <slug> --json` → `plan.md` exists and is committed in P.
     4. `agent tasks status --owned-checkout P --mission <slug> --json`.
     5. Write `tasks.md` and one `tasks/WP01-*.md` in P (minimal valid frontmatter; `owned_files` naming a file in P); `agent mission finalize-tasks --owned-checkout P --mission <slug> --json`.
     6. `next --agent claude --owned-checkout P --mission <slug> --result success --json` → decision is implement WP01 with workspace == P.
     7. `agent tasks move-task WP01 --to claimed`, then `--to in_progress`; commit an implementation change in P; then `--to for_review` — each with `--owned-checkout P --mission <slug>`.
     8. `next --agent claude --owned-checkout P --mission <slug> --json` → a review prompt whose base is WP01's claim commit (FR-010: the unique commit whose diff to `status.events.jsonl` introduced the last `to_lane=claimed` event id).
     9. `agent context resolve --owned-checkout P --action implement --mission <slug> --wp-id WP01 --json` → `resolution_kind == "owned_checkout"`, `lane_id is None`, `wp_file` and `workspace_path` under P.
  5. After every step assert that every absolute path in the JSON payload resolves under P (walk the payload for path-like strings) and that `r_snapshot` shows 0 differences.
  6. Parametrise the walk over `cwd ∈ {"R", "P", "elsewhere"}` (`monkeypatch.chdir`) and `stale ∈ {False, True}`:
     - `stale=True`: every payload of the five FR-007 reads (`agent tasks status`, `setup-plan`, `context resolve`, `next`, `finalize-tasks`) carries a non-null top-level `stale_repository_root_copy` whose `path` is under R and whose `mission_id` matches. **`stale_repository_root_copy.path` is the single allowed exception**: every other path in every payload is under P;
     - `stale=False`: the field is `null`.
  7. Tail: `agent action implement --owned-checkout P ...` and `agent action review --owned-checkout P ...` exit ≠ 0 with `error_code == "OWNED_ACTION_UNSUPPORTED"`, and R is unchanged.
  8. Keep helpers small (complexity ≤ 15): one function per quickstart step and a single `_walk(runner, P, slug)` driver that T099 reuses.
- **Files**:
  - `tests/integration/test_owned_lifecycle_acceptance_e2e.py` (new).
  - Read-only: `quickstart.md`, `tests/integration/conftest.py`, the WP08–WP13 acceptance files.
- **Parallel?**: Independent of T095–T097 in code, but it must run green on the post-T097 tree; write it after T097.
- **Validation checklist**:
  - [ ] All 6 parametrisations (3 cwd × 2 stale) pass; record the runtime in the Activity Log. If the file exceeds roughly 60 s, keep `cwd=P, stale=True` per PR and mark the rest `slow` with a rationale.
  - [ ] Non-vacuity is a **committed** test, not a local experiment: `test_walk_detects_seam_ignoring_owned` monkeypatches the placement seam's owned arm to the repository-root path and asserts (`pytest.raises(AssertionError)`) that `_walk` fails its under-P assertion. SC-001's red-first evidence is the per-WP red commits indexed in T100 (the walk itself arrives green, because every fix precedes it).
  - [ ] No `sleep`, no network; `SPEC_KITTY_HOME` is isolated.
- **Edge cases**:
  - R's own lane and coordination worktrees stay inside the snapshot (the fixture excludes exactly P's subtree, never a blanket `.worktrees/`).
  - With cwd "elsewhere", commands must still resolve R from `--owned-checkout`, not from cwd.
  - The claim commit is located by event id (`git log -S<event_id>`); never assume a commit subject.

### Subtask T099 – NFR-002 / NFR-003 measurements (`performance` marker)

- **Purpose**: NFR-002 (exactly 1 ownership validation per owned command; 0 additional per-read git subprocesses for owned status reads versus the non-owned path) is the per-PR proxy. NFR-003 (median of 5 runs < 2 s for owned `agent tasks status`, `setup-plan` and `context resolve`) is the nightly wall-clock check.
- **Steps**:
  1. **NFR-002 validation count (per PR)**, in `tests/integration/test_owned_lifecycle_acceptance_e2e.py`:
     - a fixture wraps the real `specify_cli.core.checkout_ownership.resolve_ownership_claim` with a counter (module-attribute monkeypatch; `owned_mission` imports it lazily inside the validator, so the patch is seen) and delegates to it unchanged;
     - call `specify_cli.workspace.context.clear_workspace_resolution_caches()` before each command;
     - reuse the T098 `_walk` driver with the counter enabled and assert the counter increments by **exactly 1** for every owned command in the walk (0 or ≥ 2 fails, FR-003); run it for `cwd=P, stale=False` only, to keep per-PR cost down.
  2. **NFR-002 subprocess count (per PR)**, same file:
     - wrap `subprocess.run` and `subprocess.Popen` with a counter that records calls whose argv[0] ends in `git`;
     - measure one owned `agent tasks status --json` and one non-owned `agent tasks status --json` on an equivalent mission in a plain repository root checkout;
     - measure the validator's own git probes separately with the same counter around a direct validation;
     - assert `owned - validator_probes - non_owned <= 0` and put all three numbers in the assertion message.
  3. **NFR-003 latency (nightly)**, in `tests/performance/test_owned_checkout_perf.py`:
     - every test is `@pytest.mark.performance` (collected but skipped unless `SPEC_KITTY_RUN_PERFORMANCE=1`, per `tests/conftest.py:325-333`);
     - `tests/performance/` is outside `tests/integration/`, so the WP02 fixtures are not auto-applied: import them explicitly and re-export via `__all__` (pattern: `tests/integration/test_owned_checkout_mark_status.py:13-22`), or build the fixture with the WP02 helpers, module-scoped (R + P + a finalized one-WP owned mission);
     - run each command 5 times through the real entry point, `subprocess.run([sys.executable, "-m", "specify_cli", ...], cwd=P, capture_output=True, text=True, timeout=60)` (mirroring `tests/performance/test_cli_startup_budget_4409.py:285-302`);
     - take the median of the wall-clock times and assert with `tests._perf_helpers.assert_timing_budget(median, 2.0, name="<command> owned median-of-5")`; a non-zero exit counts as `float("inf")` with the stderr tail in `name`.
  4. Keep functional assertions (exit code, payload shape) out of the performance file's timing tests, or duplicate them per PR in the e2e file. `tests/architectural/test_performance_marker_guard.py` and `test_timing_coverage_invariant.py` police the split between timing and functional asserts.
  5. Commit: `test(owned-checkout): NFR-002 counts per PR, NFR-003 latency nightly (WP18/T099)`.
- **Files**:
  - `tests/integration/test_owned_lifecycle_acceptance_e2e.py` (append).
  - `tests/performance/test_owned_checkout_perf.py` (new).
- **Parallel?**: After T098 (it reuses the driver).
- **Validation checklist**:
  - [ ] `SPEC_KITTY_RUN_PERFORMANCE=1 uv run --frozen pytest tests/performance/test_owned_checkout_perf.py -m performance -q` passes locally; record the three medians in the Activity Log.
  - [ ] Without the env var the performance tests are collected and skipped, not errored.
  - [ ] Non-vacuity is **committed**: `test_count_detects_double_validation` (patches the CLI helper to validate twice) and `test_count_detects_bypass` (patches it to skip validation) assert that the count check fails in each case.
  - [ ] `tests/architectural/test_performance_marker_guard.py` and `tests/architectural/test_timing_coverage_invariant.py` pass.
- **Edge cases**:
  - The first run of a command in a fresh interpreter pays import cost; the median of 5 absorbs it. Do not add excluded warm-up runs.
  - Workspace-resolution caches are process-global: clear them between in-process counted commands, or the counts drop to 0 on reuse.
  - Git calls made by the test's own fixture setup must happen before the counter is installed.

### Subtask T100 – Terminology guard, docs freshness, final targeted validation

- **Purpose**: close the mission's quality gates (NFR-005) on exactly the files and gates this mission implicates, without running whole heavy suites locally.
- **Steps**:
  1. Terminology: `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`. Then grep this WP's new files and every out-of-map edit for "feature" and bare "primary" used as a checkout alias; fix prose (C-008). The guard does not check Mission vs feature, so the grep is the check.
  2. Docs freshness: `uv run --frozen pytest tests/docs/test_check_docs_freshness.py tests/docs/test_docs_freshness_invariant.py tests/docs/test_docs_index_freshness.py tests/docs/test_check_cli_reference_freshness.py -q`. The new `--owned-checkout` flags (WP08/WP09) change CLI help; if the CLI reference is stale, regenerate it with `scripts/docs/build_cli_reference.py` and name the regenerated file in the Activity Log (out-of-map, generated artefact).
  3. Specific architectural gates implicated by this mission (run these files, not the directory):
     ```bash
     uv run --frozen pytest -q \
       tests/architectural/test_owned_checkout_single_authority.py \
       tests/architectural/test_owned_checkout_gate_selftest.py \
       tests/architectural/test_ratchet_baselines.py \
       tests/architectural/test_mission_runtime_surface.py \
       tests/architectural/test_layer_rules.py \
       tests/architectural/test_compat_shims.py \
       tests/architectural/test_no_dead_symbols.py \
       tests/architectural/test_read_surface_placement_guard.py \
       tests/architectural/test_single_mission_surface_resolver.py \
       tests/architectural/test_lifted_cli_accept_coord_surface_anchor.py \
       tests/architectural/test_cli_error_surface_seam.py \
       tests/architectural/test_performance_marker_guard.py \
       tests/architectural/test_timing_coverage_invariant.py \
       tests/architectural/test_fast_tier_marker_completeness.py \
       tests/architectural/test_marker_job_completeness.py \
       tests/architectural/test_no_legacy_terminology.py \
       tests/architectural/test_ruff_format_enforcement.py
     ```
  4. Mission acceptance files end to end: `uv run --frozen pytest tests/integration/test_owned_lifecycle_acceptance_*.py tests/integration/test_owned_fixtures_selftest.py -q`.
  5. Baseline: `make test-fast`.
  6. Quality on everything this WP touched (new files + every out-of-map file):
     ```bash
     uv run --frozen ruff check <touched files>
     uv run --frozen ruff format --check <touched files>
     uv run --frozen mypy --strict <touched src files> tests/architectural/test_owned_checkout_single_authority.py \
       tests/integration/test_owned_lifecycle_acceptance_e2e.py tests/performance/test_owned_checkout_perf.py
     ```
     Pass the source files you edited in T096/T097 to mypy **together** (the `specify_cli.*` `follow_imports = "skip"` override hides cross-module errors otherwise).
  6a. **Mission-tip invariants.** `uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -q` is green (S3); `grep -rn "# bridging:" src` prints nothing (S4); the T096 marker-budget reconciliation shows no unlisted marker (S5).
  6b. **NFR-005 diff coverage.** The proof is CI's `diff-cover` job in `.github/workflows/ci-aggregate.yml` (job name "diff-cover PR gate (>=90% changed critical-path lines)", `--fail-under=90`). Name that job and its result in the PR's *Tests run* section. A local run is advisory only.
  6c. **SC-005 assertion preservation.** For the SC-005 file list (the existing owned-command tests: `tests/integration/test_explicit_checkout_commands.py`, `tests/integration/test_owned_checkout_mark_status.py`, `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py`; the lane- and coordination-topology `next` tests under `tests/next/`; and the charter-authoring suites `tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py`, `test_activate_recompile_4785.py`, `test_synthesize_freshgate_4785.py`), run `git diff <planning-base-sha> -- <list>` and assert: the diff contains only added lines plus the enumerated re-points (the `owned=` call-shape adaptations recorded by WP16/WP18/WP19 and the WP12 review-test rewrite), and **no** removed or modified line containing `assert`. Implement it as a short script in the Activity Log (grep the diff for `^-.*assert`) and record its output.
  6d. **SC-002 index.** Add this table to the PR description, filling the red-commit SHA and verifying each red commit precedes its fix in `git log`:

     | Defect | Red-first test | WP |
     |---|---|---|
     | O1 | `test_owned_lifecycle_acceptance_status.py` (O1 rows) | WP09 |
     | O2 | `test_owned_lifecycle_acceptance_status.py` (O2 rows) | WP09 |
     | O3 | `test_owned_lifecycle_acceptance_context.py` (O3); `tests/mission_runtime/test_resolution_owned.py` | WP08, WP04 |
     | O4 | `test_owned_lifecycle_acceptance_context.py` (O4); `test_resolution_owned.py::test_stale_root_copy_never_wins_wp_file` | WP08, WP04 |
     | O5 | `tests/integration/test_owned_next_runtime.py` (O5); `test_owned_lifecycle_acceptance_next.py` (O5) | WP11, WP19 |
     | O6 | `test_owned_lifecycle_acceptance_finalize.py`; `test_finalize_atomicity.py` | WP13 |
     | O7 | `tests/core/test_mission_creation_owned_charter.py` (carried a37e9ee39, marker, mission-type-context rows) | WP10 |
     | O8 | `tests/integration/test_owned_next_runtime.py` (both injections) | WP11 |
     | O9 | `test_owned_lifecycle_acceptance_next.py` (O9) | WP19 |
     | O10 | `test_owned_lifecycle_acceptance_context.py` (O10) | WP08 |
  7. Occurrence-map compliance check: `grep -rnw "OwnedMission" src/ tests/ docs/context docs/adr/3.x` → only historical mentions allowed by `occurrence_map.yaml` exceptions (`kitty-specs/**`, `docs/adr/2.x/**`, `CHANGELOG.md`) and the WP03 ADR amendments' explicit "formerly `OwnedMission`" notes. Record the result.
  8. Record every command with pass/fail counts in the Activity Log for the PR's *Tests run* section. Any red that is also red on the planning base is baseline red: classify per CLAUDE.md, file an issue if new (Pre-existing Failure Reporting Rule), do not fix here.
- **Files**: no new files; possibly a regenerated CLI reference (out-of-map, generated).
- **Parallel?**: No; last.
- **Validation checklist**:
  - [ ] All commands above green (or baseline red, classified with an issue link).
  - [ ] Activity Log carries the command list and counts.
- **Edge cases**: `tests/architectural/test_marker_job_completeness.py` and `test_fast_tier_marker_completeness.py` require every new test file to carry a tier marker the CI jobs select; the three new files use `architectural`, `integration`+`git_repo`, and `performance`, which are all registered in `pytest.ini`.

## Test Strategy

- New tests: the gate (`architectural`), the e2e walkthrough plus NFR-002 counts (`integration`, `git_repo`, per PR), NFR-003 latency (`performance`, nightly).
- Commands (summary; the full list is in T100):

```bash
uv run --frozen pytest tests/architectural/test_owned_checkout_single_authority.py -q          # red at T095, green at T097
uv run --frozen pytest tests/architectural/test_ratchet_baselines.py tests/architectural/test_owned_checkout_gate_selftest.py -q
uv run --frozen pytest tests/integration/test_owned_lifecycle_acceptance_e2e.py -q
SPEC_KITTY_RUN_PERFORMANCE=1 uv run --frozen pytest tests/performance/test_owned_checkout_perf.py -m performance -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check <touched>
uv run --frozen mypy --strict <touched typed files, in one invocation>
```

Record exact commands and pass/fail counts in the Activity Log and the PR's *Tests run* section. A mypy failure fails the WP even when pytest is green.

## Risks & Mitigations

- **Vacuous gate.** A scanner that silently scans nothing passes everything. Mitigation: per-gate non-vacuity floor (T095 step 3) plus WP01's self-mutation tests.
- **Exemption creep.** Pressure to "just allowlist" a hard site. Mitigation: empty allowlist by operator decision; the ratchet leaf is 0; reviewers reject any new exemption.
- **Wide out-of-map blast radius.** T096/T097 touch files owned by WP01, WP02, WP04, WP05, WP07 and possibly others, and ~27 test files. Mitigation: one rationale line per edit; deletions only; targeted tests per touched module; the gate plus the e2e walk as the end-state oracle.
- **Ratchet meta-test coupling.** Adding a `_baselines.yaml` leaf without a `_SIZE_RATCHETS` row reds `test_ratchet_baselines.py`. Mitigation: T097 step 5.
- **Slow e2e.** Mitigation: in-process CliRunner; the cwd×stale matrix trimmed to one per-PR case plus `slow` if it exceeds budget (T098 checklist).

## Review Guidance

- Verify the commit order: T095's gate file alone, red, with offender counts in the message; then the deletions and sweep; then the e2e and perf files.
- Re-run `tests/architectural/test_owned_checkout_single_authority.py` and `test_ratchet_baselines.py`; both green, allowlist empty, YAML leaf 0.
- Check each out-of-map edit is listed with a one-line rationale and is a deletion or a re-point, nothing more.
- Check G4's org-pack exemption is by symbol/module rule as the contract says, and that the walrus local in `org_layer.py` was renamed rather than exempted.
- Run the e2e test yourself for `cwd=P, stale=True` and inspect that `stale_repository_root_copy` is present and no path lands under R.
- Confirm the implementer ran mypy across all touched source files in one invocation and it passed.

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
- 2026-09-29T23:36:43Z – claude – shell_pid=7254 – WP18 closing WP - implementation record (profile python-pedro; governance context: charter implement action).
COMMITS: 9dbc03f5c T095 gate G1-G6 red | d19cc7c4d T096 retire TRANSITIONAL(WP18) | a796c4eb4 T097 sweep, gate green | cb51696b8 T098/T099 e2e + perf | 868663bb5 prose sweep.
RED RUN (T095, lane-q tip): 4 failed, 4 passed - G2=2 (runtime_bridge.py:1640, status_transition.py:933), G4=205, G5=55, TRANSITIONAL(WP18) markers=55 lines; G1=0, G3=0, G6=0 already green (WP04-WP19 converted them). Planning-base non-vacuity run (git worktree add --detach 5e6820d19, removed after): G1=4, G2=8, G3=0, G4=431, G5=109, G6=9/9 missing, all contract floors met.
MARKER RECONCILIATION (grep found 55 lines): WP01 6 (owned_checkout.py x5 + test_owned_checkout.py), WP02 5 (owned_mission.py x3 + minter tests x2), WP04 17 (resolution.py x16 + task_utils/support.py), WP05 1 (workspace/context.py), WP07 18 (agent_tasks_ports 2, status_transition 4, commit_router 3, write_seam 2, bootstrap 2, transition_pipeline 1, models 3, emit 1), WP11 6 (decision 1, runtime_bridge 2, next_invocation_lifecycle 3) = 53; WP13 0; plus 2 prose mentions that are not markers (_owned_checkout.py docstring, test_decision_unit.py docstring). No unlisted marker; no listed marker missing.
OUT-OF-MAP EDITS: see the T096/T097/T098 commit bodies (one rationale per path). Beyond the prompt's list: deletion of the unmarked dual-shape predicate checkout_root_agrees_with_effective_root and its export + tests, tests/specify_cli/coordination/test_write_seam_owned_agreement.py (pinned only that predicate), scanner CARRIER_FIELD_RULE extension for OwnedCheckout._mint (+4 self-mutation cases), internal claim-input params renamed owned_checkout->owned_claim (G5), __all__ trims (dead-symbol gate), test_no_dead_symbols append_lifecycle_event hash re-pin (WP09 body edit; no new entry), pyproject [tool.ruff.format].exclude -24 already-formatted entries (ratchet was red on lane base, green on origin/main), test_wp03_advance_to_approval stand-ins (red on lane base).
GATE + ACCEPTANCE RUNS: see hand-back.

## Carry-forward from WP17 (2026-09-29)
- `src/specify_cli/status/transition_pipeline.py::_bare_root_subtasks_dir` carries the one `# bridging: WP18 converts` marker (placement_seam `effective_root=` for bare-root-only requests, WP07 MEDIUM-6). Delete it together with the `effective_root` parameter on `_default_resolve_subtasks_dir` when the seam's dual keyword goes.
- `_flip_phase` keeps a conditional `**({"owned": owned} if owned is not None else {})` splat into `_resolve_primary_home_or_degrade` because the birth-cutover suites stub it with a one-argument lambda; re-point those stubs and make it a plain `owned=` keyword.
- `tests/consolidation/test_pr_merge_baseline.py` mints its fact via the transitional `OwnedMission(...)` factory; re-point that construction under T097 when the factory is deleted.
- WP19 cycle-3 LOW: rename `tests/next/test_runtime_bridge_unit.py::TestMissionRoutesThroughCoordinationOwnedCheckout::test_owned_checkout_reads_topology_via_mission_context_for` — it now asserts `mission_context_for` is NOT consulted.
- WP12 cycle-2 LOW: `src/mission_runtime/claim_commit.py:91-106,127` ancestry check is unreachable except under a race (`git log -S<id> HEAD` already yields ancestors of HEAD). Either document it as a race guard in the docstring or remove it with its 3 mocked tests; do not leave it unexplained.
