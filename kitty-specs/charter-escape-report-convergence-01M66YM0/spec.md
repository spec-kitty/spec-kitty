# Mission Specification: Charter escape-report convergence

**Mission Branch**: `kitty/mission-charter-escape-report-convergence-01M66YM0`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6733 — `charter status` and `charter org validate` report escaping org-pack paths like `doctor charter-packs`"

## Context and grounding

Issue #6733 is a follow-up to #6418 (mission `doctor-body-path-containment-01M5ZD3C`, landed
in #6756). #6418 taught `doctor charter-packs` to report two org-pack faults and to exit
non-zero on them:

- an authored `drg/fragment.yaml` node whose `body_path` is not contained in the pack root
  (`ORG_FRAGMENT_BODY_PATH_ESCAPE`);
- an org asset sidecar whose `path` is not contained in the pack's `assets/` root
  (`ORG_ASSET_PATH_ESCAPE`).

Two other surfaces report on the same pack and disagree with that verdict. Reproduced on
`main@512567ee` with one org pack (one node with `body_path: ../../../../etc/hostname` and one
`assets/team-logo.asset.yaml` with the same escaping `path`):

| Surface | escaping `body_path` | escaping asset `path` |
| --- | --- | --- |
| `doctor charter-packs --json` | reported (`org_drg.body_path_escapes`, `errors`, RC=1) | reported (`org_drg.asset_path_escapes`, `errors`, RC=1) |
| `charter status --json` | **silent** (`org_layer.errors: []`) | **silent** (`org_layer.errors: []`) |
| `charter org validate` | **silent** (exit 0 on that fault) | reported (`asset_path_escape`) |

