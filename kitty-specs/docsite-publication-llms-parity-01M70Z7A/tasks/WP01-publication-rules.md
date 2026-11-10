---
work_package_id: WP01
title: 'Publication rules: unpublished set, built-site check and content'
dependencies: []
requirement_refs:
- C-001
- C-002
- C-003
- C-004
- C-006
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-010
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
- SC-005
planning_base_branch: issue-6932-docsite-publication-llms-parity
merge_target_branch: issue-6932-docsite-publication-llms-parity
branch_strategy: Planning artifacts for this mission were generated on issue-6932-docsite-publication-llms-parity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6932-docsite-publication-llms-parity unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Publication
history:
- at: '2026-11-09T20:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/site_built_check.py
- tests/docs/test_site_built_check.py
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/_dockitty_contract.py
- scripts/docs/site_contract.py
- scripts/docs/site_built_check.py
- site/dockitty-contract.json
- .github/workflows/docs-site-build.yml
- .github/workflows/ci-router.yml
- tests/release/ci_retirement_scrub.json
- Makefile
- tests/docs/test_site_built_check.py
- tests/docs/test_dockitty_contract.py
- tests/docs/test_site_scaffold.py
- tests/docs/test_site_bump.py
- tests/ci/test_docs_site_job.py
- docs/**
- site/moves.yaml
- site/url-baseline.txt
- scripts/docs/redirect_map.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---


# Work Package Prompt: WP01 – Publication rules: unpublished set, built-site check and content

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (`implementer-ivan`, role `implementer`) and behave according to its guidance before parsing the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status --mission docsite-publication-llms-parity-01M70Z7A`; address every item; record progress with `spec-kitty agent tasks add-history <WP> --note "..."`.

## Context & Constraints

- Spec/plan/research/data-model/quickstart: `kitty-specs/docsite-publication-llms-parity-01M70Z7A/`; grounding (file:line facts, doc-kitty paths): `research/code-grounding.md` — read it first.
- Charter `.kittify/charter/charter.md`; CLAUDE.md (immutable bodies, bot-regenerated surfaces, terminology). ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-5, D-8, D-9, D-11.
- doc-kitty v0.7.0 (`5acb83c`) source: `site/node_modules/@spec-kitty/doc-toolkit/` (after `cd site && pnpm install --frozen-lockfile`).
- **Test value (#7484):** tests must have lasting value — test real behaviour (the check over a fixture `dist`, the contract predicates), with mutants; never restate YAML/config shape.
- **ATDD:** commit the failing acceptance tests first, on their own commit (`test(...): ... (red)`), record the red counts, then make them green.
- Commit trailers on every commit (use plain `git commit` so commits are signed; `spec-kitty safe-commit` is only for status files):
  `Refs #<issue>` / `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` / `Co-Authored-By: Claude <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_01E5wJU8TifzpaBhQYg4LFuP`.
- Never edit `docs/development/page-inventory.yaml`, `docs/development/docs-retrieval-index.yaml` or ADR index tables (bot surfaces), `docs-pages.yml`, `seo_postprocess.py`, `seo_verify.py`.
- pytest tip: use `--tb=line` on these modules (default tracebacks over large parsed YAML/HTML are very slow).

## Branch Strategy

Populated by finalize-tasks. Work in the repository root checkout on the mission branch.

Implement: `spec-kitty agent action implement WP01 --agent claude --mission docsite-publication-llms-parity-01M70Z7A`

## Part A — Unpublished set and built-site check (T001–T005)

### Objectives & Success Criteria

- The unpublished set is defined once (FR-003): `_dockitty_contract.py` gains `DRAFT_FOLDERS = ("plans/engineering-notes", "plans/investigations", "plans/research")` (every page there must be draft — Part B makes it so), `LLMS_STANCE` (the D-9 version-stance block, copied from `docs/llms.txt` lines 5-12, as the one authority; `docs/llms.txt` keeps its own copy until #6938 deletes the file — note this as temporary duplication) and `unpublished_routes(docs_root) -> frozenset[str]` (routes of every page under `EXCLUDED_FOLDERS` or not `is_published`, using the existing `slug_of`). `site_contract.py` projects `llmsStance` into `site/dockitty-contract.json` (regenerate it).
- `scripts/docs/site_built_check.py` (stdlib only, runnable as `python3 -m scripts.docs.site_built_check <dist> [--docs docs]` with `PYTHONPATH=.:src` like `site_contract`) walks a built `dist` and reports every unpublished route found on: built HTML pages (a `<route>/index.html` exists), hub/page links (`href` to the route), `sitemap-*.xml` `<loc>`, `okf/` files, the pagefind index (its JSON/fragment metadata; read the pagefind layout in `site/dist/pagefind` after a build), `llms.txt` and `api/index.json` when present. Exit 1 with one line per finding. Design it as a registry of surface checkers so WP03/WP04 add surfaces with one line each.
- The shared workflow (`.github/workflows/docs-site-build.yml`) runs, after install: `pnpm exec dockitty-validate-frontmatter ../docs --astro-config astro.config.mjs` and `pnpm exec dockitty-check-links ../docs --strict --astro-config astro.config.mjs` (working-directory `site`); after build: the built-site check and `pnpm exec dockitty-assert-no-broken-links dist --base / --site https://docs.spec-kitty.ai` (D-11; check the bin's flags in the toolkit; if it needs `--astro-config`, pass it — `tests/ci/test_docs_site_job.py` requires every dockitty-* call line to carry `--astro-config astro.config.mjs`; if a bin does not accept it, record that and adjust the test's rule honestly, don't fake a flag). The Makefile `docs-site` target runs the same sequence. `scripts/docs/site_built_check.py` joins the `docs_site` path group in `ci-router.yml` and its scrub copy.

## Subtasks

### T001 – Red: fixtures + mutants
- `tests/docs/test_site_built_check.py`: build small fixture `docs/` + `dist/` trees in `tmp_path` (a published page, a draft page, an excluded-folder page, a sitemap, an okf file, a pagefind metadata file). Tests: clean fixture passes; one mutant per surface (draft page built; draft route in a hub `href`; draft `<loc>` in sitemap; draft in okf; draft in pagefind metadata) each fails naming the route and surface. Contract tests in `tests/docs/test_dockitty_contract.py` for `unpublished_routes` (excluded, draft, absent doc_status = unpublished, published) and the projection equality in `test_site_scaffold.py` (already compares JSON to the authority — extend if needed).
- Commit red alone; record counts.

### T002 – Contract + projection
- As above. Keep functions small (complexity ≤ 15), typed, mypy-clean.

### T003 – Built-site check script
- Implement; route normalisation must match doc-kitty's (README/index → directory route, lowercase? check `slug_of` vs built paths on the real `site/dist`).

### T004 – Wire the steps
- Workflow + Makefile + router path group + scrub copy. Keep `tests/ci/test_docs_site_job.py` green (pins, no credential, no swallowed failure, --astro-config rule).

### T005 – Measure on the current tree
- Run `make docs-site` (needs node ≥ 22.22, pnpm 10.28; `cd site && pnpm install --frozen-lockfile` first). Record: page count, and whether the frontmatter and strict link gates are already green on the current tree. The built-site check is EXPECTED to report the 12 non-draft working-note pages (and retired pages are not yet unpublished — they are still published, so not reported). Do NOT make the check pass by weakening it: Part B fixes the content. If `make docs-site` therefore fails at the check step on this WP's tree, that is the expected red-before-content state; record it in history and in the review notes. Run `tests/docs`, `tests/ci/test_docs_site_job.py`, `tests/architectural/test_no_duplicate_suite_execution.py`, `ruff check`/`ruff format --check --force-exclude` on changed files, `mypy` on new modules.

## Risks
- pagefind's index format: inspect a real build; check the metadata JSON (`pagefind-entry.json`, fragments) not the binary chunks.
- `dist/api/` is shared by the `docs/api/` section and the agent index.

## Review Guidance
- Mutants exist for every surface; no YAML-shape tests; single authority (no second list).

## Part B — Publication content (T006–T010)

Do Part B after Part A is committed (the check from Part A proves Part B).
- FR-001: every page under `docs/plans/engineering-notes`, `docs/plans/investigations`, `docs/plans/research` has `doc_status: draft` (frontmatter only; bodies are immutable — `tests/docs/test_immutable_bodies.py`). List with `grep -L '^doc_status: draft' -r docs/plans/{engineering-notes,investigations,research}` (grounding: 12 pages).
- FR-002 (operator decision: move, not draft): `git mv` the retired hosted/sync pages under `docs/archive/<section>/<same relative path>` (follow existing `docs/archive/` layout): `operations/sync-daemon-orphan-cleanup.md`, `operations/logged-out-teamspace.md`, `operations/internal-hosted-readiness.md`, `architecture/team-kitty-saas.md`, `architecture/zeitgeist-session-identity.md`, `guides/project-sync-consent.md`, `migrations/teamspace-mission-state-repair.md`, `migrations/teamspace-mission-state-920-closeout.md`, `plans/zeitgeist-client-wp01-remaining.md`, `guides/how-to/collaboration/sync-workspaces.md`. Re-verify the inventory with a fresh grep (`zeitgeist|teamspace|sync daemon|offline queue|OfflineQueue|offline_queue|sync_daemon`) outside archive/reports/convergence/changelog; add any page that is clearly a retired hosted/sync surface (not one that only mentions it as context — ADRs and `context/team-kitty.md` stay) and list the final inventory in your history note. Bodies stay byte-identical.
- For each moved page: append `site/moves.yaml` rows per its header rules (append-only; `from` = each legacy published route, e.g. `/operations/sync-daemon-orphan-cleanup.html` and any older routes in `site/url-baseline.txt` that point at it; `to` = the section hub route; a `note` saying "retired hosted/sync page, archived (#6932)"; `ref: "#6932"`); run `python3 scripts/docs/redirect_stub_generator.py regenerate-map` then `check-map` as the header says (this regenerates `scripts/docs/redirect_map.yaml`, which DocFX uses). Use `scripts/docs/moves_ledger.py` and its tests to validate.
- FR-010: reword or remove every link from a PUBLISHED page into a page that is now unpublished (draft or archived), and drop `related:` entries that name them (frontmatter). Immutable bodies (plans/, reports/, changelog/, archive/, dated ADRs) are never rewritten: if a published immutable page links to a newly unpublished page, report it as a finding (do not edit) and tell the orchestrator. DocFX still deploys: keep DocFX link/TOC checks green (`tests/docs`), update any `toc.yml` entries for moved pages.
- T009: ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`: add an `## Amendment 2026-11-09` section (do not edit D-8's text) recording: folder exclusion runs through doc-kitty's `exclude` option fed from the contract (no loader-filter shim exists); working-note folders are drafts; retired single pages are archived because `exclude` takes folders only (operator decision 2026-11-09); the unpublished set's authority is `unpublished_routes`.
- T010: `make docs-site` is green end to end, including the built-site check and both gates; record page count (650 before). Run `tests/docs` (all), `tests/architectural/test_no_legacy_terminology.py`, the moves-ledger tests.

## Risks
- Bot surfaces become stale (expected; do not edit them).
- Description/frontmatter gates on drafts (doc-kitty still validates drafts).

## Review Guidance
- Bodies byte-identical for moved/flipped immutable pages (`git diff -M --stat`, `git diff` shows frontmatter-only).
- moves.yaml rows append-only and checked.


## Progress & Status

`spec-kitty agent tasks mark-status <T...> --wp <WP> --status done --mission docsite-publication-llms-parity-01M70Z7A`, then `spec-kitty agent tasks move-task <WP> --to for_review --mission docsite-publication-llms-parity-01M70Z7A --note "..."` (it runs a pre-review gate; it may take several minutes). Commit any status files it leaves dirty with `spec-kitty safe-commit <files> -m "..." --to-branch kitty/mission-docsite-publication-llms-parity-01M70Z7A`.
