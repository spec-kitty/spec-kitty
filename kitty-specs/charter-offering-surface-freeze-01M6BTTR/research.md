# Discovery findings — charter offering public surface freeze (#6285)

Recorded 2026-11-01 on `kitty/mission-charter-offering-surface-freeze-01M6BTTR`
(base `origin/main` @ `287a226cfe`).

## D-001 — The shipped building blocks are real; the freeze itself is not

Evidence (source inspection on the base commit):

- `src/charter/offering/api.py:69-87` — `__all__` is a sorted, explicit 12-name
  literal: `ArtifactKind`, `AssetManifest`, `AssetNotFoundError`,
  `AssetPathEscapeError`, `AssetRepository`, `AssetResolutionError`,
  `CatalogLoadResult`, `LANGUAGE_TOKENS`, `RoutingRecommendation`, `evaluate`,
  `load`, `slug_for`.
- `tests/architectural/test_charter_offering_public_surface.py` asserts
  importability, sort order, `DISPOSITION == PUBLIC` coupling, no-door absence
  and strict facade coverage (its own docstring at lines 8-12 records that it
  "does not additionally pin the exact symbol set as a frozen literal").
- `tests/architectural/test_charter_facades_reexport_offering.py` asserts object
  identity for the facade table (`charter.drg`, `charter.assets`,
  `charter.model_routing`, `charter.profiles`, `charter.missions`, ...).
- `tests/architectural/test_charter_offering_does_not_import_activation.py`
  asserts the forbidden `offering → activation` edge via a full AST walk with
  committed non-vacuity controls.
- `tests/architectural/test_charter_activation_api_reexport.py` pins the
  activation seam as identity-only and split from offering.

Baseline run, all green (322 passed in 433 s):

```
uv run --frozen pytest -q \
  tests/architectural/test_charter_offering_public_surface.py \
  tests/architectural/test_charter_facades_reexport_offering.py \
  tests/architectural/test_charter_activation_api_reexport.py \
  tests/architectural/test_charter_offering_does_not_import_activation.py \
  tests/architectural/test_doctrine_census.py
```

So the gap is narrow and real: no committed census, no frozen literal pin, no
per-symbol contract/DTO annotation, no whole-picture classification, and C-003
still says "OpenAPI conventions do not apply" (which #6218 exists to reverse).

## D-002 — The census is a gate asset, not wheel data

Decision: commit the census at
`tests/architectural/charter_offering_public_surface.yaml`, beside the gate that
reads it, following the existing `tests/architectural/charter_activation_boundary_baseline.yaml`
and `dead_symbol_allowlist.yaml` precedent. Rationale:

- it is a review artefact and a test fixture, not runtime behaviour, so it must
  not enter the `spec-kitty-doctrine` wheel surface (`packs/built-in/` is the
  only shipped data);
- putting it in `src/charter/offering/` would make the wheel ship a
  test-only contract list that the runtime never reads;
- `kitty-specs/<mission>/` is a mission artifact, not a durable pin.

`charter.offering.api.__all__` stays the literal that maintainers read (its
docstring already promises one file); the census pins it rather than replacing
it, so static gates that parse the literal (`extract_static_all`, no-dead-symbol)
keep working.

## D-003 — Classification is derived from the authoritative disposition manifest, never restated

`tests/architectural/test_doctrine_census.py::DISPOSITION` is the authoritative
path disposition manifest and is re-censused from the live tree on every run.
The census records the *reached* paths and their dispositions, and the gate
compares them against `DISPOSITION` by longest-prefix (the manifest keys the
model-routing cluster at package level). Measured on the base commit:

| Disposition | Reached offering paths |
|---|---|
| PUBLIC | `artifact_kinds`, `assets.models`, `assets.repository`, `model_task_routing`, `shared.language_catalog` |
| FACADE-ONLY | `agent_profiles.operating_procedures`, `drg.loader`, `missions.step_contracts`, `missions.step_projection`, `pack_paths` |
| TICKETED-BASELINE (no door, ratchet-owned) | `drg.override_policy`, `drg.migration.hand_authored_overlay` |
| CONSTRUCTION-ROUTED | `service` |
| INTERNAL-METADATA | `charter.offering` (root) |

10 distinct paths over 6 reaching files. None of the non-PUBLIC paths is a
public-contract delta: FACADE-ONLY ones are fronted by charter facades whose
identity the facade gate already pins; the two TICKETED-BASELINE paths are the
sanctioned no-door set handled by the dead-symbol ratchet allowlist; `service`
is reached as a construction entry point, not as a public symbol; the root is
metadata. Expected delta: empty. If the gate ever finds one it must be reported
for operator approval, not widened here (C-003 of the spec).

## D-004 — Facade provenance comes from the facade modules' own import statements

Rather than re-deriving which facade fronts a symbol (and risking a second,
disagreeing source), the census records the facades that actually write
`from charter.offering.api import …`, read from the `src/charter/*.py` ASTs the
existing strict coverage assertion already walks. A census row's `facades` must
equal that set, so the frozen list and the wiring cannot drift apart.

Correction recorded during WP01: the plan first proposed reading `_FACADE_TABLE`
from `tests/architectural/test_charter_facades_reexport_offering.py`. That table
keys `charter.languages`' `LANGUAGE_TOKENS` row to its origin submodule
(`charter.offering.shared.language_catalog`), not to the `charter.offering.api`
import the facade actually performs, so filtering it by `charter.offering.api`
would have reported a false facade gap. The AST walk is the same evidence the
strict coverage assertion uses and needs no second table; the identity gate keeps
owning object identity.

## D-005 — Fold #6218's C-003 wording; do not close #6218

#6285 permits "land first or fold its wording in". #6218 is still open and is
docs/ADR-only; this mission takes the C-003 direction (spec-kitty-charter
ADR-0004: the seam's return types become contract-generated DTOs; today's
hand-written types are transitional) into `api.py` and the census rows, and
leaves #6218 open and distinct. No DTO is generated, no type is changed.

## Open questions for specify/plan

- Q-001: Should the census also pin the *facade* `__all__` sets, or is
  `facades:`-per-symbol plus the existing identity gate sufficient? Decision
  taken in favour of the latter (no gate duplication, NFR-004); revisit only if
  a facade advertises a surface symbol it does not actually re-export.
- Q-002: Does adding a docs page (`docs/architecture/…`) pull in the
  docs-freshness index? Plan: regenerate only the retrieval index
  (`python -m scripts.docs.docs_index --write`) and verify with
  `check_docs_freshness --ci`; no full CLI-reference rebuild (shared-cache
  hazard, 20 agents on this host).
