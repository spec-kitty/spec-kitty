---
title: Trail Model
description: 'Operator reference for the Phase 4 trail model: how every standalone spec-kitty dispatch writes an auditable JSONL trail for accountability, SaaS coherence, and provenance.'
doc_status: active
updated: '2026-06-15'
type: explanation
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/host-surface-parity.md
---
# Trail Model

*Operator reference for the Phase 4 runtime consumption baseline.*

## Overview

Every standalone Spec Kitty dispatch leaves an auditable trail. The trail serves three purposes:

1. **Local accountability**: operators can reconstruct what happened on any checkout without SaaS connectivity.
2. **SaaS coherence**: the dashboard timeline shows the same history as the local audit log.
3. **Governance provenance**: downstream retrospective and doctrine work can reference specific invocations.

## minimal viable trail

**One JSONL file per invocation, written locally before the executor returns.**

Every `spec-kitty dispatch "<request>"` call writes a `started` event to:

```
kitty-ops/{invocation_id}.jsonl
```

When `spec-kitty profile-invocation complete` is called, a `completed` event is appended to the same file.

This is the unconditional minimum — it is always written, regardless of SaaS connectivity, charter state, or sync configuration. The data model is defined in `src/specify_cli/invocation/record.py`.

Mission-scoped dispatchers may also record `mission_id`, `wp_id`, and the
catalog-winning `model_id` on the `started` event. An implement or review claim
that supplies `--invocation-id` treats those values as a provenance assertion:
the requested ULID and the record's embedded ID, mission, WP, action, profile,
and model must agree exactly. Uncorrelated legacy records remain readable, but
cannot prove a resolved model actual for a claim.

## Mode-of-Work Taxonomy

Every invocation belongs to one of four work modes. The mode determines which optional trail tiers are eligible — it does not override the mandatory Tier 1 rule.

| Mode | Description | Example actions | Tier 2 eligible | Tier 3 eligible |
|------|-------------|-----------------|-----------------|-----------------|
| `task_execution` | Standalone governed work, including advice, review, code changes, and test runs | `dispatch` | Yes (caller-triggered) | No |
| `mission_step` | One step in a governed mission workflow | `specify`, `plan`, `tasks`, `merge`, `accept` | Yes (caller-triggered) | Yes |
| `query` | Read-only, no execution | `profiles list`, `invocations list` | No | No |

Mode-of-work is recorded on the `started` event as the `mode_of_work` field. New standalone dispatch records use `task_execution`. Runtime enforcement is active: `profile-invocation complete --evidence` is rejected for records that are not evidence-eligible (see "Mode Enforcement at Tier 2 Promotion" below).

### Mode Enforcement at Tier 2 Promotion

`spec-kitty profile-invocation complete --evidence <path>` is rejected with `InvalidModeForEvidenceError` when the target invocation is not evidence-eligible. The enforcement runs **before** any write, so the invocation remains open and uncommitted — rerun `complete` without `--evidence` to close cleanly.

Pre-mission records (invocations opened before this enforcement landed) have no `mode_of_work` field and are accepted by enforcement — legacy behaviour is preserved. See ADR-002-mode-derivation.md for the full derivation table and rationale.

## Trail Tiers

### Tier 1 — Every Invocation (mandatory)

Written unconditionally before the executor returns.

- **Storage**: `kitty-ops/{invocation_id}.jsonl`
- **Content**: Two JSONL lines — a `started` event and (after completion) a `completed` event.
- **When**: All standalone `dispatch` invocations.

### Glossary Check Event (conditional, Tier 1)

When the invocation executor's glossary chokepoint scan detects at least one
conflict — or encounters an error — it appends a `glossary_checked` event to the
same Tier 1 JSONL file, immediately after the `started` event.

**Written ONLY when:**
- `all_conflicts` is non-empty (one or more semantic conflicts detected), OR
- `error_msg` is non-null (the chokepoint scan encountered an unexpected exception).

**Clean invocations produce NO `glossary_checked` line.** This keeps Tier 1
files minimal when there are no glossary issues to report.

Example `glossary_checked` event line:

```json
{"event": "glossary_checked", "invocation_id": "01HXYZ...", "matched_urns": ["glossary:d93244e7"], "high_severity": [{"term": "lane", "conflict_type": "ambiguous_scope", "severity": "HIGH", "candidate_senses": ["execution lane (WP routing)", "git branch lane (worktree)"]}], "all_conflicts": [...], "tokens_checked": 8, "duration_ms": 2.7, "error_msg": null}
```