Three commands that all claim to answer "is this org pack sound?" therefore give three
answers. This Mission closes that gap without inventing a fourth containment rule: every
surface derives its verdict from the same offering predicates (#6733's proposal).

**Term note.** "Escape" in this Mission means exactly what it means in #6418: a declared path
that is absolute, contains a `..` component, or resolves outside its root (a symlink), as
judged by the shared primitive `resolve_relative_path_within_root`. It does not mean "the
target file is missing": a contained path is sound whether or not its target exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "Charter status" tells me the truth about my org pack (Priority: P1)

A maintainer runs `charter status` (human or `--json`) to ask what governance is in force. When
an org pack points outside its own folder, the org-layer section must name that fault instead
of printing an empty `errors` array.

**Why this priority**: `charter status --json` is the machine-readable "what does this project
govern" surface. An empty `org_layer.errors` is read as a clean bill of health by agents and by
humans, and today it is handed out for exactly the packs `doctor charter-packs` fails.

**Independent Test**: build a project with one configured org pack whose fragment node has an
escaping `body_path`, run `charter status --json`, and confirm `org_layer.errors` names the
node. Then confirm a contained pack still reports no errors.

**Acceptance Scenarios**:

1. **Given** a configured org pack whose authored node `body_path` escapes the pack root, **When** I run `charter status --json`, **Then** `org_layer.errors` carries a finding that names the pack, the node and the escaping path, and the same text is printed by the human view.
2. **Given** a configured org pack whose asset sidecar `path` escapes the pack's `assets/` root, **When** I run `charter status --json`, **Then** `org_layer.errors` carries a finding naming the asset and the path.
3. **Given** a configured org pack whose paths are all contained, **When** I run `charter status --json`, **Then** `org_layer.errors` is empty (no false positive).
4. **Given** a pack whose merge is refused, **When** I run `charter status --json`, **Then** the escape findings are still reported (a refused merge must not hide them).
5. **Given** a containment check that cannot run, **When** I run `charter status --json`, **Then** `org_layer.errors` says the check could not run and is never read as "no escapes".

### User Story 2 - "Charter org validate" refuses an escaping fragment body (Priority: P1)

A pack author validates a pack before sharing it. When an authored fragment node's `body_path`
escapes the pack root, the validator must report a structured finding with a stable category
and a non-zero exit — the same class it already reports for an asset sidecar.

**Why this priority**: this is the surface an author runs *before* sharing a pack. It already
catches the asset half and misses the fragment half, so the author's own gate is the weakest
one.

**Independent Test**: run `charter org validate <pack>` on a pack with an escaping node
`body_path` and confirm a `body_path_escape` error, exit 1, and the same clean result for a
contained pack.

**Acceptance Scenarios**:

1. **Given** a pack whose authored node `body_path` escapes the pack root, **When** I run `charter org validate` on it, **Then** an error is reported with category `body_path_escape`, naming the node and the path, and the command exits non-zero.
2. **Given** a pack whose authored nodes are all contained, **When** I run `charter org validate` on it, **Then** no `body_path_escape` finding is produced.
3. **Given** a pack with both an escaping asset sidecar and an escaping node `body_path`, **When** I run `charter org validate`, **Then** both findings are reported (neither hides the other).

### User Story 3 - The rule survives the charter replacement (Priority: P2)

A charter-service contributor needs the containment rule as portable data, not as behaviour
buried in three command implementations, so a replacement offering inherits it.

**Why this priority**: the replacement inherits a rule only if the rule is stated somewhere a
replacement can be run against. Without it the three surfaces can drift apart again (which is
this very defect).

**Independent Test**: read the conformance case table, run it, and confirm a single table
asserts the same verdict on all three surfaces for each pack shape.

**Acceptance Scenarios**:

1. **Given** the conformance corpus, **When** it is run, **Then** each case asserts all three surfaces (doctor, status, validate) and fails if any of them disagrees.
2. **Given** a case for a contained pack, **When** it is run, **Then** all three surfaces read clean, so the table proves a positive control as well as a refusal.

### Edge Cases

- A node with an empty `body_path` is not a finding (nothing is declared, #6418's rule).
- A path that cannot be resolved at all (a NUL byte, a symlink loop) is a finding for that node or asset only and never aborts the scan.
- A discovered (validator-owned) node's `body_path` is not judged here; its own kind's validator owns it.
- A pack with no `drg/fragment.yaml` has no authored nodes to judge; the status and validate surfaces must stay silent rather than report an unpublished fault.
- The pack registry lookup for the effective pack root can fail; that is "the check could not run", reported as such, never as "no escapes".

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Status reports fragment body_path escapes | As a maintainer, I want `charter status --json` to name an org-pack node whose `body_path` escapes its pack root, so that I am never handed a clean bill for a pack `doctor charter-packs` rejects. | High | Open | [build] | no |
| FR-002 | Status reports asset sidecar escapes | As a maintainer, I want the same status channel to name an org asset sidecar whose `path` escapes its `assets/` root, so that the asset half is not silently missing either. | High | Open | [build] | no |
| FR-003 | Status reports before the merge, and reports a check that could not run | As a maintainer, I want the escape findings to survive a refused merge and to say "the check could not run" when it could not, so that a degraded read is never mistaken for a clean one. | High | Open | [build] | no |
| FR-004 | Validate emits a structured body_path finding | As a pack author, I want `charter org validate` to reject an authored fragment node whose `body_path` escapes the pack root, with a stable structured category, so that my own pre-share gate catches what doctor catches. | High | Open | [build] | no |
| FR-005 | One conformance corpus pins the shared verdict | As a charter-service contributor, I want one portable case table asserting doctor, status and validate agree per pack shape, so that a replacement offering inherits the rule and cannot drift from it. | Medium | Open | [build] | no |
| FR-006 | Contained paths stay clean on every surface | As an operator, I want a contained pack to read clean from all three surfaces, so that converging them does not turn honest configurations into findings. | High | Open | [ratchet] | yes — every case is paired with a contained-pack case on the same fixture builder, and the corpus asserts all three surfaces on it |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | One containment authority | All three surfaces derive the verdict from the shared offering predicates (`find_body_path_escapes`, `find_asset_path_escapes`, and the registry-aware wrappers in `charter.activation.drg_activation`); the change adds zero new containment implementations, measured by review of the diff and by the corpus going red when a predicate changes. | Maintainability | High | Open |
| NFR-002 | No target is opened or read | Reporting an escape reads only the fragment and sidecar metadata: zero file opens of the declared `body_path` or asset `path` targets, as #6418 established (a declared-but-missing contained target stays sound). | Security | High | Open |
| NFR-003 | Status JSON schema unchanged | `charter status --json` gains no new top-level or `org_layer` key; the findings ride the existing `org_layer.errors` string array, so an existing consumer parsing the current shape keeps working. | Compatibility | High | Open |
| NFR-004 | Diagnostic reads stay cheap | The added checks reuse the fragments each surface has already loaded: zero new graph loads, subprocesses or filesystem reads, and one additional linear pass per pack (verified by review of the diff and by the no-target-read test, not by a wall-clock threshold). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the shared primitive | Containment is judged by `resolve_relative_path_within_root` through the offering predicates only; no surface re-derives "is this path contained" from a second implementation. | Technical | High | Open |
| C-002 | Existing verdicts and vocabularies are unchanged | `doctor charter-packs` keeps its codes (`ORG_FRAGMENT_BODY_PATH_ESCAPE`, `ORG_ASSET_PATH_ESCAPE`) and its JSON keys, and `charter org validate` keeps `asset_path_escape` as the asset category; this Mission only adds. | Technical | High | Open |
| C-003 | No seam, layer or packaging change | `charter.offering.api`, the layer chain (`kernel <- charter <- specify_cli`) and `pyproject.toml` are untouched (ADR `2026-10-16-1`, Amendment 2026-10-19). | Technical | High | Open |
| C-004 | Stated scope only | The Mission fixes the two disagreeing surfaces and the rule's corpus case; it does not re-scope `doctor charter-packs` output or add a new command. | Business | High | Open |

### Key Entities

- **BodyPathEscape** (`charter.offering.drg.org_pack_loader`): one authored fragment node whose `body_path` escapes its pack root; carries `pack`, `node`, `kind`, `body_path`, `reason`, code `ORG_FRAGMENT_BODY_PATH_ESCAPE`.
- **AssetPathEscape** (`charter.offering.assets.repository`): one org asset sidecar whose `path` escapes its `assets/` root; carries `pack`, `asset`, `path`, `reason`, code `ORG_ASSET_PATH_ESCAPE`.
- **ValidationIssue** (`charter.offering.packs.pack_validator`): the validator's structured finding; the new fragment case carries category `body_path_escape`, alongside the existing `asset_path_escape`.
- **Conformance case**: one pack shape (declared paths per node/asset) plus the finding each reporting surface must produce for it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an org pack whose fragment node `body_path` escapes its pack root, 3 of 3 reporting surfaces (`doctor charter-packs`, `charter status`, `charter org validate`) name the finding; measured by the conformance corpus, which today shows 1 of 3. — [build] · no-op passable: no
- **SC-002**: For an org pack whose asset sidecar `path` escapes its `assets/` root, 3 of 3 surfaces name the finding; today 2 of 3. — [build] · no-op passable: no
- **SC-003**: For an org pack whose declared paths are all contained, 3 of 3 surfaces read clean, so the convergence produces zero false positives on the same fixture. — [ratchet] · no-op passable: yes — paired positive control on the same fixture builder, and the escaping cases above prove the probe can see a fault
- **SC-004**: A single portable corpus case table expresses all of the above as data a replacement offering can be run against, and it is green in CI. — [build] · no-op passable: no
