---
title: Handoff Packet v1
description: Tool-agnostic optional YAML-frontmatter contract for seeding a Spec Kitty mission from an upstream requirements tool.
doc_status: durable
updated: '2026-08-13'
related:
- docs/api/agent-plan-artifacts.md
- docs/contracts/README.md
---
# Handoff Packet v1

A **handoff packet** is a single Markdown file that any upstream requirements
producer can emit so `spec-kitty intake` can seed `/spec-kitty.specify`
without the agent re-inventing requirement identities.

The prose body is the compatibility surface: today's unmodified
`spec-kitty intake` already accepts any Markdown file. Optional YAML
frontmatter is what preserves identity across the passage.

This intake-side **handoff packet** (input to `spec-kitty intake`, this
contract) is a distinct artifact from the mission-side **handoff
package** (the dossier/replay export produced from `src/specify_cli/dossier/`,
mission 045) — the former seeds a mission, the latter is emitted after one.

## Design rules

1. **Frontmatter is optional and additive.** A packet-less Markdown brief
   behaves exactly as today's intake. Spec Kitty never requires this schema
   to ingest a plan.
2. **No producer vocabulary in the schema.** `source_tool` is a free-form
   string. Do not encode producer-specific types (ticket keys, story ids,
   use-case ids, or similar) into the field names.
3. **Version-gated on `handoff_packet: 1`.** Unknown versions degrade to
   prose intake rather than failing the command.
4. **All strings are untrusted.** Producers and Spec Kitty must treat every
   scalar as operator-controlled filesystem data. Spec Kitty sanitises
   provenance fields with `escape_for_comment` before they land in
   `.kittify/brief-source.yaml` or HTML comments.

## Degradation rules

| Input | Intake behaviour |
|-------|------------------|
| Markdown with no `---` frontmatter | Prose intake (today's path) |
| Frontmatter present, no `handoff_packet` key | Prose intake |
| `handoff_packet` present but not the integer `1` | Prose intake (unknown version) |
| Frontmatter YAML that does not parse | Prose intake |
| `handoff_packet: 1` with a non-list `requirements` | Prose intake |
| `handoff_packet: 1` with a malformed `acceptance_criteria` item (missing/empty `id` or `statement`) | Prose intake |
| `handoff_packet: 1` with a malformed `constraints` item (missing/empty `id`) | Prose intake |
| `handoff_packet: 1` with a valid `requirements` list | Structured packet; FR/AC IDs adopted verbatim |

Intake itself never exits non-zero because a packet is malformed. The file
is still ingested as a brief; only the structured overlay is dropped.

## Frontmatter schema (v1)

    ---
    handoff_packet: 1                  # required integer; only 1 is understood
    source_tool: example-tool          # free-form producer name
    source_tool_version: "1.0.0"       # optional
    source_mission: widget-booking
    source_ref: 0123456789abcdef0123456789abcdef01234567
    source_url: https://example.invalid/items/widget-booking
    generated_at: "2026-08-13T10:00:00Z"
    requirements:
      - id: FR-001                     # adopted verbatim into spec.md
        statement: "Operator can book a widget against an open slot."
        source_id: TKT-1042            # producer-native identity; recorded as a trace
        acceptance_criteria:
          - id: AC-001
            statement: "An open slot accepts a widget booking."
            source_id: AC-001
    constraints:
      - id: C-001
        statement: "Must remain compatible with the existing booking API."
        source_id: EXT-003
    ---

    # Human-readable rendering of the same content

### Field notes

| Field | Required when `handoff_packet: 1` | Notes |
|-------|-----------------------------------|-------|
| `handoff_packet` | yes | Integer `1` only |
| `requirements` | yes | List, may be empty |
| `requirements[].id` | yes | Spec Kitty FR id; do not renumber on ingest |
| `requirements[].statement` | yes | One sentence; not Gherkin |
| `requirements[].source_id` | no | Producer-native id (ticket, item, or similar) |
| `requirements[].acceptance_criteria` | no | List; when present, every item's `id` and `statement` are validated (non-empty strings) — a malformed item degrades the whole packet to prose, it is not silently dropped or miscounted |
| `constraints` | no | List of `C-###` items; every item's `id` is validated (non-empty string) — a malformed item degrades the whole packet to prose |
| `source_tool` / `source_mission` / `source_ref` | no | Copied into `brief-source.yaml` |

Gherkin, sequencing, and Definition of Done belong in the **Markdown body**,
not in `requirements[].statement`.

## Security expectations

- Strip ASCII control characters (except tab) from provenance scalars.
- Neutralise `-->` and `*/` before embedding strings in HTML/Markdown comments.
- Clip provenance scalars to 256 UTF-8 bytes.
- YAML dump must quote strings so a statement cannot inject a second
  document boundary or a crafted `handoff_packet` key.
- Packet size is still bounded by `intake.max_brief_bytes` (default 5 MB).

## Discovery

`spec-kitty intake --auto` scans `.handoff/*.md` at the project root in
addition to harness plan directories. Producers that cannot write that
directory can pass an explicit path:

    spec-kitty intake .handoff/widget-booking.md

## Worked example

One upstream item produces one packet. Each producer-native work item
becomes one `FR-###`; each acceptance-criterion id is preserved; Gherkin
scenarios render under **Definition of Done** in the body.

    ---
    handoff_packet: 1
    source_tool: example-tool
    source_tool_version: "1.0.0"
    source_mission: widget-booking
    source_ref: 0123456789abcdef0123456789abcdef01234567
    generated_at: "2026-08-13T00:00:00.000Z"
    requirements:
      - id: FR-001
        statement: "Book a widget against an open slot."
        source_id: TKT-1042
        acceptance_criteria:
          - id: AC-001
            statement: "An open slot accepts a widget booking."
            source_id: AC-001
    constraints:
      - id: C-001
        statement: "Bookings must not overlap an existing reservation."
        source_id: EXT-003
    ---

    # widget-booking

    ## Objective

    Book widgets.

    ## Requirements

    ### FR-001 — Book a widget against an open slot.

    - Source: `TKT-1042`
    - `AC-001`: An open slot accepts a widget booking.

    ## Constraints

    - `C-001` (source `EXT-003`): Bookings must not overlap an existing reservation.

    ## Sequencing

    - `TKT-1042` has no blockers.

    ## Definition of Done

    ### TKT-1042 / TC-001

        Given an open slot
        When the operator books a widget
        Then the slot is reserved
