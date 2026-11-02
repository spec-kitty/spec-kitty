# Implementation Plan: dispatch `--brief` governance payload

**Branch**: `issue-6990-dispatch-brief-governance-payload` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/dispatch-brief-governance-payload-01M6BV2S/spec.md`

## Summary

Add an opt-in `spec-kitty dispatch --brief` mode. It keeps every routing and
orientation field, replaces the re-embedded governance text with a digest
(hash, bytes, lines) plus an exact fetch command, and prints the same reference in
console mode instead of the ~24 KB panel. Because most of the payload is
profile-cited doctrine, `spec-kitty charter context` gains `--profile <id>` so
the printed fetch command reproduces the omitted text byte-for-byte. Default
output is unchanged.

The saving is prompt tokens, not compute: the executor still assembles the
governance context on every dispatch (spec NFR-002/C-002).

## Technical Context

**Language/Version**: Python 3.11 (repo `.python-version`)
**Primary Dependencies**: typer/click (CLI), rich (console rendering), pytest
**Storage**: N/A — the reference is computed from the payload in memory; the Op
record (`kitty-ops/<id>.jsonl`) is written exactly as today
**Testing**: pytest; `tests/specify_cli/invocation/cli/test_dispatch.py` (patches
`build_charter_context`, drives the real Typer app) plus the charter-context CLI
tests
**Target Platform**: CLI, all supported hosts
**Project Type**: single Python package (`src/specify_cli/`)
**Performance Goals**: brief `--json` envelope ≤ 10% of the baseline 24,983-byte
envelope; no extra `build_charter_context` call per dispatch
**Constraints**: default output byte-identical; no gate weakened; no new state
file, no session detection
**Scale/Scope**: 2 command modules + their tests + docs/changelog

## Charter Check

- **Single canonical authority / DIRECTIVE_044**: the fetch command prints the
  canonical `spec-kitty charter context` surface, not a bespoke reader; no second
  rendering path is introduced.
- **ATDD-first / DIRECTIVE_034**: the red-first tests drive the real `dispatch`
  and `charter context` Typer commands.
- **Locality of change / DIRECTIVE_024**: edits stay in
  `src/specify_cli/cli/commands/dispatch.py` and
  `src/specify_cli/cli/commands/charter/context.py`; the executor and payload
  contract are untouched.
- **Terminology canon**: "payload", "governance context", "Op" are used in their
  existing sense; no new domain term is coined.
- **Pre-existing Failure Reporting Rule**: any red outside this diff is
  reproduced on pristine `main` and cited in the PR's `## Deferred`.
- **Terminology guard**: user-facing prose changes, so
  `tests/architectural/test_no_legacy_terminology.py` runs before push.

## Project Structure

### Documentation (this mission)

```
kitty-specs/dispatch-brief-governance-payload-01M6BV2S/
├── plan.md              # This file
├── research.md          # Discovery findings (D1–D5)
├── spec.md              # Requirements and success criteria
├── tasks.md             # Work packages
└── tasks/               # Per-WP task files
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
├── dispatch.py                      # + --brief: reference block, console render
└── charter/context.py               # + --profile: profile-cited sections

tests/specify_cli/invocation/cli/
└── test_dispatch.py                 # brief JSON/console/dry-run, default unchanged

tests/specify_cli/cli/               # (existing charter context CLI tests)
└── test_charter_context*.py         # --profile renders profile-cited sections

docs/
├── api/cli-commands.md              # regenerated help blocks for both commands
├── architecture/governed-profile-invocation.md
└── changelog/CHANGELOG.md           # [Unreleased] entry (#6990)

src/charter/offering/skills/spec-kitty/SKILL.md   # standalone dispatch guidance
```

## Phase 0 — Outline & Research

`research.md` already records the decisions from grounding:

- **D1** the issue still reproduces (24,983 B envelope, 23,668 B text).
- **D2** rejected session-state suppression; chose the deterministic `--brief`
  flag.