Readers that encounter `"event": "glossary_checked"` and do not recognise this
event type may safely skip the line — it is additive metadata and never affects
the `started`/`completed` pair.

### Correlation Links (Tier 1 extension)

`spec-kitty profile-invocation complete` accepts two additional flags that append correlation events to the invocation JSONL:

- `--artifact <path>` — repeatable. Each value appends one `{event: "artifact_link", invocation_id, kind, ref, at}` line to `kitty-ops/<id>.jsonl`. Refs are stored repo-relative when the resolved path is under the checkout, absolute otherwise.
- `--commit <sha>` — singular. Appends one `{event: "commit_link", invocation_id, sha, at}` line.

Both events are append-only (never mutate existing lines) and readable by a single-file scan. Readers that do not recognise these event types may safely skip the line — the same additive-reader invariant that protects `glossary_checked`.

**SaaS projection status (3.2.x)**: Correlation events are **local-only** in the 3.2.x line. The projection policy (`POLICY_TABLE` in `src/specify_cli/invocation/projection_policy.py`) assigns `project=True` for `task_execution` / `mission_step` correlation events, but the dict-record submission path in `_propagate_one` is not yet wired. SaaS projection of correlation events will land in a future release consistent with the ADR-004 local-only stance for Tier 2 content.

See ADR-001-correlation-contract.md for the design; contracts/profile-invocation-complete.md for the CLI shape.

### Tier 2 — Evidence Artifact (optional, caller-triggered)

Created when the caller explicitly flags that the invocation produced checkable output.

- **Trigger**: Caller sets `--evidence <path>` on `spec-kitty profile-invocation complete`.
- **Storage**: `.kittify/evidence/{invocation_id}/evidence.md` and `.kittify/evidence/{invocation_id}/record.json`
- **When**: `task_execution` and `mission_step` modes only.

### Tier 3 — Durable Project State (optional, action-driven)

Promotion to `kitty-specs/` or doctrine artifacts only when the invocation changes project-domain state.

- **Trigger**: Action is in `TIER_3_ACTIONS` — `{specify, plan, tasks, merge, accept}`.
- **Storage**: `kitty-specs/{mission_slug}/` — existing spec/plan/tasks/status files.
- **When**: `mission_step` mode only.

### Promotion Rules

```
Tier 1 always written
  |
  +-- If caller sets evidence_ref --> Tier 2 artifact created
  |
  +-- If action in TIER_3_ACTIONS --> Tier 3 artifacts produced by workflow
```

## Doctor-Sweep Closures and the Archive Freeze (#4397)

`kitty-ops/` is one of the four immutable archive roots under the
historical-preservation gate (`tests/architectural/test_archive_root_byte_identical.py`):
a **pre-existing** `kitty-ops/<invocation_id>.jsonl` file may never be modified
— not on disk, not in the index, committed or not. An agent close appends its
`completed` event to the per-record file and that is legal only because the
record was minted in the same session (new archive history, `A` status). The
`spec-kitty doctor ops --close-stale` sweep closes Ops that are, by definition,
already committed — so recording the closure by mutating the per-record file
(and auto-committing it) reds the preservation gate.

