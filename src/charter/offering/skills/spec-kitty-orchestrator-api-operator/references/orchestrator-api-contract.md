# Orchestrator API Contract Reference

Complete CLI reference for `spec-kitty orchestrator-api` subcommands.

Every command returns a canonical JSON envelope:

```json
{
  "contract_version": "1.5.0",
  "command": "orchestrator-api.<subcommand-name>",
  "timestamp": "2026-03-21T08:00:00Z",
  "correlation_id": "uuid-v4",
  "success": true,
  "error_code": null,
  "data": { ... }
}
```

On failure, `success` is `false` and `error_code` contains a machine-readable
code. The `data` field may contain diagnostic details.

---

## 1. contract-version

Verify API contract compatibility between orchestrator and host CLI.

```bash
spec-kitty orchestrator-api contract-version [--provider-version TEXT]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--provider-version` | TEXT | none | Orchestrator's contract version for compatibility check |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `api_version` | string | Current API contract version |
| `min_supported_provider_version` | string | Minimum provider version the host accepts |

**Error codes:**

| Code | Cause |
|------|-------|
| `CONTRACT_VERSION_MISMATCH` | Provider version is below `min_supported_provider_version` (currently `0.1.0`), or is not a parseable version string |

**Usage notes:**

- Call at orchestrator startup, before any other commands
- Do not cache across host CLI version changes
- If the error fires, upgrade the orchestrator to match the host
- An unsupported `--provider-version` always exits 1 with `CONTRACT_VERSION_MISMATCH` — never a silent default — whether the version is below the minimum or simply unparseable

---

## 2. mission-state

Query the full state of a mission and all its work packages.