- **D3** the fetch command must name the profile: 18.7 KB of the 23.7 KB is
  profile-cited doctrine, and `charter context` cannot render it today.
- **D4** the printed action must be the payload's own action (role-default-verb
  derivation gives `generate`, not `implement`).
- **D5** brief mode is a command-layer rendering concern; the executor and
  `InvocationPayload` stay untouched.

## Phase 1 — Design

### Interface: `spec-kitty dispatch --brief`

```text
$ spec-kitty dispatch "implement the login handler" --profile python-pedro --json --brief
{
  "profile_id": "python-pedro",
  "action": "generate",
  ...
  "governance_context_text": null,
  "governance_context_hash": "…",
  "governance_context_available": true,
  "governance_context_reference": {
    "digest": "…",
    "bytes": 23668,
    "lines": 308,
    "fetch_command": "spec-kitty charter context --action generate --profile python-pedro"
  },
  "status": "open",
  "close_contract": { … }
}
```

Console mode replaces the "Governance Context" panel with:

```text
Governance context: digest <hash> (23668 bytes, 308 lines) — not re-embedded (--brief)
  Fetch the full text: spec-kitty charter context --action generate --profile python-pedro
```

Rules:

- `governance_context_text` becomes `null` **only** when governance text exists
  and a fetch command can reproduce it (spec C-002). When the context is
  unavailable (`mode == "missing"`) or the text is empty, brief mode changes
  nothing but the existing "unavailable" signal.
- `governance_context_reference` is present only in brief mode, so no non-brief
  envelope grows (C-003).
- `--brief` composes with `--dry-run`; the dry-run envelope gets the same
  substitution and still writes nothing.
- The ambiguous dry-run payload has no governance text; it is untouched.
- The Op record, glossary scan, recommendation and router behaviour are
  unchanged — the record still stores the same `governance_context_hash`.

### Interface: `spec-kitty charter context --profile <id>`

- New `--profile` typer option, passed to `build_charter_context(profile=…)` for
  the text render and to the `--json` payload's `text`/`context` fields.
- Unknown profile: the existing `_load_agent_profile` miss path renders without
  profile sections and warns; it does not fail the fetch.
- Structured `--json` blocks (`directives`, `tactics`, …) are DRG projections and
  stay profile-agnostic; only the rendered text is profile-aware.

### Contracts

No new file under `contracts/`: the brief block is documented in
`docs/api/cli-commands.md` (regenerated help), the skill, and the architecture
page, and the existing `contracts/` note for `cli-do-output.md` lives inside a
closed mission (`do-dispatch-open-op-lifecycle-…`), which this mission does not
edit.

## Phase 2 — Task decomposition

| WP | Scope | Requirements |
|----|-------|--------------|
| WP01 | `charter context --profile` + tests — makes the reference resolvable | FR-003, SC-002 |
| WP02 | `dispatch --brief` JSON + console + `--dry-run`, default unchanged, tests | FR-001, FR-002, FR-004, SC-001, SC-003 |
| WP03 | Docs: command reference, architecture page, skill, changelog | FR-005 |

WP02 depends on WP01 (it asserts the fetch command against the profile-aware
render). WP03 depends on both.

## Risks

| Risk | Mitigation |
|------|------------|
| Brief mode silently becomes "no governance" | Opt-in only; the reference always prints the fetch command; the skill and docs say to use it only after the first full read; default stays byte-identical |
| Fetch command drifts from the embedded text | The test renders `charter context --action <a> --profile <id>` and `dispatch --profile <id>` on one fixture and compares the texts |
| docs/api/cli-commands.md regeneration is shared-machine churn | Regenerate only the affected sections and verify with `scripts.docs.check_docs_freshness --ci` (errors=0) |
| Envelope consumers break on `null` text | Only in opt-in brief mode, documented; non-brief shape unchanged (C-003) |
