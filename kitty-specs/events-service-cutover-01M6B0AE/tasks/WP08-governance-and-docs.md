---
work_package_id: WP08
title: Governance, docs and changelog
dependencies:
- WP07
requirement_refs:
- FR-016
- FR-017
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T031
- T032
- T033
phase: Phase 5 - Polish
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- CLAUDE.md
- AGENTS.md
- .kittify/charter/charter.md
- docs/plans/events-domain-move/plan.md
- docs/development/reference/**
- docs/architecture/**
- docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md
- docs/changelog/CHANGELOG.md
- docs/context/team-kitty.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the assigned profile with the `/spk-charter-profile-load` skill (`scribe-sally`), then load `spec-kitty charter context --action implement`. Read `research/code-grounding.md` for the facts this WP relies on.

## Branch Strategy

- Planning/base branch: `issue-6915-events-service-cutover`; final merge target: `issue-6915-events-service-cutover`.
- Topology `single_branch`: no lane worktree. `lanes.json` holds one repo-root lane; work in the repository root checkout.
- Start with: `spec-kitty agent action implement WP08 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

Guidance matches the code. Requirements: FR-016, FR-017. Factual and short; the charter wins over CLAUDE.md (flag drift, never pick silently). Audience: maintainers.

## Subtasks

### T031 — CLAUDE.md, AGENTS.md, charter

- CLAUDE.md "Team Kitty" producer bullet and "Shared Package Boundary → Events services": the first `service-v*` pin is vendored (read service, `service-v0.1.0-rc.1`, CI conformance only); `services/` and the moving `contracts/` are removed; `make sync-services` is wired into `dev-setup` (extras only) and CI; the frozen-set sentence and `test_events_import_frozen.py` reference go. Keep "binding the EventBridge (#6195)" and the write-service pin as pending.
- AGENTS.md: same lines, if present (grep).
- `.kittify/charter/charter.md`: "Events services" paragraph — "This mechanism is the target state: decided, not yet built" → built (#6590) and the read-service pin vendored; drop the frozen-set sentence (the gate is removed); Attribution: the Gradle wrapper under `services/` is gone, so drop it from the third-party list (keep HumanLayer's `show-me`). Add an `Updated:` header line (2026-11-01) in the charter's own style. Charter edits are governance: keep them to these facts.
- Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`.

### T032 — Docs pointers [P]

- `docs/plans/events-domain-move/plan.md`: status line and §4 step 5 → done in this PR; note the drift found (grounding §1).
- `docs/architecture/event-ledger-writers-and-readers.md` was frozen (ADR D-1): it moves to spec-kitty-events. Replace its body with a short pointer to spec-kitty-events (keep frontmatter; set `updated:`), or leave it untouched if the ADR says core keeps it — read D-1 ("moves … stays frozen in core, and corrections are made there"): replace with a pointer now that the freeze is lifted by removal; if unsure, leave it and note it.
- `docs/development/reference/{ci-gate-mechanics,events-in-core,lock-interop-spike}.md`, `docs/architecture/status-model.md` and the C4 pages that name `services/` or `mission-status-api.yml`: one-line pointers to spec-kitty-events `service/` and `contracts/`, and to `pins/read-service.source.yaml`.
- ADR `2026-10-29-1`: add a status/confirmation note only if the ADR set's own conventions call for it (check how other 4.x ADRs record a confirmation, e.g. an "Amendment"/"Confirmation" note). If added: one dated line stating the Confirmation holds as of this PR.

### T033 — Changelog [P]

`docs/changelog/CHANGELOG.md` Unreleased: one entry (Changed/Removed per the file's style) — core pins the read service from spec-kitty-events `service-v0.1.0-rc.1`; `services/`, `contracts/` (except handoff fixtures) and three workflows removed; `make dev-setup` fetches the pinned extras; releases verify the service pins. `Refs #6915`.

## Validation

```bash
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
git grep -n "services/mission-status-api" -- docs CLAUDE.md AGENTS.md .kittify | grep -v "docs/adr/\|docs/archive/\|kitty-specs/"   # only history remains
```
Plus the docs lint the repo runs (check `make docs-lint` / `ci-router` docs-lint job) on changed docs.

## Definition of Done
- No live guidance says the pin mechanism is unbuilt or that core holds `services/`.
