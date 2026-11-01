# Tasks: dispatch `--brief` governance payload

**Mission**: `dispatch-brief-governance-payload-01M6BV2S` · **Branch**: `issue-6990-dispatch-brief-governance-payload` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing test: `charter context --profile <id>` renders the profile-cited sections that dispatch embeds | WP01 | |
| T002 | Add `--profile` to `specify_cli/cli/commands/charter/context.py` and thread it into the text render | WP01 | |
| T003 | Failing tests: `dispatch --brief --json` nulls the text and emits the reference block; console prints digest + fetch command; `--dry-run` composes | WP02 | |
| T004 | Implement `--brief` in `specify_cli/cli/commands/dispatch.py` (JSON substitution + console render), default path untouched | WP02 | |
| T005 | Prove SC-002 end to end: the printed fetch command reproduces the payload text byte-for-byte on one fixture | WP02 | |
| T006 | Changelog `[Unreleased]` entry for #6990 | WP03 | [P] |
| T007 | `docs/api/cli-commands.md`: regenerate only the `dispatch` and `charter context` help blocks | WP03 | |
| T008 | `docs/architecture/governed-profile-invocation.md` + the shipped `spec-kitty` skill: when to use `--brief`, that it never replaces the first read | WP03 | |
| T009 | Run the terminology guard and the docs-freshness check | WP03 | |

## Phase 1 — The reference must resolve

### WP01 — `charter context --profile`

**Goal**: `spec-kitty charter context --action <a> --profile <id>` renders the same profile-cited sections `dispatch --profile <id>` embeds, so a brief payload's fetch command is exact. **Priority**: P1. **Prompt**: [tasks/WP01-charter-context-profile.md](tasks/WP01-charter-context-profile.md)
**Independent test**: `tests/charter/test_context_profile_option.py` (new) renders with and without `--profile` on one fixture and asserts the profile-cited block appears only in the former.

T001 Failing test: `charter context --profile <id>` renders the profile-cited sections that dispatch embeds (WP01)
T002 Add `--profile` to `specify_cli/cli/commands/charter/context.py` and thread it into the text render (WP01)

Dependencies: none. Risk: `--json` structured blocks are DRG projections; keep them profile-agnostic and change only the rendered text.

### WP02 — `dispatch --brief`

**Goal**: an opt-in brief mode that keeps routing/orientation fields and replaces the re-embedded governance text with a digest plus the exact fetch command, in JSON and console, on the real and `--dry-run` paths; default output byte-identical. **Priority**: P1. **Prompt**: [tasks/WP02-dispatch-brief-flag.md](tasks/WP02-dispatch-brief-flag.md)
**Independent test**: `tests/specify_cli/invocation/cli/test_dispatch.py` — brief JSON, brief console, brief + `--dry-run`, and the unchanged non-brief assertions.

T003 Failing tests: `dispatch --brief --json` nulls the text and emits the reference block; console prints digest + fetch command; `--dry-run` composes (WP02)
T004 Implement `--brief` in `specify_cli/cli/commands/dispatch.py` (JSON substitution + console render), default path untouched (WP02)
T005 Prove SC-002 end to end: the printed fetch command reproduces the payload text byte-for-byte on one fixture (WP02)

Dependencies: WP01 (T005 asserts against the profile-aware render). Risk: silently masking unavailable governance; C-002 keeps the text when it cannot be reproduced.

## Phase 2 — Documented surface

### WP03 — Docs, skill and changelog

**Goal**: the flag is documented where users meet it, and the reference/help surfaces stay fresh. **Priority**: P2. **Prompt**: [tasks/WP03-docs-and-changelog.md](tasks/WP03-docs-and-changelog.md)
**Independent test**: `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0` and `pytest tests/architectural/test_no_legacy_terminology.py` passes.

T006 Changelog `[Unreleased]` entry for #6990 (WP03)
T007 `docs/api/cli-commands.md`: regenerate only the `dispatch` and `charter context` help blocks (WP03)
T008 `docs/architecture/governed-profile-invocation.md` + the shipped `spec-kitty` skill: when to use `--brief`, that it never replaces the first read (WP03)
T009 Run the terminology guard and the docs-freshness check (WP03)

Dependencies: WP01, WP02 (documents their final surfaces). Risk: a full CLI-reference rebuild reads the shared global asset cache — regenerate only the two affected blocks and verify with the freshness check.
