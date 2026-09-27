# Implementation Plan: Consolidate — canonical lane-consolidation terminology

**Branch**: `feat/consolidate-canonical-terminology` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/consolidate-canonical-terminology-01M3GSSV/spec.md`

## Summary

Promote `consolidate`/`consolidation` to the single canonical term for the **lane-consolidation** sense of `merge`, across the CLI command, code identifiers (physically renamed files), the mission gate-step name, prompt templates, high-value docs, and the drift guard — while the other two senses keep their own words (git = "merge"/"integrate"; trunk = "publish"). `spec-kitty merge` is removed this cycle (pre-stable 4.0.0rc) with a migration-error stub, not a working alias. Foundation (canonicalizing ADR `2026-07-30-1`, glossary `consolidate` entries, `_LANE_CONSOLIDATION_FORBIDDEN_PHRASES`, `CONSOLIDATED`/`PRE_CONSOLIDATION` phase naming) is already landed and is **extended, not re-created**. Technical approach and the full occurrence census live in [research.md](./research.md); the per-site classification lives in [occurrence_map.yaml](./occurrence_map.yaml).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer + rich (CLI surface); pytest, mypy, ruff (quality gates); no new runtime dependency added or removed by this mission
**Storage**: JSON files — `meta.json` (mission), `state.json` (consolidation progress under `.kittify/runtime/merge/<id>/`); no database
**Testing**: pytest ATDD/TDD; the architectural drift-ratchet in `tests/architectural/test_no_legacy_terminology.py`; the existing consolidation behavior suite (`tests/merge/`, renamed with its module)
**Target Platform**: Linux / macOS / Windows CLI
**Project Type**: single (CLI package `src/specify_cli/` + supporting modules)
**Performance Goals**: no CLI startup or consolidation runtime regression (rename only)
**Constraints**: semantic rename never bare find-replace (occurrence-map classified, DIRECTIVE_035); frozen wire-keys `baseline_merge_commit` / `MergeStrategy="merge"` / `state.json`; no consumer migration (additive re-export aliases where an external importer exists); touched functions stay at cyclomatic complexity ≤15; `ruff`/`mypy`/`ruff format` zero issues
**Scale/Scope**: ~20 modules in `src/specify_cli/merge/` + `src/specify_cli/lanes/merge.py`; the `command_installer.py` command surface + 13 agent copies + command-skills; ~5 high-value doc files; the drift guard; ~8 residual phase-name refs

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Glossary & terminology adherence** — this mission *is* the enforcement of this principle for the lane-consolidation sense. ✅ aligned.
- **Single canonical authority** — one word per sense; extends the landed canon rather than adding a second authority. ✅ aligned.
- **Bulk-edit guardrail (DIRECTIVE_035)** — `change_mode: bulk_edit` set; `occurrence_map.yaml` classifies every touched site before any edit. ✅ satisfied by Phase 1 artifact.
- **Campsite (DIRECTIVE_025)** — the stale `CLAUDE.md:396` `merge-state.json` claim is corrected in-mission. ✅.
- **Canonical sources, not generated copies** — edits target sources (`command_installer.py`, `packs/**` templates); 13 agent copies regenerate via `spec-kitty upgrade`. ✅.
- **Recorded divergence (C-004)** — alias-removal overrides #3080's alias AC; justified by pre-stable rc timing; noted on the issue. No charter conflict.

**No unjustified violations.** Complexity Tracking below is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/consolidate-canonical-terminology-01M3GSSV/
├── plan.md              # This file
├── research.md          # Phase 0 — grounding synthesis + adversarial-evidence dispositions
├── data-model.md        # Phase 1 — entities (ConsolidationState, occurrence map, frozen keys)
├── quickstart.md        # Phase 1 — how to run/verify the renamed command + guard
├── occurrence_map.yaml  # Phase 1 — bulk-edit 8-category per-site classification (REQUIRED before implement)
├── contracts/           # Phase 1 — CLI command contract + occurrence-map schema
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/
│   ├── merge.py                  → consolidate.py (command body: merge()→consolidate(); merge removed w/ migration stub)
│   ├── __init__.py               (command registration: consolidate primary)
│   └── merge_driver.py           (KEEP — git plumbing, Sense B)
├── merge/                        → consolidation/ (package rename; lane-consolidation-sense symbols)
│   ├── state.py                  (MergeState → ConsolidationState + re-export alias)
│   ├── executor.py               (_run_lane_based_merge → _run_lane_based_consolidation)
│   ├── baseline.py               (KEEP baseline_merge_commit wire-key; boyscout local identifiers only)
│   ├── config.py                 (KEEP MergeStrategy enum + "merge" value, Sense B)
│   └── … (forecast, resolve, retention, reconciliation, git_probes, …)
├── lanes/merge.py                → lanes/consolidation.py (LaneMergeResult → LaneConsolidationResult, etc.)
└── skills/command_installer.py   (command list/description/command-map: merge → consolidate)

packs/built-in/missions/mission-steps/software-dev/{accept,specify}/prompt.md   (spec-kitty merge → consolidate)
packs/built-in/toolguides/POWERSHELL_SYNTAX.md
docs/context/orchestration.md + ~5 high-value docs + CLAUDE.md (campsite)
tests/architectural/test_no_legacy_terminology.py  (drift-guard delta)
tests/merge/ → tests/consolidation/  (behavior suite rename)
```

**Structure Decision**: single CLI package. Physical file/package renames (`merge/`→`consolidation/`, `lanes/merge.py`→`lanes/consolidation.py`, `cli/commands/merge.py`→`consolidate.py`, `tests/merge/`→`tests/consolidation/`) per the resolved discovery decision, with additive re-export shims only where an external consumer imports a renamed symbol.

## Complexity Tracking

*No Charter Check violations — table intentionally empty.*

## Implementation Concern Map

> Concerns, not work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Occurrence classification map (precedes all edits)
- **Purpose**: produce `occurrence_map.yaml` classifying every touched occurrence across the 8 bulk-edit categories as rename-now / rename-deferred / keep, so no edit lands unclassified.
- **Relevant requirements**: C-001, C-002, C-003.
- **Affected surfaces**: `kitty-specs/<mission>/occurrence_map.yaml`.
- **Sequencing/depends-on**: none (gates every other IC).
- **Risks**: mis-classifying a frozen KEEP (baseline_merge_commit, MergeStrategy value, merge-drivers) as rename — the load-bearing failure. Larry's rubric + Paula's landmine map are the inputs.

### IC-02 — Code identifier + module-file rename
- **Purpose**: rename lane-consolidation-sense symbols and physically rename their files (`merge/`→`consolidation/`, `lanes/merge.py`→`lanes/consolidation.py`, `MergeState`→`ConsolidationState`), updating all internal importers + tests; additive re-export shims where an external consumer requires one.
- **Relevant requirements**: FR-004; NFR-002.
- **Affected surfaces**: `src/specify_cli/merge/**`, `src/specify_cli/lanes/merge.py`, `~41 tests/merge/**`, importer sites.
- **Sequencing/depends-on**: IC-01.
- **Risks**: whack-a-field half-rename; byte-stable public `__all__` must grow not shrink (#2057); state.json filename frozen.

### IC-03 — CLI command surface
- **Purpose**: `consolidate` becomes the primary command (full former-merge flag set); `merge` removed with a hidden migration-error stub sharing no working body.
- **Relevant requirements**: FR-001, FR-002, FR-003; C-004.
- **Affected surfaces**: `cli/commands/merge.py`→`consolidate.py`, `cli/commands/__init__.py`.
- **Sequencing/depends-on**: IC-02.
- **Risks**: flag/exit-code passthrough drift; `--resume` must still read `state.json`.

### IC-04 — Gate-step / command surface + agents & skills regeneration
- **Purpose**: rename the mission gate-step/command (`command_installer.py` list/description/command-map), skill `spk-gate-merge`→`spk-gate-consolidate`, slash command `spec-kitty.merge`→`spec-kitty.consolidate`; regenerate all 13 agent copies + command-skills via `spec-kitty upgrade`.
- **Relevant requirements**: FR-006; C-005.
- **Affected surfaces**: `src/specify_cli/skills/command_installer.py`, generated agent dirs (via upgrade).
- **Sequencing/depends-on**: IC-03.
- **Risks**: editing generated copies instead of source; incomplete regeneration across 13 agents.

### IC-05 — Prompt templates + toolguides
- **Purpose**: convert lane-consolidation-sense `spec-kitty merge`→`spec-kitty consolidate` in `packs/**` prompt.md + toolguides.
- **Relevant requirements**: FR-007.
- **Affected surfaces**: `mission-steps/software-dev/{accept,specify}/prompt.md`, `toolguides/POWERSHELL_SYNTAX.md`.
- **Sequencing/depends-on**: IC-03.
- **Risks**: missing a template that regenerates stale agent guidance.

### IC-06 — Glossary + high-value docs + CLAUDE.md campsite
- **Purpose**: mark `spec-kitty merge` removed from active command vocabulary; convert ~5 high-value doc files; fix the stale `CLAUDE.md:396` `merge-state.json` reference.
- **Relevant requirements**: FR-008; C-006 (immutable history untouched); C-008 (long-tail deferred).
- **Affected surfaces**: `docs/context/orchestration.md`, high-value docs, `CLAUDE.md`.
- **Sequencing/depends-on**: IC-03.
- **Risks**: over-reaching into archival/immutable artifacts.

### IC-07 — Drift-ratchet guard extension
- **Purpose**: add a command-surface `"spec-kitty merge"` + lane-consolidation-phrasing ratchet with its own baseline + historical allowlist; scan `src`, `docs`, and `packs/`; red-first bite + green-on-legit proofs.
- **Relevant requirements**: FR-009; NFR-004.
- **Affected surfaces**: `tests/architectural/test_no_legacy_terminology.py`.
- **Sequencing/depends-on**: IC-02..IC-06 (ratchet lands last, shrink-only over converted files).
- **Risks**: false-positive on git-merge/publish; size-pinned baseline coupling.

### IC-08 — Phase-naming coherence + frozen-KEEP verification
- **Purpose**: converge residual lane-consolidation-sense `post-merge` *prose* onto the canonical vocabulary; assert the frozen KEEPS unchanged and phase derivation still resolves. **(Amended — see A5 below: `MissionReviewMode.POST_MERGE` does not exist; actual residuals are prose in `merge/baseline.py`, and `trigger_mode` `post_merge` is a NEW frozen KEEP.)**
- **Relevant requirements**: FR-005, FR-010; C-002.
- **Affected surfaces**: `src/specify_cli/merge/baseline.py` prose; review-mode consumers.
- **Sequencing/depends-on**: IC-02.
- **Risks**: reintroducing a `POST_CONSOLIDATION` symbol (forbidden — converge on landed names); sweeping the frozen `trigger_mode` enum value.

---

## Post-Plan Brownfield Amendments (squad-folded, 2026-09-27)

Two post-plan lenses (coupling + completeness) verified the plan against live code. These
amendments **supersede** the affected ICs above. Sources: `work/3080-consolidate-terminology/squad/postplan-coupling-paula.md`, `postplan-completeness-alphonso.md`.

**A1 — IC-02 and IC-03 MERGE into ONE atomic WP (write-scope collision, red-tree-mid-mission bug).**
The physical `merge/`→`consolidation/` package rename atomically breaks every importer, including
`cli/commands/merge.py` (the file IC-03 renames: imports at `:154 _run_lane_based_merge`, `:229 has_active_merge`, `:257 MergeState`) and unowned external importer `orchestrator_api/commands.py` (`:829/:833 _run_lane_based_merge`, `:981 _mark_wp_merged_done`, `:984 lanes.merge`, `:986 merge.config`, `:988 policy.merge_gates`). These cannot be independent green commits. **The atomic rename WP owns, in one commit set:**
- Package/file renames: `merge/`→`consolidation/`, `lanes/merge.py`→`lanes/consolidation.py`, `cli/commands/merge.py`→`consolidate.py`, `tests/merge/`→`tests/consolidation/`.
- Symbol renames: `MergeState`→`ConsolidationState`, `_run_lane_based_merge`→`_run_lane_based_consolidation`, `LaneMergeResult`/`MissionMergeResult`→`…Consolidation…`.
- **CRITICAL delegation repoint (Paula #1):** `cli/commands/mission.py:323 top_level_merge = _merge` and `mission_accept_merge.py:252` invoke the command function as a *working body* — repoint to the `consolidate` body, NOT the migration stub; update `test_wrapper_delegation.py:130` (currently mocks `top_level_merge`, hiding the break) to assert the working body.
- All internal importers + `orchestrator_api/commands.py` repointed (no shim — see A3).
- **Drift-guard baseline path update MOVED here from IC-07** (`test_no_legacy_terminology.py:360/:362` pin `lanes/merge.py` + `merge/git_probes.py`; `:491 _currently_real` asserts existence → reds on rename).
- **Gate-coverage frozenset edit:** `tests/architectural/_gate_coverage.py:1983 _PRE_MISSION_MAPPED_SRC_DIRS` lists `"merge"` → update for the dir rename.
- **#2057 identity + json-contract:** `test_merge_compat_surface.py:329` (old module path) + `test_json_contract_enumeration.py:357` + `cli/commands/merge.py:525` exit-contract ref.
- **Stale logger name:** `merge/_constants.py:21` hardcodes `"specify_cli.cli.commands.merge"`.

**A2 — Machine-contract surfaces get an owning IC (both lenses; else CI reds).**
- `docs/api/cli-commands.md` is **generated** (`scripts/docs/build_cli_reference.py`) and strict-freshness-gated (`check_cli_reference_freshness.py:397-400`); carries `## spec-kitty merge` (:3063) + `merge-mission` (:4789). **Regenerate** in the command WP (IC-03/atomic), do not hand-edit. `docs/api/agent-subcommands.md` likewise.
- `src/specify_cli/core/upstream_contract.json:92` enumerates orchestrator token `merge-mission` (allowed) + `:108 merge-feature` (forbidden). See A4.

**A3 — NO re-export shim (both lenses; resolves data-model NFR-002 to "none").**
No in-repo external consumer imports a *renamed* symbol: `orchestrator_api` imports only `MergeStrategy` (frozen keep) + the private `_run_lane_based_merge` (repointed in the atomic WP); `saas_client`/`zeitgeist_client` import none. A code-level re-export alias would contradict the operator's clean-rename/no-alias posture. **Default: no shim; repoint importers.** data-model.md updated.

**A4 — ⚠️ SCOPE EXPANSION flagged for operator veto: `merge-mission` orchestrator-api command.**
Live `@app.command(name="merge-mission")` (`orchestrator_api/commands.py:2129`) is the lane-consolidation sense on the **external orchestrator-api contract**. For canonical-word consistency this plan renames it `merge-mission`→`consolidate-mission` (clean break at rc; update `upstream_contract.json` `:92` to `consolidate-mission` allowed, keep `:108 merge-feature` forbidden). **This touches an external API contract not named in #3080's IN list — operator may veto to keep it frozen.** Owned by the atomic WP if kept in scope.

**A5 — IC-08 phantom target + new frozen KEEP.** `MissionReviewMode.POST_MERGE` does not exist; the real residuals are `post-merge` *prose* in `merge/baseline.py:5,102,113,136,326,345`. **New frozen KEEP:** `trigger_mode: Literal["manual","post_merge","both"]` on a `frozen=True` model (`runtime/next/_internal_runtime/schema.py:360`) — a serialized enum value IC-08 must NOT sweep. Added to occurrence_map exceptions.

**A6 — Blast radius corrected.** Not "~41 test files": live is `tests/merge/` = 72 files; 129 test files reference `specify_cli.merge`; 51 reference `MergeState`. The atomic rename WP is large and cannot be split by write scope.

**Positive (confirmed):** `MergeState.to_dict = asdict` (`state.py:174`) persists fields only — no class-name/module-path on disk, so the class rename is on-disk-safe. No naming collisions (`consolidation/`, `ConsolidationState`, `tests/consolidation/` all free).
