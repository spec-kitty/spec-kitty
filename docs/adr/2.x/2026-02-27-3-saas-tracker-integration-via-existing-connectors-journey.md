---
title: SaaS Tracker Integration via Existing Connectors Journey
description: Folds tracker binding, snapshot ingestion, and drift reporting into the established connectors and dashboard journey instead of building a parallel hosted surface.
status: Accepted
date: '2026-02-27'
doc_status: active
kind: ADR
updated: '2026-02-27T00:00:00Z'
---

## Context and Problem Statement

Tracker integration requires team binding, work-package mapping, sync telemetry, drift reporting, and snapshot ingestion. A separate disconnected SaaS surface would duplicate navigation and break established user flows.

SpecKitty SaaS already has connector patterns, dashboards, and activity feed conventions that users rely on.

## Decision Drivers

1. Preserve coherent user journey in existing app information architecture.
2. Reuse mature connectors domain and webhook style patterns.
3. Minimize regression risk in production dashboards/nav.
4. Enable phased rollout with team-scoped flags.

## Considered Options

1. Build standalone tracker app area/navigation.
2. Integrate tracker capability into existing `apps/connectors` + dashboard views (chosen).
3. Delay SaaS integration and keep tracker entirely CLI-local.

## Decision Outcome

**Chosen option:** integrate tracker binding, snapshot ingestion, and tracker projections into existing connectors + dashboard flow.

### Required Behavior

1. Add tracker binding and mapping models inside `apps/connectors`.
2. Expose tracker APIs under `/api/v1/connectors/trackers/...`.
3. Add snapshot ingestion endpoint (`/api/v1/connectors/trackers/snapshots/`) with idempotency receipts.
4. Render tracker health/state in existing project/work-package detail surfaces.
5. Render tracker sync/drift events in existing activity feed patterns.
6. Roll out via team-scoped waffle flag for SaaS tracker capability.

### Consequences

#### Positive

1. Faster adoption through familiar navigation and pages.
2. Lower implementation risk through reuse of established domain boundaries.
3. Better observability consistency with existing event rows/cards.

#### Negative

1. Requires careful migration/test coverage in existing pages.
2. Some model growth in connectors domain.

#### Neutral

1. v1 is read/map/observe on SaaS side; outbound writes are deferred.

### Confirmation

This decision is validated when:

1. Connectors pages show tracker binding status without separate app navigation.
2. Project detail includes tracker health summary.
3. Work-package detail shows mapped external issue state.
4. Snapshot ingestion is idempotent by receipt key.
5. Existing GitHub webhook behavior remains unchanged.

## Pros and Cons of the Options

### Option 1: Standalone tracker app surface

**Pros:**

1. Strong functional separation.

**Cons:**

1. Fragmented UX and duplicate navigation.
2. Higher delivery/regression risk.

### Option 2: Existing connectors/dashboard integration (Chosen)

**Pros:**

1. Cohesive user journey.
2. Maximum reuse of existing patterns.

**Cons:**

1. Tighter coupling to current page architecture.

### Option 3: CLI-only tracker with no SaaS journey

**Pros:**

1. Lowest SaaS implementation effort.

**Cons:**

1. No team-level visibility or centralized operations.

## More Information

1. Connectors models and endpoints:
   `<spec-kitty-saas-repo>/apps/connectors/models.py`
   `<spec-kitty-saas-repo>/apps/connectors/urls.py`
   `<spec-kitty-saas-repo>/apps/connectors/views.py`
2. Dashboard integrations:
   `<spec-kitty-saas-repo>/apps/web/views.py`
   `<spec-kitty-saas-repo>/templates/web/dashboards/project_detail.html`
   `<spec-kitty-saas-repo>/templates/web/dashboards/wp_detail.html`
