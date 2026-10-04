# Implementation Plan: Pack skills: charter-activatable skill kind (slices 0+1)

**Branch**: `claude/festive-babbage-lhkqac` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: ADR `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`, issue #5193.

## Summary

Add a charter-activatable doctrine kind `skill` (URN `skill:<id>`) whose org/project-tier artifacts are rendered into project skill roots by the managed doctrine-skill installer. Slice 0 (precondition) is mostly already on main: grounding found `_BUILTIN_ARTIFACT_KINDS`, `_ALLOWED_KINDS` and `_ORG_DRG_KIND_ALIASES` derived; the remaining lockstep copies are `REQUIRED_KIND_FIELDS` (specify_cli) vs its disagreeing charter twin, and `_SINGULAR_TO_PER_KIND_FIELD`.

## Technical Context

**Language/Version**: Python 3.11+ · **Dependencies**: pydantic, ruamel.yaml, typer (existing) · **Testing**: pytest (`tests/charter`, `tests/doctrine`, `tests/specify_cli/skills`, specific `tests/architectural/` gates) · **Constraints**: layer direction `kernel <- charter <- specify_cli`; complexity ≤15; no new suppressions.

## Charter Check

- Single canonical authority (DIRECTIVE_044): skill bodies are thin; substance fetched via `charter context --include`. ✅
- DRG edges are the relationship authority (ADR 2026-07-26-1): skill → procedure only via fragment edges. ✅
- Pack tiers (ADR 2026-08-16-3): no `packs/built-in/skills/` content; internal pack excluded from wheel. ✅
- ATDD red-first: SC-001 acceptance test written first and recorded red. ✅
- No full heavy suites locally (NO_FULL_HEAVY_SUITES_IN_MISSION). ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/pack-skills-kind-01M43419/
├── spec.md  plan.md  tasks.md  tasks/
```

### Source Code (repository root)

```
src/charter/offering/artifact_kinds.py          # SKILL member + tables + org_requirable fact
src/charter/offering/drg/models.py              # NodeKind.SKILL
src/charter/offering/skills_kind/               # NEW: models.py (PackSkill), repository.py, validation
src/charter/offering/schemas/skill.schema.yaml  # NEW
src/charter/offering/drg/extractor.py           # _emit_skill_nodes (built-in shard, empty at MVP)
src/charter/activation/skill_preparation.py     # NEW: prepare_project_skill_activations (project-root seam over a pure core)
src/charter/activation/{pack_context,org_pack_discovery,drg_activation,delivery_table}.py
src/specify_cli/doctrine/org_charter.py         # required_skills, skill_namespace; derived REQUIRED_KIND_FIELDS
src/specify_cli/skills/catalog.py               # NEW: resolve_project_skill_catalog (the one seam)
src/specify_cli/skills/pack_skill_renderer.py   # NEW: render SKILL.md (+ preamble, wrapper expansion)
src/specify_cli/skills/{installer,verifier,registry}.py, runtime/agent_skills.py,
  upgrade/migrations/m_*skill*.py, upgrade/assessment.py, tool_surface/providers/managed_skills.py
