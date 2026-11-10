---
work_package_id: WP02
title: Sandboxed PlantUML service, canary and ADR
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-006
- NFR-001
- NFR-002
- C-002
- C-003
- C-004
- SC-002
planning_base_branch: issue-6936-docsite-diagrams
merge_target_branch: issue-6936-docsite-diagrams
branch_strategy: Planning artifacts for this mission were generated on issue-6936-docsite-diagrams. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6936-docsite-diagrams unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Sandbox and proof
history:
- at: '2026-11-10T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent:
- scripts/docs/site_plantuml_guard.py
- tests/docs/test_site_plantuml_guard.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/docs-site-build.yml
- tests/ci/test_docs_site_job.py
- scripts/docs/site_plantuml_guard.py
- tests/docs/test_site_plantuml_guard.py
- docs/adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Sandboxed PlantUML service, canary and ADR

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

Implement: `spec-kitty agent action implement WP02 --agent claude::implementer-ivan --mission docsite-diagrams-01M72CFS`

## Objectives & Success Criteria
- **T005:** in `.github/workflows/docs-site-build.yml`'s `build` job: a job-level `services: plantuml:` with the pinned image, `env: PLANTUML_SECURITY_PROFILE: SANDBOX`, port `8091:8080` (match doc-kitty's CI exactly; the v0.7.0 check fails if the port is not published on a matching address), plus a readiness-wait step; job `env:` `DK_DIAGRAM_BUILD_RENDER: build` and `DK_PLANTUML_SERVER_URL: http://localhost:8091/svg/`; a step that installs Playwright Chromium at the pinned version (`pnpm --dir site exec playwright install --with-deps chromium` or as doc-kitty's CI does; no unpinned download). Follow `5acb83c:.github/workflows/ci.yml` (grounding §2.6) and keep every action SHA-pinned (existing test). If the image appears in both the workflow and the Makefile, add one test asserting they are equal (lasting value: it catches a half-bumped digest).
- **T006:** before `pnpm run build`: `pnpm exec dockitty-assert-plantuml-no-remote-include --service-container "${{ job.services.plantuml.id }}" --canary-host <gateway from docker inspect> --astro-config astro.config.mjs` (working-directory site; every dockitty-* call carries `--astro-config`, `test_docs_site_job.py` enforces it). Then the plantuml-guard: doc-kitty's `plantuml-guard` is a library (grounding §2.4); add `scripts/docs/site_plantuml_guard.py` only if the guard cannot run directly (prefer a one-line `node --input-type=module -e` call into the exported library; if a wrapper is needed, keep it thin and tested with mutants: a `plantuml.com` URL and a non-self-hosted default each fail).
- **T007:** ADR `docs/adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md`: append an `## Amendment 2026-11-10` section (body unchanged): under doc-kitty the renderer is a digest-pinned PlantUML server in SANDBOX as a service container; `docker --network=none` no longer applies; the guarantee becomes "the renderer refuses every remote include, proven by a canary check on every docs-site run"; external includes stay off (#268 opt-in unused, operator ruling 2026-11-01 on #6936); the DocFX lane is unchanged until #6943. Run the terminology guard.
- **T008:** proof is on CI: the orchestrator pushes the branch and opens the draft PR; you record locally what you can (YAML parse, `uvx --from actionlint-py actionlint` on the workflow, the tests). Run `tests/ci/test_docs_site_job.py`, `tests/architectural/test_no_duplicate_suite_execution.py`, `tests/ci/test_fork_guard.py`, `tests/release/test_release_ci_ownership.py`, `tests/docs`.

## Progress & Status

`spec-kitty agent tasks mark-status <T...> --wp <WP> --status done --mission docsite-diagrams-01M72CFS`, `add-history`, then `move-task <WP> --to for_review`; commit leftovers with `spec-kitty safe-commit <files> -m "..." --to-branch kitty/mission-docsite-diagrams-01M72CFS`.
