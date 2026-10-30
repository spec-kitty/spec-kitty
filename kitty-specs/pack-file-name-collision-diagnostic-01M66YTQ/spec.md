# Mission Specification: Pack file-name collision diagnostic

**Mission Branch**: `issue-6743-pack-file-name-collision-diagnostic`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6743 — "Report a file-name collision across pack layers (same file name, different declared ids) as a pack-content error in validate and doctor"

## Problem

Activation tokens resolve **file name first, across all layers** (#6459). When a
higher-layer pack ships `024-locality-of-change.directive.yaml` declaring
`ACME_024`, that file name now stands for `ACME_024` and no file name stands for
the built-in `DIRECTIVE_024`. The operator ruled this a pack-content error
(activate-output-and-identity mission, Decision `file_name_collision`), and every
activation **writer** refuses such an id with `ActivationIdCollisionError`
(#6527). Nothing warns the pack author *before* an operator hits that refusal:
today both `spec-kitty charter pack validate` and `spec-kitty doctor
charter-packs` are silent (confirmed on `main@512567ee`).

The same shape applies to non-directive kinds: an org tactic
`shared.tactic.yaml` declaring `org-a` plus a project tactic `shared.tactic.yaml`
declaring `proj-b` makes the file name `shared` silently stand for the project
id.

## Scope

In scope:

* a **detection query on `charter.activation.identity_index.IdentityIndex`** —
  the one component that already owns pack-layer identity (stem, declared id,
  layer, path) and already builds the per-kind tables. No second directory walk
  is introduced.
* the two operator surfaces the issue names: `spec-kitty charter pack validate`
  (the pack being validated against the built-in layer) and `spec-kitty doctor
  charter-packs` (across the configured chain: project, org packs, built-in).
* severity ruling: **error** in both surfaces, with **no opt-in** (see C-003).
* changelog + the docs that describe these two surfaces.

Out of scope:

* changing the writer refusal, the resolution rule, or any activation behaviour
  (`IdentityIndex.stored_spelling` / `collision_error` stay the runtime
  authority).
* changing the upgrade migrations' documented skip-and-report posture for a
  colliding id (`m_unify_charter_activation`, `m_4_0_0rc8_promote_interview_selections`).
  They remain the stated exception; this diagnostic is the pre-warning that
  makes the collision visible at authoring time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A pack author validates a pack and is told the file name is taken (Priority: P1)

A pack author writes an org directive file named
`024-locality-of-change.directive.yaml` that declares `ACME_024`, then runs
`spec-kitty charter pack validate <pack>`. Today the pack validates clean; the
collision only surfaces later, when an operator activates `DIRECTIVE_024` and a
writer refuses.

**Why this priority**: this is the issue's headline case (the exact example in
the issue body) and the cheapest place to catch it — the author still has the
file open.

**Independent Test**: a temp pack containing that file validates with exit code
1 and one error naming the file name, both layers and both declared ids;
renaming the file returns exit code 0.

**Acceptance Scenarios**:

1. **Given** a pack whose `<kind>/<file name><ext>` declares an id different
   from the built-in file of the same name, **When** the operator runs
   `spec-kitty charter pack validate <pack>`, **Then** the command exits 1 with a
   `file_name_collision` error naming the file name, the pack's file, the
   built-in file and the id each declares, and telling them to rename one file.
2. **Given** the same pack with the file renamed to a name no other layer uses,
   **When** the operator validates it, **Then** the collision error is gone and
   the pack validates as before (positive control on the same fixture).
3. **Given** a pack that reuses a file name *and keeps the same declared id*
   (a deliberate override), **When** the operator validates it, **Then** no
   `file_name_collision` is reported — the existing override advisories are
   unchanged.

### User Story 2 - An operator sees the collision across their configured chain (Priority: P2)

An operator configured an org pack and a project pack, one of which reuses the
other's file name for a different id. `spec-kitty doctor charter-packs` reports
it and exits non-zero, instead of printing "Collisions: none".

**Why this priority**: the chain case (org vs project) cannot be seen by
validating one pack in isolation; doctor is the only repo-wide surface, and a
silent "healthy" is exactly the false-green class the charter forbids.

**Independent Test**: a temp repo with an org pack and a project pack that share
a tactic file name but declare different ids reports one finding naming both
layers and both ids, and exits 1; the same fixture with distinct file names
exits with the unchanged baseline output.

**Acceptance Scenarios**:

1. **Given** a repo whose org pack and project pack ship `shared.tactic.yaml`
   declaring different ids, **When** the operator runs
   `spec-kitty doctor charter-packs`, **Then** the output names the file name,
   both layers, both declared ids and the rename advice, the JSON payload
   carries the structured finding, and the command exits 1.
2. **Given** the same chain with no collision, **When** the operator runs it,
   **Then** no collision finding is emitted and the baseline output is
   unchanged.

### User Story 3 - The diagnostic and the writer refusal agree (Priority: P3)

A maintainer changes the identity rules later. The validate/doctor diagnostic
and the writer refusal must keep naming the same file, the same layers and the
same ids, because both read the same index.

**Why this priority**: this is the maintainability property that keeps the
diagnostic from drifting into a second source of truth (the issue's "keep the
detection in the one place that already owns pack-layer identity").

**Independent Test**: on one fixture, the collision the diagnostic reports and
the declarations inside `ActivationIdCollisionError` are equal.

**Acceptance Scenarios**:

1. **Given** a colliding fixture, **When** the diagnostic reports the collision
   and `stored_spelling` is asked for the shadowed id, **Then** both list the
   same `(layer, declared id, path)` rows in precedence order.

### Edge Cases

* **Built-in names cannot be renamed.** When a built-in file takes part, the
  message names the non-built-in file(s) to rename, mirroring
  `ActivationIdCollisionError`.
* **Intra-pack duplicate file names are impossible** (one directory, one file
  name), so a finding always involves at least two layers or two subdirectories
  of one layer; the record keeps the paths so the operator can tell which.
* **Case-different file names are distinct file names** on the filesystem and
  resolve as distinct stems; they are not a collision.
* **A file that declares no id** falls back to its stem (`kind_vocabulary`
  behaviour), so it cannot collide with a same-named file; it is not reported.
* **An unreadable or malformed artifact file** yields no id and is already
  reported by the existing `schema_invalid` path; the collision leg neither
  duplicates that finding nor crashes.
* **Kinds without files** (`template`, and `anti_pattern`, which is a re-kinded
  graph node) are not scanned.
* **`validate` takes a bare directory** that may live outside any repo, so it
  compares the pack under validation with the built-in layer only; it must not
  depend on a repo's config chain. The chain case belongs to doctor.
* **Doctor must never crash** on a broken chain: a collector failure is recorded
  as an error finding, never an exception (existing doctor discipline).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Index query for file-name collisions | As a maintainer, I want `IdentityIndex` to answer "which file names stand for more than one declared id" from the tables it already builds, so that no second pack walk is introduced. | High | Open | [build] | no |
| FR-002 | Validate reports the collision | As a pack author, I want `charter pack validate` to report a file-name collision with the built-in layer as an error, so I fix it before an operator hits the writer refusal. | High | Open | [build] | no |
| FR-003 | Doctor reports the collision across the chain | As an operator, I want `doctor charter-packs` to report file-name collisions across the configured project/org/built-in chain as an error finding, so a colliding chain is never reported healthy. | High | Open | [build] | no |
| FR-004 | Message names file name, layers, ids and the rename advice | As an operator, I want one message shape that names the file name, the layers involved, each layer's declared id and which file to rename, so the fix is obvious. | High | Open | [build] | no |
| FR-005 | Diagnostic and writer refusal stay in agreement | As a maintainer, I want the diagnostic's declarations to equal the ones `ActivationIdCollisionError` reports for the same fixture, so the two surfaces cannot drift. | Medium | Open | [ratchet] | no — paired with FR-001 on one shared fixture |
| FR-006 | Non-colliding and same-id-override packs are unchanged | As a pack author, I want a deliberate same-id override and any pack with distinct file names to validate exactly as before, so the new error never fires on legitimate content. | High | Open | [ratchet] | yes — guarded by the positive control on the same fixture (FR-002 scenario 2/3) |
| FR-007 | Structured output carries the finding | As a tooling consumer, I want `validate --json` (existing `ValidationIssue.to_dict`) and `doctor charter-packs --json` to carry the collision in machine-readable form, so automation can gate on it. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One scan per kind, no re-walk in the query | The detection costs at most one `IdentityIndex` scan per kind per command: the query itself performs **zero** additional `glob`/`rglob` calls and **zero** additional YAML reads beyond that single scan (asserted with a spy that fails the test if the query re-scans). The measured before/after cost of `charter pack validate packs/internal` and `doctor charter-packs` on this repository is recorded in the PR. | Performance | High | Open |
| NFR-002 | Deterministic order | Findings are ordered by `(kind, file name)` and, within a finding, by layer precedence, so repeated runs on one tree are byte-identical. | Reliability | High | Open |
| NFR-003 | Doctor never crashes | Any exception in the new doctor leg is recorded as a finding, never raised: `doctor charter-packs` still exits with a rendered report on a broken chain. | Reliability | High | Open |
| NFR-004 | No measurable slowdown | Full `charter pack validate packs/internal` and `doctor charter-packs` stay within their current wall-clock envelope (fixture-neutral; measured before/after in the implement step, reported in the PR). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One identity authority | Detection lives in `charter/activation/identity_index.py`; neither the CLI nor the validator re-implements stem/id/layer logic. | Technical | High | Open |
| C-002 | Layering | `charter.offering` must not import `charter.activation`, so the validate leg is wired at `charter.activation.org_charter.validate_pack_with_org_charter` (the CLI's existing validation door), not inside `pack_validator`. | Technical | High | Open |
| C-003 | Severity ruling: error, no opt-in | A reused file name with a different declared id is an error in both surfaces. A deliberate override keeps the same id and is declared through DRG override edges, so it needs no collision opt-in and none is added. | Business | High | Open |
| C-004 | Validate's scope is pack + built-in | `validate <path>` compares the pack under validation with the built-in layer only; it never reads a repo config, so a pack validated outside a repo behaves identically. | Technical | High | Open |
| C-005 | No behaviour change to activation | No resolution, writer, migration or activation output changes; `stored_spelling` / `collision_error` keep their current behaviour and messages. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's own example (an org file named like built-in `DIRECTIVE_024` declaring `ACME_024`) is reported by `charter pack validate` with exit code 1 and by `doctor charter-packs` as an error finding, where today both are silent — [build] · no-op passable: no
- **SC-002**: A pack that reuses a file name with the *same* id, and a pack with distinct file names, produce zero `file_name_collision` findings (0 regressions across the existing `charter pack validate` and `doctor charter-packs` test files) — [ratchet] · no-op passable: yes — guarded by the same-fixture positive control
- **SC-003**: The diagnostic and `ActivationIdCollisionError` report identical declarations for the same fixture, asserted in one test — [ratchet] · no-op passable: no
- **SC-004**: `doctor charter-packs --json` and `charter pack validate --json` each carry the finding in their documented shapes, asserted by payload assertions, not string matching — [build] · no-op passable: no
