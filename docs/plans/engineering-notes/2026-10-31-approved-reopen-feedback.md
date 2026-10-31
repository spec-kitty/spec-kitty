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

## Development version and validation configuration

This change stays in the already-open, unreleased `4.0.0rc8` cycle. The
[release checklist](../../../RELEASE_CHECKLIST.md#8-open-the-next-development-cycle) opens the next
version once after a release tag. Maintainer commit
[`3a1380697f`](https://github.com/spec-kitty/spec-kitty/commit/3a1380697f584aac52db9cc73590ca7b16ea50e9)
explicitly reverted a second premature development bump while retaining its
consumer changelog entry. This repair adds consumer entries without skipping
the current candidate cycle; it does not authorize a release or tag.

The external validation controller initially inherited an outer pytest
`--basetemp` through `PYTEST_ADDOPTS` and lacked the selected interpreter's bin
directory on `PATH`. Two unmodified agent tests failed on both the frozen
candidate and its untouched predecessor: a real nested pytest rejected its
ancestor temporary directory, and a Git hook could not find `python`.
Correcting only the controller environment makes both controls pass on both
sources. The original failed receipts remain historical evidence. Final
qualification uses an explicit outer temporary-directory argument, no inherited
pytest options and the pinned runtime's bin directory first on `PATH`; no
product guards, test assertions or timeouts were changed for these failures.

## Golden refusal fixture and guard coverage

The historical protected-recreate golden row exercises the live-prior refusal
before a second identity is minted. Its former check that creation and the
subsequent repository snapshots all fit inside a 1,024 ms identifier bucket was
unrelated to that refusal. Native observation matched the unchanged golden
pre-state, outcome and post-state exactly. The row keeps its real public calls,
refusal and snapshots, with the irrelevant prediction setup removed. The
branch-collision row retains its original clock proof, attempts and bounds.

A separate public-path fault detector fails if the live-prior refusal requests
another identity. A distinct protected-recreation control explicitly admits the
duplicate with documented `allow_duplicate=True` and uses the existing private
`_mission_id` test seam to reach the later scaffold guard. It checks the protected overwrite refusal and
the full repository state. Compiling a mutation that removes that actual guard
makes the control fail with `MISSION_BRANCH_EXISTS` instead of
`MISSION_ALREADY_EXISTS`; the earlier duplicate guard cannot mask it. Production
guards, golden JSON, normalization and timing budgets remain unchanged.

## Timing diagnosis and limits

An earlier native hook sample added 109.9 ms at p95 against its existing 50 ms
budget. The unchanged canonical test subsequently passed on both the untouched
predecessor and this production source, with actual installed hook bodies,
Git binary hashes and recorded lane-tip effects verified after the measured
calls. The hook runs shell and native Git commands. Passing numeric p95 values
are unknown because the canonical test does not expose them. The earlier
failure remains an observed sample without a demonstrated cause; no performance
fix or host-wide quiescence is claimed. Final receipts retain the actual sample
contexts separately.

Paired import graphs also showed the public activation API already loaded on the
predecessor. They did not support an added eager graph from this repair, so the
reviewed production import boundary stays unchanged.

## Owner and next event

The runtime context delivery lane owns source delivery, private test resources
and joined cleanup. Preserve the published predecessor and all failed-run
receipts. Review current CI findings, operational backport compatibility and
remaining acceptance parity at the next delivery boundary or on 2026-11-01.
