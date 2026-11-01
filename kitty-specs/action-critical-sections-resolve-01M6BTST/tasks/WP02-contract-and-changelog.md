---
work_package_id: WP02
title: Align the published contract and changelog
dependencies:
- WP01
requirement_refs:
- FR-006
- C-002
- SC-004
planning_base_branch: issue-6968-action-critical-sections-resolve
merge_target_branch: issue-6968-action-critical-sections-resolve
branch_strategy: Planning artifacts for this mission were generated on issue-6968-action-critical-sections-resolve. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6968-action-critical-sections-resolve unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Document the shipped rule
history:
- at: '2026-11-01T15:18:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: minutes-mahad
authoritative_surface: kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-context-resolver.md
- docs/changelog/CHANGELOG.md
role: documentarian
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Align the published contract and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `minutes-mahad`
- **Role**: `documentarian`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Review Feedback

Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`). Address all feedback before the work is complete, and record each response with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

The documents that pin this behaviour must describe the shipped rule, so the fix
cannot be "corrected" back by someone reading a stale contract.

1. The `Action-Critical Charter Sections (<action>):` row in the WP-prompt
   governance resolver contract states that only headings the active
   `charter.md` carries are advertised; a heading the charter lacks is not
   advertised and gets no fetch stanza (FR-006, SC-004).
2. The contract's "Verbatim-OR-fetch stanza" section says the `section:<slug>`
   selector is advertised only for a resolving heading, and that the direct
   selector fetch keeps its honest placeholder.
3. `docs/changelog/CHANGELOG.md` carries one `[Unreleased]` entry for #6968:
   bold impact-first lead with `(#6968)`, before/after, under 1,200 characters.
4. The docs checks that cover the touched surfaces pass.

## Context & Constraints

- The contract lives inside a historical mission's `contracts/` directory
  (`kitty-specs/wp-prompt-governance-payload-01KRR8HS/`). It is the document the
  renderer docstring cites, so it is the right place to update; do not rewrite
  the rest of that contract.
- No new doc page and no new ADR ⇒ no `docs-index` regeneration is expected.
  Verify with the freshness checker instead of rebuilding the whole reference,
  because this host shares the CLI asset cache with other agents.
- Keep the changelog entry inside the existing `[Unreleased]` structure; other
  missions are editing this file concurrently, so touch as few lines as
  possible.
- `packs/built-in` prompt prose that also names the three headings is fetched
  pack content (source `spec-kitty-open-packs`) and is out of scope; the
  follow-up issue is named in the PR's `## Deferred` section.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T006 – Update the resolver contract

- **Purpose**: The contract currently pins the defective rule ("For each section
  in the action-critical set, either the verbatim body OR the fetch + when-doing
  stanza").
- **Files**:
  `kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-context-resolver.md`.
- **Steps**:
  1. In the output-contract table, row 4 (`Action-Critical Charter Sections
     (<action>):`), change "Required when" to "bootstrap action AND at least one
     configured action-critical heading resolves in `charter.md`" and change the
     content rule to: for each **resolving** heading, the verbatim body plus the
     fetch + when-doing stanza; a heading the charter does not carry (absent,
     empty, or fence-masked) is not advertised.
  2. In the "Verbatim-OR-fetch stanza" section, add one sentence: the
     `section:<kebab-cased-heading>` selector is emitted only for a heading the
     active charter resolves; an explicit `--include section:<slug>` for a
     heading the charter lacks keeps returning the honest placeholder.
  3. Reference #6968 in the changed sentences so the reason is traceable.
- **Parallel?**: Yes.
- **Notes**: Do not touch rows 1-3, 5-8 or the token-budget section.

### Subtask T007 – Add the changelog entry

- **Purpose**: User-facing change; the operator needs a release-visible record.
- **Files**: `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink).
- **Steps**:
  1. Add one entry under `[Unreleased]`, following the file's existing shape.
  2. Lead with the impact in bold and `(#6968)`, then before/after in at most a
     few sentences; total under 1,200 characters.
  3. State the two observable changes: no `--include section:` instruction for a
     heading the charter lacks, and no empty action-critical header; and that
     present sections are unchanged.
- **Parallel?**: Yes.
- **Notes**: Do not reorder or reword neighbouring entries.

### Subtask T008 – Run the docs checks

- **Purpose**: Prove the touched docs surfaces are consistent.
- **Commands**:
  ```bash
  uv run python -m scripts.docs.check_docs_freshness --ci
  uv run pytest tests/architectural/test_no_legacy_terminology.py -q
  ```
- **Expected**: freshness `errors=0`; the terminology gate green.
- **Parallel?**: No.
- **Notes**: If a freshness error points at a generated index this mission did
  not touch, record it in the PR's `## Deferred` section with the reason rather
  than regenerating the whole reference.

## Test Strategy

- Documentation-only package: no unit tests. The meaningful checks are the docs
  freshness gate and the terminology gate above, plus a read-back that the
  contract row now states the filtered-set rule.

## Risks & Mitigations

- **Concurrent changelog edits**: keep the diff to the added entry only.
- **Stale contract wording left in place**: grep the contract for
  "action-critical set" after editing and confirm no sentence still promises a
  stanza for a missing heading.

## Review Guidance

- Confirm the contract and the renderer's actual behaviour agree, sentence by
  sentence.
- Confirm the changelog entry names #6968, leads with impact, and stays under
  1,200 characters.
- Confirm no unrelated contract or changelog content changed.
