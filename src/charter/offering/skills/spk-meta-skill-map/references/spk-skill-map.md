# Spec Kitty 3.2.0 Skill Map

Legacy family: pre-3.2.0 `spec-kitty-*` compatibility skills. They remain for
detailed workflows or aliases while new public operating skills use `spk-*`.

## Start

- `spk-start-here`: first route for users and agents.
- `spk-start-first-feature`: first mission walkthrough.
- `spk-start-command-map`: command-to-skill map.
- `spk-start-agent-surface`: host/surface compatibility.

## Mission

- `spk-mission-specify`: specification phase.
- `spk-mission-plan`: planning phase.
- `spk-mission-tasks`: tasks and WP authoring.
- `spk-mission-types`: mission type selection.
- `spk-mission-research`: research workflows.
- `spk-mission-documentation`: documentation missions.

## Run

- `spk-run-next`: runtime-next control loop.
- `spk-run-program-orchestrate`: multi-mission program orchestration.
- `spk-run-implement-review`: WP implementation/review orchestration.
- `spk-run-review-wp`: single WP review.
- `spk-run-verdict-capture`: record a WP review verdict via the deterministic event-log seam.
- `spk-run-blocked-recovery`: blocked-state repair.

## Gate

- `spk-gate-accept`: final readiness gate.
- `spk-gate-consolidate`: consolidation gate.
- `spk-gate-mission-review`: post-merge mission review.
- `spk-gate-retrospective`: post-merge retrospective.

## Admin

- `spk-admin-setup-doctor`: install and repair.
- `spk-admin-agent-config`: agent setup.
- `spk-admin-upgrade`: upgrade and migrations.
- `spk-admin-dashboard`: status and dashboard.
- `spk-admin-git-workflow`: git and worktree workflows.

## Team

- `spk-team-auth`: auth and accounts.
- `spk-team-sync`: tracker sync (local pull/push/run, hosted binding).
- `spk-team-tracker`: tracker workflows.
- `spk-team-connectors`: connector integrations.

## Doctrine

- `spk-doctrine-charter`: charter workflows.
- `spk-doctrine-glossary`: terminology.
- `spk-doctrine-spdd-reasons`: REASONS Canvas.
- `spk-doctrine-profile-load`: agent profiles.
- `spk-doctrine-show-me`: compact visuals, diagram selection, and TUI status rendering.
- `spk-doctrine-semantic-compression`: behavior-preserving code reduction.
- `spk-doctrine-bulk-edit`: bulk edit classification.

## Integration

- `spk-integrate-orchestrator-api`: external orchestrator API.

## Meta

- `spk-meta-skill-map`: discovery and naming convention.
- `spk-meta-skill-authoring`: authoring future `spk-*` skills.

## Legacy Compatibility

- `spec-kitty-runtime-next` -> prefer `spk-run-next`
- `spec-kitty-runtime-review` -> prefer `spk-run-review-wp`
- `spec-kitty-implement-review` -> prefer `spk-run-implement-review`
- `spec-kitty-mission-system` -> prefer `spk-mission-types`
- `spec-kitty-charter-doctrine` -> prefer `spk-doctrine-charter`
- `spec-kitty-setup-doctor` -> prefer `spk-admin-setup-doctor`
- `spec-kitty-git-workflow` -> prefer `spk-admin-git-workflow`
- `spec-kitty-orchestrator-api-operator` -> prefer `spk-integrate-orchestrator-api`
