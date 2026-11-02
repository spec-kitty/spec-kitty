---
work_package_id: WP02
title: Local build and doc-kitty bump targets
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-009
- NFR-004
- SC-002
planning_base_branch: issue-6930-docsite-scaffold
merge_target_branch: issue-6930-docsite-scaffold
branch_strategy: Planning artifacts for this mission were generated on issue-6930-docsite-scaffold. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6930-docsite-scaffold unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 1 - Scaffold
history:
- at: '2026-11-02T07:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/site_bump.py
create_intent:
- scripts/docs/site_bump.py
- tests/docs/test_site_bump.py
execution_mode: code_change
model: ''
owned_files:
- Makefile
- scripts/docs/site_bump.py
- tests/docs/test_site_bump.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Local build and doc-kitty bump targets

## ⚡ Do This First: Load Agent Profile

Load profile `implementer-ivan` (role: implementer) with `/spk-charter-profile-load` before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`) and address every item.

## Objectives & Success Criteria

- `make docs-site`: regenerate/check the contract JSON, `pnpm install --frozen-lockfile`, build.
- `make docs-site-bump REF=<tag|sha>`: ADR D-2 steps 1-2 — resolve the ref to a 40-character commit (`git ls-remote`, peeled tag), rewrite the pin, align `astro`, `@astrojs/starlight`, `@astrojs/markdown-remark` with the toolkit peer ranges at that commit, `pnpm install`. An unresolvable ref fails and changes nothing.
- Every `dockitty-*` call in the Makefile passes `--astro-config astro.config.mjs` (FR-009; none yet).

## Context & Constraints

Spec FR-005, FR-006, FR-009, NFR-004. Complexity <= 15; mypy/ruff clean.

## Subtasks & Detailed Guidance

### Subtask T006 – Failing tests
`tests/docs/test_site_bump.py`: pure rewrite of a fixture `package.json` from a fixture toolkit manifest; ref resolution (40-hex passthrough, peeled tag preferred, missing ref refused) with an injected `ls-remote` runner; peer range translation.

### Subtask T007 – `site_bump.py`
Network reads behind injectable callables; CLI `python -m scripts.docs.site_bump REF`.

### Subtask T008 – Makefile
Two targets with `##` help.

## Risks & Mitigations

- Network in tests: none; seams injected.

## Branch Strategy

`single_branch` Mission: work in the repository root checkout on `issue-6930-docsite-scaffold`; commits land there directly.

## Review Guidance

- Red→green: the acceptance-test commit precedes the implementation commit and was red on its parent.
- Charter: single exclusion authority, no PAT/secret, SHA-pinned actions, DocFX untouched, Mission terminology.
- Grounding: `research/code-grounding.md`; decisions: `traces/design-decisions.md`.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.
