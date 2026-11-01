---
title: Entire.io Checkpoint Import for Session History Interoperability
description: Argues for a read-only importer for Entire.io session checkpoints, so their capture tooling can coexist with Spec Kitty's own event log rather than displace it.
status: Proposed
doc_status: active
kind: ADR
date: '2026-02-11'
---

## Context and Problem Statement

Entire.io is a Tier 1 competitive threat building multi-agent orchestration with session capture infrastructure. Their production-ready system (990 commits) stores AI agent session checkpoints in Git using a dedicated branch (`entire/checkpoints/v1`) with JSONL transcript format.

**Entire.io's Value Proposition**: Session history, rewind capability, attribution tracking (agent vs human line-level)

**Spec Kitty's Value Proposition**: Spec-driven orchestration, cross-repo convergence, team SaaS, progressive privacy

There is potential for complementary value: Users may want BOTH session history (Entire) AND orchestration (Spec Kitty). However, we face an architectural decision:

1. **Adopt Git-native storage** (Entire's approach): Store events on Git branches instead of PostgreSQL
2. **Build interoperability** (import Entire checkpoints): Read their format, convert to our events
3. **Ignore Entire** (compete head-to-head): Build everything ourselves, no compatibility

Adopting Git-native storage contradicts ADR 2026-02-09-1 (Canonical WP Status Model), which established PostgreSQL JSONL as the event log foundation for team SaaS. Git-native storage cannot support:
- Real-time queries (dashboard aggregations, WP status lookups)
- Multi-tenant isolation (teams see only their projects)
- CRDT conflict resolution (requires database transactions)
- WebSocket sync (requires event log subscriptions)

However, ignoring Entire misses partnership/acquisition opportunities and forces users to choose one tool or the other.

**Strategic Question**: How can Spec Kitty leverage Entire's session infrastructure without compromising our SaaS architecture?

## Decision Drivers

- **Preserve SaaS architecture**: PostgreSQL event log (ADR 2026-02-09-1) is correct for team SaaS
- **Enable interoperability**: Users should be able to use BOTH tools (Entire for sessions, Spec Kitty for orchestration)
- **Partnership potential**: Compatible format enables future integration or acquisition discussions
- **Focus on strengths**: Spec Kitty excels at orchestration; Entire excels at session capture infrastructure
- **Avoid duplication**: Don't rebuild session capture when Entire solves it well
- **Strategic optionality**: Keep acquisition option open (estimated $10-30M if they gain traction)
- **User flexibility**: Don't force "either Entire or Spec Kitty" choice

## Considered Options

- **Option 1**: Build EntireCheckpointReader (import only) - chosen
- **Option 2**: Adopt Git-native storage (replace PostgreSQL)
- **Option 3**: Build own session capture (duplicate Entire)
- **Option 4**: Ignore Entire (no compatibility)

## Decision Outcome

**Chosen option:** "Build EntireCheckpointReader for optional import", because:

1. **Preserves architecture**: Keeps PostgreSQL event log (ADR 2026-02-09-1) for team SaaS queries, dashboards
2. **Enables interoperability**: Users can run Entire (session capture) + Spec Kitty (orchestration) together
3. **Partnership optionality**: Compatible format enables acquisition discussions if Entire gains traction
4. **Focus on strengths**: Leverage Entire's session infrastructure instead of rebuilding
5. **Low risk**: Import is optional feature, doesn't affect core architecture
6. **Strategic**: Positions as "orchestration layer" complementary to Entire's "infrastructure layer"

**Implementation**: Create `EntireCheckpointReader` class in `spec_kitty_events/sources/entire_checkpoint.py` to read `entire/checkpoints/v1` branch and convert to Spec Kitty `Event` objects. Store imported sessions in PostgreSQL event log (NOT Git).

### Consequences

#### Positive

- **Interoperability proof**: Users can use both tools together (Entire for history, Spec Kitty for orchestration)
- **Partnership potential**: Compatible format opens acquisition/integration discussions with Entire team
- **Focus on strengths**: Avoid scope creep into session capture infrastructure (Entire solves this)
- **Unified history**: Imported sessions appear in Spec Kitty dashboard alongside WP events
- **Attribution data**: Extract agent vs human attribution from Entire checkpoints for transparency
- **Strategic optionality**: Acquisition path preserved ($10-30M estimated if they reach scale)

#### Negative

- **Maintenance burden**: Must keep reader compatible with Entire's checkpoint format (risk of breaking changes)
- **Dependency risk**: If Entire shuts down or pivots, import feature becomes obsolete
- **Format lock-in**: Tightly coupled to Entire's JSONL format (migration cost if they change)
- **Limited value if Entire fails**: If Entire doesn't gain traction, import feature has low ROI
- **Complexity**: Adds another event source to maintain (Git branch reading, JSONL parsing)

#### Neutral

- **Optional feature**: Doesn't affect users who don't use Entire (zero impact on core flows)
- **One-way import**: Spec Kitty imports from Entire, but doesn't export to Entire format (asymmetric)
- **Storage remains PostgreSQL**: Imported events stored in PostgreSQL (not Git), maintains SaaS architecture

### Confirmation

**Success Metrics**:
- **Compatibility**: Successfully import 100+ Entire checkpoints without errors
- **Adoption**: 5-10% of Spec Kitty users also use Entire (indicates interoperability value)
- **Partnership**: Initiate discussions with Entire team (if they gain traction: 5K+ GitHub stars, funding)
- **Format stability**: Entire's checkpoint format remains stable (no breaking changes in 6 months)

**Validation Timeline**:
- **Month 1**: Implement EntireCheckpointReader, test with sample Entire repository
- **Month 2**: Release CLI command (`spec-kitty import-sessions --source entire`)
- **Month 3-6**: Monitor adoption, format stability, partnership signals

**Confidence Level**: **MEDIUM** (6/10)
- **High confidence**: Interoperability is valuable (users can combine tools)
- **Medium confidence**: Entire will gain traction (Tier 1 threat, but early stage)
- **Low confidence**: Format will remain stable (no version control guarantees from Entire)
- **Mitigation**: Import is optional, can deprecate if Entire fails or format breaks

## Pros and Cons of the Options

### Build EntireCheckpointReader (Import Only) - Chosen

**Description**: Read Entire checkpoints from Git branch, convert to Spec Kitty events, store in PostgreSQL.

**Pros:**

- Preserves SaaS architecture (PostgreSQL event log)
- Enables interoperability (users can use both tools)
- Partnership optionality (acquisition path preserved)
- Focus on strengths (leverage Entire's infrastructure)
- Low risk (optional feature, doesn't affect core)
- Strategic positioning ("orchestration vs infrastructure")

**Cons:**

- Maintenance burden (keep reader compatible)
- Dependency risk (if Entire shuts down)
- Format lock-in (coupled to Entire's JSONL)
- Limited value if Entire fails
- Complexity (another event source)

### Adopt Git-Native Storage (Replace PostgreSQL)

**Description**: Replace PostgreSQL event log with Git-native storage (Entire's approach).

**Pros:**

- Full compatibility with Entire (same storage model)
- Simpler infrastructure (no database required)
- Version control for events (Git history)

**Cons:**

- **Contradicts ADR 2026-02-09-1** (PostgreSQL event log foundation)
- **Breaks team SaaS**: Cannot query events efficiently (no real-time dashboard)
- **No multi-tenancy**: Git branches don't provide tenant isolation
- **No CRDT**: Cannot implement conflict resolution (requires database transactions)
- **No WebSocket sync**: Cannot subscribe to event streams
- **Wrong architecture**: Git-native is for session history (Entire's use case), NOT orchestration (Spec Kitty's use case)

### Build Own Session Capture

**Description**: Duplicate Entire's session capture infrastructure in Spec Kitty.

**Pros:**

- Full control (no dependency on Entire)
- Native integration (no import step)

**Cons:**

- **Scope creep**: Session capture is NOT Spec Kitty's core competency (we focus on orchestration)
- **Duplication of effort**: Entire already solves this (990 commits, production-ready)
- **Resource drain**: Engineering time better spent on orchestration features
- **Competitive risk**: Competing with Entire on their strength (session capture) instead of ours (orchestration)

### Ignore Entire (No Compatibility)

**Description**: Build nothing related to Entire, compete head-to-head.

**Pros:**

- Zero maintenance burden (no compatibility code)
- Simple (no additional complexity)

**Cons:**

- **Misses partnership opportunity**: No acquisition path if Entire gains traction
- **Forces user choice**: Users must pick Entire OR Spec Kitty (not both)
- **Perception risk**: "Spec Kitty ignores competitors" (not collaborative)
- **Lost learning**: Entire's session capture patterns could inform our architecture

## More Information

**References**:
- Competitive analysis: `competitive/tier-1-threats/entire-io/THREAT-ASSESSMENT.md`, `VISION-COMPARISON.md`
- Entire.io codebase: https://github.com/entireio/cli (checkpoint storage implementation)
- Product requirements: `product-ideas/prd-agent-orchestration-integration-v1.md` (AD-003)
- Integration spec: `competitive/tier-1-threats/entire-io/INTEGRATION-SPEC.md` (Section 1.1)

**Implementation Files**:
- `spec_kitty_events/sources/entire_checkpoint.py` - EntireCheckpointReader class
- `specify_cli/commands/import_sessions.py` - CLI command for import

**Related ADRs**:
- ADR-2026-02-09-1: Canonical WP Status Model (PostgreSQL event log - this ADR aligns with that decision)
- ADR-2026-02-11-4: Agent Attribution Tracking (Entire's attribution data feeds into this)
- ADR-2026-01-31-1: Vendor spec-kitty-events (event library available for checkpoint reading)

**Entire.io Checkpoint Format** (reference):
```jsonl
{
  "checkpoint_id": "2026-02-11-abc123",
  "timestamp": "2026-02-11T10:30:00Z",
  "agent": "claude-code",
  "strategy": "manual-commit",
  "transcript": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "file_changes": [{"path": "src/main.py", "diff": "...", "status": "modified"}],
  "git_metadata": {"branch": "main", "commit_sha": "abc123", "parent_sha": "def456"}
}
```

**CLI Usage Example**:
```bash
spec-kitty import-sessions \
  --source entire \
  --checkpoint-branch entire/checkpoints/v1 \
  --project-id <project-id> \
  --start-date 2026-01-01 \
  --end-date 2026-02-11

# Output:
# Importing Entire.io checkpoints...
# Found 42 checkpoints on branch 'entire/checkpoints/v1'
# Imported 42 events successfully.
# Events visible in spec-kitty dashboard under project <project-id>.
```

**Partnership/Acquisition Scenarios**:

**Scenario A: Entire gains traction** (10K+ stars, funding, enterprise customers)
- Action: Reach out to Entire team (Stefan Haubold, Alex Ong)
- Proposal: Integration partnership ("Entire infrastructure + Spec Kitty orchestration")
- Acquisition estimate: $10-30M (depending on traction, revenue)

**Scenario B: Entire format breaks** (breaking changes to checkpoint JSONL)
- Action: Version EntireCheckpointReader (detect format version, handle multiple)
- Fallback: Deprecate import if maintenance burden too high

**Rollback Plan**:
- If format breaks repeatedly: Deprecate import feature (remove from CLI)
- If Entire shuts down: Archive feature (no longer maintained)
- Zero impact on core Spec Kitty flows (import is optional)
