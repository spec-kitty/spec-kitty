---
title: 'Tracking Issue: `plan` Mission `next` Mapping'
description: Closed tracking issue for the plan mission's spec-kitty next mapping/template gap, owned by the spec-kitty team.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# Tracking Issue: `plan` Mission `next` Mapping

> **Historical (closed).** The gap is closed and the guard test is no longer `xfail`; kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

Status: CLOSED (verified 2026-09-30: `test_plan_mission_should_return_runnable_step_when_mapped` in `tests/next/test_next_command_integration.py` is a hard regression check, not `xfail`)
Owner: spec-kitty team
Created: 2026-02-17

## Problem

`spec-kitty next` can return `blocked` for `plan` mission at initial state `goals` because state-to-action mapping and template coverage are incomplete.

## Desired Behavior

For a mission of type `plan`, first `next` call returns:

1. `kind=step`
2. non-null `action`
3. non-null prompt context/output path

## Acceptance Criteria

1. `plan` mission initial and subsequent states map deterministically to supported `next` actions.
2. Command template resolution succeeds for mapped actions without fallback ambiguity.
3. Existing strict `xfail` integration test is converted to a normal passing test.
4. This file status is changed to `CLOSED` in the same PR.
