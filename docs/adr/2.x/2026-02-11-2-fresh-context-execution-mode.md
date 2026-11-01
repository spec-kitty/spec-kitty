---
title: Fresh Context Execution Mode for Long-Running Work Packages
description: An opt-in mode that resets an agent's context at every subtask boundary, trading spawn overhead for less hallucination drift on long-running work packages.
status: Proposed
date: '2026-02-11'
doc_status: active
kind: ADR
updated: '2026-02-11T00:00:00Z'
---

## Context and Problem Statement

Spec Kitty's current orchestrator spawns one AI agent per work package (WP) with persistent context throughout the entire implementation. The agent reads the WP prompt, implements all subtasks sequentially, and maintains the same context window from start to finish.

This works well for simple WPs (2-3 subtasks, <30 minutes execution), but creates quality problems for complex WPs:

1. **Context bloat**: Long-running WPs accumulate large context windows (prompts, responses, tool calls, file contents)
2. **Hallucination accumulation**: Later subtasks may hallucinate based on earlier mistakes that remain in context
3. **Context window exhaustion**: Very long WPs risk hitting model context limits (even with 1M token windows)
4. **Stale reasoning**: Agent's reasoning from subtask 1 may be outdated by subtask 10
5. **Error propagation**: Bugs introduced in subtask 3 compound in subtasks 4-10 if agent doesn't recognize the mistake

Competitive analysis of Swarm (mtomcal/swarm) demonstrates that "Ralph mode" - spawning fresh agents per iteration - prevents these quality issues. Each iteration gets clean context, focusing only on the current task without baggage from previous iterations.

As Spec Kitty moves toward more sophisticated orchestration (Feature 013: cross-repo convergence), WPs will become larger and more complex. Fresh context execution becomes increasingly important for quality.

## Decision Drivers

* **Quality**: Prevent hallucination accumulation in long-running work
* **Clarity**: Each subtask gets fresh reasoning, not influenced by prior subtask baggage
* **Reliability**: Reduce risk of context window exhaustion errors
* **Flexibility**: Optional mode allows users to choose based on WP complexity
* **Proven pattern**: Swarm's Ralph mode validates this approach
* **Performance trade-off**: Slight overhead (spawn/terminate per subtask) vs improved quality
* **Debugging**: Fresh context makes it easier to isolate which subtask introduced a bug

## Considered Options

* **Option 1**: Fresh context per subtask (Ralph-style) - chosen
* **Option 2**: Fresh context per WP (too granular)
* **Option 3**: Persistent context (current state)
* **Option 4**: Hybrid approach (context summary between subtasks)

## Decision Outcome

**Chosen option:** "Fresh context per subtask (Ralph-style)", because:

