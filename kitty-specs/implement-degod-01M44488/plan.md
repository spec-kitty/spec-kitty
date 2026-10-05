# Implementation Plan: Implement command degod (tidy-first)

**Branch**: `issue-5635-implement-degod` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/implement-degod-01M44488/spec.md`

Branch contract (from `setup-plan`):
- Current branch at plan start: `issue-5635-implement-degod`.
- Planning/base branch: `issue-5635-implement-degod`.
- Merge target for completed changes: `issue-5635-implement-degod` (`branch_matches_target: true`).

`spec-kitty consolidate` lands the lanes there, locally only. The branch then reaches `main`
through a PR that the operator merges.

## Summary

Decompose `src/specify_cli/cli/commands/implement.py` (2,304 LOC) without changing behaviour:
- **Thin command.** The command keeps Typer parsing, the JSON-safe wrapper and presentation.
- **Phase sequence.** A phase-sequence sibling module in the command package runs the ordered
  phases.
- **Seam decisions.** Each phase's pure decisions move into the existing seams:
  `core/dependency_graph.py`, `workspace/context.py`, `lanes/implement_support.py`, a new
  `coordination/planning_commit.py` beside `BookkeepingTransaction`, and the status facade.
- **Effect adapters.** Adapters that print stay in command-package siblings.
- **#5232.** The meta-derived placement fallback is replaced by a seam-owned placement
  resolution, sized by a reachability table (FR-015) and guarded by the C-007 escalation.
- **Tests.** Tests move onto the seams, with the patch-site count measured family-wide before and
  after.

The approach follows the 2026-10-04 degod precedents (#5650, #5664, #5679, #5661/#5695):
- characterization and patch-liveness coverage first;
- a verbatim move commit, then a separate adjust commit;
- gates widened or re-pointed, never loosened.

## Engineering Alignment (confirmed)

The operator brief is the engineering alignment. It asks for semi-automatic execution, stopping only
on charter conflicts, real behaviour-change decisions, or a gate that cannot be kept green honestly.
The planning questions were answered from the grounding evidence rather than an interview:

| # | Question | Answer (source) |
|---|---|---|
| 1 | Which phases does implement really have? | The eight named in spec FR-002. Auto-rebase is not on the path (code-grounding §1.2). |
| 2 | Where does each decision go? | The seam homes in IC-02…IC-06 below (code-grounding D3, post-spec squad). |
| 3 | How are stale test patches prevented? | Widen the existing liveness gate first. Moved names lose their command-module re-export (D4, FR-010/011). |
| 4 | How is #5232 delivered without a behaviour change? | A reachability table (FR-015) on real-git fixtures, then the seam-owned placement. Any reachable outcome change escalates (C-007). See research.md R-1. |
| 5 | What must stay byte-identical? | Refusal texts and codes, exit codes, console and JSON output including print order, commits, state files, and the Typer signature (C-001, FR-014). |

Invariants that shape the design:
1. **Side-effect order.** Context → preflight → dependency gate → planning commit (can commit) →
   bulk-edit → operational context → workspace/lane → write-checkout refusals → VCS lock →
   allocate → status start → claim commit.
2. **Validate errors.** Every validate-step failure renders as a tracker error with exit 1.
3. **Claim-commit exceptions.** The claim commit propagates exactly three exception types and
   softens everything else.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor), typed with mypy `--strict` for new and receiving modules
**Primary Dependencies**: typer, rich (CLI layer only); existing internal packages `mission_runtime`, `specify_cli.{status,lanes,workspace,coordination,core}`; no new dependency
**Storage**: Git repository state (branches, commits, worktrees) and mission files (`meta.json`, `status.events.jsonl`, `lanes.json`); unchanged
**Testing**: pytest (+xdist `--dist loadfile`), real-git fixtures for the characterization and reachability suites, seam unit tests without git, and the architectural gate files named in code-grounding §1.5. `make test-fast` is the baseline plus the targeted files; never `make test-full`
**Target Platform**: Linux, macOS, Windows 10+ (CLI); no platform-specific code is added
**Project Type**: single (Python package under `src/`)
**Performance Goals**: implement-direct regression subset ≤ 30 s with `-n auto` (baseline 18.3 s); no CLI latency change (C-001)
**Constraints**: behaviour preserved (C-001), move then adjust (C-002), no new size or ratchet gates (C-003), existing packages only (C-004), complexity ≤ 15 (NFR-001)
**Scale/Scope**: about 1,500 LOC moved out of one 2,304-LOC module into 4 command-package siblings and 5 seam modules, plus about 65 test files touched (re-point or migrate)

No dependency is added, upgraded or removed, so DIRECTIVE_051 supply-chain checks do not apply.

## Charter Check

*Checked before Phase 0 and re-checked after Phase 1.*

| Charter rule | How this plan satisfies it | Status |
|---|---|---|
| Single canonical authority | Each decision moves to its one owning seam. Duplicates are reduced: the claim policy metadata (FR-007) and the placement remedy (FR-018). Dependency-gate dedupe with `status/dependency_verdict.py` is explicitly deferred, not duplicated further. | PASS |
| Architectural alignment / layering | Lower packages never import the CLI layer (C-004). The gates (`test_layer_rules`, `test_status_module_boundary`, `test_cold_import_status_boundary`, `test_commit_router_layering`) run in each moving WP. | PASS |
| DDD + tiered rigour | Core-domain decisions (placement, partition, dependency gate) get seam unit tests plus real-git smokes. Presentation gets payload and golden assertions. | PASS |
| ATDD-first / red-first (SO 4, C-011) | Characterization (FR-009) and liveness widening (FR-010) are the first WP. #5232 lands its FR-015 tests red-first in their own commit before the change. | PASS |
| Campsite cleaning / boy-scout (SO 2, DIRECTIVE_025) | Scoped to touched files: vacuous tests (FR-013), dead helper (FR-018), pre-existing strict errors in `dependency_graph.py` (NFR-002), duplicated metadata helper. | PASS |
| Architectural gate discipline (SO 5) | Scans widened with a planted-violation proof (FR-012). No allow-list added; floor re-calibration only with rationale and planted break. | PASS |
| Canonical sources (SO 6) | Canonical CLI loop and templates. Gaps go to `traces/tooling-friction.md` and get filed. | PASS |
| Git/workflow (SO 7, DIRECTIVE_045) | PR only, topic branch, the operator merges, no push to `main`. | PASS |
| Mission hygiene (SO 8) | Implementer and reviewer are separate, profile-loaded subagents. Issue-matrix rows per FR-017. | PASS |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Targeted files and named gate files only (quickstart.md). | PASS |
| Terminology canon | "Mission" only. "routing" is never used bare. `--mission` only. `test_no_legacy_terminology.py` runs before push. | PASS |

Re-check after Phase 1: no new violations. The five new modules are siblings inside existing
packages (C-004). Complexity Tracking is therefore empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/implement-degod-01M44488/
├── spec.md
├── plan.md                 # this file
├── research.md             # Phase 0: decisions R-1..R-6 + squad dispositions
├── data-model.md           # Phase 1: phase results, seam decision signatures, typed errors
├── quickstart.md           # Phase 1: how to run the regression subset, gates and counter
├── contracts/
│   └── seam-decisions.md   # Phase 1: the seam function contracts the WPs must honour
├── research/               # pre-spec grounding (code-grounding.md, test-remediation.md)
├── tools/count_patch_sites.py   # SC-002 counter (committed at tasks time)
├── traces/                 # tracer files
└── tasks.md + tasks/       # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
├── implement.py                    # THIN: Typer command, _json_safe_output, presentation
├── implement_phases.py             # NEW: ordered phase functions (the implement sequence)
├── implement_planning_commit.py    # NEW: planning-artifact commit adapter (prints, typer.Exit, txn)
├── implement_claim.py              # NEW: status start + claim-commit adapter + pure path bundle
├── implement_recover.py            # NEW: --recover presentation over lanes.recovery
└── implement_cores.py              # existing pure git/placement cores (unchanged role)

src/specify_cli/core/dependency_graph.py        # + claim-precondition decision (pure, snapshot in)
src/specify_cli/workspace/context.py            # + find_wp_file, lanes-dir and target-branch reads
src/specify_cli/lanes/implement_support.py      # + lane lookup, --base resolution, repo-root refusal, VCS-lock prep
src/specify_cli/coordination/planning_commit.py # NEW sibling: partition, guard, demotion predicate,
                                                #   bookkeeping identifiers, candidate enumeration
src/specify_cli/status/ (facade)                # + shared claim-policy-metadata helper (dedupe)

tests/
├── specify_cli/cli/commands/test_implement_characterization.py   # FR-009 (public entry points only)
├── specify_cli/cli/commands/test_implement_placement_reachability.py  # FR-015 (red-first)
├── specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py    # widened (FR-010)
├── specify_cli/core/test_claim_preconditions.py
├── specify_cli/coordination/test_planning_commit.py
├── lanes/test_implement_support_lane_selection.py
├── specify_cli/workspace/test_context_implement_reads.py
└── specify_cli/cli/commands/test_implement_claim.py, test_implement_phases.py
```

