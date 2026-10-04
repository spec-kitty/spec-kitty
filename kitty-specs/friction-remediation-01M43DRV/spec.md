# Mission Specification: Regression-slice friction remediation

**Mission Branch**: `issue-5552-friction-remediation`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief (2026-10-04): deliver #5552, #5298, #5653, #5654 and #5186 as one Mission, clearing the friction the regression-slice cleanup Mission (PR #5656) hit. WP03 (#5653) and WP04 (#5654 + #5186) are sequenced behind open PRs #5650 and #5656 (see Decision Moment `01M43DSJXP334BFKRQFAVMH22J`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Squash consolidate lands a Mission that has quickstart.md or contracts/ (Priority: P1)

An operator runs the default (squash) `spec-kitty consolidate` on a coordination-topology Mission whose plan produced `quickstart.md` and `contracts/*.md`. Today the squash projection proof treats those planning files as coordination bookkeeping (their kind is unknown), finds the coordination ref lacks them or differs from the checkpoint, and refuses with "projected coordination bookkeeping content did not land on the target". `--resume` refuses the same way. The only escapes are `--strategy merge` or committing a byte-identical copy on the coordination branch.

**Why this priority**: #5552 is in the 4.0.0 release scope (parent #5001) and recurs on 4.0.0rc6; it blocks the default terminus command for any Mission whose plan emits a quickstart or contracts.

**Independent Test**: `kind_for_mission_file` classifies `quickstart.md` and `contracts/<x>.md` to a PRIMARY-partition kind, and `_post_checkpoint_mission_paths` excludes both from the projected set on a real git fixture where a lane merge brings them onto the coordination ref after the checkpoint.

**Acceptance Scenarios**:

1. **Given** a coordination Mission whose post-checkpoint coordination commits add `quickstart.md` and `contracts/a.md`, **When** the projection path set is computed, **Then** neither path is projected (they are PRIMARY planning artifacts).
2. **Given** the same fixture, **When** a coordination-bookkeeping path (e.g. `traces/approach.md`) also changed, **Then** that path is still projected (positive control on the same fixture).
3. **Given** any topology, **When** `quickstart.md` or a `contracts/` file is written through the placement seam, **Then** it resolves to the PRIMARY surface exactly as before (write placement unchanged).

---

### User Story 2 - Accept honours an explicit "this Mission defines no contracts" waiver (Priority: P1)

