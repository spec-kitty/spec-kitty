---
title: Org Doctrine Layer — Post-Implementation Architecture Review
description: "Architect Alphonso's post-merge architecture review (2026-05-16) of the org doctrine layer: how the shipped design holds up and the follow-ups."
doc_status: deprecated
updated: '2026-06-01'
related:
- plans/doctrine/layered-doctrine-resolution-design
---
# Org Doctrine Layer — Post-Implementation Architecture Review

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

**Author:** Architect Alphonso (post-merge architectural review)
**Date:** 2026-05-16
**Mission:** `layered-doctrine-org-layer-01KRNPEE` (display number 118)
**Merge commit:** `9c2c26a0` (squash) on `feat/org-doctrine-layer`
**Post-merge remediations:** `e1d58d2f` (HIGH-1 multi-pack iteration), `86c103e2` (HIGH-2 interview pre-fill wiring), `b0f69231` (MEDIUM-1 collision warnings + spec/code reconciliation), `76c9f3b4` (quality sweep on touched modules)
**Related ADRs:** `2026-03-27-1-pytestarch-architectural-dependency-testing.md`, `2026-05-16-1-doctrine-layer-merge-semantics.md`
**Related design predecessor:** [layered-doctrine-resolution-design.md](./layered-doctrine-resolution-design.md) (the *intent* blueprint, written 2026-05-15)
**Related mission review:** [mission-review-report.md](../../../kitty-specs/layered-doctrine-org-layer-01KRNPEE/mission-review-report.md)

---

## Scope and audience

This note is an architectural review of the org-doctrine-layer feature **as it actually landed**, written to complement the pre-implementation [design blueprint](./layered-doctrine-resolution-design.md). It targets future maintainers who need to:

- Understand which components the feature added and how they collaborate.
- Cross-check the implementation against the canonical architecture model, the mission specification, and the project glossary.
- Assess fit against the architectural intent statements in our ADRs and landscape model.
- Plan the documentation / glossary follow-ups needed before the next release that depends on this feature.

It is not a design document (the predecessor already covers intent) and not a user guide (see `docs/architecture/org-doctrine-layer.md` and `docs/guides/create-an-org-doctrine-pack.md`). It is engineering notes for architecture review.

---

## Executive summary

The mission shipped the planned three-layer doctrine model (`built-in → org → project`) plus a `spec-kitty doctrine` operator CLI, an `org-charter.yaml` policy file, and an advisory `charter lint` org-layer surface. Architectural boundaries (`kernel ← doctrine ← charter ← specify_cli`) hold. All 8 architectural layer-rule tests pass on `HEAD`.

Three substantive deltas vs the original blueprint are worth flagging:

1. **Merge semantics shifted from "full-replace" to field-level merge with collision warnings.** The blueprint's design table said "Full-replace on ID collision"; the implementation preserved the pre-existing field-merge `_merge()` from `BaseDoctrineRepository`. The post-mission review caught the spec/code contradiction (MEDIUM-1) and the remediation reconciled the spec to the code while adding operator-visible `DoctrineLayerCollisionWarning` emission (ADR 2026-05-16-1). The new behaviour is documented and tested; the predecessor blueprint's table entry is now stale.

2. **Multi-pack iteration was initially incorrect.** WP02 framed `org_dirs` as future-proofing — the original `_org_dir()` returned only `org_roots[0]`. Post-mission review caught this (HIGH-1) and the remediation made the loop iterate every configured pack in declaration order. The fix is in place and tested.

3. **`charter interview` pre-fill was implemented but unwired.** WP09 created `apply_org_charter_pre_fill_to_answers` (file helper) and `apply_org_charter_pre_fill` (orchestrator) but never invoked them from the live `charter interview` command (HIGH-2). The remediation added an in-memory variant `apply_org_charter_to_interview` and wired it.

The architectural boundary documented in ADR 2026-03-27-1 (charter must not import specify_cli) materially shaped two design choices: `charter._drg_helpers._resolve_org_root` is an inert stub by deliberate design (org-root resolution lives in `specify_cli.doctrine.config.resolve_org_roots` and is passed down), and the WP09 org-charter loader was lifted from charter into `specify_cli.doctrine.org_charter_loader` so the charter layer remains import-clean.

