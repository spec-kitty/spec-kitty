---
title: Owned analysis currency repair
description: Root-custody decisions and qualification scope for owned analysis recording and freshness checks.
doc_status: point_in_time
updated: '2026-10-30'
audience: docs/context/audience/internal/maintainer.md
---
# Owned analysis currency repair

## Objective and ownership

Bounded correctness repair under the Subsequent framework-facades semantic
conversion mission. The baseline is the isolated patched rc7 source `a8e8435517`;
active predecessor sources and runtimes remain immutable.

## User experience findings

A current report in a validated owned checkout was rejected because `next` read
its owned report location but relativized its planning inputs against the repository
root checkout. A fresh normal recorder cannot repair that verifier mismatch.

The explicit owned context also governs read-only charter inputs: the owned-checkout
lifecycle contract consumes the validated fact for all owned reads, while charter
authoring remains repository-root-only. The older non-owned canonical-charter
behavior remains the default. Owned analysis now records and checks its local
charter explicitly; changing that charter must invalidate the report.

## Decisions and provenance

Reuse the independently reproduced issue #146 analysis repair from the memory-safety
program: select the validated owned freshness root and thread an explicit charter
root through the canonical renderer, writer and checker. CLI callers supply it only
after canonical ownership validation. No report is manually rebound, no guard is
disabled, and no active primary checkout is upgraded. Report-only transactional
analysis is outside this qualification.

This remains Python as required by the owning CLI project's charter, and repairs
existing behavior rather than introducing a new runtime language or feature.

## Qualification and known limitations

Native regression controls cover unchanged reports, changed material, invalid
ownership, canonical non-owned governance, divergent owned governance, missing or
escaped charter inputs and the normal recorder. Existing ownership/Git-call and
non-owned acceptance tests remain required. External immutable receipts carry exact
source, executable and test identities without changing a validated candidate.

An attempted six-module analysis/acceptance aggregate did not qualify: inherited
root-startup-only assertions target a different admission stage, and an actual
acceptance invalid-claim control failed before its duplicate-option assertion.
Those acceptance changes are excluded. Preserve the exact source patch and failed
receipts for a separate canonical-CLI investigation; do not call the aggregate green.
The owned-prompt composition path may require the separately owned context repair.
Upstream source PR publication, operator merge and runtime adoption are distinct.

Read-only real-mission queries correctly classify both existing Subsequent and
Polyglot reports as stale on their owned compiled charter inputs. Their older
reports recorded the repository-root charter digest. Fresh independent analysis
against owned governance, followed by the normal official recorder, is required;
rebinding the old metadata would not establish a current analysis.
