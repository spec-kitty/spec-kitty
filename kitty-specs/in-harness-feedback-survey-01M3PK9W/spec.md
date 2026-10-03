# Mission Specification: In-Harness Feedback Survey

**Mission Branch**: `feat/in-harness-feedback-survey`  
**Created**: 2026-09-29  
**Status**: Draft  
**Input**: User description: "Add a feature to spec-kitty which presents a quick feedback questionnaire to users at the end of a mission or at other critical points. It should basically have two questions: how would you rate your experience? (1-5); what would you change (open question). Results should be sent to a web-service, so that requires explicit user consent. Fail quietly if web-service is not working (launch and forget). Questions should be presented within the harness using its default UI (cli, web, other). We could also show it after an ad-hoc cycle is closed. We don't want it to be intrusive or get in the way. Anonymous by default. Email is purely opt-in in case the user wants to be signed on the feedback."

## Purpose

Spec Kitty has no direct channel for hearing how people experience missions and ad-hoc work. A short, optional two-question **Feedback Survey** — a 1–5 experience rating plus "What would you change?" — offered at natural completion points gives maintainers a steady, low-friction signal. The survey is anonymous by default, is only ever sent after the user explicitly confirms that specific submission, and never blocks, slows, or fails the user's workflow.

## Domain Language

| Canonical term | Meaning | Avoid |
|---|---|---|
| **Feedback Survey** | The short two-question prompt (rating + open comment, optional email, consent step) shown to a user. | "questionnaire", "NPS", "poll" |
| **Feedback Submission** | The single anonymous payload sent to the Feedback Endpoint after the user confirms "Send feedback". | "telemetry" (implies automatic, unconsented collection), "event", "moment", "sync" |
| **Survey Trigger** | A completion point at which a Feedback Survey may be offered: mission end, Op close, planning complete, or on demand. | "hook" |
| **Feedback Endpoint** | The web-service address that receives Feedback Submissions. | "SaaS", "Team Kitty", "relay" |
| **Op** | A bounded, doctrine-governed ad-hoc agent action closed with a recorded outcome (see `docs/context/planning-and-tracking.md#op`). | "ad-hoc cycle", "session" |
| **Mission** | The canonical unit of planned work. | "feature" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rate a completed mission (Priority: P1)

A developer has just finished a mission. At the end of the mission, the harness they are working in (a terminal, an IDE agent, or another agent host) shows the Feedback Survey using its own native question UI. They pick a rating from 1 to 5, optionally type what they would change, optionally add their email, and are then asked "Send feedback?". They confirm, see a short thank-you, and carry on. The submission is anonymous unless they typed an email.

**Why this priority**: This is the core value — a direct experience signal at the most meaningful completion point, with consent and anonymity built in.

**Independent Test**: Complete a mission in a test project with a reachable test endpoint; answer the survey and confirm sending; verify exactly one submission arrives with only the allowed fields.

**Acceptance Scenarios**:

1. **Given** a mission has just completed successfully and the user is eligible, **When** the completion step finishes, **Then** the Feedback Survey is offered in the harness's native question UI with the rating question first.
2. **Given** the user has answered the rating and optional comment, **When** they confirm "Send feedback", **Then** exactly one Feedback Submission is sent containing the rating, the comment (if any), and only the allowed context fields.
3. **Given** the user has answered the questions, **When** they decline "Send feedback", **Then** nothing is sent and the workflow continues unchanged.
4. **Given** the user left the email field blank, **When** the submission is sent, **Then** it contains no email and no other identifying data.
5. **Given** the user typed an email, **When** the submission is sent, **Then** it includes that email and nothing else identifying.

---

### User Story 2 - Never get in the way (Priority: P1)

A developer works through many missions and Ops in a week. They see the survey at most once a week, can skip it with one action, and can switch automatic prompts off permanently. If the feedback service is down or slow, they never notice. In CI or other headless runs, the survey never appears.

**Why this priority**: The user was explicit that the survey must not be intrusive; a survey that nags, blocks, or errors would damage the experience it is meant to measure.

