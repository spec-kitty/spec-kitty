# Implementation Plan: Consolidation window provenance and reconciliation split

**Branch**: `kitty/mission-consolidation-window-provenance-01M6Y84D` (Mission branch, `single_branch` topology, not yet settled) | **Target**: `feat/consolidation-window-provenance` (the one PR branch; the operator merges it to `main`) | **Date**: 2026-11-08 | **Spec**: [`kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md`](spec.md)
**Input**: Mission specification from `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md`; issue #7403 (parent sub-epic #7358).

The planning questions were answered by the operator-confirmed Engineering Alignment (2026-11-08), recorded below. No decision is deferred, so this plan carries no `[NEEDS CLARIFICATION]` marker.

## Summary

The consolidation gate rebuilds each work package's span of work from branch history after the fact. Every check keeps its own idea of that span (nine base/window notions on `main`, see [research.md](research.md) §R-02), and the forecast, the fresh run and the resume give `build_approved_wp_set` different inputs. This Mission does four things, in strict phase order on one PR:

1. **Pin, then decide (Phase 1, no behaviour change).** A characterization corpus, a refusal-precedence matrix and an import-surface pin of `consolidation/reconciliation.py` land first, with a `RECONCILIATION_FAMILY` patch helper and its guard. A Proposed ADR records the window model.
2. **Record and unify inputs (Phase 2, no verdict change).** The status pipeline records the window-open SHA, or a typed window gap, under `policy_metadata.wp_window` on a work package's first non-migration move into `claimed` / `in_progress`. It reuses the one lane-head reading already taken for `lane_head`, through the injected probe, so the pipeline stays git-free. One `ClaimInputs` constructor with three sources feeds the forecast, the fresh run and the gate rebuild. The call sites behave exactly as before.
3. **Split (Phase 3, behaviour-preserving).** `reconciliation.py` becomes a re-exporting facade over a shared kernel, one module per check and the verifier/claim orchestration. The corpus shows zero verdict diffs, and at least one seeded mutation per moved check turns a scenario red.
4. **Change behaviour red-first (Phase 4).** Lane missions adopt the window model, with the approval-stamp bound as the fallback and a gap report. A history-read error refuses instead of counting as a deletion (#5048(b)). Resume anchors the closed world on dependency-lane tips frozen at claim capture. The forecast's excluded canceled work packages come from the same source as the fresh run's.

## Engineering Alignment (operator-confirmed 2026-11-08)

- One PR from `feat/consolidation-window-provenance`; work packages land in strict phase order (1 → 2 → 3 → 4).
- Invariants: the event log is the only provenance authority. The Mission adds no refusal code, allowlist entry or suppression. Complexity stays ≤ 15. The rollback authority is untouched. `orchestrator-api` gets the lane check through the shared refusal, with no contract bump.
- Decision Moments already resolved (not reopened): `01M6Y84WAA6RZ8HEAFGAPC1H4R` window_source, `01M6Y84YWCHHTHQXHXDZM4JYZJ` window_unification, `01M6Y851E8G36CZ3257QJWA2Q4` code_change_scope, `01M6Y8540R9E90CF2ZX0HXSXVY` live_defects, `01M6Y85GWA52TX6EDMTD3WKP3C` missing_window_rule, `01M6Y85J76PRYSKGRRSF9NTAJ4` window_writer (see `kitty-specs/consolidation-window-provenance-01M6Y84D/decisions/`).

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; `mypy --strict` on new and changed modules)
**Primary Dependencies**: `typer`, `rich`, `ruamel.yaml`; `spec-kitty-events` (`>=10.5.1,<11`; wall-clock status reducer; `policy_metadata` is an untyped `dict[str, Any]` in its status payload); the git CLI through `kernel.git` / `consolidation/git_probes.py`. No dependency is added, upgraded or removed.
**Storage**: Files only. `kitty-specs/<mission>/status.events.jsonl` (append-only JSONL; the only window authority) and `.kittify/runtime/merge/<mission_id>/state.json` (`ConsolidationState`: run-level anchors such as `pre_interrupt_lane_tips`, `pre_mutation_coord_sha`, `pre_mutation_target_sha`). No new file, sidecar or store.
**Testing**: pytest with real-git fixtures (`tests/consolidation/`, `tests/terminus/` incl. `post_approval_support.build_post_approval_mission`, `tests/status/`, `tests/integration/test_single_branch_approval_windows.py`). Strict `xfail` pins the known residuals. Red-first tests for every Phase 4 behaviour change. Seeded-mutation tests per moved check. Targeted architectural gate files only (NO_FULL_HEAVY_SUITES_IN_MISSION). `ruff check`, `ruff format --check --force-exclude`, `mypy`.
**Target Platform**: the `spec-kitty` CLI on Linux, macOS and Windows; git ≥ 2.38 (squash absorption uses `merge-tree --write-tree`).
**Project Type**: single (Python package `src/specify_cli/`, tests under `tests/`).
**Performance Goals**: the lane window check makes ≤ 2 history queries per approved work package (one per window edge), whatever the lane's commit count (NFR-007). Window capture adds 0 extra git reads per status move: it reuses the one lane-head reading already taken (NFR-006 allows ≤ 1).
**Constraints**: the status package stays git-free (C-002) and inside its cold-import boundary; no new refusal code (C-010), allowlist entry or suppression (NFR-005); cyclomatic complexity ≤ 15 (NFR-004); `rollback.py` remains the only rollback authority (C-009); `ApprovedWpCommitSet`, `Divergence` and the refusal order of `build_approved_wp_set` stay whole (C-006); the facade keeps every pinned name (C-005); no `orchestrator-api` contract bump.
**Scale/Scope**: `reconciliation.py` is 4,096 lines and 115 top-level symbols. It is imported by 11 `src` modules and about 37 test files (79 import lines). After the split, no module exceeds 1,200 lines (NFR-003).

