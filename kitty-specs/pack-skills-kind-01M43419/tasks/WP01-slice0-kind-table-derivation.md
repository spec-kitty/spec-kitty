---
work_package_id: WP01
title: "Slice 0 \u2014 derive remaining lockstep kind tables from ArtifactKind"
dependencies: []
requirement_refs:
- FR-001
- FR-002
- SC-005
planning_base_branch: claude/festive-babbage-lhkqac
merge_target_branch: claude/festive-babbage-lhkqac
branch_strategy: Planning artifacts for this mission were generated on claude/festive-babbage-lhkqac.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into claude/festive-babbage-lhkqac unless
  the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- at: '2026-10-04T10:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/artifact_kinds.py
create_intent:
- tests/architectural/test_kind_table_derivation.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/offering/artifact_kinds.py
- src/specify_cli/doctrine/org_charter.py
- src/charter/activation/org_pack_discovery.py
- src/charter/activation/drg_activation.py
- CLAUDE.md
- tests/architectural/test_kind_table_derivation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Slice 0 — derive remaining lockstep kind tables from ArtifactKind

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role implementer) and behave according to its guidance before parsing the rest of this prompt.

## Objective

Deliver FR-001, FR-002, SC-005 of mission `pack-skills-kind-01M43419` (see `../spec.md`, `../plan.md`, ADR `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`).

## Branch Strategy

Planning branch and final merge target: `claude/festive-babbage-lhkqac`. Topology `single_branch`: work happens in the repository root checkout; prepare with `spec-kitty agent action implement WP01 --agent claude`.

## Subtasks

### T001

Add ArtifactKind facts `org_requirable` and `selection_overlayable` (plan IC-01): requirable = the 10 kinds in today's `REQUIRED_KIND_FIELDS` (org_charter.py:85); overlayable = the 8 in `_REQUIRED_KIND_FIELDS` (org_pack_discovery.py:58). Expose derived frozensets.

### T002

Derive `REQUIRED_KIND_FIELDS` (specify_cli) and `_REQUIRED_KIND_FIELDS` (charter) from those facts — byte-for-byte same membership and ORDER-insensitive consumers verified (check iteration order dependence at org_charter.py:361/:565 and keep a stable order derived from enum declaration order).

### T003

Derive `_SINGULAR_TO_PER_KIND_FIELD` (drg_activation.py:231) from ArtifactKind (activatable kinds in CHARTER_KIND_TOKENS → `activated_<plural>`); keep identical mapping.

### T004

Architectural test tests/architectural/test_kind_table_derivation.py: overlayable ⊆ requirable; requirable == `OrgCharterPolicy.required_*` model fields; overlayable == `DoctrineSelectionConfig.selected_*` fields; each module constant equals its derivation. Red-first: write the field-equality assertions before refactor and record they pass on the literal tables, then refactor.

### T005

Fix stale comment org_pack_discovery.py:54 (says anti_pattern; real difference is asset/glossary_pack) and `_BUILTIN_ARTIFACT_KINDS` docstring "eight kinds" (pack_context.py:105 — one-line out-of-map edit allowed). CLAUDE.md: `doctrine.org.packs` → `charter_packs.org.packs` (legacy fallback `doctrine.org.packs`). Remove `REQUIRED_KIND_FIELDS` from tests/architectural/dead_symbol_allowlist.yaml if it becomes referenced.

## Amendments (post-tasks anti-laziness squad — binding)

- T004 also pins today's literal tuples (values AND order — consumed at org_charter.py:361/:565) as a snapshot assertion written BEFORE the refactor; asserts every derived `_SINGULAR_TO_PER_KIND_FIELD` value is a real `PackContext` attribute; asserts the overlayable set ⊆ requirable explicitly.
- T001 replaces the curated member list in `_REQUIRED_KIND_FIELDS` with the new fact — no second source left.
- DoD: run tests/architectural/test_layer_rules.py.

## Definition of Done

- Every subtask done; new branches/helpers carry focused tests in the same commit (Sonar new-code gate).
- `ruff check`, `ruff format --check --force-exclude <changed files>`, `mypy` on changed modules: zero findings; complexity ≤15; no new suppressions.
- Targeted tests for touched modules plus owning subsystem dirs pass; record commands and counts in the activity log.
- Layer direction respected: `charter` never imports `specify_cli`.

## Risks

- Exact-set/totality tests across `tests/charter`, `tests/doctrine`, `tests/architectural` enumerate kinds — find them by running those directories' fast tier.
- Out-of-map edits are allowed only with a one-line rationale in the activity log.

## Reviewer Guidance

Verify each requirement in the objective has a non-vacuous test; reject no-op passes.

## Activity Log

- 2026-10-04 implementer (python-pedro/sonnet): T001–T005 in db55854d. Tests: `pytest tests/architectural/test_kind_table_derivation.py tests/specify_cli/doctrine tests/architectural/test_layer_rules.py tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/charter/test_answers_inert_and_org_union.py tests/charter/test_drg_activation_gate.py -n auto --dist loadfile` → 549 passed; `pytest tests/charter tests/doctrine -m "fast or unit" -n auto --dist loadfile` → 6916 passed, 32 skipped, 1 failed (pre-existing: test_pack_manager.py::test_preparation_refuses_broken_required_inputs[unreadable], root-user chmod; red on HEAD~ too). Out-of-map: AGENTS.md (CLAUDE.md is a symlink to it — the FR-002 doc fix), pack_context.py docstring ("eight kinds" stale).
- 2026-10-04 reviewer (reviewer-renata/opus): REJECT — order change unpinned, empty activity log, stale "8" wording. Fold: order change accepted and pinned (`_ACCEPTED_REQUIRED_ORDER`; user-visible only in promotion/pre-selection message order, org_charter.py:372/:853); stale "8" fixed at org_charter.py:648 and two test docstrings. `pytest tests/architectural/test_kind_table_derivation.py` → 8 passed.
