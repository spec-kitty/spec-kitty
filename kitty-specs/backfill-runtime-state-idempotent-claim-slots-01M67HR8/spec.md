# Mission Specification: Backfill runtime state on a slug-identified legacy mission

**Mission Branch**: `issue-6689-backfill-claim-slots`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6689 — `upgrade --project` blocked: backfill-runtime-state fails closed on a legacy mission that already carries claim slots. Reproduce, then make the backfill idempotent for that shape without weakening the fail-closed posture for genuinely unknown state."

## Context and grounding

Issue #6689 (P1, 4.0.0 release scope, epic #3347) reports that `spec-kitty upgrade --project`
cannot complete on a project containing a legacy Mission whose WP frontmatter carries
pre-cutover claim slots (`agent`, `shell_pid`) while its event log has no initial
`planned -> claimed` transition. The cutover refuses to seed, leaves `status_phase`
untouched, and the whole upgrade exits 1 — one historical Mission blocks all 65.

Reproduced on `main` `512567eee7` with the reported Mission shape (a `meta.json` whose
`mission_id` is the Mission's own slug, a `tasks/WP01*.md` carrying `agent` + `shell_pid`
and no `shell_pid_created_at`, and a `status.events.jsonl` whose history begins at
`claimed -> in_progress`). The reproduction mints the exact event id the reporter quoted
(`0RWXZFHX7REDZWCZC43GQB3SPF`) and fails verify with
`WP01: claim mismatch (deterministic seed payload diverged)`.

**Root cause.** The seed row's envelope `mission_id` is not round-trip stable. The writer
(`_claim_carrier`) collapses `mission_id` to `None` whenever the resolved mission id equals
the Mission slug (the "no distinguishable id" convention), and `StatusEvent.to_dict()`
omits a `None` `mission_id`. On read-back, `status/store.py::_resolve_mission_id_from_dict`
re-resolves a row that carries no `mission_id` through the slug → `meta.json` lookup and
injects the slug-valued `mission_id`. The rebuilt expectation therefore carries `None`
while the row read back off disk carries the slug, forever. Every other seed field
matches, so the seed is sound; only the verifier's expectation and the reader's
re-derivation disagree — which is why no on-disk state the operator can produce satisfies
the check.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A slug-identified legacy Mission stops blocking the upgrade (Priority: P1)

An operator upgrading an old project runs `spec-kitty migrate backfill-runtime-state
--mission <slug>` (or `spec-kitty upgrade --project`). The Mission carries claim slots in
WP frontmatter and a `meta.json` whose `mission_id` is the Mission's own slug. The command
seeds the runtime state, verifies it, flips `status_phase`, and exits 0.

**Why this priority**: this is the reported defect. Until it is fixed, one legacy Mission
blocks the runtime-state cutover for the entire project, and there is no supported route to
retire or skip it.

**Independent Test**: build the reported Mission shape on disk in a temporary project and
run the real `spec-kitty migrate backfill-runtime-state --mission <slug>` entry point; it
must exit 0, the seeded claim row must carry the `meta.json`-declared `mission_id`, and a
second run must be a no-op that still verifies.

**Acceptance Scenarios**:

1. **Given** a legacy Mission whose `meta.json` `mission_id` equals its slug, whose WP01
   frontmatter carries `agent` and `shell_pid` with no `shell_pid_created_at`, and whose
   event log starts at `claimed -> in_progress`, **When** the operator runs
   `spec-kitty migrate backfill-runtime-state --mission <slug>`, **Then** the command exits
   0, the Mission flips to snapshot authority, and the seeded claim row's `mission_id`
   equals the value `meta.json` declares.
2. **Given** the same Mission after a successful run, **When** the operator runs the same
   command again, **Then** it appends nothing, still verifies, and exits 0.

---

### User Story 2 - Missions with no declared mission id keep their existing on-disk shape (Priority: P2)

