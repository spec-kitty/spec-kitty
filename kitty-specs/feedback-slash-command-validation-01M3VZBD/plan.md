# Implementation Plan: Feedback slash command and input hardening

**Branch**: `feat/in-harness-feedback-survey` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/feedback-slash-command-validation-01M3VZBD/spec.md`

## Summary

Add `/spec-kitty.feedback`, an on-demand command that has the agent ask the feedback questions through the harness question UI and submit through the existing hidden handshake with the already-defined `on_demand` trigger (not subject to the weekly throttle, so no new flag is needed). Harden the one shared validator in `payload.py` (strict rating, sanitized comment, strict email) and state the 2000-character comment limit in the comment prompt text, built from `COMMENT_MAX_LENGTH`, so every flow shows it before the user types.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: standard library only (`re`, `unicodedata`); existing `typer`, `rich` untouched
**Storage**: N/A (no new state; `feedback.json` unchanged)
**Testing**: pytest, red-first; shared parametrized input table run through the validator, terminal form, inline hook and `agent_submit`; command generation tests for all 17 agent surfaces
**Target Platform**: macOS, Linux, Windows (CLI plus 13 slash-command and 4 Agent Skills agents)
**Project Type**: single (CLI package)
**Performance Goals**: validation of one submission under 10 ms p95
**Constraints**: no new egress, `ALLOWED_KEYS` unchanged, complexity at most 15, coverage at least 90%, mypy strict and ruff clean
**Scale/Scope**: one new command, three hardened parsers, one wording change

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status |
|------|--------|
| Single canonical authority (validator stays in `payload.py`, wording in `wording.py`) | Pass |
| ATDD red-first | Pass (tests written before code, per WP) |
| Edit pack source, never agent copies | Pass |
| Terminology (Mission, no `feature*` aliases) | Pass |
| Egress consent boundary unchanged | Pass (no new call, same single consented request) |
| Layer rule (`feedback` stays inside `specify_cli`) | Pass |
| Vendor-neutral wording | Pass |
| Targeted tests only, one `make test-fast` after consolidation | Pass |

Post-design re-check: no violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/feedback-slash-command-validation-01M3VZBD/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── agent-check-on-demand.md
└── tasks.md             # created later by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/feedback/
├── payload.py           # harden parse_rating / normalize_comment / parse_email
├── wording.py           # comment prompt states the limit (from COMMENT_MAX_LENGTH)
├── agent_protocol.py    # on_demand check path, structured errors
├── terminal_form.py     # uses the updated wording and parsers
└── hooks.py             # inline prompts use the updated wording
src/specify_cli/shims/registry.py   # register "feedback" consumer skill
packs/built-in/...                  # SOURCE prompt for /spec-kitty.feedback
tests/specify_cli/feedback/                     # red-first tests, shared input table
docs/                               # CLI reference and give-feedback guide refresh
```

**Structure Decision**: single project; changes stay inside `src/specify_cli/feedback/` plus the command registry and the pack source prompt.

## Implementation Concern Map

### IC-01 — Hardened shared validator

- **Purpose**: Make rating, comment and email validation strict and sanitized in one place.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-009, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, NFR-001, NFR-002, NFR-003
- **Affected surfaces**: `src/specify_cli/feedback/payload.py`, `agent_protocol.py`, `terminal_form.py`, `hooks.py`, tests
- **Sequencing/depends-on**: none
- **Risks**: Over-stripping legitimate text (keep markup and ordinary Unicode); email rules too strict or too loose; the cleaner must never split a character at the limit.

### IC-02 — Limit shown before typing

- **Purpose**: State the 2000-character limit in every comment prompt before input.
- **Relevant requirements**: FR-010, FR-011, NFR-006
- **Affected surfaces**: `src/specify_cli/feedback/wording.py`, `terminal_form.py`, `hooks.py`, `agent_survey_payload()`
- **Sequencing/depends-on**: none (independent of IC-01)
- **Risks**: Wording tests that pin the old comment question text; the limit must come from `COMMENT_MAX_LENGTH`, never a literal.

### IC-03 — On-demand command

- **Purpose**: Provide `/spec-kitty.feedback` for every supported agent.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, SC-006
- **Affected surfaces**: pack source prompt, `src/specify_cli/shims/registry.py`, command installers and generated-surface checks, CLI-reference and completion-manifest freshness artefacts, doctrine graph check
- **Sequencing/depends-on**: IC-01 and IC-02 (the prompt relies on the structured errors and wording)
- **Risks**: Command classification sets must stay disjoint; visible-CLI-count test band; agent copies must come only from generation.

### IC-04 — Docs and verification

- **Purpose**: Update the user guide, context doc and changelog; run targeted gates.
- **Relevant requirements**: C-004, C-006, NFR-004, NFR-005
- **Affected surfaces**: `docs/guides/how-to/collaboration/give-feedback.md`, `docs/context/feedback.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: Vendor names leaking into docs; stale references to the old comment question.
