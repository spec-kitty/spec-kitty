---
title: 'Calibration Report: research'
description: 'Calibration report for the research mission: the §4.5.1 inequality check per step, finding no edge changes required against the calibration overlay.'
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/maintainer.md
---
# Calibration Report: research

**Mission**: research  
**Date**: 2026-04-27  
**Overlay**: `.kittify/charter-packs/overlays/calibration-research.yaml`  
**Status**: No edge changes required — all steps pass §4.5.1

---

## Summary

All 6 steps pass the §4.5.1 inequality. The shipped built-in DRG fragments (`packs/built-in/*.graph.yaml`) already provide the required context for every step. Transitive extras surfaced via `DIRECTIVE_003 → requires → tactic:adr-drafting-workflow` and `DIRECTIVE_037 → suggests → tactic:acceptance-test-first / atdd-adversarial-acceptance / usage-examples-sync` are classified as `known_irrelevant`.

---

## Step-by-Step Findings

### Step: scoping

| Column | Value |
|---|---|
| **Step id** | scoping |
| **Action id** | `action:research/scoping` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`†, `tactic:premortem-risk-identification`, `tactic:requirements-validation-workflow` |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:premortem-risk-identification`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 5 URNs. After: unchanged. |

---

### Step: methodology

| Column | Value |
|---|---|
| **Step id** | methodology |
| **Action id** | `action:research/methodology` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`, `tactic:premortem-risk-identification`†, `tactic:requirements-validation-workflow` |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 5 URNs. After: unchanged. |

---

### Step: gathering

| Column | Value |
|---|---|
| **Step id** | gathering |
| **Action id** | `action:research/gathering` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_037`, `tactic:acceptance-test-first`†, `tactic:adr-drafting-workflow`†, `tactic:atdd-adversarial-acceptance`†, `tactic:premortem-risk-identification`†, `tactic:requirements-validation-workflow`, `tactic:usage-examples-sync`† |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_037`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none (†transitive from `DIRECTIVE_037 → suggests` chain) |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 8 URNs. After: unchanged. |

---

### Step: synthesis

| Column | Value |
|---|---|
| **Step id** | synthesis |
| **Action id** | `action:research/synthesis` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:adr-drafting-workflow`†, `tactic:premortem-risk-identification`, `tactic:requirements-validation-workflow` |
| **Scope edges involved** | `directive:DIRECTIVE_003`, `directive:DIRECTIVE_010`, `tactic:premortem-risk-identification`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 5 URNs. After: unchanged. |

---

### Step: output

| Column | Value |
|---|---|
| **Step id** | output |
| **Action id** | `action:research/output` |
| **Profile id** | `agent_profile:researcher-robbie` |
| **Resolved DRG artifact URNs** | `directive:DIRECTIVE_010`, `directive:DIRECTIVE_037`, `tactic:acceptance-test-first`†, `tactic:atdd-adversarial-acceptance`†, `tactic:requirements-validation-workflow`, `tactic:usage-examples-sync`† |
| **Scope edges involved** | `directive:DIRECTIVE_010`, `directive:DIRECTIVE_037`, `tactic:requirements-validation-workflow` |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 6 URNs. After: unchanged. |

---

### Step: retrospect

| Column | Value |
|---|---|
| **Step id** | retrospect |
| **Action id** | `action:research/retrospect` |
| **Profile id** | `agent_profile:retrospective-facilitator` |
| **Resolved DRG artifact URNs** | `agent_profile:retrospective-facilitator`, `directive:DIRECTIVE_003/010/018`, `styleguide:kitty-glossary-writing`, `tactic:adr-drafting-workflow`, `tactic:autonomous-operation-protocol`, `tactic:glossary-curation-interview`, `tactic:premortem-risk-identification`, `tactic:requirements-validation-workflow`, `tactic:stopping-conditions` |
| **Scope edges involved** | Full retrospect scope (all the above are direct `scope` edges added by WP01) |
| **Missing context** | none |
| **Irrelevant / too-broad context** | none |
| **Recommended DRG edge changes** | none |
| **Before/after evidence** | Before: 11 URNs. After: unchanged. |
