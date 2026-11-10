---
work_package_id: WP01
title: Legacy map, stub exemption and site wiring
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-006
- FR-007
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-003
planning_base_branch: issue-6933-docsite-redirects
merge_target_branch: issue-6933-docsite-redirects
branch_strategy: Planning artifacts for this mission were generated on issue-6933-docsite-redirects. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6933-docsite-redirects unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Map and site
history:
- at: '2026-11-10T16:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/site_redirects.py
- site/legacy-redirects.json
- tests/docs/test_site_redirects.py
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/site_redirects.py
- scripts/docs/_dockitty_contract.py
- scripts/docs/site_built_check.py
- scripts/docs/site_built_check_render.py
- site/legacy-redirects.json
- site/astro.config.mjs
- tests/docs/test_site_redirects.py
- tests/docs/test_site_built_check.py
- tests/docs/test_site_built_check_render.py
- tests/docs/test_dockitty_contract.py
- docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Legacy map, stub exemption and site wiring

## Context & Constraints

- Read first: spec, plan, research and data model in `kitty-specs/docsite-redirects-01M733MD/`. The grounding, with doc-kitty file:line facts, is in `research/code-grounding.md`.
- Charter and CLAUDE.md. ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`, D-5 "Redirects" and D-14.
- doc-kitty v0.7.0 source: `site/node_modules/@spec-kitty/doc-toolkit/`, in `lib/legacy-html-redirects.mjs` and `scripts/check-redirect-coverage.mjs`.
- Never edit the DocFX path: `redirect_map.yaml`, `redirect_stub_generator.py`, the DocFX validation in `moves_ledger.py`, and `docs-pages.yml`.
- Tests must have lasting value (#7484): fixture trees with one mutant per rule and refusal. Commit the red tests first.

## Objectives & Success Criteria

- **T001 (red tests).** `tests/docs/test_site_redirects.py` covers a tmp `docs/`, moves ledger and baseline.
  - Rule 1: `X.html` goes to `X/`; `dir/README.html` goes to `dir/`.
  - Rule 2: a chain collapses; a cycle is refused.
  - Rule 3: a live, unmoved `dir/index.html` gets no key.
  - Rule 4: a draft page, or a move whose target is a draft, goes to the nearest live ancestor.
  - Rule 5: a resource file under `docs/` goes to its hub; a baseline route with no page, no move and no resource is refused.
  - Collisions: a key whose file is a live page's built file but whose target differs is refused; so is a key equal to a `site/public/` file.
  - `--check` passes when the map is equal, and fails when it is stale or missing.

  The stub-predicate fixtures cover:
  - a doc-kitty stub is recognised and its target returned;
  - a page with a refresh meta but no "Redirecting to:" title is not a stub;
  - the `page` and `render` surfaces skip a stub;
  - the `link` surface still reports a stub whose target is unpublished.
- **T002.** In `_dockitty_contract.py`, `redirect_stub_target(html: str) -> str | None`, the single predicate. Its regex mirrors doc-kitty's `REDIRECT_STUB_RE`: a `<title>Redirecting to: …</title>` followed by a `<meta http-equiv="refresh" content="N;url=…">`. Use it in `site_built_check._pages` and `site_built_check_render.surface`.
- **T003.** `scripts/docs/site_redirects.py`, modelled on `site_contract.py`:
  - stdlib plus PyYAML, runnable as `python3 -m`;
  - `render()`, `write()`, `check()` and `main()`, with `--check`;
  - inputs: baseline, moves, `docs/` and `site/public`;
  - it generates `site/legacy-redirects.json`, a flat, sorted JSON object with no comment key.
- **T004.** `site/astro.config.mjs` reads the map with `readFileSync` and passes it as `legacyHtmlRedirects`, and its header comment says so. Then build locally (`pnpm --dir site run build`) and run both gate runs; both must report 970/970 with no dead stub. The built-site check must be green.
- **T005.** Append `## Amendment 2026-11-10` to the ADR, leaving the body unchanged. It records:
  - the legacy map replaces Astro `.html` keys;
  - the gate override is retired, because gap (b) is closed in v0.7.0;
  - rule 4 lives in the generator while DocFX lives;
  - the resource rule (operator ruling 2026-11-10);
  - current counts: 970 baseline routes and the key count;
  - the file name.

  Run the terminology guard.

## Progress & Status

- `spec-kitty agent tasks mark-status <T...> --wp WP01 --status done --mission docsite-redirects-01M733MD`
- then `move-task WP01 --to for_review`.
