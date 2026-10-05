---
title: 'Context: Feedback'
description: 'Glossary context for the Feedback Survey: how Spec Kitty asks users for optional, anonymous experience feedback, and the four canonical terms that name each part of it.'
doc_status: active
updated: '2026-10-01'
type: explanation
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/collaboration/give-feedback.md
- docs/context/planning-and-tracking.md
- docs/context/orchestration.md
---
## Context: Feedback

This page is for anyone who needs the exact words for how Spec Kitty asks its
users for optional, anonymous experience feedback. Four terms cover the whole
feature. Use them as written; the **Avoid** line on each entry lists the
words that blur the meaning.

The term **telemetry** is deliberately not used for this feature. Nothing
here runs in the background: every Feedback Submission is sent only after
the person says yes to "Send feedback?".

How-to: [Give feedback on Spec Kitty](../guides/how-to/collaboration/give-feedback.md).

### Feedback Survey

| | |
|---|---|
| **Definition** | The short, optional prompt Spec Kitty offers: a rating from 1 to 5, "What would you change?" (with its character limit shown), an optional email, and "Send feedback?". Every part can be skipped, and the person can choose "Don't ask again". |
| **Context** | Feedback |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Avoid** | questionnaire, poll, NPS |
| **Related terms** | [Survey Trigger](#survey-trigger), [Feedback Submission](#feedback-submission) |

---

### Feedback Submission

| | |
|---|---|
| **Definition** | The single anonymous message sent to the Feedback Endpoint, and only after the person answers "Send feedback?" with yes. It carries the rating, the optional comment, the optional email (only if typed), and a few coarse facts about the installation. It never carries repository, mission, branch, user, host, or credential data. |
| **Context** | Feedback |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Avoid** | telemetry, event, moment, sync |
| **Related terms** | [Feedback Survey](#feedback-survey), [Feedback Endpoint](#feedback-endpoint) |

---

### Survey Trigger

| | |
|---|---|
| **Definition** | A point in the workflow where Spec Kitty may offer the Feedback Survey: planning complete (`planning_complete`), mission end (`mission_end`), [Op](./planning-and-tracking.md#op) close (`op_close`), or on demand (`on_demand`, the `spec-kitty feedback` command and the `/spec-kitty.feedback` agent command). The three automatic triggers share one limit of at most one offer per week and never fire in CI or non-interactive terminals; the `on_demand` trigger ignores that weekly limit. |
| **Context** | Feedback |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Avoid** | hook |
| **Related terms** | [Feedback Survey](#feedback-survey), [Mission](./orchestration.md#mission) |

---

### Feedback Endpoint

| | |
|---|---|
| **Definition** | The web-service address that receives a Feedback Submission. Resolved in order: the `SPEC_KITTY_FEEDBACK_URL` environment variable, then the user override in `feedback.json`, then the distribution default, then none. It must use HTTPS, except for a loopback address. With none, the automatic Feedback Survey is dormant. |
| **Context** | Feedback |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Avoid** | SaaS, Team Kitty, relay |
| **Related terms** | [Feedback Submission](#feedback-submission) |

---

### Feedback Validation

| | |
|---|---|
| **Definition** | The single set of input rules applied to every Feedback Survey answer, in the terminal form and in the agent hand-off alike. Rating: an integer from 1 to 5. Comment: control and invisible characters and terminal escape sequences removed, markup kept, newlines collapsed to a space, truncated at the shown limit with a notice. Email: optional, one well-formed address, rejected rather than corrected. If any answer is invalid, nothing is sent. |
| **Context** | Feedback |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Avoid** | sanitizing, escaping |
| **Related terms** | [Feedback Survey](#feedback-survey), [Feedback Submission](#feedback-submission) |
