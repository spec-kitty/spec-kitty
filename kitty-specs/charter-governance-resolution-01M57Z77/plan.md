# Implementation Plan: Charter governance resolution

**Branch**: `issue-6404-charter-governance-resolution-work` (PR branch `issue-6404-charter-governance-resolution`) | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification plus the Phase 1 grounding brief (`research.md`) and three brownfield scout notes (identity seam, synthesis edge and delivery, narrow activation and code reader), folded below.

## Summary

Four independent concerns in the charter activation layer, sharing one new seam:

1. A per-invocation, layer-aware **identity index** (stem ↔ declared id per kind) replaces the guessed `_normalize_directive_id` spellings and built-in-only validation (#6406, #6407, sibling defect).
2. Synthesis emits `directive --suggests--> tactic`, reconcile assigns edges by owner, synthesized edge-carrying tactics stop being roots, and synthesis appends its tactic ids to an explicit `activated_tactics` (#6404).
3. `charter activate --only` and `charter interview --narrow-activation` reuse the engine's existing `ActivationPlan.deactivated` (#6408).
4. The code reader resolves indicators root-first with JVM indicators and an extension-count tie-break; the neutrality gate matches slug components (#6405).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, ruamel.yaml, pydantic (existing); no dependency changes (supply-chain section not applicable).
**Storage**: `.kittify/config.yaml` / `charter.yaml` activation keys; project DRG overlay under `.kittify/charter-packs/`.
**Testing**: pytest (`tests/charter/`, `tests/charter_offering/`, `tests/specify_cli/cli/commands/charter/`), `make test-fast`, targeted architectural gates.
**Target Platform**: CLI (Linux/macOS/Windows).
**Project Type**: single project (`src/charter/`, `src/specify_cli/`).
**Performance Goals**: NFR-003: one identity scan per (kind, layer set) per invocation.
**Constraints**: C-001..C-007 in the spec; complexity ≤ 15; mypy strict.
**Scale/Scope**: about 20 source modules, 4 concerns.

## Charter Check

- **Single canonical authority**: the identity index becomes the one stem ↔ id authority; `_normalize_directive_id` survives only as a fallback inside it. Edge ownership in reconcile gets one helper (`edge_owner`). PASS.
- **Architectural alignment / shared-package boundary**: the index lives in `charter.activation` and is exported from `charter.activation.api`; `specify_cli` (`list_cmd.py`) imports it from there (C-002). It imports only `charter.offering.*` and `kind_vocabulary`, never `resolver` (no cycle). PASS.
- **ATDD-first / red-first**: each work package starts with an issue-pinned failing test committed before the fix. PASS.
- **Pack tiers**: only `packs/built-in/missions/mission-steps/software-dev/charter/prompt.md` changes (consumer-facing contract text, belongs in built-in). The scout verified it is outside the vendor clean-tree digest; `regenerate-graph --check` is still run. Follow-up: port the edit to `spec-kitty-open-packs`. PASS.
- **Terminology**: Mission; no retired terms. PASS.
- **Model routing**: implement on sonnet, review on opus.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-governance-resolution-01M57Z77/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md / tasks/  (by /spec-kitty.tasks)
```

`contracts`: none (no new external API; CLI flag and JSON key additions are documented in data-model.md and quickstart.md).

### Source Code (repository root)

```
src/charter/activation/
├── identity_index.py            (new)
├── api.py                       (export IdentityIndex)
├── resolver.py                  (governance base, validation, service getters)
├── action_governance_bundle.py  (identity + reach-only tactic subtraction)
├── drg_activation.py            (activation filter via identity)
├── context.py / context_json.py / compact.py / context_contract.py
├── context_renderers/{template_include,selection_block}.py
├── preset_application.py
├── activation_engine.py         (narrow_base, warnings)
├── pack_manager.py              (activate(only=))
├── org_charter.py               (org_required_stems)
├── compiler.py                  (reach-only subtraction in reference seeds)
├── evidence/code_reader.py
└── synthesizer/{project_drg,reconcile,orchestrator,write_pipeline}.py
src/charter/offering/drg/{models.py,merge.py}   (applies prose)
src/specify_cli/cli/commands/charter/{activate,interview,list_cmd}.py
packs/built-in/missions/mission-steps/software-dev/charter/prompt.md
docs/architecture/doctrine-relationships.md
```

**Structure Decision**: single project; no new packages, one new module.

## Design

### D1 — Identity index (`charter/activation/identity_index.py`)

```python
@dataclass(frozen=True)
class IdentityEntry: kind: ArtifactKind; stem: str; declared_id: str; layer: str

class IdentityIndex:
    @classmethod
    def build(cls, repo_root: Path, *, org_roots: Sequence[Path] | None = None) -> IdentityIndex
    @classmethod
    def from_pack_context(cls, ctx: PackContext) -> IdentityIndex
    def declared_id(self, kind, token) -> str | None     # stem first, then declared id (every kind)
    def selection_id(self, kind, token) -> str | None    # directives: declared id first (matches resolve_selected_id_to_stem)
    def stem(self, kind, declared_id) -> str | None
    def knows(self, kind, token) -> bool
    def source_layer(self, kind, declared_id) -> str | None
    def resolve_many(self, kind, tokens) -> tuple[list[str], list[str]]   # (ids, unknown)
```

- Roots canonicalised once: org roots that exist, in declaration order; `{"project": p}` only when `p.is_dir()`; one private `ResolutionPass`.
- Per kind, built lazily from one `_iter_artifact_paths` walk with the same precedence as `_scan_roots` (project, org reverse-declared, built-in); first match wins for `by_stem` and `by_id`.
- Directive fallback: when a token misses, `charter.offering.drg.migration.id_normalizer.normalize_directive_id(token)` is tried and accepted only if the result is a known declared id; activation lists keep the old warning-and-normalise behaviour for unknown tokens (edge case), selections report unknown.
- Kinds without files (`anti_pattern`) pass tokens through; agent profiles read `profile-id`.
- NFR-003 probe: wrap `kind_vocabulary._scan_dir_matches` / path iteration as in `tests/charter/test_directive_resolution_memoization.py:34-48`.
- `resolve_artifact_urn` gains the declared-id fallback for every kind (stem first), so callers outside the index agree.

**Threading**: built once in `build_charter_context`, `build_charter_context_json`, `build_charter_context_include` (`context.py`), passed as an `identity=` keyword (build-if-None) to `resolve_project_governance`, `_load_action_governance_bundle` (stored on the bundle), `ActiveCharterService`, `filter_graph_by_activation`, compact and JSON helpers.

**Consumers** (file:line from the scout inventory): `resolver._resolve_directive_base` (800-853), `_validate_paradigm_selection` (656-671), `_resolve_template_set_selection` text (895-910), `_resolve_unmatched_directive_token` (144-163, folded into the index), `ActiveCharterService` getters (214-335; one `_activated_ids(kind)` helper), `action_governance_bundle` (337-379), `template_include` (139, 298), `selection_block` (163, 254, 476-519), `preset_application` (286-292, 456-474), `list_cmd` (149, 287, 297), `drg_activation` (331-360), `compact` (320-338), `context_json` (155-169).

**Unknown selections (FR-010)**: `_resolve_directive_base` and `_validate_paradigm_selection` stop raising for unknown ids; they drop them and append to `GovernanceResolution.diagnostics` (already rendered by compact at :267-268). JSON context gains a top-level `diagnostics` list: add it to `CONTEXT_CONTRACT_TOP_LEVEL_KEYS` (`context_contract.py:82-100`), bump `CONTEXT_SCHEMA_VERSION` 1.3.0 → 1.4.0, extend `tests/charter/test_context_schema_version_ledger.py`. Exit stays 0. `GovernanceResolutionError` remains for template set and other genuine failures, with remediation text pointing at org packs / `.kittify/charter-packs/` / `charter list` (FR-011).

**`charter list` (FR-007)**: an entry counts as activated when its stem or its declared id is in the list; the activated column keeps showing stems (the activation form operators type into `charter activate`), with the declared id shown alongside when it differs.

### D2 — Synthesized tactic edges and delivery

- **Emission** (`project_drg.py:349-375`): tactic targets emit `DRGEdge(source=source_urn, target=urn, relation=SUGGESTS)`; directive targets keep `REQUIRES`; the built-in duplicate-triple check uses the oriented triple. `source_urns` already carry declared ids (`compiler.resolve_config_activated_roots` → `resolve_artifact_urn`), so org directives get correct endpoints.
- **Ownership** (`reconcile.py`): new `edge_owner(edge, overlay_urns)`: the synthesis shape (`suggests`, `directive:*` → overlay `tactic:*`) is owned by the target; otherwise the source if it is an overlay node; otherwise the target if it is. Used by `merge_project_overlay`, `_graph_delta`, `_edge_ref` (backing artifact; avoids a spurious orphan refusal in `_synthesis.py:859-878`), `_edge_conflict`, `_classify_conflicts`. `apply_prune` drops every edge touching a removable node.
- **Legacy strip (FR-005)**: `merge_project_overlay` and `_graph_delta` drop existing `applies` edges whose source is an overlay node (only synthesis ever emitted them). Covers full and `--topic` runs.
- **Reach-only tactics (FR-002)**: new `reach_only_tactic_ids(repo_root)` in `synthesizer/project_drg.py`: overlay `tactic` nodes that are the target of an overlay `directive:* --suggests-->` edge, computed from the project overlay before activation filtering (degrades to empty on load errors). `action_governance_bundle` subtracts it from tactic seeds after the org-required union; `compiler.py` (~1768) applies the same subtraction to reference seeds. Edgeless synthesized tactics (`testing-philosophy-tactic`, `review-policy-tactic`) and hand-authored project tactics stay roots; spec FR-002 is worded accordingly.
- **Activation append (FR-003)**: in `orchestrator.synthesize` after the post-condition (non-dry-run): ids = this run's tactic provenance slugs; `resolve_activation_write_target(repo_root)`; return if `activated_tactics` absent; `promote_activations({"activated_tactics": ids}, ..., effective_sets={})`; then `restamp_bundle_hash(repo_root)`.
- **Prose**: `RELATION_DESCRIPTIONS[APPLIES]` (`models.py:181-193`) and `docs/architecture/doctrine-relationships.md:163` updated in lockstep (no synthesis emitter remains); `merge.py:92-98` comment updated. `test_no_authored_applies_edge.py` unaffected.

### D3 — Narrow activation

- **Engine** (`activation_engine.py`): `plan_activation(..., narrow_base=None, previous_ids=())`: when `narrow_base` is given the new list is `dedupe(narrow_base)` plus the id, and `plan.deactivated` lists `previous_ids` not in it. `_plan_promotion` / `promote_activations` take `narrow_bases: Mapping[str, list[str]] | None` with the same rule. Warning texts (":338-342 Initialized from", ":568 Preserved N") keep their prefixes and add the frozen-list sentence naming `--only` (FR-014).
- **Org-required**: new public `org_required_stems(repo_root, kind_plural, warnings)` in `org_charter.py` wrapping `load_org_charter_policies` + `_normalize_required_ids` (stems, so the activation filter resolves them).
- **Manager**: `ActiveCharterManager.activate(..., only=False)`: previous = present list or preserved set; base = `org_required_stems`; `ActivationResult.deactivated` populated.
- **CLI activate**: `--only` option; refused with `--preset` (exit 2, `ctx.fail` in `_check_preset_flags`); result rendering extracted into `_render_activation_result` (keeps `activate_cmd` ≤ 15), printing "No longer in force (N): …". Cascade loop unchanged (appends).
- **CLI interview**: `--narrow-activation`; builds `narrow_bases` = selection stems ∪ `org_required_stems` per selected kind (directives, tactics, paradigms; empty selection = no narrowing); runs after `apply_org_charter_to_interview`, so it replaces. JSON payload gains `"narrowed": {key: [dropped ids]}` (`{}` when off).
- **Contract text**: `charter/prompt.md:83` and `:305-307` explain that selections are additive, an explicit activation list is frozen, and `--only` / `--narrow-activation` / `--preset minimal` keep activation narrow.

### D4 — Code reader and neutrality gate

- `_TreeScan.indicator_depths: dict[str, int]` (shallowest depth) and `ext_counts: Counter[str]`; property `indicator_files` keeps framework detection unchanged; inner loop extracted into `_observe`.
- Indicators add `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`, `gradlew`, `mvnw` → `java`. `SOURCE_EXT_LANG` maps extensions (`.kt` → `java`).
- `_detect_language`: indicators at the minimum depth decide; one language wins outright; several break by extension counts, ties by indicator order; `package.json` keeps the tsconfig / majority rule via `_js_or_ts`.
- `write_pipeline._is_generic_scoped`: `scope_tag not in target_slug.split("-")`.

## Complexity Tracking

No charter violations. `activate_cmd` sits at complexity 15 today; the extraction keeps it there.

## Implementation Concern Map

### IC-01 — Identity index and declared-id surfaces

- **Purpose**: one layer-aware authority for activation-token and selection identity; every charter surface uses it.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-017, NFR-003, NFR-004, C-002, C-007.
- **Affected surfaces**: `identity_index.py` (new), `kind_vocabulary.py`, `api.py`, `resolver.py`, `action_governance_bundle.py`, `drg_activation.py`, `context.py`, `context_json.py`, `context_contract.py`, `compact.py`, `context_renderers/*`, `preset_application.py`, `list_cmd.py`.
- **Sequencing/depends-on**: none (foundation).
- **Risks**: broad blast radius; NFR-004 golden snapshot captured on the merge-base first; stem/id collisions; schema version bump.

### IC-02 — Synthesized tactic edges, ownership and delivery

- **Purpose**: synthesized how-we-apply tactics are reachable through their directive and only through it.
- **Relevant requirements**: FR-001..FR-005, C-001, C-004.
- **Affected surfaces**: `synthesizer/project_drg.py`, `synthesizer/reconcile.py`, `synthesizer/orchestrator.py`, `action_governance_bundle.py`, `compiler.py`, `offering/drg/models.py`, `offering/drg/merge.py`, `docs/architecture/doctrine-relationships.md`.
- **Sequencing/depends-on**: IC-01 touches `action_governance_bundle.py` too; sequence after IC-01 to avoid conflicts.
- **Risks**: many reconcile tests encode the legacy `applies` shape; spurious orphan refusals if `_edge_ref` backing is wrong.

### IC-03 — Opt-in narrow activation

- **Purpose**: `--only` and `--narrow-activation`, warnings and contract text.
- **Relevant requirements**: FR-012, FR-013, FR-014, C-001, C-003.
- **Affected surfaces**: `activation_engine.py`, `pack_manager.py`, `org_charter.py`, `cli/commands/charter/activate.py`, `cli/commands/charter/interview.py`, `charter/prompt.md`.
- **Sequencing/depends-on**: none (exact-string dropped lists use stems, independent of IC-01).
- **Risks**: `activate_cmd` complexity ceiling; vendored-click path pinned by tests.

### IC-04 — Root-first stack detection

- **Purpose**: correct `primary_language` for repositories with nested sub-projects.
- **Relevant requirements**: FR-015, FR-016, C-006.
- **Affected surfaces**: `evidence/code_reader.py`, `synthesizer/write_pipeline.py`.
- **Sequencing/depends-on**: none.
- **Risks**: behaviour change for repositories with only nested manifests in two languages (flagged in the changelog).
