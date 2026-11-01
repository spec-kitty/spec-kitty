# Implementation Plan: `spec-kitty dispatch` routes a documentation-maintenance request

**Branch**: `kitty/mission-dispatch-router-docs-coverage-01M6BTTX` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/dispatch-router-docs-coverage-01M6BTTX/spec.md`

**Issue**: [spec-kitty/spec-kitty#6970](https://github.com/spec-kitty/spec-kitty/issues/6970)

## Summary

`ActionRouter.route()` refuses a documentation-maintenance request because the request's
nouns (`adr`, `index`, `docs`, `changelog`) are declared by no shipped profile, and the
one profile that owns the documentation domain only ever declares multi-word/plain
keywords that the exact-token matcher cannot see. The plan is:

1. Make keyword matching phrase-aware, so a declared keyword or canonical verb containing
   a space or hyphen matches its own normalized token sequence in the request — consulted
   only as a **fallback tier** below today's literal single-token matches, so no request
   that routes today can move (FR-011, SC-006).
2. Fold a small, documented documentation-artifact vocabulary (`doc`, `docs`,
   `documentation`, `docstring`, `readme`, `adr`, `changelog`, `guide`, `handbook`,
   `tutorial`) onto the canonical keyword `documentation`, as the lowest signal tier, so a
   docs request with no literal keyword match routes through the existing `domain_keyword`
   confidence to the shipped documentation profile.
3. Make both refusals actionable: `ROUTER_NO_MATCH` gains up to three nearest profiles
   (deterministic order) and a suggestion containing a runnable
   `spec-kitty dispatch "<request>" --profile <id>`; `ROUTER_AMBIGUOUS` names the tied ids
   and one `--profile` command per id.
4. Render refusals for humans when `--json` is absent, keeping the JSON envelope's keys
   and shape.

The router stays a pure function (ADR-3 Option A): no new I/O, no LLM call, no plugin
hook, no new confidence tier.

## Technical Context

**Language/Version**: Python 3.11+ (repo targets 3.11–3.13)
**Primary Dependencies**: stdlib only for this change (`re`, `dataclasses`); the modules touched already import `charter.profiles` for `Role`/`DEFAULT_ROLE_CAPABILITIES`
**Storage**: N/A (the routing catalog is loaded in memory by `ProfileRegistry`)
**Testing**: pytest; unit tests for the router (`tests/specify_cli/invocation/test_router.py`), CLI-surface tests through the real `dispatch` entry point (`tests/specify_cli/invocation/cli/test_dispatch.py`), and a shipped-catalog routing test modeled on `tests/specify_cli/invocation/test_writing_comms_routing.py`
**Target Platform**: cross-platform CLI (Linux/macOS/Windows)
**Project Type**: single project — `src/` packages + `tests/`
**Performance Goals**: routing stays O(catalog × keywords) with the single existing `registry.list_all()` call; the refusal path adds only in-memory scoring of the profiles already loaded (NFR-005)
**Constraints**: deterministic and total ordering for candidates (NFR-001); at most three nearest profiles (NFR-002); no change for any request that already routed (NFR-003); cyclomatic complexity ≤ 15 per function (NFR-004)
**Scale/Scope**: ~26 shipped profiles × ~10 keywords; one router module (~330 lines) + one CLI module region (~40 lines) + tests

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority (`DIRECTIVE_044`) | Vocabulary, phrase matching and refusal ranking live only in `src/specify_cli/invocation/router.py`; the CLI renders what the router decided and re-derives nothing (C-004). The ADR-3 vocabulary table stays the one routing authority; the pack's profile keywords stay the one profile authority. |
| Architectural alignment (`DIRECTIVE_001`) | The change stays inside the existing `specify_cli.invocation` package seam plus its CLI renderer; no new module, no new dependency, no cross-context import. |
| ATDD-first / red-first (`DIRECTIVE_034`, charter ATDD section) | Every FR lands a test through the pre-existing entry point (the `dispatch` Typer command, or `ActionRouter.route()` where the FR is router-internal) that is RED before the fix (C-006). |
| Tests as scaffold (`DIRECTIVE_041`) | No implementation-coupled assertions: the docs-family test asserts a routed `profile_id`, not the vocabulary table's private shape; the phrase test asserts matched/not-matched behaviour. |
| Locality of change (`DIRECTIVE_024`) + smallest viable diff | Two production files; no refactor of unrelated router tiers; no pack edits (C-001). |
| Living documentation sync (`DIRECTIVE_037`) | `docs/changelog/CHANGELOG.md` gains an `[Unreleased]` entry; the dispatch docs page that describes routing/refusal is updated; the JSON shape stays documented as-is with `candidates` now populated. |
| No full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`) | Targeted runs only: the two invocation test files, the shipped-catalog routing test, plus the specific architectural gate files the change implicates. CI owns the matrix. |
| No gate weakening (C-005) | No `# noqa`, `# type: ignore`, xfail or coverage exclusion is added. |
| Determinism (ADR-3) | Ordering is a documented total order (signal strength, `routing_priority` desc, `profile_id` asc), asserted by a shuffled-catalog test. |

