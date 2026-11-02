# Mission Specification: Op Records Stop Naming A Model, And Carry The Operator's Attribution

**Mission Branch**: `kitty/mission-op-record-model-and-coauthor-01M6EJV5`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #7013 — "Op records carry a model identifier, and the CLI's auto-commit of an Op record drops the operator's Co-Authored-By"

## Problem

Every `spec-kitty dispatch` opens an Op whose journal is `kitty-ops/<ulid>.jsonl`,
and `spec-kitty profile-invocation complete` (or the path that opens the Op)
auto-commits that journal onto the checked-out branch. Two binding repository
rules are broken by that path today:

1. **A model identifier is written into the committed record.** The v2 `started`
   event carries `model_id`, filled from the router's catalog-winning
   recommendation (`ProfileInvocationExecutor.invoke`). In this checkout, 1,014
   of the tracked records under `kitty-ops/` carry the key (`claude-opus-4-6`,
   `claude-sonnet-5`, `claude-haiku-4-5`). The rule is that no AI model
   identifier appears in any commit, PR or pushed artifact.
2. **The auto-commit has no attribution trailer.** The generated message is
   `op(<profile>): <action> [<id8>]` and nothing else, so the operator's
   configured `Co-Authored-By` never rides the commit. Runners strip the model
   key and rebuild the commit by hand on a fresh branch, because the permission
   classifier refuses an amend.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A committed Op record names no model (Priority: P1)

An operator (or auditor) reads any Op record written after this change and finds
no AI model identifier in it, whatever the routing recommendation was.

**Why this priority**: This is the rule violation the issue reports, and every
dispatched session reproduces it. Fixing it stops the repository accumulating
non-compliant history.

**Independent Test**: Open an Op through the production dispatch path with a
routing recommendation that wins on a catalog model, then read the written
`kitty-ops/<ulid>.jsonl`: it carries no model identifier at all.

**Acceptance Scenarios**:

1. **Given** a routing recommendation whose catalog candidate names a model,
   **When** `ProfileInvocationExecutor.invoke()` opens the Op, **Then** the
   written `started` event contains no `model_id` (and no other model name).
2. **Given** an Op record written before this change that carries `model_id`,
   **When** any reader parses it (`parse_op_event`, `invocations list`,
   `mission status ops`, the doctor sweep), **Then** it parses exactly as before
   and the file's bytes are unchanged.

---

### User Story 2 - The Op auto-commit carries the operator's trailer (Priority: P2)

An operator configures their attribution trailer once in `.kittify/config.yaml`;
every `op(...)` auto-commit then carries it without anyone rebuilding the commit.

**Why this priority**: The second half of the reported defect, and the manual
workaround it forces is the visible cost.

**Independent Test**: In a repository that tracks Op records, set
`commit.co_author`, close an Op, and read the commit message: it ends with
`Co-Authored-By: <configured identity>`.

**Acceptance Scenarios**:

1. **Given** `commit.co_author` is configured, **When** an agent close
   auto-commits the per-record file, **Then** the commit message carries
   `Co-Authored-By: <value>` as its final paragraph.
2. **Given** `commit.co_author` is configured, **When** the doctor sweep closes a
   stale Op and auto-commits the closure spine, **Then** that commit carries the
   same trailer.
3. **Given** `commit.co_author` is not configured, **When** an Op is closed,
   **Then** the commit message is exactly what it was before this change (no
   trailer, no failure) — a consumer repository is unaffected.

---

### User Story 3 - A caller may pass the trailer for one close (Priority: P3)

A caller whose operator identity is not in the project configuration passes the
trailer for a single close, and it overrides the configured value.

**Why this priority**: The issue offers this as the alternative to configuration;
supporting both keeps the configuration honest and gives harnesses an override.

**Independent Test**: Call the close path with an explicit trailer while a
different one is configured; the commit carries the explicit one only.

**Acceptance Scenarios**:

1. **Given** `commit.co_author` is configured, **When**
   `profile-invocation complete --co-author "<identity>"` closes the Op, **Then**
   the commit carries the explicit identity and not the configured one.
2. **Given** an explicit trailer that is empty or whitespace, **When** the close
   runs, **Then** it is refused as a usage error before anything is written.

---

### User Story 4 - A broken configuration is visible, never silent (Priority: P3)

An operator whose `commit.co_author` is malformed learns that the auto-commit was
refused and why, instead of getting an unattributed commit.

**Why this priority**: Attribution is the point; a silently dropped trailer
reproduces the bug in a harder-to-see form.

**Independent Test**: Set `commit.co_author: "not-an-identity"`, close an Op, and
read the close output plus `git log`: the record stays on disk uncommitted and
the reported reason names the configuration key.

**Acceptance Scenarios**:

1. **Given** a malformed `commit.co_author`, **When** an Op is closed, **Then**
   the completed event is durably written, the auto-commit is refused, and the
   refusal reason names `commit.co_author`.
2. **Given** the same malformed value, **When** the event is read back, **Then**
   the Op is closed and every reader behaves as before — a configuration defect
   never loses the trail.

---

### Edge Cases

