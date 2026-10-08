---
title: 'Calibration Report: software-dev'
description: 'Calibration report for the software-dev mission: the §4.5.1 inequality check per step, finding no edge changes required against the calibration overlay.'
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/maintainer.md
---
# Calibration Report: software-dev

**Mission**: software-dev  
**Date**: 2026-04-27  
**Overlay**: `.kittify/charter-packs/overlays/calibration-software-dev.yaml`  
**Status**: No edge changes required — all steps pass §4.5.1

---

## Summary

All 6 steps pass the §4.5.1 inequality after the overlay is applied (overlay is empty — no mutations required).  The shipped built-in DRG fragments (`packs/built-in/*.graph.yaml`) already provide complete required context for every step.  Transitive extras surfaced by `requires`/`suggests` traversal are classified as `known_irrelevant` (benign).

---

## Step-by-Step Findings

### Step: specify

| Column | Value |
|---|---|
| **Step id** | specify |
| **Action id** | `action:software-dev/specify` |
| **Profile id** | `agent_profile:planner-priti` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`†, `tactic:premortem-risk-identification`†, `tactic:requirements-validation-workflow` |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (†transitive extras are `known_irrelevant`) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 5 URNs. After: unchanged (no fix needed). |

---

### Step: plan

| Column | Value |
|---|---|
| **Step id** | plan |
| **Action id** | `action:software-dev/plan` |
| **Profile id** | `agent_profile:planner-priti` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`, `tactic:eisenhower-prioritisation`†, `tactic:premortem-risk-identification`, `tactic:problem-decomposition`, `tactic:requirements-validation-workflow`, `tactic:review-intent-and-risk-first`†, `tactic:stakeholder-alignment`† |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`, `tactic:premortem-risk-identification`, `tactic:problem-decomposition`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (†transitive extras from `tactic:adr-drafting-workflow → suggests` chain are `known_irrelevant`) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 9 URNs. After: unchanged. |

---

### Step: tasks

| Column | Value |
|---|---|
| **Step id** | tasks |
| **Action id** | `action:software-dev/tasks` |
| **Profile id** | `agent_profile:planner-priti` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `directive:DIRECTIVE_024`, `tactic:adr-drafting-workflow`, `tactic:change-apply-smallest-viable-diff`†, `tactic:code-review-incremental`†, `tactic:eisenhower-prioritisation`†, `tactic:premortem-risk-identification`†, `tactic:problem-decomposition`, `tactic:requirements-validation-workflow`, `tactic:review-intent-and-risk-first`†, `tactic:stakeholder-alignment`† |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `directive:DIRECTIVE_024`, `tactic:adr-drafting-workflow`, `tactic:problem-decomposition`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (†transitive from `DIRECTIVE_024 → requires → tactic:change-apply-smallest-viable-diff` etc.) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 12 URNs. After: unchanged. |

---

### Step: implement

| Column | Value |
|---|---|
| **Step id** | implement |
| **Action id** | `action:software-dev/implement` |
| **Profile id** | `agent_profile:implementer-ivan` |
| **Resolved DRG artifact URNs** | 35 URNs (all required + transitive refactoring tactics, styleguides, testing tactics via `DIRECTIVE_025`, `DIRECTIVE_030`, `DIRECTIVE_034`) |
| **Scope edges involved** | `directive:DIRECTIVE_024/025/028/029/030/034`, `tactic:acceptance-test-first`, `tactic:autonomous-operation-protocol`, `tactic:bdd-scenario-formulation`, `tactic:change-apply-smallest-viable-diff`, `tactic:function-over-form-testing`, `tactic:quality-gate-verification`, `tactic:stopping-conditions`, `tactic:tdd-red-green-refactor`, `toolguide:efficient-local-tooling` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (transitive refactoring tactics and styleguides are `known_irrelevant`) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 35 URNs. After: unchanged. |

---

### Step: review

| Column | Value |
|---|---|
| **Step id** | review |
| **Action id** | `action:software-dev/review` |
| **Profile id** | `agent_profile:reviewer-renata` |
| **Resolved DRG artifact URNs** | 47 URNs (rich review surface including `DIRECTIVE_001/031/032` transitively via `DIRECTIVE_031 → requires → DIRECTIVE_001`, plus refactoring/testing tactics) |
| **Scope edges involved** | `directive:DIRECTIVE_010/024/025/028/029/030/034/037`, review-specific tactics |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (transitive extras from `DIRECTIVE_025/030/034` are `known_irrelevant`) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 47 URNs. After: unchanged. |

---

### Step: retrospect

| Column | Value |
|---|---|
| **Step id** | retrospect |
| **Action id** | `action:software-dev/retrospect` |
| **Profile id** | `agent_profile:retrospective-facilitator` |
| **Resolved DRG artifact URNs** | `agent_profile:retrospective-facilitator`, `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `directive:DIRECTIVE_018`, `styleguide:kitty-glossary-writing`, `tactic:adr-drafting-workflow`, `tactic:autonomous-operation-protocol`, `tactic:glossary-curation-interview`, `tactic:premortem-risk-identification`, `tactic:requirements-validation-workflow`, `tactic:stopping-conditions` |
| **Scope edges involved** | `agent_profile:retrospective-facilitator`, `directive:DIRECTIVE_003/010/018`, `styleguide:kitty-glossary-writing`, `tactic:adr-drafting-workflow`, `tactic:autonomous-operation-protocol`, `tactic:glossary-curation-interview`, `tactic:requirements-validation-workflow`, `tactic:stopping-conditions` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (rich retrospect scope is appropriate) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 11 URNs. After: unchanged. |
