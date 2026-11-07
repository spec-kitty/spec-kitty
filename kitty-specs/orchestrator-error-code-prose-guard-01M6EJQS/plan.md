# Implementation Plan: Orchestrator error-code prose guard

**Branch**: `issue-7035-orchestrator-error-code-prose-guard` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/orchestrator-error-code-prose-guard-01M6EJQS/spec.md`
**Issue**: [#7035](https://github.com/spec-kitty/spec-kitty)

## Summary

`orchestrator_api.allowed_error_codes` is the machine-readable authority for the codes an
orchestrator-api caller can see. Two prose surfaces claim to enumerate the same set and neither
is checked: the API reference's `## Error Codes` bullet list is missing 22 codes and the shipped
operator skill's `## Error Code Summary` table is missing 23. This Mission makes each surface a
complete, human-readable enumeration, bounds each one with explicit in-document anchors, and
adds one contract test that asserts set equality with the authority in both directions, per
surface, plus a duplicate check — so the next registered code cannot silently go missing.

The change is documentation plus a test. No source module, no contract JSON edit, no new gate
wiring: the guard joins `tests/contract`, which CI already runs.

## Technical Context

**Language/Version**: Python 3.11 (the repo's pinned interpreter; the guard is a pytest module)
**Primary Dependencies**: `pytest`, `importlib.resources` (stdlib) — no new dependency
**Storage**: N/A — reads `src/specify_cli/core/upstream_contract.json` through the installed
package resource, the same seam `tests/contract/conftest.py` uses
**Testing**: pytest, `-m "contract and fast"`; markdownlint-cli2 for the edited docs;
`python -m scripts.docs.check_docs_freshness --ci` for the docs surface
**Target Platform**: repository CI (Linux shards) and any contributor's checkout
**Project Type**: single project (CLI + docs + shipped charter offering skills)
**Performance Goals**: guard under 2 s, offline, no subprocess
**Constraints**: contract file read-only; no gate relaxed; sub-code namespaces stay outside the
checked regions; both surfaces stay prose a human reads
**Scale/Scope**: 2 Markdown regions, 1 test class, 80 codes

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|---|---|
| Single canonical authority | **Pass** — the test reads the vendored contract at test time; the docs enumeration is the human view of it, and no second list is introduced (FR-010). |
| ATDD-first / red-first | **Pass** — the guard is written and demonstrated red against the unmodified docs before either surface is edited; half-by-half proof in SC-005. |
| DIRECTIVE_024 locality of change | **Pass** — the diff is the two enumerations plus one test class; contract-version history and per-verb narrative are untouched (C-005). |
| DIRECTIVE_025 boy-scout rule | **Bounded** — annotating the codes added to the enumerations is part of making them useful; no unrelated prose rewrite. |
| DIRECTIVE_041 tests guard real behaviour | **Pass** — the guard pins a standing invariant (docs claim completeness) and fails on a real, measured drift. |
| Terminology canon | **Pass** — "Mission", not "feature", in all added prose; error codes used verbatim from the contract. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | **Pass** — targeted module + docs gates only; CI owns the rest. |
| No gate weakening (C-002) | **Pass** — additive only; `TestAllowedErrorCodes` keeps both assertions (C-003). |

No violations; no Complexity Tracking rows.

## Project Structure

### Documentation (this mission)

```
kitty-specs/orchestrator-error-code-prose-guard-01M6EJQS/
├── spec.md              # requirements, scenarios, success criteria
├── research.md          # Phase 0: measured drift, the parse hazards, the decision
├── reasons-canvas.md    # SPDD canvas
├── plan.md              # this file
├── tasks.md             # Phase 2 (/spec-kitty.tasks)
└── tasks/               # work packages
```

### Source Code (repository root)

```
docs/api/orchestrator-api.md                       # `## Error Codes` — enumeration region
src/charter/offering/skills/
└── spec-kitty-orchestrator-api-operator/
    └── references/orchestrator-api-contract.md    # `## Error Code Summary` — table region
tests/contract/
└── test_orchestrator_api.py                     # sibling class to TestAllowedErrorCodes
docs/changelog/unreleased/<pr>.fixed.md          # per-PR fragment
```

**Structure Decision**: single project. The only production-adjacent artefact touched is the
shipped skill reference (a static Markdown file in the charter offering tree, not a module); the
guard lives beside the existing contract guards it extends.

## Phase 0 — Research (complete)

`research.md` records the measured per-surface drift (22 / 23 missing), the 21 non-contract
sub-codes that a whole-section scan would wrongly demand, and the decision to fuse the issue's
two options: restore the enumerations *and* bound them with in-document anchors, rather than
adding a third mapping file.

## Phase 1 — Design

### Contract between the docs and the guard

```
<!-- orchestrator-error-codes:begin -->
...entries...
<!-- orchestrator-error-codes:end -->
```

Semantics, fixed by the test:

1. The anchor pair must appear exactly once per file. Zero or more than one is a failure.
2. Inside the region, an *entry* is:
   - docs surface: a line `^- \`CODE\``, taking the leading backticked token;
   - table surface: a row whose first cell is exactly one backticked code.
3. Any other non-blank line inside the region must be a heading, a table header/separator, or an
   HTML comment; anything else is a parse failure naming the line — the region cannot silently
   absorb prose the guard cannot read.
4. Comparison, per surface: `set(entries) == allowed_error_codes` (both directions) and
   `len(entries) == len(set(entries))` (no duplicates).

### Entry shape

- **API reference**: one list item per code, `- \`CODE\`` with an optional short parenthetical
  where behaviour needs it. The region groups codes the way the contract orders them (usage,
  policy, mission, WP/transition, safe-commit, design-phase, decisions, design, runtime) so it
  stays readable at 80 entries.
- **Skill table**: one row per code, `| \`CODE\` | commands | description |`, matching the
  table's existing style. `WORKFLOW_EVIDENCE_REQUIRED`, `INVALID_MISSION`,
  `SAFE_COMMIT_STAGED_TREE_UNCHANGED`, `UNSUPPORTED_CAPABILITY`, `RUNTIME_NEXT_FAILED`,
  `RUNTIME_BLOCKED` and the 18 `DESIGN_*` names are added.

### Error reporting

Per surface, one assertion with a message carrying sorted `missing` and `unexpected` lists and
the file path, plus `duplicates`. A helper returns the parsed entries so the test can assert
positive controls (a known code present) alongside the equality — the same-fixture control the
non-vacuity tactic requires.

### Test seams

- Contract: `importlib.resources.files("specify_cli.core").joinpath("upstream_contract.json")`,
  reused via the existing `orchestrator_api_contract` fixture.
- Surface paths: resolved from the repository root derived from the test file's location, so the
  guard runs identically in a lane worktree and in CI.
- Parsing is a pure function over `(text, surface_kind)` so the red-first and fail-closed cases
  (missing anchor, empty region, duplicate) are exercised in-memory without editing the docs.

## Phase 2 — Task decomposition

Two work packages, sequenced (the guard must exist red before the docs go green):

- **WP01 — the guard, red-first.** Add the parsing helper and the contract test class. Prove it
  red against current `main`'s docs (22/23 missing, named), and prove the fail-closed paths
  (missing anchor, zero entries, duplicate) with in-memory fixtures. Ships the guard, not the fix.
- **WP02 — the enumerations.** Bound both surfaces with anchors, restore the missing entries with
  short meanings, and prove the WP01 guard green. Includes the user-facing prose quality pass on
  the added entries and the docs gates.

Both are owned by one implementer, reviewed independently in one round; the review reads the guard
and the docs together because the value is in the pair.

## Risks

| Risk | Mitigation |
|---|---|
| The guard becomes the next stale surface (a hand-kept anchor list). | Anchors live in the documents they bound; the only list is the test's code-free parser. Nothing to re-sync. |
| A future docs reorg deletes an anchor. | FR-005: absence is a test failure naming the anchor, and SC-003 pins it. |
| Sub-code tables get wrapped into the region by a well-meaning edit. | The region delta is bounded and the guard fails loudly (`LANE_MOVED_AFTER_APPROVAL` is not in the contract) rather than silently passing; research D-1 records why. |
| 80-entry lists become unreadable. | Grouping by contract order with one-line meanings; the contract-version history stays as the "when/why" narrative. |

## Complexity Tracking

No charter violations; no rows.