An operator finishing a software-dev Mission that defines no interfaces (test remediation, refactor) runs `spec-kitty accept`. Today strict mode blocks on the `paths.deliverables: contracts/` convention; the only escapes are `--lenient` (which relaxes every path convention) or an empty placeholder directory (#1892 calls that unintended). The operator ruled (2026-09-28, 2026-10-04) that `contracts/` stays required by default, and a Mission may declare in `meta.json` that it defines no contracts, with a rationale.

**Why this priority**: #5298 is P1 / status:ready (parent #2017) and hits about a third of Missions.

**Independent Test**: `evaluate_path_conventions(..., strict_metadata=True)` on a software-dev Mission with no `contracts/`: blocks without a waiver, blocks (and warns) with a malformed waiver, and passes with a well-formed waiver.

**Acceptance Scenarios**:

1. **Given** a software-dev Mission with no `contracts/` and `meta.json` carrying `"contracts": "none"` plus a non-empty `contracts_rationale`, **When** `accept` runs strict, **Then** no `contracts` path violation is reported and the waiver (with its rationale) is surfaced as a warning.
2. **Given** the same Mission without the waiver, **When** `accept` runs strict, **Then** the `contracts` path violation still blocks.
3. **Given** a waiver whose value is not `"none"`, or whose rationale is missing/blank/non-string, **When** `accept` runs strict, **Then** the requirement stays in force and a warning names the malformed field.
4. **Given** a corrupt `meta.json`, **When** the waiver is read, **Then** the read fails closed (the existing `MissionMetaReadError` contract).

---

### User Story 3 - Testable consolidate dry-run attestation notice (Priority: P3, sequenced)

The `consolidate --dry-run` "attestation not applied" notice is decided by a pure function, unit-tested in isolation, so its test stops stubbing 11 consolidate internals (#5653). Runs only if PR #5650 has merged.

### User Story 4 - Root-honest permission tests and order-independent migration ordering test (Priority: P3, sequenced)

The chmod tests that are vacuous or failing as uid 0 inject the failure at the I/O seam (#5654), and `TestOrdering` passes in isolation (#5186). Runs only if PR #5656 has merged.

### Edge Cases

- A `contracts/` directory that DOES exist while a waiver is declared: the waiver is still honoured (nothing missing) and no violation is produced.
- A nested contracts path (`contracts/sub/x.yaml`) classifies like a top-level one.
- A path under another Mission's slug never classifies (existing `mission_slug` scoping).
- The waiver only removes the `contracts` deliverable token; other path conventions (`src/`, `tests/`, `docs/`) still block.
- Lenient mode with a waiver: no warning about missing `contracts/`; the waiver note is still surfaced.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Classify quickstart.md as a PRIMARY kind | As an operator, I want `quickstart.md` classified to a PRIMARY-partition kind so that squash consolidate never projects it as coordination bookkeeping. | High | Open | [build] | no — the projection test is red before the classifier entry exists |
| FR-002 | Classify contracts/** as a PRIMARY kind | As an operator, I want every path under `contracts/` classified to a PRIMARY-partition kind so that squash consolidate never projects it as coordination bookkeeping. | High | Open | [build] | no — same fixture as FR-001, red before the directory entry exists |
| FR-003 | Projection still carries coordination bookkeeping | As an operator, I want unrecognised coordination bookkeeping paths still projected so that #4981/#4973 stay fixed. | High | Open | [ratchet] | yes — positive control on the FR-001/FR-002 fixture |
| FR-004 | One fail-closed contracts-waiver reader | As an operator, I want a single `core/paths.py` helper to read `contracts` / `contracts_rationale` from `meta.json` so that there is one authority for the waiver. | High | Open | [build] | no — malformed-value tests are red before the helper exists |
| FR-005 | Accept drops a waived contracts deliverable | As an operator, I want strict `accept` to skip the `contracts` path convention when the waiver is well formed so that a no-interface Mission passes without `--lenient`. | High | Open | [build] | no — strict-accept waiver test is red before the change |
| FR-006 | Unwaived or malformed stays blocking | As an operator, I want strict `accept` to keep blocking on a missing `contracts/` with no waiver or a malformed one so that the default requirement is preserved. | High | Open | [ratchet] | yes — paired with FR-005 on the same fixture |
| FR-007 | Waiver is documented | As a Mission author, I want the `meta.json` waiver fields recorded in an ADR and in the meta field documentation so that the declaration is discoverable and auditable. | Medium | Open | [build] | no |
| FR-008 | Pure dry-run attestation notice (sequenced) | As a maintainer, I want the dry-run attestation notice decided by a pure function so that its test needs no internal stubs (#5653). | Low | Open | [build] | no |
| FR-009 | Root-honest chmod tests and isolated TestOrdering (sequenced) | As a maintainer, I want the root-vacuous chmod tests to inject the failure at the seam and `TestOrdering` to pass alone (#5654, #5186). | Low | Deferred (WP04 canceled: PR #5656 still open) | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Complexity ceiling | Every new or changed function stays at cyclomatic complexity <= 15 (ruff C901); no suppression is widened. | Maintainability | High | Open |
| NFR-002 | Lint and type clean | `ruff check`, `ruff format --check --force-exclude` and `mypy` report 0 issues on changed files. | Maintainability | High | Open |
| NFR-003 | Gates stay green honestly | Every architectural gate that references a touched file passes without loosening (0 allowlist entries added). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single waiver authority | The waiver is read only from `meta.json` through one helper; no spec-frontmatter or plan-frontmatter source. | Technical | High | Open |
| C-002 | validate_mission_paths single caller | Only `evaluate_path_conventions` may call `validate_mission_paths`; the waiver applies there or below. | Technical | High | Open |
| C-003 | Hands off concurrently-owned files | No edits to `mission_finalize.py`, `tasks_move_task.py`, `orchestrator_api/commands.py`, the charter worktree write guard, #5317/#5601, #5140 or `p0_repro` marker work. | Technical | High | Open |
| C-004 | Sequencing | WP03/WP04 run only after PRs #5650 and #5656 merge; never stack on or duplicate them. | Business | High | Open |

### Key Entities

- **Mission artifact kind**: the file→kind classification (`mission_runtime.artifacts`) whose partition membership decides PRIMARY vs coordination placement and projection exclusion.
- **Contracts waiver**: the `meta.json` pair `contracts: "none"` + `contracts_rationale: <non-empty string>`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A squash-consolidate projection over a fixture with post-checkpoint `quickstart.md` and `contracts/*.md` projects 0 of those paths and still projects the coordination bookkeeping path — [build] · no-op passable: no
- **SC-002**: Strict `accept` on a waived no-contracts software-dev Mission reports 0 path violations; on the unwaived and malformed variants it reports exactly 1 — [build] · no-op passable: no
- **SC-003**: All architectural gate files that reference the touched modules pass with 0 new allowlist entries — [ratchet] · no-op passable: yes
