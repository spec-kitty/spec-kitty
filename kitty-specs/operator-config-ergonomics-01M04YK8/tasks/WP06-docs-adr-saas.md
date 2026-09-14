---
work_package_id: WP06
title: Docs, ADRs, Team Kitty (SaaS) architecture
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
requirement_refs:
- FR-011
- C-007
planning_base_branch: fix/operator-config-ergonomics
merge_target_branch: fix/operator-config-ergonomics
branch_strategy: Planning artifacts for this mission were generated on fix/operator-config-ergonomics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/operator-config-ergonomics unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
- T029
- T030
history:
- '2026-08-16: authored by /spec-kitty.tasks'
agent_profile: curator-carla
authoritative_surface: docs/
create_intent:
- docs/adr/3.x/2026-08-16-1-operator-config-env-expansion-seam.md
- docs/adr/3.x/2026-08-16-4-rc-release-channel.md
- docs/architecture/team-kitty-saas.md
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- docs/adr/3.x/2026-08-16-1-operator-config-env-expansion-seam.md
- docs/adr/3.x/2026-08-16-4-rc-release-channel.md
- docs/architecture/team-kitty-saas.md
- docs/api/environment-variables.md
- docs/api/configuration.md
- docs/guides/how-to/installation/install-and-upgrade.md
- docs/operations/sync-drain.md
- docs/guides/project-sync-consent.md
- docs/operations/internal-hosted-readiness.md
- src/doctrine/skills/spk-team-sync/SKILL.md
- src/doctrine/skills/spk-team-auth/SKILL.md
- src/doctrine/skills/spk-team-tracker/SKILL.md
- CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load `curator-carla` (implementer/curator) via `/ad-hoc-profile-load`.

## Objective
Document the shipped behavior: two ADRs, a NEW Team Kitty (SaaS) architecture section with interaction diagrams, updated consumption docs, and the SOURCE `spk-team-*` skills. Deps: **WP01–WP05** (documents their behavior). Requirement: FR-011; SC-006 fixes exactly 2 ADRs + ≥1 interaction diagram + the Team Kitty section.

## Branch Strategy
Base + merge target: `fix/operator-config-ergonomics`. Lane worktree from `lanes.json`.

## Subtasks

### T026 — ADR 1 — env-resolution seam + provenance form + kernel layering
- `docs/adr/3.x/2026-08-16-1-operator-config-env-expansion-seam.md` following `docs/architecture/adr-template.md`. Promote the mission [design-record.md](../design-record.md): decision C (kernel expander + token provenance + two-tier `.kitty.env` via `SPEC_KITTY_HOME`), drivers, rejected options (repo-relative, env-template-without-expander, `CONFIG_HOME`). Status: Accepted.

### T027 — ADR 2 — default-off rc release channel
- `docs/adr/3.x/2026-08-16-4-rc-release-channel.md`: default-off consumer channel, pinned-rc install, stable-users-never-nagged; scope boundary vs #3047 producer half. Status: Accepted.

### T028 — Team Kitty (SaaS) architecture section + interaction diagram
- `docs/architecture/team-kitty-saas.md` (new; follow `ARCHITECTURE_DOCS_GUIDE.md`, link up from `docs/architecture/index.md`). Include a Mermaid interaction/sequence diagram of the full flow: opt-in/consent → project-store (legacy→project) migration → admission/delivery-target → auth refresh → `import-history` drain-to-ledger → `sync now` to `team.spec-kitty.ai`. This is the end-to-end flow that was undocumented when opt-in kept hitting gates.

### T029 — Consumption docs + SOURCE skills
- `docs/api/environment-variables.md`: add `SPEC_KITTY_PACKS_ROOT` (canonical), the `.kitty.env` mechanism, `SPEC_KITTY_PRERELEASE`; clarify `SPEC_KITTY_HOME` locator role.
- `docs/api/configuration.md`: the single `env_file` pointer key.
- `docs/guides/how-to/installation/install-and-upgrade.md`: rc opt-in.
- `docs/operations/sync-drain.md`, `docs/guides/project-sync-consent.md`, `docs/operations/internal-hosted-readiness.md`: replace manual `SPEC_KITTY_ENABLE_SAAS_SYNC`/`SPEC_KITTY_SAAS_URL` export guidance with the `.kitty.env` path.
- SOURCE skills `src/doctrine/skills/spk-team-{sync,auth,tracker}/SKILL.md`: swap the hardcoded manual export for `.kitty.env` (edit SOURCE, NOT `.claude/` copies). Run `pytest tests/architectural/test_no_legacy_terminology.py` after prose edits.

### T030 — CHANGELOG
- `CHANGELOG.md` entry for the mission (aggregates all WPs; the `pyproject.toml` version bump was made in WP02 per C-007).

## Definition of Done
- SC-006: exactly 2 ADRs under `docs/adr/3.x/` + a Team Kitty (SaaS) section with the interaction diagram; consumption docs + SOURCE skills updated; CHANGELOG entry present.
- Terminology guard green (`pytest tests/architectural/test_no_legacy_terminology.py`) — run BEFORE finishing (RED-first equivalent for prose: the guard must pass on the edited docs/skills).
- Mermaid diagram renders; ADRs follow `adr-template.md`; `docs/architecture/index.md` links to the new section.

## Reviewer guidance
- Verify the interaction diagram covers the full opt-in→sync flow (not just a subset).
- Verify SOURCE skills edited, not `.claude/` copies.
- Verify exactly 2 ADRs (SC-006), not 1 or 3.
