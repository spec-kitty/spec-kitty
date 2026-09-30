# Implementation Plan: Owned-checkout lifecycle authority

**Branch**: `claude/sleepy-hamilton-5lelee` (planning/base = merge target) | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/spec.md`

The planning questions were answered through Decision Moments: specify decisions `01M3M2ZX…`, `01M3M300…`, `01M3M4GM…`, `01M3M4GT…` and `01M3M4GZ…`; plan decisions `01M3M65D…` and `01M3M65K…`. Evidence is in [research.md](research.md) and [research/pre-spec-options-memo.md](research/pre-spec-options-memo.md).

## Summary

An owned mission's lifecycle reads fall back to the repository root checkout. Three things cause this:
- a file-placement seam with no owned arm;
- three competing ownership authorities;
- 92 bare `effective_root: Path` parameters that every reader must remember to thread.

**Approach (operator-locked):**
- Introduce one validated ownership fact, `mission_runtime.OwnedCheckout`. It is minted only by `specify_cli.core.owned_mission`.
- Every owned read consumes the fact: the placement seam, WP and workspace resolution, the status surface, the `next` runtime, prompts, the review base, and CLI entry points.
- Convert all 92 bare-path parameters in this mission.
- Delete `OwnedMission` and `effective_root_kwargs`, with no alias left at the end of the mission (every transitional surface is marked `# TRANSITIONAL(WP18)` and deleted by the closing WP).
- Enforce the result with a non-vacuous architectural gate that has an **empty allowlist**. Operator rationale: "half-implemented work and ratchets have been hurting us for weeks. I'd rather spend the effort now."

The rename `OwnedMission` → `OwnedCheckout` makes this a **bulk-edit mission** (`change_mode: bulk_edit`). The classification workflow was run, and [occurrence_map.yaml](occurrence_map.yaml) governs which occurrences change.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; CI also runs the nightly interpreter matrix)
**Primary Dependencies**: typer and rich (CLI), ruamel.yaml (frontmatter), git CLI via subprocess, `spec_kitty_events` (status events; consumed, unchanged). No new dependencies, so no supply-chain review is needed (directive 051: no dependency decision).
**Storage**: Files in git. Mission artifacts are under `kitty-specs/<mission>/`; `status.events.jsonl` is the append-only status authority; `lanes.json`, `meta.json` and `.kittify/config.yaml` (charter activation).
**Testing**: pytest. The layers are:
- ATDD red-first acceptance tests through the real CLI (`typer.testing.CliRunner` / subprocess) on a real repository root checkout plus a linked owned worktree fixture;
- focused unit tests per seam;
- architectural gates in `tests/architectural/` (AST scans reusing `_ast_scan`, self-mutation non-vacuity tests).

