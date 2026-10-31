# Mission Specification: Charter consistency check honours the project layer

**Mission Branch**: `issue-6749-charter-consistency-project-layer`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6749 — "[bug] charter consistency-check omits project-layer activated artifacts", plus operator guidance: include the project layer through the same activation authority the other readers use, with no second membership rule.

## Problem

`charter consistency-check` decides whether an activated token is known through
`charter.activation.consistency_check._collect_all_offering_ids`, which calls
`ActiveCharterManager.list_available(..., org_root_chain=...)` **without** the
canonical project layer roots (`charter.activation.layer_roots.resolve_layer_roots`)
that every other reader passes. The catalog is therefore built-in + org only.

Grounding on `origin/main` `512567eee7`:

- The symptom the issue names for **directives and styleguides** was closed by
  #6433 (`a8dd1812a6`, landed after the `6a3e5cde` the issue cites): `_is_known`
  now resolves artifact kinds through the run's `IdentityIndex`, which already
  spans the built-in, org and **project** layers. A project-local
  `.kittify/charter-packs/directive/*.directive.yaml` (and styleguide), scaffolded
  with `charter new`, activated with `charter activate`, is coherent today.
- The **named root cause is still live** for the one kind whose membership still
  comes from that project-blind catalog: `mission-type`. A project-layer mission
  type at `.kittify/missions/mission_types/<id>.yaml` listed in
  `.kittify/charter/activation.yaml` is resolved by the runtime roster
  (`charter.activation.mission_type_profiles.resolve_layered_mission_types`) and is
  reported by `charter mission-type list --json` as
  `{"id": "<id>", "source_layer": "project", "activated": true}`, while
  `charter consistency-check --json` returns `coherent: false` with
  `"unknown_references": ["mission-type/<id>"]` and exit 1.

That is exactly the reported defect class: a charter that is inconsistent *in
force* is reported as either clean (artifact kinds, because a second membership
rule now hides the catalog's blindness) or as broken (mission-type, because the
catalog, not the readers, decides). The fix is to make the check's membership
answer come from the same layered authority the readers use — never a second
membership rule.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A project-layer activated mission type is coherent (Priority: P1)

An operator adds a mission type in the project layer, activates it, and runs
`charter consistency-check`. The check agrees with `charter mission-type list`
and the runtime roster: the activated type is known, the charter is coherent and
the command exits 0.

**Why this priority**: This is the live, user-facing false red the issue names.
It also breaks the "clean charter" contract in the opposite direction — the
check reports a defect in a charter that is consistent in force.

**Independent Test**: A git fixture whose project layer carries
`.kittify/missions/mission_types/proj-mission.yaml` (`extends: software-dev`)
and whose activation ledger lists it: `charter consistency-check --json` exits 0,
`coherent: true`, no `unknown_references` entry; the same fixture's
`charter mission-type list --json` reports it `activated` with
`source_layer: project` (the positive control proving the artifact is genuinely
in force and the probe can see it).

**Acceptance Scenarios**:

1. **Given** a project-layer mission type that the runtime roster resolves and the
   ledger activates, **When** `charter consistency-check` runs, **Then** the
   report is coherent, the token appears in no `unknown_references` entry, and the
   exit code is 0.
2. **Given** the same fixture, **When** `charter mission-type list --json` runs,
   **Then** the type is listed as activated from the project layer — the same
   fixture proves the artifact is visible to the readers the check must agree
   with.

---

### User Story 2 - The known-id catalog spans the project layer (Priority: P1)

Whoever reads the check's catalog — today the mission-type membership path,
tomorrow any consumer — sees the project layer, because the catalog call passes
the canonical project layer roots the way the other readers do.

**Why this priority**: The issue's prescribed repair. Without it the catalog is
structurally blind to the project layer even when a kind's membership is decided
there, and the next reader to rely on it re-introduces the same defect.