- **Legacy records that already carry `model_id`.** They stay byte-frozen
  history: the archive-preservation gate forbids modifying a pre-existing
  `kitty-ops/<ulid>.jsonl`, so no scrub migration is possible. They keep parsing
  because the schema ignores unknown keys; nothing copies the key forward.
- **A claim that supplies `--model` with `--invocation-id`.** With no model on the
  Op there is nothing to correlate, so the assertion can no longer be honoured.
  The claim is refused with an actionable message and no binding is fabricated.
- **A trailer already present in a caller-supplied message.** The auto-commit
  builds its message itself; the trailer value is normalised so a value that
  already starts with `Co-Authored-By:` is not double-prefixed.
- **A repository whose primary branch tracks no Op records.** The #6410 skip
  rules run first and unchanged: no commit, therefore no trailer.
- **A closed Op.** `already_closed` still wins; no second commit, no second
  trailer.
- **An Op closed while its record root is a protected branch.** The auto-commit
  refusal is unchanged and is reported before attribution is considered.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | No model identifier in a written Op record | As an operator, I want a newly written `kitty-ops/<ulid>.jsonl` to contain no AI model identifier, so that the repository rule holds for every dispatch. | High | Open | [build] | no |
| FR-002 | Legacy records stay readable and byte-identical | As an auditor, I want records that already carry `model_id` to keep their bytes and parse unchanged, so that immutable history is never rewritten. | High | Open | [ratchet] | no — paired with the new-record absence probe on the same parser fixture |
| FR-003 | Claim cannot assert a model from the Op | As a maintainer, I want a `--model` assertion with `--invocation-id` refused with an actionable message, and the claim's model slot recorded as explicit-absent, so that no model is fabricated from a record that no longer carries one. | High | Open | [build] | no |
| FR-004 | Op auto-commit carries the configured trailer | As an operator, I want the `op(...)` commit to end with my configured `Co-Authored-By`, so that I never rebuild the commit by hand. | High | Open | [build] | no |
| FR-005 | The doctor-sweep spine commit carries it too | As an operator, I want the spine commit from a stale-Op sweep to carry the same trailer, so that every automated Op commit is attributed. | Medium | Open | [build] | no |
| FR-006 | A caller may pass the trailer | As a harness, I want to pass one close's trailer (`--co-author` / an executor argument) and have it override the configured value, so that attribution follows the real operator. | Medium | Open | [build] | no |
| FR-007 | Unconfigured repositories are unaffected | As a consumer, I want an Op close in a repository with no `commit.co_author` to commit exactly as before, so that this change is additive. | High | Open | [ratchet] | no — paired with FR-004's configured-value probe on the same fixture |
| FR-008 | A malformed configuration refuses visibly | As an operator, I want a malformed `commit.co_author` to refuse the auto-commit with a reason that names the key, so that I get no silent unattributed commit. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No model identifier in new Op history | A scan of every `kitty-ops/*.jsonl` line added after this change finds zero occurrences of `model_id`; a test asserts it over a freshly written record. | Compliance | High | Open |
| NFR-002 | Attribution costs one config read | Resolving the trailer reads `.kittify/config.yaml` at most once per auto-commit attempt and adds no subprocess; the existing skip probes are unchanged in number. | Performance | Medium | Open |
| NFR-003 | Zero drift in historical Op records | `git diff` over `kitty-ops/` for this mission's branch shows no modification of any pre-existing `<ULID>.jsonl` file. | Integrity | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | History is immutable | Historical Op records are append-only under the archive-preservation gate; this mission ships no scrub migration and says so in the docs and changelog. | Regulatory | High | Open |
| C-002 | The record stays v2-parseable | Removing one optional key must not change the required-field shape or the on-disk version; every v2 reader keeps working without a migration. | Technical | High | Open |
| C-003 | Additive configuration | `commit.co_author` is optional and read through the existing `.kittify/config.yaml` authority; no new config file, no new environment variable, no CLI surface removal. | Technical | Medium | Open |

### Key Entities

- **Op started event** (`OpStartedEvent`): the first JSONL line of
  `kitty-ops/<ulid>.jsonl`. After this mission it carries `actor` (the harness
  key) but no model identifier.
- **Operator attribution trailer**: `Co-Authored-By: <Name> <email>`, configured
  per repository under `commit.co_author`, or supplied per close.
- **Resolved binding**: the claim-time record of what actually ran. Its model
  slot becomes explicit-absent when the dispatch evidence no longer carries a
  model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of Op records written after the change contain no model identifier; a same-fixture probe proves the scan can see a legacy record that does. — [build] · no-op passable: no
- **SC-002**: 100% of `op(...)` auto-commits in a repository with `commit.co_author` configured carry the trailer, on both the per-record and spine paths. — [build] · no-op passable: no
- **SC-003**: 0 pre-existing `kitty-ops/<ulid>.jsonl` files change bytes, and all 1,014 records that carry `model_id` still parse through the public readers. — [ratchet] · no-op passable: no
- **SC-004**: A repository with no `commit.co_author` produces the same commit message it produced before the change. — [ratchet] · no-op passable: yes — paired with SC-002's configured-value assertion on the same fixture
