---
title: 'Tracking Issue: `documentation` Mission `next` Mapping'
description: Closed tracking issue for the documentation mission's spec-kitty next mapping/template gap, owned by the spec-kitty team.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# Tracking Issue: `documentation` Mission `next` Mapping

> **Historical (closed).** The gap is closed and the guard test is no longer `xfail`; kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

Status: CLOSED (verified 2026-09-30: `test_documentation_mission_should_return_runnable_step_when_mapped` in `tests/next/test_next_command_integration.py` is a hard regression check, not `xfail`)
Owner: spec-kitty team
Created: 2026-02-17

## Problem

`documentation` mission does not currently yield a usable `next` step path and can terminate early due to missing state-machine/template parity in the `next` decision path.

## Desired Behavior

For a mission of type `documentation`, first `next` call returns:

1. `kind=step`
2. non-null `action`
3. non-null prompt context/output path

## Acceptance Criteria

1. `documentation` mission has explicit `next`-compatible state/action mapping.
2. Required command templates exist and resolve for mapped actions.
3. Existing strict `xfail` integration test is converted to a normal passing test.
4. This file status is changed to `CLOSED` in the same PR.