Local runs are targeted files plus `make test-fast`; the full and architectural sweeps run in CI (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: Linux, macOS and Windows 10+ developer machines and CI (`ci-windows.yml` for the case-variant identity test).
**Project Type**: single project (CLI plus libraries in `src/`).
**Performance Goals**:
- 1 ownership validation per command;
- 0 extra git subprocesses per owned status read;
- owned `agent tasks status`, `setup-plan` and `context resolve` take a median under 2 s on the acceptance fixture.
**Constraints**:
- Layer chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` (`tests/architectural/test_layer_rules.py`). The `mission_runtime` outbound ledger (cap 10 in `_baselines.yaml`) must not grow.
- `mission_runtime` public surface gates MR-1/MR-2 (`test_mission_runtime_surface.py`).
- Complexity ≤ 15; ruff, format and mypy clean; diff coverage ≥ 90%.
- No shims (`test_compat_shims` burn-down).
**Scale/Scope** (measured by the post-plan squad; about 3× the first estimate):
- 94 bare owned-root params and fields in 30 files;
- 126 `effective_root=` keyword call sites in 40 files, 21 of them `**effective_root_kwargs` splats;
- 46 `effective_root_kwargs(...)` calls in 13 files;
- 19 `"effective_root"` dict-key sites;
- 104 `OwnedMission` attribute reads;
- 87 monkeypatches of the core seams in 27 test files;
- about 26 test files to re-point.

In total, about **400 edit sites**. On top of that, 5 CLI entry points gain `--owned-checkout`, and two functions are decomposed (`accept` 59 → ≤15, `_create_mission_core_impl` 40 → ≤15).

## Charter Check

*GATE: must pass before Phase 0 research; re-checked after Phase 1 design.*

| Charter rule | Status | How the plan satisfies it |
|---|---|---|
| Single canonical authority | ✅ | One minter module. Gate G1–G3 pins it (claim primitive, validator, `_mint`). Status-source classification stays in `surface_resolver` (C-002); there is no new read-source label. |
| Architectural alignment / layer rules | ✅ | The carrier lives in `mission_runtime` and imports only `pathlib`, `dataclasses` and `mission_runtime.context`, so there are 0 new edges. `runtime → mission_runtime` is already permitted (5 existing importers). |
| DDD + tiered rigour | ✅ | `OwnedCheckout` is a value object with invariants in `__post_init__`. The validator is the aggregate boundary. Core seams (placement, status) get the most tests. |
| ATDD red-first (C-011, C-007) | ✅ | Each IC starts with red acceptance tests through the pre-existing entry point. #5009's red test commits are carried first. #4867 uses deterministic fault injection (a truncated `commondir`). |
| Architectural gate discipline (DIRECTIVE_043) | ✅ | Gates G1–G5 have concrete floors (red on the planning base), self-mutation tests and **empty** allowlists. There is no ledger (operator decision `01M3M65D…`). |
| Canonical sources (DIRECTIVE_044) | ✅ | This plan was produced with the canonical CLI. Templates come from `packs/built-in/missions`. The occurrence map is seeded from the canonical template. |
| Campsite cleaning (Standing Order 2) | ✅ | A tidy-first step precedes functional change on god-surfaces (`runtime_bridge.py`, `workspace/context.py`, `mission_finalize.py`). It is behaviour-preserving extraction to keep complexity ≤ 15 wherever signatures change. |
| Terminology canon | ✅ | The carrier fields use "repository_root" and "owned_root". New codes, messages and docs use "repository root checkout". The terminology guard runs pre-push. |
| No full heavy suites in mission | ✅ | Validation is by targeted files, the specific architectural gate files and `make test-fast` only. |
| User customization preservation | ✅ | Mission-state reads and writes only; no user-owned command or skill files are touched. |
| Pre-existing failure rule | ✅ | Any baseline red found is filed as an issue before it is accepted as baseline. |

No violations, so no Complexity Tracking entries are needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/
├── spec.md
├── plan.md                 # this file
├── research.md             # Phase 0 decisions
├── research/pre-spec-options-memo.md
├── data-model.md           # OwnedCheckout, codes, payload fields
├── contracts/
│   ├── owned-checkout-carrier.md
│   ├── cli-owned-checkout-surface.md
│   └── architectural-gate.md
├── quickstart.md           # end-to-end owned walkthrough (SC-001)
├── occurrence_map.yaml     # bulk-edit classification (DIRECTIVE_035)
├── decisions/              # Decision Moments
└── tasks.md                # produced by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/mission_runtime/
├── owned_checkout.py            # NEW: OwnedCheckout value object (private mint)
├── __init__.py                  # re-export OwnedCheckout (public surface + ADR 2026-06-07-1 note)
├── resolution.py                # placement_seam / mission_context_for / resolve_action_context / _resolve_wp_bearing_fields take `owned`
└── checkout_identity.py         # owned_checkout arm in enforce_checkout_identity
src/runtime/next/
├── runtime_bridge.py            # DecideNextContext.owned, _dn_*, board authority, composition, #4867 probe
├── runtime_bridge_engine.py, runtime_bridge_io.py, decision.py, prompt_builder.py, next_invocation_lifecycle.py
src/specify_cli/
├── core/owned_mission.py        # sole minter: resolve_owned_mission(allowed_topologies), resolve_owned_create_root, adopt_owned_checkout; TRANSITIONAL(WP18) OwnedMission factory + effective_root_kwargs deleted
├── core/checkout_ownership.py   # repository-root-itself refusal
├── core/mission_creation.py     # governance reads from the owned root
├── workspace/context.py         # owned arm, resolution_kind=owned_checkout, cache keyed on the resolved tasks dir
├── coordination/{status_service,status_transition,surface_resolver,workspace}.py
├── status/models.py             # TransitionRequest.owned
├── task_utils/support.py        # locate_work_package(owned=)
├── cli/commands/_owned_checkout.py   # NEW: OwnedCheckoutOption, resolve_owned_or_adopt, emit_owned_refusal, stale-copy helper
├── cli/commands/{next_cmd,tasks_status_cmd,agent/tasks,agent/context,agent/mission_setup_plan,agent/workflow,agent/mission_finalize,…}.py
├── cli/commands/agent/workflow_executor.py   # claim-commit review base
├── missions/operation_context.py # DELETED (cwd adoption replaced by adopt_owned_checkout)
└── (accept, consolidation, review cycle, commit_router, write_seam …)  # remaining effective_root → owned conversions
tests/
├── architectural/test_owned_checkout_single_authority.py   # NEW gates G1–G6
├── integration/test_owned_lifecycle_acceptance.py          # NEW SC-001 walkthrough + O1–O10 repros
└── (existing owned test files re-pointed; #5009 tests carried)
docs/
├── adr/3.x/2026-09-03-1-…, 2026-08-12-1-…, 2026-06-07-1-… (amendments)
└── context/execution.md         # "owned checkout" glossary entry
```

**Structure Decision**: single project. The new code is confined to one new `mission_runtime` module and one new CLI helper module. Everything else is signature migration and deletion.

## Complexity Tracking

Not needed; there are no Charter Check violations.

## Staging Strategy (operator decision `01M3M713…`)

**Top-down conversion.** A function's signature changes to `owned: OwnedCheckout | None` only once its callers hold the fact. Its not-yet-converted callees receive the bridging expression `effective_root=owned.owned_root if owned else None`, which is not a new signature.

**Bridging markers (binding).** Every bridging call site carries `# bridging: WP<n> converts`, naming the WP that converts it. The converting WP's DoD asserts `grep -rn "bridging: WP<self>" src` is empty (it converts the marked sites, in other WPs' files as declared out-of-map edits). WP18 asserts `grep -rn "# bridging:" src` is empty.

