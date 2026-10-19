---
work_package_id: WP08
title: ADR amendment, CLAUDE.md, packs/README, .gitattributes, how-to
dependencies:
- WP03
- WP06
requirement_refs:
- C-006
- FR-014
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: 07fb4e61ddc3783bee330489f13a523ca6203eb3
created_at: '2026-10-19T12:57:42.360381+00:00'
subtasks:
- T034
- T035
- T036
- T037
- T038
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md
create_intent:
- packs/README.md
- docs/development/how-to/sync-packs.md
execution_mode: code_change
model: sonnet
owned_files:
- docs/adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md
- docs/adr/3.x/2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md
- CLAUDE.md
- packs/README.md
- .gitattributes
- docs/development/how-to/sync-packs.md
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP08 – ADR amendment, CLAUDE.md, packs/README, .gitattributes, how-to

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load curator-carla` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

Governance text says to edit pack content in open-packs and then bump the pin; the ADR is amended and the internal ADR cross-referenced.

Requirements: FR-014, FR-011, C-006.

## Context

- `CLAUDE.md` sections "Template Source Location" (table points at `packs/built-in/missions/mission-steps/`) and "Pack Tiers" (built-in vs internal; "Source home (direction)" paragraph says vendored at release). Rewrite: source lives in `spec-kitty-open-packs`; core holds pins; run `make sync-packs`; bump with `spec-kitty charter pack vendor --pack <p> --ref <sha>`. Keep the packaging invariant text (internal never ships).
- ADR `2026-08-16-2`: add an "Amendment 2026-10-19" section: committed trees deleted, pin + fetch, hook. ADR `2026-08-16-3`: add a cross-reference note (invariant unchanged).
- `.gitattributes:7` `packs/built-in/missions/mission-steps/** text eol=lf` targets a now-untracked path; remove it with a note, or keep it harmless — decide and record (the fetch writes files itself, so git attributes no longer apply).
- C-006 update per FR-011 (spec.md:101): document that no `[tool.uv.sources]` is used and the subtree comes from the pin.
- How-to must state that `make sync-packs` is run once per worktree (implement and review worktrees too), since each worktree has its own untracked `packs/` trees (A4).
- Run `pytest tests/architectural/test_no_legacy_terminology.py` and the docs spelling check (`scripts.docs.check_spelling`) after editing prose. Use "Mission", never "feature".

Dependencies: Depends on WP03, WP06.

## Subtasks

### T034: ADR 2026-08-16-2 amendment

- **Purpose**: ADR 2026-08-16-2 amendment.
- **Steps**: Add the amendment section with decision, consequences and links to the pins and `pack_fetch`.
- **Edge cases / notes**: Keep the original text.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T035: ADR 2026-08-16-3 cross-reference

- **Purpose**: ADR 2026-08-16-3 cross-reference.
- **Steps**: One paragraph: internal now pinned like built-in; still never shipped.
- **Edge cases / notes**: No decision change.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T036: CLAUDE.md

- **Purpose**: CLAUDE.md.
- **Steps**: Rewrite the template-source table and pack-tier source-home text.
- **Edge cases / notes**: Agent copies are not edited.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T037: packs/README.md and how-to

- **Purpose**: packs/README.md and how-to.
- **Steps**: Explain pins, `make sync-packs`, offline cache, error codes, pin bump flow.
- **Edge cases / notes**: Link from CLAUDE.md.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T038: .gitattributes

- **Purpose**: .gitattributes.
- **Steps**: Resolve the stale `packs/built-in` rule.
- **Edge cases / notes**: Record the choice in the WP notes.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `docs/adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md`
- `docs/adr/3.x/2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md`
- `CLAUDE.md`
- `packs/README.md`
- `.gitattributes`
- `docs/development/how-to/sync-packs.md`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/architectural/test_no_legacy_terminology.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- `docs/development/how-to/sync-packs.md` documents `make sync-packs` per worktree (implement/review).
- Requirements FR-014, FR-011, C-006 demonstrably covered by a test or gate.

## Risks

Docs-index regeneration gates may need a regen when adding a how-to; run the docs-retrieval-index check if present.

## Reviewer guidance

Read the new CLAUDE.md text as a new contributor: can they find where to edit a template and how to bump? Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP08 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
