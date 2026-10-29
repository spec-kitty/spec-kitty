# M9 Phase 0 — Re-synthesis after activation (#6510, #4226)

Base: origin/main `143a39fc` (2026-10-27). Branch `issue-6510-resynthesis-after-activation`.

## 1. Code grounding (re-verified)
- `src/specify_cli/cli/commands/charter/_synthesis.py:104-149` — `directives_for_synthesis` (all
  activated directive ids, incl. project-layer ids such as `PROJECT_001`) becomes both
  `interview_snapshot.selected_directives` and the DRG snapshot nodes (`directive:<id>`).
- `_synthesis.py:241` / `:809` — the snapshot becomes `built_in_drg` for synthesize and resynthesize.
- `src/charter/activation/synthesizer/project_drg.py:334-346` — `emit_project_layer` raises
  `ProjectDRGValidationError` (FR-020/EC-6) when a target URN is in `built_in_drg.nodes`.
- Stem `001-project-intent-directive` resolves to `PROJECT_001` through the project layer root
  (`compiler._resolve_config_activated_roots`, `layer_roots={"project": ...}`).
- Ownership record already exists: `.kittify/charter/synthesis-manifest.yaml` (artifacts) +
  `.kittify/charter/provenance/directive-<slug>.yaml` (`artifact_urn: directive:PROJECT_001`).

## 2. Red-first reproduction (live CLI, scratch project)
1. `spec-kitty init --ai claude --non-interactive`; `charter interview --defaults`; `charter generate`.
2. Author `.kittify/charter/generated/...` (project-intent directive + 4 tactics/styleguides);
   `charter synthesize` → exit 0 (activation key absent ⇒ empty snapshot).
3. `charter activate directive 003-decision-documentation-requirement` → explicit
   `activated_directives` list now contains `001-project-intent-directive`.
4. `charter synthesize` (after authoring demanded companion tactics) → exit 1:
   `Additive-only violation ... colliding_urn='directive:PROJECT_001'`, `built_in_nodes=39`.
5. `charter resynthesize --topic directive:PROJECT_001` → exit 1, same error.
Side observation: step 4 also demanded `how-we-apply-project-001` (a companion tactic for the
project's own directive), which no run can ever successfully produce today.

## 3. Architectural alignment
- ADR 2026-10-16-1 (+Amend 2026-10-19): `charter.activation` incl. synthesis stays in core until
  post-GA rework; a core fix is not redone by the pre-GA direction.
- ADR 2026-10-19-1: synthesis never changes deny lists; both candidate fixes leave the activation
  ledger untouched (removing the directive from activation is the unsafe workaround #4226 documents:
  it silently drops governance delivery via `filter_graph_by_activation`).
- ADR 2026-10-22-1: event writer; unrelated.
- Epic #6518 / parent #2519: no clause on the activation→synthesis contract.

## 4. Overlaps
- M2 (#6453/#6455/#6456): no PR yet; expected surfaces `reach_only.py`, `reconcile.py`, possibly a
  run-wide lock in `synthesize.py`/`resynthesize.py`. Re-check before implementing.
- #6511 (landed): heavy prior change to the same files; filed #6510.
- #6695 (landed): `reach_only.py` fail-closed manifest read.
- #6678 (landed), #6685 (open): absent-vs-present activation keys feeding `_build_synthesis_request`.
- #5452 (open): `charter new` artifact vs synthesis target name collision (adjacent, out of scope).
- #6435 (open): ids vs stems in the effective-set union.
- #6715/#6675/#6193/#6716/events#92: no overlap.

## 5. Tidy-first candidates
- Extract the snapshot construction in `_build_synthesis_request` (`_synthesis.py:104-149`) into a
  small pure helper so the exclusion is unit-testable; behaviour-preserving first commit.

## 6. Planning decisions (2026-10-27)

- **D-1 Exclude synthesis-owned directives from synthesis input** (operator ruling, recommended
  option). *Rationale:* they are synthesis output; the snapshot is upstream input. *Alternative
  rejected:* "owned, update in place" inside `project_drg.emit_project_layer`. It loosens FR-020/EC-6
  in the charter core, needs ownership passed into the core, and sits next to M2.
- **D-2 Ownership authority = manifest → provenance `artifact_urn`.** The manifest records slugs and
  paths; only the provenance sidecar records the URN (`directive:PROJECT_001`). No new record (C-001).
  *Alternative rejected:* a `PROJECT_` id-prefix heuristic; it is not an authority and would misfire
  on a hand-authored `PROJECT_NNN`.
- **D-3 Read ownership only for a non-empty explicit list.** It keeps first runs and absent keys
  free of manifest I/O and of the fail-closed path (NFR-002 without new refusals).
- **D-4 Origin-aware refusal at the CLI seam.** The core error gains an additive `colliding_urn`
  field and neutral wording. `specify_cli` classifies the origin, because it knows activation and
  ownership. *Alternative rejected:* annotating snapshot nodes with an origin; `DRGNode` forbids
  extra fields (FR-004 of an earlier mission).
- **D-5 Scope** (decision `01M5ZD6WP0NFPTFYC1QBEQCWQS`): collision fix + wording only. Staging
  `.failed` accumulation and the neutrality gate are follow-ups.
- **D-6 Sequencing with M2:** proceed now and rebase before the PR (operator ruling). M2 had no PR on
  2026-10-27.