**The one bottom-up exception: `next`.** The `next` runtime (WP11) converts before its CLI entry (WP19). The five runtime entry points `next_cmd` calls keep a marked `TRANSITIONAL(WP18)` legacy `effective_root` keyword whose arm obtains the fact once through `_transitional_owned_from_legacy`; WP19 removes every caller, and WP18 deletes the keywords.

**Transitional surfaces: the six shared seams plus every other function marked TRANSITIONAL(WP18).** From the seam WP until the closing WP, the six shared seams accept both `owned=` and the legacy `effective_root=`:
- `placement_seam`
- `mission_context_for`
- `resolve_action_context`
- `resolve_workspace_for_wp`
- `locate_work_package`
- `TransitionRequest`

**`TRANSITIONAL(WP18)` convention and budget (binding).** Each WP that adds markers lists them exactly in its DoD with the expected `grep -c` per file; WP18 T096 fails on any marker that no WP's DoD lists.  Every transitional legacy parameter, field, property, alias or factory anywhere in `src/` or `tests/` carries a `# TRANSITIONAL(WP18): <reason>` comment on the line that declares it. This covers the six seams' legacy keyword, `effective_root_kwargs` / `_EffectiveRootKwargs`, the legacy `OwnedCheckout` properties (`primary`, `root`, `directory`, `slug`, `target`), the legacy `OwnedMission` factory function, the tests pinning them, and any other function a WP must keep dual for a later WP. The closing WP (WP18 T096) deletes **exactly** everything `grep -rn "TRANSITIONAL(WP18)" src tests` finds, and T097 asserts that grep is empty. An unmarked transitional surface is a review rejection.

**Transitional `OwnedMission` is a factory function.** It is a legacy factory **function** defined in `core/owned_mission.py` (the minter module, so G3 holds). It accepts the old positional arguments `(primary, root, directory, slug, target)` and mints an `OwnedCheckout` (topology `SINGLE_BRANCH`), marked `# TRANSITIONAL(WP18)`. The six unowned tests that construct `OwnedMission(...)` keep working unchanged until WP18 T097 re-points them. Because a function is not a type, WP02 retypes the annotation sites (`owned: OwnedMission | None`) to `OwnedCheckout` as a declared, annotation-only out-of-map edit.

Nothing ships in between: the PR contains only the final state, so none of this is a shipped shim. Reviewers must not reject a marked transitional surface before the closing WP.

