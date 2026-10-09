---
title: Batch Event Ingest API Contract
description: Batch event ingest API contract for Spec Kitty — authentication flow, event envelope fields, request/response format, event schemas, lane vocabulary, and error categorization.
doc_status: active
updated: '2026-10-09'
type: reference
audience: docs/context/audience/internal/maintainer.md
related:
- docs/api/event-envelope.md
- docs/api/orchestrator-api.md
---
# Contract: Batch Event Ingest API

**Feature**: 039-cli-2x-readiness
**Version**: 2.0.0
**Date**: 2026-02-12
**Branch**: 2.x
**Purpose**: Enable the SaaS team to validate their batch endpoint against CLI payloads without consulting CLI source code.

---

## Table of Contents

1. [Authentication Flow](#1-authentication-flow)
2. [Event Envelope Field Reference](#2-event-envelope-field-reference)
3. [Batch Request/Response Format](#3-batch-requestresponse-format)
4. [Event Types and Payload Schemas](#4-event-types-and-payload-schemas)
5. [Lane Vocabulary (Canonical 7-Lane)](#5-lane-vocabulary-canonical-7-lane)
6. [Error Categorization](#6-error-categorization)
7. [Fixture Data](#7-fixture-data)
8. [Tracker Snapshot Publish Payload (Feature 048)](#8-tracker-snapshot-publish-payload-feature-048)

---

## 1. Authentication Flow

The CLI uses a JWT-based authentication flow with credential persistence.

### 1.1 Login (Obtain Tokens)

```
POST /api/v1/token/
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "s3cret"
}
```

**Success Response (HTTP 200)**:
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>",
  "access_lifetime": 900,
  "refresh_lifetime": 604800,
  "team_slug": "my-team"
}
```

| Response Field | Type | Required | Description |
|----------------|------|----------|-------------|
| `access` | string | Yes | JWT access token |
| `refresh` | string | Yes | JWT refresh token |
| `access_lifetime` | integer | No | Access token lifetime in seconds (default: 900 = 15 min) |
| `refresh_lifetime` | integer | No | Refresh token lifetime in seconds (default: 604800 = 7 days) |
| `team_slug` | string | No | Team identifier for the authenticated user |

**Error Response (HTTP 401)**:
```json
{
  "error": "Invalid username or password"
}
```

### 1.2 Token Refresh

```
POST /api/v1/token/refresh/
Content-Type: application/json

{
  "refresh": "<jwt_refresh_token>"
}
```

**Success Response (HTTP 200)**:
```json
{
  "access": "<new_jwt_access_token>",
  "refresh": "<new_jwt_refresh_token>",
  "access_lifetime": 900,
  "refresh_lifetime": 604800,
  "team_slug": "my-team"
}
```

**Error Response (HTTP 401)**:
The CLI clears stored credentials and prompts the user to re-authenticate.

### 1.3 Authorization Header

All authenticated requests (including batch ingest) include:
```
Authorization: Bearer <jwt_access_token>
```

### 1.4 Automatic Token Refresh Behavior

The CLI checks the access token expiry before each request:
1. If the access token is valid, use it directly.
2. If the access token is expired but the refresh token is valid, silently refresh via `/api/v1/token/refresh/`.
3. If the refresh also fails (401), clear credentials and return `None` (caller handles re-auth prompting).

### 1.5 Credential Storage

Credentials are stored on the user's machine at `~/.spec-kitty/credentials` in TOML format with `chmod 600` permissions.

```toml
[tokens]
access = "<jwt_access_token>"
refresh = "<jwt_refresh_token>"
access_expires_at = "2026-02-12T10:15:00"
refresh_expires_at = "2026-02-19T10:00:00"

[user]
username = "user@example.com"
team_slug = "my-team"

[server]
url = "https://team.spec-kitty.ai"
```

A file lock (`~/.spec-kitty/credentials.lock`) prevents concurrent access.

---

## 2. Event Envelope Field Reference

This historical batch-endpoint contract describes the retired sync transport. The external `spec-kitty-events` package's Pydantic `Event` model remains the schema reference; `src/specify_cli/sync/emitter.py` was deleted with that transport and is not a live CLI source.

### 2.1 Core Fields (Pydantic `Event` model)

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `event_id` | string | Yes | Exactly 26 chars, ULID format (Crockford Base32: `[0-9A-HJKMNP-TV-Z]{26}`) | `"01JMBY1234567890ABCDEFGH"` |
| `event_type` | string | Yes | One of the 8 known types (see Section 4) | `"WPStatusChanged"` |
| `aggregate_id` | string | Yes | Min 1 char. Entity this event modifies. | `"WP01"` or `"039-cli-2x-readiness"` |
| `payload` | object | Yes | Event-specific data (see Section 4 for per-type schemas) | `{"wp_id": "WP01", ...}` |
| `timestamp` | string | Yes | ISO 8601 with timezone (wall-clock, not used for ordering) | `"2026-02-12T10:00:00+00:00"` |
| `node_id` | string | Yes | Min 1 char. Stable machine identifier (12-char hex) | `"a1b2c3d4e5f6"` |
| `lamport_clock` | integer | Yes | >= 0, monotonically increasing per node | `42` |
| `causation_id` | string | No | 26 chars ULID if present, `null` for root events | `"01JMBY1234567890ABCDEFGI"` |

### 2.2 Extended Fields (Added by EventEmitter)

These fields are added by the CLI's `EventEmitter._emit()` method and are present on every event in the batch payload:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `aggregate_type` | string | Yes | One of: `"WorkPackage"`, `"Feature"` | `"WorkPackage"` |
| `team_slug` | string | Yes | Non-empty string. `"local"` if team unavailable. | `"my-team"` |
| `project_uuid` | string | Yes* | UUID v4 format (`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`). If missing, event is queued locally only and never sent to batch endpoint. | `"550e8400-e29b-41d4-a716-446655440000"` |
| `project_slug` | string | No | Kebab-case project name, may be `null` | `"spec-kitty"` |
| `git_branch` | string | No | Current git branch, may be `null` | `"039-cli-2x-readiness-WP07"` |
| `head_commit_sha` | string | No | Full 40-char SHA, may be `null` | `"0cf3f906f4f979a000cf04c78688a397d69b6a37"` |
| `repo_slug` | string | No | `owner/repo` format, may be `null` | `"priivacy/spec-kitty"` |

*`project_uuid` is required for events to reach the batch endpoint. Events without `project_uuid` are queued locally but never transmitted.

### 2.3 ULID Format Specification

Both `event_id` and `causation_id` use ULID (Universally Unique Lexicographically Sortable Identifier):

- Length: exactly 26 characters
- Encoding: Crockford Base32 (`0123456789ABCDEFGHJKMNPQRSTVWXYZ`)
- Structure: 10-char timestamp (48-bit millisecond epoch) + 16-char randomness (80-bit)
- Regex: `^[0-9A-HJKMNP-TV-Z]{26}$`
- ULIDs are sortable by creation time when compared lexicographically

### 2.4 UUID v4 Format

The `project_uuid` field uses UUID v4 (random):

- Format: `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx` where `y` is one of `[89ab]`
- Example: `"550e8400-e29b-41d4-a716-446655440000"`

---

## 3. Batch Request/Response Format

### 3.1 Batch Request

```
POST /api/v1/events/batch/
Authorization: Bearer <jwt_access_token>
Content-Type: application/json
Content-Encoding: gzip
```

**Body** (before gzip compression):
```json
{
  "events": [
    { ... event 1 ... },
    { ... event 2 ... }
  ]
}
```

| Parameter | Value |
|-----------|-------|
| URL | `POST {server_url}/api/v1/events/batch/` (trailing slash required) |
| Max batch size | 1000 events |
| Compression | Body is gzip-compressed (`Content-Encoding: gzip`) |
| Ordering | Events are drained from the offline queue in FIFO order: `timestamp ASC, id ASC` |
| Timeout | 60 seconds |

The CLI constructs the payload as follows (from `batch.py`):
```python
payload = json.dumps({"events": events}).encode("utf-8")
compressed = gzip.compress(payload)
```

### 3.2 Success Response (HTTP 200)

```json
{
  "results": [
    {"event_id": "01JMBY1234567890ABCDEFGH", "status": "success"},
    {"event_id": "01JMBY1234567890ABCDEFGI", "status": "duplicate"},
    {"event_id": "01JMBY1234567890ABCDEFGJ", "status": "rejected", "error": "Invalid payload: missing field 'wp_id'"}
  ]
}
```

**Per-event status values**:

| Status | Meaning | CLI Behavior |
|--------|---------|--------------|
| `success` | Event accepted and stored | Remove from offline queue |
| `duplicate` | Event with this `event_id` already exists | Remove from offline queue (treated as success) |
| `rejected` | Event failed server-side validation | Retain in queue, increment `retry_count` |

**Event journal extension (#2124/#2131)**: the CLI behavior above describes the
current destructive offline event queue. After
`event-sync-retention-delivery-01KVYWRG` lands, event payload rows MUST NOT be
deleted on `success` or `duplicate`; those outcomes update the delivery ledger
for the resolved target. This extension applies to event payload delivery only.
`body_upload_queue` / `body_upload_failure_log` remain separate non-event queue
surfaces and are not converted into event-journal rows by that mission.

> **Additive note (`event-sync-retention-delivery-01KVYWRG`, #2124/#2146 — strictly
> additive, NFR-006/C-006).** The **wire** protocol in this section is unchanged:
> the request body, the per-event `status` vocabulary (`success` / `duplicate` /
> `rejected`), and every fixture below stay exactly as specified. What changes is
> only the **local CLI behavior** for *event payload* rows while the (since-retired) local
> receiver drove delivery (the canonical source of this mapping was
> `src/specify_cli/delivery/receivers.py`, removed with the delivery subsystem on this line —
> spec-kitty#5 / PR #114; the table is retained as historical wire-contract documentation):
>
> | Per-event / batch outcome | Local event-row effect after this mission |
> |---|---|
> | `success` | Delivery **ledger UPDATE** for the resolved target (records delivered); the local event-journal row is **retained**, never deleted. |
> | `duplicate` | Same as `success` — ledger UPDATE, row retained (idempotent re-delivery, NFR-003). |
> | `rejected` | Ledger **rejection** state for the target; payload retained and inspectable; eligible for a later attempt. |
> | oversized / permanent per-event failure | Ledger **terminal-failed** state; excluded from future automatic selection but never deleted (FR-015). |
> | batch-level transient failure (401 / 403 / 408 / 429 / 5xx / timeout) | Updates **attempt metadata only** (no per-event content verdict); never poisons per-event retry counts. |
>
> Row deletion now happens only via explicit `sync gc` / `sync archive`, which
> preserve delivery history/provenance. This extension covers **event payload
> delivery only**. `body_upload_queue` and `body_upload_failure_log` remain owned by
> `sync/queue.py`, are **not** event-journal rows, and no status field in this
> contract may imply otherwise (event-sync-delivery contract §6).

**Per-event result fields**:

| Field | Type | Present When | Description |
|-------|------|-------------|-------------|
| `event_id` | string | Always | The ULID of the event this result refers to |
| `status` | string | Always | One of: `"success"`, `"duplicate"`, `"rejected"` |
| `error` | string | `status == "rejected"` | Human-readable validation failure reason |
| `error_message` | string | `status == "rejected"` | Alternative field name (CLI checks both `error_message` and `error`) |

Note: The CLI accepts both `error_message` and `error` fields for the rejection reason. The SaaS should provide at least one.

### 3.3 Validation Error Response (HTTP 400)

```json
{
  "error": "Batch processing failed",
  "details": "Transaction rolled back: 3 events failed schema validation"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error` | string | Yes | Top-level error message |
| `details` | string or list | Yes | Per-event failure reasons. Can be a JSON string containing a list, a JSON list directly, or a plain description string. |

**Structured `details` format** (preferred -- enables per-event error categorization):
```json
{
  "error": "Batch processing failed",
  "details": [
    {"event_id": "01JMBY...", "error": "Missing required field: wp_id"},
    {"event_id": "01JMBY...", "reason": "Invalid event_type: FooBar"}
  ]
}
```

The CLI parses `details` as follows:
1. If `details` is a list: treat each item as `{"event_id": ..., "error"|"reason": ...}`
2. If `details` is a JSON string encoding a list: parse and treat as above
3. If `details` is a plain string: apply the top-level `error` to all events in the batch

### 3.4 Authentication Error Response (HTTP 401)

```json
{
  "error": "Token expired or invalid"
}
```

CLI behavior: Prints "Batch sync failed: Authentication failed (401)", marks all events as rejected with `error_category: "auth_expired"`, and increments retry count.

### 3.5 Permission Error Response (HTTP 403)

```json
{
  "error": "Insufficient permissions for team 'my-team' on project 'my-project'"
}
```

### 3.6 Server Error Responses (HTTP 5xx)

Any non-200/400/401 status code is treated as a server error. All events are marked rejected with `error_category: "server_error"`.

---

## 4. Event Types and Payload Schemas

The retired CLI transport emitted 8 event types. Its `_PAYLOAD_RULES` implementation was deleted with `src/specify_cli/sync/emitter.py`; this section is retained as wire-contract history.

### 4.1 WPStatusChanged

Emitted when a work package changes lane (status).

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `WorkPackage` | `"WP01"` (the wp_id) |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `wp_id` | string | Yes | Pattern: `^WP\d{2}$` | `"WP01"` |
| `from_lane` | string | Yes | One of the 7 canonical lanes (see below) | `"planned"` |
| `to_lane` | string | Yes | One of the 7 canonical lanes (see below) | `"in_progress"` |
| `actor` | string | No | String if present (actor identity) | `"claude-agent"` |
| `feature_slug` | string | No | Nullable string | `"039-cli-2x-readiness"` |

**Canonical 7-lane vocabulary** (accepted values for `from_lane` and `to_lane`):
`planned`, `claimed`, `in_progress`, `for_review`, `done`, `blocked`, `canceled`

Lane values are passed through directly from the canonical status model — no collapse or mapping is applied.

### 4.2 WPCreated

Emitted when a new work package is created.

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `WorkPackage` | `"WP01"` (the wp_id) |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `wp_id` | string | Yes | Pattern: `^WP\d{2}$` | `"WP03"` |
| `title` | string | Yes | Min 1 char | `"Implement batch sync"` |
| `feature_slug` | string | Yes | Min 1 char | `"039-cli-2x-readiness"` |
| `dependencies` | list[string] | No | Each item matches `^WP\d{2}$` | `["WP01", "WP02"]` |

### 4.3 WPAssigned

Emitted when a work package is assigned to an agent.

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `WorkPackage` | `"WP01"` (the wp_id) |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `wp_id` | string | Yes | Pattern: `^WP\d{2}$` | `"WP07"` |
| `agent_id` | string | Yes | Min 1 char | `"wp07-agent"` |
| `phase` | string | Yes | One of: `"implementation"`, `"review"` | `"implementation"` |
| `retry_count` | integer | No | >= 0 | `0` |

### 4.4 FeatureCreated

Emitted when a new feature is created.

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `Feature` | `"039-cli-2x-readiness"` (feature_slug) |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `feature_slug` | string | Yes | Pattern: `^\d{3}-[a-z0-9-]+$` | `"039-cli-2x-readiness"` |
| `feature_number` | string | Yes | Pattern: `^\d{3}$` | `"039"` |
| `target_branch` | string | Yes | Min 1 char | `"main"` |
| `wp_count` | integer | Yes | >= 0 | `9` |
| `created_at` | string | No | ISO 8601 datetime string | `"2026-02-12T10:00:00+00:00"` |

### 4.5 FeatureCompleted

Emitted when all work packages in a feature reach terminal state.

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `Feature` | `"039-cli-2x-readiness"` (feature_slug) |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `feature_slug` | string | Yes | Min 1 char | `"039-cli-2x-readiness"` |
| `total_wps` | integer | Yes | >= 0 | `9` |
| `completed_at` | string | No | ISO 8601 datetime string | `"2026-02-12T18:00:00+00:00"` |
| `total_duration` | string | No | Nullable string | `"8h 30m"` |

### 4.6 HistoryAdded

Emitted when a history entry is added to a work package.

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `WorkPackage` | `"WP01"` (the wp_id) |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `wp_id` | string | Yes | Pattern: `^WP\d{2}$` | `"WP07"` |
| `entry_type` | string | Yes | One of: `"note"`, `"review"`, `"error"`, `"comment"` | `"note"` |
| `entry_content` | string | Yes | Min 1 char | `"Completed contract document"` |
| `author` | string | No | String if present | `"wp07-agent"` |

### 4.7 ErrorLogged

Emitted when an error is logged during workflow execution.

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `WorkPackage` (if `wp_id` present) or `Feature` | `"WP01"` or `"error"` |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `error_type` | string | Yes | One of: `"validation"`, `"runtime"`, `"network"`, `"auth"`, `"unknown"` | `"validation"` |
| `error_message` | string | Yes | Min 1 char | `"Missing required field: wp_id"` |
| `wp_id` | string | No | Nullable string | `"WP03"` |
| `stack_trace` | string | No | Nullable string | `"Traceback ..."` |
| `agent_id` | string | No | Nullable string | `"wp07-agent"` |

### 4.8 DependencyResolved

Emitted when a work package dependency is resolved.

| aggregate_type | aggregate_id format |
|----------------|---------------------|
| `WorkPackage` | `"WP04"` (the dependent wp_id) |

**Payload fields**:

| Field | Type | Required | Constraints | Example |
|-------|------|----------|-------------|---------|
| `wp_id` | string | Yes | Pattern: `^WP\d{2}$` | `"WP04"` |
| `dependency_wp_id` | string | Yes | Pattern: `^WP\d{2}$` | `"WP02"` |
| `resolution_type` | string | Yes | One of: `"completed"`, `"skipped"`, `"merged"` | `"completed"` |

---

## 5. Lane Vocabulary (Canonical 7-Lane)

The CLI emits `WPStatusChanged` events using the full canonical 7-lane vocabulary directly. No lane collapse or mapping is applied — `_SYNC_LANE_MAP` has been removed.

### 5.1 Canonical Lanes

| Lane | Description |
|------|-------------|
| `planned` | Work not yet started |
| `claimed` | Claimed by an agent but not yet in progress |
| `in_progress` | Active work underway |
| `for_review` | Submitted for review |
| `done` | Complete (terminal) |
| `blocked` | Blocked by dependency or issue |
| `canceled` | Canceled (terminal) |

All 7 values are valid for both `from_lane` and `to_lane` in `WPStatusChanged` payloads.

### 5.2 SaaS Acceptance Requirements

The SaaS batch endpoint MUST accept all 7 canonical lane values in `WPStatusChanged` payload fields `from_lane` and `to_lane`.

Unknown lane values MUST be rejected with a descriptive error.

### 5.3 Alias Resolution (CLI-Side Only)

The CLI resolves the user-facing alias `doing` to `in_progress` at input boundaries (e.g., `move-task --to doing`). This resolution happens before event emission — the alias `doing` never appears in emitted events.

---

## 6. Error Categorization

The retired CLI transport categorized batch errors using keyword matching. Its `src/specify_cli/sync/batch.py` implementation was deleted; these categories remain historical wire-contract documentation.

### 6.1 Categories

| Category | Keywords | CLI Action Suggestion |
|----------|----------|-----------------------|
| `schema_mismatch` | `invalid`, `schema`, `field`, `missing`, `type` | `Inspect the invalid event with --report <file.json>` |
| `auth_expired` | `token`, `expired`, `unauthorized`, `401` | `Run 'spec-kitty auth login' to refresh credentials` |
| `server_error` | `internal`, `500`, `timeout`, `unavailable` | `Retry later or check server status` |
| `unknown` | (no keywords match) | `Inspect the failure report for details: --report <file.json>` |

The CLI applies `categorize_error()` to the error string from each rejected event result or the top-level error message from HTTP 400 responses.

### 6.2 Failure Report Format

The CLI can generate a JSON failure report after batch sync:

```json
{
  "generated_at": "2026-02-12T10:00:00+00:00",
  "summary": {
    "total_events": 100,
    "synced": 90,
    "duplicates": 3,
    "failed": 7,
    "categories": {
      "schema_mismatch": 5,
      "auth_expired": 1,
      "unknown": 1
    }
  },
  "failures": [
    {
      "event_id": "01JMBY1234567890ABCDEFGH",
      "error": "Missing required field: wp_id",
      "category": "schema_mismatch"
    }
  ]
}
```

---

## 7. Fixture Data

The following fixtures are complete request/response examples. Each fixture can be used as-is for integration testing. The JSON is shown uncompressed for readability; in production the request body is gzip-compressed.

All fixture event data validates against the Pydantic `Event` model. See `tests/contract/test_handoff_fixtures.py` for the automated contract test.

### Fixture 1: Single WPStatusChanged (Happy Path)

**Request Body**:
```json
{
  "events": [
    {
      "event_id": "01JMBY7K8N3QRVX2DPFG5HWT4E",
      "event_type": "WPStatusChanged",
      "aggregate_id": "WP01",
      "aggregate_type": "WorkPackage",
      "payload": {
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "in_progress",
        "actor": "claude-agent",
        "feature_slug": "039-cli-2x-readiness"
      },
      "timestamp": "2026-02-12T10:00:00+00:00",
      "node_id": "a1b2c3d4e5f6",
      "lamport_clock": 1,
      "causation_id": null,
      "team_slug": "priivacy",
      "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "project_slug": "spec-kitty",
      "git_branch": "039-cli-2x-readiness-WP01",
      "head_commit_sha": "0cf3f906f4f979a000cf04c78688a397d69b6a37",
      "repo_slug": "priivacy/spec-kitty"
    }
  ]
}
```

**Expected Response (HTTP 200)**:
```json
{
  "results": [
    {
      "event_id": "01JMBY7K8N3QRVX2DPFG5HWT4E",
      "status": "success"
    }
  ]
}
```

**Key fields to verify**: `event_id` is 26-char ULID, `from_lane` and `to_lane` are canonical 7-lane values, `project_uuid` is valid UUID v4.

---

### Fixture 2: Mixed Batch (3 Event Types)

**Request Body**:
```json
{
  "events": [
    {
      "event_id": "01JMBYA1B2C3D4E5F6G7H8J9KA",
      "event_type": "WPStatusChanged",
      "aggregate_id": "WP02",
      "aggregate_type": "WorkPackage",
      "payload": {
        "wp_id": "WP02",
        "from_lane": "in_progress",
        "to_lane": "for_review",
        "actor": "wp02-agent",
        "feature_slug": "039-cli-2x-readiness"
      },
      "timestamp": "2026-02-12T11:00:00+00:00",
      "node_id": "a1b2c3d4e5f6",
      "lamport_clock": 10,
      "causation_id": null,
      "team_slug": "priivacy",
      "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "project_slug": "spec-kitty",
      "git_branch": "039-cli-2x-readiness-WP02",
      "head_commit_sha": "1af4b906f4f979a000cf04c78688a397d69b6a38",
      "repo_slug": "priivacy/spec-kitty"
    },
    {
      "event_id": "01JMBYA1B2C3D4E5F6G7H8J9KB",
      "event_type": "WPCreated",
      "aggregate_id": "WP10",
      "aggregate_type": "WorkPackage",
      "payload": {
        "wp_id": "WP10",
        "title": "End-to-end integration test suite",
        "feature_slug": "039-cli-2x-readiness",
        "dependencies": ["WP02", "WP03"]
      },
      "timestamp": "2026-02-12T11:01:00+00:00",
      "node_id": "a1b2c3d4e5f6",
      "lamport_clock": 11,
      "causation_id": null,
      "team_slug": "priivacy",
      "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "project_slug": "spec-kitty",
      "git_branch": "main",
      "head_commit_sha": "2bf5c917f5f989b111df15d89799b498e7ac7b49",
      "repo_slug": "priivacy/spec-kitty"
    },
    {
      "event_id": "01JMBYA1B2C3D4E5F6G7H8J9KC",
      "event_type": "FeatureCreated",
      "aggregate_id": "040-next-feature",
      "aggregate_type": "Feature",
      "payload": {
        "feature_slug": "040-next-feature",
        "feature_number": "040",
        "target_branch": "main",
        "wp_count": 5,
        "created_at": "2026-02-12T11:02:00+00:00"
      },
      "timestamp": "2026-02-12T11:02:00+00:00",
      "node_id": "a1b2c3d4e5f6",
      "lamport_clock": 12,
      "causation_id": null,
      "team_slug": "priivacy",
      "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "project_slug": "spec-kitty",
      "git_branch": "main",
      "head_commit_sha": "2bf5c917f5f989b111df15d89799b498e7ac7b49",
      "repo_slug": "priivacy/spec-kitty"
    }
  ]
}
```

**Expected Response (HTTP 200)**:
```json
{
  "results": [
    {"event_id": "01JMBYA1B2C3D4E5F6G7H8J9KA", "status": "success"},
    {"event_id": "01JMBYA1B2C3D4E5F6G7H8J9KB", "status": "success"},
    {"event_id": "01JMBYA1B2C3D4E5F6G7H8J9KC", "status": "success"}
  ]
}
```

**Key fields to verify**: Three different event types in one batch, `dependencies` is an array of WP IDs, `feature_number` matches the pattern `^\d{3}$`.

---

### Fixture 3: Duplicate Event

**Request Body** (same `event_id` as Fixture 1, sent a second time):
```json
{
  "events": [
    {
      "event_id": "01JMBY7K8N3QRVX2DPFG5HWT4E",
      "event_type": "WPStatusChanged",
      "aggregate_id": "WP01",
      "aggregate_type": "WorkPackage",
      "payload": {
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "in_progress",
        "actor": "claude-agent",
        "feature_slug": "039-cli-2x-readiness"
      },
      "timestamp": "2026-02-12T10:00:00+00:00",
      "node_id": "a1b2c3d4e5f6",
      "lamport_clock": 1,
      "causation_id": null,
      "team_slug": "priivacy",
      "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "project_slug": "spec-kitty",
      "git_branch": "039-cli-2x-readiness-WP01",
      "head_commit_sha": "0cf3f906f4f979a000cf04c78688a397d69b6a37",
      "repo_slug": "priivacy/spec-kitty"
    }
  ]
}
```

**Expected Response (HTTP 200)**:
```json
{
  "results": [
    {
      "event_id": "01JMBY7K8N3QRVX2DPFG5HWT4E",
      "status": "duplicate"
    }
  ]
}
```

**Key point**: The SaaS MUST detect the duplicate by `event_id` and return `"duplicate"` status (not an error). The CLI treats duplicates as successful -- the event is removed from the offline queue.

---

### Fixture 4: Rejected Event (Missing Required Field)

**Request Body** (missing `error_type` in ErrorLogged payload):
```json
{
  "events": [
    {
      "event_id": "01JMBYB3C4D5E6F7G8H9J0KABM",
      "event_type": "ErrorLogged",
      "aggregate_id": "error",
      "aggregate_type": "Feature",
      "payload": {
        "error_message": "Something went wrong"
      },
      "timestamp": "2026-02-12T12:00:00+00:00",
      "node_id": "a1b2c3d4e5f6",
      "lamport_clock": 20,
      "causation_id": null,
      "team_slug": "priivacy",
      "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "project_slug": "spec-kitty",
      "git_branch": "main",
      "head_commit_sha": null,
      "repo_slug": "priivacy/spec-kitty"
    }
  ]
}
```

**Expected Response (HTTP 200 with per-event rejection)**:
```json
{
  "results": [
    {
      "event_id": "01JMBYB3C4D5E6F7G8H9J0KABM",
      "status": "rejected",
      "error": "Invalid payload for ErrorLogged: missing required field 'error_type'"
    }
  ]
}
```

**Key point**: The SaaS should validate payloads per event type and return `"rejected"` with a descriptive `error` message. The error should contain keywords like `missing` or `field` so the CLI categorizes it as `schema_mismatch`.

---

### Fixture 5: HTTP 400 Error Response

**Request Body** (entire batch fails validation):
```json
{
  "events": [
    {
      "event_id": "01JMBYC4D5E6F7G8H9J0K1WABN",
      "event_type": "WPStatusChanged",
      "aggregate_id": "WP01",
      "aggregate_type": "WorkPackage",
      "payload": {
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "in_progress",
        "actor": "agent",
        "feature_slug": null
      },
      "timestamp": "2026-02-12T13:00:00+00:00",
      "node_id": "a1b2c3d4e5f6",
      "lamport_clock": 30,
      "causation_id": null,
      "team_slug": "priivacy",
      "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "project_slug": "spec-kitty",
      "git_branch": null,
      "head_commit_sha": null,
      "repo_slug": null
    }
  ]
}
```

**Expected Response (HTTP 400)**:
```json
{
  "error": "Batch validation failed",
  "details": [
    {
      "event_id": "01JMBYC4D5E6F7G8H9J0K1WABN",
      "error": "Invalid schema: project_uuid authorization check failed for team 'priivacy'"
    }
  ]
}
```

**Key point**: The `details` field MUST be present for HTTP 400 responses. The CLI depends on it for per-event diagnostics. When `details` is a structured list, the CLI can categorize each failure independently.

---

## 8. Tracker Snapshot Publish Payload (Feature 048)

**Historical.** The CLI no longer publishes tracker snapshots: `sync_publish` refuses for both SaaS-backed and local tracker providers (`src/specify_cli/tracker/saas_service.py`, `src/specify_cli/tracker/local_service.py`, #3168), so this repository produces no snapshot payload for the SaaS to validate. The endpoint contract is owned upstream (`spec-kitty/saas`). The payload the CLI used to send, with its routing fields, null semantics and idempotency key, is recorded in [tracker-snapshot-publish.md](../../kitty-specs/048-tracker-publish-resource-routing/contracts/tracker-snapshot-publish.md).

---

## Appendix A: Full Event Lifecycle

```
1. CLI action triggers event emission (e.g., `spec-kitty agent tasks move-task WP01 --to doing`)
2. EventEmitter._emit() builds event dict with all envelope + extended fields
3. EventEmitter._validate_event() validates:
   a. Pydantic Event model (core envelope fields)
   b. aggregate_type is valid
   c. event_type is one of 8 known types
   d. ULID patterns for event_id and causation_id
   e. Payload fields match per-event-type rules
4. If project_uuid is missing: queue locally only (no batch send)
5. If authenticated + WebSocket connected: send via WebSocket
6. Otherwise: queue to SQLite offline queue (~/.spec-kitty/queue.db)
7. On the retired background flush:
   a. drain_queue(limit=1000) retrieves events FIFO
   b. Gzip compress and POST to /api/v1/events/batch/
   c. Parse per-event results
   d. Remove success/duplicate events from queue
   e. Increment retry_count for rejected events
```

## Appendix B: Source File Reference

| Component | File / source |
|-----------|---------------|
| Pydantic Event model | External `spec-kitty-events` dependency, pinned at `c93dbfbf5243330349452a31d05bca2ece26ceea` (`pyproject.toml`) |
| Retired sync transport | Deleted with issue #5; this appendix is historical only |
| SaaS fan-out (canonical 7-lane) | `src/specify_cli/status/emit.py` (`_saas_fan_out`) |
| Retired public event API | Deleted with issue #5 |
