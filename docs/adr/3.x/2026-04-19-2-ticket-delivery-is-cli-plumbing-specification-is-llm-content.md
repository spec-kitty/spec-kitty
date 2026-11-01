---
title: Ticket Delivery Is CLI Plumbing; Specification Is LLM Content
description: 'Creating a mission from a tracker ticket only fetches context and registers a pending origin record, then hands off; the CLI never writes specification prose.'
status: Accepted
date: '2026-04-19'
doc_status: active
kind: ADR
updated: '2026-04-19T00:00:00Z'
---

## Context and Problem Statement

The `mission create --from-ticket linear:PRI-42` command must do two distinct
things:

1. **Fetch an external tracker ticket and make its content available** so an LLM
   agent can write a mission specification from it.
2. **Establish a durable mission-origin link** between the external ticket and the
   resulting mission so SaaS can route lifecycle egress (status updates, comments)
   back to the originating issue.

The question is where the boundary falls: how much of the work belongs to the
CLI, and how much belongs to the LLM?

### The wrong answer

A naive implementation would make the CLI do everything: fetch the ticket, parse
its content, scaffold a mission directory, fill in a spec template from the ticket
fields, register the origin, and post a backlink comment. The LLM would be
bypassed entirely.

This is wrong for several reasons:

1. Ticket bodies contain requirements phrasing, implicit constraints, stakeholder
   context, and edge cases that a template filler cannot reason over. The LLM
   produces a better spec by reading the real content than by consuming an
   auto-generated summary.
2. It violates the established principle from
   `2026-03-09-1-prompts-do-not-discover-context-commands-do.md`: commands own
   execution context and plumbing; LLMs own content reasoning. A command that
   writes spec content is inverting that boundary.
3. It makes the flow provider-specific in ways that are hard to generalise: ticket
   schema differences across Linear, Jira, GitHub Issues, and GitLab Issues should
   not influence what the LLM sees. The CLI normalises; the LLM reasons.

### The right answer

The CLI does exactly and only the plumbing:

- Fetch and normalise the ticket into a local context file.
- Register a pending mission origin on SaaS.
- Hand off to the LLM with a clear instruction.

The LLM does exactly and only the content work:

- Read the ticket context file.
- Run `/spec-kitty.specify` to produce the mission specification.

The CLI then finalises the mission-origin link once the mission exists.

---

## Decision Drivers

- **LLM specification quality** — free-form reasoning over raw ticket content
  produces better specs than template substitution.
- **Principle of least knowledge** — the CLI should not know how to interpret
  ticket requirements; the LLM should not know how to call SaaS APIs.
- **Consistency with established ADRs** — this decision follows directly from
  `2026-03-09-1` (commands do context, prompts do not) and
  `2026-04-04-1` (binding context is discovered, not user-supplied).
- **Provider neutrality** — the ticket normalisation layer in the CLI means the
  LLM sees the same context shape regardless of whether the ticket came from
  Linear, Jira, GitHub Issues, or GitLab.
- **Backlink correctness** — the SaaS backlink comment should only be posted after
  a mission actually exists. Posting it before `specify` runs creates phantom links
  if the user abandons the session.

---

## Decision Outcome

### Core decision

`mission create --from-ticket <provider:ID>` is a CLI plumbing command. It MUST
NOT write mission specification content. It MUST hand off to the LLM.

### Responsibilities

**CLI (`mission create --from-ticket`):**

1. Fetch the ticket via SaaS → normalise to a local context file at
   `.kittify/ticket-context.md`.
2. Register a pending mission-origin record on SaaS, associating the ticket with
   this repo and assigning a provisional `mission_id`. This record is `pending`
   until a mission is confirmed to exist.
3. Write the pending `mission_id` and `origin` to local tracker config so
   `/spec-kitty.specify` can read them without re-fetching.
4. Print a handoff message and exit 0:

   ```
   Ticket PRI-42 fetched → .kittify/ticket-context.md
   Mission origin registered (pending): 01KPXXXXXX

   Run /spec-kitty.specify to create the mission from this ticket.
   The mission will be linked to PRI-42 automatically on completion.
   ```

**LLM (via `/spec-kitty.specify`):**

1. Detect the presence of `.kittify/ticket-context.md` and treat it as the
   mission brief.
