# Implementation Plan: Op Records Stop Naming A Model, And Carry The Operator's Attribution

**Branch**: `kitty/mission-op-record-model-and-coauthor-01M6EJV5` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/op-record-model-and-coauthor-01M6EJV5/spec.md`
**Input**: Mission specification from `kitty-specs/op-record-model-and-coauthor-01M6EJV5/spec.md`

## Summary

Two changes to the same seam — the Op-record lifecycle in
`src/specify_cli/invocation/`:

1. The v2 `started` event stops carrying a model identifier. `OpStartedEvent`
   loses `model_id`; `ProfileInvocationExecutor.invoke()` stops filling it from
   the router's catalog-winning recommendation. Historical records keep their
   bytes (the archive-preservation gate forbids rewriting them) and keep parsing
   because the model ignores keys it does not declare.
2. The Op auto-commit stops dropping attribution. The commit message built in
   `_commit_op_record` gains the operator's `Co-Authored-By` trailer, resolved
   once from `.kittify/config.yaml` (`commit.co_author`) or passed explicitly by
   the caller (`profile-invocation complete --co-author`, and the executor
   argument underneath it), with a visible refusal when the configured value is
   malformed.

The knock-on effect of (1) is handled explicitly rather than papered over: the
dispatch→claim seam used the Op's `model_id` as its durable evidence for a
resolved model actual. With no model on the Op, a `--model` assertion has
nothing to correlate against, so it is refused with an actionable message and
the claim records the already-defined explicit-absent sentinel
(`RESOLVED_MODEL_ABSENT`) instead of fabricating a value.

## Technical Context

**Language/Version**: Python 3.11 (repository floor; `requires-python` in `pyproject.toml`), Typer + Pydantic v2
**Primary Dependencies**: pydantic v2 (event models), typer (CLI), ruamel.yaml `YAML(typ="safe")` (the `.kittify/config.yaml` read path already used by `review/test_timeout.py`)
**Storage**: `kitty-ops/<ULID>.jsonl` (append-only Op journal, committed), `kitty-ops/op-closures.jsonl` (append-only closure spine), `.kittify/config.yaml` (project configuration)
**Testing**: pytest; the mission adds red-first tests at `tests/specify_cli/invocation/test_op_commit_attribution.py` and updates `tests/specify_cli/invocation/test_record.py`, `tests/specify_cli/invocation/test_executor.py`, `tests/specify_cli/status/test_resolved_binding_linkage.py`
**Target Platform**: cross-platform CLI (Linux, macOS, Windows); git 2.x required
**Project Type**: single Python package + CLI
**Performance Goals**: trailer resolution adds at most one YAML read per auto-commit attempt and no subprocess; the NFR-002 bound is structural (one read, zero new git calls)
**Constraints**: no rewrite of any pre-existing `kitty-ops/<ULID>.jsonl` (C-001); v2 record shape otherwise unchanged (C-002); configuration is additive and optional (C-003)
**Scale/Scope**: ~8 source files, 4 test files, 3 doc surfaces plus one changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | One reader for the configured trailer (`specify_cli/git/commit_attribution.py`); one message builder (`_op_commit_kwargs` + `_commit_op_record`) so the probe and the commit cannot disagree. |
| Architectural alignment | The trailer reader lands in `src/specify_cli/git/`, beside the commit helpers it serves, and does not reach into CLI code. `invocation/` keeps owning the Op lifecycle. |
| ATDD-first | Each behaviour is driven by a failing test through the production entry point (`ProfileInvocationExecutor.invoke`, `complete_invocation`, `_resolve_dispatch_binding`, `profile-invocation complete`) before the fix. |
| ATDD / non-vacuity (tactic `acceptance-criteria-non-vacuity`) | The absence probe for `model_id` runs on the same fixture as a positive control (a legacy record that carries it); the "no trailer configured" ratchet is paired with the configured-value assertion on one fixture. |
| Terminology canon | Mission, Op, work package, trailer — no new overloaded terms. "Operator attribution trailer" is defined once, in the spec's Key Entities. |
| Nine standing orders — witness the bug | Reproduction is recorded in `research.md` from the live checkout (1,014 records carry `model_id`) before any edit. |
| Nine standing orders — no full heavy suites in mission | Only the targeted test files plus `make test-fast` are run locally; CI owns the full sweep. |
| DIRECTIVE_024 Locality of Change | Every edit is on the Op record/commit path or the one claim seam that consumed the removed field. No unrelated refactors. |

No violations, so `## Complexity Tracking` stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/op-record-model-and-coauthor-01M6EJV5/
├── plan.md                                  # this file
├── research.md                              # grounding + decisions (D1–D5)
├── contracts/op-record-attribution.md       # record shape + commit-message contract
├── spec.md
└── tasks.md                                 # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/specify_cli/
├── invocation/
│   ├── record.py            # OpStartedEvent: drop model_id
│   ├── executor.py          # invoke(): stop recording a model; _commit_op_record(): append trailer;
│   │                        # complete_invocation(): accept an explicit trailer
│   ├── writer.py            # comment only (optional-field list)
│   └── propagator.py        # docstring only (optional-field list)
├── git/
│   └── commit_attribution.py  # NEW: operator trailer resolution + validation
└── cli/commands/
    ├── profile_invocation.py  # --co-author option on `complete`
    └── agent/workflow.py      # _resolve_dispatch_binding: no model from the Op

