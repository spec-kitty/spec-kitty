# Implementation Plan: Coord/lane actor-identity representation cluster

**Branch**: `fix/actor-identity-representation` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/actor-identity-representation-01M2T0ER/spec.md`

## Summary

Reconcile how an acting agent's identity is represented across the claim, verdict, and
ownership surfaces so four defects stop firing: a fresh full-identity implement claim
self-rejecting (#4665), an agent review verdict attributed to the git user (#4670), a
fix-mode claim after rejection blocked by stale reviewer ownership (#4673), and
`move-task --agent` not persisting the acting identity (#3029). The technical approach is
narrow and CLI-local: reconcile the two identity representations in the CLI-owned comparison
layer (not the byte-identical shared projection), thread the claimed reviewer identity through
a single completion-command render seam plus an event-log resolver, and fix the CLI-owned
rejection-release/ownership path — leaving the shared `spec-kitty-events` reducer untouched and
filing a scoped upstream follow-up only if a residual reducer fold-ordering contribution to
#4673 is proven.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (CLI); `spec-kitty-events` (PyPI-pinned `>=9,<10`, currently 9.1.6 — **read-only external contract**, not editable here)
**Storage**: Append-only status event log (`status.events.jsonl`) reduced to a snapshot; no new storage
**Testing**: pytest (`tests/status/`, `tests/specify_cli/cli/commands/agent/`, `tests/specify_cli/cli/commands/agent/review/`), `@pytest.mark.regression` red-first per ADR 2026-07-17-1
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single (CLI library)
**Performance Goals**: no regression to CLI < 2s typical; the fix adds no new full-log reads
**Constraints**: additive-only event history (no rewrites); identity key stays a bare string (generic-actor `in` test); shared projection stays byte-identical to upstream; complexity ≤15; ruff + mypy --strict + ruff format clean, zero new suppressions
**Scale/Scope**: 4 issues, ~4–6 CLI-owned source files, one execution lane

### Key seams (grounded, file:line)

- Identity projection (byte-identical local ↔ upstream, **leave unchanged**): `src/specify_cli/status/models.py:152` `actor_identity_str` / `:119` `decode_actor`; upstream `spec_kitty_events/diary.py:236` (reduced `actor` slot written at `diary.py:1109`).
- Impl-claim comparison layer (**#4665 fix seam**, CLI-owned): `src/specify_cli/status/work_package_lifecycle.py:103` `_actor_key` / `:111` `_actors_compatible` / `:49` `GENERIC_IMPLEMENTATION_ACTORS` / claim branches `:165/:203/:231`.
- Divergent claim-emit sites (#4665 whack-a-field): compact-string claim `src/specify_cli/cli/commands/implement.py:1881` (`effective_actor`) → `_start_wp_implementation_status`; structured-dict claim `src/specify_cli/cli/commands/agent/workflow_executor.py:744` `_implement_start_claim` → `status/emit.py:1305` `build_self_asserting_actor`.
- Review role channel (reviewer-vs-implementer distinctness, NOT the identity key): `work_package_lifecycle.py:328` `review_claim_decision` (degrades to ALLOW on stale/None role).
- Completion-command render (#4670 whack-a-field, ≥5 sites): `workflow_executor.py:1960/2003/2124`, `tasks_verdict_persistence.py:893`, `tasks_transition_core.py:703` (+ help text `tasks.py`, `next_cmd.py`).
- Verdict actor resolution (#4670): `tasks_move_task.py:2122` (`st.actor = st.agent or "user"`), reviewer resolver `_mt_resolve_reviewer_identity` (used only for the rejected-cycle artifact today).
- Ownership authorities (#4673, three slots — C-006): transition `actor` (overwritten each hop); runtime `agent` released on rejection (`_CLAIM_RELEASE_SLOTS`, upstream `diary.py:1042`; move-task reads it at `tasks_move_task.py:355`, fallback `:2329`); sticky resolved-binding `role` (`_RUNTIME_SLOTS`, upstream, NOT released). Rejection re-stamp: `tasks_move_task.py` `_mt_emit_runtime_state` / `_build_claim_review_override`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter (`.kittify/charter/charter.md`) present. Relevant gates:

- **Single canonical authority** (Governing Principle; DIRECTIVE_044): the mission is unification, not parity — reconcile the two identity representations to one canonical comparison rather than adding a third. PASS by design.
- **ATDD-first / red-first** (C-011; DIRECTIVE_041/034; ADR 2026-07-17-1): each defect lands an issue-pinned `@pytest.mark.regression` RED on the WP's `planning_base_branch`, GREEN after (NFR-003). PASS — encoded per WP.
- **Architectural alignment / shared-package boundary** (DIRECTIVE_001; shared-package ADR 2026-04-25-1): `spec-kitty-events` is a read-only external contract; no vendoring or editing (C-001/C-005). PASS.
- **Reviewer ≠ implementer** (Standing Order #8): each WP reviewed by a distinct role; issue-matrix row + verdict per issue. PASS — process.
- **Terminology canon** (Mission not Feature): no new user-facing `feature*` identifiers; error/help strings use `--mission`. PASS — reviewer greps changed lines.
- **No version numbers in scope** (DIRECTIVE_045): none introduced. PASS.
- **Locality of change / smallest-viable-diff** (DIRECTIVE_024/025; RECONCILE_CHANGE_SCOPE_TENSIONS): fix at the CLI comparison/render/ownership seams; do not refactor the reducer or the projection. PASS.

No violations to justify in Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/actor-identity-representation-01M2T0ER/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (behavioral contracts)
├── traces/              # tooling-friction / approach / design-decisions
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── status/
│   ├── models.py                     # actor_identity_str/decode_actor — LEAVE UNCHANGED (C-005)
│   ├── work_package_lifecycle.py     # WP01: _actor_key/_actors_compatible reconciliation; WP03: rework claim
│   └── emit.py                       # build_self_asserting_actor (claim-emit shape)
└── cli/commands/
    ├── implement.py                  # WP01: route workspace-create claim through the canonical actor shape
    └── agent/
        ├── workflow_executor.py      # WP01: _implement_start_claim; WP02: completion-command render seam
        ├── tasks_move_task.py        # WP02: verdict actor resolution; WP03: rejection-release/ownership; WP04: --agent persistence
        ├── tasks_verdict_persistence.py  # WP02: render/verdict actor
        └── tasks_transition_core.py  # WP02: render; ownership guard (read-only reference)

tests/
├── status/                                   # WP01/WP03 unit + reducer-adjacent
└── specify_cli/cli/commands/agent/           # WP01/WP02/WP03/WP04 integration
    └── review/                               # WP02 review claim→handoff→completion
```

