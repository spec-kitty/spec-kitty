---
work_package_id: WP02
title: S7637 action SHA-pinning (ci-quality.yml, ci-windows.yml) + ci-windows perm/install
dependencies: []
requirement_refs:
- FR-002
- FR-003
- NFR-001
- NFR-003
planning_base_branch: fix/ghactions-sonar-hardening
merge_target_branch: fix/ghactions-sonar-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/ghactions-sonar-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ghactions-sonar-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ghactions-sonar-hardening-01M2FYX1
base_commit: d9286ab7bb6e1c30b1a041fd73de2d889662cf66
created_at: '2026-09-14T12:54:54.017379+00:00'
subtasks:
- T003
- T004
history:
- created by /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/ci-quality.yml
- .github/workflows/ci-windows.yml
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load your profile: `spec-kitty agent profile show implementer-ivan`.

## Objective
Pin the S7637-flagged third-party actions in `ci-quality.yml` (setup-uv ×4) and `ci-windows.yml`
(paths-filter ×1) to each action's OWN current tag's full-length commit SHA (C-002), and fold in
ci-windows.yml's other in-scope findings (its S8264 permission + S8544 install) so the file lands
single-owned. Behavior-identical (NFR-001).

## Context
Match the in-repo pin style already used in `.github/actions/warmup/action.yml`
(`astral-sh/setup-uv@<sha> # v10.0.1`, `actions/checkout@<sha> # v4.4.0`): `<owner>/<action>@<full-40-char-sha> # <vX>`.

## Guidance per subtask
### T003 — SHA-pin flagged actions
- List: `curl -s "...rules=githubactions:S7637..."` filtered to ci-quality/ci-windows.
- For each flagged `uses:` at a moving tag, resolve **that tag's** current commit SHA:
  `git ls-remote https://github.com/astral-sh/setup-uv refs/tags/v5` (use the version the file currently pins — e.g. ci-quality runs setup-uv@v5; do NOT bump to v10). Pin `@<sha> # v5`.
- ci-windows paths-filter: `dorny/paths-filter@<sha> # v4` (resolve v4 tag SHA).
- **C-002**: keep each action at its CURRENT major/version — no unification, no bump.
### T004 — Fold ci-windows.yml S8264 permission + S8544, then validate
- Relocate ci-windows's workflow-level `permissions` (S8264) to the job(s) that need them (enumerate jobs first — C-003).
- Address its S8544 (self-bootstrap pip/pipx) per the adjudication note if it is the self-bootstrap case → leave + record in WP05 dossier; only pin if it is a bare 3rd-party install.
- Validate: `actionlint` / YAML parse clean on both files.

## Branch Strategy
Base + merge target `fix/ghactions-sonar-hardening`; enter the lane workspace from lanes.json.

## Definition of Done
- All in-scope S7637 sites pinned to their own-version SHA with `# vX` (FR-002); ci-windows S8264 perm relocated (FR-003); YAML valid; behavior-identical; no version bumps (C-002).

## Risks / reviewer guidance
- **Reviewer**: verify each SHA resolves to the tag the file already used (no silent bump); confirm ci-windows permission relocation left every needing job with access.
