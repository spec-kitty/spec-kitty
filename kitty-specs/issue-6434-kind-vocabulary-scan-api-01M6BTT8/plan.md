# Implementation Plan: Promote kind_vocabulary scanning helpers to a module-internal API

**Mission**: `issue-6434-kind-vocabulary-scan-api-01M6BTT8`
**Branch**: `issue-6434-kind-vocabulary-scan-api` (planning, base and merge target; planning
and merge happen on the same branch because this is a `single_branch` mission)
**Spec**: `kitty-specs/issue-6434-kind-vocabulary-scan-api-01M6BTT8/spec.md`
**Research**: `kitty-specs/issue-6434-kind-vocabulary-scan-api-01M6BTT8/research.md`

## Summary

`charter.activation.kind_vocabulary` owns artifact discovery for the whole charter layer,
but its scanning and id-reading helpers are underscore-private, and
`charter.activation.identity_index` — a production consumer — plus about a dozen test
modules reach through those private names. This plan promotes the scanning helpers and the
four other seams named in issue #6434 to named module-level API, moves every call site in
`src/` and `tests/` onto the public name, and adds one architectural ratchet that fails if
any retired underscore name returns.

The change is a **behaviour-preserving promotion**: no precedence rule, recursion rule,
reserved-directory rule or gate changes. The proof of that is the existing resolution
suites, which run unmodified apart from the seam they wrap.

## Technical Context

**Language/Version**: Python 3.11+ (repo target), typed with mypy strict on touched modules.
**Primary Dependencies**: `ruamel.yaml`, stdlib `pathlib`. No new dependency.
**Storage**: N/A — filesystem artifacts only; nothing persisted.
**Testing**: `pytest` (fast tier: `make test-fast`), `tests/architectural/` for the ratchet.
**Target Platform**: CLI/library (`charter` layer inside the core package).
**Project Type**: Single project — library plus CLI in one `src/` tree.
**Performance Goals**: no scan-count regression; per-kind `IdentityIndex` scan stays at most
one per kind per index instance, per-layer resolver scan at most one per layer per pass
(NFR-001).
**Constraints**: the `charter` layer may import `doctrine`/`kernel` but never
`specify_cli`; roots stay passed in as data (C-008-style boundary already enforced by
`tests/architectural/test_runtime_charter_activation_boundary.py`).
**Scale/Scope**: one production module pair (`kind_vocabulary`, `identity_index`) and two
renamed governance seams, plus their tests; no CLI, schema or config surface changes.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | `kind_vocabulary` stays the only discovery authority; the promotion names the existing implementation, it does not add a second one (C-003). |
| Architectural alignment / package boundaries | No new cross-layer import; the public names stay inside `charter.activation` and the existing boundary ratchet still passes (NFR-002). |
| DIRECTIVE_024 Locality of change | The diff stays inside the two production modules, the two renamed seams and the tests that reference them; no unrelated cleanup. |
| DIRECTIVE_025 Boy Scout rule | There is one licensed adjacent fix: `_load_action_governance_bundle` is already in `__all__` while carrying an underscore; the rename removes that inconsistency instead of leaving it. |
| ATDD-First Discipline (C-011) | The architectural ratchet is written and run **red** first, against the untouched tree, then the promotion makes it green. |
| DIRECTIVE_041 (test only where it guards behaviour/invariant) | One new test file, one invariant: no retired underscore name is reachable from `src/` or `tests/`, plus a positive control that the public names resolve. |
| `__all__` Declaration Convention (C-007) | Every promoted name is added to `kind_vocabulary.__all__`; the two renamed governance seams are exported from their modules. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Targeted `pytest` selections plus `make test-fast` only; CI owns the full sweep. |
| Terminology canon (Mission vs Feature) | Mission language used throughout the artifacts and the changelog. |

No violations, so **Complexity Tracking** stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6434-kind-vocabulary-scan-api-01M6BTT8/
├── spec.md
├── research.md
├── plan.md
├── tasks.md
├── meta.json
├── traces/
│   ├── approach.md
│   ├── design-decisions.md
│   └── tooling-friction.md
└── tasks/
```

### Source Code (repository root)

```
src/charter/activation/
├── kind_vocabulary.py          # the promotion: public scanning + id API, __all__ updated
├── identity_index.py           # consumes the public API; _scan -> scan
├── action_governance_bundle.py # _load_action_governance_bundle -> load_action_governance_bundle
├── compiler.py                 # _direct_root_urns -> direct_root_urns
├── context.py                  # import of the renamed bundle loader
└── pack_manager.py             # docstring cross-reference to the renamed stem helper