1. **Quality improvement**: Prevents hallucination accumulation (validated by Swarm's production use)
2. **Proven pattern**: Swarm's 235 commits demonstrate this works in practice
3. **Flexibility**: Optional flag allows users to choose persistent (fast) vs fresh (quality)
4. **Clear boundaries**: Subtasks are natural boundaries for context reset
5. **Debugging benefit**: Easier to isolate bugs (each subtask's context is isolated)
6. **Acceptable overhead**: Spawn/terminate adds ~2-3 seconds per subtask (vs hallucination risk)

### Consequences

#### Positive

* **Quality**: Fewer hallucinations in later subtasks (fresh reasoning per subtask)
* **Reliability**: No context window exhaustion (each subtask starts with clean context)
* **Clarity**: Agent focuses on current subtask, not confused by prior subtask history
* **Debugging**: Bug isolation easier (each subtask's execution is independent)
* **Flexibility**: Users choose mode based on WP complexity (simple = persistent, complex = fresh)
* **Competitive differentiation**: Quality improvement vs competitors without this pattern

#### Negative

* **Performance**: Slower execution (spawn/terminate overhead ~2-3 seconds per subtask)
  * Example: 10-subtask WP adds 20-30 seconds total overhead
* **Lost continuity**: Agent doesn't learn from prior subtask execution (only reads results, not reasoning process)
* **Complexity**: Adds execution mode dimension to orchestrator (more configuration, more testing)
* **Resource usage**: More Docker container churn (if sandboxed mode enabled)

#### Neutral

* **Optional mode**: Not a breaking change (default remains persistent for backward compatibility)
* **Subtask boundaries**: Requires well-defined subtasks (which is already best practice in Spec Kitty)
* **Prompt engineering**: Requires building focused subtask prompts (include prior results as read-only context)

### Confirmation

**Success Metrics**:
* **Quality**: Hallucination rate reduced in fresh mode vs persistent (measure: code review rejection rate)
* **Adoption**: 20-30% of WPs use fresh mode (indicates users find value)
* **Performance**: Overhead <10% of total execution time (spawn/terminate cost acceptable)
* **Reliability**: Zero context window exhaustion errors in fresh mode

**Validation Timeline**:
* **Week 1-2**: Implementation + unit tests
* **Week 3-4**: Integration testing with complex WPs (10+ subtasks)
* **Week 5-6**: A/B testing (same WP, persistent vs fresh) to measure quality delta
* **Month 2-3**: Monitor adoption rate, adjust default if >50% adoption

**Confidence Level**: **HIGH** (8/10)
* Validated by Swarm's Ralph mode production use
* Clear quality benefit (fresh reasoning)
* Low risk (optional mode, clear rollback path)
* Main uncertainty: Will users adopt, or stick with persistent for speed?

## Pros and Cons of the Options

### Fresh Context Per Subtask (Chosen)

**Description**: Spawn fresh agent for each subtask, terminate after completion. Ralph-style execution from Swarm.

**Pros:**

* Prevents hallucination accumulation (fresh reasoning per subtask)
* No context window exhaustion risk (clean context each time)
* Clear focus (agent not confused by prior subtask history)
* Debugging benefit (isolate bugs to specific subtask)
* Proven by Swarm's production use (validates quality benefit)
* Optional mode (users choose based on needs)

**Cons:**

* Performance overhead (~2-3 seconds spawn/terminate per subtask)
* Lost continuity (agent doesn't learn from prior execution, only reads results)
* Implementation complexity (new execution mode in scheduler)
* More Docker churn (if sandboxed mode enabled)

### Fresh Context Per WP

**Description**: Spawn fresh agent for each WP iteration (not per subtask).

**Pros:**

* Simpler than per-subtask (fewer iterations)
* Prevents cross-WP context bloat

**Cons:**

* **Too granular for quality benefit**: WPs are already independent, context bloat is within-WP problem
* Doesn't solve hallucination accumulation (still accumulates across subtasks within WP)
* Adds overhead without addressing root problem

### Persistent Context (Current State)

**Description**: Continue using one agent per WP with persistent context.

**Pros:**

* Fastest execution (zero spawn/terminate overhead)
* Simplest implementation (no changes needed)
* Continuity preserved (agent learns from prior subtasks)

**Cons:**

* **Quality risk**: Hallucination accumulation in long-running WPs
* **Reliability risk**: Context window exhaustion in very long WPs
* **Unclear focus**: Agent may be confused by large context in later subtasks
* **Debugging harder**: Bug could originate in any prior subtask

### Hybrid Approach (Context Summary Between Subtasks)

**Description**: Same agent, but provide context summary between subtasks (compress prior execution into summary).

**Pros:**

* No spawn/terminate overhead (same agent instance)
* Reduces context bloat (summary instead of full history)
* Preserves continuity (same agent learns patterns)

**Cons:**

* **Complex**: Requires building good summarization (which summaries? how much detail?)
* **Still risks hallucination**: Summary may include hallucinated information from prior subtasks
* **Unclear benefit**: Partial solution (reduces but doesn't eliminate context bloat)
* **Unproven**: No production validation (unlike Swarm's Ralph mode)

## More Information

**References**:
* Swarm architecture analysis: `spec-kitty-planning/competitive/tier-1-threats/entire-io/SWARM-COMPARISON.md` (Section "Ralph Mode")
* Swarm codebase: https://github.com/mtomcal/swarm (see Ralph mode implementation in `loop.sh`)
* **Cursor scaling research**: https://cursor.com/blog/scaling-agents
  * Key quote: "Prompts matter more than the harness and models"
  * Finding: Role-specific prompts prevent agent drift and maintain focus over long periods
  * Validation: Focused prompts per task improve quality more than infrastructure complexity
* Product requirements: `spec-kitty-planning/product-ideas/prd-agent-orchestration-integration-v1.md` (AD-002)
* Integration spec: `spec-kitty-planning/competitive/tier-1-threats/entire-io/INTEGRATION-SPEC.md` (Section 2.2)

**Implementation Files**:
* `orchestrator/scheduler.py` - Add `ExecutionMode` enum, `execute_wp_fresh_context()` function
* `orchestrator/executor.py` - Support subtask-scoped agent spawning
* WP prompt templates - Build focused subtask prompts (include prior results as read-only context)

**Related ADRs**:
* ADR-2026-02-09-2: WP Lifecycle State Machine (foundational state machine, fresh context mode extends with execution dimension)
* ADR-2026-02-11-1: Docker-Sandboxed Agent Execution (complementary safety pattern)
* ADR-2026-01-23-6: Config-Driven Agent Management (agent configuration foundation)

**CLI Usage Examples**:
```bash
# Default: persistent context (backward compatible)
spec-kitty implement WP03

# Opt-in: fresh context per subtask
spec-kitty implement WP03 --fresh-context

# WP metadata (records which mode was used)
# WP03-implementation.md frontmatter:
# execution_mode: fresh_per_subtask
```

**Quality Measurement Plan**:
* Track: Code review rejection rate (persistent vs fresh mode)
* Track: Hallucination reports (manual review of agent outputs)
* A/B test: Same WP executed twice (once persistent, once fresh) - compare quality

**Rollback Plan**:
* If quality benefit not observed: Keep as opt-in, don't make default
* If performance overhead too high: Adjust implementation (cache agent state? reduce spawn time?)
* Configuration: `execution_mode: persistent` in WP frontmatter to opt-out