**Independent Test**: Trigger several eligible completion points within a week with the endpoint unreachable; verify one offer at most, no errors, unchanged exit statuses, and no offers in non-interactive runs.

**Acceptance Scenarios**:

1. **Given** the survey was shown (answered or skipped) less than 7 days ago, **When** any automatic Survey Trigger fires, **Then** no survey is offered.
2. **Given** a survey is offered, **When** the user chooses "skip", **Then** nothing is sent and the next automatic offer is at least 7 days away.
3. **Given** a survey is offered, **When** the user chooses "don't ask again", **Then** no automatic survey is offered again for that user on that machine until they re-enable it.
4. **Given** the Feedback Endpoint is unreachable, slow, or returns an error, **When** the user confirms "Send feedback", **Then** they see the same thank-you, no error is shown, and the triggering command's outcome and exit status are unchanged.
5. **Given** Spec Kitty runs non-interactively (CI, headless agent run, no human at the harness), **When** an automatic Survey Trigger fires, **Then** no survey is offered and the throttle window is not consumed.

---

### User Story 3 - Feedback after an Op or after planning (Priority: P2)

A developer closes an ad-hoc Op, or finishes planning a mission (spec, plan, and tasks all done). If they are eligible, the same Feedback Survey is offered, and the submission records which completion point prompted it.

**Why this priority**: Extends the signal to the two other key moments the user named, reusing the same survey and rules.

**Independent Test**: Close an Op with outcome `done`, and separately finalize a mission's tasks, each in a fresh eligibility window; verify the survey is offered and the submission's trigger field matches.

**Acceptance Scenarios**:

1. **Given** the user is eligible, **When** an Op is closed with outcome `done` or `failed`, **Then** the Feedback Survey is offered and a sent submission records the trigger as Op close.
2. **Given** the user is eligible, **When** mission planning completes (tasks finalized), **Then** the Feedback Survey is offered and a sent submission records the trigger as planning complete.
3. **Given** an Op is closed with outcome `abandoned`, **When** the close completes, **Then** no survey is offered.

---

### User Story 4 - Give feedback on demand (Priority: P3)

A developer wants to share feedback right now, regardless of when they last saw a survey or whether they turned automatic prompts off. They run an explicit command and get the same survey.

**Why this priority**: Lets motivated users give feedback without waiting for a trigger, and keeps feedback possible for users who silenced automatic prompts.

**Independent Test**: With "don't ask again" set and a survey shown yesterday, run the on-demand command; verify the survey appears and can be sent.

**Acceptance Scenarios**:

1. **Given** the user chose "don't ask again" or saw a survey within the last 7 days, **When** they run the on-demand command, **Then** the Feedback Survey is offered.
2. **Given** no Feedback Endpoint is available, **When** the user runs the on-demand command, **Then** they are told that no feedback endpoint is configured, before any question is asked, and nothing is collected.

---

### User Story 5 - Know where feedback goes and control it (Priority: P3)

A developer (or a Spec Kitty distributor) wants to know where feedback is sent and what it contains, and to point it at a different service. Each distribution ships its own default Feedback Endpoint; a user can override it. With no endpoint at all, automatic surveys simply never appear.

**Why this priority**: Supports informed consent (the consent prompt stays short) and lets each downstream distribution route feedback to its own service.

**Independent Test**: Inspect the survey settings in a build with a packaged endpoint, override it with a user setting, then remove both; verify the reported destination and the dormant behaviour.

**Acceptance Scenarios**:

1. **Given** a distribution ships a default Feedback Endpoint and the user has no override, **When** a submission is sent, **Then** it goes to the packaged default.
2. **Given** the user has set an endpoint override, **When** a submission is sent, **Then** it goes to the override.
3. **Given** neither a packaged default nor a user override exists, **When** any automatic Survey Trigger fires, **Then** no survey is offered.
4. **Given** any configuration, **When** the user asks to see their feedback settings, **Then** they see the effective destination, the list of fields a submission contains, the last-shown date, and whether automatic prompts are on.

### Edge Cases

