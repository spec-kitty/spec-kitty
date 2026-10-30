# Mission Specification: An org DRG fragment carries its effective pack root

**Mission Branch**: `kitty/mission-org-drg-fragment-pack-root-01M66YJG`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "Org DRG fragments carry their effective pack root; drop the registry re-read in the doctor's containment wrappers (#6731). Follow-up to #6418."

## Intent Summary

`load_org_pack` already receives each pack's **effective** root (`subdir` applied) and stamps it
into `OrgDRGFragment.source_ref` as a display string. The #6418 containment wrappers
(`find_org_body_path_escapes`, `find_org_asset_path_escapes` in
`charter.activation.drg_activation`) then re-read the pack registry through
`_org_pack_roots_by_name` to rediscover that same root. One fact — pack → effective root — has two
sources, and the second one can disagree with the first if the config changes between the two
reads.

- **Primary actor**: the operator running `spec-kitty doctor charter-packs` on a project whose
  `.kittify/config.yaml` declares org packs.
- **Trigger**: the doctor's org-layer containment half judges each authored fragment node's
  `body_path` and each org asset sidecar's `path`.
- **Outcome**: the root a containment verdict is judged against is the root the loader used, carried
  on the fragment; the registry is read once per doctor run, inside `load_org_drg`.
- **Rule that must always hold**: the doctor's refusals are unchanged. Same findings, same
  messages, same JSON keys, same exit codes — this Mission removes a second authority, it does not
  change what an operator sees.

Scope limit (operator guidance in the issue): carry the root, collapse the predicates onto it,
delete the activation wrappers, and route both doctor halves through the `charter.drg` facade. Do
not restructure pack loading, merge, or validation, and do not touch pack content under
`packs/built-in/` or `packs/internal/`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One pack→root fact decides the containment verdict (Priority: P1)

An operator runs `spec-kitty doctor charter-packs` against a project with org packs configured,
including a pack with a `subdir`. Every `body_path` and asset `path` verdict is judged against the
effective root that the loader used to read that pack, not against a second registry read that
could disagree with it.

**Why this priority**: this is the whole change. Two authorities for one fact is the defect;
collapsing them is the fix. Without it, a config change between the two reads can make the doctor
judge a pack against a root it was not loaded from.

**Independent Test**: a counting test on the production entry point shows exactly one
`load_pack_registry` read for one doctor run, and a subdir pack with an escaping `body_path` still
exits 1 with the same message.

**Acceptance Scenarios**:

1. **Given** org packs configured, **When** `_collect_org_layer_data` runs for that repo, **Then**
   `charter.offering.drg.org_pack_config.load_pack_registry` is called exactly once (the read
   inside `load_org_drg`), and the same holds for `_render_org_layer_section`.
2. **Given** a pack configured with `subdir`, **When** an authored node's `body_path` resolves
   inside the checkout but outside the effective root, **Then** the escape is still reported and
   the doctor still exits 1.
3. **Given** a pack whose asset sidecar leaves `assets/`, **When** the doctor judges it, **Then**
   the finding, its message and exit code are the ones #6418 pinned.

### User Story 2 - A fragment that cannot supply its root fails loudly, never silently passes (Priority: P2)

A caller hands the containment predicate a fragment that does not carry a root — one rebuilt from a
JSON dump, or constructed by hand instead of loaded. The predicate refuses to judge containment
against nothing, and the doctor reports the check as "not checked" rather than "none".

**Why this priority**: carrying the root on the fragment replaces a lookup that always produced
*some* root. The new failure mode needs a defined, loud behaviour, or a lost private attribute would
read as "no escapes".

**Independent Test**: a fragment rebuilt from `model_dump()`/`model_validate()` triggers the typed
error, and the doctor's two halves render `not checked` for it.

**Acceptance Scenarios**:

1. **Given** a fragment whose pack root was never stamped (a dump/reload round-trip), **When**
   `find_body_path_escapes` or `find_asset_path_escapes` reads it, **Then** a typed error names the
   pack and says the root is unavailable, instead of judging against a default path.
2. **Given** that same fragment, **When** `doctor charter-packs` runs, **Then** the human output
   says the check was not checked and the JSON path records the failure in `errors`.

### Edge Cases

- A fragment loaded by `load_org_pack` is copied with `model_copy`; the carried root survives the
  copy (pydantic private attributes are copied) while a dump/reload round-trip drops it.
- The pack root is a `PrivateAttr`, so it must not appear in `model_dump()`, `model_dump_json()`,
  or the fragment's schema — anything that serialises fragments (`--json` doctor output, tests that
  compare fragments) must be byte-identical to today.
- A pack is registered but the fragment load fails: the doctor's existing early returns stay as
  they are, with `body_path_escapes` and `asset_path_escapes` present and empty.
- Two packs declare the same asset id: each is still judged against its own carried root, so a
  shadowed id is attributed to the right pack.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Fragment carries its effective root | As the loader, I want the fragment to carry the effective pack root I loaded it from so that downstream checks need no second lookup. | High | Open | [build] | no |
