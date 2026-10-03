# Tasks: Charter Service Architecture for 4.x

## Branch Strategy

Planning/base and final mission target are
`docs/charter-service-architecture`. This single-branch Mission executes work
packages sequentially in the owned checkout.

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Read the final review synthesis and identify the superseded projection-server decisions | WP01 | no |
| T002 | Author the Proposed 4.x ADR with staged ownership and invariants | WP01 | no |
| T003 | Specify read conformance, fallback retirement, and write parity gates | WP01 | no |
| T004 | Add consequences, risks, non-goals, and deferred decisions | WP01 | no |
| T005 | Update the living system-context view to place the charter service | WP02 | no |
| T006 | Update the living container view with Python seam and Java sibling | WP02 | no |
| T007 | Update the living component view with hexagonal read/write modules | WP02 | no |
| T008 | Cross-link every C4 view to the owning ADR and mark planned elements | WP02 | no |
| T009 | Add one focused strangler-prep clause to the active 4.x roadmap | WP03 | no |
| T010 | Add one forward-intent pointer to architecture vision | WP03 | no |
| T011 | Add one pointer to the current charter-resolution plan | WP03 | no |
| T012 | Validate links, terminology, Mermaid, and ownership boundaries | WP03 | no |

## WP01 — Canonical charter redesign ADR

**Goal**: Establish one decision owner for the staged Python-to-Java charter
transition.

**Independent test**: A reviewer can identify one read owner and one write
owner at every transition stage and cannot mistake deferred stack choices for
decisions.

**Prompt**: [tasks/WP01-charter-redesign-adr.md](tasks/WP01-charter-redesign-adr.md)

- [ ] T001 Read the final review synthesis and identify superseded decisions.
- [ ] T002 Author the Proposed 4.x ADR.
- [ ] T003 Specify read and write acceptance gates.
- [ ] T004 Record consequences, risks, non-goals, and deferrals.

**Dependencies**: none

## WP02 — Living C4 views

**Goal**: Make the intended system, container, and component relationships
visible without duplicating ADR rationale.

**Independent test**: The three living C4 views refine one another, link to the
ADR, and visibly mark the Java service as planned.

**Prompt**: [tasks/WP02-living-c4-views.md](tasks/WP02-living-c4-views.md)

- [ ] T005 Update system context.
- [ ] T006 Update container view.
- [ ] T007 Update component view.
- [ ] T008 Add ADR links and planned-state labels.

**Dependencies**: WP01

## WP03 — 4.x placement and validation

**Goal**: Place the decision in the 4.x plan and navigation surfaces, then
validate the aggregate documentation.

**Independent test**: The roadmap places reads under #645 and writes under
#2519, no page duplicates the ADR, and targeted validation passes.

**Prompt**: [tasks/WP03-roadmap-links-validation.md](tasks/WP03-roadmap-links-validation.md)

- [ ] T009 Add the roadmap clause.
- [ ] T010 Add the architecture-vision pointer.
- [ ] T011 Add the charter-resolution plan pointer.
- [ ] T012 Validate links, terminology, diagrams, and authority boundaries.

**Dependencies**: WP01, WP02
