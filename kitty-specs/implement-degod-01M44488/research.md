# Research: Implement command degod (tidy-first)

Phase 0 output. The pre-spec grounding lives in [`research/code-grounding.md`](research/code-grounding.md)
(decisions D1–D10) and [`research/test-remediation.md`](research/test-remediation.md). This file adds
the plan-time decisions and records the disposition of every squad finding (adversarial-squad
findings-disposition contract: accepted, changed, or deferred with rationale; none dropped).

## Decisions

### R-1 — #5232 placement: which seam query, which surviving arm

- **Decision**: **B2\*, a seam-owned placement with the degrade arms keyed on a typed flag.** It
  keeps every reachable outcome byte-identical (C-007 is not triggered). It closes #5232 under the
  issue's second acceptable shape: "a documented, tested degrade path is kept, owned by the
  placement seam and not by `implement.py`".
  1. Placement is still resolved by calling `resolve_action_context(action="implement")` first.
     That keeps today's pre-commit WP-context gate, so `MissingLanesError` and `CorruptLanesError`
     still stop implement before any commit.
  2. On success, the placement is `artifact_placement.placement_ref`. Where both resolve it equals
     `placement_seam(...).write_target(MissionArtifactKind.DECISION_LOG)`.
  3. On `ActionContextError`, the result is a typed **unresolved-context placement**, not `None`.
     Its coordination ref comes from the placement seam
     (`write_target(DECISION_LOG)`, or a seam-level coordination-ref helper), and only when the
     stored topology routes through coordination and the mission declares a coordination branch.
     If the seam itself cannot resolve, `PlacementResolutionRequired` is raised with the one
     remedy text (FR-018).
  4. The three unresolved-context outcomes survive unchanged, keyed on that typed result instead of
     `placement_ref is None`: the flat single transaction, the protected-planning-branch raise, and
     the partition commit.
  5. The decision that builds the typed placement lives in `coordination/planning_commit.py` (the
     seam). The command-package adapter only consumes it.
  6. What is removed:
     - every *placement* read of `meta.json` `coordination_branch` (the `[0]` consumer of the
       identifier tuple);
     - the `placement_ref: CommitTarget | None = None` overload;
     - the C-004 wording in docstrings and comments.
  7. What is kept: `meta.json` `coordination_branch` stays as an identity input (mid8 and the
     legacy console line, C-006 tuple).
- **Evidence**:
  - Setup: real-git fixtures built with the real CLI (`agent mission create` + `finalize-tasks`)
    against this checkout.
  - Each run is a real `spec-kitty implement WP01 --mission … --auto-commit` (and
    `--no-auto-commit`), with a dirty PRIMARY `spec.md` plus an untracked COORD-residue trace file.
  - Coverage: 64 states across flat/legacy, `single_branch` (including a minted mission branch),
    `lanes`, `coord` and `lanes_with_coord`, and the lifecycle phases. About 200 runs compared on
    exit code, console, branch deltas and `git status`.
  - B2\* was identical to today in every state.
  - Run by the plan-phase research delegate (`researcher-robbie`) on 2026-10-04. Its harness was
    session-local; FR-015's committed tests re-create the reachable rows.
- **Which artifact kind matches today's placement**:
  - `DECISION_LOG` is the only kind whose `write_target` equals the context placement ref in every
    lifecycle phase where both resolve.
  - `STATUS_STATE` and the other coordination kinds diverge to the target under PUBLISHED
    (write-side published short-circuit).
  - `ANALYSIS_REPORT`, used by `mission_record_analysis`, is a PRIMARY kind and is the wrong
    template.
