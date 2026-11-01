---
title: Task-Tracker-Agnostic Connector Architecture
description: Treats Jira as one connector behind a shared interface rather than an architectural assumption, keeping Linear, Asana, and GitHub Issues equally first-class.
status: Proposed
doc_status: active
kind: ADR
date: '2026-02-11'
---

## Context and Problem Statement

During Feature 014 (Acquisition Strategy & Competitive Analysis), **Jira** appeared frequently in competitive positioning documents as the "Ideal Task Tracker Profile" for ICP (Ideal Customer Profile) analysis. This led to potential confusion about Jira's architectural role in Spec Kitty:

**Business/Positioning Context** (Feature 014):
* Jira is widely used in Atlassian ecosystem (250K+ customers)
* Atlassian is primary acquisition target ($10-30M estimated acquisition price for Spec Kitty)
* Many enterprise customers use Jira for project management
* Jira integration is valuable for enterprise sales positioning

**Architectural Risk**:
* Confusion: Is Jira architecturally special? Should core models (Event, WorkPackage) have Jira-specific fields?
* Vendor lock-in: If Jira assumptions hardcoded in event log, state machine, or sync protocol, we lose flexibility
* Market risk: Task tracker landscape is diverse (Linear, Asana, Monday, ClickUp, GitHub Issues) - cannot assume Jira dominance
* Future-proofing: New task trackers will emerge; architecture must be agnostic

**Key Question**: Is Jira (and task trackers generally) CORE architecture or EXTERNAL integration?

**Current State**: No architectural decisions documented on task tracker integration philosophy.

## Decision Drivers

* **Vendor independence**: Spec Kitty must not be architecturally tied to any single task tracker
* **Market flexibility**: Different customers use different tools (Jira, Linear, Asana, Monday, ClickUp, GitHub Issues)
* **Future-proofing**: Task tracker market evolves; new tools emerge (e.g., Linear launched 2019, now major player)
* **Acquisition positioning**: Ironically, being Jira-agnostic is MORE valuable to Atlassian (demonstrates platform, not point solution)
* **Clear separation**: Business/ICP decisions (Jira is ideal customer profile) vs Architecture (Jira is one connector among equals)
* **Integration patterns**: Follow industry best practice (abstraction layer for external services)

## Considered Options

* **Option 1**: Task-tracker-agnostic connector architecture (chosen)
* **Option 2**: Jira-first architecture (Jira special treatment in core models)
* **Option 3**: No task tracker integration (miss enterprise value)
* **Option 4**: Manual integration only (limits automation)

## Decision Outcome

**Chosen option:** "Task-tracker-agnostic connector architecture with unified `TaskTrackerConnector` interface", because:

1. **Vendor independence**: No architectural lock-in to Jira or any single tracker
2. **Market flexibility**: Supports diverse customer tool preferences (Jira, Linear, Asana, Monday, ClickUp, GitHub Issues)
3. **Future-proofing**: New task trackers easily added via connector interface
4. **Acquisition value**: Atlassian values platform architecture (broader than just Jira integration)
5. **Clear separation**: Jira is business/ICP focus (customer targeting), NOT architectural dependency
6. **Industry pattern**: Follows Zapier/n8n model (unified connector abstraction)

**Implementation**: Create unified `TaskTrackerConnector` abstract base class in `integrations/task_tracker.py`. All task trackers (Jira, Linear, Asana, Monday, ClickUp, GitHub Issues) implement this interface with EQUAL priority. NO Jira-specific fields in core models (Event, WorkPackage, Project).

**Jira's Role - Clarified**:
* **Business/ICP**: "Ideal Task Tracker Profile" for customer targeting, acquisition positioning (Feature 014)
* **Architecture**: One connector among many, equal priority with Linear, Asana, etc.
* **Why it appears often**: Many target customers use Atlassian ecosystem (business reason), NOT architectural special treatment

### Consequences

#### Positive

* **Vendor independence**: No lock-in to Jira or any tracker (customer flexibility)
* **Market coverage**: Serve customers with ANY task tracker (broader TAM)
* **Future-proof**: New trackers (e.g., next Linear/Notion) easily added via connector
* **Acquisition value**: Atlassian sees platform (broader value) vs Jira point solution
* **Clean architecture**: Core models (Event, WorkPackage) have no task-tracker-specific fields
* **Competitive advantage**: Differentiate from competitors locked to single tracker

#### Negative

