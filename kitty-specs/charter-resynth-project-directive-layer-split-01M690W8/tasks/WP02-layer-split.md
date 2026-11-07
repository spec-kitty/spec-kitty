---
work_package_id: WP02
title: Split the layers at the request builder
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-005
- SC-001
- SC-004
planning_base_branch: issue-6768-charter-resynth-project-directive
merge_target_branch: issue-6768-charter-resynth-project-directive
branch_strategy: Planning artifacts for this mission were generated on issue-6768-charter-resynth-project-directive. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6768-charter-resynth-project-directive unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-resynth-project-directive-layer-split-01M690W8
base_commit: bd71739c2addd528f3ed6f17725584f9d96ff9dc
created_at: '2026-10-31T13:44:29.823047+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 2 - Fix
history:
- at: '2026-10-31T13:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/request.py
- src/charter/activation/synthesizer/orchestrator.py
- src/charter/activation/synthesizer/resynthesize_pipeline.py
- src/charter/activation/synthesizer/synthesize_pipeline.py
- src/specify_cli/cli/commands/charter/_synthesis.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6768'
---

# Work Package Prompt: WP02 – Split the layers at the request builder

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log
  (`specify_cli` `spec-kitty agent tasks status`). Address every item, then record what changed
  with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Make the FR-020 / EC-6 additive-only check read a genuine **built-in** layer, and keep the
project's own nodes in the **reference universe**, so `charter resynthesize --topic
directive:<PROJECT_xxx>` stops refusing its own target without breaking project references.

The design is fixed (`data-model.md`); this WP implements it and nothing more:

| consumer | layer it must read |
| --- | --- |
| `emit_project_layer(built_in_drg=…)` at every call site | built-in only |
| `targets.build_targets(drg_snapshot=…)` (EC-2) | reference universe |
| `validation_gate.validate(… built_in_drg …)` | reference universe |

## Context

- `src/specify_cli/cli/commands/charter/_synthesis.py::_build_synthesis_request` (~line 130–200)
  is where the defect lives: it fills `drg_snapshot` from `directives_for_synthesis`
  (config-activated directives, i.e. built-in + org + project) and every consumer reads it as
  "the built-in layer".
- The three additive-check consumers today:
  - `src/charter/activation/synthesizer/orchestrator.py` (`_built_in_drg_from_snapshot`, used at
    ~line 253 in `synthesize()`),
  - `src/charter/activation/synthesizer/resynthesize_pipeline.py` (`_built_in_drg_from_request`,
    used at ~line 362),
  - `src/specify_cli/cli/commands/charter/_synthesis.py::_build_synthesis_validation_callback`
    (~line 259) and `_reconciliation_preview` (~line 827).
- The reference consumers: `build_targets(...)` in `synthesize_pipeline`/`orchestrator`/
  `_synthesis`, and `validate(staging_dir, built_in_drg, org_drg=...)` in each validation
  callback.
- `charter.offering.drg.loader.load_built_in_graph()` is the one authored seam for the shipped
  graph (memoized, returns a deep copy). `DRGLoadError` is its failure mode.
- `normalize_request_for_hash` in `request.py` is documented "DO NOT change": the new field must
  not enter the hash, so every generated-artifact fixture keeps loading.

## Subtasks

### T001 — The field and the one helper

In `src/charter/activation/synthesizer/request.py`:

```python
@dataclass(frozen=True)
class SynthesisRequest:
    ...
    evidence: EvidenceBundle | None = None
    built_in_drg_snapshot: Mapping[str, Any] | None = None
```

- Document it as *the built-in layer only* — the graph the additive-only check runs against —
  and state that `None` means "use `drg_snapshot`" (pre-#6768 behaviour).
- Add `built_in_snapshot(request: SynthesisRequest) -> Mapping[str, Any]` as the single
  fallback rule, exported through `__all__` if the module has one.
- Do **not** add it to `normalize_request_for_hash`.

### T002 — Author the built-in layer

In `_build_synthesis_request`:

- Import `charter.offering.drg.loader.load_built_in_graph` (and `DRGLoadError`) lazily with the
  other imports in that function.
- Set `built_in_drg_snapshot` from `load_built_in_graph().model_dump(mode="json")`.
- Catch `DRGLoadError` and leave the field `None` (fall back to today's behaviour); do not turn
  a missing pack into a new failure mode here.
- Leave `drg_snapshot` exactly as it is: same nodes, same order, same keys. It is the reference
  universe now, not the built-in layer.
- Update the comment block so a reader learns the two roles in one place (FR-004).

### T003 — Split the CLI consumers

`_build_synthesis_validation_callback`: build **two** graphs —

- `additive_drg` from `built_in_snapshot(request)` (the emitter's `built_in_drg=` argument);
- `reference_drg` from `request.drg_snapshot` (the `validate(...)` lower layer).

Same split in `_reconciliation_preview` (the emitter call uses the additive graph; the
`reconcile_synthesis` call keeps the reference graph it has today).

### T004 — Split the library consumers

- `orchestrator.synthesize`: additive check reads `built_in_snapshot(request)`; the validation
  gate keeps `request.drg_snapshot` (plus `org_drg` as today).
- `resynthesize_pipeline`: same split in step 7.

### T005 — Propagate the field

`SynthesisRequest(...)` is reconstructed in two places; both must forward
`built_in_drg_snapshot=request.built_in_drg_snapshot`:

- `synthesize_pipeline` per-target requests,
- `resynthesize_pipeline`'s `bounded_request`.

### T006 — One stated rule, no duplicated docstrings

`_built_in_drg_from_snapshot` and `_built_in_drg_from_request` must both delegate the "which
snapshot" decision to `built_in_snapshot` rather than restating the fallback. Keep their
normalization (schema_version/generated_at/generated_by defaults) as is.

### T007 — Record the decision and the friction

`spec-kitty agent tracer-append --mission <slug> --category design-decisions --entry "…"` with
the layer matrix you implemented, and `--category tooling-friction` for anything that fought
back (for example the shared slash-command asset cache, if it hits you).

## Definition of Done

- `uv run pytest tests/charter/synthesizer/test_project_directive_layer_split_6768.py -q` is
  green, and the `p0_repro(issue=6768)` marker is removed from the T002 test (it stays as the
  regression).
- `uv run pytest tests/charter/synthesizer tests/charter -q` is green.
- `uv run mypy src/charter/activation/synthesizer src/specify_cli/cli/commands/charter` is clean.
- `uv run ruff check src/charter/activation/synthesizer src/specify_cli/cli/commands/charter`
  is clean.
- No `PROJECT_` prefix test anywhere in the fix (C-001); no edit to `project_drg.py`'s
  invariant, message or exception (C-003).

## Risks

- `SynthesisRequest` is compared/normalized in several places; adding a field with a default at
  the end is safe, changing field order is not.
- A bounded resynthesize that forgets T005 loses the new layer and quietly regresses to the old
  behaviour — the WP01 test covers exactly that path, so run it.
- `load_built_in_graph()` returns a deep copy; do not mutate it.

## Reviewer Guidance

- Check every additive-only call site reads the built-in layer and every reference call site
  keeps the universe; a single missed site leaves the defect alive on that path.
- Confirm `normalize_request_for_hash` is byte-for-byte unchanged.
- Confirm `emit_project_layer` and `validation_gate.validate` are untouched.