tests/specify_cli/
├── invocation/test_op_commit_attribution.py   # NEW: trailer behaviour, end to end
├── invocation/test_record.py                  # schema: no model_id; legacy record still parses
├── invocation/test_executor.py                # invoke() writes no model identifier
└── status/test_resolved_binding_linkage.py    # claim refuses --model, records explicit-absent

docs/
├── architecture/trail-model.md      # the field list + the history ruling
├── api/configuration.md             # commit.co_author reference
├── api/profile-invocation.md        # --co-author
├── api/cli-commands.md              # regenerated by scripts.docs.build_cli_reference
└── changelog/unreleased/<pr>.fixed.md
```

**Structure Decision**: the existing single-package layout is kept. The only new
module is `src/specify_cli/git/commit_attribution.py`, next to `commit_helpers.py`
whose `safe_commit` it feeds; it is imported by `invocation/executor.py`.

## Implementation Concern Map

### IC-01 — Op record schema loses the model identifier

- **Purpose**: A record written after this change names no AI model, while every
  record written before it keeps its bytes and stays readable.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-003, C-001, C-002
- **Affected surfaces**: `src/specify_cli/invocation/record.py`,
  `src/specify_cli/invocation/executor.py` (`invoke`, `_resolve_routing_and_context`),
  `src/specify_cli/invocation/writer.py`, `src/specify_cli/invocation/propagator.py`
- **Sequencing/depends-on**: none
- **Risks**: the raw `started.get("model_id")` reads in the claim seam must be
  removed in the same slice (IC-02) or a stale attribute error appears only on a
  correlated claim; `pydantic` ignores extra keys, so a "removed field still
  parses" test can pass vacuously unless it also asserts the field is *not*
  re-serialised.

### IC-02 — The claim seam stops asserting a model it can no longer prove

- **Purpose**: Removing the field must not leave a fabricated resolved model; the
  claim path refuses a `--model` it cannot correlate and records explicit-absence.
- **Relevant requirements**: FR-003
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/workflow.py`
  (`_resolve_dispatch_binding`, `_MODEL_OPT_HELP`), the `--model` help on
  `agent tasks move-task`
- **Sequencing/depends-on**: IC-01 (the field has to be gone first)
- **Risks**: the resolved-binding contract is load-bearing for status; the
  explicit-absent sentinel already exists (`RESOLVED_MODEL_ABSENT`, SC-011 of
  that contract), so this is a documented narrowing, and must be stated in the
  PR body and changelog rather than slipped in.

### IC-03 — The auto-commit carries the operator's trailer

- **Purpose**: Every automated `op(...)` commit ends with the operator's
  `Co-Authored-By`, from configuration or from an explicit per-close value.
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-007, FR-008, NFR-002, C-003
- **Affected surfaces**: `src/specify_cli/git/commit_attribution.py` (new),
  `src/specify_cli/invocation/executor.py` (`_commit_op_record`,
  `complete_invocation`), `src/specify_cli/cli/commands/profile_invocation.py`
- **Sequencing/depends-on**: none (independent of IC-01/IC-02, and tested
  separately so a revert of either half goes red)
- **Risks**: the auto-commit is best-effort by design (#4397/#6410); a malformed
  configuration must be reported as a refusal (`OpCommitOutcome.refusal`) and
  never turn a successful close into an error, nor commit unattributed. The
  doctor sweep shares `_commit_op_record`, so the trailer lands on both paths
  through one implementation.

### IC-04 — Docs, changelog and CLI reference stay true

- **Purpose**: Operators learn the new configuration key and the history ruling;
  the generated CLI reference matches the live Typer surface.
- **Relevant requirements**: FR-004, FR-006, C-001
- **Affected surfaces**: `docs/architecture/trail-model.md`,
  `docs/api/configuration.md`, `docs/api/profile-invocation.md`,
  `docs/api/cli-commands.md`, `docs/changelog/unreleased/<pr>.fixed.md`
- **Sequencing/depends-on**: IC-01, IC-03
- **Risks**: `docs/api/cli-commands.md` is generated — regenerate it with
  `uv run python -m scripts.docs.build_cli_reference` (verified to be
  no-diff on a clean tree) and prove freshness with
  `uv run python -m scripts.docs.check_docs_freshness --ci`.
