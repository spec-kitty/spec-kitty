# Discovery Research: charter resynthesize project-directive layer split

Mission: `charter-resynth-project-directive-layer-split-01M690Q7`
Issue: [#6768](https://github.com/spec-kitty/spec-kitty) (P0)
Grounded on `origin/main` at `d75e0bc5` (2026-10-31).

## Decision 1 — The defect reproduces on current main, and not through the path #6510 closed

**Decision**: treat #6768 as open and distinct from the closed #4226 / #6510.

**Evidence**: reproduction through the real CLI on a "synthesized once" fixture project
(the fixture shape of `tests/charter/synthesizer/test_resynthesis_after_activation_6510.py`):

1. author `.kittify/charter-packs/directive/007-local-guardrail.directive.yaml` (`id: PROJECT_007`);
2. `charter activate directive 007-local-guardrail --no-compile` (registers it as
   `adapter_id: project-direct-write`, which by design is *not* synthesis ownership);
3. author `.kittify/charter/generated/tactics/how-we-apply-project-007.tactic.yaml`;
4. `charter resynthesize --topic directive:PROJECT_007`.

Result (exit 1):

```text
Project DRG validation failed (1 error(s)): Additive-only violation (FR-020 / EC-6):
URN 'directive:PROJECT_007' is already present in the synthesis input graph. ...
built_in_nodes=1, colliding_urn='directive:PROJECT_007'
```

The #6510 fix (`synthesis_owned_directive_ids`, commit `f5413ee0c5`) only drops
*synthesis-owned* ids from the snapshot, so an activated project-authored directive still reads
as built-in. `owned_ids` is an ownership filter layered on a mis-classified snapshot.

**Supersession check**: `git log -S "synthesis_owned_directive_ids"` and the `[Unreleased]`
changelog show #6510 as the last change to this area; no ADR or merged PR reclassifies the
layers. Issue #6768 is assigned to nobody and `status:triage` before this Mission claimed it.

## Decision 2 — The snapshot is doing two jobs; split them at the request builder

**Decision**: `_build_synthesis_request` will author **two** inputs instead of one:

- the **built-in layer** for the FR-020 / EC-6 additive-only check, built from the shipped DRG
  (`charter.offering.drg.loader.load_built_in_graph()`);
- the **reference universe** (EC-2 source-URN validation and the pre-write validation gate),
  which keeps today's content: the config-activated directives (built-in, org and project).

**Evidence**:

- All three additive-check call sites read `request.drg_snapshot` as "the built-in layer":
  `orchestrator._built_in_drg_from_snapshot` (`orchestrator.py:253`),
  `resynthesize_pipeline._built_in_drg_from_request` (`resynthesize_pipeline.py:533`), and
  `_synthesis._build_synthesis_validation_callback` / `_reconciliation_preview`
  (`_synthesis.py:259`, `:827`).
- The same snapshot is the EC-2 universe: `targets.build_targets(... drg_snapshot=...)` →
  `_validate_source_urns` ("does not exist in the built-in DRG snapshot"). Draining it of
  project nodes is exactly the half-fix the issue records as failing on tactic references.
- The repo already separates these roles elsewhere: `targets._shipped_drg_urns` (#6442) and
  `validation_gate._with_shipped_endpoints` / `below_project_base` both fold the *shipped*
  graph in rather than trusting the selection list. The layer split follows that precedent.
- `emit_project_layer`'s own contract already says additive-only is built-in-only and that an
  **org** node may legitimately be overridden by the project layer while a built-in may not —
  so the built-in layer, not the activated list, is the correct input there.

## Decision 3 — New request field, absent means unchanged

**Decision**: add `SynthesisRequest.built_in_drg_snapshot: Mapping[str, Any] | None = None`.
`None` means "use `drg_snapshot`" (pre-fix behavior), so every existing caller, test and
fixture keeps its semantics.

**Evidence**: `normalize_request_for_hash` is documented "DO NOT change this function" because
fixture paths key off it; leaving the new field out of that normalization keeps every
generated-artifact fixture loading unchanged (NFR-002).

## Decision 4 — Keep the #6510 ownership filter; do not extend the prefix heuristic

**Decision**: `_directive_synthesis_inputs` keeps excluding synthesis-owned ids from
`selected_directives` (so synthesis does not demand a companion tactic for its own directive).
The collision itself is fixed by the layer split, not by any `PROJECT_` prefix test — the
issue's session-local patch used a prefix and is explicitly not the fix (C-001).

## Open questions carried into planning

1. Should the reference universe *also* add the shipped built-in nodes that are not activated?
   Not required by this issue (EC-2 already passes today); folding them in would change the
   fixture hash, so it is out of scope here and recorded as such.
2. `collision_remedy`'s "activated project directive that synthesis did not create" branch
   becomes unreachable through this path. Keep it as defensive classification (it still
   describes a real state if another emit path passes a project node as built-in); no wording
   change in this Mission.
3. Should the additive-only check also refuse shadowing an **org** node? Currently it does
   (org directives are in the activated snapshot) while `emit_project_layer`'s docstring says
   org may be overridden. The split narrows the check to built-in-only, matching the documented
   contract; the org question is a separate decision and stays out of this P0 fix.
