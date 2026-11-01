# Tasks: `spec-kitty dispatch` routes a documentation-maintenance request (#6970)

**Branch**: `kitty/mission-dispatch-router-docs-coverage-01M6BTTX` · **Merge target**: `main` · **Date**: 2026-11-01

Three work packages, sequenced: the router change lands first (it owns all routing
behaviour), the CLI rendering follows (it renders what the router produced), and the
changelog/docs close the mission with the delivered behaviour. Every work package is
red-first: its test is written and observed failing through the pre-existing entry point
(`ActionRouter.route()` for router-internal behaviour, the real `spec-kitty dispatch`
command for anything a user sees) before the production change.

Anti-vacuity (tactic `acceptance-criteria-non-vacuity`): the docs-routing test pins the
issue's exact request text against the **shipped** `packs/built-in/agent_profiles` YAML,
the phrase test pairs a two-word hit with a one-word miss on the same fixture, and the
refusal tests pair a populated `candidates` case with a zero-overlap case that must stay
empty.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | RED: docs-maintenance request refused on the shipped catalog (`#6970` repro through `dispatch --dry-run --json`) | WP01 | |
| T002 | Recognize documentation-artifact nouns as the `documentation` domain (routing vocabulary table) | WP01 | |
| T003 | RED: two-word / hyphenated keyword and canonical-verb signals never match | WP01 | |
| T004 | Phrase-aware keyword matching (contiguous normalized token run) | WP01 | |
| T005 | RED: `ROUTER_NO_MATCH` carries no candidates; `ROUTER_AMBIGUOUS` names no tied ids | WP01 | |
| T006 | Nearest-profile ranking + actionable suggestion for both refusals | WP01 | |
| T007 | Determinism + no-regression + purity assertions (shuffled catalog, existing fixtures, single `list_all`) | WP01 | [P] |
| T008 | RED: non-`--json` refusal prints a raw JSON blob; `--json` envelope shape pinned | WP02 | |
| T009 | Human-readable refusal rendering on the real and dry-run paths (no JSON when `--json` absent) | WP02 | |
| T010 | CLI-surface assertions for candidates/remedy + `ROUTER_AMBIGUOUS` tied ids | WP02 | |
| T011 | Changelog `[Unreleased]` entry with the impact-first lead and `(#6970)` | WP03 | [P] |
| T012 | Document the routing vocabulary and refusal behaviour in `docs/api/profile-invocation.md` | WP03 | [P] |
| T013 | Docs freshness, changelog-style and terminology gates over the touched docs surface | WP03 | |
| T014 | CLI-level proof: the issue's exact request routes through `dispatch --dry-run --json`; bare `index` still refuses | WP02 | |

## Work Packages

### WP01 — Router vocabulary, phrase matching and actionable refusals · FR-001…FR-006, FR-008…FR-012
**Prompt**: [tasks/WP01-router-docs-vocabulary-and-refusals.md](./tasks/WP01-router-docs-vocabulary-and-refusals.md)
**Goal**: A documentation-maintenance request routes on the shipped catalog without `--profile`, declared multi-word/hyphenated keywords match, and both refusals name the profiles the caller can choose plus the exact `--profile` command.
**Priority**: P1. **Independent test**: `dispatch "mark ADR-0068 Accepted and regenerate the ADR index" --dry-run --json` exits 0 with `curator-carla` / `domain_keyword`; a no-overlap request's `candidates` stays empty; a tied request keeps `ROUTER_AMBIGUOUS` and names the tied ids.
**Subtasks**: T001–T007. **Depends on**: none. **Risk**: over-broad vocabulary shadowing an existing route (mitigated by the differential check and by excluding bare `index`); candidate ordering must be a total order. **~250 lines.**

### WP02 — Human-readable refusal on the console · FR-001 (CLI proof), FR-007, FR-008
**Prompt**: [tasks/WP02-cli-refusal-rendering.md](./tasks/WP02-cli-refusal-rendering.md)
**Goal**: `spec-kitty dispatch` without `--json` renders a legible refusal (code, candidates, remedy, exit 1) on the real path, the dry-run path and the unknown-`--profile` refusal, while the `--json` envelope keeps its five keys unchanged. It also carries the CLI-level proof that the issue's own request routes.
**Priority**: P1. **Independent test**: a refused dispatch without `--json` prints no JSON error envelope and names the code plus a `--profile <id>` remedy; the same request with `--json` still emits the envelope; and `dispatch "mark ADR-0068 Accepted and regenerate the ADR index" --dry-run --json` exits 0 with `curator-carla`.
**Subtasks**: T008–T010, T014. **Depends on**: WP01. **Risk**: the refusal renderers drifting apart across the three call sites; leaking rich markup into the JSON path. **~160 lines.**

### WP03 — Changelog and docs · charter DIRECTIVE_037
**Prompt**: [tasks/WP03-changelog-and-docs.md](./tasks/WP03-changelog-and-docs.md)
**Goal**: The user-facing change is recorded in `[Unreleased]` and the routing vocabulary plus refusal behaviour is documented where operators read it.
**Priority**: P2. **Independent test**: the changelog entry parses with its `(#6970)` reference; the docs page names the docs vocabulary, the refusal candidates and the remedy, and `check_docs_freshness --ci` reports errors=0.
**Subtasks**: T011–T013. **Depends on**: WP01, WP02. **Risk**: regenerating a shared docs surface other agents rewrite concurrently — regenerate only the touched surface and verify with the freshness check. **~120 lines.**

---

## MVP scope

**WP01 alone** closes the reported defect (the request routes; the refusal is actionable).
WP02 completes the issue's second half for human callers, and WP03 is required by the
mission brief and the charter's living-documentation rule, so all three land.