**mypy invocation discipline.** `pyproject.toml` sets `follow_imports = "skip"` for `specify_cli.*`: an imported `specify_cli` module that is not itself on the mypy command line is typed `Any`. A signature change is therefore only type-checked when its **callers and callees are checked in the same invocation**. Every WP's mypy command lists the changed module together with every caller and callee it touched (or that calls a changed signature). `--strict` is never dropped; pre-existing errors are baselined by count (the same command on the planning base) and must not grow.

**Dead-symbol gate at the mission tip.** `tests/architectural/test_no_dead_symbols.py` is judged at the **mission tip** (WP18), not per lane or intermediate WP (a consumer may land in another lane). Expected transient reds: `OwnedCheckout` until WP02, `resolve_owned_create_root` until WP10, `adopt_owned_checkout` until WP08. WP01/WP02 name them and do not treat them as their own failures; record them in the Activity Log, never allowlist. WP18 asserts the gate green.

**Red-first proofs are commits.** The red test commit precedes its fix commit, and reviewers verify the order in `git log`. Activity-Log-only or `git stash` proofs are not accepted. Mutation checks are non-vacuity evidence, not red-first proofs; where a WP's closing proof needs one, it is committed as a test.

**Error codes.** WP01 defines `OwnedRefusalCode` (`StrEnum`, value == name) in `mission_runtime.owned_checkout`, exported from the package root with `OwnedCheckout`. Every WP and test imports codes from it (Sonar S1192); existing literal sites are converted by the WP that owns their file.