**Independent Test**: On a fixture whose project pack root holds a directive
file, the catalog function returns that directive's id for kind `directive`;
a companion assertion on the same fixture shows the identity index resolves the
same token (the authority the check actually uses), so the two answers cannot
drift.

**Acceptance Scenarios**:

1. **Given** a project-layer directive file under
   `.kittify/charter-packs/directive/`, **When** the known-id catalog is built,
   **Then** the directive's stem is present for kind `directive`.
2. **Given** the same fixture, **When** the same catalog entry is compared with
   the layers the readers scan, **Then** the catalog's ids for that kind are a
   superset of the project-layer ids the identity index knows (built-in and org
   coverage is preserved, not replaced).

---

### User Story 3 - Unknown and malformed artifacts still refuse (Priority: P1)

Activating something that no layer knows is still reported, and a malformed
project-layer artifact still fails the check closed instead of silently passing.

**Why this priority**: The fix must not trade a false red for a false green
(charter, Standing Order: no false green). Project-layer membership must be
granted by the authority, not by relaxing the check.

**Independent Test**: Two fixtures on the same construction path: one whose
ledger activates a mission type that exists in no layer (reported unknown,
incoherent), and one whose project-layer mission-type file is unparseable
(incoherent, with a `verification_errors` entry saying the check could not
verify — never a silent pass).

**Acceptance Scenarios**:

1. **Given** a ledger listing a mission type no layer provides, **When** the check
   runs, **Then** `mission-type/<id>` is reported in `unknown_references` and the
   report is incoherent.
2. **Given** an unreadable/malformed project-layer mission-type file, **When** the
   check runs, **Then** the report is incoherent and carries a
   `verification_errors` entry naming the unverifiable roster, and the process
   does not crash.

---

### Edge Cases

- **No project layer at all**: the catalog and the mission-type membership behave
  exactly as before (built-in + org), so projects without `.kittify/charter-packs/`
  see no change.
