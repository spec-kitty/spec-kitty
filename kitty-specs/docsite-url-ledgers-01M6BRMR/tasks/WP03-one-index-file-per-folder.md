---
work_package_id: WP03
title: One index file per folder
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-011
- C-003
- C-004
- C-007
- SC-004
planning_base_branch: issue-6927-url-baseline-moves-ledger
merge_target_branch: issue-6927-url-baseline-moves-ledger
branch_strategy: Planning artifacts for this mission were generated on issue-6927-url-baseline-moves-ledger. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6927-url-baseline-moves-ledger unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 3 - S-4 dual-index folders (#6928)
history:
- at: '2026-11-01T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/architecture/
create_intent:
- tests/docs/test_one_index_per_folder.py
- docs/changelog/unreleased/6927-docsite-url-ledgers.internal.md
execution_mode: code_change
model: ''
owned_files:
- docs/adr/1.x/README.md
- docs/adr/2.x/README.md
- docs/adr/3.x/README.md
- docs/architecture/README.md
- docs/architecture/index.md
- docs/architecture/vision/README.md
- docs/architecture/diagrams/README.md
- src/charter/offering/templates/diagrams/README.md
- tests/docs/test_one_index_per_folder.py
- tests/docs/test_adr_readme_prose.py
- tests/charter_offering/test_wp_authoring_contract_roundtrip.py
- tests/ci/test_regen_docs_index.py
- CLAUDE.md
- AGENTS.md
- docs/changelog/unreleased/6927-docsite-url-ledgers.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – One index file per folder

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- `docs/adr/1.x/README.md`, `docs/adr/2.x/README.md`, `docs/adr/3.x/README.md` and `docs/architecture/README.md` are deleted (FR-008, FR-009).
- `docs/architecture/index.md` carries the README's landing content: purpose line, boundary rule, living and frozen pages, decay rule, and any other section the README had. No content is lost (FR-009).
- `site/moves.yaml` gains four entries: `/adr/<era>/README.html → /adr/<era>/index.html` and `/architecture/README.html → /architecture/index.html`, `ref: "#6928"`. `scripts/docs/redirect_map.yaml` is regenerated; the four routes are already in `site/url-baseline.txt` from the walk.
- No live reference names a removed README (FR-010). Immutable history is exempt (C-003; see `occurrence_map.yaml`).
- No folder under `docs/` holds both `index.md` and `README.md` (FR-011, SC-004).
- Generated docs surfaces are not touched (C-004).

## Context & Constraints

- ADR D-7 "Index files" row and D-1 "Index-file sequencing": keep `index.md` as the index while DocFX deploys.
- `occurrence_map.yaml` (this Mission) classifies the repoint. Exceptions: ADR bodies, plans, reports, archive, changelog, `kitty-specs/`, generated index files.
- The `docs-lint` guard (`scripts/ci/check_generated_docs_untouched.py`) refuses edits to the docs index, the page inventory and new ADR era rows. Deleting the stubs adds no row.
- **Out-of-map edit (recorded)**: appending to `site/moves.yaml` and regenerating `scripts/docs/redirect_map.yaml` (WP01-owned). Append-only, a one-line rationale in the commit.

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: issue-6927-url-baseline-moves-ledger
- **Merge target branch**: issue-6927-url-baseline-moves-ledger

Implementation command: `spec-kitty agent action implement WP03 --agent claude --mission docsite-url-ledgers-01M6BRMR`

## Subtasks & Detailed Guidance

### Subtask T011 – Acceptance tests (red)

- **File**: `tests/docs/test_one_index_per_folder.py` (new).
  - `test_no_docs_folder_holds_two_index_files`: walk `docs/`, find folders holding both `index.md` and `README.md`, and assert the list is empty. Floor: ≥ 50 folders with an `index.md` examined (60 today). Positive control: the same helper on a `tmp_path` tree with both files reports that folder.
  - `test_readme_routes_redirect_to_their_index`: for each of the four, the derived map (via `moves_ledger`) maps `<dir>/README.html` to `<dir>/index.html`, and the route is in `site/url-baseline.txt`.
  - `test_architecture_index_carries_the_landing_content`: `docs/architecture/index.md` contains the headings `Boundary rule`, `Living pages and frozen history` and `Decay rule` (take the exact heading text from the README before deleting it).
- Red today: four folders collide and the routes are not in the ledger.

### Subtask T012 – Delete the stubs and fold the landing page

- `git rm docs/adr/{1,2,3}.x/README.md`.
- Fold `docs/architecture/README.md` into `docs/architecture/index.md`:
  - keep `index.md`'s frontmatter; refresh `updated:` to `2026-11-01` and drop `docs/architecture/README.md` from its `related:` list. Union in the README's `related:` entries only if they resolve; check each path exists;
  - body: the H1 stays `Architecture notes` or becomes `Architecture` (pick one and keep the title consistent with frontmatter `title`). Then the README's intro, boundary rule, living and frozen pages, decay rule and remaining sections. Then the existing page list, with its self-links to `README.md` removed (the "see README.md for the boundary rule" sentence points to the section anchor instead; the `[Architecture](README.md)` bullet is dropped);
  - fix relative links that moved: both files sit in the same folder, so links carry over unchanged. Verify with `uv run --frozen pytest tests/docs -q -k "link or related"` and `scripts/docs/related_validator.py` if it has a CLI.
- `git rm docs/architecture/README.md`.

### Subtask T013 – Ledger and map

- Append the four entries under a new comment block `# 2026-11-01 #6928: dual-index folders keep index.md (ADR D-1, D-7)`.
- `python3 scripts/docs/redirect_stub_generator.py regenerate-map && python3 scripts/docs/redirect_stub_generator.py check-map`.

### Subtask T014 – Repoint live references

Grep `architecture/README\.md`, `adr/[123]\.x/README\.md` and bare `(README.md)` links inside `docs/architecture/*.md` and `docs/adr/[123].x/*.md`. Fix each live one:

- `docs/architecture/vision/README.md` and `docs/architecture/diagrams/README.md`: `related:` entry → `docs/architecture/index.md`.
- `src/charter/offering/templates/diagrams/README.md` lines 70–71: link text and target → `docs/architecture/index.md`.
- `tests/docs/test_adr_readme_prose.py`: it reads the three READMEs. Point the prose checks at the three era `index.md` files (the claim it guards still applies to the era landing pages); keep the test meaningful.
- `tests/charter_offering/test_wp_authoring_contract_roundtrip.py`: `DOC_AUTHORED_OWNED_FILES` → `docs/architecture/index.md`.
- `tests/ci/test_regen_docs_index.py`: the `("docs/adr/1.x/README.md", True)` case classifies a path pattern (the regex still accepts a legacy README index). Leave it unless it reads the file; record the decision.
- `CLAUDE.md` and `AGENTS.md`: "following `docs/architecture/README.md` template" → `docs/architecture/index.md`.
- Leave alone: ADR bodies (`docs/adr/1.x/2026-01-23-1-…`, `docs/adr/3.x/2026-06-27-1-…`), `docs/plans/**`, the generated index and inventory, `kitty-specs/**`.
- Then run the `related` validator / docs tests to prove nothing dangles.

### Subtask T015 – Changelog fragment

- `docs/changelog/unreleased/6927-docsite-url-ledgers.internal.md`: one entry covering #6927, #6928, #2358 and #3914. Rename it to the PR number once the PR exists. Follow the style in `docs/changelog/unreleased/README.md`; run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

## Test Strategy

- `uv run --frozen pytest tests/docs/test_one_index_per_folder.py tests/docs/test_adr_readme_prose.py tests/docs/test_moves_ledger.py tests/charter_offering/test_wp_authoring_contract_roundtrip.py tests/ci/test_regen_docs_index.py -q`
- `uv run --frozen pytest tests/docs -q` (the owning subsystem directory)
- `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`
- Local DocFX build on the final tree + `generate` / `coverage`: 0 dead, 0 uncovered.

## Risks & Mitigations

- The `related:` edits collide with #6929. Keep them minimal.
- `README.md` in `docs/architecture/` may be referenced by a docs test that pins the landing page; grep `tests/` for `architecture/README` before deleting.

## Review Guidance

- The four folders hold one index file each; no content was dropped from the landing page (diff the README body against the new `index.md`).
- The ledger diff is append-only.

## Progress & Status

Use `spec-kitty agent tasks add-history WP03 --note "..."`.
