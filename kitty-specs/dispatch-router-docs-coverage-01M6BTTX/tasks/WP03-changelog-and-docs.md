---
work_package_id: WP03
title: Changelog entry and routing docs
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-004
- FR-007
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
phase: Phase 3 - Docs
history: []
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/profile-invocation.md
role: documentarian
tags: []
task_type: document
tracker_refs: []
---

# Work Package Prompt: WP03 – Changelog entry and routing docs

## ⚡ Do This First: Load Agent Profile

Load the agent profile in the frontmatter (`scribe-sally`) before reading the rest of this
prompt, and behave according to its guidance.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Mode**: `master`-the-facts — document only behaviour that is on the branch and
  verified by a test in WP01/WP02. No invented behaviour, no editorial tone.

---

## Objectives & Success Criteria

The user-facing change is recorded and documented:

1. `docs/changelog/CHANGELOG.md` gains an `[Unreleased]` entry, bold impact-first lead,
   the `(#6970)` reference, before/after, under 1,200 characters (T011).
2. `docs/api/profile-invocation.md` documents the routing vocabulary (docs artifacts fold
   onto the documentation domain) and what a refusal reports, with the remedy command
   (T012).
3. The docs freshness and terminology checks pass over the touched surface (T013).

Requirements: FR-001, FR-004, FR-007 (documented behaviour).

## Context & Constraints

- **Read the delivered code first**: `src/specify_cli/invocation/router.py` and
  `src/specify_cli/cli/commands/dispatch.py` on this branch are the truth. If a sentence
  in this prompt disagrees with the code, follow the code and record the discrepancy in
  the WP history.
- **Changelog home**: `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink
  to it — never create a second file).
- **Docs home**: `docs/api/profile-invocation.md` is the reference page for `dispatch`.
  Update it in place; do not create a new page (the page-inventory lockfile would need a
  new row for that, which this mission does not need).
- **Shared machine state**: do not run a full `docs/api/cli-commands.md` rebuild (the
  installed CLI's global asset cache is rewritten concurrently by other agents). Only the
  two docs files above change; `cli-commands.md` needs no regeneration because no flag or
  command signature changes.
- **No unrelated doc rewrite**: keep the diff to the touched sections.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T011 – Changelog entry

- **Purpose**: record the user-visible change for release notes readers (maintainers,
  operators, agent authors).
- **Steps**: add one bullet under `## [Unreleased]` → `### Fixed` (or `### Changed` if the
  behaviour reads as a change) in `docs/changelog/CHANGELOG.md`, in the house shape the
  style guard enforces: `- **<impact-first headline>** (#6970). **Before:** … **After:** …`.
  The issue reference goes **after** the bold headline, never inside it (the guard's
  `refs-in-bold` rule), `Fixed`/`Changed` entries must carry a `**Before:**` sentence
  (`contrast-missing`), and the whole entry stays under 1,200 characters (error limit;
  900 warns; there is no per-sentence cap when `**Before:**` is present). Cover all three
  behaviours: the docs request now routes without `--profile`; declared multi-word or
  hyphenated keywords now match; and a refusal names the closest profiles and the
  `--profile` remedy (and a tie names the tied ids).

### Subtask T012 – Routing docs on the reference page

- **Purpose**: let an operator understand why a request routes and what to do when it
  does not (DIRECTIVE_047 — write for the operator running `dispatch`).
- **Steps**: in `docs/api/profile-invocation.md`, extend the `spec-kitty dispatch`
  section with (a) a short "How routing picks a profile" note: canonical verb tier first,
  then a profile's declared domain keywords, with documentation-artifact nouns
  (`adr`, `docs`, `changelog`, `readme`, `guide`, …) belonging to the documentation
  domain and bare `index` deliberately not; (b) a "When routing refuses" note: what
  `ROUTER_NO_MATCH` and `ROUTER_AMBIGUOUS` report (`candidates` with ids, actions and a
  partial match reason), the `--profile <id>` remedy, that a refusal is exit 1 while
  `--dry-run --json` keeps its success payload, and that `spec-kitty profiles list` shows
  the ids for the current project. Keep it factual and short; no architecture essay.
- **Files**: `docs/api/profile-invocation.md`.
- **Validation**: no contradiction with the code; frontmatter `updated:` bumped.

### Subtask T013 – Freshness and terminology gates

- **Purpose**: the docs surfaces must stay internally consistent.
- **Steps**: run
  `uv run python -m scripts.docs.check_docs_freshness --ci`,
  `uv run python -m scripts.docs.check_changelog_style`, and
  `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`.
  If the freshness check reports a page-inventory or index error caused by your edit,
  regenerate only the affected artifact (`python -m scripts.docs.docs_index --write` when
  the page set changed). If it reports an error unrelated to your files, record it in the
  PR's `## Deferred` with the reason and file an issue only if none exists.
- **Files**: none (verification only).
- **Validation**: `errors=0` for the freshness check, changelog style exit 0, terminology
  test green.

## Validation

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
uv run python -m scripts.docs.check_changelog_style
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Definition of Done

- Changelog entry in `[Unreleased]` with the reference after a bold headline,
  `**Before:**`/`**After:**`, under 1,200 characters, and `check_changelog_style` exit 0.
- Reference page documents the vocabulary and both refusals with the remedy command.
- Freshness check `errors=0`; changelog style exit 0; terminology test green.
- Two docs files touched; no regenerated bulk surface.

## Risks & Mitigations

- **Documenting behaviour that changed in review** → re-read the final code before the PR
  body, and update the entry in the same commit series if a finding changes behaviour.
- **Concurrent docs regeneration** → only the two named files; verify with the freshness
  check rather than trusting a rebuilt index.
