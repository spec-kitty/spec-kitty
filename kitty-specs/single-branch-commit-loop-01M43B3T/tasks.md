# Tasks

## Work Package WP01: agent action implement guards the single_branch write checkout (#5459)

**Dependencies**: None

Requirement refs: FR-001, FR-002, SC-001

- [ ] T001 Red-first regression test through `agent action implement`
- [ ] T002 Extract `guard_repo_root_claim` and call it from the action path

## Work Package WP02: single_branch status annotations commit themselves (#5655)

**Dependencies**: None

Requirement refs: FR-003, SC-002

- [ ] T003 Red-first regression test (mark-status + move-task leave a clean tree)
- [ ] T004 Admit SINGLE_BRANCH in the annotation transaction predicate; route mark-status through it

## Work Package WP03: repeated -m and the gate-mechanics doc (#5647, #5648)

**Dependencies**: None

Requirement refs: FR-004, FR-005

- [ ] T005 Accept repeated -m on safe-commit and spec-commit
- [ ] T006 Point ci-gate-mechanics.md at agent acceptance-verdict
