---
title: Testing
description: Test-suite planning and tuning notes from the 3.2.x cycle — mutation testing, acceleration, the friction audit, and CI gate tuning. All retired.
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/index.md
---
# Testing

Planning artifacts for the test suite: mutation-testing findings, acceleration
remediation, the friction audit, and CI quality and coverage gate notes.

These notes follow the distil-then-retire lifecycle described in the
[plans index](../index.md): pages retire once their subject ships or is distilled.
Current testing guidance lives in [development/testing](../../development/testing/index.md)
and [CI gate mechanics](../../development/reference/ci-gate-mechanics.md). The active cycle
is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

## Live

None. Every note below belongs to closed work.

## Historical (retired)

### CI topology and gates (superseded by the modular CI, #3995)

- [CI Quality Workflow Structure](quality_check_structure.md) — the February 2026 `ci-quality.yml` layout.
- [CI Coverage Gate — Tuning Notes](ci-coverage-gate-tuning.md) — mission-062 coverage gate; per-PR coverage is now the diff-cover gate in `ci-aggregate.yml`.
- [CI job timings](ci-job-timings.md) — timings for the retired shard topology of mission `01KXBJRT`.
- [CI coverage union audit](ci-coverage-union-audit.md) — coverage evidence for the same retired topology.

### Test-suite friction and acceleration (epics #2071 and #1931 closed)

- [Test-Suite Friction Audit — "Tests as scaffold, not friction"](test-suite-friction-audit.md) — the June 2026 four-lens audit.
- [Friction Burn-Down Sequencing](friction-burn-down-sequencing.md) — found the audit's premise largely spent; its residual items have since closed.
- [QA Mission — Tidy-First Sequencing](qa-tidy-first-sequencing.md) — which degod cleanup made the test-QA mission cheaper.
- [CaaCS: test↔production change-coupling analysis](test-change-coupling-caacs.md) — git-history ranking of refactor-fragile tests.
- [Test Suite Acceleration — Final Remediation Plan](test-suite-acceleration-plan.md) — parallelization and HOME isolation, now standard practice.

### Mutation testing

- [Mutation Testing Findings (WP05)](mutation-testing-findings.md) — March 2026 baseline; see [Run mutation tests](../../development/testing/run-mutation-tests.md) for current practice.

## See also

- [Plans index](../index.md)
