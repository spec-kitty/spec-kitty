---
title: Docker-Sandboxed Agent Execution
description: Proposes running agents inside containers with memory, CPU, and process limits so a runaway agent cannot take the orchestrator or the host machine down with it.
status: Proposed
date: '2026-02-11'
doc_status: active
kind: ADR
updated: '2026-02-11T00:00:00Z'
---

## Context and Problem Statement

Spec Kitty's current orchestrator runs AI agents directly on the host system without resource limits. This creates safety risks for autonomous agent execution:

1. **Memory exhaustion**: Runaway agents can consume all available RAM, crashing the orchestrator or system
2. **CPU starvation**: Infinite loops or compute-intensive operations can monopolize CPU
3. **Fork bombs**: Agents can spawn unlimited child processes, exhausting PID limits
4. **File system access**: Agents have unrestricted access to host file system beyond intended working directory
5. **Network access**: Agents can make arbitrary network requests without controls

Competitive analysis of Swarm (mtomcal/swarm) demonstrates that Docker sandboxing with memory/CPU/PID limits is an effective safety pattern for parallel AI agent execution. As Spec Kitty moves toward autonomous multi-agent orchestration (Feature 013: cross-repo convergence), these safety concerns become critical.

Additionally, Entire.io (Tier 1 competitive threat) is building multi-agent orchestration. If they adopt similar safety patterns before Spec Kitty, it creates a perception gap on production-readiness.

## Decision Drivers

* **Safety**: Prevent runaway agents from affecting system stability
* **Isolation**: Ensure agents cannot access unintended resources (files, network, processes)
* **Reproducibility**: Provide consistent execution environment across different systems
* **Industry standard**: Docker is ubiquitous, well-understood, well-tested
* **Operational experience**: Swarm's production use validates this approach
* **Production scale validation**: Cursor research demonstrates lock-based coordination fails at scale ("20 agents slow to 2-3 throughput"); isolation via containers enables hundreds of concurrent agents
* **Competitive parity**: Match or exceed Entire.io's agent safety capabilities
* **User trust**: Demonstrate production-grade safety for enterprise adoption
* **Debugging**: Opt-out capability for local debugging without overhead

## Considered Options

* **Option 1**: Docker containers with resource limits (chosen)
* **Option 2**: Linux cgroups directly (no container)
* **Option 3**: No sandboxing (current state)
* **Option 4**: VM-based isolation

## Decision Outcome

**Chosen option:** "Docker containers with resource limits", because:

1. **Industry standard**: Docker is ubiquitous in software development, well-understood by engineers
2. **Proven pattern**: Swarm's production use with 235 commits validates effectiveness
3. **Comprehensive isolation**: Memory, CPU, PID, network, file system all controlled
4. **Minimal changes**: Orchestrator modifications are localized to `executor.py`
5. **Debugging flexibility**: Opt-out flag (`--no-sandbox`) allows local debugging
6. **Enterprise credibility**: Demonstrates production-grade safety for enterprise sales

### Consequences

#### Positive

* **Safety**: Prevents OOM crashes, CPU starvation, fork bombs from affecting orchestrator or system
* **Isolation**: Agents cannot access host file system beyond mounted working directory
* **Reproducibility**: Same Docker image ensures consistent environment across developer machines, CI, production
* **Resource monitoring**: Docker stats provide real-time visibility into agent resource usage
* **Security**: Container security options (`--no-new-privileges`) prevent privilege escalation
* **Trust**: Enterprise customers see production-grade safety (compliance, governance requirement)
* **Competitive parity**: Matches Swarm's safety model, exceeds Entire.io (which has no sandboxing currently)

#### Negative

* **Overhead**: Container spawn time adds ~1-2 seconds per agent (vs direct spawn)
* **Complexity**: Requires Docker installed on all systems (developer machines, CI, production)
* **Disk space**: Docker images consume disk space (~500MB for base Python image)
* **Network complexity**: Container networking adds layer of indirection for debugging
* **Learning curve**: Developers unfamiliar with Docker need to learn container concepts

#### Neutral

* **Opt-out available**: `--no-sandbox` flag allows running agents on host for debugging (trade-off: safety vs speed)
* **Image maintenance**: Requires maintaining `Dockerfile.agent-sandbox` (but this is standard DevOps practice)
* **Configuration surface**: Docker config (memory_limit, cpu_limit, etc.) adds configuration options to manage

### Confirmation

**Success Metrics**:
* **Performance**: Container overhead <10% (measured: agent spawn time, execution time)
* **Reliability**: Zero OOM crashes from runaway agents in production (vs current state: occasional crashes)
* **Adoption**: 95%+ of agent executions use sandboxed mode (opt-out rare, only for debugging)
* **Operational**: Docker image build/deploy works in CI/CD pipeline

