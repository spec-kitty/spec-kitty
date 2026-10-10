---
work_package_id: WP02
title: Kind-vocabulary gate rules R1'/R4/R5/R6 + synthesizable subset
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- C-001
- C-003
- NFR-001
planning_base_branch: feat/charter-kind-tier-vocab-closeout
merge_target_branch: feat/charter-kind-tier-vocab-closeout
branch_strategy: Planning artifacts for this mission were generated on feat/charter-kind-tier-vocab-closeout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/charter-kind-tier-vocab-closeout unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Kind vocabulary single authority
history:
- at: '2026-10-09T20:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: tests/architectural/test_charter_kind_vocabulary_single_authority.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_charter_kind_vocabulary_single_authority.py
- src/charter/offering/packs/pack_manifest.py
- src/charter/offering/packs/pack_assembler.py
- src/charter/activation/context_renderers/fetch_stanza.py
- src/charter/activation/consistency_check.py
- src/specify_cli/mission_step_contracts/executor.py
- src/charter/activation/synthesizer/project_drg.py
- src/charter/bundle.py
- src/charter/activation/synthesizer/write_pipeline.py
- src/specify_cli/cli/commands/charter/_synthesis.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Kind-vocabulary gate rules + site migration

Closes #5823. Depends on WP01.

## Objectives & Success Criteria

- The gate recognises five currently-missed mirror shapes, each with a red-first self-mutation test, AND every live site is migrated to derive from the authority. Allowlist stays empty; the docstring "tracked as a follow-up"/"Known shapes the rules do not yet recognise" note is removed.
- A new "leaves legitimate constructs alone" test proves the six known-good shapes are NOT flagged.

## Context & Constraints

Authority: `src/charter/offering/artifact_kinds.py` (do NOT edit it here — derive from its existing `glob_pattern`, `operator_token`/`from_operator_token`, `plural`, and the public `SYNTHESIZABLE_KINDS`). Gate: `tests/architectural/test_charter_kind_vocabulary_single_authority.py` (rules R1/R2/R3 today; classifier `_violation`, `_UNIVERSE_SCALE = 8`, empty `_ALLOWLIST`). Red-first (C-003); single canonical authority (C-001).

**Grounded current mirror sites (post-cutover):**
- R1′ padded universe set: `src/charter/offering/packs/pack_manifest.py` `RECOGNISED_ARTIFACT_DIRS` (8 plurals + `"drg"`, ~line 302 — stays a `charter.packs` facade re-export, keep its table row/identity); `src/charter/activation/context_renderers/fetch_stanza.py` `_VALID_SELECTOR_KINDS` (8 singulars + `"section"`, ~line 98).
- R4 glob/suffix map: `src/charter/offering/packs/pack_assembler.py` `_ARTIFACT_DIRS_AND_GLOBS` (~line 117; values == `ArtifactKind(singular).glob_pattern`).
- R5 operator-token→singular map: `src/charter/activation/consistency_check.py` `_CLI_KIND_TO_DRG_SINGULAR` (~line 107).
- R6 `ArtifactKind`→`NodeKind` identity map: `src/specify_cli/mission_step_contracts/executor.py` `_ARTIFACT_TO_NODE_KIND` (~line 63, 11 entries); `src/charter/activation/synthesizer/project_drg.py` `_KIND_TO_NODE_KIND` (~line 75, 4 entries).
- 3-kind subset `{directive,tactic,styleguide}`: public home `charter.activation.synthesizer.topic_resolver.SYNTHESIZABLE_KINDS` (~line 36). Restatements: `src/charter/bundle.py` `_DOUBLED_LEAF_BASES` (~383), `synthesizer/write_pipeline.py` (~512), `specify_cli/cli/commands/charter/_synthesis.py` (~580, plural form).

**MUST NOT be flagged (T014 guard):** `DIRECT_WRITE_KINDS` (hand-authored 5-tuple, <8 so R1-safe but a members-rule must skip), the intentionally-total `PROJECT_KIND_DIRS`, `charter/offering/drg/query.py` `_KIND_BY_LEGACY_FIELD` (str→`NodeKind`, NOT R6), `typing.Literal[...]` kind aliases (`synthesizer/interview_mapping.py`, `manifest.py`, `synthesize_pipeline.py` — a `Literal` cannot consume a runtime frozenset, so exempt `ast.Subscript` under `Literal[...]`), and per-kind dispatch tables whose values are callables/`NodeKind` with non-kind string/other keys (existing R2 carve-out).

## Subtasks & Detailed Guidance

- **T010–T013**: one failing self-mutation test per rule (parametrize where natural), mirroring the existing `test_gate_detects_*` style. RED first.
- **T014**: `test_gate_leaves_legitimate_constructs_alone` — assert each known-good shape yields no finding.
- **T015**: implement R1′ (universe-scale set where exactly one element is a non-kind string → still a mirror), R4 (dict with ≥8 kind-plural keys whose values all equal the kind's `glob_pattern`), R5 (dict whose keys are all operator tokens mapping to the matching singular), R6 (dict whose keys are `ArtifactKind` members and values `NodeKind` members — AST: `ast.Attribute` on `ArtifactKind`/`NodeKind`, or `ArtifactKind(...)`/`NodeKind(...)` calls). Scope each tightly so T014 stays green.
- **T016–T019 [P]**: migrate each site to a comprehension over `ArtifactKind` (R1′ sites keep their single non-kind element explicit via union; R4 derives values from `glob_pattern`; R5 from `operator_token`; R6 from `NodeKind(k.value)` or the existing mapping intent).
- **T020**: point the three `{directive,tactic,styleguide}` restatements at `SYNTHESIZABLE_KINDS` (import it; keep ordering/shape each site needs); remove the gate docstring follow-up note.

## Test Strategy

- Targeted: `pytest tests/architectural/test_charter_kind_vocabulary_single_authority.py -q`; plus the owning subsystem trees for the migrated sources: `tests/charter/ tests/charter_offering/` and the specify_cli tests covering `executor.py`/`_synthesis.py` (find via `grep -rl`). Plus `make test-fast`.
- `pytest tests/architectural/test_no_legacy_terminology.py` (charter/offering + prose touched).
- `ruff check` + `ruff format --check --force-exclude` + `mypy` on touched files.

## Review Guidance

- Each rule RED→GREEN; T014 proves no false positives; the full `src/` scan passes with empty allowlist (`test_allowlist_is_empty`, `test_gate_reaches_every_package_under_src`).
- Each migrated site derives from the authority (no residual literal); `RECOGNISED_ARTIFACT_DIRS` still identity-held through `charter.packs`.

## Activity Log

- 2026-10-09T20:40:00Z – system – Prompt created.