* **Abstraction cost**: Unified interface requires upfront design (more complex than single-tracker integration)
* **Lowest common denominator**: Interface may not expose tracker-specific features (Jira JQL, Linear cycles)
* **Testing complexity**: Must test against multiple trackers (Jira, Linear, Asana, etc.)
* **Documentation burden**: Need docs for each tracker integration (setup, auth, field mapping)

#### Neutral

* **Jira still important**: Business/ICP focus on Jira is CORRECT (Atlassian customers are ideal), just not architecturally special
* **Connector priority**: All trackers equal architecturally, but Jira may get marketing/sales priority (business decision)
* **Implementation order**: Can implement Jira connector first (business priority), then Linear, Asana (phased rollout)

### Confirmation

**Success Metrics**:
* **Architectural cleanliness**: Zero Jira-specific fields in core models (Event, WorkPackage, Project)
* **Connector parity**: Jira, Linear, GitHub Issues connectors all implement same interface (no special cases)
* **Market coverage**: 3+ task tracker integrations shipped (Jira, Linear, GitHub Issues)
* **Customer flexibility**: Customers can switch trackers without re-architecting Spec Kitty integration
* **Acquisition value**: Atlassian recognizes platform value (demonstrated by multi-tracker support)

**Validation Timeline**:
* **Month 1**: Design `TaskTrackerConnector` interface (abstract methods, common data model)
* **Month 2**: Implement Jira connector (first implementation, validates interface)
* **Month 3**: Implement Linear connector (proves interface is tracker-agnostic)
* **Month 4**: Implement GitHub Issues connector (third tracker, confirms pattern)
* **Month 5-6**: Customer validation (users with different trackers successfully integrate)

**Confidence Level**: **HIGH** (9/10)
* Follows industry best practice (connector abstraction)
* Clear separation of business (Jira focus) vs architecture (tracker-agnostic)
* Proven pattern (Zapier, n8n use similar connector model)
* Low risk (abstraction adds complexity but prevents vendor lock-in)

## Pros and Cons of the Options

### Task-Tracker-Agnostic Architecture (Chosen)

**Description**: Unified `TaskTrackerConnector` interface, all trackers equal priority architecturally.

**Pros:**

* **Vendor independence**: No lock-in, customer flexibility
* **Market coverage**: Serve customers with ANY tracker
* **Future-proof**: New trackers easily added
* **Acquisition value**: Platform > point solution (broader value to Atlassian)
* **Clean architecture**: Core models have no tracker-specific fields
* **Competitive advantage**: Differentiate from single-tracker competitors

**Cons:**

* **Abstraction cost**: Upfront design complexity
* **Lowest common denominator**: May not expose tracker-specific features
* **Testing complexity**: Must test multiple trackers
* **Documentation burden**: Docs for each tracker

### Jira-First Architecture

**Description**: Jira gets special treatment in core models (e.g., WorkPackage has jira_issue_id field).

**Pros:**

* **Simpler initially**: Direct Jira integration, no abstraction
* **Jira-specific features**: Can expose JQL, custom fields, Jira workflows
* **Faster time-to-market**: Ship Jira integration sooner (no abstraction design)

**Cons:**

* **Vendor lock-in**: Architecture tied to Jira (hard to support other trackers)
* **Market limitation**: Customers with Linear, Asana, etc. cannot adopt Spec Kitty
* **Future fragility**: If Jira declines or new tracker dominates, architecture is wrong
* **Acquisition risk**: Atlassian may see point solution (lower value) vs platform
* **Architectural debt**: Must refactor to support other trackers (costly migration)

### No Task Tracker Integration

**Description**: Spec Kitty has no task tracker integration (manual workflows only).

**Pros:**

* **Simple**: No integration complexity
* **Tracker-agnostic by default**: Users can use any tracker manually

**Cons:**

* **Misses enterprise value**: Task tracker integration is key enterprise requirement (bidirectional sync, automation)
* **Competitive gap**: Competitors with integrations win enterprise deals
* **Manual workflows**: Users must manually copy data between Spec Kitty and tracker (friction)

### Manual Integration Only

**Description**: Users manually export/import between Spec Kitty and trackers (no automated sync).

**Pros:**

* **Simpler than automated sync**: No real-time sync complexity
* **User control**: Users decide when/what to sync

**Cons:**

* **Friction**: Manual export/import is tedious (low adoption)
* **Stale data**: Manual sync means data drifts out of sync
* **Competitive gap**: Automated sync is expected feature (Zapier, n8n, etc.)

## More Information

