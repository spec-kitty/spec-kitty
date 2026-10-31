# Data Model: charter resynthesize project-directive layer split

Two graph layers, one envelope, and the rules that keep them from being confused again.

## Layer

| Field | Meaning | Authored by |
|-------|---------|-------------|
| `built_in` | The shipped doctrine every project resolves: `charter.offering.drg.loader.load_built_in_graph()`. Nodes a synthesized artifact may never shadow. | the shipped package data |
| `org` | Declared organisation packs (`org_chain_graph()`), folding the built-in layer. May legitimately be overridden by the project layer (`merge_three_layers` precedence). | `.kittify/config.yaml` + org packs |
| `project` | The project's own nodes: synthesis targets, direct-write registrations, preserved overlay nodes. | the project |

**Invariant (FR-020 / EC-6, unchanged)**: a synthesis target's URN must not exist in the
**built-in** layer, and a derived edge triple must not already exist there. The invariant is
*not* widened to org or project nodes: those may be overridden by design.

## SynthesisRequest

| Field | Type | Change | Role |
|-------|------|--------|------|
| `target` | `SynthesisTarget` | — | placeholder/primary target |
| `interview_snapshot` | `Mapping[str, Any]` | — | interview answers |
| `doctrine_snapshot` | `Mapping[str, Any]` | — | doctrine text snapshot |
| `drg_snapshot` | `Mapping[str, Any]` | — (content unchanged) | **reference universe**: the URNs a target's `source_urns` may name (EC-2) and the lower layer the validation gate resolves against |
| `run_id` | `str` | — | per-run identity |
| `adapter_hints` | `Mapping[str, str] \| None` | — | adapter selectors |
| `evidence` | `EvidenceBundle \| None` | — | evidence bundle |
| `built_in_drg_snapshot` | `Mapping[str, Any] \| None` | **new, optional, last** | **built-in layer only**: the graph the FR-020 / EC-6 additive-only check runs against |

### Validation rules

1. `built_in_drg_snapshot is None` ⇒ consumers use `drg_snapshot`. This is the pre-#6768
   behaviour and keeps every existing caller, test and fixture valid (FR-005).
2. When set, it must be a graph mapping the DRG models can validate (same normalization as
   `drg_snapshot`: `schema_version`, `generated_at`, `generated_by` defaults applied).
3. It is **excluded** from `normalize_request_for_hash`: the fixture-hash function is
   documented "DO NOT change", and the built-in layer is a function of the installed CLI,
   not of project input (NFR-002).
4. Propagation: a request derived from another (`synthesize_pipeline` per-target requests,
   `resynthesize_pipeline` bounded request) forwards the field verbatim.

### Fallback

`_build_synthesis_request` sets the field from `load_built_in_graph()`. If the shipped graph
cannot be loaded (`DRGLoadError`, e.g. a source checkout without the fetched built-in pack),
the field stays `None` and behaviour is exactly the pre-fix one — the run does not fail with
an unrelated loader error here, because the existing preflight already refuses earlier with
`BuiltInPackMissing`.

## Consumer matrix

| Consumer | Layer it must read | Why |
|----------|-------------------|-----|
| `project_drg.emit_project_layer(built_in_drg=…)` | built-in | FR-020 / EC-6 additive-only |
| `orchestrator.synthesize` additive check | built-in | same |
| `resynthesize_pipeline` step 7 additive check | built-in | same |
| `_synthesis._build_synthesis_validation_callback` → `emit_project_layer` | built-in | same |
| `_synthesis._reconciliation_preview` → `emit_project_layer` | built-in | same |
| `targets.build_targets(drg_snapshot=…)` (EC-2) | reference universe | a project tactic may name a project directive |
| `validation_gate.validate(… built_in_drg …)` | reference universe | merges the overlay with what exists below it; the overlay already holds project nodes |

## Mission-artifact note

`src/charter/activation/synthesizer/manifest.py::synthesis_owned_directive_ids` keeps its
#6510 role — keeping synthesis-owned directives out of `selected_directives` so no companion
tactic is demanded for them. It is **not** the fix for #6768 and is not extended.
