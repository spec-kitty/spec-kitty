# Implementation Plan: Semantic-check strictness parity

**Branch**: `issue-7065-semantic-check-strictness` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/semantic-check-strictness-parity-01M6GRFQ/spec.md`
**Input**: Mission specification from `kitty-specs/semantic-check-strictness-parity-01M6GRFQ/spec.md`

## Summary

`emit_semantic_check_evaluated` (`src/glossary/events.py:655`) invents the policy value
`"medium"` when the caller and the context both lack a strictness, then derives
`blocked` from `len(conflicts) > 0 and strictness != "off"`. The event is emitted by
`SemanticCheckMiddleware` (pipeline layer 2), which runs before
`GenerationGateMiddleware` (layer 4) resolves strictness from the four-tier chain
(global config → mission → step → runtime). The gate stores the resolved value on the
context afterwards; the persisted event is never repaired.

The plan replaces the duplicated decisions with one resolution path:

1. A new `resolve_context_strictness(context, *, repo_root, runtime_override)` helper in
   `src/glossary/strictness.py` owns the precedence chain once.
2. `GenerationGateMiddleware.process` calls it instead of re-implementing the chain
   (identical decisions — same inputs, same function).
3. `SemanticCheckMiddleware` gains a `runtime_override` and resolves through the same
   helper *before* emitting, storing the result on `context.effective_strictness`, so
   the emitter never has to guess.
4. `emit_semantic_check_evaluated` drops the `or "medium"` fallback: an explicit
   argument wins, then a context value, then resolution through the helper (`repo_root`
   plus an optional `runtime_override`). `blocked` is computed with `should_block()` —
   the same predicate the gate applies — instead of the coarse `!= "off"` test.
5. `create_standard_pipeline` threads `runtime_strictness` into the semantic-check
   middleware so a CLI `--strictness` override reaches the event.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `spec_kitty_events` 11.x (event contract, `GlossaryStrictness`), `ruamel.yaml` (config load), Typer (glossary CLI)
**Storage**: JSONL event log under `.kittify/events/glossary/` plus `.kittify/config.yaml`
**Testing**: pytest, `fast` marker; `tests/agent/glossary/` (event emission, middleware, generation gate)
**Target Platform**: Linux/macOS CLI
**Project Type**: single project (`src/glossary/`, `src/specify_cli/`)
**Performance Goals**: no measurable change — one extra YAML read per semantic-check step when the context carries no strictness (the gate already reads it once per step)
**Constraints**: event payload contract unchanged; `Strictness` enum unchanged; gate decisions unchanged (C-002, C-003)
**Scale/Scope**: 4 production files, ~60 changed lines, plus tests and one changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The precedence chain keeps exactly one implementation (`resolve_strictness`), called from one new helper; no second copy of global/mission/step/runtime ordering. |
| ATDD-first / red-first | The defect is reproduced through the pre-existing entry point (`emit_semantic_check_evaluated` + `GenerationGateMiddleware` on a configured `off`) before the fix; that repro becomes the regression test. |
| `change-apply-smallest-viable-diff` / locality of change | The fix stays inside `glossary/strictness.py`, `glossary/middleware.py`, `glossary/events.py`, `glossary/pipeline.py`; no contract, CLI or schema change. |
| Glossary & terminology adherence | Uses the repository's three strictness values (`off`/`medium`/`max`) and says so explicitly; the issue's "high"/"low" are severities, recorded in the spec's Terms section. |
| Test discipline (DIRECTIVE_041) | Each new test guards a standing invariant: event/gate parity, runtime precedence, contract conformance. No test asserts an implementation detail. |
| Campsite cleaning | The one test that pins the bug (`test_unresolved_strictness_is_written_as_medium`) is replaced, not duplicated. |

No violations — Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/semantic-check-strictness-parity-01M6GRFQ/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Task breakdown
└── tasks/
    └── WP01-...md       # Work package prompts
```

### Source Code (repository root)

```
src/glossary/
├── strictness.py        # + resolve_context_strictness() — the single resolution path
├── middleware.py        # SemanticCheckMiddleware resolves + stores before emitting;
│                        # GenerationGateMiddleware delegates to the helper
├── events.py            # emit_semantic_check_evaluated: no "medium" constant,
│                        # blocked via should_block()
└── pipeline.py          # threads runtime_strictness into the semantic-check layer

tests/agent/glossary/
├── test_event_emission.py     # event payload parity with the gate
├── test_middleware.py         # middleware resolves and stores before emitting
├── test_generation_gate.py    # gate behaviour unchanged
└── test_pipeline_strictness_parity.py   # new: end-to-end pipeline parity

docs/changelog/unreleased/<pr>.fixed.md     # per-PR fragment
```