2. Read the full ticket content — title, body, labels, comments — as written to
   `.kittify/ticket-context.md` by the CLI (the context file includes labels and
   comments in addition to the standard fields) and produce a spec from it using
   normal specification reasoning.
3. On completion, call the mission origin finalisation surface (exact command name
   to be determined by sk#695 implementation; the current placeholder is
   `spec-kitty agent mission finalize-origin`) to confirm the mission and trigger
   SaaS finalisation.

**SaaS (on mission confirmation):**

1. Promote the pending mission-origin record to confirmed.
2. Post a backlink comment on the originating ticket referencing the confirmed
   mission.
3. Begin routing lifecycle egress events to the ticket.

### Invariants

- The CLI MUST NOT write to any file under `kitty-specs/`. That directory is
  owned by the specify/plan/tasks pipeline.
- The CLI MUST NOT post a backlink comment before the mission is confirmed.
  Abandoned specify runs MUST NOT leave comments on tracker issues.
- `/spec-kitty.specify` MUST treat `.kittify/ticket-context.md` as optional
  context, not a required input. The specify flow must work without it.
- The SaaS provisional record ID assigned at `mission create` time MUST be the
  same one promoted to confirmed when the mission is finalised. This is a
  SaaS-internal record ID, not the spec-kitty mission ULID (as defined in
  `2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md`); the two
  namespaces are separate. The CLI MUST NOT allow a second `mission
  create --from-ticket` on the same ticket to create a duplicate pending record
  while one is already active. Deduplication is checked against the local
  `.kittify/` state first; if local state is absent, the CLI queries SaaS to
  confirm no active pending record exists for that ticket ID and repo.

---

## Consequences

### Positive

- Spec quality reflects the LLM's reasoning over the full ticket, not a
  template.
- The same CLI surface works unchanged for Linear, Jira, GitHub Issues, and
  GitLab Issues.
- No phantom backlink comments from abandoned sessions.
- The boundary between CLI plumbing and LLM content is explicit and testable.

### Negative

- The flow is two-step from the user's perspective: run the command, then run
  `/spec-kitty.specify`. A user who runs the command and walks away will have a
  dangling pending origin record that must be cleaned up.
- The CLI must implement a pending-origin TTL or explicit cancel path to prevent
  orphaned records accumulating on SaaS. The specific TTL value and cancel
  interface are deferred to sk#695; a provisional default of 7 days is assumed
  until that implementation decides otherwise.

### Neutral

- The ticket context file is a normalised Markdown document. Its schema is
  intentionally simple: a heading, standard fields (status, assignee, URL), the
  raw body, labels (as a comma-separated list), and any comments appended in
  chronological order. The LLM is not constrained to a fixed template.

---

## Confirmation

This decision is validated when:

1. `spec-kitty mission create --from-ticket linear:PRI-42` exits 0 without
   writing anything under `kitty-specs/`.
2. `.kittify/ticket-context.md` contains the full ticket body in a form the LLM
   can reason over.
3. Running `/spec-kitty.specify` after the command produces a spec that
   demonstrably reflects the ticket content, not a generic template.
4. The Linear ticket receives a backlink comment only after specify completes and
   a mission directory exists.
5. Running the command twice on the same ticket does not produce two pending
   origin records or two backlink comments.

---

## Related ADRs

- `architecture/adrs/2026-03-09-1-prompts-do-not-discover-context-commands-do.md` — the parent
  principle: commands own execution context, LLMs own content reasoning. This ADR
  applies that principle to the ticket-to-mission surface.
- `2026-04-04-1-tracker-binding-context-is-discovered-not-user-supplied.md` —
  establishes that binding uses discovered context, not user-typed metadata.
  `mission create --from-ticket` is the user-facing entry point into that
  discovery model at mission-origin time.
- `2026-02-27-2-host-owned-tracker-persistence-boundary.md` — tracker state lives
  in the host control plane. The pending/confirmed mission-origin lifecycle is
  SaaS-owned, consistent with that boundary.

## Related Issues

- sk#695 — implementation tracking for `mission create --from-ticket`
- saas#79 — mission-origin E2E validation
- saas#74 — terminal-state policy (what the CLI does to the ticket on mission completion; a separate decision)