**References**:
* Feature 014: `research/014-acquisition-strategy-and-competitive-analysis/` (Jira as ICP, Atlassian acquisition target)
* Product requirements: `product-ideas/prd-agent-orchestration-integration-v1.md` (AD-006, Section "Task Tracker Integration Philosophy")
* Integration spec: `competitive/tier-1-threats/entire-io/INTEGRATION-SPEC.md` (Section "Layer 4: External Integrations")

**Implementation Files**:
* `integrations/task_tracker.py` - TaskTrackerConnector abstract base class
* `integrations/jira_connector.py` - JiraConnector implementation
* `integrations/linear_connector.py` - LinearConnector implementation
* `integrations/github_issues_connector.py` - GitHubIssuesConnector implementation
* `config/task_trackers.yaml` - Configuration for all trackers

**Related ADRs**:
* None (this is first ADR on task tracker integration philosophy)
* Future: Specific ADRs for each connector implementation (e.g., ADR for Jira OAuth flow, Linear GraphQL integration)

**TaskTrackerConnector Interface** (sketch):
```python
from abc import ABC, abstractmethod
from typing import Dict, List

class TaskTrackerConnector(ABC):
    """Abstract base class for task tracker integrations."""

    @abstractmethod
    async def fetch_issue(self, issue_id: str) -> Dict:
        """Fetch issue details from task tracker."""
        pass

    @abstractmethod
    async def create_spec_from_issue(self, issue_id: str) -> Path:
        """Generate spec.md from task tracker issue."""
        pass

    @abstractmethod
    async def sync_wp_status_to_issue(self, wp_id: str, status: str):
        """Update issue status based on WP status."""
        pass

    @abstractmethod
    async def sync_issue_to_wp(self, issue_id: str) -> str:
        """Create WP from issue (bidirectional sync)."""
        pass

# All trackers implement this interface (equal priority)
class JiraConnector(TaskTrackerConnector):
    # ... Jira-specific implementation

class LinearConnector(TaskTrackerConnector):
    # ... Linear-specific implementation

class GitHubIssuesConnector(TaskTrackerConnector):
    # ... GitHub-specific implementation
```

**Configuration Example** (`config/task_trackers.yaml`):
```yaml
task_trackers:
  jira:
    enabled: true
    server_url: "https://company.atlassian.net"
    credentials: "env:JIRA_API_TOKEN"

  linear:
    enabled: true
    api_key: "env:LINEAR_API_KEY"

  github:
    enabled: true
    token: "env:GITHUB_TOKEN"

  # All trackers equal priority in config
```

**CLI Usage Examples**:
```bash
# Generate spec from Jira issue
spec-kitty specify --from-jira PROJECT-123

# Generate spec from Linear issue
spec-kitty specify --from-linear ISSUE-456

# Generate spec from GitHub issue
spec-kitty specify --from-github myorg/myrepo#789

# Sync WP status to any tracker
spec-kitty sync WP03 --to-jira PROJECT-123
spec-kitty sync WP03 --to-linear ISSUE-456
spec-kitty sync WP03 --to-github myorg/myrepo#789
```

**Jira's Business Role vs Architectural Role**:

| Context | Jira's Role | Rationale |
|---------|-------------|-----------|
| **Business/ICP** (Feature 014) | **"Ideal Task Tracker Profile"** | Many enterprises use Atlassian; Jira customers are ideal acquisition targets |
| **Marketing/Sales** | **Primary messaging focus** | Lead with Jira integration (appeals to Atlassian ecosystem) |
| **Architecture** (this ADR) | **One connector among equals** | No Jira-specific fields in core models; equal priority with Linear, Asana, etc. |
| **Implementation Order** | **Implement first** (Phase 3) | Business priority (most enterprise customers), NOT architectural priority |
| **Documentation** | **Featured prominently** | Jira docs on homepage (appeals to target customer), but other trackers equally documented |

**Acquisition Implications** (Atlassian):
* **Platform value**: Multi-tracker support demonstrates Spec Kitty is platform (broader appeal), not Jira point solution
* **Integration showcase**: Jira connector demonstrates integration quality (Atlassian sees example of what they could build)
* **Non-threatening**: Being tracker-agnostic reduces perception of "only valuable for Jira" (broader strategic value to Atlassian)
* **Market validation**: If Spec Kitty succeeds with multiple trackers, validates TAM beyond just Jira users

**Rollback Plan**:
* If abstraction is wrong: Can add tracker-specific fields to Event.payload (JSONB is flexible)
* If Jira features needed: JiraConnector can have Jira-specific methods (beyond interface minimum)
* Configuration: Can mark trackers as "primary" in config (business priority) while keeping architecture equal
