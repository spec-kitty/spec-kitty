# Implementation Plan: Consolidation window provenance and reconciliation split

**Branch**: `kitty/mission-consolidation-window-provenance-01M6Y84D` (Mission branch, also the coordination branch: `finalize-tasks` settled the topology to `lanes_with_coord`; `meta.json` is the authority) | **Target**: `feat/consolidation-window-provenance` (the one PR branch; the operator merges it to `main`) | **Date**: 2026-11-08 | **Spec**: [`kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md`](spec.md)
**Input**: Mission specification from `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md`; issue #7403 (parent sub-epic #7358).

The planning questions were answered by the operator-confirmed Engineering Alignment (2026-11-08), recorded below. No decision is deferred, so this plan carries no `[NEEDS CLARIFICATION]` marker.

## Summary

The consolidation gate rebuilds each work package's span of work from branch history after the fact. Every check keeps its own idea of that span (nine base/window notions on `main`, see [research.md](research.md) §R-02), and the forecast, the fresh run and the resume give `build_approved_wp_set` different inputs. This Mission does four things, in strict phase order on one PR:

1. **Pin, then decide (Phase 1, no behaviour change).** A characterization corpus (golden file of today's actual verdicts, with a window-state axis), a refusal-precedence matrix and an import-surface pin of `consolidation/reconciliation.py` land first, with a `RECONCILIATION_FAMILY` patch helper and its guard, and a seeded-mutation test that proves the corpus can fail before any code moves. A Proposed ADR records the window model.
2. **Record and unify inputs (Phase 2, no verdict change).** The status pipeline records the window-open SHA, or a typed window gap ("capture failed" or "lane branch missing"), under `policy_metadata.wp_window` on every non-migration move of a lane-mapped work package into `claimed` / `in_progress`; the reader picks the window opener (FR-021). It reuses the one lane-head reading already taken for `lane_head`, through the injected probe, so the pipeline stays git-free. One `ClaimInputs` constructor with three sources feeds the forecast, the fresh run and the gate rebuild. The call sites behave exactly as before.
3. **Split (Phase 3, behaviour-preserving).** `reconciliation.py` becomes a re-exporting facade over a shared kernel, one module per check and the verifier/claim orchestration. The corpus shows zero verdict diffs, and at least one seeded mutation per moved check turns a scenario red.
4. **Change behaviour red-first (Phase 4).** Lane missions adopt the window model: the lane's own approval stamps stop exempting its commits, other lanes' approval stamps stay exemption anchors, the approval-stamp bound is the fallback (today's check unchanged on an all-gap lane) and a gap report lists the fallbacks. A history-read error refuses instead of counting as a deletion (#5048(b)). Resume feeds one frozen claim-time anchor set to the closed world, the approved bound, the fully-canceled-lane check and the attestation check. The forecast's excluded canceled work packages and resolved coordination base come from the same source as the fresh run's. Every red-first test drives `consolidate`, `--dry-run` or `--resume` (NFR-010).

## Engineering Alignment (operator-confirmed 2026-11-08)

- One PR from `feat/consolidation-window-provenance`; work packages land in strict phase order (1 → 2 → 3 → 4).
- Invariants: the event log is the only provenance authority. The Mission adds no refusal code, allowlist entry or suppression. Complexity stays ≤ 15. The rollback authority is untouched. `orchestrator-api` gets the lane check through the shared refusal, with no contract bump.
- Decision Moments already resolved (not reopened): `01M6Y84WAA6RZ8HEAFGAPC1H4R` window_source, `01M6Y84YWCHHTHQXHXDZM4JYZJ` window_unification, `01M6Y851E8G36CZ3257QJWA2Q4` code_change_scope, `01M6Y8540R9E90CF2ZX0HXSXVY` live_defects, `01M6Y85GWA52TX6EDMTD3WKP3C` missing_window_rule, `01M6Y85J76PRYSKGRRSF9NTAJ4` window_writer (see `kitty-specs/consolidation-window-provenance-01M6Y84D/decisions/`).
- Post-plan squad rulings (operator, 2026-11-08; not reopened): `01M6YAFYHT0RMVZB03THW1WWSE` lane_anchor_set (the lane's own approval stamps no longer exempt on the window path; other lanes' approved tips stay exemption anchors; SC-001/FR-007 state the exception; dependency-chain fixture), `01M6YAFZVZAYR4G20Q2X4PN0FT` resume_anchor_scope (one frozen claim-time anchor set feeds the closed world and the approved bound on resume; each flip named in NFR-002 with a red-first test through `consolidate --resume`), `01M6YAG16WDVMM37HCJCHAC5YW` window_opener (FR-021), `01M6YAG2HE6Q2XNQMGK6X3MBEK` events_issue_filing (filed: spec-kitty/spec-kitty-events#229).

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; `mypy --strict` on new and changed modules)
**Primary Dependencies**: `typer`, `rich`, `ruamel.yaml`; `spec-kitty-events` (`>=10.5.1,<11`; wall-clock status reducer; `policy_metadata` is an untyped `dict[str, Any]` in its status payload); the git CLI through `kernel.git` / `consolidation/git_probes.py`. No dependency is added, upgraded or removed.
**Storage**: Files only. `kitty-specs/<mission>/status.events.jsonl` (append-only JSONL; the only window authority) and `.kittify/runtime/merge/<mission_id>/state.json` (`ConsolidationState`: run-level anchors such as `pre_interrupt_lane_tips`, `pre_mutation_coord_sha`, `pre_mutation_target_sha`). No new file, sidecar or store.
**Testing**: pytest with real-git fixtures (`tests/consolidation/`, `tests/terminus/` incl. `post_approval_support.build_post_approval_mission`, `tests/status/`, `tests/integration/test_single_branch_approval_windows.py`). Strict `xfail` pins the known residuals. Red-first tests for every Phase 4 behaviour change. Seeded-mutation tests per moved check. Targeted architectural gate files only (NO_FULL_HEAVY_SUITES_IN_MISSION). `ruff check`, `ruff format --check --force-exclude`, `mypy`.
**Target Platform**: the `spec-kitty` CLI on Linux, macOS and Windows; git ≥ 2.38 (squash absorption uses `merge-tree --write-tree`).
**Project Type**: single (Python package `src/specify_cli/`, tests under `tests/`).
**Performance Goals**: the lane window check makes O(approved work packages + exemption anchors) history queries plus a constant per refused commit, whatever the lane's commit count; the exempt set is computed once per lane and shared by the stamp check and the window check (NFR-007, counted at the `git_probes` / `kernel.git` history-helper seam). Window capture adds 0 extra git reads per status move: it reuses the one lane-head reading already taken (NFR-006 allows ≤ 1).
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
| Mutation testing (USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY) | PASS | NFR-008: at least one deterministic seeded mutation per moved check turns a corpus cell red. The corpus computes verdicts in process, so a mutation reaches it (IC-17); the mutation test lands in Phase 1, before the split, and is re-run after it. |
| Disciplined refactoring | PASS | The split is a pure move behind a facade, after the pins. Behaviour changes come only in Phase 4. |
| `__all__` convention (good practice; not a spec constraint, and the charter `__all__` rule binds only `src/charter` and `src/kernel`) | PASS | Every new module declares `__all__`. The facade's `__all__` is unchanged. |
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
├── test_reconciliation_seeded_mutations.py        # NEW (Phase 1, re-run Phase 3): ≥1 mutation per check + mutation table
├── test_claim_inputs_parity.py                    # NEW (Phase 2/4)
├── test_lane_approval_windows.py                  # NEW (Phase 4, red-first through consolidate / --dry-run)
└── test_resume_frozen_anchors.py                  # NEW (Phase 4, red-first through consolidate --resume, SIGKILL harness)
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

Phases are strict: no concern of a later phase may land before every concern of the earlier phase.

**Cross-cutting constraints (every concern)**: C-009 (no rollback or branch-restore caller outside `rollback.py`; `tests/consolidation/test_single_rollback_authority.py` stays green), C-013 (targeted test runs only: the changed tests, their owning subsystem directories and the named architectural gate files) and C-014 (ruff, ruff format and mypy with zero findings and no new suppressions) bind every IC below, as do NFR-004, NFR-005 and NFR-009. Each work package's review checks them; they are not repeated per IC. Each concern carries a **model tier** for implementer routing: *cheap* (mechanical, a pin or a pure move, verifiable by an existing gate), *mid* (bounded judgment against a clear oracle), *top* (design judgment, soundness-critical behaviour, or ADR authorship).

### Phase 1 — Pin and decide (no behaviour change)

#### IC-01 — Window-model ADR, amendment pointers and glossary
- **Purpose**: Write the Proposed ADR, so every later change to a check follows one recorded rule. It covers where the window is recorded, the typed window gap, `ClaimInputs` with its three sources, the durability horizon, the missing-window fallback, and a table mapping all nine base/window notions to the window model or to a named window variant.
- **Relevant requirements**: FR-001, C-001, C-010, C-011, C-012; links FR-006's issue once filed.
- **Affected surfaces**: `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` (new); amendment pointers in `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` and `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md`; `docs/context/orchestration.md` glossary entries. Do not hand-edit the ADR index (generated).
- **Sequencing/depends-on**: none (it may run alongside IC-02..IC-05).
- **Risks**: ADR prefix collisions (three `2026-09-29-1-*` files), so cite by slug. The ADR names the `blocked` opener asymmetry as a variant, it does not unify it. It states the two recording tiers: work-package transition → event log; run claim → `state.json`. It states that rollback is out of scope (#7359), and names #5703 as a limit.
- **Post-plan rulings the ADR records**: the window opener (FR-021: cycle after the last rewind to `planned`, review rejections non-resetting, leading "lane branch missing" openers skipped, topology order with log-order fallback); the exemption anchors on the window path (closed-world anchors + other lanes' approval stamps, never the lane's own) and the dependency-chain exception; one frozen anchor set on resume for all four anchor consumers; spec-kitty/spec-kitty-events#229 as the FR-006 issue.
- **Named residuals the ADR records**: parallel claims on one lane and a claim parked without returning to `planned` (over-wide window, strict `xfail`); the rewind boundary itself is found in event-log order (clock skew across the boundary is not topology-corrected); degraded anchors on resume (pre-upgrade record; status surface unresolvable at capture, so no tip was frozen); a full-restore re-baseline (#6770) makes the next resume a fresh capture by design; a canceled set that changes between capture and resume only refuses (H5) or drops anchors, both safe; the window downgrade is invisible on `orchestrator-api` (no gap report in its envelope).
- **Model tier**: **top**.

#### IC-02 — Characterization corpus (verdict matrix)
- **Purpose**: Before any code moves, pin the verdict status, refusal code, divergence fields and exit code across mode (forecast / fresh / resume) × lane shape (single lane, two-WP lane, mixed lane with a canceled WP, fully canceled dependency, dependency chain, planning lane, `single_branch`) × approval-stamp state (present, missing, rewritten) × **window state** (recorded, not recorded, capture failed, lane branch missing, not on lane). The window state is set explicitly per cell by stripping or injecting `wp_window` after the builder runs, never left to which builder wrote the events; before Phase 4 every window state must give today's verdict. `verdict_corpus.json` records today's **actual** verdict for every cell, the known-wrong ones included. Each intended verdict is a separate strict `xfail(raises=AssertionError)` test (the `test_approved_bound_residuals.py` precedent): the forecast's canceled-WP input and live coordination base, live anchors on resume (closed world, approved bound, fully-canceled lane), the #5048(b) deletion inference, the commit between two approvals (incl. the gap-then-recorded mixed lane), the rewound work package. Named-residual cells: parallel claims on one lane (strict `xfail`). Exception and weaker-check cells pinned as passing: the dependency chain (FR-007 exception), a gap WP covering a stray before a recorded WP (US3-4), an all-gap lane with a post-approval commit whose refusal **text** is pinned (FR-023), a skewed-clock rework, a leading branch-missing opener.
- **Relevant requirements**: FR-016, NFR-001, NFR-002, SC-005, C-008.
- **Affected surfaces**: `tests/consolidation/test_reconciliation_characterization.py`, `tests/consolidation/characterization/verdict_corpus.json`. The builders are reused from `tests/terminus/post_approval_support.py`, the canceled-lane builders and `tests/consolidation/test_reconciliation.py` fixtures.
- **Sequencing/depends-on**: none.
- **Risks**: Count the residuals from the test files, not from the prose (research R-13). Pin the `--dry-run` verdict for a post-approval fixture, to settle the docs drift (R-09). The runner computes verdicts **in process** (the Typer `CliRunner` or the direct `consolidate` entry, with the existing per-test HOME isolation), so seeded mutations reach it (IC-17) and no stale editable install is involved; resume cells reach their interrupted state with the SIGKILL harness, then resume in process. The golden file needs a deterministic order and normalised SHAs, so it is stable across runs. NFR-001 = golden unchanged; NFR-002 = golden diff ⊆ named cells, each with its `xfail` removed in its fix commit — both checkable by machine.
- **Model tier**: **mid to top**. The window-state axis and the in-process runner are design judgment; generating the golden file is mechanical.

#### IC-03 — Refusal-precedence matrix
- **Purpose**: A table-driven pin of the claim-time refusal text and order for every pair of `build_approved_wp_set` refusals that can occur together, with a deliberately swapped-order control. Then the split cannot reorder refusals unnoticed.
- **Relevant requirements**: FR-017, C-006.
- **Affected surfaces**: `tests/consolidation/test_refusal_precedence_matrix.py`; the `REFUSALS` table there is the authority for the order (WP03 verified it by reading the code; WP19 added the window rows in `test_refusal_precedence_matrix_windows.py`).
- **Sequencing/depends-on**: none.
- **Risks**: As planned (superseded by `REFUSALS`, which adds the unmaterializable status surface after dependency refs and the unreadable fully-canceled dependency lane, and treats authored and excluded as collectors that never refuse), the order was dependency refs → unresolvable branches → canceled dependency → mixed lane → bound → evidence → presence → authored → excluded, with `_compound_refusal` appending the bound after "This Mission also has:". Pairs that cannot co-occur must be listed as such, each with its short-circuit site, not silently skipped. For every pair the test first asserts that **both** refusal markers are present, then their order, so a fixture that yields only one refusal cannot pass vacuously.
- **Model tier**: **mid**.

#### IC-04 — Import-surface pin of `reconciliation.py`
- **Purpose**: Pin every name importable from `specify_cli.consolidation.reconciliation`, public and private, that `src` and tests reach, together with each name's object identity. Add a control showing that a removed name fails the pin.
- **Relevant requirements**: FR-018, C-005.
- **Affected surfaces**: `tests/consolidation/test_reconciliation_surface_pin.py`, plus a checked-in name list generated from the current module and an AST scan of `src/` and `tests/`.
- **Sequencing/depends-on**: none.
- **Risks**: Low. Generate the list from code, never by hand. The generator collects `import` statements **and** string-literal dotted targets (`"specify_cli.consolidation.reconciliation.X"` in patch calls), so a name reached only by a string patch is pinned too.
- **Model tier**: **cheap**.

#### IC-05 — `RECONCILIATION_FAMILY` patch helper and lookup guard
- **Purpose**: A helper modelled on `tests/consolidation/executor_family.py` that patches a name in every family module whose namespace binds it. A guard fails when a test string-patches `specify_cli.consolidation.reconciliation.<name>` and that module does not itself look `<name>` up. Without it, a patch would go silently vacuous after the move.
- **Relevant requirements**: FR-020.
- **Affected surfaces**: `tests/consolidation/reconciliation_family.py`, `tests/consolidation/test_reconciliation_family_guard.py`. Before the split the family is just `(reconciliation,)` and the guard passes; it is non-vacuous through a seeded stale-patch control.
- **Sequencing/depends-on**: none.
- **Risks**: The guard must detect `monkeypatch.setattr("<dotted>", ...)`, `mock.patch("<dotted>")` and `setattr(module, ...)` forms.
- **Model tier**: **cheap to mid**.

#### IC-17 — Seeded-mutation harness and mutation table
- **Purpose**: Prove the corpus can fail before code moves (DIRECTIVE_043, C-008). For each verification check that Phase 3 will move, one deterministic seeded mutation (a verdict forced to pass, or a flipped predicate) applied in the corpus process turns at least one named cell red. A checked-in mutation table lists: check → mutated function → mutation → expected red cell(s).
- **Relevant requirements**: NFR-008, SC-005, C-008.
- **Affected surfaces**: `tests/consolidation/test_reconciliation_seeded_mutations.py` (the table lives in it). Mutations are applied through `RECONCILIATION_FAMILY` (IC-05), so the same test runs against the unsplit module now and against the split modules in Phase 3.
- **Sequencing/depends-on**: IC-02, IC-05.
- **Risks**: A mutation that cannot reach the corpus process makes the test vacuous; the in-process runner (IC-02) is the mechanism, and a control asserts the unmutated run is green. If a cell can only be reached by a subprocess, use an env-gated mutation shim on that child, never a parent-process monkeypatch.
- **Model tier**: **mid**.

### Phase 2 — Record and unify inputs (no verdict change)

#### IC-06 — Window-open capture on the opening transition
- **Purpose**: Record the window-open SHA, or a typed window gap, under `policy_metadata.wp_window` on every non-migration move of a lane-mapped work package into `claimed` / `in_progress`. A missing lane branch is written as its own gap reason, `lane_branch_missing`, not as `capture_failed` (FR-003). The reader picks the window opener (FR-021, IC-07). The reading is the same lane-head reading the `lane_head` stamp already uses, so this adds no extra git read. The status pipeline stays git-free, and a move is never refused.
- **Relevant requirements**: FR-002, FR-003, NFR-006, C-002, C-003; contract `contracts/status-event-wp-window.md`. `test_wp_window_capture.py` pins the `move-task --to claimed` before `implement` case (gap `lane_branch_missing` on the claim, SHA on the later `in_progress`).
- **Affected surfaces**: `src/specify_cli/status/lane_head.py` (`LaneHeadReading`; the probe returns a reading, and `probe_lane_head` stays a thin sha adapter for existing callers); `src/specify_cli/status/transition_pipeline.py` (`_stamped_policy_metadata`); `src/specify_cli/status/__init__.py` (`WP_WINDOW_KEY` re-export); the two composition shells; a changelog fragment under `docs/changelog/unreleased/` (no version bump, operator ruling 2026-11-08).
- **Sequencing/depends-on**: IC-01 (key shape), Phase 1 complete.
- **Risks**: Keep `lane_head` byte-identical for every existing event shape. A not-applicable reading (planning lane, unassigned WP, no `lanes.json`) writes no key, while a failure of a lane-mapped WP writes a gap. The migration-actor check (`is_migration_actor`) is pure. The cold-import boundary stays clean: `LaneHeadReading` lives at module top level with no heavy imports.
- **Model tier**: **top**.

#### IC-07 — Window reader, gap typing and dossier SHA classification
- **Purpose**: One reader in `wp_attribution` classifies a work package's window opening as `WindowOpen(sha)` or `WindowGap(reason)`, implementing the window opener of FR-021: the cycle starts after the last non-migration move to `planned` from a non-review lane; leading `lane_branch_missing` openers are skipped; among the cycle's SHA-bearing openers the topologically earliest (an ancestor of all the others) wins, with event-log order when they are unrelated; a first non-skippable opener with no usable value gives the gap. The reasons are: not recorded; capture failed (with the recorded cause); lane branch missing (no opener of the cycle carries a SHA); not on lane (the recorded SHA is not an ancestor of the lane tip, **or does not resolve in this clone**, FR-022). The reader classifies per event, so a log that straddles the upgrade still reads. The new SHA key is classified `BRANCH_RELATIVE`.
- **Relevant requirements**: FR-004, FR-005, FR-021, FR-022, C-001.
- **Affected surfaces**: `src/specify_cli/consolidation/wp_attribution.py`; `tests/architectural/test_dossier_sha_provenance.py` (`("status.events.jsonl", "policy_metadata.wp_window.open_sha")`); unit tests.
- **Sequencing/depends-on**: IC-06.
- **Risks**: One opener selector (`window_opener_events(events, wp_id, *, cycle)`) serves both `window_open_of` (`cycle=True`, FR-021) and `approval_window_open_stamp` (`cycle=False`: today's first-claim rule, kept for the `single_branch` derivation when no window is recorded, FR-011), so the rule lives once; `first_governed_open_stamp` stays the named "lane anchor" variant. "Not on lane" and the topology order need git, so the caller passes `is_ancestor` / `resolves` predicates bound to the one lane tip the bound resolves (FR-022); the classifier performs no git read. Unit tests cover rewind, review rejection to `planned` (no reset), leading branch-missing skip, a skewed-clock rework (rework `at` earlier than the claim), unrelated SHAs (log-order fallback) and an unresolvable SHA.
- **Model tier**: **top** (soundness-critical rule).

#### IC-08 — `ClaimInputs` and its one constructor
- **Purpose**: One frozen value with these fields: target base, coordination base, frozen lane tips, frozen dependency anchors, dependency pins, excluded canceled work packages, strategy, the status directory read, and its source (`LIVE` for the forecast, `LIVE_THEN_SAVED` for a fresh run, `SAVED` for a resume). It is built by one constructor and adopted by `forecast.py`, `phase_claim.py` and `phase_gate.py`. **Phase 2 keeps every per-mode quirk exactly**, including the forecast's empty excluded set and the gate rebuild's live `mission_branch`, so zero verdicts change. A parity test pins the equal fields, and pins the known divergences as strict `xfail`.
- **Relevant requirements**: FR-012 (construction point), FR-013 (parity test scaffold), C-004.
- **Affected surfaces**: `src/specify_cli/consolidation/claim_inputs.py` (new), with a thin `build_claim(..., inputs)` adapter that calls `build_approved_wp_set` with today's keyword arguments (`reconciliation.py` is untouched in Phase 2); `forecast.py`, `phase_claim.py`, `phase_gate.py`; `tests/consolidation/test_claim_inputs_parity.py`.
- **Sequencing/depends-on**: Phase 1 complete (the corpus guards zero verdict change).
- **Risks**: The resume path's fail-closed anchor checks (`_enforce_resume_anchor_integrity`, `lane_tip_cas_ok`) must keep running before the constructor resolves a base. The frozen dependency anchors are derived from `ConsolidationState.pre_interrupt_lane_tips` (dependency lanes are Mission lanes); coverage confirmed by the post-plan squad (reviewer-renata): whenever a resume passes the H5 guard `_refuse_unanchored_resume`, every dependency lane the closed world anchors on has a frozen tip; the exceptions are named in IC-15. The parity test defines equality: refs compared by resolved SHA, `status_dir` by resolved path and event-log digest; each known divergence is its own strict `xfail`, not one blanket marker. Keep every function ≤ 15 complexity, with one small resolver per source.
- **Model tier**: **mid to top**.

#### IC-09 — Cross-repository writer issue
- **Purpose**: File a spec-kitty-events issue asking the Java write service to write, preserve and type `policy_metadata.wp_window` with the same shape and rules. Link it from the ADR. **Done**: filed as spec-kitty/spec-kitty-events#229 (operator ruling 2026-11-08, Decision Moment `01M6YAG2HE6Q2XNQMGK6X3MBEK`). What remains is the ADR link, and a follow-up comment on #229 if IC-06 changes the final key shape (the `lane_branch_missing` gap reason was added after filing).
- **Relevant requirements**: FR-006, C-003.
- **Affected surfaces**: GitHub `spec-kitty/spec-kitty-events` (an outward-facing write: confirm with the operator before posting); the ADR link.
- **Sequencing/depends-on**: IC-01 (contract text), IC-06 (final key shape).
- **Risks**: None technical. Any further comment on #229 is a GitHub write and needs operator authorization.
- **Model tier**: **cheap**.

### Phase 3 — Behaviour-preserving split

#### IC-10 — Shared kernel and claim types extraction
- **Purpose**: Move the shared kernel symbols (`_lane_branch_for`, `_dependency_lane_ids`, `_APPROVED_MEMBERSHIP_LANES`, `_closed_world_anchors`, `_lane_is_approved`, `_lane_tip_commits`, `_lane_first_parent_spine`, `_is_bookkeeping` and its nested-alias helper and regexes, `_ClaimEventLog`, `_planning_prefix`, `_LaneWalk`) and the whole `ApprovedWpCommitSet` with its content dataclasses into their own modules, re-exported by the facade. Field order stays as it is (some constructions are positional). `_refused` is not a kernel symbol: it builds an `ExternalDependencyAttribution` and moves with the closed world in IC-11 (tasks decision, 2026-11-08).
- **Relevant requirements**: FR-019, C-005, C-006, NFR-001.
- **Affected surfaces**: `reconciliation_kernel.py`, `reconciliation_claim_types.py`, `reconciliation.py` (facade re-exports).
- **Sequencing/depends-on**: Phase 2 complete.
- **Risks**: Function-local imports move with their functions, and are not hoisted. Check `CHURN_SURFACE_MODULES` (`tests/architectural/test_exemption_registry_ratchet.py`) for the module that receives `_is_bookkeeping`.
- **Model tier**: **cheap** (pure move, oracle = corpus + surface pin).

#### IC-11 — One module per check, verifier and claim orchestration
- **Purpose**: Move each check into its own module behind the facade: rendering; closed world, including external dependency refs; approved bound, with write-branch and the lane-tip re-check refusal; the canceled pair (mixed lane + canceled dependency, one slice); authorship + presence (one slice, one spine walk); the verifier, with `Divergence` and `VerifyResult` whole; and claim orchestration, with `build_approved_wp_set` and its refusal order whole. `claim_integrity_refusal` moves with the verifier, not the claim orchestration: it and `MergeOutcomeVerifier` call each other, so they share a module and no import cycle exists. Shared text helpers (`_attest_tail`, `_RECOVERY_TAIL`, `_join_refusals`, `_ALSO_HAS`, `_BOTH_NEEDED`) live in rendering; `_refused` and `_collect_excluded` in the closed world; `_collect_approved_shas`, `_unresolvable_approved_lane_branches` and `_refusal_claim` in the claim orchestration (tasks decision, 2026-11-08). Re-run the IC-17 seeded mutations against the moved checks (retargeted through `RECONCILIATION_FAMILY`); each still turns its named cell red.
- **Relevant requirements**: FR-019, NFR-001, NFR-003, NFR-004, NFR-008, C-006, C-007, SC-005, SC-006.
- **Affected surfaces**: `reconciliation_rendering.py`, `reconciliation_closed_world.py`, `reconciliation_bound.py`, `reconciliation_canceled.py`, `reconciliation_authorship.py`, `reconciliation_verifier.py`, `reconciliation_claim.py`; `reconciliation.py` reduced to the docstring plus re-exports; `tests/consolidation/test_reconciliation_seeded_mutations.py`.
- **Sequencing/depends-on**: IC-10. The order within the phase is free, but the authorship + presence slice should move last: it is the most-fixed region, and `test_presence_lane_base.py` pins its single walk.
- **Risks**: Precedence drift is caught by IC-03. A moved name hit by a string patch is caught by IC-05's guard. Keep a moved function's complexity unchanged; do not fix it in passing. Keep each module ≤ 1,200 lines.
- **Model tier**: **cheap** for the rendering, closed-world, bound and verifier moves; **mid** for the canceled pair and authorship + presence.

#### IC-12 — Patch retargeting and literal-pin housekeeping
- **Purpose**: Retarget every string patch on a moved name through `RECONCILIATION_FAMILY`, or to the name's lookup home. Update the literal pins that name the old module: the owner path in `tests/ci/test_reducer_lock_census.py`; `TERMINUS_ENTRY_POINTS` / `UnroutedTerminusPathError` in `dead_symbol_allowlist.yaml` (keep them defined in place if the contract test requires that, otherwise re-key with net 0); and a fresh-interpreter import smoke test per new module.
- **Relevant requirements**: FR-020, NFR-005, C-005.
- **Affected surfaces**: `tests/consolidation/test_reconciliation.py`, `test_canceled_dependency_attribution.py`, `test_presence_lane_base.py`, `tests/terminus/test_resume_refuses_committed_staged_deletions.py` and the other patch sites the guard flags; the census and allowlist files.
- **Sequencing/depends-on**: runs alongside IC-10/IC-11 (each move carries its own retargets).
- **Risks**: Low. The guard makes a missed retarget fail.
- **Model tier**: **cheap**.

### Phase 4 — Behaviour changes, red-first

#### IC-13 — Lane missions adopt the window model, with fallback and gap report
- **Purpose**: On a code lane with at least one `WindowOpen`, each approved work package with a `WindowOpen` covers only `(window-open SHA, newest approval stamp]`, and a work package with a `WindowGap` falls back to a degraded window `(claim base, approval stamp]`. The exemption anchors on this path are the closed-world anchors plus the approval stamps of **other** bounded lanes; the lane's own approval stamps are not anchors (that is what the windows are for), per Decision Moment `01M6YAFYHT0RMVZB03THW1WWSE`. A lane commit outside every window and every exemption anchor is refused with `LANE_MOVED_AFTER_APPROVAL`, naming the commit and the work package approved before it. A lane on which **every** approved work package has a gap calls today's `check_lane` unchanged, with today's anchors, so its verdict and text are byte-identical (FR-023). The fresh run, the resume and the forecast list every fallback work package with its gap reason, in human and JSON output. `single_branch` reads the recorded window-open SHA when present and reports its absence.
- **Relevant requirements**: FR-007, FR-008, FR-009, FR-010, FR-011, FR-021, FR-022, FR-023, NFR-002, NFR-007, NFR-010, C-010, SC-001, SC-002.
- **Affected surfaces**: `reconciliation_bound.py` (lane leg of the approved-bound verdict), `approved_bound.py` (`check_lane` gains a defaulted `exempt=None` parameter so tier 1 and tier 2 share one exempt set; its rules are unchanged), `write_branch_bound.py` (window machinery shared with lanes: `approval_windows`, `_window_reach`, `_preceding_wp`, `_outside`), `wp_attribution.py`, `claim_inputs.py`, gap rendering in the consolidate/forecast output, `tests/consolidation/test_lane_approval_windows.py`, `tests/terminus/`. `orchestrator-api` inherits the check through `approved_bound_refusal`, with no envelope change.
- **Sequencing/depends-on**: Phase 3 complete; IC-07, IC-08.
- **Risks**: Over-refusal (FR-008): commits a reviewer made during review, rework before re-approval (incl. a rejection to `planned`), and attested approvals must pass on the same fixture. On the window path the order stays as today: `stamp_refusal` first (`APPROVAL_STAMP_MISSING` / `APPROVAL_STAMP_NOT_ON_LANE`), then the refused set, filtered by `content_commits` (merges and bookkeeping-only commits dropped) exactly as today. The one lane tip `_approved_bound_verdict` resolves is passed to the classifier on every path, `approved_bound_refusal` (the `orchestrator-api` door) included, with a parity case for it (FR-022). The exempt set is computed once per lane and shared by tier 1 and tier 2 (NFR-007). The expected corpus flips are NFR-002 (a), (b) and (c) only. Red-first tests drive `consolidate` and `consolidate --dry-run` (same code, no branch moved); the dependency-chain fixture passes (exception), the own-lane variant refuses.
- **Model tier**: **top**.

#### IC-14 — A history-read error is never a deletion (#5048(b))
- **Purpose**: In the authored walk, distinguish a genuinely absent path from a probe failure, using `git_probes.path_state_at`, which returns `None` only when the path is absent. A read failure refuses the claim through the existing claim-time refusal path, naming the path and the error. A genuine deletion is still recorded.
- **Relevant requirements**: FR-014, NFR-002, SC-004.
- **Affected surfaces**: `reconciliation_authorship.py` (`_final_authored_walk`); a red-first test that runs `consolidate` in process with the probe patched at its lookup home through `RECONCILIATION_FAMILY` (a real-git history-read failure is hard to produce) and asserts that no branch moved; a positive control (genuine deletion). Relevant requirements also: NFR-010.
- **Sequencing/depends-on**: Phase 3 complete (the fix lands in the moved module).
- **Risks**: No new refusal code; reuse the existing unreadable-history refusal wording. Do not add a second git read per path beyond the one `path_state_at` replaces, and keep the single spine walk.
- **Model tier**: **mid**.

#### IC-15 — Resume anchors the closed world on frozen dependency-lane tips
- **Purpose**: On `--resume`, one frozen claim-time anchor set, built from `ClaimInputs` (`SAVED` source, frozen at claim capture), feeds **every** consumer of `_closed_world_anchors` (Decision Moment `01M6YAFZVZAYR4G20Q2X4PN0FT`). There are four callers, not five: the mixed-lane resolver (`reconciliation.py:2116`), the approved bound (`reconciliation.py:2268`), the fully-canceled lane's own commits (`reconciliation.py:2529`) and the approved-reviewed attestation (`approved_attestation.py:198`). The attestation caller runs before the claim: on a resume it reads the same `SAVED` anchor set; on a fresh run it reads live tips, which are the values the claim then freezes on an unmutated state. A dependency lane that moved after the interruption no longer widens what is exempt on any axis. A fresh run keeps its verdict.
- **Relevant requirements**: FR-015, NFR-002, NFR-010, SC-004.
- **Affected surfaces**: `reconciliation_kernel.py` / `reconciliation_closed_world.py` (anchor source threaded from `ClaimInputs`), `approved_attestation.py`, `claim_inputs.py`, `tests/consolidation/test_resume_frozen_anchors.py` (red-first, one test per NFR-002 flip (e), (f), (g), each through `consolidate --resume`).
- **Sequencing/depends-on**: IC-08, Phase 3 complete.
- **Risks**: The fixtures use the terminus SIGKILL harness (`tests/terminus/rollback_harness.py`, `approved_content_support.py`), killed after `save_state` of the anchors (`phase_claim.py:344-345`) and before `_phase_merge_lanes`, with the merge lock removed; each test first asserts that `state.json` holds `pre_interrupt_lane_tips` for the dependency lane; no hand-written `state.json`. An exception exit does not reach this state (a pre-mutation exit clears the fresh record; a full-restore rollback re-baselines it and drops the tips on LANES/`single_branch`, #6770), so it would make the resume a fresh run and the red test vacuous. The planning-lane exclusion and the fully-canceled exclusion stay. Degraded anchors keep today's live read and are named in the ADR: a pre-upgrade record, and a record whose status surface did not resolve at capture (`_capture_coord_checkpoint` is `None`, so no tip is frozen and H5 is off). A full-restore re-baseline making the next resume a fresh capture is by design. A canceled set that changes between capture and resume only refuses (H5) or removes anchors, both safe. The gate re-check already uses frozen SHAs (`run.bound_anchor_shas`) and must stay consistent.
- **Model tier**: **top**.

#### IC-16 — Forecast uses the fresh run's excluded canceled work packages
- **Purpose**: The `LIVE` source derives the excluded canceled work packages the way the fresh run does, resolves the coordination base to the SHA the fresh run resolves (not the live `mission_branch` name), and reads the same status directory as the fresh run, so the forecast and the fresh run produce equal claim inputs on an unmutated state. Each parity `xfail` from IC-08 flips to pass in its own fix commit.
- **Relevant requirements**: FR-012, FR-013, NFR-002, NFR-010, SC-003.
- **Affected surfaces**: `claim_inputs.py`, `forecast.py`, `tests/consolidation/test_claim_inputs_parity.py`.
- **Sequencing/depends-on**: IC-08, Phase 3 complete.
- **Risks**: If characterization shows a forecast verdict change, it is red-first through `consolidate --dry-run --json` and limited to NFR-002 (h). The forecast still does not run the verify-side checks it skips today (see #7362).
- **Model tier**: **mid**.

### Concern-to-requirement coverage

| Requirement | Concern(s) |
|---|---|
| FR-001 | IC-01 |
| FR-002, FR-003 | IC-06 |
| FR-004, FR-005 | IC-07 |
| FR-021 | IC-07, IC-13 |
| FR-022 | IC-07, IC-08, IC-13 |
| FR-023 | IC-13 |
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
| NFR-001, NFR-003 | IC-02, IC-11 |
| NFR-008 | IC-17, IC-11 |
| NFR-002 | IC-13..IC-16 |
| NFR-004, NFR-005, NFR-009 | every concern |
| NFR-006 | IC-06 |
| NFR-007 | IC-13 |
| NFR-010 | IC-13, IC-14, IC-15, IC-16 |
| C-009, C-013, C-014 | every concern (cross-cutting; see the note above Phase 1) |

### Model-tier notes (post-plan fold, 2026-11-08)

- **Raised**: IC-02 mid → mid to top (window-state axis, in-process runner, actual-verdict golden); IC-07 mid → top (the opener rule with topology order is soundness-critical).
- **New**: IC-17 mid (seeded-mutation harness, Phase 1).
- **Unchanged but heavier**: IC-13 and IC-15 stay top; IC-15 now owns the SIGKILL fixtures and four anchor consumers. IC-11's mutation work moved to IC-17, so its moves stay cheap except the canceled pair and authorship + presence (mid).
- **Routing hint**: the SIGKILL harness fixtures (IC-15) and the in-process corpus runner (IC-02) should go to the same implementer or be reviewed together, because both decide which state a resume really reaches.