```bash
spec-kitty orchestrator-api mission-state --mission TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug (e.g., `017-my-mission`) |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `summary.done_count` | int | WPs in the `done` lane |
| `summary.for_review_count` | int | WPs in the `for_review` lane |
| `summary.in_progress_count` | int | WPs in the `in_progress` lane |
| `summary.planned_count` | int | WPs in the `planned` lane |
| `summary.total_wps` | int | Total number of work packages |
| `work_packages` | list | Per-WP objects with `wp_id`, `lane`, `dependencies`, `last_actor` |

**Error codes:**

| Code | Cause |
|------|-------|
| `MISSION_NOT_FOUND` | No mission with this slug exists in `kitty-specs/` |

---

## 3. list-ready

List work packages that are ready to start (dependencies satisfied, in
`planned` lane).

```bash
spec-kitty orchestrator-api list-ready --mission TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ready_work_packages` | list | Objects with fields below |
| `ready_work_packages[].wp_id` | string | Work package identifier (e.g., `WP01`) |
| `ready_work_packages[].lane` | string | Current lane (always `planned` for ready WPs) |
| `ready_work_packages[].dependencies_satisfied` | bool | Always `true` for returned WPs |

**Error codes:**

| Code | Cause |
|------|-------|
| `MISSION_NOT_FOUND` | No mission with this slug exists |

**Usage notes:**

- This is a query-only command; it does NOT modify any state
- Safe to poll repeatedly from CI
- An empty `ready_work_packages` list means all WPs are either in-progress, in-review, or done

---

## 4. start-implementation

Claim a work package and begin implementation. This is a composite transition
that moves the WP through planned -> claimed -> in_progress atomically.

```bash
spec-kitty orchestrator-api start-implementation \
  --mission TEXT --wp TEXT --actor TEXT --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--wp` | TEXT | required | Work package ID (e.g., `WP01`) |
| `--actor` | TEXT | required | Identity of the claiming actor |
| `--policy` | TEXT | required | JSON string with policy metadata (see below) |

**Policy JSON fields (all required):**

| Field | Type | Description |
|-------|------|-------------|
| `orchestrator_id` | string | Unique identifier for this orchestrator |
| `orchestrator_version` | string | Version of the orchestrator |
| `agent_family` | string | Agent type: `claude`, `codex`, `gemini`, etc. |
| `approval_mode` | string | `manual`, `auto`, or `supervised` |
| `sandbox_mode` | string | `container`, `none`, `vm`, etc. |
| `network_mode` | string | `restricted`, `full`, `none` |
| `dangerous_flags` | list | Any dangerous flags the agent has enabled |
| `tool_restrictions` | string or null | optional | Tools the agent is permitted to use |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `workspace_path` | string | Computed worktree path (the caller is responsible for creating the worktree) |
| `prompt_path` | string | Path to the WP task file (the caller is responsible for presenting it to the agent) |
| `from_lane` | string | Lane the WP was in before (`planned`, `claimed`, or `in_progress` for idempotent calls) |
| `to_lane` | string | Lane the WP is now in (`in_progress`) |
| `policy_metadata_recorded` | bool | Whether policy metadata was recorded |
| `no_op` | bool | `true` if WP was already `in_progress` by the same actor (idempotent hit) |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing or incomplete |
| `WP_ALREADY_CLAIMED` | Another actor has already claimed this WP |
| `TRANSITION_REJECTED` | Guard failure (dependency not met, invalid state) |

---

## 5. start-review

Reviewer claim/start: transitions a WP from `for_review` to `in_review` so a
reviewing actor owns the review lane. `--review-ref` is optional and links an
external review artifact when one exists.

```bash
spec-kitty orchestrator-api start-review \
  --mission TEXT --wp TEXT --actor TEXT [--review-ref TEXT] --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--wp` | TEXT | required | Work package ID |
| `--actor` | TEXT | required | Identity of the reviewing actor |
| `--review-ref` | TEXT | none | Optional reference to review feedback (PR comment URL, review ID) |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `from_lane` | string | Lane the WP was in before (typically `for_review`) |
| `to_lane` | string | Lane the WP is now in (`in_review`) |
| `prompt_path` | string | Path to the WP task file |
| `policy_metadata_recorded` | bool | Whether policy metadata was recorded |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing or incomplete |
| `TRANSITION_REJECTED` | WP is not in `for_review` lane or guard checks failed |

---

## 6. transition

Perform an explicit lane transition on a work package.

```bash
spec-kitty orchestrator-api transition \
  --mission TEXT --wp TEXT --to TEXT --actor TEXT \
  [--note TEXT] [--policy TEXT] [--force] [--review-ref TEXT] \
  [--review-result-json TEXT] [--evidence-json TEXT]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--wp` | TEXT | required | Work package ID |
| `--to` | TEXT | required | Target lane |
| `--actor` | TEXT | required | Identity of the transitioning actor |
| `--note` | TEXT | none | Audit note explaining the transition |
| `--policy` | TEXT | none | JSON policy metadata (required for run-affecting lanes) |
| `--force` | FLAG | off | Override guard checks (recovery only) |
| `--review-ref` | TEXT | none | Review artifact reference |
| `--review-result-json` | TEXT | none | Structured review outcome required for transitions from `in_review` |
| `--evidence-json` | TEXT | none | Structured evidence for `done` transitions |

**Valid target lanes:**

| Lane | Requires `--policy` | Description |
|------|---------------------|-------------|
| `planned` | no | Reset WP to planning state |
| `claimed` | yes | Mark WP as claimed by an actor |
| `in_progress` | yes | Mark WP as actively being worked |
| `for_review` | yes | Submit WP for review |
| `in_review` | yes | Mark WP as actively being reviewed |
| `approved` | no | Mark WP as approved |
| `done` | no | Mark WP as complete |
| `blocked` | no | Mark WP as blocked |
| `canceled` | no | Cancel the WP |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `from_lane` | string | Previous lane |
| `to_lane` | string | New lane |

**Error codes:**

| Code | Cause |
|------|-------|
| `TRANSITION_REJECTED` | Guard failure or invalid lane transition |
| `POLICY_METADATA_REQUIRED` | Run-affecting lane without `--policy` |

**Usage notes:**

- Use `--force` only for recovery from known-bad state, never in normal flow
- Use `--note` to record reasoning for audit trail
- Use `--review-ref` when transitioning from `for_review` or `approved` back to `in_progress` or `planned` (review rollback guard)

---

## 7. append-history

Append a timestamped note to a work package's history log.

```bash
spec-kitty orchestrator-api append-history \
  --mission TEXT --wp TEXT --actor TEXT --note TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--wp` | TEXT | required | Work package ID |
| `--actor` | TEXT | required | Identity of the author |
| `--note` | TEXT | required | History note content |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `history_entry_id` | string | Unique identifier for the history entry |

---

## 8. accept-mission

Mark a mission as accepted. All work packages must be `approved` or `done`.

```bash
spec-kitty orchestrator-api accept-mission --mission TEXT --actor TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--actor` | TEXT | required | Identity of the accepting actor |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `accepted` | bool | True if mission was accepted |
| `accepted_wps` | list[string] | WPs counted by mission acceptance (`approved` plus `done`) |
| `approved_wps` | list[string] | Review-passed WPs still awaiting merge/integration |
| `done_wps` | list[string] | WPs already merged/integrated |
| `merge_pending_wps` | list[string] | Alias of `approved_wps`; WPs accepted-ready but not done |

**Error codes:**

| Code | Cause |
|------|-------|
| `MISSION_NOT_READY` | One or more WPs are not `approved` or `done` |

**Usage notes:**

- Always call `mission-state` first to verify every WP is in `approved` or `done`
- This is a guard-protected operation; it will reject if any WP is not `approved` or `done`
- `accept-mission` does not move WPs from `approved` to `done`; merge owns that transition


---

## 9. merge-mission

Merge all work packages for a mission into the target branch.

```bash
spec-kitty orchestrator-api merge-mission \
  --mission TEXT [--target TEXT] [--strategy merge|squash|rebase] [--push]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--target` | TEXT | auto-detected from `meta.json` | Target branch to merge into |
| `--strategy` | TEXT | `squash` | Merge strategy: `merge`, `squash`, or `rebase` |
| `--push` | FLAG | off | Push to remote after merge |

**Data fields:**

| Field | Type | Description |
|-------|------|-------------|
| `merged` | bool | Whether the merge completed successfully |
| `merged_wps` | list | Work package IDs that were merged |
| `target_branch` | string | Branch merged into |
| `strategy` | string | Merge strategy that was used |
| `worktree_removed` | bool | Whether worktrees were cleaned up |

**Usage notes:**

- Mission should be accepted before merging
- The WP merge order respects the dependency graph
- Use `--push` only when the orchestrator has confirmed the merge result

---

## 10. resolve-workspace (read-only, contract >= 1.2.0)

Resolve a WP's **existing** lane workspace without allocating, creating,
validating-clean, or transitioning — the read-only companion of
`start-implementation` for a WP already past implementation (for example,
dispatching a reviewer to a WP parked in `for_review` after an interrupted
run, where `start-implementation` would wrongly re-transition it).

```bash
spec-kitty orchestrator-api resolve-workspace \
  --mission <mission> \
  --wp <WP-id>
