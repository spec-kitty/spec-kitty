# Mission Specification: One activation spelling at the effective-set seam

**Mission Branch**: `issue-6435-effective-set-one-spelling`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6435 — "Charter effective-set union mixes declared IDs and activation stems"

## Problem

An org-pack artifact may declare an `id:` that differs from its file stem
(`acme-skill-file.skill.yaml` declaring `id: acme-skill-id`). Activation lists
are stored in **one** spelling — the file stem (#6527) — and every writer is
supposed to converge on it through :class:`charter.activation.identity_index.IdentityIndex`.

The seam itself (`charter.activation.effective_set.resolve_effective_sets`) was
converged by `a8dd1812a6` (#6527 local slice): the service half of the union is
mapped to stems through `IdentityIndex` before it is unioned with the scanned
stems. Grounding on `main` @ 6f73b2a98e confirms no declared id survives in any
resolved set, for any kind, against the real built-in plus internal pack.

The mixing does still reproduce **through a consumer of the seam**.
`ActiveCharterManager.activate` materialises an absent activation key from
`PackContext.allow_for(...)` when the kind is required-only (`skill`), i.e. from
the raw `required_<kind>` **declared ids**, bypassing the identity authority that
every other writer uses. Reproduced on `main`:

```yaml
# org pack: skills/acme-skill-file.skill.yaml declares id: acme-skill-id
#           org-charter.yaml: required_skills: [acme-skill-id]
# $ spec-kitty charter activate skill other-skill-file
activated_skills: [acme-skill-id, other-skill-file]   # one declared id beside one stem
```

The runtime gate still admits the declared id, so nothing breaks visibly — but
the list now carries both spellings of the same artifact space, which is exactly
what #6435 asks the effective-set union *and its consumers* to stop doing. The
second half of the issue's ask is assurance: the union's spelling rule has two
copies (the resolved path and the `fallback_ids` path), and the fallback copy is
unguarded — removing its stem mapping leaves every existing test green, while
`fallback_ids` is what `activate` writes when the set cannot be resolved.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An activation list never stores a declared id beside a stem (Priority: P1)

An operator runs `charter activate` on a project whose org pack requires an
artifact whose declared id differs from its file stem. The activation list that
is written holds the file stem only, for every kind.

**Why this priority**: it is the user-visible defect the issue reports, on the
production entry point, and it is the only path where the mixing still happens.

**Independent Test**: build a project with an org pack whose `required_skills`
names an artifact whose file stem differs from its declared id, run
`charter activate skill <other-artifact>` on the CLI, and assert the written
`activated_skills` list holds stems only.

**Acceptance Scenarios**:

1. **Given** an org pack with `required_skills: [acme-skill-id]` declared by
   `acme-skill-file.skill.yaml`, and no `activated_skills` key, **When** the
   operator activates another skill, **Then** the written list contains
   `acme-skill-file` and never `acme-skill-id`.
2. **Given** the same project, **When** the operator activates the required
   artifact by its declared id, **Then** the written list holds its stem.
3. **Given** a required id whose file name another layer already uses for a
   different id, **When** any writer materialises the key, **Then** it still
   refuses with `ActivationIdCollisionError` and writes nothing.

### User Story 2 - The effective set has one spelling rule, not two copies (Priority: P2)

A maintainer changing how the union spells its ids changes one place, and both
the resolved and the fallback half follow.

**Why this priority**: the resolved half is already converged; the fallback half
carries a duplicate of the rule and no test depends on it, so a regression there
silently stores declared ids.

**Independent Test**: revert the fallback half's stem mapping and confirm the
effective-set suite goes red on a mixed org-pack fixture.

**Acceptance Scenarios**:

1. **Given** an unresolvable effective set and an org pack whose artifact's
   declared id differs from its stem, **When** the fallback is computed, **Then**
   `fallback_ids` holds the stem only.
2. **Given** that fallback, **When** `activate` seeds the absent key from it,
   **Then** the written list holds stems only.

### User Story 3 - Both spellings are pinned for every applicable kind and layer (Priority: P3)

A reviewer can see, per kind, that the union lists an id≠stem artifact once, by
its stem, whichever layer and whichever org pack declares it, and that both
spellings resolve to the same artifact.

**Why this priority**: assurance for the contract the issue's Expected section
names; it is what lets the remaining compensating conversions be judged.

**Independent Test**: run the effective-set suite over a two-pack fixture whose
id≠stem artifacts sit in both the lower- and the higher-precedence pack.

**Acceptance Scenarios**:

1. **Given** two declared org packs, each holding an id≠stem artifact, **When**
   the union is resolved, **Then** each artifact is listed once, by its stem, and
   its declared id appears nowhere in the set.
2. **Given** the same fixture, **When** a consumer is asked for the artifact by
   its declared id or by its stem, **Then** both spellings resolve to the same
   stored stem.

### Edge Cases

- An id the identity index does not know (a service-only artifact) stays in the
  set as given, so it cannot vanish; this is existing, documented behaviour and
  is not changed here.
- A required id that resolves in no readable layer is kept as written (existing
  `org_required_stems` contract) — no new refusal is introduced.
- A `mission-type` and `skill` key still never resolve through the seam
  (ledger / required-only), unchanged.
- An artifact whose file name is shared by another layer's file with a different
  id remains a pack-content collision, refused by every writer (Decision
  `file_name_collision`); no new policy is invented.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Required-floor materialisation stores stems | As an operator, I want `activate` on an absent required-only key to write the org-required artifacts by their file stem, so that the list holds one spelling. | High | Open | [build] | no |
| FR-002 | One union spelling rule | As a maintainer, I want the seam's resolved and fallback halves to apply the same identity-authority mapping, so that the rule cannot drift between them. | Medium | Open | [build] | no |
| FR-003 | Union pinned per kind and layer | As a reviewer, I want the mixed two-org-pack union pinned for every applicable kind, in both pack orders, with both spellings resolving to one stem. | Medium | Open | [ratchet] | no — the fallback half is unguarded on `main` (proved by mutation) |
| FR-004 | Consumers keep one spelling | As a reviewer, I want the `activate` consumer path pinned end-to-end on the production CLI, for the required-only and the all-kinds branches. | Medium | Open | [ratchet] | no — paired with the reproduced `activated_skills` defect of FR-001 |
| FR-005 | Collision refusal preserved | As a maintainer, I want a colliding org-required id to keep refusing through the same `ActivationIdCollisionError`, so that FR-001 cannot weaken the writer contract. | High | Open | [ratchet] | no — same-fixture positive control: the non-colliding required id is materialised |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra scans | The required-floor fix adds no artifact scan: the existing `org_required_stems` call that already ran for the collision refusal is reused, so an `activate` performs at most the index builds it performs on `main`. | Performance | Medium | Open |
| NFR-002 | Bounded test runtime | The new tests must finish within 60 s each on the CI shard they join and add no more than ~60 s to `tests/charter/activation/test_effective_set.py`. | Performance | Medium | Open |
| NFR-003 | Fail closed unchanged | An unresolvable set stays `resolved=False` with a reason, never a partial or silently re-spelled set; the number of tests asserting fail-closed behaviour does not decrease. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No spelling-contract change | Activation id spelling stays owned by #6518/#6527; this Mission converges call sites on stems and changes no stored-format contract. | Technical | High | Open |
| C-002 | No ambiguity-policy change | Unknown-token and ambiguity policy stays with #6433; this Mission invents no new refusal or tolerance rule. | Business | High | Open |
| C-003 | Use the existing scanner and authority | Do not reimplement `ActiveCharterManager.list_available_detailed` and do not add a second identity authority; route through `IdentityIndex` / `org_required_stems`. | Technical | High | Open |
| C-004 | No gate weakening | No test is skipped, xfailed or deleted to pass; no CI gate is edited. | Regulatory | High | Open |

### Key Entities

- **Effective set**: the ids in force for an activation key while that key is
  absent, in activation-stem spelling, per kind.
- **Activation stem**: the artifact's file name, the one spelling an activation
  list stores.
- **Declared id**: the artifact's `id:` field, accepted as input, never stored
  when a stem exists.
- **Required floor**: the org packs' `required_<kind>` ids for a required-only
  kind, in force while the key is absent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a project whose org pack requires an id≠stem artifact, `charter activate` on an absent required-only key writes each in-force artifact once, by its stem, and 0 declared ids — [build] · no-op passable: no
- **SC-002**: `fallback_ids` for a mixed org-pack fixture contains 0 declared ids; reverting the fallback stem mapping turns the effective-set suite red — [ratchet] · no-op passable: no
- **SC-003**: Every applicable activatable kind with an id≠stem artifact in a declared org pack appears exactly once in its effective set, by stem — [ratchet] · no-op passable: no
- **SC-004**: Both spellings (stem and declared id) of the same artifact resolve to the same stored stem through the production `charter activate` entry point — [ratchet] · no-op passable: no

## Issue matrix

| Issue | Role | Claim | Verdict |
|-------|------|-------|---------|
| #6435 | source | claimed, assigned to Ivan-Melck | in-mission |

## Intent & Discovery (non-interactive run)

**Primary actor**: an operator running `spec-kitty charter activate <kind> <id>`
on a project whose org pack requires an artifact whose declared id differs from
its file stem.

**Trigger**: the kind's activation key is absent, so `activate` materialises what
is already in force (and, for an all-kinds key, the effective set).

**Desired outcome**: the written `activated_<kind>` list holds exactly one
spelling per artifact — the file stem — for every activatable kind, whether the
entry came from the scanned offering, from the service mapping, from the org
`required_<kind>` floor, or from the tolerant fallback.

**Rules that must always hold**: a declared id is accepted on input and stored as
the stem; a declared id whose file name another layer uses for a different id is
still refused (`ActivationIdCollisionError`); an unresolvable set still reports
`resolved=False` with a reason and is never narrowed silently.

**Assumptions**: the operator's mission instruction (converge on the existing
identity authority, pin both spellings, change no contract and no ambiguity
policy) is the confirmed intent; the discovery interview is recorded as deferred
rather than asked, because this run is non-interactive (governed batch agent).

**Deferred decisions**: none that block; the two open questions in
`research.md` are answered there.
