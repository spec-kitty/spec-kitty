---
work_package_id: WP04
title: Decision record and changelog
dependencies:
- WP03
requirement_refs:
- FR-019
- C-005
planning_base_branch: issue-6675-write-service-protocol
merge_target_branch: issue-6675-write-service-protocol
branch_strategy: Planning artifacts for this mission were generated on issue-6675-write-service-protocol. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6675-write-service-protocol unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
phase: Phase 3 - Record
history:
- at: '2026-10-27T18:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md
- docs/adr/4.x/index.md
- docs/adr/4.x/2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Decision record and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log and address every item before handing back.

## Objectives & Success Criteria

- ADR `2026-10-27-1` (status Accepted, operator rulings of 2026-10-25 and 2026-10-27) records:
  the transport (loopback HTTP, `127.0.0.1`, random port), the endpoint file (location, fields,
  modes, Windows ACL rule, temp-file-and-rename), the bearer scheme, service authority, the
  durability contract (one `O_APPEND` write, `fsync` before ack, batched `fsync`; Windows under the
  lock, by reference to #6193), version negotiation, the refusal vocabulary rule (reuse CLI codes,
  reason URNs, protocol-only codes), the client shape and binder, and an Open questions section
  with each provisional default (idempotent retry, backpressure, token rotation, MCP mode,
  shutdown and idle, size cap, write-location verification). FR-019.
- It amends ADR 2026-10-22-1 open question 3 (a local socket → loopback HTTP) and D-7 (the
  append semantics are ruled: one `O_APPEND` write); ADR 2026-10-22-1 gains an amendment pointer
  line only, its decisions are not rewritten.
- `docs/adr/4.x/index.md` lists the new ADR; `docs/changelog/CHANGELOG.md` `[Unreleased]` has one
  entry.
- References only, no change: #6676 (launcher), #6193 (lock spike), spec-kitty-events #92
  (envelope), #6195 (cut-over).

## Context & Constraints

- Follow the frontmatter and section shape of `docs/adr/4.x/2026-10-22-1-*.md` (title,
  description, status, date; Context, Drivers, Options, Outcome with D-n decisions, Consequences,
  Confirmation, Open questions, More Information). Reader persona: a maintainer building the
  client or the service.
- Any ADR gate under `tests/architectural/` or `tests/docs/` that reads ADR frontmatter or the
  index must pass (find them with `grep -rl "docs/adr" tests/ --include=*.py`).

## Branch Strategy

- **Strategy**: single_branch (set by finalize-tasks)
- **Planning base branch**: issue-6675-write-service-protocol
- **Merge target branch**: issue-6675-write-service-protocol

Implementation command: `spec-kitty agent action implement WP04 --agent claude --mission write-service-protocol-01M5Z6N5`

## Subtasks & Detailed Guidance

### Subtask T017 – The ADR

- One decision per D-n; mark derived clauses as in ADR 2026-10-22-1. Link the contract module
  `contracts/mission-write/openapi.yaml` and the client shapes module.

### Subtask T018 – Index and amendment pointer

- Add the index row in date order; add an "Amended by ADR 2026-10-27-1 (open question 3, D-7)"
  line to ADR 2026-10-22-1's header block.

### Subtask T019 – Changelog

- One `[Unreleased]` bullet under the right heading, naming #6675, the contract module, the layout
  rule and the client shapes.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q $(grep -rl "docs/adr" tests/architectural tests/docs --include=*.py 2>/dev/null | tr '\n' ' ')
```

## Risks & Mitigations

- ADR index format drift: copy the neighbouring row's shape.

## Review Guidance

- Every operator ruling and every provisional default appears; nothing in ADR 2026-10-22-1 is
  rewritten beyond the pointer.

## Progress & Status

Recorded through the status event log.