An operator upgrades a project whose oldest Missions have a `meta.json` with no
`mission_id` at all. Those seeds must keep writing no `mission_id`, because no reader can
re-derive one for them.

**Why this priority**: the fix must not turn "no mission id" into "a fabricated mission id".
Writing the slug for a Mission that declares nothing would make the row carry an identity
the reader would never have produced.

**Independent Test**: build a Mission whose `meta.json` has no `mission_id`; the seeded
claim row's JSON carries no `mission_id` key and verify still passes.

**Acceptance Scenarios**:

1. **Given** a legacy Mission whose `meta.json` carries no `mission_id`, **When** the
   backfill seeds its claim state, **Then** the persisted row has no `mission_id` key and
   verify passes.

---

### User Story 3 - The fail-closed posture is preserved (Priority: P1)

A maintainer needs the cutover to keep refusing genuinely unknown or damaged state: a
tampered seed row, a stripped-before-verify frontmatter, a phantom WP, or a corpus whose
deterministic seed is missing.

**Why this priority**: the whole point of the verifier is that it aborts before reader
cutover. Making the reported shape pass must not turn any other mismatch into a warning.

**Independent Test**: on the same fixture that must now pass, corrupt one seed payload
value, then separately strip a frontmatter claim slot before verify; each must still abort
with the specific fail-closed error.

**Acceptance Scenarios**:

1. **Given** a Mission whose deterministic claim seed payload is corrupted, **When**
   verify runs, **Then** it reports a claim mismatch and the cutover aborts.
2. **Given** a Mission whose WP frontmatter claim slots were stripped before verify,
   **When** verify runs, **Then** it raises the strip-before-verify ordering error.
3. **Given** the same fixture with no corruption, **When** verify runs, **Then** it passes
   (positive control for scenarios 1 and 2).

### Edge Cases

- A `meta.json` whose `mission_id` is the Mission slug *and* whose event log has an
  initial `planned -> claimed` transition: the claim carrier may or may not be minted
  (the already-migrated suppression), but verify must pass either way.
- A Mission with a real ULID `mission_id`: unchanged on disk and in the seed id namespace.
- A two-leg (PRIMARY `read_dir` / COORD write leg) Mission: the seed id namespace and the
  envelope identity still come from the PRIMARY leg; the COORD leg's own `meta.json` is
  never consulted.
- A WP that carries claim slots but no honest timestamp to anchor them to: still skipped
  with a warning, never failed.
- A Mission whose event log already contains a pre-fix seed row (written without the
  `mission_id` key): the row reads back *as* the declared identity, so verify must accept
  it as sound rather than demand a rewrite.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Slug-identified Mission verifies after backfill | As an operator, I want the runtime-state cutover to accept a Mission whose `meta.json` `mission_id` equals its slug, so that one legacy Mission cannot block a project-wide upgrade. | High | Open | [build] | no |
