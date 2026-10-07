# Mission Specification: Orchestrator 2 governed mission and planning API

**Mission Branch**: `issue-5846-orchestrator-two`
**Created**: 2026-10-06
**Status**: Draft
**Input**: Lynn authorized revising Gokitty3 first, then completing Python, reconciling Stijn, publishing reviewable PRs for Stijn and Nik, then DMing Nik. Mission and planning coverage are required.

## User Scenarios & Testing

### User Story 1 - Complete planning through the API (Priority: P1)

An external client discovers mission templates/governance, creates a mission, records interview/design decisions, submits specification and plan artifacts, authors wps.yaml and package prompts, and finalizes packages without manual repository writes or separate host CLI calls.

**Why this priority**: Current tests bridge scaffold/finalize gaps with manual writes and commits.
**Independent Test**: Black-box client starts in an initialized scratch project and uses orchestrator-api only through finalized dependency-valid packages. Initialization precedes the first API call.

**Acceptance Scenarios**:

1. **Given** an initialized project, **When** the client creates and authors a mission and finalizes packages using only API calls, **Then** canonical host placement/commit/gates produce ready work.
2. **Given** an artifact digest, **When** replacement targets that digest, **Then** the client receives the new digest and attributable commit outcome; stale digests refuse before effects. Changed upstream specification, plan or governance invalidates downstream submissions/validation; finalization refuses stale parents until revalidated.
3. **Given** blocked plan prerequisites, **When** the delegate reports result=blocked or a typed error, **Then** the outer API reports typed failure.

### User Story 2 - Advance the canonical runtime (Priority: P1)

Clients query or advance the same next-step authority as the host CLI and resolve decisions through existing verbs.

**Independent Test**: Query does not bootstrap a run. Advancing preserves charter preflight, run-index locking, invocation/result pairing and lifecycle records.

**Acceptance Scenarios**:

1. **Given** a mission without a run, **When** next is queried, **Then** no run is created.
2. **Given** a mission ready to advance, **When** next is called with agent/result, **Then** the canonical action/prompt is returned and blocked/decision_required states remain explicit.

### User Story 3 - Reconcile the delivery honestly (Priority: P1)

Existing clients retain their verbs. Discovery maps the amended Go contract to actual Python semantics and unavailable capabilities.

**Independent Test**: Contract census, docs and invocation fixtures agree. Go leases, fences, GapDB authority, native async/watch and durable operation replay are explicitly unavailable.

### Edge Cases

- Absolute/traversal/symlink paths, status/meta/event writes, finalized/executing package content, foreign missions and undeclared kinds refuse before effects.
- Placeholder specification/plan, duplicate or unknown requirements, dependency cycles, oversize content and duplicate targets refuse; tests pair each negative with a valid journey.
- Open design decisions block completion. Changed upstream artifacts invalidate downstream validation and package finalization.
- Failed commits expose materialized-but-uncommitted outcomes without claiming persistence success.
- Missing templates/capabilities return typed diagnostics without inventing authority.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Complete design journey | Create, author and finalize entirely through the API. | High | Open | [build] | no |
| FR-002 | Governed discovery | Expose resolved mission types, templates, action context and interview/decision mechanisms. | High | Open | [build] | no |
| FR-003 | Artifact read/submission | Registered design artifacts use canonical placement, expected digests and host commits; no arbitrary state writes. | High | Open | [build] | no |
| FR-004 | Canonical gates | Reuse substantive committed spec, plan prerequisites, manifest validation/finalization and status bootstrap; blocked results remain failures; unresolved design decisions and stale parent revisions block completion. | High | Open | [build] | no |
| FR-005 | Canonical next | Query/advance existing next authority including decisions and step completion. | High | Open | [build] | no |
| FR-006 | Capability truth | Preserve verbs/envelope and document supported, translated and unavailable Go semantics. | High | Open | [build] | no |
| FR-007 | Stijn reconciliation | Integrate #5664 modules and existing claim/status services; reconcile #5231, #5532, #5735 without claiming deferred work shipped. | High | Open | [folded] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounds | Publish finite UTF-8 bytes/count limits and enforce before effects. | Security | High | Open |
| NFR-002 | Refusal safety | Invalid/stale requests leave previous artifacts byte-identical. | Reliability | High | Open |
| NFR-003 | Proof | Red-first acceptance, affected existing tests and specific architectural gates pass. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Shared authority | No shell workflow, duplicate state reducer, raw event/store writes or arbitrary paths. | Technical | High | Open |
| C-002 | Persistence honesty | Existing filesystem/event/git authorities remain; do not promise Go atomic journal/lease/fence/operation replay. | Technical | High | Open |
| C-003 | Scope | No Docker subscriptions, unit economics, DeepSeek, new hosted Team Kitty, main merge or release bump. | Delivery | High | Open |

### Key Entities

- Mission: immutable identity, selected mission type, topology and governed artifacts.
- Design artifact: registered kind, host-selected location, content and digest.
- Work-package manifest: canonical wps.yaml schema/finalizer.
- Runtime decision: existing query/step/blocked/decision_required/terminal authority.
- Delivery profile: semantic mappings, limits and unsupported capabilities.

## Success Criteria

- **SC-001**: API-only client reaches finalized packages and observable ready work. — [build] · no-op passable: no
- **SC-002**: Traversal, stale revisions and blocked planning fail on fixtures where valid controls succeed. — [ratchet] · no-op passable: yes
- **SC-003**: Stijn and Nik receive reviewable Python and Go changes with truthful evidence. — [build] · no-op passable: no
