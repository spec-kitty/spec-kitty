# Implementation Plan: Bound review_ref at the WPStatusChanged wire projection

**Branch**: `issue-3954-review-ref-wire-bound` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/review-ref-wire-bound-01M2QNMY/spec.md`

## Summary

`move-task`/`emit_status_transition` transitions carrying a legacy-prose `review_ref` longer than 240 UTF-8 bytes make the pinned events codec raise `ZeitgeistAttrsOverflowError`, which `zeitgeist_bridge._broadcast_moment` catches and turns into a whole-moment drop (0 offers). This mission adds one minimal, pointer-biased bound on `review_ref` inside `_broadcast_status_transition`, **before** `to_zeitgeist_attrs` runs, so a prose note is collapsed to one line and truncated to ≤240 UTF-8 bytes with a trailing `…` (byte-identical to the codec's own `_truncate_utf8`), while pointer-shaped values ride through verbatim. The canonical local status event log is untouched (the bridge has no journal write path; the journal append precedes fan-out). This is an MVP interim; the structural fix (`summary` attr + `review_ref` pointer-only) is #4327/#4336, kept separate.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `spec-kitty-events` (pinned `>=9,<10`, resolves 9.1.6 — codec `spec_kitty_events.zeitgeist_attrs`; consumed, never edited), pydantic (payload models).
**Storage**: append-only `status.events.jsonl` (canonical local log — read-only for this mission; must remain full-fidelity).
**Testing**: pytest; black-box through the pre-existing CLI (`spec-kitty agent tasks move-task`) and the pre-existing `emit_status_transition` seam; `@pytest.mark.regression`, RED-first (ADR 2026-07-17-1).
**Target Platform**: Linux/macOS CLI.
**Project Type**: single project (CLI).
**Performance Goals**: no added network offer or Git deadline vs a normal broadcast (NFR-003).
**Constraints**: 240-**byte** per-attr bound (relay-enforced, C-001); codepoint-safe; events pin unchanged; single seam only (C-002/C-003).
**Scale/Scope**: one source file (`src/specify_cli/status/zeitgeist_bridge.py`) + its tests. ~1 WP.

## Constitution / Charter Check

*GATE: must pass before implementation; re-check after design.*

- **Single canonical authority**: the bound lives in exactly one helper in `zeitgeist_bridge.py`; no duplication into `tasks_move_task.py`/`emit.py`/codec (C-003). PASS.
- **Architectural alignment (client-repo inversion)**: the events codec is an upstream client dependency; the CLI-side bound respects that boundary (C-002). PASS.
- **DDD tiered rigour**: a small, deterministic pure-function seam (bound + classify) with focused unit tests + e2e — proportional to a single-seam interim. PASS.
- **ATDD-first / red-first**: every defect path lands an issue-pinned `@regression` repro RED through the pre-existing entry point before the fix; transitional repros become focused unit tests after (SO#9). PASS by design (see Test Plan).
- **Terminology**: "moment", "status commit"; no "sync"/"ceremony"/"feature". PASS.
- **Interim discipline**: `# SUNSET: remove when #4327 lands`, `refs #3954`, INFO log, PR-body panel note (FR-008). PASS.

No violations → Complexity Tracking empty.

## Design

### Change site
`src/specify_cli/status/zeitgeist_bridge.py` → `_broadcast_status_transition` (payload construction, ~L169). Introduce the bound where `review_ref` is read from `metadata.review_ref`, feeding the bounded value into `StatusTransitionPayload`. All downstream (`_broadcast_moment` → `to_zeitgeist_attrs`) is unchanged; the codec now receives an already-bounded prose value and no longer overflows.

### The helper (behavioral contract — see `contracts/review_ref_bound.md`)
A pure function `_bound_wire_review_ref(value: str | None) -> str | None`:
1. `None`/empty → return unchanged.
2. **Classify** (pointer-biased, structural, KISS — no regex sentence detection): value is a POINTER (⇒ return verbatim) iff it is whitespace-free and matches `<verb>:<id>` / URI-scheme, OR it contains a path separator and no line break. Otherwise it is PROSE.
3. **Prose path**: collapse whitespace (`" ".join(value.split())`) FIRST (removes newlines/tabs before the byte check and before the codec's printable guard); if the collapsed value is ≤240 UTF-8 bytes, return it; else truncate codepoint-safe to a 237-byte prefix + `…` (byte-identical to the codec's `_truncate_utf8`) and emit an INFO log.

Scope guard: the helper touches only `review_ref`; every other attr still reaches the codec unbounded (T8 — codec fail-closed unchanged).

### Data model (review_ref shapes)
- **Pointer**: `review:WP04`, `approval:WP04`, `auto-approval:WP04:2026-09-17`, a URI, or a path (incl. a path with spaces). → verbatim.
- **Prose**: a free-text `--note`. → collapse + bound.

## Project Structure

```
src/specify_cli/status/zeitgeist_bridge.py     # the one change site (+ helper, + #4318 docstring campsite)
tests/status/test_zeitgeist_moment_handler.py  # extend: seam-unit tests (bound/classify/offer-count)
tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py  # NEW: e2e through move-task
kitty-specs/review-ref-wire-bound-01M2QNMY/
├── plan.md
├── research.md            # points to the ratified squad brief
└── contracts/review_ref_bound.md   # the helper's input→output contract table
```

**Structure Decision**: single project; one source file + two test files. No new modules, no package moves.

## Test Plan (ATDD matrix → tasks)

8 issue-pinned `@pytest.mark.regression`, RED-first, black-box; byte assertions use `len(v.encode("utf-8")) <= 240`.

| ID | Family / case | Entry point | Key assertion |
|----|---------------|-------------|---------------|
| T1 | approval, >240B multi-line prose | `move-task --to approved --note` | 1 offer; wire review_ref ≤240B, one-line, `…`; INFO log; full note in `status.events.jsonl` |
| T2 | completion (multi-hop) | `move-task --to done` | exactly one offer per emitted event |
| T3 | rejection/rework | `move-task --to doing --note` | bounded broadcast, 1 offer |
| T4 | direct emission | `emit_status_transition` (clock-derived `at=`) | bounded broadcast |
| T5 | over-bound pointer (space-in-path) | seam-unit | rides verbatim; codec fails closed loudly if rejected |
| T6 | codepoint boundary | seam-unit | multi-byte char never split; `…` budget honored |
| T7 | exactly-one-offer single-hop | seam-unit | 1 offer |
| T8 | over-bound non-review_ref attr | seam-unit | untouched → codec fail-closed unchanged |

Homes: seam-unit → `tests/status/test_zeitgeist_moment_handler.py`; e2e → new `tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py`.

## Complexity Tracking

*No Constitution/Charter violations — none.*

## Parallel Work Analysis

Not applicable — single seam, single WP, no parallel streams.
