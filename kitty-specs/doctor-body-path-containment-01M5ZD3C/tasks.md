# Tasks: Doctor flags org-pack nodes whose body_path escapes the pack

**Mission**: `doctor-body-path-containment-01M5ZD3C` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6418-doctor-body-path-containment`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests for the charter predicate (`..`, absolute, Windows forms, symlink, contained, missing target, discovered node ignored, no body_path) | WP01 | |
| T002 | `BodyPathEscape` + `find_body_path_escapes(fragment, pack_root)` in `charter.offering.drg.org_pack_loader` | WP01 | |
| T003 | `find_org_body_path_escapes(repo_root, fragments)` in `charter.activation.drg_activation` | WP01 | |
| T004 | Red-first doctor tests: JSON exit 1 + `errors` + `body_path_escapes`; human section; contained control exits 0; check-crash recorded as error | WP01 | |
| T005 | JSON collector wiring (`_charter_pack_collect.py`) | WP01 | |
| T006 | Human renderer wiring (`_profile_health_render.py`) | WP01 | |
| T007 | Drop `@wip @defect:6418` from PR-CHARTER-SHARING-004 and update its header comment | WP02 | [P] |
| T008 | PROMISES.md: PR-CHARTER-SHARING-004 → bound, authority names the doctor check | WP02 | [P] |
| T009 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry | WP02 | [P] |

## Phase 1 — Foundational + Story 1/2 (P1)

### WP01 — Doctor reports escaping fragment body_path ([tasks/WP01-doctor-body-path-escapes.md](tasks/WP01-doctor-body-path-escapes.md))

- **Goal**: `doctor charter-packs` exits 1 and names each authored fragment node whose `body_path` escapes its pack root; contained paths stay healthy.
- **Priority**: P1 (MVP)
- **Independent test**: the #6418 fixture exits 1 (`..` and absolute); the same fixture with a contained `body_path` exits 0 with `body_path_escapes: []`.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-004
- **Included subtasks**:

T001 Red-first tests for the charter predicate (WP01)
T002 BodyPathEscape + find_body_path_escapes in org_pack_loader (WP01)
T003 find_org_body_path_escapes in drg_activation (WP01)
T004 Red-first doctor tests (WP01)
T005 JSON collector wiring (WP01)
T006 Human renderer wiring (WP01)

- **Sketch**: tests red → predicate → registry wrapper → doctor tests red → collector → renderer → all green.
- **Dependencies**: none
- **Risks**: complexity ceiling in `_collect_org_layer_data` and `_render_org_layer_section` (keep the check in helpers); `authored_nodes` relies on the node subclass (call it on the loader's fragment, never a copy).

## Phase 2 — Story 3 (P2)

### WP02 — Bind PR-CHARTER-SHARING-004 and record the fix ([tasks/WP02-bind-scenario-and-changelog.md](tasks/WP02-bind-scenario-and-changelog.md))

- **Goal**: the consumer promise gates again; the changelog records the fix.
- **Priority**: P2
- **Independent test**: the feature file and PROMISES.md carry no `@wip`/`@defect:6418` for PR-CHARTER-SHARING-004; the changelog has an `[Unreleased]` entry citing #6418.
- **Requirements**: FR-006
- **Included subtasks**:

T007 Drop @wip/@defect:6418 tags on the scenario (WP02)
T008 PROMISES.md row to bound (WP02)
T009 CHANGELOG [Unreleased] entry (WP02)

- **Dependencies**: WP01
- **Risks**: the scenario runs only in the JVM lane; its step asserts a non-zero exit, which WP01 delivers.

## Parallelization

WP02 depends on WP01 (it would turn a red scenario on without the fix). Inside WP02, T007–T009 touch separate files.

## MVP

WP01 alone fixes the defect; WP02 makes it gate.
