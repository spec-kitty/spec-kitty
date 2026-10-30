# Implementation Plan: Agent String Parser Hardening

**Branch**: `issue-6755-agent-string-parser-hardening` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: `kitty-specs/agent-string-parser-hardening-01M6699F/spec.md`
**Audience**: software-engineer and automation-agent.

## Summary

Deliver #6755 in one bounded WP01: `parse_agent_boundary_string` (src/specify_cli/status/models.py) strips every segment, treats a segment that is blank after stripping as absent (`None`; the tool segment as the existing empty-tool `ValueError`), and raises `ValueError` for a value with more than four segments. The three explicit `--agent` paths (`move-task`, `mark-status`, `add-history`) already convert a parser `ValueError` into the existing clean `Invalid --agent value: <reason>` refusal before any write, so no call-site change is needed; the lenient free-text paths pre-check the segment count or catch `ValueError` and keep storing the value whole (#6400 contract). #2861's thin, non-synthesizing bare-tool rule is untouched.

Engineering alignment is confirmed by the operator's task instructions and the issue body: Python repository, existing status/CLI authority, red-first verification through the pre-existing entry points, targeted test surface, PR only. No technology or interview decision remains open.

## Technical Context

**Language/Version**: Python 3.11+; repository CLI `spec-kitty` 4.0.0rc8
**Primary Dependencies**: Existing typer/rich CLI; no additions, upgrades or removals
**Storage**: Existing status event log and structured actor dict (`{tool, role, profile, model}`); no schema change
**Testing**: Existing pytest entry points — `tests/status/test_actor_boundary_normalize.py` for the parser rows, the #6400 CLI refusal tests under `tests/specify_cli/cli/commands/agent/` for the three explicit paths; failing-first commit before the production fix
**Target Platform**: Existing Linux/macOS/Windows CLI
**Project Type**: Single existing Python CLI repository
**Performance Goals**: None added; the parser is O(segments) and stays trivial
**Constraints**: One refusal message envelope (`Invalid --agent value: <reason>`); lenient paths keep whole-value storage; no synthetic defaults; new/changed-line coverage ≥90% (diff-cover); mypy --strict clean; no full heavy suite locally
**Scale/Scope**: One issue, one WP; `src/specify_cli/status/models.py` plus tests and the changelog

## Charter Check

*Entry and post-plan review: pass; no new architecture or dependency decision.*

- Canonical authority: the fix lives in the one owning parser; no second segment-count check or parser copy (NFR-001). Supply-chain controls not applicable: no dependency decision.
- ATDD first: failing tests through the pre-existing parser and CLI entry points, committed RED before the production fix (FR-004).
- Locality: candidate files `src/specify_cli/status/models.py` and the two test files; no unrelated cleanup. Opening campsite check: the function is 9 lines, single-purpose, already isolated — recorded no-enabler conclusion in traces.
- Mission hygiene: three tracer files seeded at planning; issue-matrix row for #6755 with claim recorded; reviewer distinct from implementer.
- Git: current/base/mission branch `issue-6755-agent-string-parser-hardening`; PR to `main` only; NO merge, no auto-merge, no push to `main`.
- Terminology: "compact agent string", "structured actor", "lenient builder" keep their #6400/#2861 meanings.

## Project Structure

### Documentation (this mission)

```text
kitty-specs/agent-string-parser-hardening-01M6699F/
├── spec.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── reasons-canvas.md
├── data-model.md
├── quickstart.md
├── contracts/agent-boundary-parser.md
├── traces/
│   ├── approach.md
│   ├── design-decisions.md
│   └── tooling-friction.md
└── tasks.md              (created by /spec-kitty.tasks)
```

### Source Code (repository root)

```text
src/specify_cli/status/
├── models.py             # parse_agent_boundary_string (the fix)
└── actor.py              # read-only: verified lenient pre-checks and fallbacks

tests/status/
└── test_actor_boundary_normalize.py       # parser rows (red-first)

tests/specify_cli/cli/commands/agent/
├── test_structured_actor_annotations_6400.py   # add-history / mark-status refusals
└── test_move_task_structured_actor_6400.py     # move-task refusal
```

**Structure Decision**: single existing Python CLI repository; only the owning parser module changes, tests land beside their existing #6400/#2861 counterparts.

## Complexity Tracking

No Charter Check violations to justify.

## Implementation Concern Map

One concern; not decomposed further (single-WP mission).

### IC-01 — Parser hardening and its blast radius

- **Purpose**: Make the compact parser's segment handling truthful (strip, blank-is-absent, refuse >4 segments) without changing any call-site contract.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004; C-001, C-002, C-003.
- **Affected surfaces**: `src/specify_cli/status/models.py`; tests as listed above.
- **Sequencing/depends-on**: none.
- **Risks**: a caller that silently relied on truncation — ruled out by the call-site survey in [research.md](research.md) (all direct callers either refuse, pre-check, or catch `ValueError`).
