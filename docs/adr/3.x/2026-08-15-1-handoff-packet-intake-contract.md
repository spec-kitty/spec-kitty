---
title: 'ADR: Own a Tool-Agnostic, Versioned, Optional Handoff-Packet Intake Contract'
description: 'Ratifies handoff-packet v1: an additive, version-gated frontmatter overlay that seeds spec-kitty intake with stable FR/AC ids from upstream tools, degrading to prose when absent.'
status: Accepted
date: '2026-08-15'
related:
- docs/contracts/handoff-packet-v1.md
doc_status: active
kind: ADR
updated: '2026-08-15T00:00:00Z'
---

# Own a Tool-Agnostic, Versioned, Optional Handoff-Packet Intake Contract

**Filename:** `2026-08-15-1-handoff-packet-intake-contract.md`

**Status:** Accepted

**Date:** 2026-08-15

**Deciders:** Maintainer

**Technical Story:** [PR #3379]

---

## Context and Problem Statement

`spec-kitty intake` today only accepts unstructured Markdown. When a brief was
authored (or exported) by an upstream requirements tool, `/spec-kitty.specify`
re-mints FR and AC ids from prose and drops the producer's native identity —
so a ticket, story, or use-case id that already existed upstream has no
traceable link to the Spec Kitty artifact born from it. Upstream requirements
tools generally do have stable ids worth preserving across that passage.

Spec Kitty should be able to accept a structured seed from any such tool
without knowing anything about that tool specifically — no ticket-key shape,
no story-id convention, no producer-specific vocabulary baked into the
schema. This ADR ratifies that PR #3379's answer to that problem is a
contract Spec Kitty owns and commits to, not a one-off parsing convenience.

## Decision Drivers

* Preserve producer-native FR/AC identity across intake instead of re-minting it.
* Never require a specific upstream tool, and never let any tool's vocabulary
  leak into the schema.
* Zero risk to the existing, already-working prose-intake path.
* Producer-controlled strings are filesystem input from an untrusted source.

## Decision

Own a **tool-agnostic, optional, versioned** intake overlay — the handoff-packet
contract at [`docs/contracts/handoff-packet-v1.md`] — bound by three invariants:

1. **Additive; degrades to prose.** A packet-less or malformed brief behaves
   exactly as today's intake. `spec-kitty intake` never fails because the
   overlay is absent or invalid — a malformed packet still ingests the file
   as a prose brief; only the structured overlay is dropped.
2. **Version-gated.** The overlay activates only on `handoff_packet: 1`.
   Unknown or future versions degrade to prose. A v2, if one is ever needed,
   ships as a parallel, additive step alongside v1 rather than replacing it.
3. **All producer strings are untrusted.** Provenance scalars are sanitised
   (`escape_for_comment`, ASCII control-character stripping, a 256-byte clip)
   before they land in `.kittify/brief-source.yaml` or any HTML/Markdown
   comment. The brief's SHA-256 hash stays computed over the raw file, not
   the parsed overlay.

The existing discovery-gate confirmation at specify step 5 is preserved
unchanged — the packet governs FR/AC id **numbering**, not whether the human
confirms discovery. `source_tool` and `source_id` remain free-form strings;
the schema encodes no producer-specific types (ticket keys, story ids, or
similar).

This intake-side **handoff packet** is a distinct artifact from the
mission-side **handoff package** — the dossier/replay export produced by
`src/specify_cli/dossier/` (mission 045,
`kitty-specs/045-mission-handoff-package-version-matrix/`). The packet seeds a
mission; the package is emitted after one. Same surface word, opposite
direction of travel — name the one meant.

## Consequences

### Positive

* Producers that emit v1 packets get stable, traceable FR/AC ids instead of
  re-minted ones, and the producer-native id survives as a recorded trace.
* Every other intake path is byte-for-byte unchanged; there is no migration
  and no schema bump for projects that never emit a packet.

### Negative and accepted trade-offs

* Spec Kitty now commits to a producer-facing contract surface it must
  version and eventually retire deliberately, rather than being free to
  reshape intake parsing at will.
* The contract is not yet registered in
  `docs/contracts/contract-registry.yaml` — that registry's `kind` vocabulary
  is currently `fallback_name` / `retired_literal` only, with no
  payload/intake-contract kind to register this record under. Adding that
  `kind` and registering this contract is a follow-up ([#3446](https://github.com/Priivacy-ai/spec-kitty/issues/3446)).

## Alternatives Considered

### Require a mandatory structured format

Rejected. Forcing every intake to be YAML-frontmatter-bearing would break the
compatibility surface this contract exists to protect: "prose is always
valid input" must remain true for every producer that never adopts the
overlay.

### Encode producer-specific vocabulary in the schema

Rejected. Modeling ticket types, story shapes, or use-case ids directly in
the frontmatter schema would couple Spec Kitty to a specific upstream tool's
domain model. `source_tool` / `source_id` stay deliberately free-form so any
producer can populate them without a schema change.

## References

* Contract: [`docs/contracts/handoff-packet-v1.md`]
* [PR #3379]

[`docs/contracts/handoff-packet-v1.md`]: ../../contracts/handoff-packet-v1.md
[PR #3379]: https://github.com/Priivacy-ai/spec-kitty/pull/3379