**Structure Decision**: Single CLI library. All edits are CLI-owned modules under
`src/specify_cli/`. The shared `spec-kitty-events` reducer and the byte-identical projection
helper are explicitly out of the editable set (C-001/C-005).

## Complexity Tracking

No Constitution Check violations — table intentionally empty.

## Parallel Work Analysis

### Dependency Graph

```
WP01 (#4665 identity-key reconciliation) ──► WP02 (#4670 reviewer attribution)
        │                                 └─► WP03 (#4673 fix-mode ownership)
        └───────────────────────────────────► WP04 (#3029 move-task --agent persistence)
```

WP01 defines the reconciled identity semantics the others consume, so it lands first.

### Work Distribution — expect ONE lane (honest collapse)

`finalize-tasks` unions WPs into lanes by **owned-file OVERLAP**, not dependency. The overlap
graph is fully connected: WP01↔WP03 share `work_package_lifecycle.py`; WP02↔WP03↔WP04 share
`tasks_move_task.py`; WP01↔WP02 share `workflow_executor.py`. **Therefore all four WPs collapse
into a single lane and execute serially** in dependency order WP01 → {WP02, WP03, WP04}. This is
authored deliberately — do NOT declare parallel lanes that finalize will merge anyway (avoids the
post-finalize planning-sha staleness footgun). No cross-lane coordination points exist because
there is one lane.

### Coordination Points

- Single lane ⇒ no inter-lane sync. Each WP is a distinct commit (or small commit set) with its
  own red-first regression, reviewed independently (reviewer ≠ implementer).
- WP04 (#3029) begins with a live re-verification on the base; if the behavior is already green,
  it lands a characterization regression + evidence and closes #3029 rather than changing code.
