# Discovery — mission-type capability contract on the offering seam (#6331)

**Mission**: `mission-type-capability-offering-seam-01M68ZMR`
**Grounded against**: canonical `origin/main` at `dfe9efb0e8` (2026-10-31).

## Facts established before the spec

### The issue and its current state

- #6331 asks that `ResolvedMissionType` (with `wp_driven` / `requires_substantive_spec`)
  and `resolve_mission_type_context` be reachable through `charter.offering.api`, with the
  DISPOSITION census rows and offering public-surface gates satisfied.
- The issue is labelled `triage:needs-revision` and already carries a governed triage
  comment (batch 17) ruling that its **extraction rationale and #645 sequencing are
  superseded**: #645 is closed `not_planned`, #6188 is complete, and ADR
  `2026-10-16-1` (Amendment 2026-10-19) keeps the Python charter in core behind a frozen
  offering seam. That comment explicitly forbids "a blind activation re-export".
- Consequence for scope: the *exposure of the capability contract* is still real and
  unfulfilled (the triage comment confirms the exports are absent from
  `src/charter/offering/api.py:69-86` while the DTO/resolver remain in
  `src/charter/activation/mission_type_profiles.py:401-470,605-713`); the *extraction
  narrative* is not. This mission delivers the former and retires the latter in the record.

### Sibling scope (stay off these diffs)

- **#6330** hardens the contract *internals*: `run_dir` threading into
  `gather_artifact_presence`, narrowing or logging `_requires_substantive_spec`'s
  `except Exception`, and `wp_driven` charter-vs-runtime parity. Nothing in this mission
  touches those files' behaviour.
- **#6327** adds a third capability, `code_producing`, to `ResolvedMissionType`. The design
  here must let that land without a rename: hence a protocol (structural) plus a value
  object (additive field), not a tuple or a re-exported class.

### Architectural boundary (load-bearing)

- ADR `2026-10-16-1` records a **verified** dependency direction: `src/charter/offering/**`
  contains no runtime import of `charter.activation` (67 textual matches are docstrings),
  while the reverse edge is ~360 references. Offering sits *below* activation.
- Therefore "re-export `ResolvedMissionType` / `resolve_mission_type_context` from
  `charter.offering.api`" would invert the layer and is refused. The **contract** crosses
  the seam; the activation implementation does not.
- Additive seam symbols follow the precedent ADR `2026-10-03-1` Amendment 2026-10-20 set for
  `LANGUAGE_TOKENS` (#6541): symbol lands on `charter.offering.api`, ADR amendment records
  it, the seam's own gates narrow it, a `charter.*` facade re-exports it.

### Code facts

- `src/charter/offering/api.py` is a pure re-export manifest with a sorted `__all__`
  (12 entries today: `ArtifactKind`, `AssetManifest`, `AssetNotFoundError`,
  `AssetPathEscapeError`, `AssetRepository`, `AssetResolutionError`, `CatalogLoadResult`,
  `LANGUAGE_TOKENS`, `RoutingRecommendation`, `evaluate`, `load`, `slug_for`).
- `ResolvedMissionType` (`src/charter/activation/mission_type_profiles.py:401`) is a frozen
  dataclass with `mission_type`, `governance_text`, `action_sequence`, `provenance`,
  `wp_driven` (eager field) and lazy `cached_property` capabilities
  (`requires_substantive_spec`, `governance`, `template_set`, `expected_artifacts`,
  `step_contracts`).
- `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC` is `{software-dev: True, research: True,
  documentation: False, plan: False}`; undeclared custom types default `False`.
- Gates that a seam addition must satisfy, all in-tree and read in full:
  - `tests/architectural/test_doctrine_census.py` — `DISPOSITION` rows per offering module
    path; `test_every_reached_offering_path_has_disposition` fails on an unclassified reach.
    The table is a documented *superset* of reached paths, so an unreached row is legal.
  - `tests/architectural/test_charter_offering_public_surface.py` — importable + non-`None`,
    sorted/unique `__all__`, every symbol's origin module `PUBLIC` in `DISPOSITION`
    (longest-prefix match), no-door symbols absent, and the **strict** coverage rule that
    every `charter.offering.api.__all__` symbol is re-exported from `charter.offering.api`
    by at least one `src/charter/*.py` facade.
  - `tests/charter_offering/test_language_tokens_seam.py` — the model seam test: pins the
    seam↔origin import set, asserts internals stay off the seam, asserts the facade hands
    out the same object.
  - `tests/architectural/test_charter_facades_reexport_offering.py` — object identity
    between facade and origin.
- `charter.missions` facade (`src/charter/missions.py`) is the natural door: it already
  fronts the mission-type repositories and is a pure re-export module.

## Decisions

- **D1 — Expose the contract, not the resolver.** `charter.offering.missions.capabilities`
  defines a frozen `MissionTypeCapabilities` value object, a runtime-checkable
  `MissionTypeCapabilitySource` protocol, and `capabilities_of()`. Activation's
  `ResolvedMissionType` satisfies the protocol structurally and gains a `capabilities`
  property. No activation import appears in the offering module.
- **D2 — Three symbols, no more.** The seam grows by exactly `MissionTypeCapabilities`,
  `MissionTypeCapabilitySource`, `capabilities_of`; `charter.missions` re-exports all three.
- **D3 — One source of truth.** `capabilities_of()` reads the source's own attributes; no
  built-in capability table is copied into offering (constraint C-004).
- **D4 — Layering is tested, not asserted.** A test imports the module in a fresh
  subprocess and asserts `charter.activation*` is absent from `sys.modules`, with a positive
  control proving the detector can see an activation import.

## Open questions (resolved in-mission or deferred)

- *Does the offering value object need to carry provenance?* No — capabilities only; adding
  provenance would duplicate `ResolvedMissionType.provenance` and widen the seam for no
  consumer.
- *Should `resolve_mission_type_context` also be reachable from the seam?* No: it is an
  activation-tier resolver (it reads the activated roster from disk). Importing it into
  offering would invert the layer. The consumer obtains the resolved object from its own
  tier and reads capabilities through the seam — that is exactly user story 1.
- *Does the ADR amendment need operator sign-off?* It follows the documented #6541
  precedent mechanically; recorded in the ADR amendment and the changelog. Flagged in the
  PR body for the operator's review, not blocking.