**Structure Decision**: a single Python package. Exact new file names may be adjusted by the WP that
creates them, as long as the module stays inside the package named above (C-004) and the gate
lists are widened to include it (FR-012).

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

> Concerns are not work packages; `/spec-kitty.tasks` maps them onto WPs.

### IC-01 — Safety net before any move

- **Purpose**: freeze today's behaviour through public entry points, and make stale patches loud,
  so every later move is provably behaviour-preserving.
- **Relevant requirements**: FR-009, FR-010, FR-013, FR-014, SC-002 (counter), SC-003
- **Affected surfaces**:
  - new `tests/specify_cli/cli/commands/test_implement_characterization.py`;
  - `tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py` (widened to the
    implement family);
  - `kitty-specs/.../tools/count_patch_sites.py`;
  - the vacuous tests named in FR-013.
- **Sequencing/depends-on**: none (first).
- **Risks**:
  - The characterization suite must not patch the implement namespace (FR-009), so failures are
    induced through real fixtures or by patching *external* seams the command calls. Example: make
    `status.start_implementation_status` fail by patching it in `specify_cli.status`, never in
    `implement`.
  - Widening the liveness gate may surface dead implement patches today. Fix them; do not baseline
    them (FR-010).

### IC-02 — Context and dependency gate into the workspace and dependency-graph seams

