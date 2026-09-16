---
title: Orchestrator API Reference
description: Machine-contract API for external orchestration providers.
doc_status: active
updated: '2026-09-03'
related:
- docs/api/event-envelope.md
- docs/migrations/feature-flag-deprecation.md
- docs/migrations/mission-id-canonical-identity.md
- docs/migrations/mission-type-flag-deprecation.md
---
# Orchestrator API Reference

`spec-kitty orchestrator-api` is the canonical JSON-first host interface for
external orchestrators.

It is intentionally stricter than the human-facing CLI:

- use `--mission`; the `--feature` flag has been removed from all user-facing commands
- expect one JSON envelope on stdout for both success and failure
- treat `error_code` as the stable machine discriminator
- do not append `--json`; JSON is the default output for this command group

## Canonical Terms

- `Mission Type` = reusable blueprint key
- `Mission` = tracked item under `kitty-specs/<mission-slug>/`
- `Mission Run` = runtime/session instance

## Contract Version

- `CONTRACT_VERSION`: `1.5.0`
- `MIN_PROVIDER_VERSION`: `0.1.0`
- Startup probe: `spec-kitty orchestrator-api contract-version`
- A `--provider-version` below `MIN_PROVIDER_VERSION`, or one that does not
  parse as a version string, always returns exit code 1 with
  `error_code: CONTRACT_VERSION_MISMATCH` — never a silent default. Call
  `contract-version` with `--provider-version` at startup to fail fast on an
  incompatible provider instead of discovering the mismatch mid-workflow.

Version history (the authoritative ledger lives at the `CONTRACT_VERSION`
constant in `src/specify_cli/orchestrator_api/envelope.py`):

- `1.1.0` — `start-implementation` allocates/reuses the lane worktree; its
  response carries `lane_id` / `lane_branch` / `lane_base_ref`, and
  `workspace_path` means that lane worktree. New error code
  `LANE_ALLOCATION_FAILED`.