**FR-015 oracle.** The atomic-finalize oracle is `git status --porcelain --ignored` in P **plus content hashes of the ignored files** (WP02's `tests/_owned_tree_hash.hash_tree`, the same hashing as `r_snapshot`), `HEAD` and the index, so ignored writes and rewrites (for example under `.kittify/derived/`) are caught too.

**Every WP leaves the tree green.** The gate's self-mutation and floor tests land green in the foundation WP. The G1–G6 assertions are committed red as the **first commit of the closing WP** and turn green within it (red-first inside that WP).

**One owning WP per shared file** (tasks must honour this):

| File | Owner concern |
|---|---|
| `next_invocation_lifecycle.py`, `runtime_bridge*.py`, `decision.py` | IC-05 runtime (WP11) |
| `next_cmd.py` | IC-05 CLI entry (WP19) |
| `prompt_builder.py` | IC-05/IC-06 (WP12) |
| `agent_tasks_ports.py` | IC-04 |
| `cli/commands/accept.py` | IC-10a |
| `mission_finalize.py` | IC-07 |
| `core/owned_mission.py` | IC-01 (it holds `adopt_owned_checkout` and `resolve_owned_create_root` as well) |

**Campsite first.** The first commit of each owning WP is a behaviour-preserving extraction for any touched function at complexity ≥ 12:
- `finalize_tasks` (15, `noqa`)
- `_commit_finalize_artifacts` (15)
- `query_current_state` (15)
- `resolve_context` (15)
- `_state_to_action` (14)
- `_build_wp_prompt` (14)
- `_print_standard_human` (14)
- `next_step`, `create_rejected_review_cycle`, `_run_bootstrap_loop` (12)

## Test Layout and Markers

- **One acceptance file per WP**: `tests/integration/test_owned_lifecycle_acceptance_{status,context,next,review,finalize,cli,create}.py`, marked `integration` + `git_repo` (in-process CliRunner).
- **Shared fixtures** (`owned_checkouts`, `r_snapshot`, `stale_root_copy`) live in `tests/integration/conftest.py`, not imported from test modules. The tree-hash walk behind `r_snapshot` is a plain helper, `tests/_owned_tree_hash.py`, reusable outside `tests/integration/` (WP13's oracle). `stale_root_copy` writes a `lanes.json` by default (the O4 fail-open base).
- **Minting facts in tests.** Tests may reference `OwnedCheckout._mint` (gate G3 scans `src/` only), but should prefer WP02's fixture helper or the real validator, so facts stay realistic.
- **Seam unit tests** are marked `unit` + `fast`. **Gates** are marked `architectural`.
- **Tests that build with `spec-kitty init` or an installed CLI** are marked `e2e` + `slow` (nightly). The per-PR guard for coordination-topology owned `next` is the in-process twin (FR-022).
- **NFR-002 counts** patch at `checkout_ownership.resolve_ownership_claim` and clear the workspace caches first.
- **NFR-003** is `performance` (nightly).
- **Windows case-variant test**: its file is added to the `ci-windows.yml` path filter.

## Implementation Concern Map

> Concerns are not work packages. `/spec-kitty.tasks` decomposes them.

### IC-01 — Validated ownership fact and sole minter
- **Purpose**: one value object and one minting module.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-020, FR-021 (helper), FR-023, C-001, C-003, NFR-002, NFR-006.
- **Affected surfaces**:
  - New `src/mission_runtime/owned_checkout.py`, re-exported from `mission_runtime/__init__.py` and added to `_PUBLIC_SURFACE`:
    - `OwnedCheckout.files()` reuses `kernel.resolution.resolve_rejecting_loops` to keep the symlink and loop defence of today's `ensure_within_directory`;
    - containment reuses `mission_runtime.checkout_identity._is_within`;
    - Windows case-folding goes through `kernel.paths.is_windows()`.
  - `core/owned_mission.py`:
    - `resolve_owned_mission(..., allowed_topologies)`, with `LIFECYCLE_OWNED_TOPOLOGIES` / `NEXT_OWNED_TOPOLOGIES`;
    - `resolve_owned_create_root`, which returns a typed `OwnedCreateRoot` value rather than a bare `Path`;
    - `adopt_owned_checkout`: excludes R, other repositories, coordination worktrees (`classify_worktree_topology(...) is COORD_WORKTREE`), lane worktrees (via `lanes.json` membership) and rejected checkouts. It also re-expresses today's mission-surface-conflict refusal for different mission ids (US7-AS5).
    - The legacy `OwnedMission` factory function, `_EffectiveRootKwargs` and `effective_root_kwargs` are marked `# TRANSITIONAL(WP18)` and deleted in the closing WP.
  - `core/checkout_ownership.py`: add `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`.
  - Rename the 104 attribute sites according to `occurrence_map.yaml`.
  - The gate's self-mutation and floor tests land here, green.
- **Sequencing**: foundation.
- **Risks**:
  - The attribute renames are grep-hostile; `mypy --strict` is the safety net.
  - The contract note that "`LANE_WORKTREE` means registered non-coordination" is recorded in the carrier contract.

### IC-02 — Placement seam and mission-runtime resolution
- **Purpose**: close the fold-back at its source.
- **Relevant requirements**: FR-006, FR-007, FR-009, FR-011, FR-023.
- **Affected surfaces**:
  - `mission_runtime/resolution.py`: add the owned arm to `placement_seam` / `PlacementSeam.owned`, `mission_context_for`, `resolve_action_context` (target branch from the fact) and `_resolve_wp_bearing_fields`.
  - **Delete `_require_owned_single_branch`** (`:1505,1596,2361`). Topology is decided once, at minting, so this is not a second topology authority.
  - `task_utils/support.py::locate_work_package`.
  - The dual keyword starts here.
- **Sequencing**: IC-01.

### IC-03 — Workspace resolution: owned arm, kind, cache
- **Relevant requirements**: FR-006, FR-008, FR-011, FR-019.
- **Affected surfaces**:
  - `workspace/context.py`:
    - `resolution_kind="owned_checkout"` with `lane_id=None`;
    - coordination-topology owned missions keep the lane arm through the owned seam;
    - caches keyed on the resolved read `tasks_dir`, with `clear_workspace_resolution_caches` tests.
  - `mission_runtime/checkout_identity.py`: owned arm.
  - Carry the lookup and cache half of #5009 edaa9cd83.
- **Sequencing**: IC-01, IC-02.

### IC-04 — Status surfaces and the status pipeline
- **Relevant requirements**: FR-003, FR-013, FR-014, C-002.
- **Affected surfaces**:
  - `coordination/status_service.py`: **all six shape-guard sites** (`:159,166,221,228,340,347`, covering read, stream read and write-contract validation) route through the new `surface_resolver.primary_read_targets_coord_worktree(path, *, owned)`. `EventLogReadContract` and `EventLogWriteContract` each gain `owned`.
  - `coordination/transaction.py:644`: replace the raw `".worktrees" in parts` check with `is_under_worktrees_segment`.
  - `coordination/status_transition.py`: remove the `:903-917` re-validation.
  - The status pipeline's `TransitionRequest` readers (`status/models.py`, `transition_pipeline`, `emit`, `bootstrap`, `transaction`, `commit_router`, `write_seam`) collapse `effective_root` and `owned_mission` into `owned`. This is the status half of the old IC-10.
  - `agent_tasks_ports.py` (`MissionHandle.owned`).
  - `cli/commands/accept.py:342`: stop re-validating (the edit is owned by IC-10a).
  - Carry #5009 4ff6ff0c0 with its `test_owned_contract_validates_root_and_mission` dropped. Add a same-path **registered** coordination-worktree control (FR-014).
- **Sequencing**: IC-02.

### IC-05 — `next` runtime
- **Relevant requirements**: FR-002, FR-007, FR-008, FR-009, FR-012, FR-022 (in-process twin), FR-023.
- **Affected surfaces**:
  - `next_cmd.py`: goes through `resolve_owned_or_adopt(NEXT_OWNED_TOPOLOGIES)`; resolves the handle in P for handle-less `next`; delete `_emit_checkout_ownership_error`.
  - `runtime/next/runtime_bridge.py`:
    - `DecideNextContext.owned` and the `_dn_*` helpers;
    - the board authority `_resolve_wp_board_action`, `_implement_action` and `_review_action`;
    - composition policy read from `owned.owned_root`;
    - `_wrap_with_decision_git_log` cwd;
    - resolve the WP workspace **before** persisting the advance (O5).
  - `runtime_bridge_engine.py`, and `runtime_bridge_io.py:1155` (the presence probe folds into the fact).
  - `decision.py`, `prompt_builder.py`, `next_invocation_lifecycle.py`.
  - `coordination/workspace.py:163`: capture stderr, raise a typed `CoordinationWorkspaceUnavailable` (subclassing `CalledProcessError`, so the transient-lock retry still applies), and map it to a `blocked` decision with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
  - Carry #5009 edaa9cd83 (the `next` half) and 1be5352ee (the composition half). Re-express e6923bc97.
- **Sequencing**: IC-02, IC-03, IC-04, IC-08 core.
- **Risks**: god-module, so campsite-extract first. Split into three WPs: the runtime core (WP11), the CLI entry `next_cmd.py` (WP19, after WP11), and prompt/review (WP12, after both).

### IC-06 — Unified review base (decision `01M3M70Y…`)
- **Relevant requirements**: FR-010, FR-025.
- **Affected surfaces**:
  - A new helper, `claim_commit_for_wp(mission_dir: Path, wp_id: str)`, in `mission_runtime`. It is topology-agnostic (not a G6 consumer of the fact), runs git in-layer via `subprocess` with a timeout (the `lifecycle_phase.py` precedent; no general kernel git seam exists), and fails closed.
  - Used by both the `owned_checkout` and `repo_root` review paths.
  - **Delete the three subject matchers**: `workflow_executor.py:2259`, `prompt_builder.py:255` and `core/worktree_topology.py:125`. The `prompt_builder` edit is owned by IC-05's WP, or the WP is split and sequenced after it.
  - Rewrite #5009 1be5352ee's review assertion to the claim-commit contract.
  - Pin that no later event cites a claim `event_id`: a test for the `-S` uniqueness assumption.
- **Sequencing**: IC-05.
- **Risks**: squash-rebasing P's branch folds the claim into implementation commits. This is documented, and the helper still fails closed.

### IC-07 — Atomic `finalize-tasks`
- **Relevant requirements**: FR-013, FR-015.
- **Affected surfaces**: `cli/commands/agent/mission_finalize.py` and `tasks_finalize_validation.py`:
  1. build the whole plan in memory first, reusing `--validate-only` (INV-6);
  2. then apply all writes in one phase.
- **Sequencing**: IC-04, IC-08 core.
- **Risks**: the oracle is `git status --porcelain --ignored` plus ignored-file content hashes, including `.kittify/derived/`.

### IC-08 — CLI owned surface and validated flagless adoption
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-007, FR-018, FR-020, FR-021, NFR-004.
- **Affected surfaces**:
  - New `cli/commands/_owned_checkout.py`: `OwnedCheckoutOption`, `resolve_owned_or_adopt`, `emit_owned_refusal` (built on `cli/json_contract.json_error`, keeping each command's envelope keys, always with `error_code`), and a stale-copy reporter.
  - Move **all eight** inline `--owned-checkout` declarations onto the option:
    - `tasks.py:782,916`
    - `mission_finalize.py:3237`
    - `mission_check_prerequisites.py:563`
    - `next_cmd.py:132`
    - `accept.py:763`
    - `spec_commit_cmd.py:166`
    - `mission_create.py:753`
  - New flags:
    - `agent tasks status`: `tasks.py:1361` / `tasks_status_cmd._do_status`
    - `setup-plan`: `mission_setup_plan.py:996`
    - `context resolve`: `agent/context.py:110`
    - `agent action implement` / `agent action review`: `workflow.py:1336,1858`, refusal only
  - Delete `missions/operation_context.py`.
  - Update the golden contracts.
- **Sequencing**: core helper after IC-01; per-command wiring after IC-02/03/04.

### IC-09 — Governance reads at owned create
- **Relevant requirements**: FR-016, FR-017.
- **Affected surfaces**: `core/mission_creation.py` `:848`, `:951`, `:963`, `:968`. Carry a37e9ee39 and re-express 1f42f76ea.
- **Sequencing**: IC-01, IC-14b (decomposition first).

### IC-10 — Remaining conversion (all bare owned roots)
- **IC-10a — acceptance.** `cli/commands/accept.py` and `acceptance/*`. Carries IC-14a.
- **IC-10b — task commands and history.** `tasks_move_task`, `tasks_mark_status`, `tasks_shared`, `tasks_parsing_validation`, `tasks_verdict_persistence`, `spec_commit_cmd`, `mission_check_prerequisites`, `issue_matrix`, `review/cycle`, `consolidation/baseline`, `git/commit_helpers`, `missions/_read_path_resolver` and `migration/runtime_state_cutover`.
- **Scope**: this also covers the renamed-carrier state fields (`owned_checkout: Path | None` at `tasks_mark_status.py:114`, `tasks_move_task.py:248` and `mission_creation.py:127`) and the `"effective_root"` dict-key splats (for example `mission_finalize.py:929` and `agent_tasks_ports.py:251`).
- **Relevant requirements**: FR-001, FR-003, FR-022.
- **Sequencing**: IC-04, IC-08 core.

### IC-11 — Single-authority gate (closing)
- **Relevant requirements**: FR-001, SC-004.
- **Affected surfaces**:
  - `tests/architectural/test_owned_checkout_single_authority.py`, following `contracts/architectural-gate.md`: AST scans of all reference forms, an identifier ban, the carrier-field FQN rule and self-mutation cases.
  - The closing WP commits the G1–G6 assertions red, then deletes everything marked `TRANSITIONAL(WP18)` (the six shared seams' legacy keyword plus every other marked surface) and every remaining `effective_root` outside the org-pack module rule, so the gate turns green.
  - Add the `_baselines.yaml` section `test_owned_checkout_single_authority: {owned_root_bare_path_params: 0}`.
- **Sequencing**: last.

### IC-12 — ADRs and glossary
- **Relevant requirements**: FR-024, C-005.
- **Affected surfaces**: ADRs 2026-09-03-1, 2026-08-12-1 and 2026-06-07-1, and `docs/context/execution.md`. Run the docs index, freshness and terminology tooling.
- **Sequencing**: none.

### IC-13 — #5009 provenance
Each carried commit keeps author Samuel Goff (`cherry-pick -x`) and lands at the start of its concern's WP:

| Commit | Destination | Handling |
|---|---|---|
| a37e9ee39 | IC-09 | carry |
| edaa9cd83 | IC-03 / IC-05 | carry, split by file ownership |
| 1be5352ee | IC-05 / IC-06 | carry, then adapt |
| 4ff6ff0c0 | IC-04 | carry, then trim |
| 22f380055 | pyproject | only if the engine file is still formatter-excluded |

The fix commits are re-expressed with a `Co-authored-by: Samuel Goff <samuel@defpix.com>` trailer. 6d682dce3 and the doc and style commits are dropped.

### IC-14 — Complexity restoration (decision `01M3M718…`)
- **IC-14a**: decompose `accept()` (59 → ≤15), behaviour-preserving, with focused tests.
- **IC-14b**: decompose `_create_mission_core_impl` (40 → ≤15), behaviour-preserving, with focused tests.
- Remove `C901` from the `ruff.toml` per-file ignores for `cli/commands/accept.py` and `core/mission_creation.py`. They are the only over-limit functions in those files.
- **Relevant requirements**: FR-026.
- **Sequencing**: IC-14a precedes the IC-10a conversions; IC-14b precedes IC-09. Both are pure refactors, done before the functional change (tidy-first).