```

No `--policy` is required: the command mutates nothing.

**Response `data` fields:**

| Field | Meaning |
|---|---|
| `mission_slug` / `mission_number` / `mission_type` | Resolved canonical mission identity |
| `wp_id` | The requested work package |
| `workspace_path` | The WP's lane worktree path (not guaranteed to exist for a never-started WP) |
| `prompt_path` | WP markdown prompt file |
| `lane_id` / `lane_branch` / `lane_base_ref` | Present when the WP is lane-assigned |

**Failure codes:** `MISSION_NOT_FOUND`, `WP_NOT_FOUND`.

---

## 11. specify (contract >= 1.4.0)

Create a mission scaffold — the same enriched payload the host CLI's own
`spec-kitty specify --json` path returns.

```bash
spec-kitty orchestrator-api specify \
  --mission TEXT --mission-type TEXT [--topology TEXT] --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--mission-type` | TEXT | required | Mission type (e.g., `software-dev`) |
| `--topology` | TEXT | context-derived | Create-time mission shape: `single_branch` \| `lanes` \| `coord` \| `lanes_with_coord` |
| `--policy` | TEXT | required | JSON string with policy metadata (see command 4) |

**Data fields** (mirrors the host CLI's own enriched `specify --json` payload — `specify_cli.cli.commands.lifecycle._create_mission_for_specify_json`; not a bare pass-through):

| Field | Type | Description |
|-------|------|--------------|
| `mission_slug` / `mission_number` / `mission_id` / `mission_type` | string | Mission identity — this verb's payload carries `mission_id`, unlike the read verbs below (which use the slug/number/type-only identity shape) |
| `feature_dir` / `spec_file` / `meta_file` | string | Paths written |
| `scaffold_only` | bool | Always `true` — this verb creates a scaffold, not a substantive spec |
| `spec_state` | string | Always `scaffold_only` |
| `next_action` / `next_step` | string | The recommended follow-up action (same value on both keys) |
| `topology` | string | Resolved mission topology |
| `coordination_branch` / `coordination_branch_created` | string or null, bool | Coordination branch, when the mission's topology has one |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `MISSION_ALREADY_EXISTS` | The delegate mission-creation call refused a duplicate (typed `MissionAlreadyExistsError` signal, #3861) |
| `MISSION_CREATE_FAILED` | Mission creation failed for any other reason (or the delegate's own typed `error_code`, passed through verbatim when present) |

**Usage notes:**

- This creates a scaffold only; it does not author a substantive spec. Follow with the agent authoring flow and then `plan`.

---

## 12. plan (contract >= 1.4.0)

Scaffold `plan.md` for a mission.

```bash
spec-kitty orchestrator-api plan --mission TEXT --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields** (an unenriched pass-through of `agent_feature.setup_plan`'s own `--json` payload — `mission_setup_plan.py`; deliberately asymmetric with `specify` above, no fields are added beyond filling in `mission_slug` when the delegate payload omits it):

| Field | Type | Description |
|-------|------|--------------|
| `result` | string | `success`, `blocked`, or `error` |
| `phase_complete` | bool | Whether `plan.md` is substantive |
| `mission_slug` | string | Mission slug |
| `plan_file` / `feature_dir` / `spec_file` | string | Paths |
| `plan_substantive` | bool | Whether plan content passed the substantiveness check |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `PLAN_SETUP_FAILED` | Fallback code when the delegate call failed without a more specific typed `error_code` of its own (which, when present, is passed through verbatim) |

**Usage notes:**

- Call after `specify` has produced a substantive, committed `spec.md`.

---

## 13. tasks (contract >= 1.4.0)

Finalize work-package task metadata for a mission.

```bash
spec-kitty orchestrator-api tasks --mission TEXT --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields:** an unenriched pass-through of `agent_feature.finalize_tasks`'s own `--json` payload (`mission_finalize.py`), with `mission_slug` filled in when the delegate payload omits it — the same deliberate non-enrichment as `plan` above.

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `TASKS_FINALIZE_FAILED` | Fallback code when the delegate call failed without a more specific typed `error_code` of its own (which, when present, is passed through verbatim) |

---

## 14. check-prerequisites (contract >= 1.4.0, read-only)

Read-only mission-prerequisite context for `/spec-kitty.analyze`. Supplies
context only — it never performs `analyze`'s cross-artifact reasoning
itself.

```bash
spec-kitty orchestrator-api check-prerequisites \
  --mission TEXT [--include-tasks]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--include-tasks` | FLAG | off | Include `tasks.md` validation |

No `--policy` is required: the command mutates nothing.

**Data fields:** a pass-through of the host CLI's own `check_prerequisites` Typer command (`mission_check_prerequisites.py`), with `mission_slug` filled in when the delegate payload omits it.

**Error codes:**

| Code | Cause |
|------|-------|
| `MISSION_NOT_FOUND` | Translated from the host CLI's own `FEATURE_CONTEXT_UNRESOLVED` (Terminology Canon guard — that feature-named code never crosses onto this surface verbatim) |
| `CHECK_PREREQUISITES_FAILED` | Fallback code when the delegate call failed without a more specific typed `error_code` of its own (which, when present, is passed through verbatim) |

---

## 15. record-analysis (contract >= 1.4.0)

Persist an `/spec-kitty.analyze` report, verified against disk before
reporting success.

```bash
spec-kitty orchestrator-api record-analysis \
  --mission TEXT [--input-file TEXT] [--agent TEXT] --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--input-file` | TEXT | `-` | Markdown report path, or `-` to read the report body from stdin |
| `--agent` | TEXT | none | Agent name that produced the analysis report |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields (on success):**

| Field | Type | Description |
|-------|------|--------------|
| `mission_slug` | string | Mission slug |
| `path` | string | Path to the written `analysis-report.md` |
| `verdict` | string | Recorded verdict |
| `generated_at` | string | Timestamp of the confirmed write |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND` | `--input-file` could not be read |
| `RECORD_ANALYSIS_EMPTY_BODY` | `--input-file`/stdin body was empty |
| `RECORD_ANALYSIS_MALFORMED_CARRIER` | The submitted body carried a present-but-invalid `analysis-findings/v1` carrier |
| `PLACEMENT_RESOLUTION_REQUIRED` | The write placement could not be resolved (fail-closed; never a silent current-branch fallback) |
| `DIRTY_WORKTREE` | Pre-existing uncommitted changes block the write |
| `RECORD_ANALYSIS_WRITE_NOT_CONFIRMED` | No fresh `analysis-report.md` write (a `generated_at` later than the call start) could be confirmed on disk |
| `RECORD_ANALYSIS_VERDICT_UNRELIABLE` | A fresh write was confirmed, but its verdict is not a trustworthy match for this call — either it disagrees with the submitted verdict, or the submission itself carried no valid carrier and computed to `unknown` |

**Usage notes:**

- Success is determined solely by re-reading `analysis-report.md` off disk after the write attempt — never by the underlying write call's own return/raise/hang behavior.
- A verdict of `unknown` (no valid `analysis-findings/v1` carrier in the submitted body) is never reported as `success: true`, even on a confirmed fresh write.

---

## 16. open-decision (contract >= 1.4.0)

Open a new Decision Moment ledger entry, or return idempotently if a
matching one already exists.

```bash
spec-kitty orchestrator-api open-decision \
  --mission TEXT --origin TEXT --input-key TEXT --question TEXT \
  [--step-id TEXT] [--slot-key TEXT] [--options TEXT] \
  --actor TEXT --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--origin` | TEXT | required | Origin flow: `charter` \| `specify` \| `plan` |
| `--input-key` | TEXT | required | The input key this decision governs |
| `--question` | TEXT | required | Human-readable question text |
| `--step-id` | TEXT | none | Interview step identifier |
| `--slot-key` | TEXT | none | Slot key (use when `--step-id` is unavailable) |
| `--options` | TEXT | none | Candidate answers as a JSON array string |
| `--actor` | TEXT | required | Identity of the opening actor |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields:**

| Field | Type | Description |
|-------|------|--------------|
| `mission_slug` / `mission_number` / `mission_type` | string | Resolved canonical mission identity |
| `decision_id` | string | Ledger entry ID (ULID) |
| `status` | string | `open` |
| `idempotent` | bool | `true` if an existing matching-logical-key entry was returned instead of creating a new one |
| `artifact_path` | string | Path to the decision's ledger artifact |
| `event_lamport` | int | Lamport clock of the recorded event |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `INVALID_ORIGIN_FLOW` | `--origin` is outside `{charter, specify, plan}` — rejected before the decisions service is ever called |
| `DECISION_MISSING_STEP_OR_SLOT` | Neither `--step-id` nor `--slot-key` was supplied |
| `DECISION_ALREADY_CLOSED` | A matching logical-key entry already exists in a terminal state |
| `DECISION_EVENT_REPAIR_FAILED` | Idempotent-open path: the missing `DecisionPointOpened` event could not be re-emitted |

---

## 17. resolve-decision (contract >= 1.4.0)

Resolve a decision with a concrete final answer.

```bash
spec-kitty orchestrator-api resolve-decision \
  --mission TEXT --decision-id TEXT --final-answer TEXT \
  [--other-answer] [--rationale TEXT] [--resolved-by TEXT] \
  --actor TEXT --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--decision-id` | TEXT | required | Decision ledger entry ID (ULID) |
| `--final-answer` | TEXT | required | The chosen answer (non-empty) |
| `--other-answer` | FLAG | off | `true` if the answer is a write-in |
| `--rationale` | TEXT | none | Explanation of the choice |
| `--resolved-by` | TEXT | falls back to `--actor` | Identity of the resolving party |
| `--actor` | TEXT | required | Identity of the resolving actor |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields:**

| Field | Type | Description |
|-------|------|--------------|
| `mission_slug` / `mission_number` / `mission_type` | string | Resolved canonical mission identity |
| `decision_id` | string | Ledger entry ID |
| `status` | string | Resulting decision status |
| `terminal_outcome` | string | Terminal outcome recorded |
| `idempotent` | bool | `true` if this call matched an already-terminal entry with the SAME outcome/payload |
| `event_lamport` | int | Lamport clock of the recorded event |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `DECISION_NOT_FOUND` | `--decision-id` is not present in the mission's ledger |
| `DECISION_TERMINAL_CONFLICT` | The decision is already terminal with a DIFFERENT outcome/payload than requested |

---

## 18. defer-decision (contract >= 1.4.0)

Defer a decision for later resolution.

```bash
spec-kitty orchestrator-api defer-decision \
  --mission TEXT --decision-id TEXT --rationale TEXT \
  [--resolved-by TEXT] --actor TEXT --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--decision-id` | TEXT | required | Decision ledger entry ID (ULID) |
| `--rationale` | TEXT | required | Explanation of why (must be non-empty) |
| `--resolved-by` | TEXT | falls back to `--actor` | Identity of the deferring party |
| `--actor` | TEXT | required | Identity of the deferring actor |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields:** same shape as `resolve-decision` (command 17) above.

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `DECISION_MISSING_STEP_OR_SLOT` | `--rationale` is empty or whitespace-only |
| `DECISION_NOT_FOUND` | `--decision-id` is not present in the mission's ledger |
| `DECISION_TERMINAL_CONFLICT` | The decision is already terminal with a DIFFERENT outcome/payload than requested |

---

## 19. cancel-decision (contract >= 1.4.0)

Cancel a decision deemed no longer relevant.

```bash
spec-kitty orchestrator-api cancel-decision \
  --mission TEXT --decision-id TEXT --rationale TEXT \
  [--resolved-by TEXT] --actor TEXT --policy TEXT
```

**Flags and data fields:** identical shape to `defer-decision` (command 18) above.

**Error codes:** identical to `defer-decision` (command 18) above.

---

## 20. answer-decision (contract >= 1.4.0, full host-CLI lifecycle parity)

Resolve a `spec-kitty next` `decision_required` moment — the run-snapshot's
pending-decision map, distinct from the `decisions/index.json` ledger the
four verbs above operate on. Matches what the real CLI invocation
`spec-kitty next --answer <value> --decision-id <id> --agent <name> --result
<success|failed|blocked>` does in one pass, not just the two underlying
engine calls.

```bash
spec-kitty orchestrator-api answer-decision \
  --mission TEXT --agent TEXT --answer TEXT --result TEXT \
  [--decision-id TEXT] --policy TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |
| `--agent` | TEXT | required | Agent/actor identity performing this call |
| `--answer` | TEXT | required | The answer value to persist for the pending decision |
| `--result` | TEXT | required | Outcome of the current issuance: `success` \| `failed` \| `blocked` (required alongside `--answer`) |
| `--decision-id` | TEXT | auto-resolved | Run-snapshot pending decision id to answer; auto-resolved when omitted and exactly one decision is pending |
| `--policy` | TEXT | required | JSON string with policy metadata |

**Data fields** (`Decision.to_dict()`, byte-identical field-for-field to `next --answer ... --json`, plus one sibling field):

| Field | Type | Description |
|-------|------|--------------|
| `kind` | string | `step` \| `decision_required` \| `blocked` \| `terminal` \| `query` |
| `agent` | string or null | Agent identity |
| `mission_slug` / `mission_number` / `mission_type` | string | Mission identity — note this is NOT the same shape as `specify`'s payload: there is no `mission_id` key here |
| `mission` | string | Mission handle as passed |
| `mission_state` | string | Current mission state |
| `timestamp` | string | ISO timestamp |
| `action` / `wp_id` / `workspace_path` / `prompt_file` / `reason` | string or null | Step-shaped fields, populated per `kind` |
| `guard_failures` | list | Guard failures, if any |
| `progress` | object or null | Progress snapshot |
| `origin` | object | Origin metadata |
| `run_id` / `step_id` / `decision_id` / `input_key` / `question` | string or null | Run/decision identifiers |
| `options` | list or null | Candidate answers, when applicable |
| `is_query` | bool | `true` when `kind == query` |
| `preview_step` | string or null | Preview of the next step |
| `answered_decision_id` | string | The `decision_id` this call persisted an answer against — this verb's own field name for the CLI's terser `answered` key. `data` carries NO `answer` echo key: the submitted value is intentionally omitted (the host already has it) |

**Error codes:**

| Code | Cause |
|------|-------|
| `POLICY_METADATA_REQUIRED` | `--policy` missing |
| `RESULT_REQUIRED` | `--result` is required alongside `--answer` |
| `INVALID_RESULT` | `--result` is not one of `success`, `failed`, `blocked` |
| `NO_PENDING_DECISION` | No pending decisions to answer |
| `AMBIGUOUS_PENDING_DECISION` | More than one pending decision and `--decision-id` was omitted |
| `DECISION_NOT_PENDING` | `--decision-id` does not match any entry in the current run's pending decisions |

**Usage notes (binding integrator guarantee):**

- This verb achieves **full host-CLI lifecycle parity**: alongside the two engine calls (persisting the answer, advancing the DAG), it also pairs the previous issuance's `started` lifecycle record, appends the `MissionNextInvoked` mission-event-log entry, and — when the resulting decision's `kind` is `step` — writes the new issuance lifecycle record. These are reached through a seam shared with the host CLI's own `next_cmd.py` (`runtime.next.next_invocation_lifecycle`), never inlined or reimplemented independently, so the two callers cannot drift apart. This is a binding operator ruling, not an implementation detail: `kitty-specs/design-phase-orchestrator-api-01M1HE6M/reviews/spec.ruling.md` (ruling on finding SPEC-FRESH2-001).
- `FR-012`'s `INVALID_ORIGIN_FLOW` guard (command 16) does NOT apply to this verb — it operates on the run-snapshot, not `decisions/index.json`, so a mission phase with no `OriginFlow` member can still have a pending decision here.

---

## 21. design-status (contract >= 1.4.0, read-only)

Query the design-phase status of a mission: current phase, next
recommended action, and any open ledger decisions blocking advancement.

```bash
spec-kitty orchestrator-api design-status --mission TEXT
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission` | TEXT | required | Mission slug |

No `--policy` is required: this is a read-only reduction, not a state
transition — it never invokes the WP-loop or `next` engines.

**Data fields:**

| Field | Type | Description |
|-------|------|--------------|
| `mission_slug` / `mission_number` / `mission_type` | string | Resolved canonical mission identity |
| `current_phase` | string | `specify` \| `plan` \| `tasks` \| `analyze` |
| `next_action` | string or null | The verb the host should call next; `null` once the design phase is complete with no open decisions |
| `open_decisions` | list | Objects with `decision_id` / `origin`, for every OPEN ledger entry regardless of which phase opened it |

**Error codes:**

| Code | Cause |
|------|-------|
| `MISSION_NOT_FOUND` | No mission with this slug exists |
| `DESIGN_STATUS_EVENT_LOG_UNREADABLE` | `status.events.jsonl` could not be read cleanly (a torn/truncated line, or a detected drift against `status.json`'s persisted work-package set) while deriving the tasks-finalized signal |

**Usage notes (binding integrator guarantee):**

- This verb **fails closed**: on a torn, truncated, or drifted event log it returns `DESIGN_STATUS_EVENT_LOG_UNREADABLE` rather than guessing and reporting a plausible-but-wrong `current_phase`/`next_action`. It is never silently reported as "not finalized." A returned `current_phase` can therefore be trusted at face value — but callers MUST handle this error explicitly rather than assume the query always succeeds for an existing mission.
- An open decision always overrides `next_action` to `resolve-decision`, regardless of the artifact-derived phase.

---

## Error Code Summary

| Error Code | Commands | Description |
|------------|----------|-------------|
| `CONTRACT_VERSION_MISMATCH` | contract-version | Provider version too old |
| `MISSION_NOT_FOUND` | mission-state, list-ready | Unknown mission slug |
| `MISSION_NOT_READY` | accept-mission | Not all WPs are approved or done |
| `WORKFLOW_EVIDENCE_REQUIRED` | accept-mission | Workflow files changed without runner proof |
| `POLICY_METADATA_REQUIRED` | start-implementation, start-review, transition | Missing or incomplete policy JSON |
| `POLICY_VALIDATION_FAILED` | start-implementation, start-review, transition | Policy JSON invalid or contains secret-like values |
| `USAGE_ERROR` | all commands | CLI usage error or missing required arguments |
| `DEPENDENCIES_NOT_SATISFIED` | start-implementation, transition | WP dependencies do not permit the requested transition |
| `HISTORY_COMMIT_FAILED` | append-history | Branch lookup or commit setup failed |
| `SAFE_COMMIT_BACKSTOP` | append-history | Safe commit refused unexpected staged paths |
| `SAFE_COMMIT_DESTINATION_NOT_FOUND` | append-history | Safe commit destination branch does not exist |
| `SAFE_COMMIT_DESTINATION_REF_SHAPE` | append-history | Safe commit destination ref is not short-form |
| `SAFE_COMMIT_EMPTY_CHANGESET` | append-history | Safe commit was called without requested paths |
| `SAFE_COMMIT_GENERIC` | append-history | Generic safe commit failure |
| `SAFE_COMMIT_HEAD_MISMATCH` | append-history | Worktree HEAD differs from destination branch |
| `SAFE_COMMIT_NOT_A_WORKTREE` | append-history | Safe commit target is not a git worktree |
| `SAFE_COMMIT_PROTECTED_BRANCH` | append-history | Safe commit refused a protected branch |
| `SAFE_COMMIT_RECOVERY_FAILED` | append-history | Safe commit created or attempted a commit but could not restore caller staging |
| `TRANSITION_REJECTED` | start-implementation, start-review, transition | Guard failure or invalid transition |
| `WP_ALREADY_CLAIMED` | start-implementation, start-review | Another actor owns the WP |
| `MISSION_ALREADY_EXISTS` | specify | Delegate mission-creation call refused a duplicate (typed `MissionAlreadyExistsError` signal, #3861) |
| `MISSION_CREATE_FAILED` | specify | Mission creation failed for a reason other than a typed duplicate signal |
| `PLAN_SETUP_FAILED` | plan | Delegate plan-scaffold call failed with no more specific typed `error_code` of its own |
| `TASKS_FINALIZE_FAILED` | tasks | Delegate finalize-tasks call failed with no more specific typed `error_code` of its own |
| `CHECK_PREREQUISITES_FAILED` | check-prerequisites | Delegate validation call failed with no more specific typed `error_code` of its own |
| `RECORD_ANALYSIS_EMPTY_BODY` | record-analysis | `--input-file`/stdin body was empty |
| `RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND` | record-analysis | `--input-file` could not be read |
| `RECORD_ANALYSIS_MALFORMED_CARRIER` | record-analysis | Submitted body carried a present-but-invalid `analysis-findings/v1` carrier |
| `RECORD_ANALYSIS_WRITE_NOT_CONFIRMED` | record-analysis | No fresh `analysis-report.md` write could be confirmed on disk after the call |
| `RECORD_ANALYSIS_VERDICT_UNRELIABLE` | record-analysis | A fresh write was confirmed but its verdict is not a trustworthy match (mismatch, or the submitted verdict was `unknown`) |
| `DIRTY_WORKTREE` | record-analysis | Pre-existing uncommitted changes block the write |
| `PLACEMENT_RESOLUTION_REQUIRED` | record-analysis | The write placement could not be resolved (fail-closed; never a silent current-branch fallback) |
| `INVALID_ORIGIN_FLOW` | open-decision | `--origin` is outside `{charter, specify, plan}` |
| `DECISION_MISSING_STEP_OR_SLOT` | open-decision, defer-decision, cancel-decision | Neither `--step-id` nor `--slot-key` supplied (open-decision); or an empty `--rationale` (defer-decision, cancel-decision) |
| `DECISION_ALREADY_CLOSED` | open-decision | A matching logical-key entry already exists in a terminal state |
| `DECISION_EVENT_REPAIR_FAILED` | open-decision | Idempotent-open path: the missing `DecisionPointOpened` event could not be re-emitted |
| `DECISION_NOT_FOUND` | resolve-decision, defer-decision, cancel-decision | `--decision-id` is not present in the mission's ledger |
| `DECISION_TERMINAL_CONFLICT` | resolve-decision, defer-decision, cancel-decision | The decision is already terminal with a DIFFERENT outcome/payload than requested |
| `RESULT_REQUIRED` | answer-decision | `--result` is required alongside `--answer` |
| `INVALID_RESULT` | answer-decision | `--result` is not one of `success`, `failed`, `blocked` |
| `NO_PENDING_DECISION` | answer-decision | No pending decisions to answer |
| `AMBIGUOUS_PENDING_DECISION` | answer-decision | More than one pending decision and `--decision-id` was omitted |
| `DECISION_NOT_PENDING` | answer-decision | `--decision-id` does not match any entry in the current run's pending decisions |
| `DECISION_OPERATION_FAILED` | open-decision, resolve-decision, defer-decision, cancel-decision | A decision-ledger operation failed for a reason without a more specific registered code |
| `DESIGN_STATUS_EVENT_LOG_UNREADABLE` | design-status | `status.events.jsonl` could not be read cleanly (torn/truncated line, or a detected drift against `status.json`) while deriving the tasks-finalized signal |
| `WP_NOT_FOUND` | resolve-workspace, start-implementation, start-review, transition, append-history | Work package ID does not exist in the mission |
| `PREFLIGHT_FAILED` | merge-mission | Preflight checks failed before merge (target-branch/git-state errors, or a `RuntimeError` from the lane-consolidation step) |
| `UNSUPPORTED_STRATEGY` | merge-mission | Requested `--strategy` is not one of `merge`, `squash`, `rebase` |
| `LANE_ALLOCATION_FAILED` | start-implementation, transition | Lane worktree allocation failed (dirty reuse, a dependency-lane consolidation conflict, or an unhonorable base) |
| `ANCESTRY_NOT_ESTABLISHED` | start-implementation, transition | The recorded planning commit or an approved dependency lane's tip is not (yet) a git ancestor of the claimed workspace's HEAD, even after self-heal re-ran the reuse-path merges |
| `SAFE_COMMIT_PATH_POLICY` | append-history | Safe commit refused to stage a path under `.worktrees/` from the primary repo root before mutating the index |
| `STATUS_READ_PATH_NOT_FOUND` | all mission-scoped commands | Coord topology with a stale/unaddressable primary surface (fail-closed read-path guard fired; carries coord/primary candidates) |

---

## Orchestrator Integration Pattern

A typical external orchestrator loop:

```bash
# 1. Verify contract
spec-kitty orchestrator-api contract-version --provider-version "1.0.0"

# 2. Query ready WPs
spec-kitty orchestrator-api list-ready --mission 017-my-mission

# 3. Start implementation for each ready WP
spec-kitty orchestrator-api start-implementation \
  --mission 017-my-mission --wp WP01 --actor "ci-bot" \
  --policy '{"orchestrator_id":"my-orch",...}'

# 4. (Agent executes the prompt_file in the worktree the orchestrator created)

# 5. Record history
spec-kitty orchestrator-api append-history \
  --mission 017-my-mission --wp WP01 --actor "ci-bot" --note "Implementation complete"

# 6. Transition to review
spec-kitty orchestrator-api transition \
  --mission 017-my-mission --wp WP01 --to for_review --actor "ci-bot" \
  --policy '{"orchestrator_id":"my-orch",...}'

# 7. (Reviewer reviews the work)

# 8. Transition to done with structured review result and terminal evidence
spec-kitty orchestrator-api transition \
  --mission 017-my-mission --wp WP01 --to done --actor "reviewer-bot" \
  --review-ref "PR #42" \
  --review-result-json '{"reviewer":"reviewer-bot","verdict":"approved","reference":"PR #42"}' \
  --evidence-json '{"review":{"reviewer":"reviewer-bot","verdict":"approved","reference":"PR #42"}}' \
  --note "Approved in PR #42"

# 9. When all WPs are approved or done, accept and merge
spec-kitty orchestrator-api accept-mission --mission 017-my-mission --actor "ci-bot"
spec-kitty orchestrator-api merge-mission --mission 017-my-mission --strategy squash --push
```