- **Reachability of the fallback today** (the FR-015 table seed):

  | State | Reachable on the real path? | Today | B2\* |
  |---|---|---|---|
  | Coordination worktree unmaterialized or empty; flat topology with a coord branch; merged mission | yes | refused earlier ("WP … is not finalized"), no commit | = |
  | Coordination branch deleted | yes | refused at `resolve_status_surface_with_anchor`, no commit | = |
  | Coordination branch declared but never created | yes | context resolves; commit refused `DESTINATION_REF_NOT_FOUND` | = |
  | `lanes.json` missing or corrupt | yes | `MissingLanesError` / `CorruptLanesError` escape the narrow catch; exit 1, no commit | = |
  | Duplicate WP prompt (`WORK_PACKAGE_UNRESOLVED`), flat | yes | arm (a): 1 transaction, then a later refusal | = |
  | Duplicate WP prompt, coordination | yes | arm (c): partition commit, then a later refusal | = |
  | Protected coord target + `--no-auto-commit` + committed residue + duplicate WP | yes (exotic) | arm (b): `PlacementResolutionRequired`, 0 commits | = |
  | Merged mission with coordination branch torn down, re-run | yes | proceeds (clean) / commits PRIMARY then `CoordinationBranchDeleted` (dirty) | = |
  | Healthy, every topology | yes | resolved partition arm | = |

- **Alternatives considered**:
  - **B1**, `write_target` only and one surviving arm: changes four reachable rows.
    - A flat duplicate-WP run goes from 1 to 2 commits.
    - Arm (b) becomes commit-then-refuse.
    - A merged mission with a deleted coordination branch goes from exit 0 to
      `PlacementResolutionRequired`.
    - A missing or corrupt `lanes.json` gives a different refusal text and commits first.
    - Rejected under C-001; it would need an operator escalation.
  - **B3**, context first with a seam fallback and a single arm: like B1 apart from the
    `lanes.json` rows. Rejected for the same reason.
  - **B2** (B2\* without the declared-branch condition): a double-fault row
    (duplicate WP + coord topology with no declared branch) goes from 1 to 2 commits. Rejected.
- **Consequence for INV-7** (`test_flat_legacy_none_seam_success_arms.py`): it survives with
  its intent intact. It is re-keyed from `placement_ref=None` to the typed unresolved-context
  placement with no coordination ref, and must still reach the flat success arm. It is not deleted.
- **Follow-up**: the single seam-only commit path (B1) would be the literal end state #5232
  describes. It changes four reachable outcomes, so it is filed as a follow-up for an operator
  decision rather than taken here.

### R-1b — #5232 refinement after the WP06 review (supersedes R-1's degrade source)

- **Finding**: the WP06 review built four reachable double-fault states (D1–D3, D5) where B2\*
  changed outcomes. B2\* resolved the coordination ref through `write_target(DECISION_LOG)` behind a
  topology gate, and did so eagerly, before the #1598 structural check.
  - **D1–D3**: a merged coord mission whose coordination branch was torn down, plus a duplicate WP.
    The early `PlacementResolutionRequired` pre-empted the clean-tree return, the PRIMARY-leg commit
    and the structural refusal.
  - **D5**: a stale `coordination_branch` key on a lanes mission. The topology gate flipped arm (c)
    to arm (a).
  - The R-1 64-state matrix did not contain these combinations.
- **Decision (Decision Moment `01M44THPFVJSWH7FEE8X5JKSZV`)**: B2\*\*. On an unresolved WP context,
  the coordination ref is the mission's **declared coordination-branch value**.
  - It is read by the coordination seam (`coordination/planning_commit.py`) through the identity
    cascade (primary-anchored meta, then the `feature_dir` fallback).
  - There is no topology gate and no existence probe.
  - It is computed **lazily in the adapter, after the structural check**, at the same point where
    today's code read it.
  - This is identical to today by construction for every state, D1–D5 included, so C-007 is not
    triggered.
- **Why this still closes #5232**: #5232 accepts *"a documented, tested degrade path kept, owned by
  the placement seam and not by `implement.py`"*.
  - The `None` default and the implement-local read are gone.
  - The degrade lives, documented and tested, in the coordination seam beside the bookkeeping
    transaction.
- **Not taken**: a seam-probing single path (R-1 B1/B2\*). It changes reachable outcomes and
  remains the operator follow-up already listed for WP12.

### R-2 — Where the phase sequence lives

- **Decision**: `cli/commands/implement_phases.py`, a sibling inside the command package.
- **Rationale**: the phase sequence drives the `StepTracker` and the per-step exception rendering,
  which are CLI concerns. Putting it in a lower package would import the CLI upward (C-004).
  `runtime.next` must not import the CLI layer either.
