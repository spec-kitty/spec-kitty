---
work_package_id: WP05
title: Adjudication dossier for safe-as-written hotspots + false-positives
dependencies: []
requirement_refs:
- C-001
- FR-005
planning_base_branch: fix/ghactions-sonar-hardening
merge_target_branch: fix/ghactions-sonar-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/ghactions-sonar-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ghactions-sonar-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T009
history:
- created by /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: kitty-specs/ghactions-sonar-hardening-01M2FYX1/
create_intent:
- kitty-specs/ghactions-sonar-hardening-01M2FYX1/adjudication.md
execution_mode: planning_artifact
model: sonnet
owned_files:
- kitty-specs/ghactions-sonar-hardening-01M2FYX1/adjudication.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load your profile: `spec-kitty agent profile show implementer-ivan`.

## Objective
Author `adjudication.md`: the won't-fix rationale (Sonar UI + PR body) for every in-scope
safe-as-written / false-positive `githubactions` finding — NO code edit (C-001, FR-005).

## Guidance per subtask
### T009 — Write the dossier
Enumerate (pull current lists from the Sonar API) and give each a one-line, defensible rationale:
- **S8541 `uv sync --frozen` (~46)** — `spec-kitty-cli` self-installs via the hatchling build backend; `--no-build`/`--only-binary` would break the required source build; installs are `--frozen` against a `uv.lock` with 1420 sha256 hashes (locked + integrity-verified). No untrusted package built.
- **S8541/S8544 on `uv run ... pytest`** — test invocations against an already-built venv, not installs.
- **S8544 warmup drift `--upgrade-package`** — nightly full-mode intentionally resolves latest upstream to detect drift (research D2); non-PR path; PR mode is `--frozen`.
- **S8544 release-readiness install-from-`uv export --frozen` lock** — the locked path, not unlocked.
- **S6506 / S8482 (warmup)** — URL already `https://pypi.org`; downloaded content is JSON data, only the version field is read (no code executed).
- **S6505 `npm install -g @anthropic-ai/claude-code`** — requires its install lifecycle scripts; `--ignore-scripts` would break the tool. `npx markdownlint-cli2 ... || true` — non-blocking linter.
Group by rule; cite file:line where useful. State clearly at the top that these are HOTSPOT-REVIEW / won't-fix items, separate from the code fixes in WP01-04.

## Branch Strategy
Base + merge target `fix/ghactions-sonar-hardening`; this WP writes a mission artifact (planning partition), no workflow edits.

## Definition of Done
- adjudication.md lists every in-scope safe-as-written/FP finding with rationale (FR-005); zero code edits (C-001).

## Risks / reviewer guidance
- **Reviewer**: confirm the dossier makes NO code change and each rationale is technically correct (esp. the hatchling-self-install claim for the 46 uv-sync hotspots).