**Supply-chain check (DIRECTIVE_051)**: not applicable. The Mission makes no dependency decision, so no control applies and no adversarial dependency pass is owed.

## Charter Check

*Gate evaluated before Phase 0 and re-checked after Phase 1 design. Source: `.kittify/charter/charter.md`, `spec-kitty charter context --action plan` (compact), profile `architect-alphonso` (directives 001, 003, 031, 032, 041, 043, 044, 051).*

| Charter rule | Verdict | How this plan satisfies it |
|---|---|---|
| Single canonical authority | PASS | The window lives only on status transition events (C-001). `ClaimInputs` is one construction point. `wp_attribution` keeps the window reader rules. |
| Architectural alignment / layer rules | PASS | The status pipeline stays pure: the probe is injected by the two composition shells (`status/emit.py`, `coordination/status_transition.py`). `WP_WINDOW_KEY` is re-exported from the `status` facade, as `LANE_HEAD_KEY` already is (SR-2, `test_status_module_boundary.py`, `test_cold_import_status_boundary.py`). The new modules are flat files under `consolidation/`, inside the existing `specify_cli` layer, with no pyproject package-set change. |
| DDD + terminology adherence | PASS | The spec's Domain Language table governs: work-package window, window-open SHA, window gap, gap report, claim inputs, named window variant. The ADR concern adds glossary entries under `docs/context/orchestration.md`. User-facing text says "Mission" and names the sense of merge (C-012). |
| ATDD-first / red-first (DIRECTIVE_034, 041) | PASS | Phase 1 pins today's behaviour before code moves. Every Phase 4 change commits a failing test first, then the fix (NFR-002). |
| Campsite cleaning (DIRECTIVE_025) | PASS | Phase 1 is the tidy-first enabler. It also reconciles the `--dry-run` docs drift (research R-09) by test, not by reading. |
| Architectural gate discipline (DIRECTIVE_043) | PASS | The patch-lookup guard and the surface pin are non-vacuous: each has a self-mutation control (a removed name fails the pin; a stale patch target fails the guard). The plan adds no allowlist entry. |
| Mutation testing (USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY) | PASS | NFR-008: at least one deterministic seeded mutation per moved check turns a corpus scenario red. |
| Disciplined refactoring | PASS | The split is a pure move behind a facade, after the pins. Behaviour changes come only in Phase 4. |
| `__all__` convention (C-007) | PASS | Every new module declares `__all__`. The facade's `__all__` is unchanged. |
| ADR discipline / citations by slug | PASS | One new Proposed ADR, plus amendment pointers in `2026-10-04-5-approval-stamp-bounds-the-approved-claim` and `2026-09-29-1-closed-world-refuse-on-mixed-lanes`. Citations use the full slug (C-011). The generated ADR index is not hand-edited. |
| Test policy (NO_FULL_HEAVY_SUITES_IN_MISSION) | PASS | Only targeted files and owning subsystem directories run, plus the named architectural gate files (C-013). |
| Mission hygiene (issue matrix) | PASS (heads-up) | This plan cites #7403, #7358, #5721, #5048, #7359, #7362, #5703 and #7283. The ones the Mission owes work (#7403, #5721 bullet, #5048(b)) need issue-matrix rows at review. The context-only ones are marked "Follow-up / see". |
| Version-bump rule for `__init__.py` | PASS (operator ruling 2026-11-08) | CLAUDE.md asks for a version bump plus a changelog fragment on any `__init__.py` change, and re-exporting `WP_WINDOW_KEY` touches `src/specify_cli/status/__init__.py`. **Operator ruling: no version bump.** This matches charter standing order 7 ("no version numbers in scope"). The Mission adds only a changelog fragment under `docs/changelog/unreleased/` and does not touch `pyproject.toml`'s version. The split uses flat modules, so it creates no new `__init__.py`. |
| "No new registry entries" (NFR-005) vs FR-005 | **Interpretation recorded** | FR-005 requires a new row in `DOSSIER_SHA_FIELDS` (`tests/architectural/test_dossier_sha_provenance.py`). That map is a classification registry, not an allowlist or exemption, so it does not count against NFR-005. The re-keyed `dead_symbol_allowlist.yaml` entries move, and their net count stays 0. Adding a module to `CHURN_SURFACE_MODULES` widens a scan, which is stricter, not an exemption. |

