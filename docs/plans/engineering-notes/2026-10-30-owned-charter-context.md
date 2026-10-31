---
title: Owned prompt charter scope repair
description: Typed scope propagation keeps prompt policy and charter context reads within the validated owned checkout.
doc_status: point_in_time
updated: '2026-10-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/2026-10-30-owned-analysis-currency.md
- docs/plans/engineering-notes/index.md
---
# Owned prompt charter scope repair

## Objective and ownership

Repair the existing prompt and charter-context read boundary for a validated
owned checkout. The isolated source builds on `45eb8735b1`; predecessor runtimes
and other owners' source remain immutable. This is a bounded Python correctness
repair in the owning CLI project.

## User experience findings

A successful owned `next` could render the primary checkout's companion charter
and policy. A legacy primary could also block an otherwise valid owned project.
The source prompt must contain the owned project's actual selected directive
intent and correct display-source path, including compact context fetches and
JSON provenance. A current analysis report alone does not establish that policy
was rendered from the correct authority.

## Decisions and provenance

Reuse the memory-safety program's typed `CharterScope` repair, supplied under
issue #146. Its exact source packet and source identities are preserved in the
external qualification receipt. The validated owned fact projects into the
existing scope type, which flows through context, configuration, renderers and
JSON collection. Ordinary callers keep canonical primary-root behavior. No
ambient resolver replacement, context variable, guard bypass or primary upgrade
is introduced.

The paired prompt tests use real Git checkouts, the canonical fact minter and a
source-pinned authored directive fixture. They check actual directive intents,
source paths, primary drift, equal-YAML/different-companion cases, scoped JSON
and invalid mission boundaries. Source compilation also identified an explicit
loader callback's new scope keyword contract; a protocol records that contract.
Default collaborators retain their original invocation when no explicit
scope is supplied, including their error/provenance behavior.

## Known limitations and qualification boundaries

The supplied combined create test expected every raw symlink claim to fail.
The canonical minter explicitly supports valid owned-checkout aliases, so that
expectation conflicts with existing tests. Preserve the original failed packet;
qualify primary, foreign and primary-alias refusals separately from valid-owned
and valid-alias success, and verify the primary remains unchanged. Do not weaken
or tighten the shared validator merely to satisfy a different startup harness.

Acceptance routing remains outside this increment. The other owner's inherited
acceptance and root-stage tests do not qualify this startup aggregate. The
external final receipt records exact test results, failed experiments and source
hashes; this document does not claim publication, upstream merge or runtime
adoption before those events occur.

## Resources and next action

The owner records private source, environment, fixture, cache and process-group
identities before qualification. Bound executions, join their descendants and
retain source and reconstruction evidence before retiring eligible resources.
The source remains a delivery obligation until reviewed publication and actual
main delivery; active consumer runtimes remain protected. Review the retained
obligations at the next source delivery or on 2026-10-31, whichever comes first.