| FR-002 | Seeded claim row carries the declared identity | As a maintainer, I want the minted claim row's envelope `mission_id` to equal what `meta.json` declares (and what the reader re-derives), so that the row read back off disk is byte-identical to the rebuilt expectation. | High | Open | [build] | no |
| FR-003 | Undeclared mission id stays undeclared | As a maintainer, I want a Mission whose `meta.json` declares no `mission_id` to keep seeding a row with no `mission_id` key, so that no identity is fabricated. | High | Open | [ratchet] | no — paired with FR-002's declared-identity case on one fixture family |
| FR-004 | Deterministic seed identity is unchanged | As a maintainer, I want seed `event_id`s and their namespace input unchanged for every existing corpus shape, so that already-seeded projects stay idempotent (no rewrite, no duplicate rows). | High | Open | [ratchet] | no |
| FR-005 | Converged re-run seeds nothing and still verifies | As an operator, I want a second `backfill-runtime-state` run on the reported Mission to append nothing and still verify, so that the repair is idempotent rather than self-healing into a second state. | High | Open | [build] | no |
| FR-006 | Tampered seed stays red | As a maintainer, I want a corrupted claim-seed payload to keep reporting a claim mismatch, so that the fix cannot buy the reported shape by widening the tamper tolerance. | High | Open | [ratchet] | no — companion positive control on the identical fixture |
| FR-007 | Strip-before-verify stays red | As a maintainer, I want a frontmatter stripped before verify to keep raising the ordering error, so that the pinned `backfill -> verify(pre-strip)` order is still enforced. | High | Open | [ratchet] | no — companion positive control on the identical fixture |
| FR-008 | CLI entry point exits 0 for the reported shape | As an operator, I want `spec-kitty migrate backfill-runtime-state --mission <slug>` to exit 0 and flip `status_phase` for the reported shape, so that the documented production entry point is what the fix is proven on. | High | Open | [build] | no |
| FR-009 | Pre-fix rows remain sound | As an operator whose project already carries a seed row written before this fix, I want verify to accept that row as sound instead of demanding a rewrite it cannot perform, so that the upgrade converges for already-half-migrated projects. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Determinism across runs | Two consecutive dry-runs over the same corpus produce byte-identical would-seed payloads; a live run followed by a second live run appends 0 events (measured: second run `seeded_count == 0`). | Reliability | High | Open |
| NFR-002 | No extra writes on a converged corpus | A live run over an already-converged corpus performs zero appends and zero `meta.json` rewrites (measured: file mtimes/bytes unchanged; `action == "skip"`). | Performance | High | Open |
| NFR-003 | Verifier still aborts on unknown state | Every fail-closed class (tampered payload, missing seed, phantom WP, strip-before-verify) still produces a non-`ok` result or the ordering error — measured as 100% of the sampled classes, no silent downgrade to a warning. | Reliability | High | Open |
| NFR-004 | No reader change | `src/specify_cli/status/store.py`'s event-read/identity-resolution behaviour is byte-unchanged by this Mission (measured: file not in the diff). | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One canonical carrier builder | The carrier's envelope shape has exactly one authority (`_claim_carrier`); the builder and the legacy-contract reference must not fork into two envelope constructors. | Technical | High | Open |
| C-002 | No identity semantics change | A slug-valued `mission_id` is not reinterpreted as absent, and `backfill-identity` is not changed to mint ULIDs for it — that is a separate decision on #6689's "possible directions". | Business | High | Open |
| C-003 | Fail-closed stays fail-closed | No gate, tolerance, skip, or xfail may be added to make the reported shape pass; the only allowed tolerance is the one that already exists (old `at`, pre-#2985 carrier, superseded subtask seed). | Technical | High | Open |
| C-004 | Scope boundary | Out of scope: `archive create` accepting accepted-but-not-merged Missions, the "WP file with no YAML frontmatter at all" read error, and any change to `upgrade`'s command surface. | Technical | High | Open |

### Key Entities

- **Seed carrier row**: the deterministic `planned -> claimed` `StatusEvent` whose
  `policy_metadata` sidecar carries the pre-cutover claim slots. Its `event_id` is
  namespaced on the Mission identity; its envelope `mission_id` is the identity the row
  declares.
- **Declared mission id**: the `mission_id` value `meta.json` carries (a ULID, a legacy
  slug, or nothing at all). Distinct from the *seed namespace* root, which falls back to
  the directory name when nothing is declared.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The reported Mission shape reaches `status_phase` snapshot authority through `spec-kitty migrate backfill-runtime-state --mission <slug>` with exit code 0 (was: exit 1, `status_phase` untouched). — [build] · no-op passable: no
- **SC-002**: A second consecutive run over that Mission appends 0 events and exits 0 (idempotent convergence). — [build] · no-op passable: no
- **SC-003**: Each of the three sampled fail-closed classes still aborts with its specific error on the same fixture that now passes. — [ratchet] · no-op passable: no — positive control is SC-001's fixture
- **SC-004**: Existing backfill/cutover test files covering the untouched shapes pass unchanged (no edits to their assertions required). — [ratchet] · no-op passable: no