No violations: **Complexity Tracking is empty**.

## Project Structure

### Documentation (this mission)

```
kitty-specs/dispatch-router-docs-coverage-01M6BTTX/
├── plan.md              # This file
├── research.md          # Phase 0: reproduction, root causes, decisions
├── data-model.md        # Phase 1: vocabulary, candidate, decision terms
├── quickstart.md        # Phase 1: before/after operator recipes
├── traces/              # Tracer files (tooling-friction, approach, design-decisions)
├── tasks/               # Work package prompts (Phase 2)
└── tasks.md             # Task index (Phase 2)
```

### Source Code (repository root)

```
src/specify_cli/invocation/
├── router.py            # ActionRouter: vocabulary + phrase matching + nearest-profile ranking
├── errors.py            # RouterAmbiguityError (unchanged shape; candidates now populated)
└── registry.py          # ProfileRegistry (read-only input)

src/specify_cli/cli/commands/
└── dispatch.py          # human-readable refusal rendering (non-`--json` path)

tests/specify_cli/invocation/
├── test_router.py                       # router-internal behaviour (phrase match, ranking, determinism)
├── test_docs_domain_routing.py          # NEW: shipped-catalog docs routing (#6970 repro)
└── cli/test_dispatch.py                 # refusal rendering + JSON compatibility through the CLI

docs/
├── changelog/CHANGELOG.md               # [Unreleased] entry
└── guides/ (dispatch/routing page)      # document the vocabulary + refusal behaviour
```

**Structure Decision**: single project. The change is two production modules in the
existing `specify_cli.invocation` package and its CLI renderer, plus the matching test
modules; no new package or directory is introduced.

## Implementation Concern Map

### IC-01 — Vocabulary, phrase matching and the tier ladder in the router

- **Purpose**: Give the documentation domain a routable vocabulary and make multi-token
  keywords/verbs match, without moving any request that routes today.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-010, FR-011, FR-012
- **Affected surfaces**: `src/specify_cli/invocation/router.py`
  (`_normalize_tokens`, keyword-match pass, new documented vocabulary table, tier ladder)
- **Sequencing/depends-on**: none
- **Risks**: over-broad synonyms could shadow an existing route (NFR-003) — resolved by the
  tier ordering in `data-model.md` §"Signal tiers" (single-token literal > phrase literal
  > docs alias), proven by a differential corpus test over the shipped catalog; bare
  `index` excluded (FR-002).

### IC-02 — Actionable refusals

- **Purpose**: Make `ROUTER_NO_MATCH` and `ROUTER_AMBIGUOUS` name the profiles the caller
  can choose and the exact `--profile` command.
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-008
- **Affected surfaces**: `src/specify_cli/invocation/router.py` (nearest-profile
  ranking, suggestion text), `src/specify_cli/invocation/errors.py` (unchanged), JSON
  envelope keys in `dispatch.py`
- **Sequencing/depends-on**: IC-01 (the ranking reuses the normalized-token and phrase
  primitives)
- **Risks**: the JSON envelope is consumed by tests and agents — additive only (FR-008);
  ranking must be a total order (NFR-001) and capped (NFR-002).

### IC-03 — Human-readable refusal on the console

- **Purpose**: Make the non-`--json` refusal legible instead of a JSON blob on stderr,
  for every refusal the command can emit (no match, ambiguity, unknown `--profile`).
- **Relevant requirements**: FR-007, FR-008
- **Affected surfaces**: `src/specify_cli/cli/commands/dispatch.py`
  (`_emit_routing_error_and_exit`, the dry-run/real error branches)
- **Sequencing/depends-on**: IC-02 (renders the candidates the router produced)
- **Risks**: the `--json` path must not change at all; the two error paths (dry-run and
  real) must render identically, or the CLI drifts from itself.

### IC-04 — Changelog and docs

- **Purpose**: Record the user-facing change and document the routing vocabulary and the
  refusal behaviour where operators read it.
- **Relevant requirements**: none directly (charter DIRECTIVE_037; the mission brief's
  changelog rule)
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`, the dispatch/routing docs page
- **Sequencing/depends-on**: IC-01, IC-02, IC-03 (documents delivered behaviour)
- **Risks**: `docs/api/cli-commands.md` is regenerated from a shared installed-CLI cache
  other agents rewrite concurrently; regenerate only what the diff changes and verify
  with `check_docs_freshness --ci`.

## Complexity Tracking

No charter violations to justify.
