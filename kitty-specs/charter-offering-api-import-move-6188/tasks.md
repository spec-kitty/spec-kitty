# Tasks / slices — charter module entry-point seams (#6188)

Sliced by surface; each independently reviewable. Status reflects this mission's PR.

## Landed in this PR

- **S1 — Offering seam: enforce for all external consumers.** Repoint
  `src/glossary/entity_pages.py` off `charter.offering.drg.models` onto the `charter.drg`
  facade; extend `test_runtime_charter_doctrine_boundary.py` scan roots to add `src/glossary`
  and `src/mission_runtime`. Gate green (51 passed). ✅
- **S2 — Activation seam: entry point.** New `src/charter/activation/api.py` — curated identity
  re-export surface, first tranche = `read_mission_type`, `canonical_mission_type_key`. Split
  invariant: no `charter.offering` symbol. ✅
- **S3 — Activation seam: identity + split gate.** New
  `test_charter_activation_api_reexport.py` (by-identity re-export, `__all__` completeness,
  no-offering-leak). 50 passed. ✅
- **S4 — Activation seam: enforcing boundary gate (shrink-only).** New
  `test_runtime_charter_activation_boundary.py` + `charter_activation_boundary_baseline.yaml`
  (236 pre-existing reaches frozen; new FAIL / drained (stale) FAIL) + `_baselines.yaml` leaf +
  `test_ratchet_baselines.py` `_SIZE_RATCHETS` row. 3 passed. ✅
- **S5 — First activation drain tranche.** Repoint the 11
  `charter.activation.mission_type_key` consumers onto `charter.activation.api`. ✅

## Staged follow-on (owner: epic #6099 — the extraction)

- **Drain the 236 baselined activation-internal reaches** (`(file, module)` pairs across 81 files) onto `charter.activation.api`,
  growing the seam tranche by tranche (`pack_context` 25 pairs, `layer_roots` 18,
  `mission_type_profiles` 13, `charter_yaml_io` 12, `compiler` and
  `active_charter_service_builder` 10 each, `kind_vocabulary` and `invocation_context` 9 each, the
  `synthesizer.*` cluster 33 across 20 modules, …), lowering the `_baselines.yaml` count each time, until the
  baseline is empty and the gate's non-exempt set closes to zero.
- **Drain the offering seam's ticketed residuals** (#3179/#2173/#3593): the 11 lazy
  `charter.offering.*` reaches (sole-door service, override_policy, operating_procedures,
  hand_authored_overlay, runtime step contracts/projection).
- **The extraction ADR + physical split** (epic #6099) — out of scope here.
