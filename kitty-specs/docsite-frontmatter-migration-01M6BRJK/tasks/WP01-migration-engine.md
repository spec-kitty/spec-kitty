---
work_package_id: WP01
title: Migration engine and immutable-body guard
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-005
- FR-006
- FR-008
- FR-010
- NFR-001
- NFR-003
- NFR-004
- SC-002
planning_base_branch: issue-6929-docsite-frontmatter-migration
merge_target_branch: issue-6929-docsite-frontmatter-migration
branch_strategy: Planning artifacts for this mission were generated on issue-6929-docsite-frontmatter-migration. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6929-docsite-frontmatter-migration unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Foundation
history:
- at: '2026-11-01T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/_dockitty_contract.py
- scripts/docs/dockitty_frontmatter_migration.py
- tests/docs/test_immutable_bodies.py
- tests/docs/test_dockitty_contract.py
- tests/docs/test_dockitty_frontmatter_migration.py
execution_mode: code_change
owned_files:
- scripts/docs/_dockitty_contract.py
- scripts/docs/dockitty_frontmatter_migration.py
- tests/docs/test_immutable_bodies.py
- tests/docs/test_dockitty_contract.py
- tests/docs/test_dockitty_frontmatter_migration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Migration engine and immutable-body guard

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- A test proves the migration never changes a byte after the closing frontmatter fence of any immutable file (FR-001, NFR-001). It is committed **first** and is red (import error) on the base.
- One contract module owns the doc-kitty frontmatter rules in core (single canonical authority).
- One script migrates `audience`, ADR `doc_status`/`kind`, and `related` → slugs + `external_references` (FR-002, FR-005, FR-006, FR-008), idempotently (FR-010). It does **not** run over `docs/` in this WP; WP03 applies it.

## Context & Constraints

- Spec: `kitty-specs/docsite-frontmatter-migration-01M6BRJK/spec.md`; plan, research (R-2..R-5), data-model in the same folder; grounding in `research/code-grounding.md`.
- Charter: ATDD-first (C-011), single canonical authority, complexity ≤ 15, mypy-clean, no blanket suppressions.
- Never touch the generated surfaces (`scripts/ci/generated_docs_surfaces.py::is_generated_surface`) or `docs/adr/*/README.md`, `docs/architecture/README.md` (C-003): the migration must skip them.
- Changelog fragments under `docs/changelog/unreleased/` are not pages (`scripts/docs/_page_scope.py`); skip them.

## Branch Strategy

- **Strategy**: `single_branch`; WPs run sequentially in the repository root checkout on `issue-6929-docsite-frontmatter-migration`.
- **Planning base branch**: `issue-6929-docsite-frontmatter-migration`
- **Merge target branch**: `issue-6929-docsite-frontmatter-migration`
- Implement with `spec-kitty agent action implement WP01 --agent claude --mission docsite-frontmatter-migration-01M6BRJK`.

## Subtasks

### T001 — Body-hash immutability test (commit first, red)

`tests/docs/test_immutable_bodies.py`:
- Immutable set (from the contract, `is_immutable(rel)`): dated ADRs `docs/adr/<era>/YYYY-MM-DD-*.md`, `docs/plans/**`, `docs/reports/**`, `docs/changelog/**` (pages only), `docs/archive/**`.
- For every immutable file: `sha256(body(text)) == sha256(body(migrate_text(rel, text)))`. `body` = bytes after the closing `---` fence (whole text when there is no frontmatter).
- Non-vacuity: assert ≥ 400 immutable files examined, and that at least one file's frontmatter **does** change under the migration on the base tree (so the test exercises real rewrites, not a no-op). After WP03 applies the migration that second assertion no longer holds, so phrase it as: the migration *rewrites* on a synthetic old-shape copy of a real ADR + plan (read a real file, reset its frontmatter to old shape in memory).
- Negative control: a migrator that appends one character to the body is detected (monkeypatch or a helper `assert_body_preserved(before, after)` that raises; test it with a mutated string).
- Mark `pytestmark = pytest.mark.architectural`? No: these are fast unit checks; use `pytest.mark.fast` if the suite uses it (check `tests/docs/` neighbours) so `make test-fast` picks it up.
- Commit alone: `test(docsite-frontmatter-migration): body-hash immutability guard (red)`.

### T002 — Contract module `scripts/docs/_dockitty_contract.py`

