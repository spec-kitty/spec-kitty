---
title: 'ADR: Org-aware mission-type loader + `path_conventions` doctrine slot (full charter convergence deferred to #2652)'
description: 'The mission-type loader is made org-aware — it routes through the shared org-aware resolver and builds a neutral Mission for sparse org-registered types — so org/override custom types resolve as themselves instead of software-dev; `path_conventions` is a new charter doctrine slot with a canonical `VALID_PATH_KEYS` home. Full convergence onto charter `ResolvedMissionType` (retiring the legacy resolver) is deferred to #2652 because the legacy and charter sources encode different concerns.'
status: Accepted
date: '2026-09-20'
---

## Context and Problem Statement

Spec Kitty resolves a mission's *type* through **three** independent registries that
disagree (issues #3831, #4088):

1. **Legacy template loader** — `src/specify_cli/mission.py` loads a `Mission` from a
   directory containing `mission.yaml` via `_mission_path_by_name`, consulting only two
   tiers (`.kittify/missions/<name>`, then packaged built-ins). It is **org-blind** and
   bypasses the six-tier resolver (`src/specify_cli/runtime/resolver.py`) that the
   *command-template* lookup already uses.
2. **Org-tier governance resolver** — `charter.activation.mission_type_profiles.
   resolve_mission_type_context` (+ `MissionTypeRepository`, `resolve_org_dirs`), which
   *is* org-aware.
3. **`mission-runtime.yaml` resolver** — `runtime/next/runtime_bridge_io.py`, org-aware,
   owns the runtime step-DAG.

Because (1) never consults the org tier, an org-pack-activated custom mission type falls
through `_mission_path_by_name`, `get_mission_for_feature` swallows the
`MissionNotFoundError`, and the mission silently loads as **software-dev** — carrying
software-dev's path conventions and required/optional artifact sets instead of its own.
#4088 is the same function failing to consult a project override tier.

### Re-scope discovery (2026-09-21): the two sources encode different concerns

This mission began as the #2652 "single canonical mission-type source" slice — converge
mission-type loading onto charter `ResolvedMissionType` and retire the
`specify_cli/mission.py` resolver. Implementation surfaced a load-bearing fact the planning
had assumed away: **the charter/doctrine tier does not carry built-in path/artifact data
equivalent to the legacy `mission.yaml`, and the two encode different concerns.** Legacy
`artifacts.required/.optional` is a **template-selection** list (what a mission template
offers); charter `expected_artifacts.required_by_step` is a **runtime step-gate
completeness** spec. Their token sets diverge materially, and `path_conventions` is
unpopulated (`null`) for all three built-ins. A wholesale "read everything from charter"
rewrite would therefore silently change built-in behavior (SC-004/NFR-001 regression), not
refactor it.

**Decision (operator, 2026-09-21): re-scope to the targeted, behavior-safe fix** — make the
loader org-aware (the fix #3831's author originally proposed) and defer the full convergence
(retiring the resolver + reconciling/authoring built-in doctrine data as a two-concern
merge) to the **#2652 epic**. The `path_conventions` slot and the charter `VALID_PATH_KEYS`
home (below) are retained as the foundation that convergence will build on.

This ADR is a companion to, not a reversal of, two earlier decisions:

* **ADR 2026-07-14-2** (Doctrine → Charter → Core Mission-Type Resolution Unification)
  already named the north-star — `src/specify_cli/missions/` should eventually be
  deleted and `software-dev` should be an ordinary built-in doctrine mission type fed
  through the charter, with no hardcoded core knowledge of `software-dev`. This mission
  is a concrete step toward that north-star, specifically for the `mission.yaml`
  `Mission`/`MissionConfig` resolver (a *third*, still-undecided surface that ADR
  2026-07-14-2's problem statement did not itself retire).
* **ADR 2026-07-15-1** (Doctrine offers, Charter activates, Runtime consumes) established
  the layering this mission's `path_conventions` slot lives inside: charter is the single
  offering surface a doctrine artifact (a `MissionType`) is authored against; runtime and
  `specify_cli` consume it, never author competing copies.

It **reconciles ADR 2026-08-28-1** (a project `path_conventions` override precedes the
doctrine default). That ADR's "doctrine default" side was, at the time, `MissionConfig.
paths` sourced from `specify_cli/mission.py`'s `mission.yaml` tier — the resolver this
mission makes org-aware (full retirement deferred to #2652). 2026-08-28-1's *decision* (project override remaps the resolved
directory; the accept-blocking policy from #3783 is unchanged; one canonical frozenset of
valid path keys, reused by both validation and the override reader) is preserved
unmodified; the *doctrine-default* side of that precedence chain moves onto the charter
`MissionType.path_conventions` slot introduced here. `VALID_PATH_KEYS` — the
"one canonical frozenset" 2026-08-28-1 already called for — is the concrete relocation
target: charter becomes its canonical home (Directive 044, single canonical authority),
per FR-004/FR-009 of this mission's spec.

### The `Mission` name collision

Two independent, unrelated classes are both named `Mission` in this codebase, and this
mission's convergence makes the collision load-bearing rather than incidental:

* **`specify_cli.mission.Mission`** (`src/specify_cli/mission.py`) — the legacy
  `mission.yaml`-backed domain object this ADR makes org-aware (`MissionConfig`-validated,
  carries `workflow`, `artifacts`, `paths`, etc.; full retirement deferred to #2652). This
  is the resolver named in the Context section above.
* **`charter.offering.missions.models.Mission`** (`src/charter/offering/missions/
  models.py:151`) — an unrelated **schema-generation model** used only by
  `scripts/generate_schemas.py` to emit `src/charter/offering/schemas/mission.schema.yaml`
  (a minimal `schema_version`/`key`/`name`/`steps` shape). It is explicitly **not** the
  runtime domain model (see its own docstring) and has no `path_conventions`,
  `MissionConfig`, or `mission.yaml` relationship at all.

Neither `Mission` class is renamed by this mission — that is out of scope here — but a
reader who greps `class Mission` and finds two hits, in two packages this mission is
actively moving authority *between*, needs the disambiguation on record: **the `Mission`
this ADR concerns (makes org-aware; retirement deferred to #2652) is
`specify_cli.mission.Mission`; the `Mission` in
`charter/offering/missions/models.py` is untouched and unrelated.** The field this
mission *does* add lives on a third, distinctly-named class in the same module —
`charter.offering.missions.models.MissionType` (`:234`) — which is not `Mission` at all.
Future work that renames either `Mission` to resolve this collision should treat this ADR
as the reference for which one is which.

## Decision

1. **Org-aware mission-type loader (this mission).** `get_mission_by_name`
   (`specify_cli/mission.py`) resolves `mission.yaml` through the shared **org-aware**
   resolver `specify_cli.runtime.resolver.resolve_mission` (override → legacy → org →
   global → package — the same chain command-template resolution already uses), and, when a
   type is org-registered via a sparse `mission_types/<type>.yaml` but ships no
   `mission.yaml`, builds a **neutral `Mission`** (the org type's `display_name` identity,
   its own `path_conventions` or none, no software-dev conventions). `get_mission_for_feature`
   preserves the typeless→software-dev *template* default and now raises a visible
   `MissionNotFoundError` for a typed-but-unknown type instead of warn-and-substituting.
   This closes #3831 and #4088 without touching built-in behavior. The legacy `Mission` /
   `MissionConfig` / `mission.yaml` resolver is **retained** here — retiring it, and making
   charter `ResolvedMissionType` the *sole* source, is the **#2652 epic** (it requires the
   two-concern merge + built-in doctrine-data authoring described in the Re-scope section).
   Direction of dependency is unchanged: consumers depend downward onto charter, never the
   reverse (C-001).

2. **`path_conventions` — a new doctrine slot (FR-004).** `MissionType` gains an optional
   `path_conventions: dict[str, str] | None` field (WP02, `models.py`). A mission type
   that declares **no** conventions (`None`, the default) is a pure no-op for downstream
   consumers — accept-path validation does not fall back to another type's shape (e.g.
   software-dev's `src/`/`tests/`) when a type is silent. This is the one genuinely new
   schema this mission introduces; every other legacy `mission.yaml` field migrates to an
   existing charter/dossier home or is retired outright (see the mission's `plan.md`
   consumer census).

3. **`VALID_PATH_KEYS` relocates into charter (FR-004/FR-009, Directive 044).** The
   frozenset of valid path-convention keys — `{"workspace", "tests", "deliverables",
   "documentation", "data"}` — is added to `charter.offering.missions.models` (WP02,
   T011) as the **canonical** home, together with a `validate_path_conventions` validator
   that rejects (raises `ValueError`, fail-closed) any key outside that set. The historical
   copy at `specify_cli.mission.VALID_PATH_KEYS` (`mission.py:159`) is deliberately **not**
   deleted here — both copies carry the identical literal value, pinned by the WP02 test
   suite (`tests/charter/test_path_conventions_slot.py`) so drift is caught. Deleting the
   `specify_cli` copy and repointing its importers (`config/path_conventions.py`) onto the
   charter home is part of the **#2652** convergence (originally WP04, now deferred with the
   rest of the resolver retirement), not this slice.

4. **The `Mission` name collision is documented, not resolved, here** (see above). No
   rename is performed by this mission.

## Consequences

* **Positive.** Org-tier and project-override custom mission types resolve as themselves
  instead of being warn-and-substituted with software-dev (#3831, #4088 closed by this
  mission). A typed-but-unknown mission type now fails visibly instead of silently. Path
  conventions get a doctrine-governed slot for org types to declare.
* **Built-ins byte-unchanged.** The loader special-cases the resolver's PACKAGE tier back to
  the historical `src/specify_cli/missions/<type>/` source, so built-in path conventions and
  artifact sets are identical to before and stay consistent with `discover_missions` /
  `list_available_missions` / `get_active_mission` (which read the same source). The two
  built-in package roots (`src/specify_cli/missions/` vs the canonical
  `packs/built-in/missions/`) have pre-existing drift (e.g. `documentation.paths.deliverables`
  `docs/` vs `docs/output/`, and terminology); unifying them onto the canonical root and
  deleting the `specify_cli` copy is the #2652 convergence, deliberately out of scope here so
  this slice changes no built-in behavior. The `.kittify/missions/` project tier now emits the
  shared resolver's `run spec-kitty migrate` deprecation nudge, consistent with
  command-template resolution.
* **Cost / risk — standing dual-home until #2652.** `VALID_PATH_KEYS` exists in two places
  (charter canonical + the retained `specify_cli` copy) until the #2652 convergence deletes
  the legacy resolver. Both are value-pinned by tests so they cannot drift. This is a
  scoped, documented exception to single-authority for the life of the deferral, not silent
  duplication.
* **Layering.** `path_conventions` and `VALID_PATH_KEYS` are added strictly *downward*
  into `charter` — no new `charter → specify_cli` import is introduced (C-001). WP02 does
  not touch `packs/built-in/` doctrine content or a doctrine-derived pack schema, so the
  pack-manifest regen gate (`spec-kitty doctrine regenerate-graph`) is not triggered by
  this WP; it remains in scope for whichever later WP first authors a built-in
  `mission_types/*.yaml` entry with a `path_conventions:` key.
* **ATDD.** WP01 already landed red-first repros for #3831/#4088 through the pre-existing
  entry point (ADR 2026-07-17-1 discipline); WP02's `path_conventions`/`VALID_PATH_KEYS`
  slot is covered by new, issue-pinned unit tests
  (`tests/charter/test_path_conventions_slot.py`) rather than a repro, since the slot is
  net-new rather than a defect fix.

## Alternatives Considered

* **Give `path_conventions` its own top-level YAML artifact / schema file distinct from
  `MissionType`.** Rejected: `MissionType` is already the governed descriptor for a
  built-in or extension mission type (one YAML file per type, `id`-keyed); a sibling
  artifact would duplicate that identity and reintroduce a second registry to keep in
  sync — exactly the class of defect this mission closes.
* **Warn-and-continue on an unknown `path_conventions` key** (mirroring the historical
  `specify_cli.mission.MissionConfig` behaviour, which used `warnings.warn`). Rejected:
  charter's `MissionType`/`MissionStep` models are `extra="forbid"`, fail-closed models
  throughout (see `_validate_id`, `validate_action_sequence`); a silently-tolerated typo
  in a path-convention key is exactly the "looks configured, isn't enforced" failure mode
  Directive 044 (single canonical authority, no silent drift) exists to prevent.
* **Rename one of the two `Mission` classes as part of this WP.** Rejected as out of
  scope: WP02's owned files are `models.py`, this ADR, and the new test file; a rename
  touches every consumer of whichever class is renamed and belongs to a dedicated,
  reviewed WP of its own.

## References

* Issues: #3831 (org-tier custom mission type invisible to the loader), #4088 (project
  override tier never consulted), #2652 (single canonical mission-type source epic).
* Mission: `kitty-specs/mission-type-canonical-source-01M302V9/spec.md`,
  `.../plan.md` (consumer census, WP sequencing).
* Related ADRs: `docs/adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md`
  (companion — names the north-star this mission advances),
  `docs/adr/3.x/2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md`
  (companion — the layering `path_conventions` lives inside),
  `docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md`
  (reconciled — its override-precedence decision is preserved; its doctrine-default side
  now points at `MissionType.path_conventions`; the `mission.yaml` resolver is made
  org-aware here, with full retirement deferred to #2652).
* Charter: Directive 044 (single canonical authority / no drifting duplicate lists), C-001
  (`charter` must never import `specify_cli`), C-005 (routing-safety coupling between the
  path-convention value and the mission artifact-token vocabulary, unchanged by this ADR).
