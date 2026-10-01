---
title: 'Comprehensive Manual Test Plan'
description: 'Full-ecosystem manual verification plan for Spec Kitty Beta/GA readiness: SaaS staging, CLI, tracker connectors, and webhook integrations across all repositories.'
doc_status: active
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-08-10'
related:
- docs/operations/index.md
---
# Spec Kitty: Comprehensive Manual Test Plan

**Date**: 2026-03-01
**Scope**: Full ecosystem verification across all repositories
**Goal**: Validate Beta/GA readiness for the Spec Kitty SaaS platform

---

## Prerequisites

### Accounts Required

- [ ] Spec Kitty SaaS staging account (https://team.spec-kitty.ai)
- [ ] Jira Cloud test project with API token
- [ ] Linear test workspace with API key
- [ ] GitHub test repository with configured webhook
- [ ] GitLab test project with configured webhook
- [ ] Slack test workspace with bot token and app installed
- [ ] Polar merchant account (staging/sandbox)
- [ ] Stripe test account (existing, for comparison)
- [ ] Nango account (nango.dev) with staging environment and connector configs

### Local Environment

- [ ] Python 3.11+ with `spec-kitty-cli` v2.0.2 installed (`pip install spec-kitty-cli`)
- [ ] Git configured with SSH access to Priivacy-ai org
- [ ] `SPEC_KITTY_ENABLE_SAAS_SYNC=1` environment variable set
- [ ] `spec-kitty auth login` completed successfully
- [ ] Local test repository initialized with `spec-kitty init`
- [ ] Browser with DevTools available (Chrome/Firefox)
- [ ] Slack desktop or web client open

### Staging Infrastructure

- [ ] spec-kitty-saas deployed to Fly.io staging
- [ ] PostgreSQL database accessible
- [ ] Redis instance running (for Channels + Celery)
- [ ] Celery workers running
- [ ] Nango SaaS staging environment accessible (nango.dev)
- [ ] Mailgun sandbox domain configured

---

## Section 1: CLI Core Functionality

### 1.1 Installation and Version

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 1.1.1 | Run `spec-kitty --version` | Displays `2.0.2` or later | | |
| 1.1.2 | Run `spec-kitty doctor skills` (a bare `spec-kitty doctor` runs no diagnostic and exits 2 by design) | Skills/command-surface diagnostic passes, no critical errors | | |
| 1.1.3 | Run `spec-kitty auth status` | Shows authenticated user, team slug, server URL | | |

### 1.2 Mission Lifecycle (software-dev)

Create a fresh test feature and run through the full lifecycle:

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 1.2.1 | Run `spec-kitty specify` with a short feature description | Creates `kitty-specs/<NNN>-<slug>/spec.md` with user stories and acceptance criteria | | |
| 1.2.2 | Verify `meta.json` created | Contains `mission: "software-dev"`, feature slug, creation date | | |
| 1.2.3 | Run `spec-kitty plan` | Creates `plan.md` with architecture decisions, tech stack, data model | | |
| 1.2.4 | Run `spec-kitty tasks` (outline + packages + finalize) | Creates `tasks.md` and `tasks/WP*.md` files with frontmatter | | |
| 1.2.5 | Verify dependency frontmatter | Each WP has `dependencies: []` field, no cycles detected | | |
| 1.2.6 | Run `spec-kitty implement WP01` | Creates or reuses `.worktrees/<slug>-lane-a/`, switches to the lane branch | | |
| 1.2.7 | Make a code change and commit in the worktree | Commit succeeds, WP status moves to `in_progress` | | |
| 1.2.8 | Run `spec-kitty agent tasks move-task WP01 --to for_review` | WP status commits to main, status.events.jsonl updated | | |
| 1.2.9 | Run `spec-kitty review` on WP01 | Review workflow starts, can approve or request changes | | |
| 1.2.10 | Move WP01 to `done` | Status event appended, `status.json` materialized | | |

### 1.3 Status Model

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 1.3.1 | Run `spec-kitty agent tasks status` | Kanban board renders with correct lanes and WP counts | | |
| 1.3.2 | Verify `status.events.jsonl` | Events are append-only, sorted keys, valid JSON per line | | |
| 1.3.3 | Verify `status.json` | Snapshot matches event log (deterministic reducer) | | |
| 1.3.4 | Test transition guards: try `planned` → `done` directly | Rejected (must go through intermediate lanes) | | |
| 1.3.5 | Test `doing` alias | Resolves to `in_progress`, alias never persisted in events | | |
| 1.3.6 | Test `force` flag on terminal lane exit | `done` → `in_progress` only works with `--force` | | |

### 1.4 Local Status View

The bundled local web dashboard has been removed; local status is read from the CLI.

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 1.4.1 | Run `spec-kitty agent tasks status --mission <slug>` | Lane board printed with WPs in correct lanes and correct status counts | | |
| 1.4.2 | Run `spec-kitty agent tasks status --mission <slug> --json` | Valid JSON with the same lane assignments | | |
| 1.4.3 | Run `spec-kitty orchestrator-api mission-state --mission <slug>` | Mission state and WP lanes match the status board | | |
| 1.4.4 | Save the `--json` output | Kept for parity comparison with SaaS (Section 8) | | |

### 1.5 Merge System (Feature 017)

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 1.5.1 | Run `spec-kitty merge --dry-run` on a multi-WP mission | Conflict forecast shows predicted conflicts, auto-resolvable flags | | |
| 1.5.2 | Run `spec-kitty merge --mission <slug>` | Preflight validates the lane manifest, lane worktrees are clean, and target branch exists | | |
| 1.5.3 | Run `spec-kitty merge --dry-run --json` | JSON shows mission branch, target branch, and computed lanes | | |
| 1.5.4 | Complete a full merge | Lane branches merge into the mission branch, then the mission branch merges into target, and lane worktrees are cleaned up | | |
| 1.5.5 | Verify status file auto-resolution | `status.events.jsonl` merge conflicts auto-resolved (append-both) | | |

---

## Section 2: Authentication and Sync

### 2.1 CLI Authentication

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 2.1.1 | Run `spec-kitty auth login` with valid credentials | Tokens stored in `~/.spec-kitty/credentials`, success message | | |
| 2.1.2 | Run `spec-kitty auth login` with invalid credentials | Clear error message, no tokens stored | | |
| 2.1.3 | Run `spec-kitty auth status` | Shows username, team slug, server URL, token expiry | | |
| 2.1.4 | Run `spec-kitty auth logout` | Credentials removed, confirmation displayed | | |
| 2.1.5 | Attempt sync operation while logged out | Prompts to log in first | | |
| 2.1.6 | Wait for access token expiry (or simulate) | Auto-refresh happens silently, next operation succeeds | | |

### 2.2 Event Sync (CLI → SaaS)

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 2.2.1 | Create a feature while authenticated | `FeatureCreated` event emitted, visible in SaaS within 5 seconds | | |
| 2.2.2 | Move a WP to `in_progress` | `WPStatusChanged` event synced, SaaS dashboard updates | | |
| 2.2.3 | Move a WP to `for_review` | Event synced, SaaS shows WP in review lane | | |
| 2.2.4 | Move a WP to `done` | Event synced with evidence, SaaS shows WP complete | | |
| 2.2.5 | Disconnect network, make status changes | Events queued in `~/.spec-kitty/queue.jsonl` | | |
| 2.2.6 | Reconnect network | Queued events batch-synced, SaaS catches up | | |
| 2.2.7 | Verify Lamport clock ordering | Events arrive with monotonically increasing clock values | | |
| 2.2.8 | Verify event envelope fields | Each event has: event_id (ULID), event_type, timestamp, project_uuid, project_slug, team_slug, node_id, lamport_clock, payload | | |

### 2.3 WebSocket Connection

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 2.3.1 | Observe WebSocket connection on login | Connection established, ping/pong heartbeat active | | |
| 2.3.2 | Kill server temporarily | Client enters RECONNECTING state with exponential backoff | | |
| 2.3.3 | Restart server | Client reconnects automatically, resumes sync | | |
| 2.3.4 | Verify background sync interval | Queue flushes every 5 minutes (configurable) | | |

---

## Section 3: SaaS Dashboard

### 3.1 Account and Team Management

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 3.1.1 | Sign up with email | Email confirmation sent, account created | | |
| 3.1.2 | Verify email | Account activated, redirected to dashboard | | |
| 3.1.3 | Sign in with Google OAuth | Successful authentication, team auto-created | | |
| 3.1.4 | Sign in with GitHub OAuth | Successful authentication, team auto-created | | |
| 3.1.5 | Create a team | Team created with slug, user is admin | | |
| 3.1.6 | Invite a team member | Invitation email sent with accept link | | |
| 3.1.7 | Accept invitation (as invitee) | Invitee joins team with member role | | |
| 3.1.8 | Verify team isolation | Members only see their team's projects/features | | |
| 3.1.9 | Toggle team feature flag (via Waffle) | Feature appears/disappears for team members | | |

### 3.2 Project and Feature Views

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 3.2.1 | View project list | All synced projects visible with slug and UUID | | |
| 3.2.2 | Click into a project | Features listed with status summary counts | | |
| 3.2.3 | Click into a feature | Kanban board with WPs in correct lanes | | |
| 3.2.4 | Click into a WP | WP detail page with status history, artifact links | | |
| 3.2.5 | Verify real-time updates | When CLI changes WP status, SaaS board updates without page refresh | | |

### 3.3 Collaboration Panel

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 3.3.1 | Open collaboration panel for a feature | Panel renders with session info, participant list | | |
| 3.3.2 | Verify participant presence | Active users shown with heartbeat indicator | | |
| 3.3.3 | View collaboration timeline | Events listed chronologically with actor attribution | | |
| 3.3.4 | Post a comment | Comment appears in timeline, visible to other participants | | |
| 3.3.5 | View concurrent driver warnings | If two agents work same WP, warning displays | | |
| 3.3.6 | Verify empty states | Empty panel shows helpful guidance, not blank | | |

### 3.4 Decision Inbox

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 3.4.1 | Navigate to decision inbox | List of pending decisions visible | | |
| 3.4.2 | View decision detail | Shows question, context, authority scope, alternatives | | |
| 3.4.3 | Answer a decision | Decision captured with actor, timestamp, rationale | | |
| 3.4.4 | View decision audit trail | Full history: who asked, who answered, when, what alternatives | | |
| 3.4.5 | Verify decision-point timeline | Decision lifecycle events visible in collaboration timeline | | |

### 3.5 Dossier (Mission Artifacts)

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 3.5.1 | View dossier for a feature | Artifact index with file names, types, content hashes | | |
| 3.5.2 | Click into an artifact | Content rendered (markdown → HTML) | | |
| 3.5.3 | Verify artifact status tracking | Active, superseded, missing states shown correctly | | |
| 3.5.4 | Verify dossier snapshot | Parity summary matches local artifacts | | |

### 3.6 Glossary Dashboard

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 3.6.1 | View glossary projection | Semantic health status (healthy/warning/blocked) | | |
| 3.6.2 | View conflict list | Active conflicts with severity (high/medium/low) | | |
| 3.6.3 | View top ambiguous terms | Most-conflicted terms listed | | |
| 3.6.4 | View recent clarifications | Resolved conflicts with resolution history | | |

---

## Section 4: Connector Flows (E2E)

### 4.1 Jira Integration

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 4.1.1 | Connect Jira via OAuth in SaaS | ConnectorBinding created, status: connected, health: healthy | | |
| 4.1.2 | View Jira connector health in dashboard | Health status visible, last sync time shown | | |
| 4.1.3 | Create a Jira issue in test project | Issue exists in Jira with title and description | | |
| 4.1.4 | Ingest Jira issue into spec-kitty mission | Issue payload normalized to canonical mission-input schema | | |
| 4.1.5 | Start `spec-kitty specify` from ingested issue | Specification pre-populated from Jira issue content | | |
| 4.1.6 | Move WP to `in_progress` in spec-kitty | Jira issue transitions to corresponding status | | |
| 4.1.7 | Move WP to `for_review` in spec-kitty | Jira issue transitions, comment added with spec-kitty link | | |
| 4.1.8 | Move WP to `done` in spec-kitty | Jira issue resolved/closed, final comment with summary | | |
| 4.1.9 | Verify bidirectional: change status in Jira | Spec-kitty reflects the Jira status change | | |
| 4.1.10 | Verify idempotency: replay same webhook | No duplicate events, no status regression | | |
| 4.1.11 | Verify error handling: revoke Jira token | Connector health degrades to `degraded`, ops log records failure | | |
| 4.1.12 | Rotate credentials via Nango | Token refreshed, connector returns to `healthy` | | |
| 4.1.13 | Disconnect Jira in SaaS | Binding revoked, audit event emitted | | |

### 4.2 Linear Integration

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 4.2.1 | Connect Linear via OAuth in SaaS | ConnectorBinding created, healthy | | |
| 4.2.2 | View Linear connector health | Health visible in dashboard | | |
| 4.2.3 | Create a Linear issue | Issue exists in Linear | | |
| 4.2.4 | Ingest Linear issue into spec-kitty | Canonical mission-input created | | |
| 4.2.5 | Start mission from Linear issue | Specification pre-populated | | |
| 4.2.6 | Move WP through lifecycle in spec-kitty | Linear issue status updates at each transition | | |
| 4.2.7 | Verify bidirectional: change status in Linear | Spec-kitty reflects change | | |
| 4.2.8 | Verify idempotency on duplicate webhook | No duplicates | | |
| 4.2.9 | Verify error → recovery cycle | Degrade → fix → healthy | | |
| 4.2.10 | Disconnect Linear | Binding revoked, audit emitted | | |

### 4.3 GitHub Issues Integration

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 4.3.1 | Connect GitHub via OAuth | ConnectorBinding created, webhook registered | | |
| 4.3.2 | View GitHub connector health | Health visible, webhook active | | |
| 4.3.3 | Create a GitHub issue in test repo | Issue exists on GitHub | | |
| 4.3.4 | Ingest GitHub issue into spec-kitty | Canonical mission-input created | | |
| 4.3.5 | Start mission from GitHub issue | Specification pre-populated | | |
| 4.3.6 | Move WP through lifecycle | GitHub issue labels/status update | | |
| 4.3.7 | Verify bidirectional: close issue on GitHub | Spec-kitty reflects closure | | |
| 4.3.8 | Verify webhook signature validation | Invalid signature rejected with 403 | | |
| 4.3.9 | Verify webhook deduplication | Same delivery ID processed once | | |
| 4.3.10 | Disconnect GitHub | Webhook removed, binding revoked | | |

### 4.4 GitLab Issues Integration

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 4.4.1 | Connect GitLab via OAuth | ConnectorBinding created, webhook registered | | |
| 4.4.2 | Create GitLab issue and ingest | Canonical mission-input created | | |
| 4.4.3 | Start mission from GitLab issue | Specification pre-populated | | |
| 4.4.4 | Move WP through lifecycle | GitLab issue status updates bidirectionally | | |
| 4.4.5 | Verify webhook signature validation | Invalid token rejected | | |
| 4.4.6 | Disconnect GitLab | Webhook removed, binding revoked | | |

### 4.5 Slack Integration

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 4.5.1 | Connect Slack via OAuth in SaaS | Bot token stored, binding created | | |
| 4.5.2 | View Slack connector health | Health visible in dashboard | | |
| 4.5.3 | Verify bot appears in Slack workspace | Bot user visible, can be invited to channels | | |
| 4.5.4 | Trigger a stand-up notification (see Section 5) | Message posted to designated channel | | |
| 4.5.5 | Verify Slack → SaaS message relay | Responses in Slack thread captured as decision events | | |
| 4.5.6 | Disconnect Slack | Bot revoked, binding cleaned up | | |

### 4.6 Connector Operations and Telemetry

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 4.6.1 | Check tracker health rollup API | Returns aggregated health across all connectors | | |
| 4.6.2 | Verify ingress ops logs | Inbound webhook events logged with timestamps, connector ID | | |
| 4.6.3 | Verify egress ops logs | Outbound status sync calls logged with response codes | | |
| 4.6.4 | Trigger a connector failure | Dead-letter telemetry records the failed event | | |
| 4.6.5 | Verify dead-letter replay | Failed event can be retried from ops view | | |
| 4.6.6 | Verify rate limiting | Webhook ingestion respects 300/min limit | | |

---

## Section 5: Spontaneous Stand-ups

### 5.1 Stand-up Trigger (LLM-Initiated)

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 5.1.1 | During a mission step, LLM reaches a decision point above significance threshold | Stand-up triggered automatically | | |
| 5.1.2 | Verify RACI inference | Correct participants selected (responsible, accountable, consulted, informed) | | |
| 5.1.3 | Verify significance threshold | Low-significance decisions handled by LLM alone, not escalated | | |
| 5.1.4 | Verify Slack notification sent | Stand-up thread created in designated Slack channel | | |
| 5.1.5 | Verify SaaS decision inbox updated | Pending decision appears in inbox | | |

### 5.2 Stand-up Trigger (Human-Initiated)

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 5.2.1 | Human creates a stand-up from SaaS decision inbox | Stand-up session created with question context | | |
| 5.2.2 | Slack notification sent to RACI participants | Thread created with question, authority scope, response actions | | |
| 5.2.3 | Verify participant list includes both humans and LLMs | Both types listed per RACI chart | | |

### 5.3 Stand-up Discussion and Resolution

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 5.3.1 | Human responds in Slack thread | Response captured as collaboration event | | |
| 5.3.2 | Multiple participants discuss | All messages captured in timeline | | |
| 5.3.3 | Mission owner makes final decision | Decision captured with: actor, timestamp, rationale, alternatives considered | | |
| 5.3.4 | Verify decision feeds back to workflow | Original LLM/mission step receives the decision and continues | | |
| 5.3.5 | Verify audit trail | Full stand-up history: trigger, participants, messages, decision, outcome | | |

### 5.4 Stand-up Edge Cases

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 5.4.1 | Stand-up with no responses within timeout | Timeout escalation triggers (per runtime timeout policy) | | |
| 5.4.2 | Mission owner unavailable | Escalation path per RACI (accountable takes over) | | |
| 5.4.3 | Duplicate stand-up for same decision | Deduplication prevents duplicate threads | | |
| 5.4.4 | Stand-up while Slack disconnected | Graceful degradation, decision falls back to SaaS inbox only | | |

---

## Section 6: Payments and Billing (Polar)

### 6.1 Subscription Lifecycle

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 6.1.1 | Visit pricing page | Plans displayed with pricing, features, and CTA | | |
| 6.1.2 | Start checkout for a paid plan | Redirected to Polar checkout | | |
| 6.1.3 | Complete payment in Polar sandbox | Webhook received, subscription state: `active` | | |
| 6.1.4 | Verify team entitlements update | Paid features unlocked for team | | |
| 6.1.5 | Add a team member (per-seat billing) | Quantity incremented, Polar notified | | |
| 6.1.6 | Remove a team member | Quantity decremented | | |
| 6.1.7 | Simulate payment failure | Subscription state: `delinquent`, grace period starts | | |
| 6.1.8 | Resolve payment failure | Subscription returns to `active` | | |
| 6.1.9 | Cancel subscription | State: `canceled`, access reverts at period end | | |
| 6.1.10 | Verify audit events | Billing lifecycle events logged with timestamps | | |

### 6.2 Polar Webhook Handling

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 6.2.1 | Simulate `checkout.completed` webhook | Subscription created, team mapped | | |
| 6.2.2 | Simulate `subscription.updated` webhook | Subscription state updated | | |
| 6.2.3 | Simulate `subscription.canceled` webhook | Access scheduled for revocation | | |
| 6.2.4 | Verify webhook signature validation | Invalid signatures rejected | | |
| 6.2.5 | Verify idempotent processing | Replayed webhooks produce no side effects | | |

---

## Section 7: Transactional Emails

### 7.1 Account Emails (Existing)

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 7.1.1 | Sign up | Confirmation email received | | |
| 7.1.2 | Reset password | Reset email received with valid link | | |
| 7.1.3 | Change email | Verification email sent to new address | | |
| 7.1.4 | Team invitation | Invitation email with accept link received | | |

### 7.2 Workflow Notification Emails

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 7.2.1 | Decision request created | Email sent to accountable/responsible participants | | |
| 7.2.2 | Stand-up participation requested | Email sent to RACI participants (if Slack unavailable) | | |
| 7.2.3 | WP moved to `for_review` | Reviewer notification email sent | | |
| 7.2.4 | WP moved to `done` | Mission owner notification email sent | | |
| 7.2.5 | Feature completed (all WPs done) | Completion summary email to team | | |
| 7.2.6 | Connector health degraded | Admin notification email sent | | |

### 7.3 Email Preferences

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 7.3.1 | Navigate to email preferences page | All notification categories listed with toggles | | |
| 7.3.2 | Disable decision request emails | No email sent on next decision request | | |
| 7.3.3 | Re-enable decision request emails | Email resumes on next decision request | | |
| 7.3.4 | Verify team-level defaults | New team members inherit team notification defaults | | |
| 7.3.5 | User override of team defaults | Personal toggle overrides team setting | | |

---

## Section 8: Status Parity (Local CLI vs SaaS)

### 8.1 Status Comparison

The bundled local web dashboard has been removed. Compare `spec-kitty agent tasks status` output with the SaaS dashboard for the same Mission:

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 8.1.1 | Compare lane layout | Same lanes, same lane names | | |
| 8.1.2 | Compare WP content | Same information: WP ID, title, status, assignee | | |
| 8.1.3 | Compare lane vocabulary | Identical: planned, claimed, in_progress, for_review, done, blocked, canceled | | |
| 8.1.4 | Compare Mission list/overview | Same Missions visible with same status counts | | |
| 8.1.5 | Take a SaaS screenshot and save the CLI `--json` output | Archive for brand review sign-off | | |

### 8.2 Brand Token Verification

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 8.2.1 | Verify `--sk-baby-blue` (#A7C7E7) used in SaaS | Present in CSS custom properties | | |
| 8.2.2 | Verify `--sk-grassy-green` (#7BB661) mapped to `--primary` | DaisyUI primary uses grassy-green family | | |
| 8.2.3 | Verify neutral surfaces | Creamy-white/light-gray family for backgrounds | | |
| 8.2.4 | Verify `--sk-dark-text` (#2c3e50) | Body text uses spec-kitty dark text | | |
| 8.2.5 | Verify DaisyUI error/success semantics preserved | Error/success badges still use DaisyUI defaults for accessibility | | |
| 8.2.6 | Check contrast ratios | Badge + text combinations meet WCAG AA | | |

---

## Section 9: API and Integration Contracts

### 9.1 REST API

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 9.1.1 | Fetch OpenAPI schema: `GET /api/schema/` | Valid OpenAPI 3.0 document returned | | |
| 9.1.2 | Open Swagger UI: `/api/schema/swagger-ui/` | Interactive API documentation loads | | |
| 9.1.3 | Open ReDoc: `/api/schema/redoc/` | Reference documentation loads | | |
| 9.1.4 | `GET /api/v1/sync/projects/` with JWT | Returns team-scoped project list | | |
| 9.1.5 | `GET /api/v1/sync/features/` with JWT | Returns features for project | | |
| 9.1.6 | `GET /api/v1/sync/work-packages/` with JWT | Returns WPs with status | | |
| 9.1.7 | `POST /api/v1/events/batch/` with event array | Events ingested, 2xx response | | |
| 9.1.8 | Verify team isolation on API | Cannot access other team's resources with valid JWT | | |
| 9.1.9 | Verify rate limiting | Exceeding rate limit returns 429 | | |
| 9.1.10 | Use API key (UserAPIKey) instead of JWT | Same endpoints accessible | | |
| 9.1.11 | Use TeamAPIKey | Machine-client access works for team resources | | |

### 9.2 WebSocket

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 9.2.1 | Connect WebSocket with valid token | Connection established | | |
| 9.2.2 | Verify heartbeat | Ping/pong within expected interval | | |
| 9.2.3 | Send event via WebSocket | Event processed, acknowledged | | |
| 9.2.4 | Receive real-time update | Status change from CLI appears via WebSocket push | | |
| 9.2.5 | Connect with expired token | Rejected with auth error | | |

---

## Section 10: Monitoring and Observability

### 10.1 Health Checks

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 10.1.1 | `GET /health/` | Returns 200 with database and Redis status | | |
| 10.1.2 | Kill Redis, check health | Returns degraded status for Redis | | |
| 10.1.3 | Restart Redis, check health | Returns healthy | | |

### 10.2 Prometheus Metrics

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 10.2.1 | `GET /metrics` | Prometheus-format metrics returned | | |
| 10.2.2 | Verify request timing metrics | `django_http_requests_latency_seconds` present | | |
| 10.2.3 | Verify custom business metrics | Event ingestion counts, sync latency present | | |

### 10.3 Sentry Integration

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 10.3.1 | Trigger an unhandled exception | Error appears in Sentry with full stack trace | | |
| 10.3.2 | Verify user context | Sentry event includes user ID and team | | |
| 10.3.3 | Verify tag propagation | Custom tags (project_slug, feature_slug) present | | |

---

## Section 11: Security

### 11.1 Authentication Security

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 11.1.1 | Attempt SQL injection on login form | Rejected, no error leak | | |
| 11.1.2 | Attempt XSS in user-submitted content | Content sanitized, no script execution | | |
| 11.1.3 | Attempt CSRF on state-changing endpoint | Rejected without valid CSRF token | | |
| 11.1.4 | Verify credential file permissions | `~/.spec-kitty/credentials` has 0600 permissions | | |
| 11.1.5 | Verify connector secrets encrypted at rest | Fernet-encrypted in database, not plaintext | | |

### 11.2 Authorization

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 11.2.1 | Member attempts admin action | Rejected with 403 | | |
| 11.2.2 | User attempts to access another team's data | Rejected, no data leak | | |
| 11.2.3 | API key with revoked team access | Rejected immediately | | |
| 11.2.4 | Expired JWT without refresh | 401 returned, no access | | |

---

## Section 12: Edge Cases and Error Handling

### 12.1 Concurrent Agent Operations

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 12.1.1 | Two agents implement same WP simultaneously | Concurrent driver warning emitted | | |
| 12.1.2 | Two agents move same WP to different lanes | Last-write-wins with full audit trail, no data corruption | | |
| 12.1.3 | Agent works in stale worktree | Clear error or merge conflict on push, not silent data loss | | |

### 12.2 Network Failures

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 12.2.1 | CLI loses network mid-sync | Graceful degradation to offline queue | | |
| 12.2.2 | SaaS database unreachable | Health check fails, 503 returned, no crash | | |
| 12.2.3 | Connector webhook endpoint unreachable | Dead-letter queue captures event for retry | | |
| 12.2.4 | Nango token refresh fails | Connector health degrades, ops log records it | | |

### 12.3 Data Integrity

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 12.3.1 | Corrupt a line in `status.events.jsonl` | `spec-kitty doctor mission-state --audit` detects corruption, reports it | | |
| 12.3.2 | Duplicate event IDs in event log | Deduplication prevents double-processing | | |
| 12.3.3 | Merge two branches with divergent event logs | Events merged deterministically by ULID ordering | | |
| 12.3.4 | Delete a WP file while in `in_progress` | Status system detects orphan, `doctor mission-state --audit` reports it | | |

---

## Section 13: Performance Smoke Tests

| # | Step | Expected Result | Pass/Fail | Notes |
|---|------|-----------------|-----------|-------|
| 13.1 | SaaS dashboard page load (cold) | Under 3 seconds | | |
| 13.2 | SaaS dashboard page load (warm) | Under 1 second | | |
| 13.3 | Kanban board with 50+ WPs | Renders without lag | | |
| 13.4 | Batch sync of 100 queued events | Completes within 10 seconds | | |
| 13.6 | `spec-kitty status` command | Output in under 1 second | | |
| 13.7 | `spec-kitty next` command | Decision returned in under 2 seconds | | |
| 13.8 | WebSocket reconnection after drop | Reconnects within 5 seconds (first attempt) | | |

---

## Section 14: GA Readiness Gate Checklist

Cross-reference with Feature 022 WP09 GA readiness report:

| Gate | Criterion | Status | Notes |
|------|-----------|--------|-------|
| **Billing** | Polar checkout → subscription → entitlement flow works | | |
| **Billing** | Subscription lifecycle (trial → active → delinquent → canceled) | | |
| **OAuth (Jira)** | Connect → token → sync → rotate → disconnect | | |
| **OAuth (Linear)** | Connect → token → sync → rotate → disconnect | | |
| **OAuth (GitHub)** | Connect → token → webhook → sync → disconnect | | |
| **OAuth (GitLab)** | Connect → token → webhook → sync → disconnect | | |
| **OAuth (Slack)** | Connect → bot → thread → notification → disconnect | | |
| **Notifications** | Decision request email triggers | | |
| **Notifications** | Stand-up participation email triggers | | |
| **Notifications** | Status transition notifications trigger | | |
| **Notifications** | User preference toggles work | | |
| **Dashboard** | Brand tokens applied | | |
| **Dashboard** | Status parity with local CLI verified (Section 8) | | |
| **Security** | Connector secrets encrypted at rest | | |
| **Security** | Webhook signature validation on all endpoints | | |
| **Observability** | Connector health rollup API operational | | |
| **Observability** | Ingress/egress ops logs visible | | |
| **Observability** | Dead-letter telemetry operational | | |
| **Stability** | No critical Sentry errors in 48-hour staging soak | | |

---

## Execution Notes

### Test Order Recommendation

1. **Section 1** (CLI core) — baseline verification, no SaaS needed
2. **Section 2** (Auth/sync) — establishes CLI ↔ SaaS connection
3. **Section 3** (SaaS dashboard) — verify the web experience
4. **Section 8** (Status parity) — compare local CLI vs SaaS
5. **Section 4.1–4.4** (Jira → Linear → GitHub → GitLab) — follows ADR connector order
6. **Section 4.5** (Slack) — prerequisite for stand-ups
7. **Section 5** (Spontaneous stand-ups) — the flagship differentiator
8. **Section 6** (Payments) — Polar integration
9. **Section 7** (Emails) — notification flows
10. **Section 9–13** (API, monitoring, security, edge cases, performance) — hardening

### Reporting

For each section, record:
- **Date tested**
- **Tester name**
- **Environment** (staging URL, CLI version, browser)
- **Pass/Fail** for each line item
- **Screenshots** for visual tests (Sections 3, 8)
- **Blockers** requiring engineering fix before retest

### Retest Policy

- Any **Fail** in Sections 1–6 blocks Beta
- Any **Fail** in Section 14 (GA gate) blocks Paid GA
- Section 12 (edge cases) failures are logged as issues, not Beta blockers unless data loss
- Section 13 (performance) failures trigger investigation, not automatic block
