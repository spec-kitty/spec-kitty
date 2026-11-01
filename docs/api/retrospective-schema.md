---
title: Retrospective Schema and Events Reference
description: retrospective.yaml field schema, proposal kinds, retrospective status events, and synthesizer exit codes.
doc_status: active
updated: '2026-10-31'
---
# Retrospective Schema and Events Reference

This reference documents the `retrospective.yaml` schema, proposal types, retrospective status
events, and synthesizer exit codes. For how to use the retrospective loop, see
[How to Use the Retrospective Learning Loop](../guides/how-to/governance/use-retrospective-learning.md).

---

## retrospective.yaml schema

Retrospective records are stored at:
```
.kittify/missions/<mission_id>/retrospective.yaml
```

The file is keyed by canonical mission ULID, not display number. The schema is implemented by
`specify_cli.retrospective.schema.RetrospectiveRecord`.

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | Yes | Literal `"1"` |
| `mission` | object | Yes | Mission identity: `mission_id`, `mid8`, `mission_slug`, `mission_type`, timestamps |
| `mode` | object | Yes | Retrospective mode: `autonomous` or `human_in_command`, plus source signal |
| `status` | string | Yes | Persisted values: `completed`, `skipped`, or `failed`. `pending` exists in the model but the writer refuses to persist it. |
| `started_at` | ISO 8601 timestamp | Yes | When retrospective handling started |
| `completed_at` | ISO 8601 timestamp | Conditional | Required when `status: completed` |
| `actor` | object | Yes | Actor that authored the record |
| `helped` | list[Finding] | No | Artifacts, directives, tactics, tests, or context that helped |
| `not_helpful` | list[Finding] | No | Targets flagged as not helpful during the mission |
| `gaps` | list[Finding] | No | Governance or context gaps identified during the mission |
| `proposals` | list[Proposal] | No | Structured change proposals (see Proposal kinds below) |
| `provenance` | object | Yes | Record author, runtime version, write timestamp, schema version |
| `skip_reason` | string | Conditional | Required when `status: skipped` |
| `failure` | object | Conditional | Required when `status: failed` |
| `successor_mission_id` | ULID string | No | Follow-up mission identity when one is created |

### Finding shape

`helped`, `not_helpful`, and `gaps` entries share the same shape:

| Field | Type | Description |
|---|---|---|
| `id` | string | Finding identifier unique within the record |
| `target.kind` | string | One of `doctrine_directive`, `doctrine_tactic`, `doctrine_procedure`, `drg_edge`, `drg_node`, `glossary_term`, `prompt_template`, `test`, `context_artifact` |
| `target.urn` | string | Target URN |
| `note` | string | Human-readable note, max 2000 characters |
| `provenance.source_mission_id` | ULID string | Mission that produced the evidence |
| `provenance.evidence_event_ids` | list[ULID] | Event IDs that support the finding |
| `provenance.actor` | object | Actor that captured the finding |
| `provenance.captured_at` | timestamp | Capture timestamp |

---

### Generator-shape records (`retrospect create`)

`spec-kitty retrospect create` (and `backfill`) write the **generator record shape** read by
`specify_cli.retrospective.reader.read_gen_record`; its original contract is the archived
`kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json`,
which is a frozen historical record and is not edited (the `kitty-specs/` archive root is
byte-preserved). The live machine authority for the optional `payload` added in this release is the
discriminated `ProposalPayload` union in `src/specify_cli/retrospective/schema.py`. The shape differs
from the nested schema above in two ways that matter to `synthesize`:

| | Nested record | Generator record |
|---|---|---|
| `proposals[].id` | ULID | `p-001`, `p-002`, … |
| `proposals[].action` | `kind` + discriminated `payload` | free-text `suggested_action` (+ optional `payload`) |