The resolved design (#4397, option "record closure on the append-only spine"):

- **Per-record `kitty-ops/<id>.jsonl` files are byte-frozen once committed.**
  The sweep never touches them.
- **Sweep closures are recorded on a dedicated append-only spine,
  `kitty-ops/op-closures.jsonl`** — one v2 `OpCompletedEvent` JSON line per
  closure (same frozen model as the per-record `completed` event, carrying
  `outcome="abandoned"`, `closed_by="doctor_sweep"`). The preservation gate
  admits this one path the same way it admits `kitty-ops/lifecycle.jsonl`:
  a modification is legal only as a byte-prefix-preserving append whose new
  rows parse as valid v2 completed events.
- **The close still goes through the canonical executor path**
  (`ProfileInvocationExecutor.complete_invocation`, research R4): the spine
  append *is* that path's write for a `closed_by="doctor_sweep"` close, the
  event is still submitted to the SaaS propagator, and the idempotent
  already-closed guard now checks both the per-record file (concurrent manual
  close) and the spine (concurrent sweep).
- **Open-Op detection reads both surfaces**: an Op is closed when its
  per-record file carries a `completed` event OR the spine carries a closure
  for its invocation id (`list_orphan_ops`).
- **The sweep auto-commits only the spine** (`op(<profile>): <action>
  [<id8>] (doctor sweep)`). A refused commit (e.g. the protected-branch guard
  on `main`) is reported per-entry in the sweep output and plainly stated in
  the command's output — an uncommitted closure will not survive a checkout
  or reset; a committed one is visible only on branches that carry the commit.
  The same visibility applies to the agent close path: a refused per-record
  auto-commit is printed as an actionable warning (`executor.last_op_commit`)
  instead of dying in a `logger.warning`.

Rejected alternatives: letting the sweep mutate per-record files without
committing (still reds the gate, which compares the working tree against the
merge-base — and leaves closures non-durable), and narrowing the archive roots
themselves (weakens the preservation guarantee far beyond this surface).

## SaaS Read-Model Policy

Projection is conditional on `CheckoutSyncRouting.effective_sync_enabled`. When sync is disabled for a checkout, no events are emitted — even if the user is authenticated. When sync is enabled and the user is authenticated, Spec Kitty consults `src/specify_cli/invocation/projection_policy.py::POLICY_TABLE` to decide per `(mode_of_work, event)` what to project.

| mode_of_work | event | project | include_request_text | include_evidence_ref |
|--------------|-------|---------|----------------------|----------------------|
| task_execution | started | yes | yes | no |
| task_execution | completed | yes | yes | yes |
| task_execution | artifact_link | yes | no | no |
| task_execution | commit_link | yes | no | no |
| mission_step | started | yes | yes | no |
| mission_step | completed | yes | yes | yes |
| mission_step | artifact_link | yes | no | no |
| mission_step | commit_link | yes | no | no |
| query | any | no | — | — |

Pre-mission records (no `mode_of_work`) project under the `task_execution` rules — the legacy 3.2.0a5 behaviour is preserved for them.

Policy is additive and resolvable from code/config alone. See ADR-003-projection-policy.md for the rationale.

Projection is additive. Events accumulate; there is no deletion, replay-based overwrite, or idempotency-key gating in 3.2.

## Tier 2 SaaS Projection — Deferred

**Status**: Tier 2 evidence artifacts (`.kittify/evidence/<invocation_id>/evidence.md` and `record.json`) are **local-only** in the 3.2.x release line. They are not uploaded to SaaS. This decision was finalised by the Phase 4 closeout mission (ADR-004-tier2-saas-deferral.md).

**Reasoning**:
1. The shipped 3.2.0a5 baseline already behaves this way; operators observing the product today see local-only evidence.
2. SaaS projection of evidence bodies requires privacy, redaction, and size-limit design that lies outside the Phase 4 closeout scope.
3. Future projection remains possible without contract change — a later epic can read the existing local artifact and emit its own envelope.

**Revisit trigger**: any of (a) a named future epic accepts SaaS evidence projection as scope, (b) operators actively request the feature with a concrete use case, (c) a regulatory or audit requirement mandates centralised retention.

## Retention and Redaction

| Field | Treatment |
|-------|-----------|
| `request_text` | Retained as-written in local JSONL. No automatic redaction in 3.2. |
| `governance_context_hash` | First 16 hex chars of SHA-256 only. Full governance context is never persisted. |
| JSONL files | Persist indefinitely unless the operator purges `kitty-ops/`. |
| SaaS propagation | Additive. No delete-on-disable in 3.2. |

Propagation failures are written to `kitty-ops/propagation-errors.jsonl` and never affect the CLI exit code.

## `spec-kitty intake` — Not a Profile Invocation

`spec-kitty intake` ingests a plan document into `.kittify/mission-brief.md` for use by `/spec-kitty.specify` brief-intake mode. It is **not** a standalone Op and produces no `InvocationRecord`. The governed trail begins when the host calls `spec-kitty dispatch "<request>"` — not when the user stages a brief.

## Host surfaces that teach the trail

The standalone dispatch surface is taught to host LLMs through per-host skill packs. See [`docs/host-surface-parity.md`](host-surface-parity.md) for the authoritative matrix of supported hosts and each host's parity status.

## `spec-kitty explain` — Deferred to Phase 5

`spec-kitty explain` (issue #534) is not part of this release. It requires Phase 5 DRG glossary addressability to produce fully-cited answers. A partial implementation without glossary citations would be misleading.
