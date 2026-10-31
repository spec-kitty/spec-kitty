---
work_package_id: WP01
title: ADR amendment and governance clarifications
dependencies: []
requirement_refs:
- FR-001
- C-002
planning_base_branch: companion-services-wheel
merge_target_branch: companion-services-wheel
branch_strategy: Planning artifacts for this mission were generated on companion-services-wheel. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into companion-services-wheel unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Decision record
history:
- at: '2026-10-31T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/4.x/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md
- CLAUDE.md
- docs/plans/events-domain-move/plan.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – ADR amendment and governance clarifications

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: docs/adr/4.x/`.

---

## Branch Strategy

- Planning base and final merge target: `companion-services-wheel`.
- Topology `single_branch`: no lane worktree. Work in the repository root checkout on `companion-services-wheel`.
- Start with `spec-kitty agent action implement WP01 --agent claude --mission companion-services-wheel-01M694B1`.


## Objective

Record operator ruling 2 of 2026-10-31 (#6117) and the plan-time workspace-member ruling as an amendment to
ADR 2026-10-29-1, before any code lands (FR-001). This is the single recorded authority for the companion wheel.

## Context

- ADR: `docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md`. D-4 already reserves
  "an install-provided slot ... so a companion platform wheel can be added later". Amendment 2026-10-30 is the format precedent:
  a `## Amendment <date> (Accepted): <title>` section at the end; the body above stays unchanged.
- The rulings: `docs/plans/events-domain-move/companion-wheel-research.md` §3 (all 12 as recommended), plus Decision Moment
  `01M694GPQYVGRKCF3B582FWQ1Y` (uv workspace member, ruled A).
- **Do not** edit `docs/architecture/event-ledger-writers-and-readers.md` (D-9 frozen; `tests/architectural/test_events_import_frozen.py`).

## Subtasks

### T001 — Amendment 2026-10-31 (Accepted): the optional companion services wheel

Append a section after Amendment 2026-10-30. Cover, as short bullets (house style: one fact per bullet):
1. **Name**: distribution `spec-kitty-services`, import package `spec_kitty_services`, source `packages/spec-kitty-services/` (outside `src/`).
2. **Install**: extra `services` on `spec-kitty-cli` → `spec-kitty-services==<cli version>`; a direct `pip install spec-kitty-services==<v>` also works.
3. **Version lock**: companion version == CLI version == extra pin; built from the same release commit's `pins/`; embedded `_manifest.json`.
   Provider offers nothing on a version or host mismatch, so a skew degrades to the fetch; resolution still digest-checks.
4. **Contents**: native write-service and charter-service for the wheel's target only. Never the read service (D-6), no jar, no extras assets.
5. **Fallback**: a binary-free `py3-none-any` wheel; every host can install the extra.
6. **Tags**: `manylinux_2_39_x86_64`, `manylinux_2_39_aarch64`, `macosx_11_0_arm64`, `win_amd64`; the glibc floor is a build input (2.39 = ubuntu-24.04 builders).
7. **Build**: `scripts/build_services_wheel.py` fetches every asset through `kernel.service_artifacts.fetch_asset` (sha256-verified), never rebuilds; stdlib wheel writer; deterministic output.
8. **Size**: fail above 95 MB per wheel, warn above 60 MB (PyPI's per-file cap is 100 MB; plan §3.4). Splitting per service needs its own amendment.
9. **Release**: `build-companion-wheels` → `publish-companion-pypi` (environment `pypi-services`, Trusted Publishing) → `publish-pypi`.
10. **Empty pins**: only the fallback wheel.
11. **Resolution order unchanged** (D-5): explicit → install slot → cache → jar → refusal; the slot is digest-checked and a mismatch refuses.
12. **uv workspace member**: `[tool.uv.workspace]` + `[tool.uv.sources] spec-kitty-services = { workspace = true }` so the exact extra locks;
    this is a first-party member, not a dev override of an external package (the Shared Package Boundary rule is unchanged).
13. **Operator prerequisites**: a PyPI pending Trusted Publisher for `spec-kitty-services` and the GitHub environment `pypi-services`.

Also update the frontmatter `description`? **No** — keep it; only append. Add `updated:` only if the frontmatter already has one (it does not; leave it).

### T002 — CLAUDE.md clarification

In CLAUDE.md "Shared Package Boundary" → the bullet "**Dev editable/path overrides:** never committed in `pyproject.toml [tool.uv.sources]`",
append one sentence: a first-party uv workspace member (`spec-kitty-services`, `packages/spec-kitty-services/`, ADR 2026-10-29-1 Amendment
2026-10-31) is not an override and is allowed.

### T003 — Plan §3.4 pointer

In `docs/plans/events-domain-move/plan.md` §3.4, add one line after the recommendation: option C's companion is now decided by ADR 2026-10-29-1
Amendment 2026-10-31 (#6904). Update its frontmatter `updated:` to `'2026-10-31'`.

## Validation

- `uv run --frozen pytest tests/architectural/test_events_import_frozen.py -q` (frozen paths untouched).
- `pytest tests/architectural/test_no_legacy_terminology.py -q` (prose touched).
- `git diff --stat` touches only the three owned files.

## Definition of Done

- The amendment covers all 13 points above; CLAUDE.md and plan.md each carry one added sentence/line.

## Commit discipline

- The red test is its own commit **before** the implementation commit (charter ATDD-First, C-011).
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier.
