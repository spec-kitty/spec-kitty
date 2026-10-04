# Tasks: Pack skills — charter-activatable skill kind (slices 0+1)

Strictly sequential (single_branch): WP01 → WP02 → WP03 → WP04 → WP05.

## WP01 — Slice 0 — derive remaining lockstep kind tables from ArtifactKind

**Prompt**: [tasks/WP01-slice0-kind-table-derivation.md](tasks/WP01-slice0-kind-table-derivation.md)  
**Dependencies**: none  
**Requirements**: FR-001, FR-002, SC-005

Subtasks:
- T001 — Add ArtifactKind facts `org_requirable` and `selection_overlayable` (plan IC-01): requirable = the 10 kinds in today's `REQUIRED_KIND_FIELDS` (org_charter
- T002 — Derive `REQUIRED_KIND_FIELDS` (specify_cli) and `_REQUIRED_KIND_FIELDS` (charter) from those facts — byte-for-byte same membership and ORDER-insensitive consumers verified (check iteration order dependence at org_charter
- T003 — Derive `_SINGULAR_TO_PER_KIND_FIELD` (drg_activation
- T004 — Architectural test tests/architectural/test_kind_table_derivation
- T005 — Fix stale comment org_pack_discovery

## WP02 — Register the `skill` kind — enum, NodeKind, schema, model, repository, doctor health

**Prompt**: [tasks/WP02-skill-kind-registration.md](tasks/WP02-skill-kind-registration.md)  
**Dependencies**: WP01  
**Requirements**: FR-003, FR-004, FR-005, FR-015, SC-008, SC-009

Subtasks:
- T006 — Add `ArtifactKind
- T007 — Pydantic model `PackSkill` (pack_skills/models
- T008 — Validator: for org/project tiers refuse a `scripts/` dir next to the skill and any permission-widening frontmatter key (`allowed-tools`) in the body; refuse ids/rendered names starting with `spk-`, `spec-kitty-`, `spec-kitty
- T009 — `PackSkillRepository` (BaseDoctrineRepository subclass) loading built-in/org/project tiers; same id in two sibling org packs → hard conflict error; overrides/enhances per ADR (enhances may change defaults/triggers/tools/narrow invocation, never body or expansion)
- T010 — Doctor health dimension `PackSkillHealth` (loaded/skipped) in _doctrine_health

## WP03 — Skill activation, default-in-force, and prepare_skill_activations

**Prompt**: [tasks/WP03-skill-activation-and-preparation.md](tasks/WP03-skill-activation-and-preparation.md)  
**Dependencies**: WP02  
**Requirements**: FR-006, FR-007, FR-008, SC-006, SC-011

Subtasks:
- T011 — Config key `activated_skills` (derived via CHARTER_KIND_TOKENS / YAML_KEY_MAP; verify pack_manager, charter_yaml_io, `_NON_PACK_ACTIVATION_KEYS` in specify_cli/charter_pack_registry
- T012 — Default in force (plan decision 5): add ArtifactKind fact `effective_when_absent` (`all` | `required`); SKILL = `required`
- T013 — Cascade: `charter activate skill X --cascade procedure,directive` follows DRG requires/suggests; deactivate keeps artifacts still referenced (C-005)
- T014 — `prepare_skill_activations(pack_context/service, project_root-agnostic inputs) -> list[PreparedSkill]` pure: id, tier, rendered_name (`<namespace>-<id>`; project namespace from config key `charter_packs

## WP04 — Catalog seam and project-root projection through the managed installer

**Prompt**: [tasks/WP04-project-skill-projection.md](tasks/WP04-project-skill-projection.md)  
**Dependencies**: WP03  
**Requirements**: FR-009, FR-010, FR-011, FR-013, SC-001, SC-003, SC-007, SC-010, NFR-002, NFR-004

Subtasks:
- T015 — RED FIRST: write tests/integration/test_pack_skill_lifecycle
- T016 — Renderer (pack_skill_renderer
- T017 — Catalog seam catalog
- T018 — Migrate every install/assess caller to the seam: verifier
- T019 — `charter activate/deactivate skill` (cli/commands/charter/activate

## WP05 — Drift/staleness findings, packaging safety, ADR acceptance, docs

**Prompt**: [tasks/WP05-drift-findings-docs-closeout.md](tasks/WP05-drift-findings-docs-closeout.md)  
**Dependencies**: WP04  
**Requirements**: FR-012, FR-014, SC-002, SC-004, NFR-001, NFR-003

Subtasks:
- T020 — pack_skill_drift
- T021 — Packaging safety: add explicit assertion no `packs/internal/skills/` path in wheel (test_packaging_safety
- T022 — ADR → Accepted (status front-matter + body), resolve open questions with plan decisions 1–3; note #2470 supersession remains owner call
- T023 — Quality sweep: ruff check, ruff format --check --force-exclude on changed files, mypy on changed modules, complexity ≤15; make test-fast + targeted dirs (tests/charter tests/doctrine tests/specify_cli/skills + specific architectural gates)
