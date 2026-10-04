# Mission Specification: Pack skills: charter-activatable skill kind (slices 0+1)

**Mission Branch**: `claude/festive-babbage-lhkqac`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Issue [#5193](https://github.com/spec-kitty/spec-kitty/issues/5193) — implement ADR 2026-09-27-1 (pack skills), slices 0 and 1. The owner accepted the ADR for this mission (Proposed → Accepted).

## Intent Summary

- **Primary actor:** a project maintainer whose charter registers an org pack (or who authors project-tier doctrine) and wants the team's shorthand entry points shared from that pack instead of private per-user copies.
- **Trigger:** `spec-kitty charter activate skill <id>` (or the default-in-force rule when `activated_skills` is absent).
- **Outcome:** the activated pack skill is rendered into every configured tool's **project** skill root (`.claude/skills/`, `.agents/skills/`, …), survives `spec-kitty upgrade`, and is retired on deactivation without touching anything else.
- **Invariant:** a pack skill is a thin entry point; substance stays in the procedures it `requires` through DRG edges (never inline fields). Every caller that composes the installed skill catalog goes through one seam, so no caller prunes pack skills.
- **Boundary:** Slice 0 (derive the lockstep kind sets from `ArtifactKind`) is a precondition delivered first. Slices 2 (procedure-first migration of the four internal shorthands) and 3 (trust `--accept` gate, remote pinning, non-skill-tool command files, promote scaffolder, `spk-*` convergence) are out of scope.

Brief-intake mode: the ADR plus the issue are the confirmed brief; the operator chose "Accept ADR, do Slice 0+1".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Adding a kind needs no lockstep copies (Priority: P1)

A doctrine maintainer adds a new `ArtifactKind` member. The activation pack context, the activation config allow-list, the org-DRG kind alias table, and the required-kind-fields table pick it up from `ArtifactKind` facts instead of hand-copied sets.

**Independent Test**: architectural test asserts each of the four tables equals its `ArtifactKind`-derived value; adding `skill` in story 2 changes none of those four modules.

**Acceptance Scenarios**:

1. **Given** current `main`, **When** the four tables are computed, **Then** they equal the values they had before (behaviour-preserving derivation).
2. **Given** an architectural test, **When** it rebuilds each table from `ArtifactKind` facts, **Then** it equals the module constant (a hand-copied literal fails).

### User Story 2 - Activate a pack skill and get it in project skill roots (Priority: P1)

A maintainer runs `spec-kitty charter activate skill <id>`. The skill, declared in an org pack's `skills/` directory (or the project tier `.kittify/doctrine/skills/`), is rendered as `<namespace>-<id>` into the project skill roots of the configured tools, owned by `.kittify/skills-manifest.json`.

**Independent Test**: ATDD over a temp project with a fixture org pack: activate → present in `.claude/skills/` and `.agents/skills/`; `upgrade` → still present; deactivate → removed; every other file byte-identical.

**Acceptance Scenarios**:

1. **Given** an org pack with `skills/land-pr.skill.yaml` and `skill_namespace: acme`, **When** `charter activate skill land-pr` runs, **Then** `.claude/skills/acme-land-pr/SKILL.md` and `.agents/skills/acme-land-pr/SKILL.md` exist and the manifest records them with provenance and `content_hash`.
2. **Given** the skill is installed, **When** `spec-kitty upgrade` (or any other catalog caller with retire semantics) runs, **Then** the skill is still installed.
3. **Given** the skill is installed, **When** `charter deactivate skill land-pr` runs, **Then** only the manifest-owned skill directories are removed.
4. **Given** the skill `requires` `procedure:landing-contributor-prs`, **When** rendered, **Then** the SKILL.md carries a generated preamble that runs `spec-kitty charter context --include procedure:landing-contributor-prs` and does not inline the procedure body.

### User Story 3 - Namespaces and collisions fail before any write (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an org/project skill whose rendered name starts with `spk-`, `spec-kitty-` or `spec-kitty.`, **When** prepared, **Then** preparation fails naming the reserved prefix.
2. **Given** two activated skills rendering to the same name, **When** projection runs, **Then** it fails before writing anything.
3. **Given** an unowned (not in manifest) directory with the rendered name, **When** projection runs, **Then** that directory is preserved untouched and reported.

### User Story 4 - Drift and staleness are reported (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an installed pack skill edited locally, **When** `doctor` (skills check) runs, **Then** it reports drift pointing to the pack source path.
2. **Given** the pack's skill content changed so its `content_hash` differs from manifest provenance, **When** `doctor`/`upgrade` runs, **Then** it reports staleness pointing to the pack source.

### Edge Cases

- `activated_skills` absent → default in force is org-pack `required_skills` plus built-in defaults (empty at MVP), never "every available skill".
- Wrapper-form skill whose `expands_to.target` is `builtin:<cmd>` not in the command set → refused by the `specify_cli` adapter.
- Org/project skill directories carrying `scripts/` or permission-widening frontmatter (`allowed-tools`) → refused by the validator.
- Same skill id in two sibling org packs → hard conflict.
- Project-tier skill with no configured project `skill_namespace` → refused with a clear remedy.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Derive kind tables from ArtifactKind | As a doctrine maintainer, I want `REQUIRED_KIND_FIELDS` (`specify_cli/doctrine/org_charter.py`) and its charter twin `_REQUIRED_KIND_FIELDS` (`org_pack_discovery.py`) reconciled and derived from one `ArtifactKind` fact (`_BUILTIN_ARTIFACT_KINDS`, `_ALLOWED_KINDS`, `_ORG_DRG_KIND_ALIASES` are already derived on main — grounding verified), plus `_SINGULAR_TO_PER_KIND_FIELD` in `drg_activation.py`, so that adding a kind needs no lockstep copies. | High | Open | [ratchet] | no — the two lists disagree today and need real derivation code |
| FR-002 | Fix org-pack config key doc drift | As a contributor, I want CLAUDE.md to name `charter_packs.org.packs` (legacy fallback `doctrine.org.packs`) and the `org_pack_discovery.py:54` comment to name `asset`, so that docs match code. | Low | Open | [folded] | yes — doc-only |
| FR-003 | Register the `skill` kind | As a pack author, I want `skill` as an `ArtifactKind` and `NodeKind` (URN `skill:<id>`, charter-activatable) so that skills participate in DRG edges, cascade and `--include`. | High | Open | [build] | no |
| FR-004 | Skill schema and validator | As a pack author, I want a `*.skill.yaml` schema for `prompt` (with `body_path`) and `wrapper` (with `expands_to`) forms, refusing `scripts/` and permission-widening frontmatter for org/project tiers, so that malformed skills fail at load. | High | Open | [build] | no |
| FR-005 | Skill repository across tiers | As a maintainer, I want skills loaded from built-in `packs/built-in/skills/` (empty), org `<pack>/skills/` and project `.kittify/doctrine/skills/`, with `overrides`/`enhances` semantics per the ADR and a hard conflict on same id in sibling org packs. | High | Open | [build] | no |
| FR-006 | Activation and cascade | As a maintainer, I want `charter activate/deactivate skill <id> [--cascade …]` through `plan_activation`/`commit_plan` with config key `activated_skills`, cascading along `requires`/`suggests` and C-005 shared-reference safety on deactivate. | High | Open | [build] | no |
| FR-007 | Default in force | As a maintainer, I want the effective skill set, when `activated_skills` is absent, to be org-pack `required_skills` plus built-in defaults, never every available skill. | High | Open | [build] | no |
| FR-008 | prepare_skill_activations | As the adapter layer, I want a pure charter function returning, per effective skill, id, rendered name, body or expansion, required URNs, provenance and `content_hash`, so that rendering needs no doctrine knowledge. | High | Open | [build] | no |
| FR-009 | One catalog-composition seam | As a maintainer, I want every caller that builds the installable skill catalog and installs with retire semantics (init, upgrade migrations, verifier, managed-skills provider) to go through one `resolve_project_skill_catalog(project_root)` seam, so that no caller prunes pack skills. | High | Open | [build] | no |
| FR-010 | Project-root projection | As a maintainer, I want activated pack skills rendered into project skill roots of configured tools only (never user-global), with a generated `charter context --include` preamble, recorded in `.kittify/skills-manifest.json`, and retired on deactivation. | High | Open | [build] | no |
| FR-011 | Reserved namespaces and collisions | As a maintainer, I want `spk-`/`spec-kitty-`/`spec-kitty.` reserved for built-in, org/project skills rendered as `<skill_namespace>-<id>`, render-name collisions failing before any write, and unowned same-name directories preserved and reported. | High | Open | [build] | no |
| FR-012 | Drift and staleness findings | As a maintainer, I want `doctor`/`upgrade` to report a locally edited rendered pack skill, or a pack `content_hash` differing from manifest provenance, as drift pointing to the pack source. | Medium | Open | [build] | no |
| FR-013 | Wrapper target validation | As the adapter layer, I want `builtin:` expansion targets validated against the `spec-kitty.*` command set in `specify_cli` and `cli:` targets limited to `spec-kitty` argv. | Medium | Open | [build] | no |
| FR-015 | Skill doctor health dimension | As a maintainer, I want `doctor doctrine` to report loaded and skipped pack skills so that a broken skill is never reported healthy. | Medium | Open | [build] | no |
| FR-014 | Accept the ADR | As the owner, I want ADR 2026-09-27-1 marked Accepted and its open questions resolved in the ADR. | Medium | Open | [folded] | yes — doc-only |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Wheel safety | Zero `packs/internal/skills/**` paths in the built wheel (packaging safety test). | Security | High | Open |
| NFR-002 | Fail before write | 0 files written when preparation or collision checks fail (asserted by snapshotting the project tree). | Reliability | High | Open |
| NFR-003 | Quality gates | New code: 0 ruff/mypy findings, complexity ≤15, diff coverage ≥90%. | Maintainability | High | Open |
| NFR-004 | Layer direction | `charter` imports nothing from `specify_cli` (layer rules test green). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Closed command-skill owner | `command_installer.py`, `CONSUMER_SKILLS` and the `spec-kitty.*` contract are not widened. | Technical | High | Open |
| C-002 | Edges not fields | Skill → procedure relationships live only in DRG fragments (ADR 2026-07-26-1). | Technical | High | Open |
| C-003 | Pack tiers | No skill content is added to `packs/built-in/skills/` at MVP; `packs/internal/` never ships. | Technical | High | Open |
| C-004 | Out of scope | Slices 2 and 3 (internal shorthand migration, `--accept` trust gate, remote pinning, non-skill command files, promote scaffolder, `spk-*` convergence) are not delivered. | Business | High | Open |
| C-005 | No baked bindings | Rendered files carry no operator handle or repository slug; run-time binding placeholders are deferred to slice 2 (ADR open question recorded). | Security | Medium | Open |

### Key Entities

- **Pack skill** (`skill:<id>`): thin, parameterised entry point; forms `prompt | wrapper`; tiers built-in/org/project.
- **Skill namespace**: per org pack (`skill_namespace` in `org-charter.yaml`) or project (config key); prefixes rendered names.
- **Skill activation** (`activated_skills`): charter config list; absent → default in force.
- **Prepared skill**: output of `prepare_skill_activations` — rendered name, body/expansion, required URNs, provenance, `content_hash`.
- **Project skill catalog**: union of built-in doctrine skills and prepared pack skills, the single input to the managed installer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ATDD test activate → `.claude/skills/` + `.agents/skills/` present → `upgrade` keeps → deactivate removes, with every other file byte-identical — [build] · no-op passable: no
- **SC-002**: Packaging safety test reports 0 `packs/internal/skills/**` paths in the wheel (pre-existing ratchet extended with an explicit skills assertion) — [ratchet] · no-op passable: yes
- **SC-003**: Two activated skills with the same rendered name fail with 0 files written; an unowned same-name directory is preserved and reported — [build] · no-op passable: no
- **SC-004**: A locally edited rendered copy and a changed pack `content_hash` are each reported as drift naming the pack source — [build] · no-op passable: no
- **SC-005**: Architectural test rebuilds `REQUIRED_KIND_FIELDS`, `_REQUIRED_KIND_FIELDS`, `_SINGULAR_TO_PER_KIND_FIELD` from `ArtifactKind` facts and matches the `OrgCharterPolicy.required_*` / `DoctrineSelectionConfig.selected_*` fields — [ratchet] · no-op passable: no
- **SC-006**: Deactivating a skill whose required procedure is still referenced by another active artifact keeps that procedure active (C-005) — [build] · no-op passable: no
- **SC-007**: A wrapper-form skill renders a SKILL.md that invokes its `builtin:` target; an unknown `builtin:` target is refused before any write — [build] · no-op passable: no
- **SC-008**: Same skill id in two sibling org packs is a hard conflict; a project-tier skill without a project namespace is refused with a remedy — [build] · no-op passable: no
- **SC-009**: `doctor doctrine --json` reports a skill health dimension (loaded/skipped skills) — [build] · no-op passable: no
- **SC-010**: No install/assess caller in `specify_cli` builds `SkillRegistry.from_package()` outside the catalog seam (architectural test) — [ratchet] · no-op passable: no
- **SC-011**: With `activated_skills` absent, activating one skill yields `required_skills ∪ {it}`, never every available skill — [build] · no-op passable: no