tests/charter/
├── activation/test_identity_index.py            # probe the public seam
├── activation/test_compile_check_identity_6433.py
├── activation/test_context_identity_reuse.py    # wraps IdentityIndex.scan
├── test_directive_resolution_memoization.py
├── test_resolver_directive_activation_keying.py # wraps IdentityIndex.scan
├── test_kind_vocabulary_scan_roots.py
├── test_action_governance_bundle_activation.py
├── test_synthesized_in_force_snapshot.py
├── test_context_service_seams.py
├── test_context_display_charter_md.py
├── synthesizer/test_styleguide_reach_only.py
├── synthesizer/test_reach_only_delivery.py
├── charter_offering/test_owner_delivery.py
├── charter_offering/drg/test_org_pack_node_inference.py
├── charter_offering/drg/test_recursion_parity_gate.py
├── charter_offering/test_activation_parity_guard.py  # docstring reference only
└── test_org_scan_dirs_activation_regression.py       # docstring reference only

tests/architectural/
└── test_charter_kind_vocabulary_public_scan_api.py   # new ratchet (the red-first proof)

docs/changelog/CHANGELOG.md   # [Unreleased] entry under the existing governance section
```

**Structure Decision**: single project. The `charter` layer is an in-repo package under
`src/charter/`, its consumers are the sibling modules listed above, and no packaging or
entry-point surface moves, so no new directory is introduced.

## Phase 0 — Research

Discovery already recorded the grounding, the reproduction and the naming decisions in
`research.md` (created at the `discovery` step). Plan-phase extension, appended there:

- **Decision**: promote in place and delete the private names, rather than keep aliases.
  **Rationale**: an alias keeps the coupling the issue reports; the module is internal to
  the `charter` layer, so no external consumer depends on the underscore names.
  **Alternatives considered**: deprecated aliases with a warning (rejected: no deprecation
  machinery for in-repo private names, and it would leave two names for one helper);
  a separate `scanning.py` module (rejected: it would split the single discovery authority
  across two files for no gain, and the issue asks for a small API *in* `kind_vocabulary`).
- **Decision**: `read_artifact_id` (pass-memoised) vs `parse_artifact_id` (uncached full
  parse) stay two names. **Rationale**: the scan/memoization tests assert the memoised
  reader is the only seeder of `ResolutionPass.ids`, and compare against the uncached
  parse; collapsing them would weaken that assertion.
- **Decision**: the ratchet scans `src/` and `tests/` text for the retired attribute names
  (`kind_vocabulary._<retired>`, `IdentityIndex._scan`,
  `action_governance_bundle._load_action_governance_bundle`,
  `compiler._direct_root_urns`). **Rationale**: it is the only check that a no-op cannot
  pass and it guards recurrence; a pure "the names exist" test would be vacuous.
  **Alternatives considered**: an import-graph test (rejected: attribute access inside a
  module is not an import, and the tests patch by attribute).

No `NEEDS CLARIFICATION` markers remain. `data-model.md` is not applicable (no entities
beyond the existing in-memory `IdentityEntry`/scan-root tuples already documented in the
spec), and the mission declares no interfaces, so `contracts/` is waived via `meta.json`
(`"contracts": "none"` + rationale).

## Phase 1 — Design

**Public surface of `charter.activation.kind_vocabulary` after the promotion** (added to
`__all__` beside the existing resolver names):

| Name | Replaces | Contract |
| --- | --- | --- |
| `artifact_id_field(kind)` | `_id_field_for` | YAML key holding the id for `kind` (`profile-id` for agent profiles, else `id`). |
| `parse_artifact_id(path, id_field, yaml)` | `_parse_id` | Uncached full parse; declared id, else filename stem, else `None`; never raises for unreadable/unparseable files. |
| `read_artifact_id(path, id_field, yaml, resolution_pass=None)` | `_read_id` | Canonical reader; memoised per `ResolutionPass` when one is supplied. |
| `artifact_config_stem(path)` | `_config_stem` | Filename with every suffix removed. |
| `scan_dir_matches(scan_dir, pattern, *, recursive)` | `_scan_dir_matches` | Files under one root matching the kind's pattern; recursive scans exclude the reserved immediate `built-in/` child. |
| `built_in_scan_dir(kind)` | `_built_in_scan_dir` | `(dir, recursive)` for the flattened built-in root, or `None` when it cannot be located. |
| `scan_roots(kind, *, offering_root, org_roots, layer_roots)` | `_scan_roots` | Ordered `(dir, recursive)` pairs: project, org packs last-to-first, built-in. |
| `iter_artifact_paths(kind, *, offering_root, org_roots, layer_roots, resolution_pass=None)` | `_iter_artifact_paths` | The artifact paths for `kind` across those roots; memoised per pass. |

Other seams: `IdentityIndex.scan(kind)` (was `_scan`), `load_action_governance_bundle`
(was `_load_action_governance_bundle`, already in `__all__`), `compiler.direct_root_urns`
(was `_direct_root_urns`).

**Invariants preserved** (each pinned by an existing test, none rewritten):
1. Flat-before-legacy org ordering and flat-wins precedence
   (`tests/charter/test_kind_vocabulary_scan_roots.py`).
2. Loader↔resolver recursion parity, including the reserved `built-in/` exclusion
   (`tests/charter_offering/drg/test_recursion_parity_gate.py`,
   `test_activation_parity_guard.py`).
3. One scan per kind per index, one scan per layer per resolution pass
   (`test_identity_index.py`, `test_directive_resolution_memoization.py`).
4. Directive id round-trip and ambiguity refusal
   (`tests/charter/test_config_stem_parity.py`, `test_directive_resolution_memoization.py`).
5. Governance-bundle content and reach-only exclusions
   (`tests/charter/test_action_governance_bundle_activation.py`,
   `tests/charter/synthesizer/test_styleguide_reach_only.py`).

**Red-first proof**: `tests/architectural/test_charter_kind_vocabulary_public_scan_api.py`
runs against the untouched tree, reports the retired names, and only goes green once every
call site has moved. A negative control (a synthetic snippet containing a retired name) is
asserted to be detected, so the scanner cannot pass by finding nothing at all.

## Complexity Tracking

*No charter violations, so this section is intentionally empty.*

## Implementation Concern Map

### IC-01 — kind_vocabulary's scanning and id surface

- **Purpose**: make artifact discovery a named API instead of private helpers, so the
  module that owns discovery can be read and tested as an interface.
- **Relevant requirements**: FR-001, FR-002, FR-007, NFR-004, C-001, C-002, C-003
- **Affected surfaces**: `src/charter/activation/kind_vocabulary.py`,
  `src/charter/activation/pack_manager.py` (docstring reference)
- **Sequencing/depends-on**: none
- **Risks**: a blind global rename can hit unrelated helpers with similar names
  (`_iter_mission_scan_roots`, `_default_scan_roots`, `catalog._resolve_scan_roots`,
  `pack_assembler._read_id`); every rename must be anchored on the module attribute or the
  exact definition.

### IC-02 — IdentityIndex consumes the public surface

- **Purpose**: remove the production coupling that the issue reports, and give tests a
  documented per-kind scan seam.
- **Relevant requirements**: FR-003, FR-004, NFR-001, NFR-002
- **Affected surfaces**: `src/charter/activation/identity_index.py`, and the four test
  modules that wrap the scan seam
- **Sequencing/depends-on**: IC-01
- **Risks**: the scan-count tests assert exact root counts; the seam must wrap the same
  per-kind scan, not a per-root helper, or the counts change.

### IC-03 — governance-seam renames

- **Purpose**: promote the two remaining names the issue lists, so graph-seeding tests
  import supported surface.
- **Relevant requirements**: FR-005, FR-007
- **Affected surfaces**: `src/charter/activation/action_governance_bundle.py`,
  `src/charter/activation/compiler.py`, `src/charter/activation/context.py`, and the test
  modules that import them
- **Sequencing/depends-on**: none (independent of IC-01/IC-02)
- **Risks**: `context.py` re-exports the loader under a private alias for its own use and a
  test inspects `context_module._load_action_governance_bundle`; the alias must keep
  pointing at the renamed function so the AST/signature assertions keep their meaning.

### IC-04 — ratchet, changelog and mission close-out

- **Purpose**: prove the promotion is complete and cannot silently regress, and record the
  change for the maintainer.
- **Relevant requirements**: FR-006, FR-007, NFR-003, SC-001, SC-004, C-004
- **Affected surfaces**: `tests/architectural/test_charter_kind_vocabulary_public_scan_api.py`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: the ratchet must stay in the fast tier (AST/text scan only, no pack fetch) and
  must not flag the changelog's own mention of the retired names — it scans `src/` and
  `tests/`, not `docs/`.
