# Mission Specification: Charter CLI typed errors and JSON

**Mission Branch**: `issue-6557-charter-cli-typed-errors-json` (planning base and merge target)
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "Charter CLI typed errors and JSON (#6557, local slices of #6525/#6526). See operator decisions recorded in this session."

Issues: #6557 (whole), #6525 and #6526 (independent local-acceptance slices only, per the operator ruling
of 2026-10-23 recorded in their bodies). The held integration completion of #6525/#6526 (contract field
mapping #6520, contract revision #6521, contract refusal codes #6524) stays with epic #6518 and is out of
scope. Grounding and operator decisions: [research.md](research.md).

## Intent Summary (confirmed 2026-10-27, decision `01M5ZCD0WNV5AYF5KTBADN4Y4E`)

The primary actor is an operator, or tooling such as the charter corpus harness, running
`spec-kitty charter status`, `spec-kitty charter activate KIND ID` or `spec-kitty charter deactivate KIND ID`.

1. A broken or non-mapping `charter.yaml` makes `charter status` refuse with the typed code
   `ACTIVE_CHARTER_CONFIG_INVALID`, naming the file and the remedy, exit 1, nothing written; in text and in `--json`.
2. Positional `activate` and `deactivate` accept `--json`: success emits a versioned payload of what changed
   plus a cascade report; refusals emit the canonical coded error; exit codes are unchanged.
3. `charter status --json` gains an `activation` block describing the effective, locally available activation state.

Invariant: the human-readable output of these commands is unchanged except for the #6557 refusal and the
coded error lines. No contract code, revision or camelCase contract field is invented.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Broken charter is a fixable refusal, not a crash (Priority: P1)

An operator hand-edits `.kittify/charter/charter.yaml`, breaks the YAML (or makes its root a list), and
runs `spec-kitty charter status`. Today they see "Unexpected error" with a raw parser message (or a
misleading "Bundle schema version not found … run upgrade"). They should see a coded refusal that names the
file, the problem and how to fix it.

**Why this priority**: It is a reported bug (#6557); "Unexpected" reads as a CLI defect and the list-root
message sends the operator to the wrong remedy.

**Independent Test**: break `charter.yaml` in a scratch project and run `charter status` with and without `--json`.

**Acceptance Scenarios**:

1. **Given** an unparseable `charter.yaml`, **When** the operator runs `charter status`, **Then** it exits 1 and prints `Error (ACTIVE_CHARTER_CONFIG_INVALID): …` naming the file, the parser problem and the remedy, and never the word "Unexpected".
2. **Given** a `charter.yaml` whose root is a list, **When** the operator runs `charter status`, **Then** it exits 1 with the same code and remedy, and never mentions the bundle schema version or `spec-kitty upgrade`.
3. **Given** either broken file, **When** the operator runs `charter status --json`, **Then** stdout is exactly one JSON object `{"ok": false, "error": {"code": "ACTIVE_CHARTER_CONFIG_INVALID", "message": …}}` and exit is 1.
4. **Given** a sound `charter.yaml`, **When** the operator runs `charter status`, **Then** behaviour is unchanged.

---

### User Story 2 - Activation changes are machine-readable (Priority: P2)

Tooling (the corpus harness, a CI script) runs `charter activate directive <id> --cascade all --json` or
`charter deactivate … --json` and needs to know exactly what changed, what the cascade touched and why a
refusal happened, without parsing human text.

**Why this priority**: #6525 local slice; unblocks harness work on its own evidence.

**Independent Test**: run positional activate/deactivate with `--json` in a scratch project, with and without `--cascade`, plus each refusal case.

**Acceptance Scenarios**:

1. **Given** a valid kind and id, **When** `charter activate KIND ID --json` runs, **Then** stdout is one JSON object carrying `schema_version: "1.0.0"`, the command, kind, id, the entries that changed and the warnings, and exit is 0.
2. **Given** `--cascade SCOPE`, **When** activate or deactivate runs with `--json`, **Then** the payload carries a cascade report: the source URN, and for every touched artifact its kind, stored spelling (config id) and URN, grouped as cascaded, reinstated, failed, skipped (out of scope / deactivated / unreached / kind-filtered / shared with the still-referencing URN, or required).
3. **Given** any refusal (unknown kind, bad scope, broken charter config, org-required deactivation, linked-worktree write root, activation failure), **When** run with `--json`, **Then** stdout is one canonical error object with a code and message, and the exit code equals the exit code of the same command without `--json`.
4. **Given** the same invocation without `--json`, **Then** the human-readable lines are unchanged except that refusals print `Error (<CODE>): …`.
5. **Given** `--json`, **When** the catalog recompile or resynthesis that follows prints progress, **Then** none of it reaches stdout as non-JSON.

---

### User Story 3 - Effective activation state in status JSON (Priority: P3)

Tooling reads `charter status --json` and needs the project's activation state (where it comes from, what is
selected and deactivated, which org-required ids are in force) without reading `.kittify` files.

