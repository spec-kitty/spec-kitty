---
title: 'ADR: replace charter reads and writes through a staged Java service strangler'
description: 'Define the staged transition from the Python charter implementation to a per-worktree Java read service and, later, Java write adapters.'
status: Proposed
date: '2026-10-03'
---
# Replace charter reads and writes through a staged Java service strangler

**Status:** Proposed

**Date:** 2026-10-03

**Deciders:** Stijn Dejongh (operator). Analysis by the charter-service architecture review squad.

**Technical Story:** the charter-read strangler step under
[#645](https://github.com/spec-kitty/spec-kitty/issues/645) / 4.x Work, distinct
from the Mission Status Read facet in
[#5528](https://github.com/spec-kitty/spec-kitty/issues/5528); later CLI 4.x
stable work under
[#2519](https://github.com/spec-kitty/spec-kitty/issues/2519) for write migration.
Neither item belongs to milestone 11 or gates the 4.0.0 release.

---

## Context and Problem Statement

Charter guidance is currently loaded, parsed, merged, activated, and resolved in Python for
each CLI or agent interaction. Repeated process startup and graph construction are
hypothesized to make high-frequency reads expensive, but that has not been established by
an end-to-end benchmark. Independently of performance, the current shape makes the
capability harder to offer consistently through CLI, REST, and MCP.

The 4.x direction is a local, per-worktree Java charter service reached through a Python
charter API seam. That seam does not exist yet. It is planned under
[#645](https://github.com/spec-kitty/spec-kitty/issues/645), the stable application API,
which the [4.0.0 roadmap](../../plans/4-0-0-milestone-roadmap.md) lists as the precondition
for moving charter code. Java will implement production reads after cross-language
conformance. Python remains the production write path initially; Java writes migrate later,
one operation at a time.

Today callers reach into charter internals directly. `specify_cli`, `runtime`, and `glossary`
import `charter.drg` (about 55 imports), `charter.activation.pack_context` (about 34),
`charter.bundle` (about 22), `charter.activation.charter_yaml_io` (about 18),
`charter.activation.compiler` (about 13), `charter.activation.resolver` (about 12),
`charter.missions`, and `charter.profiles`. A Java service cannot sit behind these imports.
The seam has to come first.

This supersedes the investigated projection-server design in which Python would permanently
compile charter meaning and Java would only serve that projection. Python is a temporary
conformance oracle and write implementation, not the permanent production reader.

## Decision Drivers

- Preserve one answer while implementations overlap.
- Move existing callers behind one charter API seam, planned under #645, before any read moves.
- Separate read and write infrastructure while sharing a pure domain representation.
- Keep YAML, HTTP, MCP, JSON, and future SQL concerns outside the domain.
- Preserve authored YAML during an eventual write migration.
- Scope service identity, lifecycle, freshness, and credentials to one worktree.
- Keep the Python wheel usable while the service transition is incomplete.

## Considered Options

1. Keep all charter behavior in Python and optimize repeated reads in-process.
2. Keep Python as the permanent compiler and use Java only as a projection server.
3. Move reads to a Java service first, retain Python writes temporarily, then migrate writes
   operation by operation (chosen).
4. Replace reads and writes in one cut-over.

## Decision Outcome

**Chosen option:** Option 3. It creates one controlled transition seam and allows read and
distribution work to proceed without waiting for lossless write support. Java is the
intended owner of each write operation once that operation's gates pass.

### Staged ownership

| Stage | Production reads | Production writes | Required evidence |
|---|---|---|---|
| Current | Python | Python | Existing Python behavior |
| Callers move onto the seam | Python, behind the #645 seam | Python, behind the #645 seam | The seam exists; callers outside `charter` no longer import charter internals; a ratchet holds the count at zero |
| Read shadow | Python; Java compared out of band | Python | Contract and fixture equivalence |
| Java primary | Java; loud, observable Python fallback | Python | Conformance gate, freshness and failure behavior |
| Java reads complete | Java only | Python | Explicit fallback-retirement criteria met |
| Write migration | Java reads | Python or Java, per operation | Lossless codec, mapping and confined-mutation gates |
| Intended end state | Java | Java | Every migrated operation satisfies its write gates |

The Java-primary fallback is transitional. It must be visible in diagnostics and telemetry,
must never silently select a second answer, and must have explicit retirement criteria:
the supported fixture corpus passes, stale and unavailable service behavior is proven,
cross-OS packaging is supported, and an agreed observation period finds no unresolved
semantic divergence.

### Hexagonal dependency direction

The service has a pure Java domain and separate read and write application modules.
Infrastructure depends inward:

```text
Python charter API seam ──> REST or MCP
                             │
adapter-in-rest ─────────────┤
adapter-in-mcp  ─────────────┴─> read application ──> domain models + ports

adapter-in-write ──────────────> write application ─> domain models + ports
adapter-out-yaml / store / future SQL ──────────────> domain repository ports
```

Repository interfaces and charter invariants belong to the domain. Implementations belong
to outbound infrastructure. The domain is plain Java and imports no YAML, JSON, HTTP, MCP,
database, or framework library. Read and write APIs are separate infrastructure modules;
they share domain types and semantic services, not transport models or persistence models.
Their application modules do not depend on each other. The Python charter API seam remains
outside the Java hexagon and calls an exposed transport; the outbound store adapter is not
the rejected projection-server design.

API models, domain models, and storage models are distinct:

- API models are versioned REST, JSON, and MCP contracts optimized for consumers.
- Domain models express charter meaning and enforce semantic invariants.
- YAML document models preserve source syntax and provenance.
- A future SQL model may optimize queries without changing domain or API contracts.

The application layer maps across these boundaries through ports. A SQL adapter can
therefore replace or complement a document projection without changing the domain,
inbound adapters, or charter-facing Python seam.

### Cross-language contract

Python and Java align by contract, not by importing each other's implementation. The
contract consists of:

- the versioned OpenAPI 3.1 contract and YAML document schemas, kept under
  `contracts/charter/` (see "Service stack and contract");
- semantic merge, activation, traversal, and resolution rules;
- canonical identifiers and diagnostics;
- positive, negative, provenance, and conflict fixtures;
- expected action-specific guidance and graph-query results.

The configured built-in, organization, and project inputs remain explicit. Implementations
must not infer the internal pack from directory presence.

### Read cut-over

Java reads parse YAML into source models, map to domain objects, validate and merge the
active graph, and answer through versioned REST and MCP adapters. The planned Python
charter API seam (#645) is the single entry point for existing CLI callers. It delegates
read operations to the service behind an internal adapter.

Agent harnesses may call the governed MCP adapter directly, because MCP lets them read
charter guidance without starting a CLI process for each question. This is an additional transport
into the same read application and domain policies, not a second semantic read path. CLI
callers do not bypass the Python seam, and neither REST nor MCP may implement charter
resolution independently.

The sequence is:

0. Move callers onto the #645 seam. Nothing below starts until this is done.
1. Run Java in shadow mode against the same fixtures and live configured inputs as Python.
2. Make Java primary only when conformance is a blocking gate.
3. Keep Python fallback loud and temporary while lifecycle and distribution evidence grows.
4. Retire production Python reads once the fallback-retirement criteria are met.

Read cut-over does not wait for YAML write parity.

### Write cut-over

Python remains the production write path initially, behind the same seam. Java write
support uses a lossless YAML document representation at the infrastructure edge and a
semantic domain representation in the centre. An unchanged document must survive a
round-trip without a byte diff, including comments, ordering, scalar styles, anchors,
document markers, and explicit null spellings.

Three gates prevent a fake parity result:

1. **Codec identity:** lossless YAML load and emit is byte-identical.
2. **Mapping identity:** YAML maps into the domain and back into the same source document
   without a business mutation, and remains byte-identical.
3. **Confined mutation:** a deliberate domain change produces only its expected local diff.

Passing codec identity alone does not prove that domain mapping participated. A production
write operation also cannot move on mapping identity alone: a document-level copy could
ignore the domain object and still reproduce the original bytes. Confined mutation is the
witness that the semantic mapping participated. A production write operation moves to Java
only after all three gates pass for that operation and the shared negative fixtures produce
equivalent diagnostics.

### Service boundary

The service is local-only. It is scoped per worktree because each worktree can carry
different charter and pack inputs, and a shared process would answer from the wrong ones. Its endpoint, process identity,
capability credential, source fingerprints, and compiled state cannot be shared implicitly
between worktrees. Ordinary reads do not perform network freshness checks. Stale local
inputs cause a refusal or loud fallback; explicit refresh and mutation operations rebuild
the active graph atomically.

The [Mission Status Read API decision](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md)
is the sibling model for loopback binding, credential scope, and cross-OS release
practice. The services do not share a process, persistence model, or domain, and this
charter-read facet of #645 is not the Mission Status Read facet.

### Service stack and contract

The charter service follows the Mission Status service. It adopts:

- **Runtime:** Java 25 and Spring Boot 4, with Spring MVC on virtual threads.
- **Build:** the same Gradle multi-project build as the Mission Status service.
- **Contract:** one contract-first OpenAPI 3.1 document under `contracts/charter/`, beside
  `contracts/mission-status/`. The server and its clients build against the contract.
  The same `contracts/` tooling governs it: layout, lint, breaking-change, and release checks.
- **Versioning:** paths live under `/api/v1`. Response schemas are closed. Any change to a
  response shape ships as a new schema version and a new published OpenAPI release.
  A version that is not yet released carries a `-SNAPSHOT` suffix.

The domain stays plain Java (see "Hexagonal dependency direction"). Spring Boot and the
OpenAPI types live in the inbound adapters only.

### Consequences

#### Positive

- Repeated charter reads can reuse a warm, preloaded graph.
- CLI commands and agent harnesses receive one stable entry point while implementations
  change behind it.
- REST, OpenAPI, and MCP become first-class adapters without entering the domain.
- Separate storage adapters allow a later SQL projection without changing the API or domain.
- Java read work and lossless write work can advance independently.

#### Negative

- Python and Java implementations coexist temporarily and require blocking conformance
  tests.
- The service adds process lifecycle, local authentication, stale-state, and per-worktree
  isolation concerns.
- A separate JVM/native artifact adds release, signing, and cross-OS test matrices.
- Lossless YAML mutation is materially harder than semantic parsing.
- The Java-only end state requires deliberate retirement work; the strangler is not
  self-completing.

#### Neutral

- Runtime speed, inference savings, installation friction, exact YAML library, MCP
  integration library, native-image posture, and SQL technology remain hypotheses or
  implementation choices.
- This work belongs to 4.x evolution and does not gate the 4.0.0 GA milestone.

### Confirmation

The decision is confirmed when:

- the same contract corpus runs against both implementations;
- `contracts/charter/` passes the `contracts/` layout, lint, and breaking-change checks;
- shadow reads report no unexplained semantic or diagnostic differences;
- stale, unavailable, and wrong-worktree service cases are tested;
- Java-primary fallback is observable and its retirement criteria are met;
- Java-only production reads no longer need the Python read implementation, while Python
  remains the production writer until each write operation migrates;
- every migrated write operation passes codec identity, mapping identity, confined
  mutation, and negative-fixture equivalence.

## Pros and Cons of the Options

### Option 1: Python only

**Pros:** one implementation and no new runtime. **Cons:** retains per-process startup and
distribution constraints and offers no direct Java service transition.

### Option 2: permanent Python compiler with Java projection server

**Pros:** minimizes semantic duplication. **Cons:** makes Java dependent on Python forever,
keeps two runtimes in the final distribution, and contradicts the intended Java read and
later write ownership.

### Option 3: staged Java reads, then writes

**Pros:** separates migration risk, keeps callers stable, and permits full eventual
replacement. **Cons:** requires temporary double implementation and strong conformance
governance.

### Option 4: one-step replacement

**Pros:** shortest conceptual transition. **Cons:** couples read behavior, lossless YAML
writes, transports, packaging, and lifecycle into one high-risk cut-over with no reliable
fallback.

## Deferred Decisions

A later implementation decision selects the YAML codec, the MCP library, the projection
format, the SQL product if any, the daemon launcher, the native-image posture, and release
packaging. Those choices must preserve the dependency direction and contract gates above.

Performance, inference-cost reduction, and adoption improvement require measurements.
A warm service is expected to avoid repeated startup and graph construction, while token
savings require bounded responses that replace broad source inspection; neither benefit is
asserted as achieved by this ADR.

Before making a performance or adoption claim, benchmarks must compare cold and warm
end-to-end reads rather than parser microbenchmarks, and prompt/token studies must compare
equivalent agent tasks and response scopes. JDK path APIs are likewise an unselected
implementation option, not evidence that existing Python, Git, shell, or repository path
behavior improves.

## More Information

- [4.0.0 milestone roadmap](../../plans/4-0-0-milestone-roadmap.md)
- [Architecture vision](../../architecture/vision/README.md)
- [Living architecture diagrams](../../architecture/diagrams/README.md)