**Validation Timeline**:
* **Week 1-2**: Implementation + unit tests
* **Week 3-4**: Integration testing with real WP executions
* **Week 5-6**: Production rollout (sandboxed as default)
* **Month 2-3**: Monitor metrics, adjust limits if needed

**Confidence Level**: **HIGH** (9/10)
* Validated by Swarm's production use
* Docker is proven, stable technology
* Minimal risk, clear rollback path (opt-out flag)

## Pros and Cons of the Options

### Docker Containers (Chosen)

**Description**: Run agents in Docker containers with `--memory`, `--cpus`, `--pids-limit` flags.

**Pros:**

* Industry standard solution (Docker ubiquitous)
* Comprehensive isolation (memory, CPU, PID, network, file system)
* Proven by Swarm's production use (235 commits, battle-tested)
* Minimal code changes (localized to executor.py)
* Real-time monitoring via `docker stats`
* Security hardening options (`--no-new-privileges`, `--security-opt`)
* Debugging flexibility (opt-out flag available)

**Cons:**

* Requires Docker installed (dependency)
* Container spawn overhead (~1-2 seconds)
* Docker image storage (~500MB)
* Container networking complexity
* Learning curve for Docker-unfamiliar developers

### Linux cgroups Directly

**Description**: Use Linux cgroups v2 API to set resource limits without containers.

**Pros:**

* No Docker dependency (lower barrier to entry)
* Slightly faster (no container overhead)
* More direct control over resource limits

**Cons:**

* Linux-only (not portable to macOS for local development)
* More complex implementation (cgroups API is lower-level than Docker CLI)
* No file system isolation (agents still access host file system)
* No network isolation
* Less familiar to developers (Docker is more common)
* No standard image management (harder to ensure consistent environment)

### No Sandboxing (Current State)

**Description**: Continue running agents directly on host without resource limits.

**Pros:**

* Zero overhead (fastest possible execution)
* Simplest implementation (no changes needed)
* No dependencies (works everywhere Python works)

**Cons:**

* **Unsafe**: Runaway agents can crash orchestrator or system
* **No isolation**: Agents can access any file on host
* **No resource limits**: Agents can consume unlimited memory, CPU
* **Not production-ready**: Enterprise customers will question safety
* **Competitive risk**: Perception gap vs competitors with sandboxing

### VM-Based Isolation

**Description**: Run agents in lightweight VMs (e.g., Firecracker, gVisor).

**Pros:**

* Strongest isolation (kernel-level separation)
* Security benefits (VM escape harder than container escape)

**Cons:**

* **Too heavy**: VM startup time 5-10 seconds (vs 1-2 seconds for containers)
* **Complex**: VM management much more complex than Docker
* **Resource intensive**: VMs consume more memory than containers
* **Overkill**: Agent code is not malicious, just potentially buggy; VM-level isolation unnecessary
* **Less familiar**: Firecracker/gVisor less common than Docker

## More Information

**References**:
* Swarm architecture analysis: `spec-kitty-planning/competitive/tier-1-threats/entire-io/SWARM-COMPARISON.md`
* Swarm codebase: https://github.com/mtomcal/swarm (see Docker sandbox implementation)
* **Cursor scaling research**: https://cursor.com/blog/scaling-agents
  * Key finding: Lock-based coordination creates severe bottlenecks (20 agents → 2-3 effective throughput)
  * Validation: Hundreds of concurrent workers require process isolation (not locks)
  * Conclusion: Isolation via containers enables scale; locking prevents it
* Product requirements: `spec-kitty-planning/product-ideas/prd-agent-orchestration-integration-v1.md` (AD-001)
* Integration spec: `spec-kitty-planning/competitive/tier-1-threats/entire-io/INTEGRATION-SPEC.md` (Section 2.1)

**Implementation Files**:
* `orchestrator/executor.py` - Add `spawn_agent_sandboxed()` method
* `orchestrator/config.py` - Add `DockerSandboxConfig` class
* `docker/Dockerfile.agent-sandbox` - Base image for agent execution

**Related ADRs**:
* ADR-2026-02-11-2: Fresh Context Execution Mode (complementary safety pattern)
* ADR-2026-01-23-6: Config-Driven Agent Management (agent configuration foundation)

**Rollback Plan**:
* If Docker overhead unacceptable: Use `--no-sandbox` flag globally (environment variable)
* If Docker unavailable on system: Automatic fallback to direct spawn (with warning)
* Configuration: `docker_sandbox.enabled = false` in config/docker_sandbox.yaml