- `1.2.0` — new read-only `resolve-workspace` command (#2337). Purely additive.
- `1.3.0` — `transition` accepts structured `--review-result-json`, allowing
  guarded `in_review` exits without recovery-only force overrides.
- `1.4.0` — added 11 new verbs (#3837): design-phase scaffolding (`specify`,
  `plan`, `tasks`, `check-prerequisites`, `record-analysis`);
  decision-resolution (`open-decision`, `resolve-decision`, `defer-decision`,
  `cancel-decision`, `answer-decision`); plus the read-only `design-status`
  query verb. Purely additive — see [Design-Phase Commands](#design-phase-commands)
  below. An external host can now drive the entire design pipeline
  (`specify → plan → tasks → check-prerequisites/record-analysis →
  decision resolution`) without crossing into host-CLI territory; see
  [Host Boundary Rules](../../src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/host-boundary-rules.md)
  for the updated Boundary Decision Matrix.
- `1.5.0` — the `tasks` verb's pass-through `data` gained the
  `planning_commit` object (`action` / `sha` / `previous_sha` / `branch_tip`)
  from the delegate finalize-tasks `--json` payload (#4141, the
  `--refresh-planning-commit` re-point affordance). Purely additive.

## Response Envelope

Every command returns exactly one JSON object with these 7 top-level keys:

```json
{
  "contract_version": "1.0.0",
  "command": "orchestrator-api.mission-state",
  "timestamp": "2026-04-08T12:00:00+00:00",
  "correlation_id": "corr-0123456789abcdef",
  "success": true,
  "error_code": null,
  "data": {}
}
```

| Field | Meaning |
|---|---|
| `contract_version` | Host API contract version. |
| `command` | Fully-qualified command name. |
| `timestamp` | ISO 8601 UTC response timestamp. |
| `correlation_id` | Unique per-response correlation token. |
| `success` | `true` for success, `false` for failure. |
| `error_code` | Machine-readable failure code, otherwise `null`. |
| `data` | Command-specific payload. |

Parser and usage failures also return the same envelope shape with
`error_code="USAGE_ERROR"`.

## Canonical Mission Identity

Success payloads that identify a tracked mission emit:

| Field | Meaning |
|---|---|
| `mission_id` | Canonical ULID machine identity. Aggregate routing uses this field. |
| `mission_slug` | Human-readable mission slug. Display context only. |
| `mission_number` | **Display-only** numeric prefix. `null` pre-merge, assigned at merge time. Never used for identity. |
| `mission_type` | Blueprint key |

The `--mission` selector accepts any of `mission_id`, `mid8` (first 8 chars of
the ULID), or `mission_slug`. Ambiguous handles return
`MISSION_AMBIGUOUS_SELECTOR` and list the candidates — there is no silent
fallback. See [Mission ID Canonical Identity Migration](../migrations/mission-id-canonical-identity.md).

Forbidden in orchestrator-api payloads:

- `feature_slug`

Removed at the CLI boundary:

- `--feature` (hard-removed in #1060; passing it yields exit code 2 with "No such option: --feature")

## Commands

| Command | Mutates state | Purpose |
|---|---:|---|
| `contract-version` | no | Check API compatibility. |
| `mission-state` | no | Query mission state and WP lanes. |
| `list-ready` | no | List WPs ready to start. |
| `resolve-workspace` | no | Resolve a WP's existing lane workspace (contract >= 1.2.0). |
| `start-implementation` | yes | Atomically move a WP into implementation. |
| `start-review` | yes | Claim active review for a WP. |
| `transition` | yes | Emit one explicit lane transition. |
| `append-history` | yes | Append a WP activity-log note. |
| `accept-mission` | yes | Record mission acceptance. |
| `merge-mission` | yes | Merge the mission into its target branch. |
| `specify` | yes | Create a mission scaffold (contract >= 1.4.0). |
| `plan` | yes | Scaffold `plan.md` for a mission (contract >= 1.4.0). |
| `tasks` | yes | Finalize WP task metadata (contract >= 1.4.0). |
| `check-prerequisites` | no | Read-only mission-prerequisite context for `analyze` (contract >= 1.4.0). |
| `record-analysis` | yes | Persist an `analyze` report, artifact-verified (contract >= 1.4.0). |
| `open-decision` | yes | Open a Decision Moment ledger entry (contract >= 1.4.0). |
| `resolve-decision` | yes | Resolve a decision with a final answer (contract >= 1.4.0). |
| `defer-decision` | yes | Defer a decision for later resolution (contract >= 1.4.0). |
| `cancel-decision` | yes | Cancel a decision (contract >= 1.4.0). |
| `design-status` | no | Read-only design-phase status query (contract >= 1.4.0). |
| `answer-decision` | yes | Resolve a `spec-kitty next` `decision_required` moment, with full host-CLI event/lifecycle parity (contract >= 1.4.0). |

Legacy command names such as `feature-state`, `accept-feature`, and
`merge-feature` are forbidden.

See [Design-Phase Commands](#design-phase-commands) below for the full
request/response/error-code contract of the 11 new verbs.

## Required Flags

The tracked-mission selector is always:

```bash
spec-kitty orchestrator-api mission-state --mission 077-mission-terminology-cleanup
```

Run-affecting implementation and review mutations require `--policy`. Today
that means `start-implementation`, `start-review`, and `transition` when the
target lane is run-affecting. `append-history`, `accept-mission`, and
`merge-mission` do not accept `--policy`.

The policy JSON object must include:

- `orchestrator_id`
- `orchestrator_version`
- `agent_family`
- `approval_mode`
- `sandbox_mode`
- `network_mode`
- `dangerous_flags`

Secret-like values in `--policy` are rejected.

Minimal policy example:

```json
{
  "orchestrator_id": "spec-kitty-orchestrator",
  "orchestrator_version": "0.1.0",
  "agent_family": "claude",
  "approval_mode": "full_auto",
  "sandbox_mode": "workspace_write",
  "network_mode": "none",
  "dangerous_flags": []
}
```

## Lane Model for Orchestrators

External providers should treat these lanes as the public orchestration model:

| Lane | Meaning |
|---|---|
| `planned` | WP exists but has not started. |
| `claimed` | WP is claimed by an actor as part of implementation start. |
| `in_progress` | Implementation or rework is active. |
| `for_review` | Implementation is ready for review. |
| `in_review` | A reviewer has claimed active review. |
| `approved` | Review accepted but integration may still be pending. |
| `done` | WP is complete. |
| `blocked` | WP cannot continue without intervention. |
| `canceled` | WP was intentionally canceled. |

The reference orchestrator normally drives:

```text
planned -> claimed -> in_progress -> for_review -> in_review -> done
```

Rejected review cycles move back through:

```text
in_review -> in_progress -> for_review
```

## Acceptance Payload

`accept-mission` requires every WP to be `approved` or `done`. It returns:

| Field | Meaning |
|---|---|
| `accepted_wps` | WPs counted by mission acceptance (`approved` plus `done`) |
| `approved_wps` | Review-passed WPs still awaiting merge/integration |
| `done_wps` | WPs already merged/integrated |
| `merge_pending_wps` | Alias of `approved_wps`; WPs accepted-ready but not done |

`accept-mission` does not move WPs from `approved` to `done`; merge owns that
transition.

## Design-Phase Commands

Contract `1.4.0` (#3837) adds 11 verbs so an external host can drive the
entire design pipeline — `specify → plan → tasks →
check-prerequisites/record-analysis → decision resolution` — the same way it
already drives the WP-implementation loop above, without ever calling
`spec-kitty next` or another host-CLI command directly. See
[Host Boundary Rules](../../src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/host-boundary-rules.md)
for when to use these verbs versus the host CLI.

### specify

Creates a mission scaffold — the same enriched payload the host CLI's own
`specify --json` returns (`agent_feature.create_mission`'s raw payload plus
`scaffold_only` / `spec_state` / `next_action` / `next_step`), not the
unenriched dict one layer beneath it.

Request:

```bash
spec-kitty orchestrator-api specify \
  --mission 090-orchestrator-driven-mission \
  --mission-type software-dev \
  --topology lanes \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

| Flag | Required | Meaning |
|---|---|---|
| `--mission` | yes | Mission slug to create. |
| `--mission-type` | yes | Blueprint key (e.g. `software-dev`). |
| `--topology` | no | Create-time mission shape: `single_branch` \| `lanes` \| `coord` \| `lanes_with_coord`. Defaults to the context-derived default (matches the host CLI's own `--topology` default) when omitted. |
| `--policy` | yes | Policy metadata JSON (see [Required Flags](#required-flags)). |

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_ALREADY_EXISTS` (the mission-creation delegate refused a duplicate —
a live same-key prior mission (#4033), or a retry whose scaffold is
byte-identical to what is already committed — surfaced as the typed
`MissionAlreadyExistsError` signal), `MISSION_CREATE_FAILED`
(any other creation failure with no more specific `error_code`; a typed
upstream code such as `CharterPackConfigError` is passed through verbatim
instead). Classification consumes only the delegate's typed `error_code`,
never its message prose (#3861).

### plan

Scaffolds `plan.md`. Deliberately **unenriched** — the response `data` is
`agent_feature.setup_plan`'s raw payload verbatim (the host CLI's own
`--json` path adds no enrichment here either, unlike `specify`), with
`mission_slug` filled in only if the delegate payload did not already carry
it.

Request:

```bash
spec-kitty orchestrator-api plan \
  --mission 090-orchestrator-driven-mission \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `PLAN_SETUP_FAILED` (delegate call failed with no more
specific `error_code` of its own; a typed upstream code is passed through
verbatim instead).

### tasks

Finalizes WP task metadata. Same deliberate non-enrichment as `plan` — the
response `data` is `agent_feature.finalize_tasks`'s raw payload verbatim,
with `mission_slug` always filled in (unlike `plan`, the raw payload never
carries it).

Request:

```bash
spec-kitty orchestrator-api tasks \
  --mission 090-orchestrator-driven-mission \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `TASKS_FINALIZE_FAILED` (delegate call failed with no
more specific `error_code` of its own; a typed upstream code is passed
through verbatim instead).

### check-prerequisites

Read-only mission-prerequisite context for `/spec-kitty.analyze` — it
supplies context only and never performs `analyze`'s cross-artifact
reasoning itself. No `--policy` required.

Request:

```bash
spec-kitty orchestrator-api check-prerequisites \
  --mission 090-orchestrator-driven-mission \
  --include-tasks
```

| Flag | Required | Meaning |
|---|---|---|
| `--mission` | yes | Mission slug. |
| `--include-tasks` | no | Include `tasks.md` validation (matches the host CLI's own `--include-tasks` default of `false`). |

Response `data`: the host CLI's own `validate_feature_structure` shape, with
`mission_slug` filled in (the raw shape does not already carry it).

Error codes: `MISSION_NOT_FOUND` (also returned — translated — when the
delegate call reports its own `FEATURE_CONTEXT_UNRESOLVED`, which never
crosses this surface verbatim per the Terminology Canon),
`CHECK_PREREQUISITES_FAILED` (fallback; any other typed upstream
`error_code` is passed through verbatim).

### record-analysis

Persists an `/spec-kitty.analyze` report. **Success is determined by
re-reading the artifact off disk after the write, never by the underlying
write call's own return/raise/hang behavior** (NFR-004): a caller MUST NOT
build retry logic that assumes a raised exception or a timeout means the
write did not happen — it may have. Concretely, `success: true` requires
BOTH (a) `analysis-report.md`'s re-read `generated_at` is strictly later
than this call's start timestamp, AND (b) the re-read `verdict` matches the
verdict submitted in this call's body. An `unknown` verdict (no valid
`analysis-findings/v1` carrier in the submitted body) is never reported as
success, even when the write itself genuinely, freshly succeeds.

Request:

```bash
spec-kitty orchestrator-api record-analysis \
  --mission 090-orchestrator-driven-mission \
  --input-file analysis-report-draft.md \
  --agent ci-bot \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

| Flag | Required | Meaning |
|---|---|---|
| `--mission` | yes | Mission slug. |
| `--input-file` | no (default `-`) | Markdown report path, or `-` to read the report body from stdin. |
| `--agent` | no | Agent name that produced the analysis report. |
| `--policy` | yes | Policy metadata JSON. |

Response `data` (success): `mission_slug`, `path` (the written
`analysis-report.md`), `verdict`, `generated_at`.

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND` (`--input-file`
could not be read), `RECORD_ANALYSIS_EMPTY_BODY` (body was empty),
`RECORD_ANALYSIS_MALFORMED_CARRIER` (the body carried a
present-but-invalid `analysis-findings/v1` carrier), `PLACEMENT_RESOLUTION_REQUIRED`,
`DIRTY_WORKTREE` (pre-existing uncommitted changes block the write),
`RECORD_ANALYSIS_WRITE_NOT_CONFIRMED` (no fresh write could be confirmed by
re-reading the artifact), `RECORD_ANALYSIS_VERDICT_UNRELIABLE` (a fresh
write WAS confirmed but its re-read verdict either disagrees with what this
call submitted, or the submission itself computed to `unknown`).

### open-decision

Opens a new Decision Moment ledger entry, or returns idempotently if a
matching one already exists.

Request:

```bash
spec-kitty orchestrator-api open-decision \
  --mission 090-orchestrator-driven-mission \
  --origin specify \
  --input-key clarification.scope \
  --question "Should this mission include the legacy migration path?" \
  --step-id interview-scope \
  --options '["yes", "no"]' \
  --actor ci-bot \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

| Flag | Required | Meaning |
|---|---|---|
| `--mission` | yes | Mission slug. |
| `--origin` | yes | Origin flow: `charter` \| `specify` \| `plan`. |
| `--input-key` | yes | The input key this decision governs. |
| `--question` | yes | Human-readable question text. |
| `--step-id` | no | Interview step identifier. |
| `--slot-key` | no | Slot key (use when `--step-id` is unavailable). |
| `--options` | no | Candidate answers as a JSON array string. |
| `--actor` | yes | Actor identity. |
| `--policy` | yes | Policy metadata JSON. |

Response `data`: mission identity fields (`mission_slug` / `mission_number` /
`mission_type` — no `mission_id`, unlike the Canonical Mission Identity
payload shape documented above), `decision_id`, `status` (`"open"`),
`idempotent`, `artifact_path`, `event_lamport`.

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `INVALID_ORIGIN_FLOW` (`--origin` outside
`{charter, specify, plan}`, rejected before the decision service is ever
called), `DECISION_MISSING_STEP_OR_SLOT` (neither `--step-id` nor
`--slot-key` supplied), `DECISION_ALREADY_CLOSED` (a matching logical-key
entry already exists in a terminal state), `DECISION_EVENT_REPAIR_FAILED`
(the idempotent-open path could not re-emit a missing ledger event).

### resolve-decision

Resolves a decision with a concrete final answer.

Request:

```bash
spec-kitty orchestrator-api resolve-decision \
  --mission 090-orchestrator-driven-mission \
  --decision-id 01HXYZDECISIONULID \
  --final-answer "yes" \
  --rationale "Legacy migration is in scope per stakeholder sign-off." \
  --actor ci-bot \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

| Flag | Required | Meaning |
|---|---|---|
| `--mission` | yes | Mission slug. |
| `--decision-id` | yes | Decision ledger entry ID (ULID). |
| `--final-answer` | yes | The chosen answer (non-empty). |
| `--other-answer` | no | Set when the answer is a write-in, not one of the offered options. |
| `--rationale` | no | Explanation of the choice. |
| `--resolved-by` | no | Identity of the resolving party (falls back to `--actor`). |
| `--actor` | yes | Actor identity. |
| `--policy` | yes | Policy metadata JSON. |

Response `data`: mission identity fields (`mission_slug` / `mission_number` /
`mission_type` — no `mission_id`, unlike the Canonical Mission Identity
payload shape documented above), `decision_id`, `status`
(`"resolved"`), `terminal_outcome`, `idempotent`, `event_lamport`.

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `DECISION_NOT_FOUND` (`--decision-id` not present in
the ledger), `DECISION_TERMINAL_CONFLICT` (the decision is already terminal
with a **different** outcome/payload than requested — never pre-checked
locally, always the service layer's own verdict, matching the host-CLI
`decision_app resolve` subcommand's own error code).

### defer-decision

Defers a decision for later resolution.

Request:

```bash
spec-kitty orchestrator-api defer-decision \
  --mission 090-orchestrator-driven-mission \
  --decision-id 01HXYZDECISIONULID \
  --rationale "Awaiting stakeholder input; revisit after design review." \
  --actor ci-bot \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

| Flag | Required | Meaning |
|---|---|---|
| `--mission` | yes | Mission slug. |
| `--decision-id` | yes | Decision ledger entry ID (ULID). |
| `--rationale` | yes | Explanation of why (must be non-empty). |
| `--resolved-by` | no | Identity of the deferring party (falls back to `--actor`). |
| `--actor` | yes | Actor identity. |
| `--policy` | yes | Policy metadata JSON. |

Response `data`: mission identity fields (`mission_slug` / `mission_number` /
`mission_type` — no `mission_id`, unlike the Canonical Mission Identity
payload shape documented above), `decision_id`, `status`
(`"deferred"`), `terminal_outcome`, `idempotent`, `event_lamport`.

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `DECISION_MISSING_STEP_OR_SLOT` (empty/whitespace-only
`--rationale`, rejected before the service layer is ever called — reuses
this code rather than minting a new one, matching the host CLI's own
`cmd_defer` guard verbatim), `DECISION_NOT_FOUND`, `DECISION_TERMINAL_CONFLICT`.

### cancel-decision

Cancels a decision deemed no longer relevant. Same request/response/error
shape as `defer-decision` above (`status` is `"canceled"` instead of
`"deferred"`; `--rationale` is likewise required and non-empty).

Request:

```bash
spec-kitty orchestrator-api cancel-decision \
  --mission 090-orchestrator-driven-mission \
  --decision-id 01HXYZDECISIONULID \
  --rationale "Superseded by a later decision; no longer applicable." \
  --actor ci-bot \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `DECISION_MISSING_STEP_OR_SLOT`, `DECISION_NOT_FOUND`,
`DECISION_TERMINAL_CONFLICT`.

### design-status

Read-only design-phase status query — no `--policy` required, no state
transition, no event emission (mirrors `list-ready`'s contract for the
design pipeline instead of the WP loop).

**Fails closed rather than reporting a wrong phase.** If
`status.events.jsonl` cannot be read cleanly — a torn/truncated line, or a
structural drift between the persisted `status.json` and a fresh event-log
reduction — this verb returns `DESIGN_STATUS_EVENT_LOG_UNREADABLE` instead
of a plausible-but-wrong `current_phase`/`next_action`. A caller can trust
any `current_phase` this verb actually returns; it must handle the explicit
unreadable case rather than treating a non-`success` response as
"phase unknown, assume the beginning."

Request:

```bash
spec-kitty orchestrator-api design-status --mission 090-orchestrator-driven-mission
```

Response `data`: mission identity fields (`mission_slug` / `mission_number` /
`mission_type` — no `mission_id`, unlike the Canonical Mission Identity
payload shape documented above), `current_phase` (`specify` \|
`plan` \| `tasks` \| `analyze`), `next_action` (the verb the host should
call next, or `null` once the design phase is complete; overridden to
`resolve-decision` whenever any decision is open, regardless of phase),
`open_decisions` (list of `{decision_id, origin}` for every open ledger
entry, from any phase).

Error codes: `MISSION_NOT_FOUND`, `DESIGN_STATUS_EVENT_LOG_UNREADABLE`.

### answer-decision

Resolves a `spec-kitty next` control-loop `decision_required` moment (a
blocking audit checkpoint, or a missing required input) for a DAG step in
**any** mission phase.

**This is a composite verb, not a simple single-purpose call.** One
invocation performs, in order: (1) persists the answer against the
resolved `decision_id`; (2) pairs the previous issuance's lifecycle record
before the DAG advances; (3) advances the DAG (the engine call that produces
the next `Decision`, using this call's own `--result`); (4) emits the
mission's `MissionNextInvoked` event-log entry; (5) writes a new issuance
lifecycle record whenever the resulting decision's `kind` is `"step"`. Steps
2/4/5 are **full host-CLI lifecycle parity** — `answer-decision` reaches
them through the same extracted seam `spec-kitty next --answer ...` itself
calls (operator ruling `SPEC-FRESH2-001`), so a host driving decisions
exclusively through `answer-decision` produces the identical event log and
lifecycle-record trail a host shelling `spec-kitty next --answer` would have
produced. Treat this parity as a promise: an external host does not need to
also call the host CLI to keep the mission's audit trail complete.

Request:

```bash
spec-kitty orchestrator-api answer-decision \
  --mission 090-orchestrator-driven-mission \
  --agent ci-bot \
  --answer "yes" \
  --result success \
  --policy '{"orchestrator_id":"ci","orchestrator_version":"1.0.0","agent_family":"ci-bot","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

| Flag | Required | Meaning |
|---|---|---|
| `--mission` | yes | Mission slug. |
| `--agent` | yes | Agent/actor identity performing this call. |
| `--answer` | yes | The answer value to persist for the pending decision. |
| `--result` | yes | Outcome of the current issuance: `success` \| `failed` \| `blocked`. |
| `--decision-id` | no | Run-snapshot pending decision id to answer; auto-resolved when omitted and exactly one decision is pending. |
| `--policy` | yes | Policy metadata JSON. |

Response `data`: the SAME shape `spec-kitty next --answer ... --json`
returns — every `Decision.to_dict()` field (`kind`, `agent`, `mission_slug`,
`mission_number`, `mission_type`, `mission`,
`mission_state`, `timestamp`, `action`, `wp_id`, `workspace_path`,
`prompt_file`, `reason`, `guard_failures`, `progress`, `origin`, `run_id`,
`step_id`, `decision_id`, `input_key`, `question`, `options`, `is_query`,
`preview_step`) — plus one sibling field, `answered_decision_id` (the
`decision_id` this call persisted the answer against). Note `Decision.to_dict()`
does NOT carry a `mission_id` field (unlike the Canonical Mission Identity
payload shape documented above, its `mission_identity_fields()` helper here
only normalizes `mission_slug` / `mission_number` / `mission_type`). `data`
does **not** carry an `answer` echo key; the host CLI's terser `answered`
key is similarly not used.

Error codes: `POLICY_METADATA_REQUIRED`, `POLICY_VALIDATION_FAILED`,
`MISSION_NOT_FOUND`, `RESULT_REQUIRED` (`--result` omitted), `INVALID_RESULT`
(`--result` is not one of `success`/`failed`/`blocked`, rejected before any
decision resolution or persistence), `NO_PENDING_DECISION` (no pending
decision exists to answer), `AMBIGUOUS_PENDING_DECISION` (more than one
pending decision and `--decision-id` was omitted — lists the candidate ids),
`DECISION_NOT_PENDING` (an explicit `--decision-id` does not match any
currently-pending entry).

## Example Commands

```bash
spec-kitty orchestrator-api contract-version
spec-kitty orchestrator-api mission-state --mission 077-mission-terminology-cleanup
spec-kitty orchestrator-api list-ready --mission 077-mission-terminology-cleanup
spec-kitty orchestrator-api start-implementation \
  --mission 077-mission-terminology-cleanup \
  --wp WP12 \
  --actor codex \
  --policy '{"orchestrator_id":"local","orchestrator_version":"1.0.0","agent_family":"codex","approval_mode":"never","sandbox_mode":"danger-full-access","network_mode":"enabled","dangerous_flags":[]}'
```

### Start implementation

```bash
spec-kitty orchestrator-api start-implementation \
  --mission 077-mission-terminology-cleanup \
  --wp WP12 \
  --actor spec-kitty-orchestrator \
  --policy '{"orchestrator_id":"spec-kitty-orchestrator","orchestrator_version":"0.1.0","agent_family":"claude","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}'
```

Important response fields:

| Field | Meaning |
|---|---|
| `workspace_path` | Path where the provider should run the implementation agent. |
| `prompt_path` | WP markdown prompt file to feed to the implementation agent. |
| `to_lane` | Expected to be `in_progress` on a fresh start. |
| `no_op` | `true` when the same actor already owns the compatible state. |

### Resolve an existing workspace (read-only, contract >= 1.2.0)

```bash
spec-kitty orchestrator-api resolve-workspace \
  --mission 077-mission-terminology-cleanup \
  --wp WP12
```

Returns the WP's lane `workspace_path` / `prompt_path` (plus `lane_id` /
`lane_branch` / `lane_base_ref` when the WP is lane-assigned) for its
**existing** lane — without allocating, creating, validating-clean, or
transitioning. Use it to resume a WP already past `start-implementation`
(for example, dispatching a reviewer to a WP parked in `for_review` after an
interrupted run, where calling `start-implementation` would wrongly
re-transition it). No `--policy` is required: the command mutates nothing.
The composed path is not guaranteed to exist for a WP that was never started.

### Mark implementation ready for review

```bash
spec-kitty orchestrator-api transition \
  --mission 077-mission-terminology-cleanup \
  --wp WP12 \
  --to for_review \
  --actor spec-kitty-orchestrator \
  --policy '{"orchestrator_id":"spec-kitty-orchestrator","orchestrator_version":"0.1.0","agent_family":"claude","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}' \
  --subtasks-complete \
  --implementation-evidence-present \
  --note "Implementation complete"
```

`in_progress -> for_review` requires evidence that the implementation handoff
is ready. Providers may supply the explicit guard hints shown above or omit them
and let the host derive the facts. `--force` is reserved for recovery.

### Claim review

```bash
spec-kitty orchestrator-api start-review \
  --mission 077-mission-terminology-cleanup \
  --wp WP12 \
  --actor spec-kitty-orchestrator \
  --policy '{"orchestrator_id":"spec-kitty-orchestrator","orchestrator_version":"0.1.0","agent_family":"codex","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}' \
  --review-ref review/WP12/attempt-1
```

On current hosts this moves `for_review -> in_review`.

### Complete approved review

```bash
spec-kitty orchestrator-api transition \
  --mission 077-mission-terminology-cleanup \
  --wp WP12 \
  --to done \
  --actor spec-kitty-orchestrator \
  --policy '{"orchestrator_id":"spec-kitty-orchestrator","orchestrator_version":"0.1.0","agent_family":"codex","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}' \
  --review-ref review/WP12/attempt-1 \
  --review-result-json '{"reviewer":"codex","verdict":"approved","reference":"review/WP12/attempt-1"}' \
  --evidence-json '{"review":{"reviewer":"codex","verdict":"approved","reference":"review/WP12/attempt-1"}}' \
  --note "Codex review approved"
```

The structured review result satisfies the `in_review` exit guard; done evidence
keeps the terminal event independently auditable. `--force` remains recovery-only.

### Send rejected review back to rework

```bash
spec-kitty orchestrator-api transition \
  --mission 077-mission-terminology-cleanup \
  --wp WP12 \
  --to in_progress \
  --actor spec-kitty-orchestrator \
  --policy '{"orchestrator_id":"spec-kitty-orchestrator","orchestrator_version":"0.1.0","agent_family":"codex","approval_mode":"full_auto","sandbox_mode":"workspace_write","network_mode":"none","dangerous_flags":[]}' \
  --review-ref review/WP12/attempt-1 \
  --review-result-json '{"reviewer":"codex","verdict":"changes_requested","reference":"review/WP12/attempt-1"}' \
  --note "Review rejected; rework required"
```

Then rerun the implementation agent with the review feedback and transition
back to `for_review`.

## Worktree Expectations

The host returns the workspace path. The provider is responsible for ensuring
the path exists and is usable for the agent process before spawning an agent.
Do not treat the returned string as proof that a worktree already exists.

State mutation commands should not be run from a protected main branch when
they need to commit activity-log updates. Use a mission lane/worktree branch for
provider-owned mutation calls.

## Error Codes

Current machine-readable error codes (the authoritative list is
`allowed_error_codes` in `src/specify_cli/core/upstream_contract.json`):

- `USAGE_ERROR`
- `POLICY_METADATA_REQUIRED`
- `POLICY_VALIDATION_FAILED`
- `MISSION_NOT_FOUND`
- `STATUS_READ_PATH_NOT_FOUND`
- `WP_NOT_FOUND`
- `TRANSITION_REJECTED`
- `WP_ALREADY_CLAIMED`
- `MISSION_NOT_READY`
- `WORKFLOW_EVIDENCE_REQUIRED`
- `PREFLIGHT_FAILED`
- `CONTRACT_VERSION_MISMATCH`
- `UNSUPPORTED_STRATEGY`
- `HISTORY_COMMIT_FAILED`
- `DEPENDENCIES_NOT_SATISFIED`
- `LANE_ALLOCATION_FAILED`
- `ANCESTRY_NOT_ESTABLISHED`
- `SAFE_COMMIT_BACKSTOP`
- `SAFE_COMMIT_DESTINATION_NOT_FOUND`
- `SAFE_COMMIT_DESTINATION_REF_SHAPE`
- `SAFE_COMMIT_EMPTY_CHANGESET`
- `SAFE_COMMIT_GENERIC`
- `SAFE_COMMIT_HEAD_MISMATCH`
- `SAFE_COMMIT_NOT_A_WORKTREE`
- `SAFE_COMMIT_PROTECTED_BRANCH`
- `SAFE_COMMIT_PATH_POLICY`
- `SAFE_COMMIT_RECOVERY_FAILED`

Added in contract `1.4.0` (#3837), for the 11 design-phase verbs above:

- `MISSION_ALREADY_EXISTS` — `specify`
- `MISSION_CREATE_FAILED` — `specify`
- `PLAN_SETUP_FAILED` — `plan`
- `TASKS_FINALIZE_FAILED` — `tasks`
- `PLACEMENT_RESOLUTION_REQUIRED` — `record-analysis`
- `CHECK_PREREQUISITES_FAILED` — `check-prerequisites`
- `RECORD_ANALYSIS_EMPTY_BODY` — `record-analysis`
- `RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND` — `record-analysis`
- `RECORD_ANALYSIS_MALFORMED_CARRIER` — `record-analysis`
- `RECORD_ANALYSIS_WRITE_NOT_CONFIRMED` — `record-analysis`
- `RECORD_ANALYSIS_VERDICT_UNRELIABLE` — `record-analysis`
- `DIRTY_WORKTREE` — `record-analysis`
- `INVALID_ORIGIN_FLOW` — `open-decision`
- `DECISION_MISSING_STEP_OR_SLOT` — `open-decision`, `defer-decision`, `cancel-decision`
- `DECISION_ALREADY_CLOSED` — `open-decision`
- `DECISION_NOT_FOUND` — `resolve-decision`, `defer-decision`, `cancel-decision`
- `DECISION_TERMINAL_CONFLICT` — `resolve-decision`, `defer-decision`, `cancel-decision`
- `DECISION_EVENT_REPAIR_FAILED` — `open-decision`
- `DESIGN_STATUS_EVENT_LOG_UNREADABLE` — `design-status`
- `RESULT_REQUIRED` — `answer-decision`
- `INVALID_RESULT` — `answer-decision`
- `NO_PENDING_DECISION` — `answer-decision`
- `AMBIGUOUS_PENDING_DECISION` — `answer-decision`
- `DECISION_NOT_PENDING` — `answer-decision`
- `DECISION_OPERATION_FAILED` — `open-decision`, `resolve-decision`, `defer-decision`, `cancel-decision` (fallback when a decision-ledger operation fails for a reason without a more specific registered code)

## Provider Rules

- Call `contract-version` once before mutating state.
- Use only `orchestrator-api` for lane changes.
- Keep retry decisions based on `error_code`, not prose.
- Preserve `review_ref` values in logs and issue/PR links.
- Treat `mission-state` as authoritative after every recovery.
- Keep agent stdout/stderr in provider logs; do not stuff full logs into WP
  history entries.

## Migration Notes

- The human-facing CLI still supports hidden deprecated aliases during the
  migration window.
- The orchestrator API does not. It is canonical-only on `--mission` and
  `mission_*` payload fields.

See also:

- [Event Envelope Reference](event-envelope.md)
- [Feature Flag Deprecation](../migrations/feature-flag-deprecation.md)
- [Mission Type Flag Deprecation](../migrations/mission-type-flag-deprecation.md)