**Why this priority**: #6526 local slice.

**Independent Test**: `charter status --json` on a migrated (ledger) project and on a supported legacy project.

**Acceptance Scenarios**:

1. **Given** a project with an activation ledger, **When** `charter status --json` runs, **Then** the payload has an `activation` block with `schema_version`, `source: "ledger"`, `path`, `selected`, `deactivated`, `mission_types`, `activated_kinds` and `required`.
2. **Given** a legacy (unmigrated) project, **Then** `source` is `"legacy"` and `path` names the legacy file actually read.
3. **Given** an org pack that requires an id which an explicit allow list leaves out, **Then** that id appears in `required` with `in_force: false`; a required id not left out has `in_force: true`.
4. **Given** the text (non-JSON) `charter status`, **Then** output is unchanged.

### Edge Cases

- Empty or comment-only `charter.yaml`: refused by the same gate (`ACTIVE_CHARTER_CONFIG_INVALID`, "no content").
- No `charter.yaml` at all: `charter status` behaves as today (no refusal from this gate).
- A `charter:` pointer in `.kittify/config.yaml` naming a missing file (operator decision at the pre-merge squad fold): `charter status` refuses with `ACTIVE_CHARTER_CONFIG_INVALID` (it exited 0 before), with a remedy that fits a missing file (point the key at an existing file or remove it, or re-run `spec-kitty charter generate --from-interview`); status refusals never print "Nothing was written.". The shared gate is unchanged for synthesize/resynthesize.
- Malformed `.kittify/config.yaml` (non-mapping): `charter status` refuses with `ACTIVE_CHARTER_CONFIG_INVALID` (the charter soundness gate reads that file first). `CHARTER_CONFIG_SHAPE_INVALID` remains the mapping for the evidence reader's shape error should it be raised after the gate passes.
- A genuinely unexpected exception in `charter status`: still reported as unexpected, now with code `INTERNAL_ERROR` in the canonical envelope.
- A cascade target whose activation fails mid-walk: recorded as a failure in the report; the command still completes as today.
- `activate --json` combined with `--preset`: unchanged (existing preset JSON).
- An activation kind with no allow list (absent = all): `selected` reports it as unrestricted, distinguishable from an empty list.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Status refuses an unparseable charter with a typed code | As an operator, I want `charter status` on an unparseable `charter.yaml` to exit 1 with `ACTIVE_CHARTER_CONFIG_INVALID`, the file, the problem and the remedy, so that I can fix the file myself. | High | Open | [build] | no |
| FR-002 | Status refuses a non-mapping charter with the same code | As an operator, I want a list-rooted or empty `charter.yaml` refused the same way, never with the bundle-schema "run upgrade" message, so that I am sent to the right remedy. | High | Open | [build] | no |
| FR-003 | Status errors use the canonical JSON envelope | As tooling, I want every `charter status --json` error to be `{ok:false, error:{code,message}}` with a code, so that I parse one shape across charter commands. | High | Open | [build] | no — paired with FR-001's text-mode assertion on the same fixture |
| FR-004 | Local codes for the remaining refusals | As tooling, I want each refusal of status/activate/deactivate to carry a documented local code (ACTIVATION_KIND_UNKNOWN, CASCADE_SCOPE_INVALID, DEACTIVATION_REFUSED_REQUIRED, CHARTER_WRITE_ROOT_INVALID, ACTIVATION_FAILED, CHARTER_CONFIG_SHAPE_INVALID, CHARTER_STATUS_FAILED, INTERNAL_ERROR, ACTIVE_CHARTER_CONFIG_INVALID, RESYNTHESIS_FAILED; and ACTIVATION_STATE_UNREADABLE as the status `activation` block's error code), so that I can branch on the cause. | Medium | Open | [build] | no |
| FR-005 | `--json` on positional activate | As tooling, I want `charter activate KIND ID [--cascade] --json` to emit a versioned success payload of changed entries and warnings, so that I need not parse text. | High | Open | [build] | no |
| FR-006 | `--json` on deactivate | As tooling, I want `charter deactivate KIND ID [--cascade] --json` to emit the same payload shape, so that both verbs are symmetric. | High | Open | [build] | no |
| FR-007 | Cascade report | As tooling, I want the cascade report to list the source URN and every touched artifact with kind, stored spelling and URN, by outcome (cascaded, reinstated, failed, skipped by scope/deactivated/unreached/kind-filtered/shared/required), so that I see the complete effect. | High | Open | [build] | no |
| FR-008 | Refusal exit codes preserved | As tooling, I want each refusal's exit code under `--json` to equal its exit code without it, so that existing scripts keep working. | High | Open | [ratchet] | yes — paired with FR-004's code assertion on the same fixture |
| FR-009 | Activation block in status JSON | As tooling, I want `charter status --json` to carry an `activation` block (schema_version, source, path, selected, deactivated, mission_types, activated_kinds, required with in_force), so that I read effective activation state without parsing files. | High | Open | [build] | no |
| FR-010 | Required ids with in-force flag | As tooling, I want `required` to list each org-required id with whether it is in force, using the project's existing required-on-read rule, so that I can spot a required id an allow list keeps out. | Medium | Open | [build] | no |
| FR-011 | Human output unchanged | As an operator, I want the non-JSON output of these commands unchanged apart from the refusal and coded error lines, so that nothing I rely on moves. | High | Open | [ratchet] | yes — paired with the FR-005/FR-006 positive JSON runs on the same fixtures |
| FR-012 | Schemas documented | As a tool author, I want the activate/deactivate payload, the activation block and the local codes documented with their schema version, and pinned by snapshot tests, so that I can rely on them. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | JSON-only stdout | In `--json` mode, stdout of every covered invocation (success and refusal) is exactly one parseable JSON document: 0 non-JSON bytes, verified on every acceptance test. | Reliability | High | Open |
| NFR-002 | No added latency | Adding the activation block keeps `charter status --json` within the charter's < 2 s CLI budget on the test fixture project (measured wall time increase ≤ 200 ms). | Performance | Medium | Open |
| NFR-003 | Fail closed | Every refusal writes nothing: 0 changed bytes under `.kittify/` after a refused invocation, asserted in tests. | Reliability | High | Open |
| NFR-004 | Quality gates | Changed code passes ruff, ruff format, mypy --strict with 0 new suppressions; no function above complexity 15; diff coverage ≥ 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Contract values held | No contract refusal code (#6524), contract revision (#6521) or camelCase `ActivationConfig` field mapping (#6520) is minted or substituted; local codes are UPPER_SNAKE and documented as local. | Business | High | Open |
| C-002 | Issues stay open | #6525 and #6526 are referenced, not closed; only #6557 is closed by this mission. | Business | High | Open |
| C-003 | Read activation through its owning module | Activation state is read only through the activation ledger module / `charter.activation` seam (ADR 2026-10-19-1); no offering import from activation (ADR 2026-10-06-2). | Technical | High | Open |
| C-004 | One soundness authority | The status refusal reuses the existing charter soundness gate; no second charter-parse rule. | Technical | High | Open |
| C-005 | JSON registration inventory | Every `--json` registration changed or added is classified in the JSON contract enumeration gate. | Technical | High | Open |
| C-006 | Breaking status error envelope is announced | The move of `charter status` errors off the legacy envelope is recorded in the CHANGELOG `[Unreleased]` section. | Business | Medium | Open |

### Key Entities

- **Coded error**: a code (local UPPER_SNAKE) and a message, optionally with a payload (for example the packs that require an id).
- **Activation change report**: schema version, command, kind, id, changed entries, warnings, optional cascade report.
- **Cascade report**: source URN plus per-outcome lists of touched artifacts (kind, stored spelling, URN, and a reason or referencing URN where relevant).
- **Activation block**: schema version, source (ledger / legacy), path, selected, deactivated, mission types, activated kinds, required (id, kind, in force, requiring packs).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the #6557 reproduction cases (unparseable, list-rooted, empty charter) end in the typed refusal with a remedy, in both output modes; 0 show "Unexpected". — [build] · no-op passable: no
- **SC-002**: 100% of covered refusal paths of the three commands carry a documented code under `--json`. — [build] · no-op passable: no
- **SC-003**: Tooling can determine every artifact a cascade activation or deactivation touched, and its outcome, from the JSON alone (pinned by a snapshot or exact-equality assertion on a fixture with each outcome present). — [build] · no-op passable: no
- **SC-004**: The activation state reported by `charter status --json` matches the project's activation files on both a ledger and a legacy fixture. — [build] · no-op passable: no
- **SC-005**: Text output of the three commands on success paths is byte-identical before and after the change on the test fixtures. — [ratchet] · no-op passable: yes — paired with SC-002/SC-003 runs on the same fixtures

## Assumptions

- The corpus harness and other consumers of `charter status --json` errors can absorb the envelope change (operator decision `01M5ZCANVH16B2ANT1BJ115S8R`).
- `schema_version` "1.0.0" is local to these payloads and independent of `context_schema_version`.
- Org-required "in force" follows the existing required-on-read rule (an explicit allow list that leaves a required id out keeps it out of force; a deny never removes it).
