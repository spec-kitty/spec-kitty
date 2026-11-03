---
work_package_id: "WP01"
title: "One resolved strictness for the event and the gate"
dependencies: []
planning_base_branch: "issue-7065-semantic-check-strictness"
merge_target_branch: "issue-7065-semantic-check-strictness"
branch_strategy: "Planning artifacts were generated on issue-7065-semantic-check-strictness; completed changes must merge back into issue-7065-semantic-check-strictness."
subtasks:
  - "T001"
  - "T002"
  - "T003"
  - "T004"
  - "T005"
  - "T006"
phase: "Phase 1 - Implementation"
assignee: ""
agent: ""
shell_pid: ""
history:
  - timestamp: "2026-11-03T13:10:00Z"
    agent: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP01 – One resolved strictness for the event and the gate

## Objective

Make `SemanticCheckEvaluated` record the strictness the generation gate enforces, and the
blocking decision the gate derives from it, by giving the emitter, the semantic-check
middleware and the gate one resolution path instead of three opinions.

Issue: spec-kitty/spec-kitty#7065.

## Context

- `src/glossary/events.py:655` `emit_semantic_check_evaluated` currently ends its
  strictness with `or "medium"` and derives
  `blocked = len(conflicts) > 0 and eff_str != "off"`.
- `src/glossary/middleware.py:180` `SemanticCheckMiddleware` emits that event as pipeline
  layer 2; `GenerationGateMiddleware` (layer 4) resolves the four-tier precedence chain
  and calls `should_block()`.
- `src/glossary/strictness.py` owns `Strictness`, `resolve_strictness` and
  `should_block` — the policy vocabulary this fix must reuse, not re-invent.
- `src/glossary/pipeline.py` `create_standard_pipeline` builds the layers and currently
  passes `runtime_strictness` only to the gate.

The reproduced defect, on current `main`: with `.kittify/config.yaml` set to
`glossary: {strictness: off}` and one high-severity conflict, the event records
`effective_strictness="medium"`, `blocked=true`, while `GenerationGateMiddleware`
resolves `Strictness.OFF` and does not block. A runtime `--strictness` override is
likewise absent from the event.

## Subtasks

### T001 — Red-first parity test (config `off`)

Create `tests/agent/glossary/test_strictness_parity.py` (`pytestmark = pytest.mark.fast`).
Through the public entry points only:

1. Build a repo root with `.kittify/config.yaml` containing `glossary: {strictness: off}`.
2. Build a context with a high-severity `SemanticConflict` and no
   `effective_strictness`.
3. Call `emit_semantic_check_evaluated(context=..., conflicts=[conflict], repo_root=root)`
   and `GenerationGateMiddleware(repo_root=root).process(context2)`.
4. Assert the event's `effective_strictness` equals the gate's resolved value
   (`"off"`), that `blocked` is `False`, and that `build_record(event)` accepts the payload.

This must fail on unmodified `src` (event says `medium`/`True`, gate says `off`). Record
the failing output in the mission record.

### T002 — Red-first parity test (configured `max`, runtime override, medium-severity no-block)

In the same module:

- configured `max` + low-severity conflict → event `"max"`, `blocked is True`, gate
  `Strictness.MAX` and blocks.
- configured `max` + `runtime_override=Strictness.OFF` → event `"off"` through the
  pipeline (`create_standard_pipeline(..., runtime_strictness=Strictness.OFF)`), gate
  resolves `Strictness.OFF`.
- default policy + medium-severity conflict → event `blocked is False` (the gate's
  `should_block` returns `False`), while a high-severity conflict on the same fixture
  keeps `blocked is True` (positive control).

### T003 — `resolve_context_strictness` in `src/glossary/strictness.py`

```python
def resolve_context_strictness(
    context: Any,
    *,
    repo_root: Path | None = None,
    runtime_override: Strictness | None = None,
) -> Strictness:
```

Reads `mission_strictness` and `step_strictness` from the context, loads the global
default with `load_global_strictness(repo_root)` when `repo_root` is given (else
`Strictness.MEDIUM`), and applies `resolve_strictness(...)`. Normalise enum/string
overrides through `Strictness(value)`; an unknown value falls back to `Strictness.MEDIUM`
(NFR-002) rather than raising. Then replace the inline chain in
`GenerationGateMiddleware.process` with a call to it. The gate's decisions must not change.

### T004 — `SemanticCheckMiddleware` resolves before emitting

Add `runtime_override: Strictness | None = None` to `__init__` (after `repo_root`, keyword
use only), resolve with `resolve_context_strictness(...)` in `process()` before
`_emit_semantic_check_evaluated`, store the result on `context.effective_strictness`, and
pass it to the emitter. Do not re-implement precedence here.

### T005 — `emit_semantic_check_evaluated` stops inventing policy

- Add `runtime_override: Strictness | None = None`.
- Resolution order: explicit `effective_strictness` argument → `context.effective_strictness`
  → `resolve_context_strictness(context, repo_root=repo_root, runtime_override=runtime_override)`.
  Delete the `or "medium"` fallback and the comment that justified it.
- `blocked = should_block(effective_strictness, conflicts)`.
- Keep the `hasattr(value, "value")` enum/string normalisation so the contract always gets
  `"off" | "medium" | "max"`.

### T006 — Wire the pipeline and replace the test that pinned the bug

`create_standard_pipeline` passes `runtime_strictness` to `SemanticCheckMiddleware`.
Replace `test_unresolved_strictness_is_written_as_medium` in
`tests/agent/glossary/test_event_emission.py` with a test that pins resolution-from-config
(configured `off`, no context value → event `"off"`) rather than the constant.

## Definition of Done

- The new parity tests pass; the specific repro fails on the pre-fix code.
- `uv run pytest tests/agent/glossary -q` passes.
- `uv run ruff check src/glossary tests/agent/glossary` and
  `uv run ruff format --check src/glossary tests/agent/glossary` pass.
- No test added with `skip`, `xfail`, or a weakened assertion.
