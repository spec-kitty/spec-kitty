---
title: '`next` Mission Mapping Tracker'
description: 'Closed tracker for the plan and documentation mission spec-kitty next mapping gaps; both are now guarded by hard regression tests.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# `next` Mission Mapping Tracker

> **Historical (closed tracker).** Both tracked gaps are closed; kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

This directory tracks mission-specific `spec-kitty next` mapping/template gaps that are accepted temporarily.

Status rules:

1. `OPEN`: known gap is accepted short-term, guarded by `xfail(strict=True)` test.
2. `CLOSED`: full behavior implemented, `xfail` converted to normal passing test.

## Live

None. No mission-specific `next` mapping gap is currently tracked here.

## Historical (closed)

Both former strict-`xfail` tests are now ordinary regression checks in
`tests/next/test_next_command_integration.py` (`TestNextCommandKnownBlockedMissions`).
They assert that the first `next` call maps an action and never returns a `step` with a null prompt file.

1. [`plan` mission `next` mapping](issue-plan-mission-next-mapping.md) — CLOSED.
2. [`documentation` mission `next` mapping](issue-documentation-mission-next-mapping.md) — CLOSED.