A generator-shape proposal may therefore carry an **optional `payload`** block, validated against
the same `ProposalPayload` union `synthesize` applies — there is no second payload schema. When it
does, `synthesize` translates the proposal into a nested proposal (a derived ULID id, always `pending`:
`auto_applicable` is a hand-editable flag, not an accept decision). Select it with
`--proposal-id`; it is never part of the default batch. A proposal without a payload is not plannable; `retrospect create` writes
none of its own, and grading findings into payloads is tracked in
[#3947](https://github.com/spec-kitty/spec-kitty/issues/3947).

Every `synthesize` run on a generator-shape record adds a top-level `diagnostics` object to the
JSON envelope (and a matching warning on the Rich surface):

```json
"diagnostics": {
  "record_schema": "generator",
  "findings": {"helped": 0, "not_helpful": 19, "gaps": 2, "proposals": 0},
  "proposals_translated": 0,
  "proposals_planned": 0,
  "untranslatable": [],
  "next_action": "This retrospective uses the generator record schema and carries no proposals, …"
}
```

`untranslatable` names every proposal that could not be translated, with the reason. Nested-schema
records never carry the block, so their envelopes are unchanged.

---

## Proposal kinds

Each proposal in the `proposals` list has `id`, `kind`, `payload`, `rationale`, `state`, and
`provenance`. Proposal IDs and evidence event IDs are ULIDs. `state.status` is one of `pending`,
`accepted`, `rejected`, `applied`, or `superseded`.

The synthesizer applies the **effective batch**: accepted proposal IDs plus every
`flag_not_helpful` proposal. `flag_not_helpful` is auto-included in that batch, but no proposal
mutates project state unless the operator passes `--apply`.

### add_glossary_term

Add a new term to the project glossary.

| Field | Required | Description |
|---|---|---|
| `payload.kind` | Yes | `add_glossary_term` |
| `payload.term_key` | Yes | Safe term key, e.g. `lifecycle-terminus` |
| `payload.definition` | Yes | Human-readable definition |
| `payload.definition_hash` | Yes | Hash of the proposed definition |
| `payload.related_terms` | No | Related term keys |

### update_glossary_term

Update an existing glossary term's definition or scope.

| Field | Required | Description |
|---|---|---|
| `payload.kind` | Yes | `update_glossary_term` |
| `payload.term_key` | Yes | Existing term key to update |
| `payload.definition` | Yes | New definition |
| `payload.definition_hash` | Yes | Hash of the proposed definition |
| `payload.related_terms` | No | Related term keys |

### flag_not_helpful

Flag a DRG or doctrine artifact as not helpful. This proposal kind is auto-included in the
effective apply batch, but it still writes only when `--apply` is used.

| Field | Required | Description |
|---|---|---|
| `payload.kind` | Yes | `flag_not_helpful` |
| `payload.target.kind` | Yes | Target kind |
| `payload.target.urn` | Yes | Target URN |

### add_edge

Add a relationship in the project-local DRG overlay.

| Field | Required | Description |
|---|---|---|
| `payload.kind` | Yes | `add_edge` |
| `payload.edge.from_node` | Yes | Source node URN |
| `payload.edge.to_node` | Yes | Target node URN |
| `payload.edge.kind` | Yes | Edge kind |

The schema also defines `remove_edge` for compatibility, but the current apply path does not
provide an operator-facing apply handler for it.

### rewire_edge

Replace one edge with another.

| Field | Required | Description |
|---|---|---|
| `payload.kind` | Yes | `rewire_edge` |
| `payload.edge_old` | Yes | Existing edge object |
| `payload.edge_new` | Yes | Replacement edge object |

### synthesize_directive / synthesize_tactic / synthesize_procedure

Create or update project-local doctrine artifacts.

| Field | Required | Description |
|---|---|---|
| `payload.kind` | Yes | One of the three `synthesize_*` kinds |
| `payload.artifact_id` | Yes | Safe artifact identifier |
| `payload.body` | Yes | Artifact body |
| `payload.body_hash` | Yes | Hash of the body |
| `payload.scope.actions` | No | Action scope list |
| `payload.scope.profiles` | No | Profile scope list |

### Synthesizer acceptance criteria

The synthesizer accepts a proposal when:
- All required fields are present and valid
- No conflicting proposal exists in the same batch (same target with different values)
- The referenced artifacts (evidence event IDs) still resolve in the event log

The synthesizer rejects a proposal when:
- Required fields are missing
- Referenced evidence event IDs no longer resolve in the source mission event log
- The term key or artifact ID is malformed
- A conflicting proposal exists (fail-closed: the entire conflicting set is rejected)

---

## Retrospective status events

Retrospective lifecycle events are written to `kitty-specs/<slug>/status.events.jsonl` alongside
other mission lifecycle events. Filter by event name prefix `retrospective.` to isolate them.

| Event name | When emitted | Description |
|---|---|---|
| `retrospective.requested` | At mission terminus | The runtime requested a retrospective |
| `retrospective.started` | Facilitator dispatched | The retrospective facilitator began execution |
| `retrospective.proposal.generated` | Per proposal | One event per generated proposal (×N) |
| `retrospective.completed` | Facilitator finished | The retrospective completed successfully |
| `retrospective.skipped` | Operator skipped | The operator explicitly skipped (HiC mode only) |
| `retrospective.failed` | Facilitator failed | The facilitator encountered an error |
| `retrospective.proposal.applied` | Per applied proposal | One event per applied proposal (×N) |
| `retrospective.proposal.rejected` | Per rejected proposal | One event per proposal rejected during apply |

The `retrospective.skipped` event and the corresponding `status: skipped` in the YAML record are
both required. Neither alone is sufficient to record a valid skip.

---

## Synthesizer exit codes

`spec-kitty agent retrospect synthesize` uses the following exit codes:

| Exit code | Meaning | Action required |
|---|---|---|
| 0 | Success — dry-run complete (no changes, including an empty generator-shape batch, which is reported through `diagnostics`) or proposals applied successfully | None |
| 1 | Invalid project root, unresolvable mission handle, or other command error | Fix invocation/project state |
| 2 | I/O error reading retrospective data | Inspect filesystem permissions and paths |
| 3 | Retrospective record missing or malformed | Create or repair `.kittify/missions/<mission_id>/retrospective.yaml` |
| 4 | Conflicts present during `--apply` | Resolve conflicts before applying |
| 5 | Stale evidence or invalid payload rejection during `--apply` | Refresh evidence or fix proposal payloads |

The `--apply` flag is required for any mutations. Omitting `--apply` always exits 0 on a valid
dry-run regardless of proposal count or detected conflicts.

For the current exit code list, run:
```bash
uv run spec-kitty agent retrospect synthesize --help
```

---

## See Also

- [How to Use the Retrospective Learning Loop](../guides/how-to/governance/use-retrospective-learning.md)
- [Understanding the Retrospective Learning Loop](../architecture/retrospective-learning-loop.md)
