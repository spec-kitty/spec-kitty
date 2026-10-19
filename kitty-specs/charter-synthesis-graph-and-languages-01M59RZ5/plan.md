# Implementation Plan: Charter synthesis graph and languages

**Branch**: `issue-6442-charter-synthesis-graph-work` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/charter-synthesis-graph-and-languages-01M59RZ5/spec.md`

All planning questions are answered by eight resolved Decision Moments in `decisions/` (operator, 2026-10-19).

## Summary

The Mission makes four changes:

- **Reach-only styleguides (#6442).** The tactic reach-only model from #6404 is generalised to a set of reach-only kinds. Synthesized testing, quality-gate and documentation styleguides are sourced from DIRECTIVE_034, DIRECTIVE_030 and DIRECTIVE_037 through `source_urns`. They become reach-only. Removal sticks, using a per-kind created-artifact record.
- **Project-intent directive (#6443).** The always-synthesized directive is renamed to `project-intent-directive`, and its dead `requires --> mission_type:*` edge is retired. One charter-layer helper does the move. Both an upgrade migration and synthesize call it.
- **One language authority (#6444).** An I/O-free language catalog lives in `charter.offering.shared`, and one activation-layer authority resolves observed and declared languages from it. On top of that come multi-language evidence, a `kotlin` token, and a `jvm` family expanded at match time. The shared JVM toolguides are retagged `jvm` in core, re-seeded into open-packs and pinned back.
- **Local-only reds.** Three real reds on `main` and one environment leak are fixed: the upgrade runner guard, the orphan ceiling, and nag-test hermeticity.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ruamel.yaml, typer, pytest. No new dependency.
**Storage**: project files under `.kittify/` (charter, charter-packs, synthesis manifest, provenance, created-artifact record).
**Testing**: pytest, red-first per ADR 2026-07-17-1. Targeted module tests plus owning-subsystem directories. No `make test-full`; CI owns the heavy suites.
**Target Platform**: the CLI (`spec-kitty`).
**Project Type**: single
**Performance Goals**: NFR-005. Extra source counting runs only when it is needed, and the synthesis performance envelopes stay green.
**Constraints**: C-001..C-007, ADR-guarded request hash (amended), DIRECTIVE_044 (never edit a shipped migration), offering ↛ activation layering.
**Scale/Scope**: about 30 source files and about 40 test files across `src/charter/`, `src/specify_cli/upgrade/` and `src/specify_cli/cli/commands/charter/`, plus one `packs/built-in` retag and one open-packs re-seed.

## Charter Check

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | The language catalog becomes the one vocabulary table, enforced by an architectural test. The reach-only predicate, edge stamping and created-artifact record are parameterised by kind rather than copied. One rename helper serves both the migration and synthesize. |
| Architectural alignment / layering | The catalog lives in `charter.offering.shared`, which offering matching can import. The authority lives in `charter.activation`. `specify_cli` reaches new behaviour only through `charter.activation.api` (C-005). |
| ATDD / red-first | Every behavioural FR gets an issue-pinned failing test before its fix. Regression markers are converted to focused tests before review. |
| Terminology | Mission, never "feature". The glossary is checked at review. |
| Canonical sources | Built-in doctrine edits follow the vendor flow: edit in core, re-seed open-packs, pin back. Migrations go through `order_manifest.txt`. |
| No suppression | No new `noqa` or `type: ignore`. Complexity ≤ 15. |

The gate passes, and there are no violations.

## Design Decisions

- **D-01: per-kind created-artifact record.** The new record is `.kittify/charter/synthesized-artifacts.yaml`, with keys `created_tactics` and `created_styleguides`.
  - The read takes the union with the legacy, unreleased `.kittify/charter/synthesized-tactics.yaml` `created_tactics`. The legacy file is never written.
  - A write keeps any key it does not own.
  - If either file is unreadable, synthesis appends nothing for any kind and warns.
  - Rationale: the record has not shipped (CHANGELOG `[Unreleased]`, no tag), and the name should match the content.
- **D-02: reach-only kinds.** `REACH_ONLY_KINDS = (tactic, styleguide)` drives these, so that generalised functions replace the tactic-only ones and the existing tactic stamps stay byte-identical:
  - `synthesized_edge_reason(kind, slug)` (the tactic reason text is unchanged)
  - `is_synthesized_source_edge`
  - `edge_owner` (target-owned for every reach-only kind)
  - `_is_legacy_applies` (strips `applies` from any reach-only kind)
  - `_derived_edge` (`suggests` for every reach-only kind)
  - `reach_only_ids(repo_root, kind)`
  - `append_synthesized_activations(repo_root, created_by_kind)`
  - `created_slugs(reconciliation, kind)`

  The public API exposes the generalised names, and the re-export test is updated.
- **D-03: styleguide source table.** `_STYLEGUIDE_SOURCE_DIRECTIVES` is a fixed table in `interview_mapping.py`, carried per kind through `source_urns_by_kind` into `build_targets`.
  - The edge is emitted only when the directive exists in the DRG snapshot. That is a presence check, like `mission_type_urn_candidate`, so no URN dangles.
  - The compiled-references root filter (`compiler._direct_root_urns`) excludes reach-only styleguides. The action bundle is unchanged (it seeds no styleguide roots), and a test pins that.
- **D-04: project-intent rename.**
  - **Synthesis side.** `targets.py` gets slug `project-intent-directive` and title "Project Intent Directive". `_mission_type_evidence_urns`, `mission_type_urn_candidate` and `_MISSION_TYPE_URN_BY_NORMALIZED_ID` are deleted. Reconcile strips a `directive:PROJECT_* --requires--> mission_type:*` overlay edge and reports it.
  - **The rename helper.** `rename_legacy_project_intent_directive(repo_root) -> RenameReport` lives in a new `charter/activation/synthesizer/legacy_rename.py` and is exported from `charter.activation.api`. It works in two phases: a preflight with no writes (refusing on a collision), then the moves listed in FR-008, then a bundle restamp. The artifact body is not rewritten.
  - **Callers.** synthesize and resynthesize call it before writing. The migration `m_4_0_0rc8_project_intent_directive_rename` (`clone_local_effect = False`, appended to `order_manifest.txt`) calls it too. Its `detect` reads legacy slug-keyed files.
- **D-05: language catalog and authority.**
  - **`charter/offering/shared/language_catalog.py`.** A pure-data table of `LanguageSpec(token, extensions, manifests, declared_patterns, families)` for python, javascript, typescript, java, kotlin, go, rust, ruby, php, swift, plus build/test tokens that declare the `jvm` family. It also provides `expand_language_families`.
  - **`charter/activation/language_authority.py`.** It holds `observe_languages(repo_root, max_depth)` (moved out of `code_reader`), `declared_languages(text)` (replaces `extract_declared_languages`) and `resolve_declared(...)`.
  - **Delegation.** `code_reader`, `language_scope` and `offering/shared/scoping.applies_to_languages_match` all delegate to it. Matching expands families on the active side. `lacks_specialist_guidance` expands families before intersecting.
  - **Unchanged.** The doctrine-derived "has guidance" vocabulary (`language_vocabulary.py`, #5284) stays separate.
  - **Gate.** `tests/architectural/test_single_language_vocabulary.py` AST-scans `src/` for literals holding three or more catalog tokens or source extensions outside the catalog. `review/fix_prompt.py` is allowlisted with a rationale.
- **D-06: multi-language rule.**
  - **Inclusion.** `languages` holds every language with a manifest at the shallowest manifest depth, plus any language whose source share is ≥ 20% of counted sources. The order is primary first, then by source count.
  - **JVM split.** A JVM manifest chooses between `kotlin` and `java` by `.kt` vs `.java` counts.
  - **When counting runs.** Only when a JVM manifest, or two or more candidate languages, are present (NFR-005).
  - **Hash.** It adds `languages` only when `len(languages) > 1`.
  - **Gate exemption.** The neutrality gate exempts a slug component that is in observed ∪ declared, after family expansion.
  - **Corpus.** It still loads by primary language.
- **D-07: upgrade outside git (FR-015).** The runner's `_apply_migration` treats `charter.resolution.NotInsideRepositoryError`, raised by `can_apply`/`apply`, as not applicable: skipped, warned, unrecorded. The shipped rc35 migration is not edited (DIRECTIVE_044). The exception is reached through `charter.activation.api` if the boundary test requires it.
- **D-08: orphan ceiling (FR-016).** The shipped-graph test derives its ceiling from the shipped-orphan set already maintained in `tests/charter_offering/drg/migration/test_extractor_projection.py`, if it can import it cleanly. Otherwise it is raised to 25 with a dated rationale. A dated addendum goes into `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md`.
- **D-09: JVM retag flow (FR-018).**
  1. Edit `packs/built-in/toolguides/{java-supply-chain,maven-review-checks}.toolguide.yaml` to `applies_to_languages: [jvm]` and run `charter pack regenerate-graph`.
  2. Push the branch.
  3. Re-seed open-packs `built-in/` from that core commit with its own re-seed script, open the open-packs PR, and wait for the operator's merge.
  4. Run `spec-kitty charter pack vendor --ref <merged sha>` in core.

  The core PR stays draft until step 4. If the bump also pulls unrelated open-packs commits, they are listed in the PR.
- **D-11: configured project languages (FR-020, operator decision 2026-10-19).** `.kittify/config.yaml` gains an operator-confirmed language list; the exact key is chosen by WP07 after checking existing config conventions, and documented.
  - `charter interview` runs observed detection (the language authority over the collector's walk), proposes the result, and writes the confirmed list.
  - The language authority reads it first. When set, it is the evidence `languages`, with the primary first, and it is the declared set for doctrine scoping (`infer_repo_languages` / `catalog.languages`). Detection and free-text parsing are the fallback only when it is absent.
  - Families are still expanded at match time and never stored.
- **D-10: ADR amendments (FR-019).** Each amendment is made in the work package that changes the contract:
  - 2026-04-17-1 (request-hash inputs) → styleguide sources and the slug change
  - 2026-04-19-6 (generated layout and slug) → the rename
  - 2026-10-06-2 (removal sticks, per-kind record) → styleguides

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-synthesis-graph-and-languages-01M59RZ5/
├── spec.md, plan.md, tasks.md, tasks/
├── decisions/          # 8 resolved Decision Moments
├── research/           # squad reports (alignment, brownfield, post-spec, local reds)
└── traces/             # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/charter/offering/shared/language_catalog.py        (new)
src/charter/offering/shared/scoping.py
src/charter/activation/language_authority.py           (new)
src/charter/activation/language_scope.py, evidence/code_reader.py, evidence/orchestrator.py
src/charter/activation/synthesizer/{reach_only,reconcile,project_drg,interview_mapping,targets,evidence,request,write_pipeline,resynthesize_pipeline}.py
src/charter/activation/synthesizer/legacy_rename.py    (new)
src/charter/activation/{compiler,api}.py
src/specify_cli/cli/commands/charter/{synthesize,resynthesize,status,_status_collectors}.py
src/specify_cli/upgrade/runner.py
src/specify_cli/upgrade/migrations/m_4_0_0rc8_project_intent_directive_rename.py (new), order_manifest.txt
packs/built-in/toolguides/{java-supply-chain,maven-review-checks}.toolguide.yaml, packs/built-in.source.yaml
docs/adr/…, docs/changelog/CHANGELOG.md, docs/development/testing/testing-flakiness.md
```