src/specify_cli/cli/commands/_doctrine_health.py / _doctrine_collect.py  # skill health dimension
tests/...                                        # mirrored
```

## Design decisions (ADR open questions resolved)

1. **Project-tier namespace**: required config key `charter_packs.project.skill_namespace` in `.kittify/config.yaml`; a project-tier skill without it is refused with a remedy. Org packs declare `skill_namespace` in `org-charter.yaml`.
2. **Run-time binding placeholders**: deferred to slice 2 (C-005); rendered files contain no bindings.
3. **`/name` exposure**: recorded in the ADR as a finding from `capability_matrix.py`; projection targets every configured tool with a project skill root regardless.
4. **Single catalog seam (retire hazard)**: `CanonicalSkill` is path-based and `SkillRegistry.snapshot_catalog` refuses non-files, so pack skills are **rendered into a staged root** (`.kittify/runtime/pack-skills/<rendered-name>/SKILL.md`, regenerated each run) and exposed as a second `SkillRegistry`; `resolve_project_skill_catalog(project_root)` returns the merged registry (built-in ∪ staged pack). All install/assess callers with retire semantics use the seam; an architectural test pins that no module outside the seam calls `SkillRegistry.from_package()` for install/assess. Pinned caller list: `skills/verifier.py`, `runtime/agent_skills.py`, `cli/commands/init.py`, `upgrade/migrations/m_2_0_11_install_skills.py`, `m_2_1_1_repair_skill_pack.py`, `m_3_0_3_globalize_skill_pack.py`, `m_3_2_0rc35_spk_skill_pack.py`, `upgrade/assessment.py`, `tool_surface/providers/managed_skills.py`, `tool_surface/providers/plugin_bundle.py`. Test: deactivating the last pack skill retires it even when the built-in catalog is empty (guard at `installer.py:739`).
5. **Default in force**: lives in the effective-set computation (`pack_context` three-state resolution), not the planner: `activated_skills is None` → effective = org `required_skills` ∪ built-in defaults (empty). Kind fact `ArtifactKind.effective_when_absent` = `"all"` (existing kinds) | `"required"` (SKILL). The engine keeps reading `effective_ids`. Test: absent key + `activate skill X` ⇒ `required ∪ {X}`, never all skills.
6. **Hashing / manifest**: `installation_class` stays a placement taxonomy. Manifest entries gain optional fields `origin` (`builtin` default | `pack`), `source_ref` (pack source path) and `source_hash` (sha256 of the prepared input: JSON-canonical (`sort_keys`) skill record + body bytes), backward compatible for old manifests. `content_hash` keeps its meaning (rendered bytes → drift); `source_hash` mismatch → staleness.
7. **Layer direction**: charter reads `skill_namespace` / `required_skills` from org-charter docs via `_iter_org_charter_docs` (charter side) — never imports `specify_cli`.

## Implementation Concern Map

### IC-01 — Slice 0 residue (FR-001, FR-002)
The two lists are deliberately different sets: keep them distinct and derive both from `ArtifactKind` facts — `org_requirable` (the 10 `required_<plural>` fields on `OrgCharterPolicy`) and `selection_overlayable` (the 8 with a `selected_<plural>` field on `DoctrineSelectionConfig`). Architectural test: overlayable ⊆ requirable, and overlayable == the `selected_*` fields; requirable == `OrgCharterPolicy.required_*` fields. Derive `_SINGULAR_TO_PER_KIND_FIELD`. Fix stale comment at `org_pack_discovery.py:54` (names `anti_pattern`, real difference is `asset`) and the `_BUILTIN_ARTIFACT_KINDS` docstring. CLAUDE.md key fix. No behaviour change.

### IC-02 — Kind registration + schema + repository (FR-003, FR-004, FR-005)
Enum member, NodeKind, tables, PROJECT_KIND_DIRS (`skills`), schema, Pydantic model (`prompt|wrapper` discriminated), validator (reserved prefixes, no `scripts/`, no `allowed-tools`), repository over three tiers with overrides/enhances + sibling conflict, extractor helper, delivery-table entry (`slot=None` with reason), doctor health dimension, exact-set test updates.

### IC-03 — Activation + preparation (FR-006, FR-007, FR-008)
Config key `activated_skills`, `required_skills` in org-charter (SKILL is org_requirable, not overlayable), `effective_when_absent` resolved in pack_context, charter-side namespace read, cascade over edges, `prepare_project_skill_activations` returning `PreparedSkill` records.

### IC-04 — specify_cli projection (FR-009, FR-010, FR-011, FR-013)
Staged-root rendering + merged-registry catalog seam (`snapshot_catalog` respected), manifest `origin`/`source_ref`/`source_hash`, renderer, installer integration with manifest ownership, collisions-before-write, unowned-dir preservation, all callers migrated, wrapper target validation, deactivate → reproject.

### IC-05 — Drift findings + ATDD + docs (FR-012, FR-014, SC-001..005)
Doctor/upgrade findings, end-to-end ATDD, packaging safety assertion, ADR → Accepted, CHANGELOG, docs index regen.

## Sequencing

WP01 (IC-01) → WP02 (IC-02) → WP03 (IC-03) → WP04 (IC-04) → WP05 (IC-05). Strictly sequential (single_branch).

## Complexity Tracking

None beyond the ADR's stated kind-registration cost.
