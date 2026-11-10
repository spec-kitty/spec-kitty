---
work_package_id: WP01
title: Diagram rendering and the diagram surface
dependencies: []
requirement_refs:
- FR-001
- FR-004
- FR-005
- NFR-003
- C-001
- C-005
- SC-001
- SC-003
planning_base_branch: issue-6936-docsite-diagrams
merge_target_branch: issue-6936-docsite-diagrams
branch_strategy: Planning artifacts for this mission were generated on issue-6936-docsite-diagrams. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6936-docsite-diagrams unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Render and prove
history:
- at: '2026-11-10T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/site_built_check_diagrams.py
- tests/docs/test_site_built_check_diagrams.py
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/site_built_check_diagrams.py
- scripts/docs/site_built_check.py
- tests/docs/test_site_built_check_diagrams.py
- tests/docs/test_site_built_check.py
- site/astro.config.mjs
- site/package.json
- site/pnpm-lock.yaml
- Makefile
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Diagram rendering and the diagram surface

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `implementer-ivan` (role `implementer`) and behave according to its guidance.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status --mission docsite-diagrams-01M72CFS`; address every item; record progress with `spec-kitty agent tasks add-history <WP> --note "..."`.

## Context & Constraints

- Spec/plan/research/data-model/quickstart: `kitty-specs/docsite-diagrams-01M72CFS/`; grounding with doc-kitty file:line facts: `research/code-grounding.md` — read it first.
- Charter and CLAUDE.md. ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-11 "Diagrams"; ADR `docs/adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md`.
- doc-kitty v0.7.0 source: `site/node_modules/@spec-kitty/doc-toolkit/`.
- Operator decisions: image `plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66adc6728ba6dd353a29d4ada73f8358b68549a0f710c4bf46b43c103618`; SANDBOX + canary is enough, no network isolation, no external includes (doc-kitty #268 opt-in NOT used); the 5 `@startyaml` blocks stay (verified renderable, research.md R-1).
- Never edit the DocFX path: `scripts/docs/plantuml_*`, the jar restore, `docs-pages.yml`.
- Tests must have lasting value (#7484): built-site fixtures + mutants and the real CI run; no YAML-shape tests. ATDD red-first commits.
- Plain `git commit` (signed) with trailers: `Refs #6936` / blank / `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` / `Co-Authored-By: Claude <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_01E5wJU8TifzpaBhQYg4LFuP`.
- This container has no docker daemon and no Playwright browsers: a full diagram render is proven on CI (WP02), not locally. pytest: `--tb=line`.

## Branch Strategy

Populated by finalize-tasks. Work in the repository root checkout `/home/user/spec-kitty` on the mission branch.

Implement: `spec-kitty agent action implement WP01 --agent claude::implementer-ivan --mission docsite-diagrams-01M72CFS`

## Objectives & Success Criteria
- **T001 (red):** `tests/docs/test_site_built_check_diagrams.py`: fixture `docs/` + `dist/` trees. A clean fixture passes (N source blocks → N rendered figures per page). One mutant per failure mode fails, naming page and reason: a raw `mermaid`/`plantuml` code fence left in built HTML; a doc-kitty diagram error block; fewer figures than source blocks; a `plantuml.com` URL; a diagram on an unpublished page counted (must not be). Commit red alone.
- **T002:** `scripts/docs/site_built_check_diagrams.py` (stdlib, `html.parser`): a surface for `site_built_check.py`'s registry; ONE registration line. Learn the built markup doc-kitty emits for a rendered diagram figure and for an error block from the toolkit source (`lib/remark/diagram-figure.ts` etc., cite lines). Count source blocks only on published pages (`_dockitty_contract`). Complexity ≤ 15, mypy clean.
- **T003:** `diagrams: true` in `site/astro.config.mjs` (update its "Not wired here yet" comment). Add `playwright` to `site/package.json` with an EXACT version (the one doc-kitty tests with; grounding says 1.62.1 — verify in the toolkit's own package.json/lock) and refresh `site/pnpm-lock.yaml` with `pnpm install`. Keep the doc-kitty lockfile entry in https form (`tests/docs/test_site_scaffold.py` refuses the SSH form; if pnpm rewrites it, restore it as in #7480).
- **T004:** Makefile `docs-site`: export `DK_DIAGRAM_BUILD_RENDER=build` and `DK_PLANTUML_SERVER_URL=http://localhost:8091/svg/` for the build; a preflight that fails clearly (printing the hardened `docker run` line with the pinned digest from the grounding) when `localhost:8091` does not answer; optionally a `docs-site-plantuml` helper target that starts that container. The digest also appears in the workflow (WP02): if it is duplicated, WP02 pins their equality with one test.
- `make docs-site` cannot fully run here (no docker daemon): run the build path up to the preflight, and record that. Run `tests/docs -n 4 --dist loadfile --tb=line`, `tests/ci/test_docs_site_job.py`, ruff/mypy.

## Progress & Status

`spec-kitty agent tasks mark-status <T...> --wp <WP> --status done --mission docsite-diagrams-01M72CFS`, `add-history`, then `move-task <WP> --to for_review`; commit leftovers with `spec-kitty safe-commit <files> -m "..." --to-branch kitty/mission-docsite-diagrams-01M72CFS`.
