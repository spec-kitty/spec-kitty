---
title: '[Short descriptive title]'
description: 'The ADR authoring template for Spec Kitty: the filename convention, status/date/decider header, and section structure every architecture decision record follows.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# [Short descriptive title]

**Filename:** `YYYY-MM-DD-N-descriptive-title-with-dashes.md` (where N is 1, 2, 3... for that day)

**Status:** [Proposed | Accepted | Deprecated | Superseded]

**Date:** [YYYY-MM-DD]

**Deciders:** [List of people involved in decision]

**Technical Story:** [Optional: Link to ticket/issue]

---

## Context and Problem Statement

[Describe the context and problem statement clearly. What architectural challenge are we facing? Why does this decision matter? Include relevant background that helps understand the situation.]

## Decision Drivers

[List the key factors that influenced this decision]

* [Driver 1]
* [Driver 2]
* [Driver 3, etc.]

## Considered Options

* [Option 1]
* [Option 2]
* [Option 3, etc.]

## Decision Outcome

**Chosen option:** "[Option X]", because [justification].

### Consequences

#### Positive

* [Positive consequence 1]
* [Positive consequence 2, etc.]

#### Negative

* [Negative consequence 1]
* [Negative consequence 2, etc.]

#### Neutral

* [Neutral consequence 1, etc.]

### Confirmation

[How will we know this decision was correct? What metrics or signals will validate it? What's our confidence level in this decision?]

## Pros and Cons of the Options

### [Option 1]

[Brief description of option 1]

**Pros:**

* [Pro 1]
* [Pro 2, etc.]

**Cons:**

* [Con 1]
* [Con 2, etc.]

### [Option 2]

[Brief description of option 2]

**Pros:**

* [Pro 1]
* [Pro 2, etc.]

**Cons:**

* [Con 1]
* [Con 2, etc.]

### [Option 3, etc.]

[Same structure as above]

## More Information

[Optional section for links to related decisions, supporting documentation, prototypes, or additional context]

---

## Template Notes

* **Keep it concise**: ADRs should be 1-2 pages maximum
* **One decision per ADR**: If you have multiple decisions, create separate ADRs
* **Immutable once accepted**: Don't edit accepted ADRs; create new ones that supersede them
* **Focus on "why"**: Explain reasoning and tradeoffs, not implementation details
* **Include rejected options**: Document why alternatives were not chosen