Pure functions, `__all__`, docstrings, standard library + `scripts.docs._inventory.parse_frontmatter`:
- `EXCLUDED_FOLDERS: tuple[str, ...] = ("archive", "reports", "convergence", "changelog/unreleased")` — doc comment: mirrors `exclude` on `defineDocKittyIntegrations`; #6930's `site/astro.config.mjs` must use this list.
- `INDEX_BASENAMES = ("README", "index")`.
- `slug_of(rel_under_docs: str) -> str`: strip `.md`, strip a trailing `/README` or `/index` (and a bare `README`/`index` → `""`).
- `is_excluded(rel_under_docs) -> bool`.
- `page_for_slug(docs_root, slug) -> Path | None`: `<slug>.md`, `<slug>/README.md`, `<slug>/index.md`, in that order; case-sensitive.
- `is_published(docs_root, rel_under_docs, frontmatter) -> bool`: not excluded and `(doc_status or "draft") != "draft"`.
- `PERSONA_ROOT = "context/audience"`; `profile_of_persona_path(value) -> str | None` for `docs/context/audience/<p>.md` (also tolerate page-relative `../context/audience/<p>.md`); `persona_page(docs_root, profile) -> Path | None` (`<p>.md` or `<p>/index.md` under `docs/context/audience/`).
- `is_dated_adr(rel)`, `is_immutable(rel)`.
- Tests in `tests/docs/test_dockitty_contract.py` cover every branch (index forms, root, excluded prefixes vs look-alikes such as `archived/`, drafts, absent status, persona resolution, nested profile `internal/maintainer`).

### T003 — Frontmatter block editor

In `scripts/docs/dockitty_frontmatter_migration.py`:
- `split_document(text) -> (frontmatter_lines, fence_end_index, body)`; preserve the original newline style and the exact body string.
- `replace_block(lines, key, new_lines)`: a top-level block is the `key:` line plus following lines that are indented or start with `- `; returns new lines. `insert_after(lines, key, new_lines)` and `append`.
- Emit blocks with `ruamel.yaml` (safe, `default_flow_style=False`, width large) for one key at a time, so only that block's text is new.
- After each rewrite, re-parse old and new frontmatter; every key except the intended ones must compare equal, else raise `MigrationIntegrityError`.

### T004 — Audience rule

- Input: scalar or list of strings. Persona path → `{profile: <p>, guidance_text: "Written for the <Persona title> reader."}`; the persona title is the persona page's `title` with a leading `Persona: `/`Audience: ` style prefix removed if present (inspect `docs/context/audience/internal/maintainer.md` for the real title format and pick the reader-facing name). Free text → `{profile: <text>, guidance_text: "Written for <text>."}`.
- Already a list of mappings → unchanged (idempotent).

### T005 — ADR rule

- Only `is_dated_adr`. `status` → `doc_status` via `ADR_DOC_STATUS = {"Accepted": "active", "Proposed": "active", "Superseded": "superseded"}`; unknown status raises (fail closed). Insert `doc_status` and `kind: ADR` right after the `status:` line when absent; never change `status`, `date`, `superseded_by`. An existing `doc_status` that disagrees with the mapping raises.

### T006 — Related rule

For each entry (string; `{ref, note}` already-migrated entries kept):
- Already a slug of a published page → keep.
- `docs/<x>.md` that exists and is published → `slug_of(x)`.
- `docs/<x>.md` that exists and is **not** published (excluded folder or draft) → `external_references` `{url: https://github.com/spec-kitty/spec-kitty/blob/main/docs/<x>.md, title: <target title>}`.
- Any other existing repository path (outside `docs/`, or a non-Markdown file in `docs/`) → `{url: …/blob/main/<path>, title: <path>}`; a directory → `…/tree/main/<path>`.
- Target missing → drop; record in the report.
- Publication of a target uses its frontmatter **after** the ADR rule (so ADRs count as published). Compute ADR status from the target's `status` when it has no `doc_status`.
- Keep entry order; dedupe. Empty `related` → remove the key; merge into an existing `external_references` without duplicates.

### T007 — CLI and idempotency

`python -m scripts.docs.dockitty_frontmatter_migration [--docs-root docs] [--repo-root .] (--check | --apply | --verify-against REF) [--json]`:
- `--check`: report per class counts and files that would change; exit 1 if anything would change.
- `--apply`: write changed files; report the same counts plus dropped references.
- `--verify-against REF`: for every `docs/**/*.md` changed since `REF` (`git diff --name-only REF -- docs`), assert the body at `REF` equals the body now (`git show REF:path`); exit 1 naming offenders. Added files are skipped.
- Skip: generated surfaces, `docs/adr/*/README.md`, `docs/architecture/README.md`, `docs/changelog/unreleased/**`, files without frontmatter.
- Tests (`tests/docs/test_dockitty_frontmatter_migration.py`): each rule on fixtures in `tmp_path`, unknown ADR status fails, integrity error on a forced bad edit, second run reports zero changes, `--verify-against` red/green on a throwaway git repo (use `tests.docs.conftest.init_git_repo_with_base`).

## Definition of Done

- T001 committed first and red on the base; green at the end.
- `ruff check`, `ruff format --check --force-exclude`, `mypy` clean on the new files; no function > complexity 15.
- `pytest tests/docs/test_immutable_bodies.py tests/docs/test_dockitty_contract.py tests/docs/test_dockitty_frontmatter_migration.py` green; `--check` over the real `docs/` reports the expected counts (≈344 audience, 227 ADR, ≈413 related files).

## Risks / Reviewer guidance

- Verify no body edit is possible through the editor API (it never receives the body).
- Verify the integrity check would catch a reformatted neighbouring key.
