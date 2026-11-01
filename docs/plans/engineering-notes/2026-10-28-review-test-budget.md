---
title: Review test budget repair
description: Implementation decisions, validation evidence and remaining release obligations for the review test budget repair.
doc_status: draft
updated: '2026-10-28T00:00:00Z'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/configuration/review-test-budget.md
kind: Planning
---
# Review test budget repair

## Objective and owner

Independent repair lane `issue-6746-review-test-budget`, owned by the Crucible fleet
program's Spec Kitty blocker agent. Based on upstream `6a3e5cde11516298dc33cc97cfd91b7673240177`.
Addresses upstream issue #6746, the configurable-budget portion related to broader issue #3046.

## UX findings

A complete downstream Zig aggregate naturally took 801.570 seconds before returning
six real test failures. The review framework's hardcoded 300 seconds for each leg
prevented either baseline or candidate from finishing. Its existing command/scope
extensions do not provide a supported execution-budget override. Detached execution
or narrowing the required test scope would erase evidence.

## Decisions

Use one reviewed project setting for both legs, retain the 300-second default and
independent lock deadline, and reject malformed declarations before execution.
Record the actual budget in baseline receipts and recapture when it changes;
failed recapture cannot resurrect a stale clean receipt. Explicit receipt budgets use
the same strict validator, so malformed JSON such as boolean `true` cannot equal
a legitimate one-second budget. Absent legacy fields retain the known historical 300. Existing process-group
cleanup, oversized-scope classification and failure policy remain authoritative.
No dependencies, model settings, providers, cloud services or host installations change.

## Validation and outcomes

The initial acceptance test was committed before implementation. It observed actual
baseline and candidate runners both receiving 300 instead of the declared 1200,
and a longer command escaping the declared one-second budget. The first repair
passed both tests. The affected package and three transition suites then passed
689 tests, with 11 skipped, in 160.99 seconds. A subsequent cache-provenance increment
passed 70 focused tests, with one skipped, in 50.48 seconds. Final expanded validation
is recorded externally against frozen candidate bytes before publication.

Independent review identified an owned-checkout authority mismatch: lazy baseline
capture still resolved command and budget from the primary repository. Its red
regression was committed before the correction. The helper now receives the
validated owned fact, resolves both command and budget from its owned root, and
uses the existing owned placement and commit seam for the receipt. Same-fixture
actual child commands and receipt commits prove the owned branch advances while
the primary HEAD and primary command remain untouched, including an invalid
primary budget paired with a valid owned budget. Invalid owned settings refuse
before capture rather than borrowing a permissive primary setting.

## Known limitations and delivery

The source checkout identifies itself as unreleased 4.0.0rc8; the newest published,
non-yanked package at admission is 4.0.0rc7. Source validation is not installed
runtime adoption. Upstream merge and package publication require the owning
maintainers; this agent has read-only upstream repository access. Issue assignment
was denied, so the existing issue remains unassigned. A separate project-layer
charter consistency defect remains outside this repair.

## Resource custody and cleanup

The independent source clone shares its primary's object store; preserve that store
until this useful lane closes. A private locked development environment and owned
pytest caches support validation without changing shared installs. Test subprocesses
use existing group cleanup and joined test completion. External receipts retain
runtime identity, red/green output, candidate hashes, measured sizes and retained
resource obligations. No shared cache or other owner's checkout is pruned.

## CI feedback and corrective scope

PR #6747's first CI run found three documentation failures and one owned-checkout
fixture failure despite the earlier local passes. The exact four cases were
reproduced on the published source before this correction. Preserve those failed
receipts; they do not qualify this amended candidate.

The dated implementation record now lives in the existing engineering-notes
section with required metadata. The retrieval index is regenerated using its
canonical generator; structural validators remain unchanged. The owned fixture
now supplies the selected repository root used by the real move-task state and
checks actual receipt and budget selection against a distinct primary root.
No production fallback or weakened authority check is added. Changed-input checks
and independent review remain mandatory; upstream release and installed runtime
adoption are still separate obligations.