**Structure Decision**: single project. Charter changes stay in `src/charter/`, upgrade changes in `src/specify_cli/upgrade/`, and CLI wiring in `src/specify_cli/cli/commands/charter/`.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Local-only reds

- **Purpose**: turn three real reds on `main` green and make the nag tests hermetic.
- **Relevant requirements**: FR-015, FR-016, FR-017
- **Affected surfaces**:
  - `src/specify_cli/upgrade/runner.py`
  - `tests/specify_cli/cli/commands/test_upgrade_command.py`, `tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`
  - the residual doc, `docs/development/testing/testing-flakiness.md`
- **Sequencing/depends-on**: none
- **Risks**:
  - The runner guard must not mask a partial write. `resolve_canonical_repo_root` runs before any write in rc35. The guard is limited to that exception type.

### IC-02 — Reach-only by kind

- **Purpose**: make synthesized styleguides follow their directive, and make removal stick.
- **Relevant requirements**: FR-001..FR-005, FR-019 (2026-10-06-2, 2026-04-17-1 part)
- **Affected surfaces**:
  - synthesizer: `reach_only`, `reconcile`, `project_drg`, `interview_mapping`, `targets`, `resynthesize_pipeline`
  - `compiler`, `api`
  - CLI: `synthesize`, `resynthesize`
  - fixture-adapter styleguide fixtures