- **Org chain declared and a project type activated**: org ids stay known (no
  regression of #6338); project ids are added, not substituted.
- **Implicit all-active project (no activation keys)**: the check still skips the
  catalog entirely; the new roster read must not run when no mission-type
  activation list exists (NFR-003).
- **A malformed mission-type file in the org layer** behaves like the project
  case: fail closed with `verification_errors`.
- **`skill` kind**: the project layer cannot be scanned for skills by design
  (required-only, org-required floor) — the catalog keeps returning an empty set
  for it and the check keeps its current behaviour.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Project-layer mission type is known | As an operator, I want a mission type activated from the project layer to be accepted by the consistency check, so that a charter consistent in force is reported coherent. | High | Open | [build] | no — the token is `unknown` on the pre-fix path |
| FR-002 | Mission-type membership uses the layered roster | As a maintainer, I want the check's mission-type membership to come from the layered mission-type roster the runtime and the CLI readers use, so that there is one membership rule, not two. | High | Open | [build] | no — the built-in-only catalog answers differently on a project-layer type |
| FR-003 | Catalog passes the canonical project layer roots | As a maintainer, I want the known-id catalog to pass `resolve_layer_roots`' project root into `list_available`, so that no catalog consumer is structurally blind to the project layer. | High | Open | [build] | no — the pre-fix catalog has no project ids |
| FR-004 | Unknown mission types still refuse | As an operator, I want a ledger entry no layer knows to stay reported, so that the fix does not silence typos. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture construction |
| FR-005 | Malformed project mission-type fails closed | As an operator, I want an unparseable project-layer mission-type file reported as "could not verify", so that a corrupt roster never reads as a clean charter. | High | Open | [build] | no — pre-fix the file is invisible |
| FR-006 | CLI acceptance covers the production entry point | As a maintainer, I want the acceptance tests to drive `charter consistency-check` (the CLI command), not only an internal helper, so that the wiring cannot rot green. | Medium | Open | [build] | no — the assertions read the CLI's JSON/exit code |
| FR-007 | Directive/styleguide project-layer regression stays pinned | As a maintainer, I want the already-fixed project-layer directive/styleguide behaviour pinned at the CLI, so that the #6433 repair cannot silently regress while this catalog changes. | Medium | Open | [ratchet] | no — pinned through the CLI against the project layer |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new scan under implicit all-active | A check on a project with no activation keys performs zero catalog and zero roster reads (the existing "doctrine scan should not run without activation keys" invariant). | Performance | High | Open |
| NFR-002 | Roster read is lazy | The layered mission-type roster is read at most once per run and only when at least one `mission_type_activations` entry exists; a check on a project with no mission-type activation list performs zero roster reads. | Performance | High | Open |
| NFR-003 | Existing run budget holds | The existing `run_consistency_check` wall-clock budget (≤ 6.0 s on the shipped corpus, `tests/charter/test_consistency_check.py`) still passes with the roster read in place. | Performance | Medium | Open |
| NFR-004 | Fail-closed on unreadable roster | A roster read failure surfaces as a `verification_errors` entry and `coherent: false`; it never raises out of `run_consistency_check` and never yields a partial membership set. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One membership authority per kind | Artifact kinds resolve through the run's `IdentityIndex`; `mission-type` resolves through the layered mission-type roster. No third scanner, no re-derived directory walk, no installed hotpatch, no activation bypass. | Technical | High | Status |
| C-002 | Layer direction preserved | `charter.activation.consistency_check` may reach the roster only through the `charter.missions` facade; it must not import `specify_cli` (layer ratchet, `tests/architectural/test_layer_rules.py`). | Technical | High | Open |
| C-003 | No behaviour change for projects without a project layer | A project with no `.kittify/charter-packs/` and no project `missions/mission_types/` produces the same report as before the change. | Technical | High | Open |
| C-004 | Not the activation writer | `charter activate mission-type <project-type>`'s availability refusal is a separate surface with a different root cause; this mission changes the consistency check only and names that surface as a follow-up. | Business | Medium | Open |

### Key Entities

- **Known-id catalog** (`_collect_all_offering_ids`): per-kind frozenset of ids the
  check treats as known; built once per run on the explicit-activation path.
- **Layered mission-type roster** (`resolve_layered_mission_types`): built-in → org
  → project `mission_types/*.yaml` resolution, the same authority
  `charter mission-type list`, `charter activate`'s preflight and the runtime use.
- **Identity index** (`IdentityIndex`): the per-run layer-aware token index that
  already decides artifact-kind membership (built-in, org, project).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the project-layer mission-type fixture, `charter consistency-check --json` exits 0 with `coherent: true` and zero `unknown_references` entries (today: exit 1, one entry). — [build] · no-op passable: no
- **SC-002**: The known-id catalog contains every project-layer directive id the identity index knows, on a fixture with one project-layer directive (today: zero). — [build] · no-op passable: no
- **SC-003**: An unknown mission type and a malformed project-layer mission-type file both leave the report incoherent (unknown entry / verification error respectively). — [ratchet] · no-op passable: no
- **SC-004**: The full `tests/charter`, `tests/charter_offering` and
  `tests/specify_cli/cli/commands/charter` suites pass unchanged apart from the new
  tests, and `run_consistency_check` stays inside its 6.0 s budget. — [ratchet] · no-op passable: no
- **SC-005**: A project with no project layer and no project mission types reports
  exactly what it reported before the change (C-003 control). — [ratchet] · no-op passable: no

## Out of Scope

- `charter activate mission-type <project-layer-type>`'s "Unknown mission-type ID"
  availability refusal (`ActiveCharterManager.activate` → `list_available`, whose
  mission-type scan is deliberately flat/built-in-only). Same root cause, different
  surface, needs its own decision about the mission-type availability layout; filed
  as a follow-up issue and named in the PR's `## Deferred` section.
- The directive/styleguide instance of the reported symptom: already fixed by
  #6433; pinned here (FR-007) rather than re-implemented.
- Any installed runtime hotpatch, activation bypass, ledger migration or
  `charter.yaml` rewrite.