Post-design re-check (after `data-model.md` and `contracts/`): no new violation. Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/consolidation-window-provenance-01M6Y84D/
├── spec.md              # committed (entry gate)
├── plan.md              # this file
├── research.md          # Phase 0: decisions + squad findings disposition
├── data-model.md        # Phase 1: WorkPackageWindow, WindowGap, ClaimInputs, wp_window key
├── quickstart.md        # Phase 1: local verification
├── contracts/
│   └── status-event-wp-window.md   # status-event payload extension (JSON Schema + rules)
├── decisions/           # resolved Decision Moments
├── traces/              # mission tracer files (tooling-friction, approach, design-decisions)
└── tasks.md             # NOT created here (/spec-kitty.tasks)
```

### Source Code (repository root)

```
docs/adr/4.x/
└── 2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md   # NEW (Proposed)
docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md              # amendment pointer
docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md                    # amendment pointer
docs/context/orchestration.md                                                       # glossary entries

src/specify_cli/status/
├── lane_head.py              # LaneHeadReading (sha | not-applicable | failure cause); probe returns it
├── transition_pipeline.py    # _stamped_policy_metadata also writes wp_window on opening moves
└── __init__.py               # re-export WP_WINDOW_KEY (facade, SR-2)

src/specify_cli/consolidation/
├── claim_inputs.py                     # NEW (Phase 2): ClaimInputs, ClaimInputSource, the one constructor
├── wp_attribution.py                   # window reader: window_open_of(events, wp_id) -> WindowOpen | WindowGap
├── write_branch_bound.py               # window machinery generalised for lanes (Phase 4)
├── approved_bound.py                   # rule home of the bound (unchanged rules)
├── forecast.py / phase_claim.py / phase_gate.py   # adopt ClaimInputs (Phase 2); gap report (Phase 4)
├── reconciliation.py                   # Phase 3: re-exporting facade (docstring + re-exports only)
├── reconciliation_kernel.py            # NEW: shared kernel (lane branch, dependency ids, anchors, bookkeeping, event log)
├── reconciliation_claim_types.py       # NEW: ApprovedWpCommitSet (whole), content dataclasses
├── reconciliation_rendering.py         # NEW: refusal/clause text helpers
├── reconciliation_closed_world.py      # NEW: excluded collection + external dependency refs
├── reconciliation_bound.py             # NEW: approved bound + write-branch + lane-tip re-check refusals
├── reconciliation_canceled.py          # NEW: mixed-lane + canceled-dependency (one slice)
├── reconciliation_authorship.py        # NEW: authored walk + presence (one slice, one spine walk)
├── reconciliation_verifier.py          # NEW: VerifyStatus, Divergence (whole), VerifyResult, MergeOutcomeVerifier
└── reconciliation_claim.py             # NEW: build_approved_wp_set (refusal order whole) + claim integrity

