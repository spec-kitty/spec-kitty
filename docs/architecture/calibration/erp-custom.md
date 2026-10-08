---
title: 'Calibration Report: erp-custom'
description: 'Calibration report for the erp-custom (ERP integration) mission: the §4.5.1 inequality check per step against its overlay and ERP-integration fixture.'
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/maintainer.md
---
# Calibration Report: erp-custom

**Mission**: erp-custom (ERP Integration custom mission)  
**Date**: 2026-04-27  
**Overlay**: `.kittify/charter-packs/overlays/calibration-erp-custom.yaml`  
**Fixture**: `tests/fixtures/missions/erp-integration/mission.yaml`  
**Status**: No edge changes required — all steps pass §4.5.1

---

## Summary

All 7 steps of the ERP Integration custom mission pass the §4.5.1 inequality. The ERP mission reuses built-in action URNs (`action:research/gathering`, `action:software-dev/implement`, `action:software-dev/specify`, `action:software-dev/retrospect`) — the shipped graph satisfies all requirements. Transitive extras are classified as `known_irrelevant`.

## Action Mapping

| ERP step | Mapped action URN | Rationale |
|---|---|---|
| query-erp | `action:research/gathering` | Pulls data from ERP endpoint |
| lookup-provider | `action:research/gathering` | Looks up matching provider record |
| ask-user | `action:software-dev/specify` | Operator confirms export shape |
| create-js | `action:software-dev/implement` | Generates JS adapter |
| refactor-function | `action:software-dev/implement` | Refactors legacy function |
| write-report | `action:research/gathering` | Summarizes the run |
| retrospective | `action:software-dev/retrospect` | Mission retrospective marker |

---

## Step-by-Step Findings

### Step: query-erp

| Column | Value |
|---|---|
| **Step id** | query-erp |
| **Action id** | `action:research/gathering` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_037`, + 5 transitive URNs |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_037`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (transitive extras are `known_irrelevant`) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 8 URNs. After: unchanged. |

---

### Step: lookup-provider

| Column | Value |
|---|---|
| **Step id** | lookup-provider |
| **Action id** | `action:research/gathering` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | Same as query-erp (same action URN) |
| **Scope edges involved** | Same as query-erp |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 8 URNs. After: unchanged. |

---

### Step: ask-user

| Column | Value |
|---|---|
| **Step id** | ask-user |
| **Action id** | `action:software-dev/specify` |
| **Profile id** | `agent_profile:implementer-ivan` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`†, `tactic:premortem-risk-identification`†, `tactic:requirements-validation-workflow` |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 5 URNs. After: unchanged. |

---

### Step: create-js

| Column | Value |
|---|---|
| **Step id** | create-js |
| **Action id** | `action:software-dev/implement` |
| **Profile id** | `agent_profile:implementer-ivan` |
| **Resolved DRG artifact URNs** | 35 URNs (full implement surface — required + transitive refactoring/testing tactics) |
| **Scope edges involved** | `directive:DIRECTIVE_024/025/028/029/030/034`, implement-specific tactics |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (transitive extras `known_irrelevant`) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 35 URNs. After: unchanged. |

---

### Step: refactor-function

| Column | Value |
|---|---|
| **Step id** | refactor-function |
| **Action id** | `action:software-dev/implement` |
| **Profile id** | `agent_profile:implementer-ivan` |
| **Resolved DRG artifact URNs** | Same as create-js (same action URN) |
| **Scope edges involved** | Same as create-js |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 35 URNs. After: unchanged. |

---

### Step: write-report

| Column | Value |
|---|---|
| **Step id** | write-report |
| **Action id** | `action:research/gathering` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | Same as query-erp (same action URN) |
| **Scope edges involved** | Same as query-erp |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 8 URNs. After: unchanged. |

---

### Step: retrospective

| Column | Value |
|---|---|
| **Step id** | retrospective |
| **Action id** | `action:software-dev/retrospect` |
| **Profile id** | `agent_profile:retrospective-facilitator` |
| **Resolved DRG artifact URNs** | `agent_profile:retrospective-facilitator`, `directive:DIRECTIVE_003/010/018`, `styleguide:kitty-glossary-writing`, `tactic:adr-drafting-workflow`, `tactic:autonomous-operation-protocol`, `tactic:glossary-curation-interview`, `tactic:premortem-risk-identification`, `tactic:requirements-validation-workflow`, `tactic:stopping-conditions` |
| **Scope edges involved** | Full retrospect scope |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 11 URNs. After: unchanged. |
