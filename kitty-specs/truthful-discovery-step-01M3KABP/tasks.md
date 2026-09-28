# Work Packages: Truthful software-dev discovery step and finalize shim cleanup

**Inputs**: `kitty-specs/truthful-discovery-step-01M3KABP/` (spec.md, plan.md, research.md)
**Tests**: Required. Each WP opens with a red-first regression test pinned to its issue (ADR 2026-07-17-1), converted to focused tests before review.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: research mission scaffolds research.md/data-model.md from shipped templates | WP01 | |
| T002 | Route research.py asset lookup through canonical resolve_template with a destination→template table | WP01 | |
| T003 | Retire legacy resolve_template_path and its core export | WP01 | |
| T004 | Update tests pinning the legacy resolver / "no template for any type" | WP01 | |
| T005 | Keep #4926 guards: positive + negative control on one fixture | WP01 | |
| T006 | Red-first: end-to-end discovery contract test through next | WP02 | |
| T007 | Rewrite the mission-step research prompt (discovery + /spec-kitty.research contract) | WP02 | |
| T008 | Plan prompt Phase 0: extend, don't replace research.md (+ text invariant test) | WP02 | [P] |
| T009 | Align spk-mission-research skill, command map, slash-command doc | WP02 | [P] |
| T010 | Changelog entry under [Unreleased] and doctrine regen gates | WP02 | |
| T011 | Delete _ensure_branch_checked_out and its three test patches | WP03 | [P] |
| T012 | Rebuild validate-only read-only fixture with HEAD ≠ target | WP03 | [P] |
| T013 | Drop dead fire_dossier_sync test patch | WP03 | [P] |

---

## Work Package WP01: Research command resolves shipped templates canonically (Priority: P1)

**Goal**: `spec-kitty research` creates all four advertised artifacts for a research mission via the canonical resolver, keeping the #4926 guards.
**Independent Test**: research mission with filled plan → 4/4 non-empty artifacts; software-dev mission → 0 created, 0 overwritten.
**Prompt**: `tasks/WP01-research-command-canonical-templates.md`
**Requirement Refs**: FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, C-003

### Included Subtasks

T001 Red-first: research mission scaffolds research.md/data-model.md from shipped templates (WP01)
T002 Route research.py asset lookup through canonical resolve_template with a destination→template table (WP01)
T003 Retire legacy resolve_template_path and its core export (WP01)
T004 Update tests pinning the legacy resolver / "no template for any type" (WP01)
T005 Keep #4926 guards: positive + negative control on one fixture (WP01)

### Dependencies

- None.

---

## Work Package WP02: Truthful discovery prompt, aligned guidance, e2e contract test (Priority: P1)

**Goal**: every instruction in the prompt `next` issues for `discovery` is executable before a plan exists; `/spec-kitty.research` states its per-type contract; all agent-facing research guidance agrees.
**Independent Test**: new end-to-end test drives `next` to `discovery`, runs every `spec-kitty` invocation in the issued prompt (exit 0), and sees `next` advance.
**Prompt**: `tasks/WP02-truthful-discovery-prompt.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-008, FR-012, FR-013, NFR-004, C-001, C-002

### Included Subtasks

T006 Red-first: end-to-end discovery contract test through next (WP02)
T007 Rewrite the mission-step research prompt (discovery + /spec-kitty.research contract) (WP02)
T008 Plan prompt Phase 0: extend, don't replace research.md (+ text invariant test) (WP02)
T009 Align spk-mission-research skill, command map, slash-command doc (WP02)
T010 Changelog entry under [Unreleased] and doctrine regen gates (WP02)

### Dependencies

- Depends on WP01 (prompt wording describes WP01's final command behaviour; changelog covers both).

---

## Work Package WP03: Retire the finalize checkout shim (Priority: P3)

**Goal**: no test-only no-op in production; the read-only test proves the divergent-branch claim.
**Independent Test**: `git grep _ensure_branch_checked_out -- src tests` is empty; finalize tests pass; read-only test fails if validate-only moves HEAD.
**Prompt**: `tasks/WP03-retire-finalize-checkout-shim.md`
**Requirement Refs**: FR-009, FR-010, FR-011, C-004, C-005

### Included Subtasks

T011 Delete _ensure_branch_checked_out and its three test patches (WP03)
T012 Rebuild validate-only read-only fixture with HEAD ≠ target (WP03)
T013 Drop dead fire_dossier_sync test patch (WP03)

### Dependencies

- None (parallel with WP01).
