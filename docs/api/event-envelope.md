---
title: Event Envelope Reference
description: Reference for Spec Kitty event envelopes. Understand the 3.0.0 contract schema, canonical terms, and validation parameters for outbound payloads.
doc_status: active
updated: '2026-06-09'
related:
- docs/migrations/feature-flag-deprecation.md
- docs/migrations/mission-id-canonical-identity.md
- docs/migrations/mission-type-flag-deprecation.md
---
# Event Envelope Reference

This document describes the vendored machine-facing contract enforced by
[`src/specify_cli/core/upstream_contract.json`](https://github.com/spec-kitty/spec-kitty/blob/main/src/specify_cli/core/upstream_contract.json)
and `specify_cli.core.contract_gate.validate_outbound_payload()`.

The current contract version is `3.0.0`.

## Canonical Terms

- `Mission Type` is the reusable blueprint key, serialized as `mission_type`.
- `Mission` is the tracked item under `kitty-specs/<mission-slug>/`. Its **canonical** machine identity is `mission_id` (a ULID). The human-readable `mission_slug` and the display-only `mission_number` are serialized alongside it for context, but **selectors and event routing use `mission_id`**.
- `Mission Run` is the runtime/session concept. It is not serialized as tracked-mission identity.

See [Mission ID Canonical Identity Migration](../migrations/mission-id-canonical-identity.md) for the rationale and ADR 2026-04-09-1.

## Core Envelope

The upstream event envelope requires these top-level fields:

| Field | Required | Notes |
|---|---|---|
| `schema_version` | Yes | Must equal `3.0.0`. |
| `build_id` | Yes | Producer build identifier. |
| `aggregate_type` | Yes | Allowed: `Mission`, `WorkPackage`, `MissionDossier`. Forbidden: `Feature`. |
| `event_type` | Yes | Event name for the emitted record. |

Forbidden top-level fields in the envelope:

- `feature_slug`
- `feature_number`

## Mission-Scoped Payloads

Any first-party payload that identifies a tracked mission must carry the
canonical identity fields:

| Field | Required | Meaning |
|---|---|---|
| `mission_id` | Yes | Canonical ULID machine identity (e.g. `01J6XW9KQT7M0YB3N4R5CQZ2EX`). Aggregate routing uses this field. |
| `mission_slug` | Yes | Human-readable mission slug (e.g. `my-feature`). Display context only. |
| `mission_number` | Yes, nullable | Display-only numeric prefix (e.g. `77`). `null` pre-merge, assigned at merge time. Never used for identity. |
| `mission_type` | Yes | Blueprint key (for example `software-dev`). |

Forbidden mission-scoped payload fields:

- `feature_slug`
- `feature_number`
- `feature_type`

This applies to first-party machine-facing payloads such as status snapshots,
derived board/progress views, context tokens, acceptance matrices, merge-gate
evaluations, `next --json` decisions, and `orchestrator-api` response payloads.

## Body Sync Payloads

The `body_sync` contract requires:

| Field | Required |
|---|---|
| `project_uuid` | Yes |
| `mission_slug` | Yes |
| `target_branch` | Yes |
| `mission_type` | Yes |
| `manifest_version` | Yes |

Forbidden body-sync fields:

- `feature_slug`
- `mission_key`

## Compatibility Notes

- Historical read paths may still accept `feature_slug` when ingesting old
  artifacts such as legacy `status.events.jsonl` records.
- Active first-party emitters must not dual-write `feature_slug`.
- `mission_run_slug` is forbidden.
- Catalog event names remain `MissionCreated` and `MissionClosed`.
- `aggregate_type="MissionRun"` is forbidden.

## Migration

Operator-facing CLI migration guidance lives here:

- [Feature Flag Deprecation](../migrations/feature-flag-deprecation.md)
- [Mission Type Flag Deprecation](../migrations/mission-type-flag-deprecation.md)

The migration policy is asymmetric:

- human/operator CLI surfaces may still accept hidden deprecated aliases during
  the migration window
- machine-facing contracts are canonical-only on `mission_*`
