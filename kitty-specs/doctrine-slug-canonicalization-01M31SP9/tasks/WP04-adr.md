---
work_package_id: WP04
title: ADR + changelog for the canonical slug convention
dependencies:
- WP01
requirement_refs:
- FR-008
planning_base_branch: fix/doctrine-slug-canonicalization
merge_target_branch: fix/doctrine-slug-canonicalization
branch_strategy: Planning artifacts for this mission were generated on fix/doctrine-slug-canonicalization. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctrine-slug-canonicalization unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
history:
- at: '2026-09-21T11:10:00+00:00'
  actor: claude
  note: WP created by /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/adr/3.x/
create_intent:
- docs/adr/3.x/2026-09-21-1-kebab-canonical-doctrine-artifact-slug.md
execution_mode: code_change
owned_files:
- docs/adr/3.x/2026-09-21-1-kebab-canonical-doctrine-artifact-slug.md
- CHANGELOG.md
role: curator
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Run `/ad-hoc-profile-load curator-carla` (or `spec-kitty agent profile show curator-carla` + `spec-kitty charter context --action implement --json`) and apply it. State which you applied.

## Objective

Record the canonical-convention decision as an ADR and a changelog entry, so the reasoning (and the dropped-migration rationale) is durable. Read `research.md` (Decisions 1–6 + Adversarial evidence) — the ADR is a distillation of it. Depends on WP01 (the decision is realised there).

## Subtasks

### T017 — Author the ADR
- Create `docs/adr/3.x/2026-09-21-1-kebab-canonical-doctrine-artifact-slug.md` following `docs/adr/` conventions (check a recent 3.x ADR for the exact frontmatter/heading shape). Content:
  - **Context**: three surfaces (scaffolder / registration engine / bundle validator) derived a doctrine artifact's on-disk slug independently and disagreed → `charter bundle validate` reported 2 errors per project directive (#4832) and rejected the engine's own `agent_profile`/`procedure` sidecars (#4833, `procedure` a latent twin).
  - **Decision**: kebab-case is the canonical filename/slug; `id` is preserved and formally decoupled from slug (built-in precedent: a descriptive slug decoupled from the authored id). A single pure `slug_for(kind, id)` authority (preserving `quote(…, safe="")`) serves the scaffolder and engine; the bundle validator is hybrid manifest-driven (manifest for registered artifacts, filesystem walk for orphans/legacy); the recognised-kind set derives from one importable `DIRECT_WRITE_KINDS` constant.
  - **Consequences**: new artifacts born validate-clean; existing SCREAMING-filename repos validate green via the manifest **without renaming** (migration deliberately dropped — a rename is cosmetic and would risk silently dropping stem-keyed directive activations, #3816 class); the drift class is closed by construction (DIRECTIVE_043); #4834 path-update fixed independently.
  - Reference the post-plan brownfield adversarial point-cut (research.md § Adversarial evidence).

### T018 — Changelog entry [P]
- Add a `CHANGELOG.md` entry under the current `[Unreleased]` section (Fixed) summarising the #4832/#4833 fix + #4834, matching the changelog's house style (a single dense bullet with the before/after and the issue refs). Note the go-forward-only (no migration) decision.

## Branch Strategy
Base/merge: `fix/doctrine-slug-canonicalization`. Topology coord. This is a documentation WP.

## Definition of Done
- ADR file present with Context / Decision / Consequences, matching `docs/adr/` conventions.
- CHANGELOG.md entry added under `[Unreleased]`.
- Markdown lints clean (if a docs lint runs).

## Risks
- ADR frontmatter/numbering drift — copy the shape from a recent 3.x ADR; pick a non-colliding `-1-` suffix for the date.

## Reviewer guidance
Confirm the ADR states the dropped-migration rationale (not just the kebab decision) and cites the adversarial evidence; confirm the changelog bullet names #4832/#4833/#4834.
