---
work_package_id: WP03
title: docs-site router job
dependencies:
- WP01
- WP02
requirement_refs:
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- SC-001
- SC-003
- SC-004
planning_base_branch: issue-6930-docsite-scaffold
merge_target_branch: issue-6930-docsite-scaffold
branch_strategy: Planning artifacts for this mission were generated on issue-6930-docsite-scaffold. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6930-docsite-scaffold unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 1 - Scaffold
history:
- at: '2026-11-02T07:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/ci-router.yml
create_intent:
- tests/ci/test_docs_site_job.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- tests/release/ci_retirement_scrub.json
- tests/ci/test_docs_site_job.py
- docs/changelog/unreleased/6930*.md
- docs/changelog/unreleased/7066.internal.md
- scripts/ci/router_gate.py
- tests/architectural/test_dual_mode_contract.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – docs-site router job

## ⚡ Do This First: Load Agent Profile

Load profile `implementer-ivan` (role: implementer) with `/spk-charter-profile-load` before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`) and address every item.

## Objectives & Success Criteria

- New non-src filter group `docs_site`: `docs/**`, `site/**`, `.github/workflows/ci-router.yml`, `scripts/docs/site_contract.py`, `scripts/docs/_dockitty_contract.py`; a `changes.outputs.docs_site` row with the standard fold; not in the `unmatched` union.
- Job `docs-site`: `needs: [changes]`, `if: needs.changes.outputs.docs_site == 'true'`, `contents: read`, `timeout-minutes: 20`, SHA-pinned checkout / pnpm / node / upload actions, `pnpm install --frozen-lockfile` with no token, contract check, build, upload `site/dist`. Not in `router-gate.needs`.
- `--astro-config astro.config.mjs` structural check over workflow and Makefile, with a self-mutation fixture.
- Scrub registry row; changelog fragment.

## Context & Constraints

Spec FR-007..FR-009, NFR-001..003, C-001, C-002. `_GROUP_REF` pitfall (grounding). DocFX untouched.

## Subtasks & Detailed Guidance

### Subtask T009 – Failing tests
`tests/ci/test_docs_site_job.py`: selection for docs/site/src paths, non-src group, job wiring, not in router-gate, frozen install, no secrets, SHA pins, fork-guard reachability through `changes`, `--astro-config` invariant + self-mutation, scrub row parity, `docs-pages.yml` untouched.

### Subtask T010 – group, output, scrub row
### Subtask T011 – job
### Subtask T012 – changelog fragment

## Risks & Mitigations

- Existing router gates may pin job/group sets: run them (named list in grounding).

## Branch Strategy

`single_branch` Mission: work in the repository root checkout on `issue-6930-docsite-scaffold`; commits land there directly.

## Review Guidance

- Red→green: the acceptance-test commit precedes the implementation commit and was red on its parent.
- Charter: single exclusion authority, no PAT/secret, SHA-pinned actions, DocFX untouched, Mission terminology.
- Grounding: `research/code-grounding.md`; decisions: `traces/design-decisions.md`.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP03 --note "..."`.