The glossary and parts of the mission spec are now out of sync with the shipped semantics (see [Domain concepts cross-check](#domain-concepts-cross-check)). This is the single largest gap left after the remediations.

---

## Architectural overview (C4-style component diagram)

### Layer landscape (system context, simplified C4-1)

```
                ┌──────────────────────────────────────────────────────┐
                │                spec-kitty (CLI shell)                │
                │   - typer commands, charter lint, runtime adapters   │
                │   - hosts adapters to git, HTTPS, vendor APIs        │
                └──────────────────────────────────────────────────────┘
                                       │ uses
                                       ▼
        ┌────────────────────────────────────────────────────────┐
        │                       charter                          │
        │   - charter generate / interview / context             │
        │   - DRG helpers (3-layer load)                         │
        │   - synthesizer pipeline                               │
        └────────────────────────────────────────────────────────┘
                                       │ uses
                                       ▼
        ┌────────────────────────────────────────────────────────┐
        │                      doctrine                          │
        │   - artifact repositories (8 kinds + agent profiles)   │
        │   - BaseDoctrineRepository (3-source merge)            │
        │   - DRG loader (single-file or fragment dir)           │
        └────────────────────────────────────────────────────────┘
                                       │ uses
                                       ▼
        ┌────────────────────────────────────────────────────────┐
        │                       kernel                           │
        │   - zero-dependency primitives (paths, glossary)       │
        └────────────────────────────────────────────────────────┘
```

The arrow direction is **import / call**: higher layers depend on lower layers; the reverse is forbidden and enforced by `tests/architectural/test_layer_rules.py`. ADR `2026-03-27-1` is the binding source.

### Component diagram for the org-doctrine-layer feature (C4-3)

```
                                                          ┌─────────────────────────────────┐
                                                          │ .kittify/config.yaml            │
                                                          │   doctrine.org.packs: [...]     │
                                                          └───────────────┬─────────────────┘
                                                                          │ reads
                                                                          ▼
                                                ┌────────────────────────────────────────────┐
                                                │ specify_cli.doctrine.config                │
                                                │   OrgPackConfig (pydantic)                 │
                                                │   PackRegistry                             │
                                                │   load_pack_registry / save_pack_registry  │
                                                │   resolve_org_roots                        │
                                                └───────────────┬────────────────────────────┘
                                                                │ provides org_roots
        spec-kitty doctrine fetch                               │
        ──────────────────────────►  ┌──────────────────────────┴───────────────┐
                                     │ specify_cli.doctrine.sources              │
                                     │   OrgDoctrineSource (Protocol)            │
                                     │   GitSource | HttpsBundleSource | ApiSource│
                                     │   FetchResult                             │
                                     └──────────────────────────┬────────────────┘
                                                                │ writes (atomic)
                                                                ▼
                                     ┌─────────────────────────────────────────┐
                                     │ specify_cli.doctrine.snapshot           │
                                     │   write_snapshot                        │
                                     │   write_pack_manifest                   │
                                     │   fetch_pack (dispatcher)               │
                                     └─────────────────────────────────────────┘
                                                                │
                                                                │ produces local pack dir
                                                                ▼
        spec-kitty doctrine                ┌────────────────────────────────────────────┐
        pack validate / pack assemble  ──► │ specify_cli.doctrine.pack_validator         │
                                           │   validate_pack, ValidationResult           │
                                           │ specify_cli.doctrine.pack_assembler         │
                                           │   assemble_pack, AssemblyResult             │
                                           └────────────────────────────────────────────┘

        charter interview / generate                  ┌─────────────────────────────────────┐
        ────────────────────────────►                 │ specify_cli.doctrine.org_charter    │
                                                      │   OrgCharterPolicy, GovernancePolicy│
                                                      │   load_org_charter_policy           │
                                                      │   load_org_charter_policies (merge) │
                                                      │   apply_org_charter_pre_fill        │ ──┐
                                                      │   apply_org_charter_to_interview    │   │
                                                      └──────────┬──────────────────────────┘   │
                                                                 │ uses data parameter         │
                                                                 ▼                              │
                                                      ┌───────────────────────────────┐         │
                                                      │ charter.interview              │         │
                                                      │   apply_org_charter_pre_fill_  │◄────────┘
                                                      │     to_answers (file side-fx)  │
                                                      └───────────────────────────────┘

        DoctrineService(org_roots=[...])                 ┌─────────────────────────────────┐
        (constructed in specify_cli or charter)  ──────► │ doctrine.service.DoctrineService │
                                                         │   _org_dirs(artifact)            │
                                                         └──────────┬───────────────────────┘
                                                                    │ instantiates per-type
                                                                    ▼
                                                         ┌───────────────────────────────┐
                                                         │ doctrine.<artifact>.Repository│   (× 8)
                                                         └──────────┬────────────────────┘
                                                                    │ extends
                                                                    ▼
                                                         ┌───────────────────────────────┐
                                                         │ doctrine.base                 │
                                                         │   BaseDoctrineRepository      │
                                                         │   _apply_org_overrides (loop) │
                                                         │   _record_collision_if_present│
                                                         │   _emit_collision_warning ──► UserWarning
                                                         │     [DoctrineLayerCollision-  │
                                                         │      Warning]                 │
                                                         └───────────────────────────────┘

        spec-kitty doctor doctrine                       ┌─────────────────────────────────┐
        ──────────────────────────►                      │ specify_cli.cli.commands.doctor  │
                                                         │   doctrine_check                 │
                                                         │   _collect_doctrine_collisions   │
                                                         │     (instantiates DoctrineService│
                                                         │      and captures warnings)      │
                                                         └─────────────────────────────────┘

        spec-kitty charter lint                          ┌─────────────────────────────────┐
        ──────────────────────────►                      │ specify_cli.charter_lint.checks  │
                                                         │   .org_layer.OrgOverridesBuiltin │
                                                         │   .org_layer.OrgCharterDeviation │
                                                         └─────────────────────────────────┘
```

Lines crossing a layer boundary are import edges; all cross-layer edges go from a higher layer to a lower layer. No edge points the other way.

### Where each new component sits

| Layer | Module | Components introduced or significantly modified |
|---|---|---|
| `doctrine` | `base.py` | `DoctrineLayerCollisionWarning`, `_emit_collision_warning`, `BaseDoctrineRepository(org_dirs=...)`, `_apply_org_overrides` (loop over packs), `_record_collision_if_present` |
| `doctrine` | `service.py` | `DoctrineService(org_roots=...)`, `_org_dirs(artifact_type) -> list[Path]` |
| `doctrine` | `agent_profiles/repository.py` | `AgentProfileRepository(org_dirs=...)`, `_load_org_profiles_from_dir`, `_record_profile_collision_if_present` |
| `doctrine` | `drg/loader.py` | `load_graph_or_dir` (used by 3-layer DRG merge) |
| `doctrine` | All 8 sub-repos (directives, tactics, …, mission_step_contracts) | `org_dirs` kwarg threaded through |
| `charter` | `_drg_helpers.py` | `load_validated_graph(repo_root, org_root)` (3-layer); `_resolve_org_root` (intentionally inert stub) |
| `charter` | `context.py` | `build_charter_context_json` adds per-artifact `source` provenance + `org_charter` block |
| `charter` | `interview.py` | `apply_org_charter_pre_fill_to_answers` (pure data side-effect on YAML) |
| `charter` | `compiler.py`, `reference_resolver.py`, `synthesizer/project_drg.py`, `synthesizer/resynthesize_pipeline.py`, `synthesizer/validation_gate.py`, `synthesizer/write_pipeline.py` | Route through `load_graph_or_dir` |
| `specify_cli` | `doctrine/config.py` (new) | `OrgPackConfig`, `PackRegistry`, `load_pack_registry`, `save_pack_registry`, `resolve_org_roots` |
| `specify_cli` | `doctrine/sources/*.py` (new) | `OrgDoctrineSource` Protocol, `GitSource`, `HttpsBundleSource`, `ApiSource`, `FetchResult` |
| `specify_cli` | `doctrine/snapshot.py` (new) | `write_snapshot`, `write_pack_manifest`, `fetch_pack` |
| `specify_cli` | `doctrine/pack_validator.py` (new) | `validate_pack`, `ValidationIssue`, `ValidationResult`, `render_validation_result` |
| `specify_cli` | `doctrine/pack_assembler.py` (new) | `assemble_pack`, `ConflictItem`, `AssemblyResult`, `render_assembly_result` |
| `specify_cli` | `doctrine/org_charter.py` (new) | `OrgCharterPolicy`, `GovernancePolicy`, `load_org_charter_policy/policies`, `apply_org_charter_pre_fill`, `apply_org_charter_to_interview` |
| `specify_cli` | `doctrine/org_charter_loader.py` (new) | `load_org_charter_json_block` |
| `specify_cli` | `cli/commands/doctrine.py` (new) | `doctrine fetch`, `doctrine pack validate`, `doctrine pack assemble` command group |
| `specify_cli` | `cli/commands/doctor.py` | `doctrine_check`, `_resolve_pack_version`, `_count_pack_artifacts`, `_summarize_org_charter`, `_render_doctrine_pack`, `_collect_doctrine_collisions` |
| `specify_cli` | `cli/commands/charter.py` | `_build_doctrine_service_with_org_layer`, in-memory pre-fill wiring in `interview()` |
| `specify_cli` | `charter_lint/checks/org_layer.py` (new) | `OrgOverridesBuiltinChecker`, `OrgCharterDeviationChecker` |
| filesystem rename | `src/doctrine/<artifact>/built-in/` | 8 directories renamed from `shipped/` (provenance tag `"builtin"` unchanged) |

---

## Dependency flows and key interactions

Four interactions explain how the surfaces compose. They are sequence-style narratives; the boundary annotations call out which layer each step lives in.

### Interaction 1 — `spec-kitty doctrine fetch`

```
operator → specify_cli.cli.commands.doctrine.fetch
        → specify_cli.doctrine.config.load_pack_registry         (read .kittify/config.yaml)
        → specify_cli.doctrine.snapshot.fetch_pack(pack)         (dispatch)
            → specify_cli.doctrine.sources.GitSource / HttpsBundleSource / ApiSource
                ├── GitSource: git clone or fetch + reset --hard
                └── HTTPS / API: write_snapshot (temp dir → validate → atomic rename)
                                + write_pack_manifest (sanitised source_url)
            → returns FetchResult
        → prints per-pack outcome
```

Only this code path performs network operations. All other call paths read from local pack directories, per Constraint C-001 and Principle 4 (local-first operation).

### Interaction 2 — Three-layer resolution at read time

```
caller (charter, lint, or doctor) → DoctrineService(org_roots=resolve_org_roots(repo_root))
        → service.directives                                      (lazy property)
            → DirectiveRepository(shipped_dir=..., org_dirs=service._org_dirs("directives"), project_dir=...)
                → BaseDoctrineRepository._load
                    ├── _load_shipped_items                       (provenance: "builtin")
                    ├── _apply_org_overrides
                    │     for org_dir in self._org_dirs:           (loop in declaration order)
                    │         for yaml in scan(org_dir):
                    │             merge or add; tag provenance "org"
                    │             _record_collision_if_present  → DoctrineLayerCollisionWarning
                    └── _apply_project_overrides
                          for yaml in scan(project_dir):
                              merge or add; tag provenance "project"
                              _record_collision_if_present  → DoctrineLayerCollisionWarning
        ← returns resolved repository
```

The `_org_dirs` list is iterated **in declaration order**; later packs overlay earlier ones for the same artifact ID. The `_record_collision_if_present` helper centralises warning emission and uniformly catches all four collision shapes (org-over-builtin, project-over-builtin, project-over-org, org-pack-N-over-pack-(N-1)).

### Interaction 3 — `charter interview` org-charter pre-fill (FR-026)

```
operator → spec-kitty charter interview --defaults
    specify_cli.cli.commands.charter.interview
        → charter.interview.default_interview(...)               (builds default CharterInterview)
        → specify_cli.doctrine.org_charter.apply_org_charter_to_interview(interview_data, repo_root)
                → load_pack_registry → early return if no packs
                → load_org_charter_policies(repo_root)
                       └── for pack in registry: load_org_charter_policy(pack) and merge
                              ├── interview_defaults: last-wins on key collision
                              ├── required_directives: union, order preserved
                              └── governance_policies: dedup
                → mutate interview_data.answers (only missing keys)
                → mutate interview_data.selected_directives (only new directives)
                → return list[str] of human-readable messages
        → console.print("[cyan]Org charter:[/cyan] ...") per message
        → prompt loop (unchanged; uses interview_data as default values)
        → write_interview_answers(answers_path, interview_data)
```

Two things matter architecturally here:

- The `apply_org_charter_to_interview` helper sits in `specify_cli.doctrine.org_charter` and accepts the (mutable) `CharterInterview` instance. The charter layer hosts the dataclass and the file-level helper `apply_org_charter_pre_fill_to_answers`; the orchestration that knows about pack registry / config lives in `specify_cli`. The architecture's "data flows down, orchestration flows up" pattern is preserved.
- The pre-fill is non-destructive: existing keys are never overwritten. This is the contract that lets operators safely re-run the interview after configuring an org pack.

### Interaction 4 — Collision auditing via `spec-kitty doctor doctrine`

```
operator → spec-kitty doctor doctrine
    specify_cli.cli.commands.doctor.doctrine_check
        → load_pack_registry (enumerate configured packs)
        → for each pack: _resolve_pack_version, _count_pack_artifacts, _summarize_org_charter
        → _collect_doctrine_collisions(repo_root)
                → DoctrineService(org_roots=resolve_org_roots(repo_root), project_root=...)
                → warnings.catch_warnings(record=True) as captured:
                       getattr(service, name) for each of the 8 artifact accessors
                → regex-parse each captured DoctrineLayerCollisionWarning into a structured dict
        → render "Collisions" section + JSON `collisions` array
```

This is the only place where the warning *category* is consumed programmatically. It is also the one spot the architecture review flags as fragile (see [Recommended follow-ups](#recommended-follow-ups)).

---

## Domain concepts cross-check

This section compares the canonical glossary against the spec and the implementation. Notation: ✓ aligned, ⚠ documentation drift, ✗ outright conflict.

### Aligned terms (no action needed)

| Term | Source of truth |
|---|---|
| Doctrine (umbrella) | `docs/context/charter.md:9` matches implementation usage. |
| Charter Interview | `docs/context/governance.md:69` matches `spec-kitty charter interview` semantics. |
| Charter Compiler | `docs/context/governance.md:81` matches the synthesis pipeline. |
| Project Charter | `docs/context/configuration-project-structure.md:70` matches the project-layer artifact. |

### Discrepancies — implementation lands them; glossary and parts of spec lag

| Term | Glossary state | Spec state | Implementation state | Verdict |
|---|---|---|---|---|
| `shipped` → `built-in` rename | Glossary still uses `shipped/` paths in every `Location` field of `docs/context/charter.md` (lines 181, 194, 207, 220). | Spec is internally inconsistent: Domain Language table at `spec.md:114` mandates `"spec-kitty built-in"` and adds `"Avoid: 'shipped'"`, but FR-001 (`spec.md:132`) and the `DoctrineLayers` entity (`spec.md:202, 204`) still say `shipped`. | Code uniformly uses `built-in/` (filesystem) and `"builtin"` (provenance tag). All 8 directories were renamed via WP10. | ✗ Glossary out of date; spec internally inconsistent. |
| `provenance` vs `source attribution` | Neither term is glossed as a doctrine-specific concept (only one informal mention in `doctrine.md:139`). | Spec declares `source attribution` canonical (`spec.md:122`) and explicitly avoids `provenance label`. **But FR-003 wording (post-remediation) uses `provenance`** ("its `provenance` becomes that layer"). | Code uses `provenance` everywhere (`_provenance` dict, `get_provenance()` method). | ⚠ Spec internally inconsistent. Implementation diverges from spec's stated canonical term. Resolution: either glossary adopts `provenance` (matching code) and spec is updated, or code is renamed (large surface change). My recommendation in the [follow-ups](#recommended-follow-ups) is option 1. |
| `doctrine pack` | Closest concept in glossary is `Doctrine Catalog` (`doctrine.md:165`) — a registry of available items, not a directory primitive. | Defined at `spec.md:113`. | New primitive throughout `src/specify_cli/doctrine/`. | ⚠ Glossary needs `doctrine pack` entry; `Doctrine Catalog` relationship to `doctrine pack` should be clarified (a pack is a packagable subset of the catalog). |
| `doctrine layer` / `built-in layer` / `org layer` / `project layer` | Not defined. | Defined in Overview + Domain Language (`spec.md:115-116, 202`). | Pervasive. | ⚠ Whole-feature pivot concept missing from glossary. |
| `org pack` / `org doctrine pack` | Not defined. | Defined at `spec.md:115`. | Used throughout `specify_cli/doctrine/`. | ⚠ Add entry. |
| `pack registry` | Not defined. | `spec.md:120, 197`. | `specify_cli/doctrine/config.py` model. | ⚠ Add entry. |
| `pack assembly` / `assembled pack` / `assemble` | Not defined. | `spec.md:123`, FR-013, FR-022, C-007. | `specify_cli/doctrine/pack_assembler.py`. | ⚠ Add entry; distinguish "assembled distributable" from "hand-authored pack". |
| `pack-manifest.yaml` | Not defined. | FR-015, FR-021. | Emitted by `specify_cli/doctrine/snapshot.py::write_pack_manifest`. | ⚠ Add entry. |
| `doctrine fetch` / `doctrine pack validate` / `doctrine pack assemble` / `doctor doctrine` | Not defined. | Defined operationally in spec and FR-007–FR-013, FR-015, FR-024. | New CLI subcommand group. | ⚠ Add entries for the four operator-facing commands. |
| `DRG` / `Doctrine Reference Graph` / `GraphFragment` / `GraphExtension` | **Entirely absent.** | Used in FR-004, FR-005 and entities (`spec.md:206-207`). | Central to `doctrine.drg.loader` and `charter._drg_helpers`. | ⚠ Pre-existing gap that this mission widens. DRG is a load-bearing concept and deserves a glossary section of its own. |
| `org-charter.yaml` / `OrgCharterPolicy` / `interview_defaults` / `required_directives` / `governance_policies` | Not defined. The existing glossary `Charter` entry is project-only. | `spec.md:205`, FR-025–FR-028. | `src/specify_cli/doctrine/org_charter.py`. | ⚠ Glossary `Charter` entry must be revised to acknowledge tiered composition (built-in defaults → org charter(s) → project charter). Add entries for the three policy fields. |
| `OrgDoctrineSource` / `GitSource` / `HttpsBundleSource` / `ApiSource` / `FetchResult` | Not defined. | `spec.md:201` mentions `OrgDoctrineSource` as an entity name. | `src/specify_cli/doctrine/sources/`. | ⚠ Add Source Protocol entry. |
| `collision` / `DoctrineLayerCollisionWarning` / `shadow` / `override` / `overlay` | Not defined. ("Overlay" not used anywhere; "override" only informal.) | `spec.md:124` explicitly says "Avoid: graph overlay" (in DRG context). FR-003 uses both `override` and `shadowed`. | Code uses `shadowed` in warning text; class is `DoctrineLayerCollisionWarning`. | ⚠ Need one canonical term and one glossary entry; recommend `override` for the action, `shadow` for the resulting state, `collision` for the merge event. |
| `git-managed pack` / `local clone` / `local snapshot` | Not defined. | `spec.md:117-119` with explicit avoid-list ("avoid: cache, mirror, snapshot for git sources"). | Implemented in `sources/git_source.py` (clone) and `sources/https_source.py` / `api_source.py` (snapshot). | ⚠ Add entries; preserve spec's avoid-list discipline. |

### Drift between predecessor design blueprint and shipped behaviour

The blueprint's `## Key design decisions` table contains an entry that no longer matches reality:

> | ID collision semantics | Full-replace (org replaces shipped; project replaces org) | Simpler authoring contract than field-level merge; authors need to substitute, not patch |

The shipped semantics is **field-level merge with collision warnings**, reconciled by ADR `2026-05-16-1`. The blueprint should be amended to note "superseded by ADR 2026-05-16-1" on that row, or the row should be replaced. The blueprint's Target resolution stack diagram says "full-replace on ID collision (org overrides shipped)" — same correction applies.

This is not a defect — the post-mission review caught the inconsistency and the remediation produced the ADR. It is documentation hygiene that has to land before the next reader is misled.

---

## User journey impact analysis

Source: `docs/plans/user_journey/`.

| Journey | Affected? | Net change |
|---|---|---|
| 001 — Project Onboarding & Bootstrap | PARTIAL | The Phase-3 agent customisation and Phase-4–7 charter capture phases gain org-charter pre-fill via `apply_org_charter_to_interview`. The Project Owner now sees org-pre-selected approaches / directives instead of a blank slate; org-pack-supplied items appear in catalogs alongside built-in. Mitigation: `DoctrineLayerCollisionWarning` can surface during bootstrap if an org pack shadows a built-in approach — bootstrap UX should explain provenance, or new operators may be confused. |
| 002 — System Architecture Design | NO | Operates on `architecture/*` and ADR artifacts. Doctrine-layered governance does not enter this workflow. |
| 003 — System Design & Shared Understanding | NO | Operates on the living glossary (a per-project artifact, not a doctrine layer). The shipped→built-in rename is invisible from this journey. |
| 004 — Curating External Practice into Governance | YES | Phase-4 governance integration and Phase-5 charter selection gain a new placement target: an artifact can now be curated **into the org layer** (a shared pack) instead of only the project layer. `spec-kitty doctrine pack validate` and `pack assemble` let a curator test a candidate pack before publishing. Risk: schema-gate (Coordination Rule 4) must now consider cross-layer validity; `DoctrineLayerCollisionWarning` may fire when curated org tactics shadow built-in tactics. |
| 005 — Governance Mission Charter Operations | YES (most impacted) | Phase 2 (Curate) and Phase 6 (Apply charter extraction) directly interact with the new layered model. `charter sync` must reconcile org-layer directives alongside project selections. `charter status` should reflect which selections come from org vs project. Coordination Rule 1 (HIC escalation under D-011) gains a new trigger: collision warnings. The new `spec-kitty doctrine` group plus `doctor doctrine`'s Collisions section become first-class workflow surfaces. |
| Init Doctrine Flow (`init-doctrine-flow.md`) | YES | The decision tree's "defaults" path (Path 1) previously loaded `src/charter/defaults.yaml` only. The loader chain is now built-in → org → project, so an org may override the default paradigms / directives that `_apply_doctrine_defaults()` writes. Paths 2/3 gain pre-population via `apply_org_charter_to_interview`. `spec-kitty doctrine fetch` can hydrate an org pack before `spec-kitty init` runs, so CI bootstraps inherit org policy without per-repo configuration. Risk: NFR-001 (≤2 s) could regress if org-pack fetch is in the critical path; the checkpoint format does not record layer provenance, so a resumed interview after org-pack changes may produce inconsistent answers. |
| Evaluation document | METADATA-ONLY | The journey index should note that the layered doctrine model introduces a canonical surface (org layer + doctrine CLI) not represented in any current journey; consider promoting a new journey from the brainstorm set. |

### Net-new journey candidate

None of the existing journeys covers the operator-facing flow:

> *Discover an org pack → fetch it → validate it → assemble against project → audit collisions via `spec-kitty doctor doctrine` → confirm provenance via `charter context --json`.*

This is plausibly **Journey 006 — Adopting and Auditing an Organisation Doctrine Pack**, with the platform / governance lead as primary actor, `DoctrineLayerCollisionWarning` events as a first-class coordination signal, and the Collisions section of `doctor doctrine` as the acceptance surface. The `init-doctrine-flow` note captures a partial slice (defaults loading) but does not cover multi-pack composition, fetch lifecycle, or collision triage.

---

## Architectural intent fit

### Where the implementation honours the intent

- **Layer rule (ADR 2026-03-27-1).** All 8 layer-rule tests pass. The two places where this rule shaped the design — the inert `_resolve_org_root` stub in `charter._drg_helpers` and the lifting of org-charter loading into `specify_cli.doctrine.org_charter_loader` — are documented and tested.
- **Local-first operation (Landscape README Principle 4).** Network access is confined to `spec-kitty doctrine fetch`. Every resolution / context / lint path is offline. Constraint C-001 and FR-018 enforce this.
- **Governance at the execution boundary (Principle 5).** The same `DoctrineService` that the runtime consumes for agent context now resolves all three layers; agents do not need to know whether a directive came from the org pack or the built-in defaults.
- **Doctrine package isolation (Landscape README §Dependency Rules).** The new behaviour fits inside `BaseDoctrineRepository` and `AgentProfileRepository`; the doctrine layer's API surface to charter is unchanged in shape (same `service.directives.list_all()` etc.).
- **Shared-package boundary (ADR 2026-04-25-1).** The feature introduces no new shared-PyPI consumption, no `spec_kitty_runtime` imports in production code, and no new edges into `spec_kitty_events` / `spec_kitty_tracker`.

### Where the implementation deviates from intent — and why it is defensible

- **Field-merge instead of full-replace.** The blueprint listed full-replace as a key design decision; the implementation preserved the pre-existing field-merge `_merge()`. The post-mission ADR `2026-05-16-1` documents the rationale (zero migration burden for existing project overlays; operator ergonomics; the user-mission-review feedback explicitly asked for collision visibility rather than behaviour change). Net effect: the spec was updated to match the code; user-facing behaviour is identical to pre-mission baseline plus the new collision warnings.
- **`charter interview` pre-fill landed late.** Initially WP09 produced the helper without wiring; the wiring landed in the post-mission remediation. This is the only place where the mission shipped an unconsumed surface; the gap was caught by mission review and closed within a day.

### Where intent and implementation are in tension, and the tension is not yet resolved

- **Documentation drift.** The mission delivered the feature; the glossary and parts of the spec did not catch up. The cross-check above lists ~30 new doctrine concepts unglossed and 2 spec inconsistencies (`shipped`/`built-in`, `provenance`/`source attribution`). This is recoverable but should be done before any downstream mission inherits the vocabulary.
- **Brittle warning-string parsing.** `doctor.py::_collect_doctrine_collisions` regex-parses warning messages to reconstruct structured collision data. If the warning format ever changes, doctor silently drops collisions from its JSON output. The post-mission review flagged this as a follow-up; the architecturally clean fix is to carry structured data as attributes on the `DoctrineLayerCollisionWarning` instance (e.g. `DoctrineLayerCollisionWarning(item_id=..., higher_layer=..., ...)`) and have doctor consume those attributes rather than the formatted message.
- **`_resolve_org_root` is intentionally inert.** This is correct given the layer rule, but the function exists and is callable; a future reader may assume it is meant to do real work. Adding a `__deprecated__`-style marker, or removing the function and inlining the `None` return at the single call site, would make the intent unambiguous.

### Architectural intent gaps the feature surfaces

- **Multi-pack within the org layer has no explicit "collision policy" UX.** Today, when packs collide on an artifact ID, the later pack wins silently (subject to warnings). The architecture intent statements in the landscape README emphasise traceability of governance decisions. A future capability — a `pack overrides allow:` policy in `org-charter.yaml`, or an explicit collision policy at registry level — would let governance leads codify *which* packs are allowed to override *which* others, beyond just observing that they do.
- **No DRG-extension fidelity check at the registry boundary.** `pack validate` checks a single pack; `pack assemble` checks the merged output. There is no operator-facing equivalent of "validate the resolved DRG across all configured packs in this project before installing them". `doctor doctrine` enumerates packs but does not currently exercise the DRG merge. This is consistent with the mission's scope (single-pack and assembled-pack validation), but the multi-pack case is the operator's common one.

---

## Recommended follow-ups

Ordered by leverage (high-impact items first).

1. **Update the glossary** (`docs/context/charter.md` + `governance.md` + `configuration-project-structure.md`) to add the ~30 net-new concepts from the cross-check table and revise the `Charter` entry to acknowledge tiered composition. Replace every `shipped/` path with `built-in/`. Estimated effort: 1 PR; ~300 lines net additions.
2. **Reconcile the mission spec internally** (`kitty-specs/layered-doctrine-org-layer-01KRNPEE/spec.md`): change FR-001 wording from `shipped` to `built-in`; rename the `DoctrineLayers` and `SourceAttribution` entities accordingly; pick one canonical term among `provenance` vs `source attribution` (recommendation: `provenance`, since that is what the code uses end-to-end). The spec is the source of truth for future maintenance — internal inconsistency multiplies its cost. Estimated effort: 1 small PR.
3. **Amend the predecessor blueprint** (`docs/development/layered-doctrine-resolution-design.md`) to note that the `ID collision semantics` row was superseded by ADR `2026-05-16-1` and the `Target resolution stack` diagram should describe field-merge with collision warnings. Estimated effort: 5-line edit.
4. **Refactor `DoctrineLayerCollisionWarning` to carry structured data**, and update `doctor.py::_collect_doctrine_collisions` to consume attributes instead of regex-parsing the message string. This removes the brittleness flagged in MEDIUM-1's post-review and makes the JSON output schema-stable. Estimated effort: small PR; touches `src/doctrine/base.py`, `src/doctrine/agent_profiles/repository.py`, `src/specify_cli/cli/commands/doctor.py` plus tests.
5. **Add a Journey 006** to `docs/plans/user_journey/` covering org-pack adoption + collision audit, with the platform lead as actor. Use the existing user-journey template; the workflow content is already implicit in the `docs/guides/create-an-org-doctrine-pack.md` how-to.
6. **Wire `apply_org_charter_to_interview` into the non-interactive `default_interview` compile path** at `src/specify_cli/cli/commands/charter.py:1385` (the second call site flagged in the HIGH-2 review). Today only the interactive `charter interview` command applies the pre-fill; agent-driven non-interactive bootstraps do not. Estimated effort: 1 small PR; mirrors the HIGH-2 pattern.
7. **Add a dedicated pack-N-over-pack-(N-1) collision test** (current coverage is incidental in `TestMultiplePackPrecedence`). Future refactors of the org-loop could regress without this guard.

---

## Process architecture: where the glossary / architecture alignment failed

The mission shipped 10 well-tested WPs and passed every per-WP review. Three substantive drifts surfaced only at post-merge mission review (HIGH-1 multi-pack, HIGH-2 dead-code wiring, MEDIUM-1 spec vs code on field-merge), and the ~30 glossary terms left unglossed surfaced only when **this** review was performed.

The question is: was this an execution error (the people / agents skipped a check that exists), a structural gap (no check exists), or both?

The evidence below says **both — but the structural gap is primary and reliably reproduces the execution failure**. Fix the structure and the execution failure becomes unlikely; lecture the operators without fixing the structure and the failure recurs in the next mission.

### Evidence from this mission

| Artifact | Status on disk | Implication |
|---|---|---|
| `kitty-specs/.../analysis-report.md` or equivalent | **Absent** | `/spec-kitty.analyze` was never invoked on this mission. |
| `kitty-specs/.../checklists/requirements.md` | Present | The requirements-quality checklist ran. It is scoped to "do the FRs have IDs, statuses, measurable thresholds" — not to terminology or ADR alignment. |
| `kitty-specs/.../mission-review-report.md` | Present (from my run) | Mission-review post-merge caught MEDIUM-1 and HIGH-1/HIGH-2. It missed the glossary-vs-spec drift because the skill text does not direct the reviewer to compare against `docs/context/*.md`. |
| `kitty-specs/.../tasks/WP02-base-repository-org-layer.md` | Contains the line: *"Key invariant to preserve: The existing `_merge()` (field-level merge) is used … The same field-level merge is used for org overrides of shipped."* | The WP02 task file **explicitly ratified field-merge** as a key invariant. The mission spec (`spec.md` FR-003) **explicitly forbade field-merge**. No reviewer caught the contradiction between the WP task file and the spec it depends on. |
| Reviewer profile `reviewer-renata.agent.yaml` | Loads directive **032 Conceptual Alignment** with rationale: *"Terminology in code and docs must align with the project glossary — language drift signals architectural drift."* | The structural rule for glossary alignment **exists and is loaded by the reviewer's profile**. It was not applied — the per-WP review prompts do not surface a glossary checklist step. |

### Where each alignment SHOULD happen, what each tool DOES, and the gap

Walking the mission lifecycle:

| Phase | Tool / skill | Theoretical capability | What it actually does | Gap |
|---|---|---|---|---|
| `/spec-kitty.specify` | `.claude/commands/spec-kitty.specify.md` + author | Could require the spec to cite glossary terms; could auto-flag undefined domain language | No glossary check. Does say "do not mix functional and non-functional"; does not say "cite the glossary for any new domain term you introduce". | **STRUCTURAL**: no glossary linter on spec-authoring boundary. |
| `/spec-kitty.plan` | `.claude/commands/spec-kitty.plan.md` + author | Could require the plan to cite architectural ADRs; could compare the plan's design decisions against existing ADRs and flag conflicts | No ADR-fit check. The blueprint's "full-replace" decision contradicted both the existing `_merge()` code and what would later become ADR `2026-05-16-1`; no automation detected this. | **STRUCTURAL**: no automated "this plan conflicts with ADR X" check. |
| `/spec-kitty.tasks` + `tasks-finalize` | `.claude/commands/spec-kitty.tasks.md` | Could require each WP's `owned_files` to be consistent with the spec / plan invariants | Validates dependency graph + lane assignment. No content checks (no "the WP02 'Key invariant to preserve' note must agree with FR-003"). | **STRUCTURAL**: WP-level invariant notes are free-form prose; no formal contract that binds them to the spec text. |
| `/spec-kitty.analyze` | `.claude/commands/spec-kitty.analyze.md` (CRITICAL: this skill exists and would have caught some drift) | Detection passes include "Terminology drift (same concept named differently across files)" and "Charter Alignment" — `Inconsistency` category F | **It is opt-in and not gated.** Never invoked on this mission. The skill only checks spec/plan/tasks against each other and against the project charter — **NOT against `docs/context/*.md` or against `docs/adr/2.x/*.md`**. | **PRIMARY STRUCTURAL + EXECUTION**: opt-in (executor can skip → did skip) AND scope-limited (would not have caught glossary drift even if run). |
| `/spec-kitty.implement` (per-WP) | `.claude/commands/spec-kitty.implement.md` + per-WP prompt file | Could surface a "consult glossary before introducing terminology" checklist item | The generated prompt focuses on `owned_files`, acceptance criteria, integration verification. No glossary surface. | **STRUCTURAL**: implement-prompt template does not include a terminology-fidelity item. |
| `/spec-kitty.review` (per-WP) | `.claude/commands/spec-kitty.review.md` + reviewer profile | reviewer-renata has directive 032 loaded; the directive's rationale is "Terminology in code and docs must align with the project glossary" | The review prompt does NOT include a glossary-check step. **Directive loaded ≠ checklist enforced.** No item in the per-WP review prompt prompts the reviewer to grep the glossary. | **STRUCTURAL + EXECUTION**: the review prompt template owes the reviewer a glossary checkpoint; it doesn't have one. The directive is information, not enforcement. |
| `spec-kitty-mission-review` (post-merge) | `.claude/skills/spec-kitty-mission-review/SKILL.md` (the skill I ran for this mission) | Step 5 (FR Trace) and Step 6 (Drift and Gap Analysis) could be extended to include a "glossary diff" pass and an "ADR diff" pass | Caught MEDIUM-1 because the spec's text is internally inconsistent (FR-003 in plan vs FR-003 wording in spec.md). Did NOT catch: (a) `shipped` → `built-in` rename inconsistent across spec sections; (b) `provenance` vs `source attribution` term clash; (c) ~30 doctrine concepts unglossed. The skill's drift detection is implementation-vs-spec, not spec-vs-glossary. | **STRUCTURAL**: glossary diff is not a step in the skill. |
| `spec-kitty-glossary-context` (curation skill) | `.claude/skills/spec-kitty-glossary-context/SKILL.md` | Pull-based: operator says "update the glossary" or "fix term drift" | It is operator-pull, never auto-invoked on any mission boundary. | **STRUCTURAL**: the curation tool is not wired into the planning / review pipeline. |
| `tests/architectural/test_layer_rules.py` | pytestarch static analysis | Enforces import-direction rules at code level | Works correctly. Caught nothing during the mission because the implementer correctly respected the boundary (with one early confusion that was resolved). | (Not a gap — code-level structural check that worked as designed.) |

### Verdict: structural gap is primary

There are **four** distinct missed checks, of which **three are structural gaps** and **one is an execution failure that the structural gap created**:

1. **STRUCTURAL — Glossary alignment never gates a phase.** `docs/context/*.md` is treated as a reference document, not as a gate input to any tool. The reviewer profile loads directive 032, but the per-WP review prompt template never surfaces it as a checklist item. The mission-review skill (which I ran) does not include a glossary-diff step. The `spec-kitty-glossary-context` skill is operator-pull, never auto-invoked.
2. **STRUCTURAL — No planning-time ADR-fit check exists.** `/spec-kitty.plan` and `/spec-kitty.analyze` validate spec/plan/tasks against each other and against the project charter, never against `docs/adr/2.x/*.md`. The "full-replace vs field-merge" intent drift was thus undetectable until post-merge.
3. **STRUCTURAL — WP task-file "Key invariant to preserve" notes are unbound to the spec.** WP02 wrote "field-level merge is the key invariant" while FR-003 said the opposite. There is no contract that binds WP-level invariant notes to the spec they implement; no analyzer cross-checks them.
4. **EXECUTION — `/spec-kitty.analyze` was not invoked on this mission.** It is opt-in. The operator skipped it. (Even if invoked, it would only have caught the spec's internal FR-001 vs FR-003 inconsistency on `shipped` — the structural-gap analysis above explains why everything else was outside its scope.)

The structural gaps reliably reproduce the execution failure. An operator running `/spec-kitty.analyze` on the next mission would still miss the glossary drift (because analyze doesn't compare against the glossary). A reviewer applying directive 032 would still skip the glossary check (because the review prompt doesn't surface it). The only place the failure stops is post-merge mission review — and even my own application of that skill missed the glossary drift.

### Recommended process-architecture changes

Ordered by leverage. These are skill / prompt / template changes, not new tooling. None require new modules.

1. **Add a glossary-alignment detection pass to `/spec-kitty.analyze`.** Extend the skill text to enumerate every domain term used in `spec.md` and grep it against `docs/context/*.md`. Findings go in a new Section G ("Glossary Alignment") with severity HIGH for "spec introduces term not in glossary" and MEDIUM for "spec uses term with different definition than glossary". Effort: skill text update; no new code.
2. **Add an ADR-fit detection pass to `/spec-kitty.analyze`.** Enumerate the decisions in `plan.md`'s "Architecture / stack choices" section and compare against the title lines of `docs/adr/2.x/*.md`. Findings flag any plan decision that contradicts an existing ADR's title. Effort: skill text update.
3. **Make `/spec-kitty.analyze` a gate before `/spec-kitty.implement`, not an optional pre-flight.** Today the operator can skip it; the analysis report should be a required artifact (saved to `kitty-specs/<mission>/analysis-report.md`) before any WP enters `in_progress`. Implementation: a check in `spec-kitty agent action implement` that errors if `analysis-report.md` is missing OR was generated against an older `spec.md` mtime. Effort: small CLI change + skill update.
4. **Surface directive 032 in the per-WP review prompt.** The reviewer profile already loads directive 032 (Conceptual Alignment). The per-WP review prompt template (in `src/specify_cli/.../review_prompts/`) should include a step: *"For every new domain term in the WP diff, confirm it appears in `docs/context/*.md` with the same meaning. Flag mismatches."* This converts "directive in profile context" into "checklist item the reviewer cannot skip silently". Effort: prompt-template addition.
5. **Bind WP task-file "Key invariant to preserve" notes to the spec.** Either drop the prose-only field (and replace with explicit `requirement_refs` of the FRs the invariant restates), or have `tasks-finalize` parse the prose and emit a warning if the invariant's claim contradicts the referenced FR's text. Lighter alternative: forbid the prose field entirely; rely on `requirement_refs` and let `/analyze` do the comparison.
6. **Extend the `spec-kitty-mission-review` skill with a glossary-diff and ADR-diff step.** Add steps 5.5 (Glossary Diff) and 5.6 (ADR Alignment) to the skill text. These run after the FR Trace and before the verdict. Findings of class GLOSSARY-DRIFT or ADR-CONTRADICTION elevate the report verdict to PASS-WITH-NOTES at minimum.
7. **Auto-invoke `spec-kitty-glossary-context` curation on every `/spec-kitty.specify` boundary.** When a new spec is created, the skill should be asked to enumerate the spec's domain terms and propose glossary updates as a separate PR companion. Curator can accept or modify; the mission cannot proceed to `/plan` until the glossary side-PR is at least proposed.

### Architect's verdict on root cause

The implementation team did good work. The drift problems are not "people skipped their checks"; they are "the system does not have a check at the right boundary, so the check that exists in the profile directive never becomes a checklist item the reviewer reads".

The single highest-leverage fix is **#4 (surface directive 032 in the per-WP review prompt)**, because it converts existing latent guidance into actively-applied review work without requiring new tooling or new skills. The second highest-leverage fix is **#3 (make analyze gating, not optional)**, because it converts a power-user skill into a default gate that catches half the drift before code lands.

---

## Root cause: is this caused by a lack of project charter, or a deeper issue?

The project has a charter — `.kittify/charter/charter.md`, 278 lines, version 1.1.5, actively maintained. So the answer to "is this caused by lack of charter" is **no**. The deeper issue is what the charter itself documents at lines 266-272:

> **Regression Vigilance (2026-04-06):** The `--feature` → `--mission` rename has been a persistent source of regressions. Mission 065 swept ~45 user-facing references, **but the pattern keeps recurring because:**
> 1. New code copies from old code that still uses `feature` as variable names …
> 2. Error messages and guidance strings are written ad-hoc without checking the canon
> 3. **Subagent-implemented code may not see this charter**

The charter is **conscious of its own enforcement failure**. It explicitly names the structural problem (point 3) and tries to compensate with "Hyper-vigilance rules" — but those rules are still prose ("Code reviewers MUST grep for …"), not automated gates. What just happened with `shipped → built-in` and `provenance / source attribution` is the same pattern the charter predicted, simply applied to a different term-pair that hasn't yet earned its own "Regression Vigilance" section.

### Three nested causes, deepest first

1. **Dogfood gap (deepest).** Spec-kitty is the framework that builds layered doctrine pipelines for other projects — three-layer resolution, provenance tagging, charter-context injection, doctrine-pack validation, the whole apparatus. **Spec-kitty does not auto-apply that pipeline to its own missions.** When the doctrine framework runs on the doctrine framework's own development, the doctrine layer is read-only context; nothing in the workflow injects the charter's terminology canon into the per-WP review prompt the way `charter context --action implement` would inject it into a downstream consumer's agent context. The charter is documentation that humans (and human-driven LLM reviewers) are expected to read; it is not a gate.
2. **Policy-vs-mechanism asymmetry.** The charter contains policy ("terminology canon", "regression vigilance rules", "code reviewers MUST grep for X"). The framework lacks mechanism — there is no `spec-kitty agent action review` step that calls a terminology linter, no `/spec-kitty.analyze` pass that diffs against the charter's `Terminology Canon` section. The reviewer profile loads directive 032 *because directive 032 exists in the doctrine catalog*, but the review prompt template does not render it as a checklist item. Policy without mechanism degrades to empty process.
3. **Drift-prone artefact split.** The same canonical term lives in five places: `docs/context/*.md`, `charter.md` "Terminology Canon", individual ADRs, mission spec Domain Language tables, and code symbols. There is no single source of truth and no diff between them. The charter's "Hyper-vigilance" section is the symptom of recognising this — a senior reviewer noticed the same drift kept recurring across missions and tried to legislate against it. Legislation without an executor is hope.

### Why "more charter" is not the answer

If we wrote a new charter clause that said "every spec must cite the glossary for any new term" or "every WP review must run a glossary-diff before approval", we would be solving the wrong problem. The charter already says equivalent things for Mission/Feature and Branch-Intent terminology. The next mission would still drift in some other dimension because charter prose is not what blocks merges — automated gates are. Adding more prose to the charter without adding the gate is what produced the 2026-04-06 "Regression Vigilance" pattern: an honest admission of recurring failure addressed with more prose.

### What the answer actually is

The structural-gap recommendations from [Process architecture](#process-architecture-where-the-glossary--architecture-alignment-failed) above, with one addition: a charter clause that **says spec-kitty must enforce its own charter via gates, not via reviewer attention**. Specifically:

- `/spec-kitty.analyze` becomes a gate (not opt-in) AND extends its detection to diff against `charter.md`, `docs/context/*.md`, and `docs/adr/2.x/*.md`.
- The per-WP `review` prompt template renders directive 032 as an explicit checklist item the reviewer must answer.
- `spec-kitty-mission-review` skill grows a glossary-diff and ADR-diff step.

These three changes are the mechanism the charter is missing. They convert "Hyper-vigilance rules" (prose appeals to reviewer attention) into "gates that fail loudly when drift is introduced".

### One-line takeaway

It is not a charter gap. It is a **dogfood gap**: spec-kitty's own missions are not subject to the same auto-applied doctrine pipeline that spec-kitty builds for its users. Closing the dogfood gap is the structural fix; everything else is symptom management.

---

## Empirical addendum: the doctrine/charter pipeline IS invoked at the implement boundary — but what it returns is degenerate

After the first round of analysis above, a sharper read of the question came back: *the framework IS being used to build itself; the issue is what the pipeline emits at the entry point*. To answer empirically I installed `spec-kitty-cli==3.1.8` in a fresh venv and inspected (a) what `spec-kitty charter context --action implement` returns and (b) what the WP-prompt builder actually injects into the generated implement prompt.

### What the canonical lookup returns

Running `spec-kitty charter context --action implement` against this project (a software-dev mission) returns this verbatim:

```
Action: implement (compact)
Governance:
  - Template set: software-dev-default
  - Paradigms: (none)
  - Tools: git, spec-kitty
Directive IDs:
  - DIR-001
  - DIR-002
  - DIR-003
  - DIR-004
Tactic IDs:
  - (none)
Section Anchors:
  - Spec Kitty Charter
  - Purpose
  - Technical Standards
  - Languages and Frameworks
  - Testing Requirements
  - Performance and Scale
  - Deployment and Constraints
  - Architecture: Shared Package Boundaries
  - ... (35 more section anchors) ...
  - Terminology Canon (Mission vs Feature)
  - Regression Vigilance (2026-04-06)
  - Diagnostics: No available_tools selection provided; using runtime tool registry fallback. | Template set not selected in charter; fallback 'software-dev-default' applied.
  - Languages: python
  - Project root: .../.kittify/doctrine
```

### What the WP implement prompt actually contains

The runtime prompt builder calls this same resolver. `src/specify_cli/next/prompt_builder.py::_build_wp_prompt` invokes `_governance_context(repo_root, action="implement")` at line 147 for every implement and review prompt, and the function in turn calls `charter.context.build_charter_context(repo_root, action=action, mark_loaded=True)` at line 273. The output is injected verbatim into the WP prompt above the "CRITICAL: work package ISOLATION RULES" block.

The implement template at `src/specify_cli/missions/software-dev/command-templates/implement.md:68-71` then **explicitly forbids** the agent from looking elsewhere for governance:

> *"The output of `spec-kitty agent action implement ...` is the authoritative work package prompt and execution context. Do **not** separately call `spec-kitty charter context` or rummage through unrelated files looking for a 'newer' prompt unless the command output tells you to."*

So the pipeline IS wired. The entry point exists. The agent is told to trust it.

### Why "compact wiring + authoritative" still failed

The resolved context the agent receives is informationally degenerate in four ways that compound:

1. **Section anchors only, not section bodies.** The `Section Anchors` list contains `Terminology Canon (Mission vs Feature)` and `Regression Vigilance (2026-04-06)` as headings. **The actual hyper-vigilance rules in those sections — the very prose that says "Use Mission as canonical, Feature is prohibited, reviewers MUST grep for --feature" — do not appear in the prompt.** The agent sees a table of contents and is told to treat it as authoritative.

2. **Charter directive namespace ≠ doctrine catalog directive namespace.** The lookup returns `DIR-001 / DIR-002 / DIR-003 / DIR-004`. Those are the project's actual directives, auto-extracted from `charter.md` by `spec-kitty charter sync` (the file `.kittify/charter/directives.yaml` is auto-generated and contains exactly these four). However, the agent profile loaded for the WP (e.g. python-pedro for an implementer) references **doctrine-catalog directives** in a parallel namespace: `DIRECTIVE_010` (Specification Fidelity), `DIRECTIVE_024` (Locality of Change), `DIRECTIVE_025` (Boy Scout), `DIRECTIVE_030` (Test & Typecheck Quality Gate), `DIRECTIVE_034` (Test-First). Those `DIRECTIVE_NNN` IDs **do not appear** in the resolved charter context. The reviewer's profile references `DIRECTIVE_032` (Conceptual Alignment — the very directive that says "terminology in code and docs must align with the project glossary"). It also does not appear. The charter sync extracts charter-prose directives into the charter namespace; the doctrine catalog directives are never surfaced at the WP-prompt boundary.

3. **`Tactic IDs: (none)` and `Paradigms: (none)`.** The reviewer-renata profile cares about tactics like `code-review-incremental`, `language-driven-design` (which the profile's rationale explicitly says: *"Detect terminology conflicts in diffs as early signals of architectural problems"*), `reverse-speccing`, `test-readability-clarity-check`. None of these surface. The doctrine catalog has dozens of tactics; the resolver returns zero.

4. **Charter sync fallback diagnostics are buried.** The resolved context has a `Diagnostics:` line that reveals **two systemic config gaps in this project's charter**: *"No available_tools selection provided; using runtime tool registry fallback. | Template set not selected in charter; fallback 'software-dev-default' applied."* These diagnostics tell the experienced reader that the charter is under-specifying its own configuration — but they're at the bottom of the section-anchor list, buried in prose, easy to miss.

5. **Glossary and ADR pointers are absent.** There is no line that says "consult `docs/context/*.md` for canonical terminology" and no line that says "the ADRs that constrain this work live in `docs/adr/2.x/*.md`". The agent has no signposted way to discover either, and the template's "do not rummage" rule actively discourages looking.

### The mechanism that produced the recent drift, in one sentence

The WP implement / review prompt **invokes the doctrine-charter pipeline, gets back a table of contents with four charter-extracted directives and zero tactics in the wrong ID namespace, and tells the agent that this content-free injection is authoritative.** No directive, no tactic, no glossary pointer, no ADR pointer — and an explicit instruction not to look elsewhere. The agent then implements code without the governance it would have read if it had been allowed to look.

This is exactly the past pattern. The Mission-vs-Feature "Regression Vigilance (2026-04-06)" section in `charter.md` is the symptom of the same root cause: when the only place a rule lives is the section body of `charter.md`, and the WP prompt surfaces only the section title, the rule is invisible to the executing agent — by design.

### What the entry point is missing

| Component | Current behaviour | Needed behaviour |
|---|---|---|
| `charter context --action implement` | Returns section anchors, charter-extracted directives (DIR-NNN), no tactics, no paradigms, no glossary pointer, no ADR pointer. | Return section anchors **plus** the body of every section whose anchor is critical for the action (e.g. `Terminology Canon`, `Regression Vigilance`, `Code Review Checklist`); resolve the loaded **agent profile**'s `directive-references` and `tactic-references` into actual `DIRECTIVE_NNN` and tactic bodies; emit explicit pointers to `docs/context/*.md` and `docs/adr/2.x/*.md`. |
| `charter sync` (the auto-extractor) | Walks `charter.md` and extracts items it heuristically tags as directives into `directives.yaml` with sequential `DIR-NNN` IDs. | Cross-link extracted directives to doctrine catalog `DIRECTIVE_NNN` IDs when the charter cites them by reference (e.g. "see directive 032"). Today there is no such cross-link; the two namespaces float free. |
| `_governance_context` in `prompt_builder.py` | Calls `build_charter_context(action=action, mark_loaded=True)` once and injects the compact text. | Additionally render the **loaded agent profile's** directive-references and tactic-references inline (the profile is selected for the WP — it should pull its own directives into the prompt). |
| `implement.md` runtime template lines 68-71 | Explicitly forbids the agent from looking elsewhere. | Either (a) remove the forbid clause now that the prompt is augmented, or (b) keep the forbid clause AND ensure the prompt actually contains the rule bodies, not just anchors. |
| `.kittify/charter/charter.md` | Does not declare a template set, does not declare `available_tools`. | Add an explicit `template_set: software-dev-default` and `available_tools: [...]` block so the diagnostics fallback messages disappear and the resolver knows what to load. |

### Updated root cause

It is not a charter gap (the charter exists, 278 lines, well-maintained). It is not exactly a dogfood gap either — the pipeline IS invoked. It is a **content gap at the resolution boundary**: the doctrine-charter lookup returns anchors instead of rules, returns the wrong directive namespace, returns no tactics, and points at no external authority (glossary, ADRs). The implement template then declares this anchor-only injection authoritative and forbids the agent from compensating. Two namespaces (charter `DIR-NNN`, doctrine catalog `DIRECTIVE_NNN`) coexist without a cross-link. The profile's loaded directives never surface in the prompt the profile's own agent will read.

The "missing entry point" the user identified is precisely this: the entry point is wired, but it does not carry the payload. Adding the payload — section bodies, profile-referenced directives and tactics, glossary pointer, ADR pointer — is the structural fix.

---

## Verification

- All 96 architectural layer-rule tests pass (`tests/architectural/`). Confirmed at HEAD on `feat/org-doctrine-layer`.
- All 2566 doctrine + charter + specify_cli/doctrine + new collision CLI tests + architectural tests pass.
- `ruff` and `mypy` are clean on the 13 source modules and 6 test modules touched by the three post-mission remediations.
- The full suite reports 17634 passed, 244 failed. The 244 failures are concentrated in `tests/tasks/test_planning_workflow_integration.py`, `tests/tasks/test_tasks_2x_unit.py`, and `tests/test_dashboard/test_scanner.py` — all pre-existing and unrelated to the doctrine / charter / specify_cli.doctrine modules touched by this feature.

The implementation is structurally sound. The work left is documentation alignment, not behavioural correction. The process-architecture changes recommended above are the way to prevent the same pattern in the next mission.