- **Purpose**: move the context reads (`find_wp_file`, the lane-state dir, the target branch) into
  `workspace/context.py`, and the claim-precondition decision into `core/dependency_graph.py` as a
  pure snapshot-in function.
- **Relevant requirements**: FR-003, FR-006, NFR-002 (fix the 2 pre-existing strict errors in
  `dependency_graph.py`).
- **Affected surfaces**: `implement.py`, `workspace/context.py`, `core/dependency_graph.py`,
  `test_dependency_graph_canceled.py`, `test_trio_read_seam_migration.py` (find_wp_file),
  `dead_symbol_allowlist.yaml` (find_wp_file row), `test_issue_1615…`.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - Cold-import boundary: keep status imports lazy where the gate requires it.
  - Preserve the lane-map derivation `.get("lane", Lane.GENESIS)` exactly; it is pinned, not
    deduplicated.
  - `find_wp_file` has no production importer outside `implement.py`; the other files only
    mention it in docstrings.

### IC-03 — Planning-artifact commit split (verbatim) into coordination decisions plus a command adapter

- **Purpose**: move the ~890-LOC planning-commit block verbatim out of `implement.py`. Pure
  decisions go to `coordination/planning_commit.py` with typed results. The adapter (prints,
  `typer.Exit`, `BookkeepingTransaction` execution, `_commit_recipes` use) goes to
  `cli/commands/implement_planning_commit.py`.