- **Endpoint failures**: DNS failure, refused connection, timeout, TLS error, 4xx/5xx, or malformed response all end silently with the same thank-you; the answers are discarded (no retry, no local copy).
- **User abandons mid-survey** (closes the harness, interrupts, or dismisses the UI): nothing is sent; the offer counts as shown for throttling.
- **Several triggers close together** (e.g., planning complete and mission end in the same week): only the first eligible trigger offers a survey.
- **Two Spec Kitty processes hit a trigger at the same moment**: at most one survey is offered.
- **Invalid rating input** (0, 6, text): the user is asked again or may skip; no invalid rating is ever sent.
- **Very long comment**: accepted up to 2,000 characters; longer text is cut to that limit and the user is told before the consent step.
- **Malformed email**: the user is told it looks invalid and may re-enter it or leave it blank; a malformed email is never sent.
- **Harness without a structured question UI**: the survey falls back to plain-text questions with the same choices.
- **Unreadable or corrupt survey preferences**: Spec Kitty never crashes; it fails toward *not* offering an automatic survey until preferences are valid again.
- **System clock moved backwards** (last-shown date in the future): no automatic survey until the date is in the past or the preferences are reset.
- **Triggering workflow fails** (e.g., mission consolidation fails): no survey is offered for that trigger.
- **User-supplied endpoint override is not a valid address**: treated as no endpoint (dormant); the settings view and the on-demand command explain why.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Two-question survey content | As a user, I want to be asked "How would you rate your experience?" (1–5, required to submit) and "What would you change?" (optional free text) so that I can give quick, meaningful feedback. | High | Open | [build] | no |
| FR-002 | Optional email field | As a user, I want an optional, clearly-labelled email field (blank by default) so that I can sign my feedback only if I choose to. | High | Open | [build] | no |
| FR-003 | Per-submission explicit consent | As a user, I want a final "Send feedback?" confirmation on every survey, with nothing transmitted unless I confirm, so that no data leaves my machine without my say. | High | Open | [build] | yes — paired with the confirm-sends-exactly-one-submission assertion on the same fixture |
| FR-004 | Anonymous payload allowlist | As a user, I want a submission to contain only the rating, the comment, the email if I typed one, and the allowed context fields (Spec Kitty version and distribution, Survey Trigger, agent harness, OS/platform, mission type) so that my feedback is anonymous by default. | High | Open | [build] | yes — paired with a positive control that the allowed fields are present on the same captured submission |
| FR-005 | Mission-end trigger | As a user, I want the survey offered after a mission completes successfully so that I can rate the whole mission experience. | High | Open | [build] | no |
| FR-006 | Op-close trigger | As a user, I want the survey offered after I close an Op with outcome `done` or `failed` (not `abandoned`) so that I can rate ad-hoc work. | Medium | Open | [build] | no |
| FR-007 | Planning-complete trigger | As a user, I want the survey offered once mission planning completes (spec, plan, and tasks done) so that I can rate the planning experience. | Medium | Open | [build] | no |
| FR-008 | On-demand survey | As a user, I want an explicit command that offers the survey at any time, ignoring the weekly limit and "don't ask again", so that I can give feedback whenever I want. | Medium | Open | [build] | no |
| FR-009 | Harness-native presentation | As a user, I want the survey shown in my harness's own default question UI (interactive terminal prompt, IDE agent question picker, or plain-text fallback) so that it feels native and quick. | High | Open | [build] | no |
| FR-010 | Human-only answers | As a user, I want the survey answered only by me, never auto-filled or answered by an agent on my behalf, so that the feedback is genuine. | High | Open | [build] | yes — paired with the human-answer-is-recorded assertion on the same prompt fixture |
| FR-011 | Weekly throttle | As a user, I want automatic surveys offered at most once per 7 days across all triggers and projects on my machine, counted from the last time one was shown, so that I am not nagged. | High | Open | [build] | yes — paired with the eligible-after-7-days assertion on the same preferences fixture |
| FR-012 | Skip | As a user, I want to skip any offered survey with a single action, sending nothing, so that it never gets in my way. | High | Open | [build] | no |
| FR-013 | Don't ask again | As a user, I want a "don't ask again" choice on every automatic offer that silences automatic surveys for me on this machine until I re-enable them, so that I stay in control. | High | Open | [build] | yes — paired with the offered-before-opt-out assertion on the same preferences fixture |
| FR-014 | Fire-and-forget send | As a user, I want a confirmed submission sent in a single bounded attempt with no retry, no queue, and no local copy, with any failure ignored silently and the same thank-you shown, so that a broken service never affects me. | High | Open | [build] | yes — paired with the reachable-endpoint-receives-submission assertion on the same fixture |
| FR-015 | Workflow outcome untouched | As a user, I want the triggering command's result recorded before the survey is offered, and its outcome and exit status unchanged whatever I do with the survey, so that feedback never alters my work. | High | Open | [build] | yes — paired with the survey-was-offered assertion on the same command run |
| FR-016 | Endpoint resolution | As a distributor, I want each distribution to ship its own default Feedback Endpoint that a user-level setting can override, so that feedback goes to the right service. | High | Open | [build] | no |
| FR-017 | Dormant without an endpoint | As a user, I want automatic surveys never offered when no endpoint is available, and the on-demand command to explain that before asking anything, so that I never answer questions that cannot be sent. | Medium | Open | [build] | yes — paired with the offered-when-endpoint-present assertion on the same fixture |
| FR-018 | Non-interactive skip | As a user, I want automatic surveys skipped silently in non-interactive runs (CI, headless, no human present) without consuming the weekly window, so that automation never stalls. | High | Open | [build] | yes — paired with the offered-in-interactive-run assertion on the same trigger fixture |
| FR-019 | Settings transparency | As a user, I want to view my feedback settings — effective destination, fields sent, last-shown date, automatic prompts on/off — and re-enable or disable automatic prompts, so that my consent is informed. | Medium | Open | [build] | no |
| FR-020 | Input validation | As a user, I want invalid ratings re-asked, comments capped at 2,000 characters with notice, and malformed emails re-asked or left blank, so that only well-formed feedback is ever sent. | Medium | Open | [build] | no |
| FR-021 | Versioned submission format | As a maintainer of the receiving service, I want every submission to carry a submission-format version so that the service can evolve without breaking older clients. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Non-blocking send | After the user confirms "Send feedback", control returns to the user within 1 second in 100% of cases, including an unreachable, slow, or erroring endpoint; the background send attempt is abandoned after at most 5 seconds. | Performance | High | Open |
| NFR-002 | Silent failure | 100% of endpoint failure modes (DNS, connection refused, timeout, TLS error, 4xx, 5xx, malformed response) produce zero user-visible errors or warnings and zero change to the triggering command's exit status. | Reliability | High | Open |
| NFR-003 | Low trigger overhead | When no survey is offered at a trigger, the eligibility check adds no more than 100 ms to the triggering command (keeping typical CLI operations under the charter's 2-second budget). | Performance | High | Open |
| NFR-004 | Anonymity | With the email left blank, a submission contains 0 fields outside the FR-004 allowlist — no repository name or path, mission name or id, branch, username, hostname, git identity, or authentication token. | Privacy | High | Open |
| NFR-005 | Throttle guarantee | No user receives more than 1 automatic survey in any rolling 7-day window per machine, including when two Spec Kitty processes reach a trigger concurrently. | Usability | High | Open |
| NFR-006 | Transport security | Submissions to any non-loopback endpoint are sent only over an encrypted connection; an unencrypted non-loopback endpoint is treated as no endpoint. | Security | High | Open |
| NFR-007 | Cross-platform parity | Survey behaviour, preferences, and throttling are identical on Linux, macOS, and Windows 10+. | Portability | Medium | Open |
| NFR-008 | Quick to complete | A user can complete the survey (rating, optional comment, consent) in 4 interactions or fewer and under 30 seconds. | Usability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical terminology | Use "Feedback Survey" / "Feedback Submission" consistently in CLI text, docs, and code; never call it telemetry; the Mission-not-Feature canon applies. | Business | High | Open |
| C-002 | Reuse the harness-prompt pattern | Harness-native presentation must reuse the established pattern already used by the startup upgrade check (the CLI decides eligibility and returns a structured prompt; the harness renders it natively; answers are recorded back through the CLI) rather than inventing a second mechanism. | Technical | High | Open |
| C-003 | Independent of Team Kitty / Zeitgeist | Feedback Submissions use their own channel: they are not Zeitgeist moments, do not reintroduce sync, are not gated by Team Kitty login or membership, and never carry Team Kitty credentials. | Technical | High | Open |
| C-004 | Receiving service out of scope | This mission delivers the client side and the submission-format contract only; building or hosting the receiving web service is out of scope. | Business | High | Open |
| C-005 | Per-user controls only | Controls are per user on a machine ("skip", "don't ask again", endpoint override, re-enable); no project-level or org-level switch is provided. | Business | Medium | Open |
| C-006 | Preferences stay out of the repository | Survey preferences and throttle state are stored at user level, never in the project repository, and are never committed. | Technical | High | Open |
| C-007 | Short consent wording | The consent step reads simply "Send feedback?" and does not display the endpoint address; the destination is available through the settings view (FR-019) and documentation. | Business | Medium | Open |
| C-008 | Canonical command sources | Survey instructions reach every supported harness through the canonical command/skill sources and the upgrade propagation path, never through hand-edited generated agent copies. | Technical | High | Open |

### Key Entities

- **Feedback Survey**: The prompt shown to a user — rating (1–5), optional comment, optional email, and the "Send feedback?" consent step, with "skip" and (for automatic offers) "don't ask again" choices.
- **Feedback Submission**: One anonymous payload sent after consent — submission-format version, rating, optional comment, optional email, and the allowed context fields (Spec Kitty version and distribution, Survey Trigger, agent harness, OS/platform, mission type).
- **Survey Trigger**: The completion point that offered the survey — mission end, Op close, planning complete, or on demand.
- **Survey Preferences**: Per-user, per-machine state — last-shown date, automatic prompts on/off ("don't ask again"), and optional endpoint override.
- **Feedback Endpoint**: The effective destination — the user override if set, otherwise the distribution's packaged default, otherwise none (dormant).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from the survey appearing to "thank you" in under 30 seconds and 4 interactions or fewer. — [build] · no-op passable: no
- **SC-002**: With the Feedback Endpoint unreachable, 100% of triggering workflows finish with the same outcome and exit status as with the survey switched off, and show no error. — [build] · no-op passable: yes — paired with the survey-offered-and-sent assertion on the same workflow run with a reachable endpoint
- **SC-003**: 0 submissions are ever sent without an explicit "Send feedback" confirmation, across all four Survey Triggers. — [build] · no-op passable: yes — paired with the confirmed-sends-exactly-one assertion for each trigger on the same fixture
- **SC-004**: No user sees more than one automatic survey in any rolling 7-day window. — [build] · no-op passable: yes — paired with the survey-offered-after-7-days assertion on the same preferences fixture
- **SC-005**: With email left blank, 100% of submissions contain only allowlisted fields (0 identifying fields). — [build] · no-op passable: yes — paired with the allowlisted-fields-present assertion on the same captured submission
- **SC-006**: The survey renders natively in a plain terminal and in at least three supported agent harnesses (for example Claude Code, Cursor, and Codex), each offering skip, rating, comment, email, and consent. — [build] · no-op passable: no

## Assumptions

- The on-demand command ignores both the weekly limit and "don't ask again"; "don't ask again" only silences automatic offers.
- A rating is required to submit; the comment and email are optional.
- "Mission end" means a mission's consolidation completed successfully; a failed consolidation offers no survey.
- An Op closed with outcome `abandoned` offers no survey; `done` and `failed` do.
- An offer that is skipped, abandoned, or answered all count as "shown" for the weekly limit; non-interactive runs do not.
- The comment is sent as the user wrote it (within the length cap); the consent step is the user's control over its content.
- Distributions without a packaged default endpoint (possibly including the upstream open-source build) will have dormant automatic surveys until a user configures an endpoint.
- Spec Kitty can detect CI and non-interactive terminals, but it cannot tell whether an agent harness session has a human present. For agent-presented surveys, FR-018 therefore relies on the agent following the instruction to offer the survey only when a human is in the loop; this limitation is documented for users.
