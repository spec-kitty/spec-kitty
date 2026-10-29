# Tasks: Re-synthesis after activation

**Mission**: `resynthesis-after-activation-01M5ZD62` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6510-resynthesis-after-activation`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Characterization test + tidy-first extraction of the directive → synthesis-input derivation | WP01 | |
| T002 | Red-first CLI acceptance tests (synthesize / resynthesize after activation, delivery, activation untouched, hand-authored directive) | WP01 | |
| T003 | Ownership reader `synthesized_urns(repo_root, kind)` in the synthesizer manifest module + unit tests | WP01 | [P] |
| T004 | Exclude synthesis-owned directives at the request seam | WP01 | |
| T005 | Blast-radius run, quality gates, live quickstart check | WP01 | |
| T006 | Red-first tests for the structured `colliding_urn` and origin-aware refusal text | WP02 | |
| T007 | Additive `colliding_urn` field + origin-neutral core wording at both raise sites | WP02 | |
| T008 | Collision remedy helper (new module) classifying the origin | WP02 | |
| T009 | Wire the remedy into `synthesize` and `resynthesize` (human + JSON) | WP02 | |
| T010 | Blast-radius run, complexity and quality gates | WP02 | |

## Phase 1 — Core fix

### WP01 — Exclude synthesis-owned directives from synthesis input

- **Prompt**: [tasks/WP01-exclude-owned-directives.md](tasks/WP01-exclude-owned-directives.md)
- **Goal**: `charter synthesize` and `charter resynthesize --topic directive:PROJECT_001` succeed after a directive is activated (FR-001, FR-002). Activation and delivery do not change (FR-004, FR-005), and hand-authored directives behave as before (FR-008).
- **Priority**: P1 (MVP). **Dependencies**: none.
- **Independent test**: the new CLI acceptance file is RED on the planning base and GREEN on the WP's last commit.

T001 Characterization test + tidy-first extraction of the directive → synthesis-input derivation (WP01)
T002 Red-first CLI acceptance tests (WP01)
T003 Ownership reader `synthesized_urns(repo_root, kind)` + unit tests (WP01)
T004 Exclude synthesis-owned directives at the request seam (WP01)
T005 Blast-radius run, quality gates, live quickstart check (WP01)

**Implementation sketch**: T001 (behaviour-preserving commit) → T002 (failing tests commit) → T003 → T004 (tests go green) → T005.
**Risks**: building a real prior synthesis in a test fixture without patching the request builder; the dead-symbol gate needs the new public helper to have a `src/` caller (T004 provides it in the same WP).

## Phase 2 — Refusal quality

### WP02 — Origin-aware collision refusal

- **Prompt**: [tasks/WP02-origin-aware-refusal.md](tasks/WP02-origin-aware-refusal.md)
- **Goal**: a remaining collision refusal names the colliding node's origin and the recovery, and carries a structured `colliding_urn` (FR-006, FR-007, SC-003). The additive-only check itself is unchanged.
- **Priority**: P2. **Dependencies**: WP01 (it uses the ownership reader to classify).
- **Independent test**: the refusal-text tests are RED on WP01's tip and GREEN on WP02's last commit.

T006 Red-first tests for structured `colliding_urn` and origin-aware refusal text (WP02)
T007 Additive `colliding_urn` field + origin-neutral core wording at both raise sites (WP02)
T008 Collision remedy helper (new module) classifying the origin (WP02)
T009 Wire the remedy into `synthesize` and `resynthesize` (WP02)
T010 Blast-radius run, complexity and quality gates (WP02)

**Risks**: the `synthesize` command's `SynthesisError` branch is already long; keep the added logic in the helper so no function exceeds complexity 15.

## Dependencies

WP01 → WP02. No parallel WPs; WP01 is the MVP.

## Closeout (orchestrator, not a WP)

`docs/changelog/CHANGELOG.md` `[Unreleased]` entry; follow-up issues for the staging `.failed` accumulation and the neutrality gate (#4226); the issue matrix rows for #6510 and #4226.