**Structure Decision**: single project, existing packages. No new module is created
except the parity test file; the helper joins the module that already owns
`resolve_strictness`.

## Phase 0 — Research (resolved, no external work)

| Question | Answer | Evidence |
| --- | --- | --- |
| Does the defect still reproduce on `main`? | Yes. With `.kittify/config.yaml` `glossary.strictness: off` and a high-severity conflict, the event records `effective_strictness="medium"`, `blocked=true`, while `GenerationGateMiddleware` resolves `Strictness.OFF`. | Local repro through the public entry points (`emit_semantic_check_evaluated`, `GenerationGateMiddleware`). |
| Is the issue superseded? | No. `git log -S '"medium"'` shows only #6399 (which removed the `"None"` string), no commit or PR mentions 7065. | `git log --grep=7065`, `gh pr list --search 7065` (empty). |
| Which strictness values exist? | `off`, `medium`, `max`. The issue's `high`/`low` name severities, not strictness. | `src/glossary/strictness.py`, `spec_kitty_events.glossary.GlossaryStrictness`. |
| How many callers emit this event? | One production caller: `SemanticCheckMiddleware._emit_semantic_check_evaluated`. The CLI reads the event, never writes it. | `grep -rn emit_semantic_check_evaluated src/`. |
| Is the gate the only other resolution site? | Yes for production; tests construct it directly. `glossary/attachment.py` reads `context.effective_strictness` but does not resolve. | `grep -rn resolve_strictness src/`. |

## Phase 1 — Design

### Data model

No new persisted entity. `SemanticCheckEvaluated.effective_strictness` keeps its
contract type (`off`/`medium`/`max`); only its *source* changes — the resolved policy
instead of a literal.

### Contract

```python
# src/glossary/strictness.py
def resolve_context_strictness(
    context: Any,
    *,
    repo_root: Path | None = None,
    runtime_override: Strictness | None = None,
) -> Strictness: ...

# src/glossary/events.py
def emit_semantic_check_evaluated(
    context: Any,
    conflicts: list[Any],
    effective_strictness: str | Strictness | None = None,
    repo_root: Path | None = None,
    runtime_override: Strictness | None = None,   # new, keyword-only in practice
) -> dict[str, Any] | None: ...

# src/glossary/middleware.py
SemanticCheckMiddleware(store, scope_order=None, repo_root=None, runtime_override=None)
```

Resolution order inside the emitter: explicit argument → `context.effective_strictness`
→ `resolve_context_strictness(...)`. Every branch yields a `Strictness`, so the
contract value is never fabricated.

### Concerns (inform how tasks are cut)

- **IC-01 — Single resolution path.** `resolve_context_strictness` in
  `strictness.py`; gate delegates; both keep their current decisions.
  Requirements: FR-003, FR-004. Surfaces: `strictness.py`, `middleware.py`.
- **IC-02 — Emitter honesty.** Remove the constant, derive `blocked` from
  `should_block`, keep explicit-argument precedence.
  Requirements: FR-001, FR-002, FR-005. Surfaces: `events.py`.
- **IC-03 — Wiring and proof.** Pipeline threads `runtime_strictness` into layer 2;
  red-first tests cover config `off`, config `max`, runtime override, medium-severity
  non-block, and contract conformance.
  Requirements: FR-001–FR-005, NFR-001–003. Surfaces: `pipeline.py`, `tests/agent/glossary/`.

## Phase 2 — Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Two strictness reads per step (emitter + gate) could diverge if the config file changes mid-run. | Both call the same helper; the middleware stores the resolved value and the emitter reads it, so the event and the gate consume the stored value when present. The extra config read only happens for callers that never went through the middleware. |
| A caller that relied on `blocked` meaning "a conflict exists". | The event now records the gate's decision, which is what the contract's `blocked` documents; the change is stated in the changelog fragment as a behaviour change. |
| Clarification (layer 3) resolves conflicts after the check, so `blocked` may over-report a block for a run the gate then allows. | Pre-existing and unavoidable without patching persisted events; documented in the spec's edge cases and in the changelog fragment. The mission fixes the strictness/predicate class, not clarification ordering. |
| Non-`Strictness` context values (tests pass raw strings). | Normalise through `Strictness(value)` with a `medium` fallback for unknown values (NFR-002). |
| The existing test that pins the bug (`test_unresolved_strictness_is_written_as_medium`) fails after the fix. | Replace it with the parity tests; deleting a test that asserts the defect is the intended outcome and is named in the PR body. |