| FR-002 | Root is not serialized | As an API consumer, I want the carried root kept out of the fragment's serialized and schema surface so that JSON output and fragment contracts are unchanged. | High | Open | [ratchet] | no |
| FR-003 | Offering predicates take only a fragment | As a containment caller, I want `find_body_path_escapes` and `find_asset_path_escapes` to take one fragment and read its name and root from it so that the pack→root pairing cannot be supplied from a second source. | High | Open | [build] | no |
| FR-004 | Activation wrappers deleted | As a maintainer, I want `find_org_body_path_escapes`, `find_org_asset_path_escapes` and `_org_pack_roots_by_name` gone from `charter.activation.drg_activation` so that the registry re-read has no home. | High | Open | [build] | no |
| FR-005 | Doctor reaches the predicates through the `charter.drg` facade | As the doctor's two halves (JSON collect and human render), I want to call the offering predicates through `charter.drg` so that neither half adds a `charter.activation` internal reach of its own. | High | Open | [build] | no |
| FR-006 | One registry read per doctor run | As an operator, I want the containment flow to read the pack registry exactly once, inside `load_org_drg`, so that there is one pack→root authority. | High | Open | [build] | no |
| FR-007 | Missing root fails loudly | As a caller with a fragment that carries no root, I want a typed refusal naming the pack so that containment is never judged against a default or a guess. | Medium | Open | [build] | no |
| FR-008 | Doctor refusals unchanged | As an operator, I want every containment finding, message, JSON key and exit code to stay exactly as #6418 shipped it so that this refactor changes nothing I see. | High | Open | [ratchet] | yes — the escaping fixtures are the positive control that the refusal probe can still see a refusal |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Registry reads are bounded | For one `_collect_org_layer_data` run and one `_render_org_layer_section` run over a repo with N ≥ 1 configured org packs, `load_pack_registry` is called exactly once (3 before the change). | Reliability | High | Open |
| NFR-002 | No new seam bypass | `tests/architectural/test_runtime_charter_activation_boundary.py` passes with `tests/architectural/charter_activation_boundary_baseline.yaml` unchanged: no new `(file, module)` pair is added, and no row is drained, because both doctor files keep reaching `charter.activation.drg_activation` for `load_org_drg`. | Maintainability | High | Open |
| NFR-003 | No serialized-surface drift | The key set of `OrgDRGFragment.model_dump()` and the fragment JSON schema after the change are identical to before it (measured on the example-org fixture). | Compatibility | High | Open |
| NFR-004 | Changed lines are covered | CI's diff-cover gate reports at least 90% coverage on the changed lines; the touched test modules stay in the `unit`/`fast` tier and run in under 60 s together. | Testability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Behaviour-preserving refactor | No operator-visible output changes: same findings, messages, JSON keys and exit codes. A user-facing changelog entry is added only if the diff turns out to change what an operator sees. | Business | High | Open |
| C-002 | Offering layering preserved | The asset containment predicate may not import upward into `charter`/`specify_cli`; whatever type contract it takes must respect `charter.offering` internal layering (see the module docstring of `charter.offering.drg.org_pack_loader`). | Technical | High | Open |
| C-003 | No pack-content edits | `packs/built-in/` and `packs/internal/` are fetched trees; this Mission edits code and tests only and triggers no pack-manifest regeneration. | Technical | High | Open |
| C-004 | Existing tests stay the spec | The #6418 doctor tests keep their assertions; only references to a deleted symbol (monkeypatch targets) may be re-pointed, and the registry-aware offering tests keep their subdir/symlink/shadowing scenarios. | Technical | High | Open |

### Key Entities

- **OrgDRGFragment**: one loaded org pack's DRG fragment. Gains a typed, non-serialized carried
  pack root, stamped by the loader that already received the effective root.
- **Containment predicate**: `find_body_path_escapes` (authored node `body_path` vs pack root) and
  `find_asset_path_escapes` (org asset sidecar `path` vs `<root>/assets`). Both become
  fragment-only.
- **Pack registry read**: `load_pack_registry(repo_root)`, the authority for pack name → effective
  root. It stays the loader's input and stops being the doctor's second lookup.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One `_collect_org_layer_data` run over a repo with one configured org pack calls
  `load_pack_registry` exactly once, down from three, measured by a counting test on the production
  entry point. — [build] · no-op passable: no
- **SC-002**: The doctor's containment refusal matrix (dot-dot escape, absolute escape, contained
  control; body_path and asset path) produces the same findings and exit codes as before the
  change, with the escaping fixtures as the positive control. — [ratchet] · no-op passable: yes —
  paired with the escaping fixtures on the same test module
- **SC-003**: `charter.activation.drg_activation` no longer exposes the two wrapper names, and the
  architectural activation-seam gate passes with its baseline file unchanged. — [build] ·
  no-op passable: no
- **SC-004**: The fragment's serialized key set is unchanged, so doctor `--json` output and any
  fragment comparison stay byte-identical. — [ratchet] · no-op passable: no
