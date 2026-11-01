---
work_package_id: WP04
title: doc-kitty build evidence
dependencies:
- WP03
requirement_refs:
- FR-004
- FR-011
- C-002
- C-004
- SC-001
planning_base_branch: issue-6929-docsite-frontmatter-migration
merge_target_branch: issue-6929-docsite-frontmatter-migration
branch_strategy: Planning artifacts for this mission were generated on issue-6929-docsite-frontmatter-migration. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6929-docsite-frontmatter-migration unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
phase: Phase 4 - Evidence
history:
- at: '2026-11-01T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: kitty-specs/docsite-frontmatter-migration-01M6BRJK/
create_intent:
- kitty-specs/docsite-frontmatter-migration-01M6BRJK/build-evidence.md
execution_mode: planning_artifact
owned_files:
- kitty-specs/docsite-frontmatter-migration-01M6BRJK/build-evidence.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – doc-kitty build evidence

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- The spike's one-off doc-kitty build of this branch's `docs/` passes (FR-011, SC-001), with `indexBasename: ['README', 'index']`, native `exclude` (`archive`, `reports`, `convergence`, `changelog/unreleased`), `DK_PUBLISH_DRAFTS=off`, doc-kitty pinned by commit (`fe835cd` or later `main`).
- A control build on the base tree fails (FR-004/FR-011 non-vacuity).
- `build-evidence.md` records commands, versions, page count, and every gap found (upstream gaps filed or named, never shimmed — C-004).

## Context & Constraints

- Everything runs in `/tmp`; nothing from the site project is committed (C-002; #6930 owns `site/`).
- The four dual-index folders collide until #6928 lands; simulate #6928 in the `/tmp` copy only (delete `adr/{1,2,3}.x/README.md` and `architecture/README.md` there), as the spike did, and say so.
- Also run `dockitty-validate-frontmatter` and `dockitty-check-links` with `--astro-config astro.config.mjs` over the copy and record their verdicts as information (they are #6937's gates, not this issue's Done-when).

## Branch Strategy

- **Strategy**: `single_branch` on `issue-6929-docsite-frontmatter-migration`.

## Subtasks

### T016 — One-off build
Copy `docs/` to `/tmp/dk-site/docs`, apply the #6928 simulation, build with the pinned toolkit, count `dist/**/index.html` pages that are not redirect stubs, and keep the log.

### T017 — Control build
Same commands on `git archive origin/main docs` → expect failure on the first `audience` string.

### T018 — Record
Write `kitty-specs/docsite-frontmatter-migration-01M6BRJK/build-evidence.md`: toolchain versions, the exact `package.json`, `astro.config.mjs`, `content.config.ts`, commands, exit codes, page count vs the spike's 637, gate verdicts, and gaps.

## Definition of Done

- Build exit 0 recorded; control failure recorded; evidence committed.
