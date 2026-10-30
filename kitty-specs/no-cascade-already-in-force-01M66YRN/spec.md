# Mission Specification: `charter activate` names referenced artifacts that are already in force

**Mission Branch**: `issue-6742-no-cascade-already-in-force`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6742 — charter activate without --cascade warns 'was not activated' for referenced artifacts that are already in force"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The no-cascade report distinguishes "already in force" from "not activated" (Priority: P1)

An operator activates a doctrine artifact (or a mission type) on a project whose
activation keys are absent, so every built-in artifact of an "all" kind is in force. They
do not pass `--cascade`, because they only meant to activate one thing. Today the command
prints one `Warning: referenced <kind>/<id> was not activated (no --cascade).` per
referenced artifact — for an artifact that is already in force — and a hint telling them
to re-run with `--cascade`. That reads like a failed activation and sends them chasing a
problem that does not exist.

**Why this priority**: it is the whole issue; the command's own success path currently
reports the opposite of the truth, at ~150 lines per run.

**Independent Test**: run `charter activate --no-compile mission-type software-dev` on a
project whose activation keys are all absent; the output names the referenced artifacts as
already in force and no `Warning: referenced … was not activated` line appears.

**Acceptance Scenarios**:

1. **Given** a project with no `activated_directives` key, **When** the operator runs
   `charter activate --no-compile mission-type software-dev`, **Then** each referenced
   directive is reported with a line that says it is already in force and does not tell
   the operator it "was not activated".
2. **Given** a project with an explicit `activated_directives` list that does not contain
   the referenced directive, **When** the operator activates a directive without
   `--cascade`, **Then** the `Warning: referenced directive/<id> was not activated (no
   --cascade).` line is still printed, unchanged.
3. **Given** a project where the referenced artifact is deactivated, **When** the operator
   activates a directive without `--cascade`, **Then** the existing
   `Warning: referenced <kind>/<id> is deactivated and was not activated.` line is still
   printed, unchanged.
4. **Given** a project whose `activated_procedures` list already contains the referenced
   procedure, **When** the operator activates a directive without `--cascade`, **Then** the
   procedure is reported as already in force, and the warning is not printed for it.

---

### User Story 2 - The `--json` change report keeps the same distinction (Priority: P2)

A tool consuming `charter activate … --json` cannot tell an artifact that is already in
force from one the run left out, because both land in `referenced_not_cascaded`. The
report must expose the already-in-force artifacts separately, so a key that is documented
as "not cascaded" no longer contains artifacts that were in force all along.

**Why this priority**: the JSON is the machine contract of the same report; fixing the text
only would leave the two surfaces disagreeing.

**Independent Test**: `charter activate … --json` on the US1 fixture prints
`referenced_already_in_force` with the referenced artifacts and an empty `referenced_not_cascaded`.

**Acceptance Scenarios**:

1. **Given** a project with no `activated_<kind>` keys, **When** the operator runs
   `charter activate … --json` without `--cascade`, **Then** `referenced_already_in_force`
   lists the referenced artifacts (kind, id, urn) and `referenced_not_cascaded` does not.
2. **Given** a project whose explicit list omits the referenced artifact, **When** the
   operator runs the same command with `--json`, **Then** that artifact is in
   `referenced_not_cascaded` and not in `referenced_already_in_force`.
3. **Given** any run with `--cascade`, **When** the operator asks for `--json`, **Then**
   both lists are empty, exactly as `referenced_not_cascaded` is today.

---

### User Story 3 - The recovery hint only appears when there is something to recover (Priority: P3)

The hint "Re-run with `--cascade <scope>` … to activate the referenced artifacts" is
printed underneath the no-cascade report. When every referenced artifact is already in
force there is nothing for `--cascade` to activate, so the hint is noise.

**Why this priority**: it is a consequence of US1; on its own it is cosmetic, but leaving
it would advertise an action that changes nothing.

**Independent Test**: on the US1 fixture the output contains no `Hint: Re-run with
--cascade` line; on the US1-scenario-2 fixture it still does.

**Acceptance Scenarios**:

1. **Given** every referenced artifact is already in force, **When** the operator runs
   `charter activate` without `--cascade`, **Then** no `--cascade` recovery hint is printed.
2. **Given** at least one referenced artifact is not in force, **When** the operator runs
   the same command, **Then** the hint is printed as before.

---

### Edge Cases

- **`--only` narrows the list.** `activate directive <id> --only` rewrites
  `activated_directives` to the selection, so a referenced directive is genuinely not in
  force afterwards and keeps its warning. The verdict is taken from the state the command
  leaves behind, not the state it found.
- **A referenced artifact the kind's explicit list already names** is in force and is
  reported as already in force, not as "not activated".