- **Relevant requirements**: FR-004, FR-012, NFR-005.
- **Affected surfaces**:
  - `implement.py` and the two new modules;
  - the 8 test files that import `_ensure_planning_artifacts_committed_git`, and the files
    importing the private planning helpers;
  - `test_wp_integrity_partition_call_shape._IMPLEMENT`;
  - `test_exemption_registry_ratchet.CHURN_SURFACE_MODULES`;
  - `test_trio_seam_only._TRIO_FILES`;
  - `test_no_write_side_rederivation._WRITE_DIR_CONSUMER_MODULES`;
  - `test_meta_fail_closed_full_census_contract`, `test_mid8_contract_sensitive_routing`.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - This is the largest move.
  - The C-006 five-tuple contract of the bookkeeping identifiers must hold.
  - The partition guard keeps raising `commit_router.PrimaryKindReachedCoordStagingError`.
  - `coordination/` must not import `cli` (`test_commit_router_layering`).
  - Run `tests/e2e/test_cli_smoke.py::test_full_workflow_sequence` (the #3371 lesson).

### IC-04 — #5232: seam-owned placement

- **Purpose**: replace the meta-derived placement fallback with the placement seam.
- **Relevant requirements**: FR-008, FR-015, FR-018, SC-004, C-007.
- **Affected surfaces**:
  - `implement_planning_commit.py` (after IC-03), `implement_cores.py` (`_resolve_placement_ref`,
    `_resolve_claim_commit_target`), the phase call site;
  - tests that pin or force the `None` path: `test_coordination_remedy_5113.py`,
    `test_implement_command.py:710`, `test_lane_base_honoring.py:260`,
    `test_issue_2993_lane_planning_ancestry.py`, `test_flat_legacy_none_seam_success_arms.py`
    (INV-7, rewritten, not deleted), `test_implement_writeside.py`, `test_precondition_ref_unification.py`,
    `test_implement_bookkeeping_identifiers.py` (C-006 consumer);
  - `test_wp_integrity_partition_call_shape` floor re-calibration;
  - the CHANGELOG.
- **Sequencing/depends-on**: IC-03, and research.md R-1.
- **Risks**:
  - research.md R-1 selects B2\*, which a 64-state real-git characterization showed byte-identical
    to today, so C-007 is not triggered.
  - The risk is reproducing B2\* faithfully: context first, a typed unresolved-context placement, a
    seam-owned coordination ref (`DECISION_LOG`), and the three degrade arms keyed on the typed
    result.
  - FR-015's committed tests re-create every reachable R-1 row.

### IC-05 — Lane selection and allocation preflight into the lanes seam

- **Purpose**: move the following into `lanes/implement_support.py` with typed errors:
  `_resolve_execution_lane`, `_resolve_active_lanes_manifest` and the origin-preferred base-ref
  family, `_refuse_repo_root_checkout_if_unavailable`, and the VCS-lock decision. The command keeps
  the printed texts.
- **Relevant requirements**: FR-005, C-006.
- **Affected surfaces**: `implement.py`, `lanes/implement_support.py`, `test_implement_base_flag.py`,
  `test_implement_base_ref.py`, `test_lane_base_honoring.py`,
  `test_single_branch_implement_refusals.py`, `dead_symbol_allowlist.yaml` (`_ensure_vcs_in_meta`
  row), and `test_no_write_side_rederivation` if a moved function hits its grammars.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - The single canonical "Base ref … does not resolve" message and the planning-lane warning stay
    byte-identical.
  - The refusals-before-VCS-lock order is pinned.
  - `_ensure_vcs_in_meta` is in `__all__` and the dead-symbol allow-list.

### IC-06 — Claim recording

- **Purpose**: move the claim recording into `cli/commands/implement_claim.py`: status start with its
  error translation, the claim auto-commit with its propagate/soften contract, and
  `_primary_surface_status_paths`. Extract the claim-commit path bundle as a pure function (shapes
  #5673). Dedupe the claim-policy-metadata helper with `agent/workflow_executor.py` into the status
  facade.
- **Relevant requirements**: FR-007, FR-012.
- **Affected surfaces**:
  - `implement.py`, `implement_claim.py`, `status/` (one helper), `agent/workflow_executor.py`
    (call site only);
  - `test_issue_610_head_mismatch_not_swallowed.py`, `test_implement_compact_identity_4665.py`;
  - `test_no_write_side_rederivation` WS#3 allow-list + twin (`_status_commit_destination_branch`
    moves with the claim preflight);
  - `test_implement_placement_routing.py` except-order source pin.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - The except-order source pin freezes the claim-commit `try`. Re-point it to the new home in the
    same commit.
  - Code in `status/` needs in-matrix coverage (diff-cover critical path).

### IC-07 — Thin command and phase sequence

- **Purpose**: turn `implement()` into Typer parsing plus a call to `implement_phases`. Move
  presentation helpers and `--recover` to their siblings or keep them in the thin module.
  `implement()` complexity drops below 15. Re-point the remaining source pins
  (`test_operational_context_wiring`, `test_implement_placement_routing` forbidden-ternary scan).
- **Relevant requirements**: FR-001, FR-002, FR-014, NFR-001, NFR-002 (quarantine entry), SC-001.
- **Affected surfaces**: `implement.py`, `implement_phases.py`, `implement_recover.py`,
  `agent/workflow.py` (unchanged call site; verify only), `test_implement_programmatic_call.py`,
  `test_implement_json_safe_output.py`, `pyproject.toml` (mypy quarantine entry).
- **Sequencing/depends-on**: IC-02, IC-03, IC-05, IC-06.
- **Risks**:
  - The `--json` capture depends on print order, and on the console singleton never being cached.
  - The Typer signature and decorators stay byte-identical (OptionInfo class, #5650).

### IC-08 — Test migration and closing measurements

- **Purpose**: migrate the remaining class-A/B tests (above all `tests/agent/test_implement_command.py`,
  with 54 string targets) onto seams or real fixtures. Report SC-002 with the counter, and check
  SC-005 (one seam unit test per phase). Re-point the docs (FR-016) and draft the issue-matrix rows
  (FR-017).
- **Relevant requirements**: FR-011, FR-016, FR-017, SC-002, SC-005, NFR-003.
- **Affected surfaces**: `tests/agent/test_implement_command.py`, `test_status_emit_on_alloc_failure.py`,
  `test_implement_bulk_edit_planning.py`, `test_implement_vcs_lock_claim.py`,
  `test_implement_runtime_frontmatter_claim.py`, `test_specify_topology_flag.py`, the docs listed in
  FR-016, `docs/changelog/CHANGELOG.md`.
- **Sequencing/depends-on**: IC-07 (and IC-04 for the changelog line).
- **Risks**:
  - Do not edit an assertion to make a migration pass (spec C-002 spirit, brief rule).
  - Add a seam unit test before trimming any e2e test.
  - Keep at least one smoke test per family (test-remediation §5).