- **Alternatives considered**: a new `specify_cli/implement/` application service shared with
  `agent action implement` and `orchestrator_api` (rejected for this mission: it is a new package and
  needs an ADR; filed as a follow-up). Keeping the sequence inside `implement.py` (rejected: SC-001,
  FR-001).

### R-3 — Re-export policy for moved names

- **Decision**: a moved name loses its re-export from `implement.py` in the same WP, unless
  production code imports it from there. Today that is only `implement` itself
  (`cli/commands/__init__.py`, `agent/workflow.py`). Tests are re-pointed.
- **Rationale**: a re-export keeps a stale `patch("…implement.X")` silently non-intercepting
  (test-remediation §2c). Deleting the re-export turns it into an `AttributeError`, and the widened
  liveness gate catches the rest.
- **Alternatives considered**: identity re-exports (#5650/#5679 precedent). Rejected: in this file
  they would mask about 100 patch sites, and `test_no_dead_symbols` counts a re-export as a caller.
  The existing `implement_cores` shim block is reduced in the same way as its names stop being used
  from `implement`.

### R-4 — Claim-policy-metadata dedupe home

- **Decision**: one `claim_policy_metadata(shell_pid, agent)` exported by the status facade next to
  `build_claim_policy_metadata`, importing `core.process_liveness` lazily. `implement` and
  `agent/workflow_executor.py` both call it.
- **Rationale**: the two bodies are semantically identical today (workflow_executor.py:92–117 and
  implement.py:1812–1830). The status facade is importable from both callers without a layer break.
- **Alternatives considered**: `core/process_liveness.py` (rejected: it would import status upward
  in the core-to-status direction for a status-owned key layout). Keeping both copies (rejected: the
  single-authority principle; the copies are documented duplicates).

### R-5 — Characterization without coupling assertions to internals

- **Decision**: the FR-009 suite runs `implement` in two ways, both on real-git fixtures: through
  `typer.testing.CliRunner`, and by calling the command function directly. The fixtures are built
  with the helpers the existing integration tests use
  (`tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`,
  `tests/integration/test_wp_integrity_*`).
- **Failure injection**: where a failure can only be induced by substituting a collaborator (the
  claim-commit exception table, the #4888 status-start failure), the substitution target is looked
  up in one dispatch-map fixture (logical collaborator → current dotted target). A moving WP
  updates the map, never an assertion. The widened liveness gate checks that every mapped target
  is live.
- **Rationale**: FR-009 / SC-003 require zero assertion edits across the moves. Patching the owner
  module alone does not intercept a name the command imported into its own namespace.

### R-6 — Census-scan widening proof

- **Decision**: each widened scan list (FR-012) is proven by temporarily planting a violation in the
  new module and running that gate red, then removing the plant. The plant is never committed; the
  command and the red output are recorded in the WP review notes.

## Squad finding dispositions

### Pre-spec grounding squad (4 lenses)

All findings are dispositioned in `research/code-grounding.md` §2 (D1–D10) and §1.6 (related issues).
Disposition summary:
- **Accepted:** auto-rebase dropped, liveness gate first, scan widening, source-pin re-pointing,
  mypy strictness on moved code, out-of-matrix local runs, #5673 shaping, #5676 out of scope.
- **Deferred with follow-up issues:**
  - the planning commit runs before late validation;
  - the misleading "not finalized" message for an unmaterialized coordination worktree;
  - a shared implement application service.

### Post-specify squad

| Finding (lens) | Disposition |
|---|---|
| FR-009 frozen suite vs FR-008 change (renata, HIGH) | **Changed**: FR-015 added. Placement outcomes are pinned red-first outside FR-009's frozen set. |
| US3-3 refusal phase (renata, HIGH) | **Changed**: the scenario names the planning-commit phase inside the `validate` tracker step. |
| SC-004 forbids identity reads (renata + alphonso, HIGH) | **Changed**: SC-004 is scoped to commit destinations and placement refs. The identity tuple, mid8, the legacy console line and the demotion guard are kept. |
| SC-002 gameable or unmeasurable (renata + alphonso, HIGH/MED) | **Changed**: family-wide count with a committed counter script. Console couplings and private imports are reported. |
| `mission_record_analysis` kind is PRIMARY (alphonso, HIGH) | **Changed**: the assumption is corrected, and the kind choice moved to R-1 / FR-015. |
| C-007 domain too narrow, no lifecycle axis (alphonso, HIGH) | **Changed**: C-007 covers any reachable outcome change. FR-015 covers topology × lifecycle phase. |
| FR-001 vs SC-001 phase-sequence home (both, MED) | **Changed**: FR-001 names the sibling adapters; SC-001 states `wc -l` and a per-sibling cap. |
| FR-002 no-op passable (renata, MED) | **Changed**: own check, a phase-call-order test. |
| C-002 vs mypy fixes and re-export deletion (renata, MED) | **Changed**: the adjust commit may carry typing-only fixes and re-export deletion. |
| NFR-002 quarantine and pre-existing errors (renata, MED) | **Changed**: quarantine entry rule stated; `dependency_graph.py` errors fixed in passing. |
| FR-010 baseline (renata, MED) | **Changed**: the unresolvable baseline is not raised, and dead patches are fixed. |
| FR-012 positive control and checklist (renata, MED) | **Changed**: planted-violation control, checklist cited, floor re-calibration sanctioned with proof. |
| FR-013 not enumerated (renata, MED) | **Changed**: the four tests are named. |
| Missing docs, changelog, tracker, dead helper, out-of-matrix runs (renata, MED) | **Changed**: FR-016, FR-017, FR-018 and NFR-006 added. Format-exclude rule added to NFR-004. |
| FR-009 must not patch the implement namespace (renata, MED) | **Changed**: stated in FR-009, and R-5 here. |
| NFR-005 not measurable (renata, LOW) | **Changed**: move commits shown with `--color-moved`, listed in the PR. |
| FR-007 mixes ratchet and build (renata, LOW) | **Changed**: the exception table moved into FR-009; FR-007 is build-only. |
| FR-014 decorators (renata, LOW) | **Changed**: decorators and option defaults named. |
| C-008 vs tool attribution trailer (renata, LOW) | **Changed**: C-008 states that the operator rule overrides the default trailer. |
| Legacy console line removal (alphonso, MED) | **Changed**: only docstrings and comments lose the C-004 wording; the console line is kept. |
| "Collapses to two arms (flat: single)" contradicts code (alphonso, MED) | **Changed**: the surviving arm structure is decided by R-1, not assumed. |
| Partition-call floor would drop (alphonso, MED) | **Changed**: FR-012 sanctions re-calibration with rationale and planted break. |
| FR-007 upward import of the status-artifact collector (alphonso, MED) | **Changed**: the bundle stays in the command package (`implement_claim.py`). The metadata half is a dedupe (R-4). |
| D4 re-export rule missing (alphonso, MED) | **Changed**: FR-011 states the rule (R-3). |
| FR-003 single-authority tension with `dependency_verdict` (alphonso, LOW) | **Deferred**: pinned, not deduplicated, in this mission. Dedupe recorded as part of the shared-service follow-up. |
| FR-004 only pure decisions move (alphonso, LOW) | **Accepted**: the contract lists exactly which functions move and which stay in the adapter. |
| FR-006 `__all__` and allow-list (alphonso, LOW) | **Accepted**: FR-006 and the contract name both. |
| Recover mode, console singleton, #3371 e2e (alphonso, LOW) | **Accepted**: spec edge cases added. |

### Post-tasks squad (planner-priti planning lens, architect-alphonso feasibility lens)

Both lenses' verdict was "not ready as written"; every finding is folded below.

| Finding | Disposition |
|---|---|
| Liveness gate cannot see dispatch-map values; pre-filter `"commands.agent"` would scan zero implement files (both, HIGH) | **Changed**: WP01 T001 per-family config incl. pre-filter; T002 explicit dispatch-map liveness case with planted dead entry |
| Mandated attribute-call style would be reported dead by the seam rule (priti, HIGH) | **Changed**: WP01 adds the attribute rule (`<alias-of-M>.<name>` reads are live); one mission-level call-style rule in every prompt |
| Missing refusal families incl. DESTROYED_LANE / LANE_WORK_TIP_UNKNOWN through implement() (priti, HIGH) | **Changed**: characterization split into its own WP02 with all families listed |
| SC-002 laundering via the dispatch map / dynamic targets; reduction relied on WP08 only (priti, HIGH) | **Changed**: counter counts `patch_collaborator` calls; map scope limited; dynamic targets forbidden; WP09 phase functions take `repo_root`/context as parameters; WP10 per-target reduction plan |
| Ownership walls on ~25 test files (priti, HIGH) | **Changed**: explicit owned files per WP plus a mission rule granting mechanical re-point leeway (charter ownership-map leeway), logged |
| `test_commit_recipes` `silently demotes` allow-list goes stale inside the #5699-red test (both, HIGH) | **Changed**: WP04 re-keys it; every WP compares the failing set to base |
| `_git_stdout` needed by the planning adapter → circular import (both, HIGH/MED) | **Changed**: WP05 moves it to `lanes/implement_support.git_stdout` (twin of `lifecycle_sync._git_stdout` named, not merged) |
| `--base` unresolved case cannot be no-mutation (alphonso, HIGH) | **Changed**: WP02 pins the actual post-state |
| Typed `BaseRefUnresolved` would change tracker text and force assertion edits (alphonso, HIGH) | **Changed**: WP07 catches inline inside the create try; CLI-side `_validate_base_ref` translator kept |
| `claim_policy_metadata` name collides with a local in workflow_executor (F823) (alphonso, HIGH) | **Changed**: WP08 imports under an alias |
| `detect_feature_context` stays → import cycle; checkout-identity source pin unlisted (alphonso, HIGH) | **Changed**: WP09 moves it to `implement_phases`; re-points the :299–304 pins |
| No no-CLI guard covers the receiving lower modules (alphonso, MED) | **Changed**: mission rule + FR-012 text; each WP adds coverage with a plant |
| `is_legacy` / success line must use the same value as the arms (alphonso, MED) | **Changed**: WP06 objective |
| `write_intent not in implement_cores` pin goes vacuous (both, MED) | **Changed**: WP06 re-points it |
| FR-015 lifecycle rows + adapter-wiring planted break; "red on base" wording vs B2* (priti, MED) | **Changed**: WP06 rows + plant; spec FR-015 reworded |
| SC-005 bulk-edit / operational-context / present tests unassigned (priti, MED) | **Changed**: WP09 mandatory direct tests |
| NFR-003 measured once; suites budget unclear (priti, MED) | **Changed**: per-WP timing; characterization/reachability ≤ 60 s each (spec NFR-003) |
| WP03 / WP08 too large (pre-renumbering IDs; priti, MED) | **Changed**: split, now WP04+WP05 and WP10+WP11 |
| Deferred remediation items need issues (priti, MED) | **Changed**: WP12 follow-up 5 |
| `resolve_lanes_dir` name collision; `_find_wp_file` twin; allow-list row (alphonso, MED) | **Changed**: `resolve_lane_state_dir`; twin named; row handled in WP03 |
| Exception-visibility and OptionInfo programmatic-call details; Rich wrapping (alphonso, MED) | **Changed**: WP02 context section |
| git-operations-matrix real path; coverage_breadth baseline; format-exclude entries (priti, LOW) | **Changed**: WP11 owned files and objectives |
| Characterization file matched by globs of later WPs (priti, LOW) | **Changed**: mission rule — `git diff <WP02 tip>` must be empty |
| VcsLockOutcome vs bool; test_resolve_lanes_dir ownership (alphonso, LOW) | **Changed**: contract says bool; WP03 owns it |

### Analyze step (analyst-annie): verdict ready (0 critical/high, 5 medium, 10 low)

- **Folded**:
  - I1, the WP08 pin wording now points at WP09;
  - CV1, two refused-before-placement rows added to WP06;
  - CH1, the cli.console carve-out cites the test_layer_rules precedent plus a follow-up issue;
  - CH2, the pre-existing-failure issue rule is in every WP's validation;
  - I2, the footer is the tool footer, not a model identifier;
  - I3, I4, I5, I6, I7, I8, I9, I10;
  - the I11 phase label;
  - CV2, NFR-006 recording is added to the shared rules.
- **Kept as is**: I11's `create_intent` entries for files created by earlier WPs. They are required
  by `finalize-tasks` literal-path validation.