- **An org-required artifact whose kind's key is absent** (`skill` is the only such kind)
  is in force when the org packs require it, and is reported as already in force; a
  non-required skill of an absent list is not in force and keeps its warning.
- **A deactivated artifact** stays a warning even when its kind has no explicit list: the
  deny list wins over "effective when absent".
- **A referenced artifact of a kind that cannot be activated** (`asset`, `template`) keeps
  its separate `Not cascaded: … (kind not charter-activatable)` line; it is neither in
  force nor a candidate.
- **Long reports stay long**: the issue's fixture legitimately names ~150 referenced
  artifacts. The change is about what each line says, not about collapsing them.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Already-in-force references are reported as such | As an operator, I want a referenced artifact that is in force to be reported as in force so that the report does not claim my activation failed. | High | Open | [build] | no |
| FR-002 | Only genuinely-not-in-force references carry the warning | As an operator, I want the `Warning: referenced … was not activated (no --cascade).` line only for artifacts that are not in force so that warnings mean something. | High | Open | [build] | no |
| FR-003 | The in-force verdict follows the activation rules | As a maintainer, I want the verdict read from the project's own membership rule (absent list, explicit list, org-required floor, deny list) so that the report cannot drift from what the runtime enforces. | High | Open | [build] | no |
| FR-004 | The verdict is taken after the write | As an operator using `--only`, I want the report to describe the project my command leaves behind so that a narrowed list still reports what it dropped. | High | Open | [build] | no |
| FR-005 | `--json` separates the two groups | As a tool author, I want the already-in-force artifacts in their own list so that `referenced_not_cascaded` keeps its documented meaning. | Medium | Open | [build] | no |
| FR-006 | The recovery hint needs something to recover | As an operator, I want no `--cascade` hint when every referenced artifact is already in force so that I am not sent to a no-op command. | Medium | Open | [build] | no |
| FR-007 | Deactivated references keep their warning | As an operator, I want a deactivated reference to stay a warning so that the exclusion is still surfaced. | Medium | Open | [build] | no |
| FR-008 | The documented text and JSON contract are updated | As a reader of the CLI reference, I want the no-cascade section and the change-report table to describe the new line and field so that the docs match the command. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One membership authority | The in-force verdict is obtained from the existing `PackContext.admits` membership accessor plus the existing three-state activation-ledger read; no second rule for "what is in force" is introduced (0 new membership predicates). | Maintainability | High | Open |
| NFR-002 | No behaviour change to activation | With the same project state and arguments, the set of artifacts the command activates, the files it writes and its exit code are identical before and after: only the report changes (0 activated/deactivated ids differ across the fixture matrix). | Reliability | High | Open |
| NFR-003 | Line ordering preserved | The relative order of the remaining lines (activated lines, tension warnings, deactivated warnings, hint, kind-filtered lines, notices) is unchanged; only the new notes are added, in the position the removed warnings occupied. | Compatibility | Medium | Open |
| NFR-004 | Report cost | The extra work is one `PackContext.from_config` read and one ledger read per invocation; no additional DRG walk and no additional artifact resolution pass (0 extra `ResolutionPass` instances). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Activate-only surface | `render_no_cascade_warning` is reached only from the no-`--cascade` branch of `charter activate`; `charter deactivate` already reports in-force children as `still-active`/`skipped (required by …)` and is out of scope. | Technical | High | Open |
| C-002 | No contract renegotiation | `spec-kitty-charter`'s activation contract is untouched; this is the local CLI change report (`schema_version` 1.0.0) and its `referenced_*` keys, one key added. | Technical | High | Open |
| C-003 | Follow the issue's wording | The reported case is worded as the issue asks: already in force, with the reason, and "not added by this command" instead of "was not activated". | Business | Medium | Open |

### Key Entities

- **Referenced artifact**: an artifact node reached from the activated source through the
  DRG reference relations; carries an operator kind token, a config-stem id and a DRG URN.
- **No-cascade report**: the value the text renderer and the JSON serializer both read;
  its buckets are skipped, deactivated, kind-filtered and (new) already-in-force.
- **In-force verdict**: whether the project's activation state admits the referenced
  artifact, as the activation layer defines it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a project with no activation keys, `charter activate --no-compile mission-type software-dev` prints zero `was not activated (no --cascade)` lines for artifacts that are in force, and one already-in-force line per referenced artifact — [build] · no-op passable: no
- **SC-002**: On a project whose explicit list omits the referenced artifact, the warning count for that artifact is exactly 1 (unchanged from `main`) — [ratchet] · no-op passable: no
- **SC-003**: `charter activate … --json` on the same two fixtures partitions the referenced artifacts between `referenced_already_in_force` and `referenced_not_cascaded` with zero artifacts counted in both — [build] · no-op passable: no
- **SC-004**: The activation state written by the command is byte-identical to `main`'s for every fixture in the covered matrix — [ratchet] · no-op passable: no