- **Sequencing/depends-on**: none
- **Risks**:
  - Fixture re-keying for styleguides.
  - The inverted tests `test_project_drg.py::test_styleguide_source_urn_keeps_applies_edge` and the styleguide-applies case in `test_synthesize_reconcile.py`.
  - The new implement/review delivery must be pinned.

### IC-03 — Project-intent directive

- **Purpose**: name the directive for its content, retire the dead edge, and converge existing projects.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-019 (2026-04-19-6)
- **Affected surfaces**:
  - `targets`, `interview_mapping`, `reconcile`, new `legacy_rename.py`, `api`
  - the synthesize/resynthesize pre-step
  - the new migration and `order_manifest.txt`
  - about 25 slug-pinning tests and the fixture-adapter directive fixtures
- **Sequencing/depends-on**: IC-02 (shared files: reconcile, targets, interview_mapping, synthesize CLI)
- **Risks**:
  - Two provenance shapes (`directive-project-001.yaml` and `directive-mission-type-scope-directive.yaml`).
  - Stem tokens in the activation write target.
  - The acceptance cutover golden.

### IC-04 — Language catalog and authority

- **Purpose**: one language vocabulary and family map, used by detection, declaration and matching.
- **Relevant requirements**: FR-009, FR-013
- **Affected surfaces**: the new catalog and authority, `code_reader`, `language_scope`, `offering/shared/scoping`, the architectural test
- **Sequencing/depends-on**: none
- **Risks**:
  - Layering (offering ↛ activation).
  - A declared "Gradle" now yields `jvm`.
  - About 21 test files use `infer_repo_languages`.

### IC-05 — Multi-language evidence

- **Purpose**: describe polyglot repositories and gate them correctly.
- **Relevant requirements**: FR-010, FR-011, FR-012, FR-014
- **Affected surfaces**: synthesizer `evidence`, `request`, `write_pipeline`; the authority; CLI `_status_collectors`, `status`, `synthesize`
- **Sequencing/depends-on**: IC-04, and IC-02 (shares `synthesize.py`)
- **Risks**:
  - The hash must stay byte-identical for single-language repositories.
  - Performance envelopes.

### IC-06 — JVM retag, vendor flow, integration golden

- **Purpose**: ship `jvm` doctrine without a Kotlin regression, and document the combined delivery change.
- **Relevant requirements**: FR-018, NFR-001
- **Affected surfaces**:
  - two built-in toolguides, `packs/built-in.source.yaml`, the open-packs re-seed PR
  - a new synthesized-project golden
  - CHANGELOG and docs
- **Sequencing/depends-on**: IC-02..IC-05
- **Risks**:
  - Cross-repo: the core pin bump waits on the operator merging the open-packs PR.
  - The pin bump may carry unrelated open-packs commits.
