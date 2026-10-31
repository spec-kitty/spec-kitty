---
title: Approved implementation reopen feedback
description: Preserve explicitly supplied reopen references through canonical CLI planning and actor guards.
doc_status: point_in_time
updated: '2026-10-31'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/2026-10-30-owned-charter-context.md
- docs/plans/engineering-notes/index.md
---
# Approved implementation reopen feedback

## Observed behavior and contract

An actual owned-checkout CLI call from `approved` to `in_progress` supplied a
persisted feedback file and omitted `--force`, but recorded `force: true` and a
null `review_ref`. The file had passed the existing file guard; planning dropped
its reference because this implementation reopen is outside the frozen review
rejection family.

The existing FR-015 planner contract already admits this edge without force
when its review reference reaches the canonical FSM and wire validators. It also
explicitly promotes the missing-reference backward move to a forced transition.
Both policies remain intact: supplied valid feedback now reaches those same
validators; a missing reference retains its documented forced behavior and is
never described as force-free. Missing or non-file feedback still refuses before
writes. The review-rejection predicate, review-cycle creation rules, terminal
lane rules and shared transition validators remain authoritative.

## Actor identity and proof boundary

The operational rc7 investigation also found dropped implementation profiles.
The upstream development source already contains the unified structured actor
builder. Actual CLI transitions through claim, implementation, submission,
review claim and approval confirm that the same tool with distinct explicitly
supplied profiles records independent actors. Unknown models stay null, and a
poisoned work-package frontmatter profile is ignored. Reuse this existing
implementation when preserving operational parity.

These controls use real Git owned checkouts, the canonical ownership minter,
committed planning and implementation evidence, the registered tasks CLI leaf,
and append-only event reads. Historical same-host identities are controlled
fixture input. Prior events and primary/sibling snapshots remain unchanged;
forbidden global command and skill writers must never be called. The fixture
proves forwarding, identity and transition behavior; it does not certify a real
Mission's review quality or acceptance.

## Implementation and qualification

This is a bounded repair in the existing Python CLI under its owning charter.
A private helper selects the existing approved implementation reopen separately
from rejection. The ordinary file guard supplies its validated path to the
existing transition planner. Source compilation also exposed pre-existing
constructor typing omissions in the wire probe: explicit null Mission and
summary fields match the dependency's actual defaults byte-for-byte and invent
no identity. Baseline compiler output and runtime payload parity are retained.

External receipts preserve the unchanged-source CLI failure, existing-profile
positive controls and final frozen-source results. Final checks and publication
are separate events; recording them does not edit a validated source log.

## Owner and next event

The runtime context delivery lane owns source delivery, private test resources
and joined cleanup. Preserve the published predecessor and all failed-run
receipts. Review current CI findings, operational backport compatibility and
remaining acceptance parity at the next delivery boundary or on 2026-11-01.
