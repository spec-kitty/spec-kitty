---
work_package_id: WP02
title: llms.txt, agent index and render parity
dependencies:
- WP01
requirement_refs:
- C-005
- C-007
- FR-006
- FR-007
- FR-008
- FR-009
- SC-003
- SC-004
planning_base_branch: issue-6932-docsite-publication-llms-parity
merge_target_branch: issue-6932-docsite-publication-llms-parity
branch_strategy: Planning artifacts for this mission were generated on issue-6932-docsite-publication-llms-parity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6932-docsite-publication-llms-parity unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
- T017
- T018
phase: Phase 2 - Surfaces
history:
- at: '2026-11-09T20:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: site/
create_intent:
- site/src/pages/llms.txt.ts
- site/src/pages/api/index.json.ts
- scripts/docs/site_built_check_llms.py
- tests/docs/test_site_built_check_llms.py
- scripts/docs/site_built_check_render.py
- tests/docs/test_site_built_check_render.py
execution_mode: code_change
model: ''
owned_files:
- site/src/pages/llms.txt.ts
- site/src/pages/api/index.json.ts
- scripts/docs/site_built_check_llms.py
- tests/docs/test_site_built_check_llms.py
- site/astro.config.mjs
- scripts/docs/site_built_check_render.py
- tests/docs/test_site_built_check_render.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---


# Work Package Prompt: WP02 – llms.txt, agent index and render parity

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

Implement: `spec-kitty agent action implement WP02 --agent claude --mission docsite-publication-llms-parity-01M70Z7A` (depends on WP01).

## Part A — llms.txt and agent index (T011–T014)

### Objectives & Success Criteria
- FR-006: `site/src/pages/llms.txt.ts` — a thin wrapper over doc-kitty's `llmsTxtRoute` (see the toolkit's `src/lib/routes/llms-txt.ts` and `example/src/pages/llms.txt.ts`) that inserts `contract.llmsStance` (from `site/dockitty-contract.json`, the WP01 projection of `LLMS_STANCE`) after the title/description header. A header comment cites doc-kitty #265 (no preamble option at v0.7.0) and says to delete the wrapper when #265 ships. Keep only what doc-kitty selects (`feeds: llms` sections).
- FR-007: `site/src/pages/api/index.json.ts` mounting `agentIndexRoute` (toolkit `src/lib/routes/agent-index.ts`), so `llms.txt`'s machine-index line resolves. Check no collision with the `docs/api/` section's built pages.
- `scripts/docs/site_built_check_llms.py`: an llms surface for the WP01 check — `llms.txt` exists, contains the stance block exactly, lists no unpublished route and no route from a section whose `feeds` (from `docs/_meta/sections.yaml`) lack `llms`, and `api/index.json` exists. Register it in `scripts/docs/site_built_check.py` with ONE line (declared out-of-map edit; note it in history). Tests with fixtures + mutants (stance missing; plans route listed; draft route listed; index missing) — red first.
- T014: `dockitty-assert-no-broken-links` already runs (WP01); confirm it is green with the new files. Upstream: doc-kitty #265 exists — reference it. If you find a new gap (e.g. the unconditional machine-index line), write the issue text into your history note; the orchestrator files it upstream.
- `make docs-site` green; record page count and the first 20 lines of `site/dist/llms.txt` in history. Run `tests/docs`, terminology guard.

## Part B — Render parity (T015–T018)

### Objectives & Success Criteria
- FR-008: `githubAlerts: true` in `site/astro.config.mjs` (toolkit `src/lib/config.ts:274-283`); update the header comment ("Not wired here yet" now lists only redirects #6933 and diagrams #6936). Do NOT add `starlight.head` (doc-kitty #295 drops toolkit head entries).
- FR-009: `scripts/docs/site_built_check_render.py`, a render surface for the WP01 check: every built HTML page has a non-empty `meta name="description"`, a `link rel="canonical"` equal to the page's own URL on `https://docs.spec-kitty.ai`, `og:title`, `og:description`, `og:url`; no built page body contains a literal GitHub alert marker (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`) outside code blocks. Register it in `scripts/docs/site_built_check.py` with ONE line (declared out-of-map edit). Fixture tests + mutants (missing description, foreign canonical, missing og:url, literal alert) — red first. Use `html.parser` (stdlib).
- T018: SEO parity checklist vs DocFX: for each rule in `scripts/docs/seo_verify.py` (V-01..) and `seo_postprocess.py`, state its doc-kitty equivalent (cite toolkit/Starlight source), or "dropped by ruling" (JSON-LD, ruling 3 in #6100), or a gap with an upstream issue reference (#295 etc.). Do NOT write it under kitty-specs/ (ownership ban): put the full checklist as Markdown in your final history note (`add-history`), the orchestrator commits it to the mission's `research/seo-parity-checklist.md`.
- `make docs-site` green; confirm the literal-alert pages listed in the grounding note (§0.6) now render callouts; record page count. Run `tests/docs`, terminology guard.


## Progress & Status

`spec-kitty agent tasks mark-status <T...> --wp <WP> --status done --mission docsite-publication-llms-parity-01M70Z7A`, then `spec-kitty agent tasks move-task <WP> --to for_review --mission docsite-publication-llms-parity-01M70Z7A --note "..."` (it runs a pre-review gate; it may take several minutes). Commit any status files it leaves dirty with `spec-kitty safe-commit <files> -m "..." --to-branch kitty/mission-docsite-publication-llms-parity-01M70Z7A`.