tests/consolidation/
├── reconciliation_family.py                       # NEW (Phase 1): RECONCILIATION_FAMILY + patch helper
├── test_reconciliation_family_guard.py            # NEW: patched-name-is-looked-up guard (+ control)
├── test_reconciliation_surface_pin.py             # NEW: name set + object identity (+ removed-name control)
├── characterization/verdict_corpus.json           # NEW: golden verdict matrix
├── test_reconciliation_characterization.py        # NEW: corpus runner (forecast / fresh / resume)
├── test_refusal_precedence_matrix.py              # NEW: pairwise precedence (+ swapped-order control)
├── test_reconciliation_seeded_mutations.py        # NEW (Phase 3): ≥1 mutation per moved check
├── test_claim_inputs_parity.py                    # NEW (Phase 2/4)
└── test_lane_approval_windows.py                  # NEW (Phase 4, red-first)
tests/status/test_wp_window_capture.py             # NEW (Phase 2)
tests/architectural/test_dossier_sha_provenance.py # + policy_metadata.wp_window.open_sha (BRANCH_RELATIVE)
tests/ci/test_reducer_lock_census.py               # owner path follows build_approved_wp_set (Phase 3)
tests/architectural/dead_symbol_allowlist.yaml     # re-key moved symbols, net 0 (Phase 3, only if required)
```

**Structure Decision**: a single Python project. The split uses **flat sibling modules** with a `reconciliation_` prefix, not a subpackage. Two reasons: a subpackage cannot share the name of the facade module `reconciliation.py`, and a new `__init__.py` would bring in the version-bump rule. Module ownership in `.github/ci-module-registry.yml` is by directory glob, so the registry needs no edit.

## Complexity Tracking

No Charter Check violation needs a justification. (`ApprovedWpCommitSet` keeps its width, and the facade keeps re-exporting private names. Both are deliberate and temporary, spec C-005/C-006. Migrating callers off the facade is out of scope.)

## Implementation Concern Map

> **Note**: Implementation concerns are NOT work packages and are NOT executable units.
> `/spec-kitty.tasks` translates these into executable WPs — one concern may become
> multiple WPs; multiple small concerns may merge into one WP. Do not label concerns
> with WP-style IDs or sequencing language.

Phases are strict: no concern of a later phase may land before every concern of the earlier phase. Each concern carries a **model tier** for implementer routing: *cheap* (mechanical, a pin or a pure move, verifiable by an existing gate), *mid* (bounded judgment against a clear oracle), *top* (design judgment, soundness-critical behaviour, or ADR authorship).

### Phase 1 — Pin and decide (no behaviour change)

#### IC-01 — Window-model ADR, amendment pointers and glossary
- **Purpose**: Write the Proposed ADR, so every later change to a check follows one recorded rule. It covers where the window is recorded, the typed window gap, `ClaimInputs` with its three sources, the durability horizon, the missing-window fallback, and a table mapping all nine base/window notions to the window model or to a named window variant.
- **Relevant requirements**: FR-001, C-001, C-010, C-011, C-012; links FR-006's issue once filed.
- **Affected surfaces**: `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` (new); amendment pointers in `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` and `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md`; `docs/context/orchestration.md` glossary entries. Do not hand-edit the ADR index (generated).
- **Sequencing/depends-on**: none (it may run alongside IC-02..IC-05).
- **Risks**: ADR prefix collisions (three `2026-09-29-1-*` files), so cite by slug. The ADR names the `blocked` opener asymmetry as a variant, it does not unify it. It states the two recording tiers: work-package transition → event log; run claim → `state.json`. It states that rollback is out of scope (#7359), and names #5703 as a limit.
- **Model tier**: **top**.

#### IC-02 — Characterization corpus (verdict matrix)
- **Purpose**: Before any code moves, pin the verdict status, refusal code, divergence fields and exit code across mode (forecast / fresh / resume) × lane shape (single lane, two-WP lane, mixed lane with a canceled WP, fully canceled dependency, planning lane, `single_branch`) × stamp state (present, missing, rewritten). The matrix includes today's known-wrong cases as strict `xfail` pins of the intended verdict: the forecast's canceled-WP input, live closed-world anchors on resume, the #5048(b) deletion inference, and the commit between two approvals.
- **Relevant requirements**: FR-016, NFR-001, NFR-002, SC-005, C-008.
- **Affected surfaces**: `tests/consolidation/test_reconciliation_characterization.py`, `tests/consolidation/characterization/verdict_corpus.json`. The builders are reused from `tests/terminus/post_approval_support.py`, the canceled-lane builders and `tests/consolidation/test_reconciliation.py` fixtures.
- **Sequencing/depends-on**: none.
- **Risks**: Count the residuals from the test files, not from the prose (research R-13). Pin the `--dry-run` verdict for a post-approval fixture, to settle the docs drift (R-09). A corpus that shells out must not depend on a stale editable install. The golden file needs a deterministic order and normalised SHAs, so it is stable across runs.
- **Model tier**: **mid**. Choosing the scenarios is judgment; generating the golden file is mechanical.

#### IC-03 — Refusal-precedence matrix
- **Purpose**: A table-driven pin of the claim-time refusal text and order for every pair of `build_approved_wp_set` refusals that can occur together, with a deliberately swapped-order control. Then the split cannot reorder refusals unnoticed.
- **Relevant requirements**: FR-017, C-006.
- **Affected surfaces**: `tests/consolidation/test_refusal_precedence_matrix.py`.
- **Sequencing/depends-on**: none.
- **Risks**: The order today is dependency refs → unresolvable branches → canceled dependency → mixed lane → bound → evidence → presence → authored → excluded, with `_compound_refusal` appending the bound after "This Mission also has:". Pairs that cannot co-occur must be listed as such, not silently skipped.
- **Model tier**: **mid**.

#### IC-04 — Import-surface pin of `reconciliation.py`
- **Purpose**: Pin every name importable from `specify_cli.consolidation.reconciliation`, public and private, that `src` and tests reach, together with each name's object identity. Add a control showing that a removed name fails the pin.
- **Relevant requirements**: FR-018, C-005.
- **Affected surfaces**: `tests/consolidation/test_reconciliation_surface_pin.py`, plus a checked-in name list generated from the current module and an AST scan of `src/` and `tests/`.
- **Sequencing/depends-on**: none.
- **Risks**: Low. Generate the list from code, never by hand.
- **Model tier**: **cheap**.

#### IC-05 — `RECONCILIATION_FAMILY` patch helper and lookup guard
- **Purpose**: A helper modelled on `tests/consolidation/executor_family.py` that patches a name in every family module whose namespace binds it. A guard fails when a test string-patches `specify_cli.consolidation.reconciliation.<name>` and that module does not itself look `<name>` up. Without it, a patch would go silently vacuous after the move.
- **Relevant requirements**: FR-020.
- **Affected surfaces**: `tests/consolidation/reconciliation_family.py`, `tests/consolidation/test_reconciliation_family_guard.py`. Before the split the family is just `(reconciliation,)` and the guard passes; it is non-vacuous through a seeded stale-patch control.
- **Sequencing/depends-on**: none.
- **Risks**: The guard must detect `monkeypatch.setattr("<dotted>", ...)`, `mock.patch("<dotted>")` and `setattr(module, ...)` forms.
- **Model tier**: **cheap to mid**.

### Phase 2 — Record and unify inputs (no verdict change)

#### IC-06 — Window-open capture on the opening transition
- **Purpose**: Record the window-open SHA, or a typed window gap, under `policy_metadata.wp_window` on every non-migration move of a lane-mapped work package into `claimed` / `in_progress`. Readers bind to the first such event. The reading is the same lane-head reading the `lane_head` stamp already uses, so this adds no extra git read. The status pipeline stays git-free, and a move is never refused.
- **Relevant requirements**: FR-002, FR-003, NFR-006, C-002, C-003; contract `contracts/status-event-wp-window.md`.
- **Affected surfaces**: `src/specify_cli/status/lane_head.py` (`LaneHeadReading`; the probe returns a reading, and `probe_lane_head` stays a thin sha adapter for existing callers); `src/specify_cli/status/transition_pipeline.py` (`_stamped_policy_metadata`); `src/specify_cli/status/__init__.py` (`WP_WINDOW_KEY` re-export); the two composition shells; a changelog fragment under `docs/changelog/unreleased/` (no version bump, operator ruling 2026-11-08).
- **Sequencing/depends-on**: IC-01 (key shape), Phase 1 complete.
- **Risks**: Keep `lane_head` byte-identical for every existing event shape. A not-applicable reading (planning lane, unassigned WP, no `lanes.json`) writes no key, while a failure of a lane-mapped WP writes a gap. The migration-actor check (`is_migration_actor`) is pure. The cold-import boundary stays clean: `LaneHeadReading` lives at module top level with no heavy imports.
- **Model tier**: **top**.

#### IC-07 — Window reader, gap typing and dossier SHA classification
- **Purpose**: One reader in `wp_attribution` classifies a work package's window opening as `WindowOpen(sha)` or `WindowGap(reason)`. The reasons are: not recorded (no key on the first opening event); capture failed (with the recorded cause); not on lane (the recorded SHA is not an ancestor of the lane tip). The reader classifies per event, so a log that straddles the upgrade still reads. The new SHA key is classified `BRANCH_RELATIVE`.
- **Relevant requirements**: FR-004, FR-005, C-001.
- **Affected surfaces**: `src/specify_cli/consolidation/wp_attribution.py`; `tests/architectural/test_dossier_sha_provenance.py` (`("status.events.jsonl", "policy_metadata.wp_window.open_sha")`); unit tests.
- **Sequencing/depends-on**: IC-06.
- **Risks**: The reader is the only place the window-opener rule lives; `approval_window_open_stamp` keeps its contract for `single_branch` until IC-13. "Not on lane" needs the lane tip from `ClaimInputs`, so the ancestry check is a reader parameter, not a git read inside the classifier.
- **Model tier**: **mid**.

#### IC-08 — `ClaimInputs` and its one constructor
- **Purpose**: One frozen value with these fields: target base, coordination base, frozen lane tips, frozen dependency anchors, dependency pins, excluded canceled work packages, strategy, the status directory read, and its source (`LIVE` for the forecast, `LIVE_THEN_SAVED` for a fresh run, `SAVED` for a resume). It is built by one constructor and adopted by `forecast.py`, `phase_claim.py` and `phase_gate.py`. **Phase 2 keeps every per-mode quirk exactly**, including the forecast's empty excluded set and the gate rebuild's live `mission_branch`, so zero verdicts change. A parity test pins the equal fields, and pins the known divergences as strict `xfail`.
- **Relevant requirements**: FR-012 (construction point), FR-013 (parity test scaffold), C-004.
- **Affected surfaces**: `src/specify_cli/consolidation/claim_inputs.py` (new), with a thin `build_claim(..., inputs)` adapter that calls `build_approved_wp_set` with today's keyword arguments (`reconciliation.py` is untouched in Phase 2); `forecast.py`, `phase_claim.py`, `phase_gate.py`; `tests/consolidation/test_claim_inputs_parity.py`.
- **Sequencing/depends-on**: Phase 1 complete (the corpus guards zero verdict change).
- **Risks**: The resume path's fail-closed anchor checks (`_enforce_resume_anchor_integrity`, `lane_tip_cas_ok`) must keep running before the constructor resolves a base. The frozen dependency anchors are derived from `ConsolidationState.pre_interrupt_lane_tips` (dependency lanes are Mission lanes); confirm coverage before Phase 4 relies on it. Keep every function ≤ 15 complexity, with one small resolver per source.
- **Model tier**: **mid to top**.

#### IC-09 — Cross-repository writer issue
- **Purpose**: File a spec-kitty-events issue asking the Java write service to write, preserve and type `policy_metadata.wp_window` with the same shape and rules. Link it from the ADR.
- **Relevant requirements**: FR-006, C-003.
- **Affected surfaces**: GitHub `spec-kitty/spec-kitty-events` (an outward-facing write: confirm with the operator before posting); the ADR link.
- **Sequencing/depends-on**: IC-01 (contract text), IC-06 (final key shape).
- **Risks**: None technical. It is a GitHub write, so it needs operator authorization.
- **Model tier**: **cheap**.

### Phase 3 — Behaviour-preserving split

#### IC-10 — Shared kernel and claim types extraction
- **Purpose**: Move the shared kernel symbols (`_lane_branch_for`, `_dependency_lane_ids`, `_APPROVED_MEMBERSHIP_LANES`, `_closed_world_anchors`, `_lane_is_approved`, `_lane_tip_commits`, `_lane_first_parent_spine`, `_is_bookkeeping` and its nested-alias helper and regexes, `_ClaimEventLog`, `_planning_prefix`, `_refused`, `_LaneWalk`) and the whole `ApprovedWpCommitSet` with its content dataclasses into their own modules, re-exported by the facade. Field order stays as it is (some constructions are positional).
- **Relevant requirements**: FR-019, C-005, C-006, NFR-001.
- **Affected surfaces**: `reconciliation_kernel.py`, `reconciliation_claim_types.py`, `reconciliation.py` (facade re-exports).
- **Sequencing/depends-on**: Phase 2 complete.
- **Risks**: Function-local imports move with their functions, and are not hoisted. Check `CHURN_SURFACE_MODULES` (`tests/architectural/test_exemption_registry_ratchet.py`) for the module that receives `_is_bookkeeping`.
- **Model tier**: **cheap** (pure move, oracle = corpus + surface pin).

#### IC-11 — One module per check, verifier and claim orchestration
- **Purpose**: Move each check into its own module behind the facade: rendering; closed world, including external dependency refs; approved bound, with write-branch and the lane-tip re-check refusal; the canceled pair (mixed lane + canceled dependency, one slice); authorship + presence (one slice, one spine walk); the verifier, with `Divergence` and `VerifyResult` whole; and claim orchestration, with `build_approved_wp_set` and its refusal order whole. Add one seeded mutation per moved check that turns a corpus scenario red.
- **Relevant requirements**: FR-019, NFR-001, NFR-003, NFR-004, NFR-008, C-006, C-007, SC-005, SC-006.
- **Affected surfaces**: `reconciliation_rendering.py`, `reconciliation_closed_world.py`, `reconciliation_bound.py`, `reconciliation_canceled.py`, `reconciliation_authorship.py`, `reconciliation_verifier.py`, `reconciliation_claim.py`; `reconciliation.py` reduced to the docstring plus re-exports; `tests/consolidation/test_reconciliation_seeded_mutations.py`.
- **Sequencing/depends-on**: IC-10. The order within the phase is free, but the authorship + presence slice should move last: it is the most-fixed region, and `test_presence_lane_base.py` pins its single walk.
- **Risks**: Precedence drift is caught by IC-03. A moved name hit by a string patch is caught by IC-05's guard. Keep a moved function's complexity unchanged; do not fix it in passing. Keep each module ≤ 1,200 lines.
- **Model tier**: **cheap** for the rendering, closed-world, bound and verifier moves; **mid** for the canceled pair, authorship + presence, and the seeded mutations.

#### IC-12 — Patch retargeting and literal-pin housekeeping
- **Purpose**: Retarget every string patch on a moved name through `RECONCILIATION_FAMILY`, or to the name's lookup home. Update the literal pins that name the old module: the owner path in `tests/ci/test_reducer_lock_census.py`; `TERMINUS_ENTRY_POINTS` / `UnroutedTerminusPathError` in `dead_symbol_allowlist.yaml` (keep them defined in place if the contract test requires that, otherwise re-key with net 0); and a fresh-interpreter import smoke test per new module.
- **Relevant requirements**: FR-020, NFR-005, C-005.
- **Affected surfaces**: `tests/consolidation/test_reconciliation.py`, `test_canceled_dependency_attribution.py`, `test_presence_lane_base.py`, `tests/terminus/test_resume_refuses_committed_staged_deletions.py` and the other patch sites the guard flags; the census and allowlist files.
- **Sequencing/depends-on**: runs alongside IC-10/IC-11 (each move carries its own retargets).
- **Risks**: Low. The guard makes a missed retarget fail.
- **Model tier**: **cheap**.

### Phase 4 — Behaviour changes, red-first

#### IC-13 — Lane missions adopt the window model, with fallback and gap report
- **Purpose**: On a code lane, each approved work package with a `WindowOpen` covers only `(window-open SHA, newest approval stamp]`. A work package with a `WindowGap` falls back to a degraded window `(claim base, approval stamp]`, which is exactly today's approval-stamp coverage. A lane commit outside every window and every existing anchor is refused with `LANE_MOVED_AFTER_APPROVAL`, naming the commit and the work package approved before it. The fresh run, the resume and the forecast list every fallback work package with its gap reason, in human and JSON output. `single_branch` reads the recorded window-open SHA when present and reports its absence.
- **Relevant requirements**: FR-007, FR-008, FR-009, FR-010, FR-011, NFR-002, NFR-007, C-010, SC-001, SC-002.
- **Affected surfaces**: `reconciliation_bound.py` (lane leg of the approved-bound verdict), `write_branch_bound.py` (window machinery shared with lanes: `approval_windows`, `_window_reach`, `_preceding_wp`, `_outside`), `wp_attribution.py`, `claim_inputs.py`, gap rendering in the consolidate/forecast output, `tests/consolidation/test_lane_approval_windows.py`, `tests/terminus/`. `orchestrator-api` inherits the check through `approved_bound_refusal`, with no envelope change.
- **Sequencing/depends-on**: Phase 3 complete; IC-07, IC-08.
- **Risks**: Over-refusal (FR-008): commits a reviewer made during review, rework before re-approval, and attested approvals must pass on the same fixture. A lane where every work package has a gap must reproduce today's verdict byte for byte (US3). The only expected corpus flips are the IC-02 `xfail` scenarios for the commit between two approvals. Keep 2 history queries per approved work package.
- **Model tier**: **top**.

#### IC-14 — A history-read error is never a deletion (#5048(b))
- **Purpose**: In the authored walk, distinguish a genuinely absent path from a probe failure, using `git_probes.path_state_at`, which returns `None` only when the path is absent. A read failure refuses the claim through the existing claim-time refusal path, naming the path and the error. A genuine deletion is still recorded.
- **Relevant requirements**: FR-014, NFR-002, SC-004.
- **Affected surfaces**: `reconciliation_authorship.py` (`_final_authored_walk`), red-first test with an injected probe error, plus a positive control.
- **Sequencing/depends-on**: Phase 3 complete (the fix lands in the moved module).
- **Risks**: No new refusal code; reuse the existing unreadable-history refusal wording. Do not add a second git read per path beyond the one `path_state_at` replaces, and keep the single spine walk.
- **Model tier**: **mid**.

#### IC-15 — Resume anchors the closed world on frozen dependency-lane tips
- **Purpose**: On `--resume`, `_closed_world_anchors` takes the dependency-lane tips from `ClaimInputs` (`SAVED` source, frozen at claim capture), not from live branch names. A dependency lane that moved after the interruption no longer widens what is exempt. A fresh run keeps its verdict.
- **Relevant requirements**: FR-015, NFR-002, SC-004.
- **Affected surfaces**: `reconciliation_kernel.py` / `reconciliation_closed_world.py` (anchor source threaded from `ClaimInputs`), `claim_inputs.py`, red-first resume test.
- **Sequencing/depends-on**: IC-08, Phase 3 complete.
- **Risks**: The other axes that call `_closed_world_anchors` (five in all) must get the same frozen anchors, or none of them may change. The planning-lane exclusion and the fully-canceled exclusion stay. A pre-upgrade record with no frozen tip for a dependency lane keeps today's live read, and the ADR names this as a degraded anchor. The gate re-check already uses frozen SHAs (`run.bound_anchor_shas`) and must stay consistent.
- **Model tier**: **top**.

#### IC-16 — Forecast uses the fresh run's excluded canceled work packages
- **Purpose**: The `LIVE` source derives the excluded canceled work packages the way the fresh run does, so the forecast and the fresh run produce equal claim inputs on an unmutated state. The parity `xfail` from IC-08 flips to pass.
- **Relevant requirements**: FR-012, FR-013, NFR-002, SC-003.
- **Affected surfaces**: `claim_inputs.py`, `forecast.py`, `tests/consolidation/test_claim_inputs_parity.py`.
- **Sequencing/depends-on**: IC-08, Phase 3 complete.
- **Risks**: If characterization shows a forecast verdict change, it is red-first and limited to the scenarios named in NFR-002. The forecast still does not run the verify-side checks it skips today (see #7362).
- **Model tier**: **mid**.

### Concern-to-requirement coverage

| Requirement | Concern(s) |
|---|---|
| FR-001 | IC-01 |
| FR-002, FR-003 | IC-06 |
| FR-004, FR-005 | IC-07 |
| FR-006 | IC-09 |
| FR-007, FR-008, FR-009, FR-010, FR-011 | IC-13 |
| FR-012, FR-013 | IC-08, IC-16 |
| FR-014 | IC-14 |
| FR-015 | IC-15 |
| FR-016 | IC-02 |
| FR-017 | IC-03 |
| FR-018 | IC-04 |
| FR-019 | IC-10, IC-11 |
| FR-020 | IC-05, IC-12 |
| NFR-001, NFR-003, NFR-008 | IC-02, IC-11 |
| NFR-002 | IC-13..IC-16 |
| NFR-004, NFR-005, NFR-009 | every concern |
| NFR-006 | IC-06 |
| NFR-007 | IC-13 |
