---
title: Operations
description: 'Durable operational runbooks for Spec Kitty: deployment, CI/CD setup, and standing CI-gate procedures that outlive any single mission.'
doc_status: active
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-10-04'
related:
- docs/configuration/index.md
- docs/guides/index.md
- docs/index.md
- docs/operations/how-to-maintain.md
- docs/operations/identity-boundary-ci-gate.md
- docs/operations/manual-test-plan.md
- docs/operations/internal-hosted-readiness.md
- docs/operations/p0-baseline-refresh.md
- docs/operations/recovery-index.md
- docs/operations/ssh-deploy-keys.md
- docs/operations/sync-daemon-orphan-cleanup.md
- docs/operations/upgrade-with-live-lanes-recovery.md
- docs/plans/index.md
---
# Operations

Durable operational procedures — deployment, on-call, incident, and standing
CI-gate runbooks. These pages are maintainer-facing references that stay correct
across missions (unlike the effort-scoped notes that live under
[`../plans/`](../plans/index.md)).

## Pages

- [SSH deploy-key setup for CI/CD](ssh-deploy-keys.md) — one-time deploy-key provisioning runbook.
- [Identity-boundary CI gate](identity-boundary-ci-gate.md) — retired record of the former `drift-detector` required check, deleted with the sync transport.
- [Recovery guides](recovery-index.md) — task-oriented recovery procedures, including [logged-out on a connected teamspace](logged-out-teamspace.md).
- [Recovery after an upgrade with live lanes](upgrade-with-live-lanes-recovery.md) — recover when `consolidate`, review or implement refuses on `.kittify/metadata.yaml` after an upgrade mid-Mission.
- [Sync daemon orphan cleanup](sync-daemon-orphan-cleanup.md) — operator runbook for stale sync daemons.
- [Internal hosted-readiness mode (pre-launch)](internal-hosted-readiness.md) — the hidden SaaS rollout-gate path for internal dogfooding, not for end users.
- [How to maintain the issue tracker](how-to-maintain.md) — maintainer runbook for tracker structure, priority levels, issue types, and milestone/release-goal conventions.
- [P0 baseline refresh](p0-baseline-refresh.md) — targeted P0 test-failure baseline record and its per-cluster reproduction status.
- [Manual test plan](manual-test-plan.md) — comprehensive manual verification plan across all repositories for Beta/GA readiness (SaaS, CLI, connectors, webhooks).

## See also

- [Documentation home](../index.md)
- [Guides](../guides/index.md)
- [Configuration](../configuration/index.md)
