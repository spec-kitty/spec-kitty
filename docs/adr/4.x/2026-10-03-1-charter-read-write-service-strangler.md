---
title: 'ADR: replace charter reads and writes through a staged Java service strangler'
description: 'Define the staged transition from the Python charter implementation to a per-worktree Java read service and, later, Java write adapters.'
status: Accepted
date: '2026-10-03'
updated: '2026-10-19'
---
# Replace charter reads and writes through a staged Java service strangler

**Status:** Accepted (2026-10-19), with Amendment 2026-10-19 (below). Proposed 2026-10-03.

> **Read the Amendment 2026-10-19 first.** It narrows this record to the seam routing, ships
> stages 3 and 4 together with no Python read fallback and no observation period, makes the
> conformance corpus the only gate, and decides the service launcher. Where the body below
> says otherwise (the "Java authoritative; loud, observable Python fallback" stage, the
> observation period, "refusal or loud fallback", the deferred daemon launcher, #645 as the
> seam), the amendment wins.

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
conformance. Python code remains the production writer initially (see "Write cut-over" for
the current write paths); Java writes migrate later, one operation at a time.

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
| --- | --- | --- | --- |
| Current | Python | Python | Existing Python behavior |
| Callers move onto the seam | Python, behind the #645 seam | Python, behind the #645 seam | The seam exists; callers outside `charter` no longer import charter internals; a ratchet holds the count at zero |
| Read shadow | Python; Java compared out of band | Python | Contract and fixture equivalence |
| Java authoritative | Java; loud, observable Python fallback | Python | Conformance gate, freshness and failure behavior |
| Java reads complete | Java only | Python | Explicit fallback-retirement criteria met |
| Write migration | Java reads | Python or Java, per operation | Lossless codec, mapping and confined-mutation gates |
| Intended end state | Java | Java | Every migrated operation satisfies its write gates |

"Java authoritative" means Java gives the production answer and Python answers only as a
fallback. This ADR avoids "primary" for that stage: the word already has four senses in this repository.

The Java-authoritative fallback is transitional. It must be visible in diagnostics and telemetry,
must never silently select a second answer, and must have explicit retirement criteria:
the supported fixture corpus passes, stale and unavailable service behavior is proven,
cross-OS packaging is supported, and an agreed observation period finds no unresolved
semantic divergence.

### Reversibility

Each stage can step back one stage, until the point of no return.

- **Callers move onto the seam:** move a caller back to its direct import. Python behavior
  does not change.
- **Read shadow:** turn the out-of-band comparison off. Python already answers.
- **Java authoritative:** switch the seam adapter back to Python reads. This works while the
  Python read implementation exists.
- **Write migration:** send a migrated write operation back to Python, one operation at a
  time. This works while that operation's Python writer exists.

**The point of no return is retiring the Python reads** (the Java reads complete stage).
After that, going back means restoring deleted code from a release, not switching an
adapter. Retire the Python reads only after the fallback-retirement criteria are met and the
observation period ends. Retiring each Python writer repeats this choice for its operation.

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
must not infer the internal pack from directory presence. They read the packs listed under
`charter_packs.org.packs` in `.kittify/config.yaml`. The retired `doctrine.org.packs` key is
still read as a legacy form.

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
2. Make Java authoritative only when conformance is a blocking gate.
3. Keep Python fallback loud and temporary while lifecycle and distribution evidence grows.
4. Retire production Python reads once the fallback-retirement criteria are met.

Read cut-over does not wait for YAML write parity.

### Write cut-over

Python remains the production writer initially, behind the same seam. There is no single
Python write adapter today. Three paths write authored or derived YAML:

- **Activation:** `commit_plan` in `charter.activation.activation_engine` writes the
  activation lists with a single save. `resolve_activation_write_target` in
  `charter.activation.pack_manager` picks the file: `.kittify/config.yaml` for a project
  without a `charter:` pointer, `charter.yaml` for a migrated one.
- **Charter document:** `charter.activation.charter_yaml_io` (`prepare_yaml_write`,
  `apply_yaml_write`, `save_charter_yaml`) writes `charter.yaml` and preserves the authored
  sections.
- **Compile:** `write_compiled_charter` in `charter.activation.compiler` refreshes only the
  derived `catalog` and `metadata` sections of `charter.yaml`, through `charter_yaml_io`.
  `charter.bundle` validates bundles and writes nothing.

Each of these is a write operation to migrate. The seam must front all three before any
moves. Java write
support uses a lossless YAML document representation at the infrastructure edge and a
semantic domain representation in the centre. An unchanged document must survive a
round-trip without a byte diff, including comments, ordering, scalar styles, anchors,
document markers, and explicit null spellings.

#### One writer at a time

During write migration, Python and Java could both change the same authored YAML. One side
holds the single write lock at any time. The Python seam holds it until the last write
operation migrates. Java mutates a file only through a handoff that the seam grants for
that operation. The service rebuilds its active graph from the source fingerprints after
any write made outside it, and never serves a graph built before that write.

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

### Where the seam lives

The seam is code under `src/charter/`, in the charter layer. Its only service-facing code is a
transport client. It fronts the existing Python read and write paths. It does not start, stop,
or locate the service. Service launch and lifecycle live in `specify_cli`, which hands the
seam an endpoint and a credential. So `charter` gains no outbound edge to `specify_cli`, and the
enforced import chain stays `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`.

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
- Java-authoritative fallback is observable and its retirement criteria are met;
- each stage's rollback switch is tested before the next stage starts;
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

**MCP adapter authorization is deferred.** A later decision defines who may call the MCP
adapter and how. It should reuse the Mission Status service model: loopback-only binding,
Host checks, and a capability token scoped to one worktree. Until then, the MCP adapter is
planned only and must not ship without that decision.

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

## Amendment 2026-10-19 (Accepted): seam routing only, one switch-over, and a CLI-started per-worktree daemon

**Deciders:** Stijn Dejongh (operator), 2026-10-19. Requested by `spec-kitty-charter`
[ADR-0010](https://github.com/spec-kitty/spec-kitty-charter/blob/main/docs/adr/0010-cutover-scope-and-seam-boundary.md)
(cutover scope and seam boundary) and
[ADR-0011](https://github.com/spec-kitty/spec-kitty-charter/blob/main/docs/adr/0011-seam-runtime-fail-closed-daemon-and-freshness.md)
(seam runtime: fail closed, daemon, freshness), both recorded in
[spec-kitty-charter#88](https://github.com/spec-kitty/spec-kitty-charter/pull/88). The
decision this ADR records is accepted with this amendment; the body above is kept as written.

### Scope of this record (spec-kitty-charter ADR-0010)

> This record governs the seam routing only: the stages, the switch at
> `charter.offering.api`, and the seam's failure behavior. The offering's internals, its
> contract and the Charter Pack structure are decided in spec-kitty-charter. Stage 1 is
> reached (#6188). Stages 3 and 4 ship together, with no Python read fallback, and the
> conformance corpus is the only gate. Compile keeps a ratcheted Python read path until it is
> the first write migrated.

Read against the *Staged ownership* table and the *Read cut-over* sequence above:

- **Stage 1 ("Callers move onto the seam") is reached.** The seam is `charter.offering.api`,
  delivered by #6188 (PR #6200), not the #645 epic the body names (#645 is closed
  `not_planned`).
- **"Java authoritative" and "Java reads complete" ship together.** The release that routes
  reads to Java also stops calling Python for reads. There is no loud Python fallback stage
  and no observation period (`spec-kitty-charter` #75 is dropped).
- **The conformance corpus is the only gate.** A divergence on the supported corpus fails
  core's CI (`spec-kitty-charter` #72).
- **The cutover covers every offering read**, including the reads `charter.activation` makes
  of offering data; activation's own state logic stays in core.
- **Compile is the ratcheted exemption.** Compile keeps a Python read path for its inputs; a
  ratchet test stops any other caller from using it. The exemption ends when compile is the
  first write migrated to Java (stage 5, *Write migration*).
- **The seam fails closed** (`spec-kitty-charter` ADR-0011, Decision 1). A refusal from the
  service is the answer and the seam passes it on. A transport failure (no service, timeout,
  wrong contract version, wrong worktree) is a named error with a remedy and a non-zero exit.
  There is no Python fallback and no cached last-good answer. In *Service boundary*, "stale
  local inputs cause a refusal or loud fallback" now reads "cause a refusal".
- **The point of no return moves.** With no fallback stage, rollback after the switch-over is
  a release downgrade. The Python read code is deleted in the release after the switch-over,
  not in the same one (ADR-0010, Risks).

### Service boundary (spec-kitty-charter ADR-0011)

This replaces the "daemon launcher" item of *Deferred Decisions* and extends *Service
boundary*:

> The CLI starts one charter service per worktree on first use, on loopback with a
> per-worktree token, and stops it on idle or worktree removal. This is a CLI-started daemon;
> it is limited to read operations and has no browser-facing surface.

The launcher lives in `specify_cli` (`spec-kitty-charter` #70), as *Where the seam lives*
already requires; the seam receives only an endpoint and a credential. CI runs the same
daemon.

### Why a CLI-started daemon, when the dashboard daemon was rejected

**The Charter Offering service must be available in every repository and development
environment.** After the cutover a spec-kitty CLI without it cannot operate: every charter
read (action context, the active charter, profile resolution, doctrine lookups) crosses the
seam, and the seam fails closed. That availability requirement is what separates this
service from the two cases where core chose differently:

- **The event system** needs only its writer to be present. The CLI appends to the
  `status.events.jsonl` ledger itself; a reader exists only when an integration depends on
  one. The Mission Status Read API ([ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md),
  Amendment 2026-10-03) can therefore be a *detached* service that no spec-kitty command
  starts.
- **The removed dashboard UI server** was optional. The CLI worked without it, and its
  in-CLI daemon brought PID-recycling and token-leak defects with no availability need to
  justify them. It was removed from the CLI (#5530), and ADR 2026-10-01-2 rejected its
  Option 4 because it "put a daemon *inside the CLI*".

For a service the CLI cannot work without, the choice is between **launch when down** (the
CLI starts it on first use) and **requiring every user and every consumer, CI included, to
keep it running**, where a stopped service is a blocker on the next command. Launch when down
is chosen: availability is the CLI's job, not a setup step every user and runner must
remember.

The trust model the dashboard rejection closed is reopened only as far as this need
requires (`spec-kitty-charter` ADR-0011, Decision 2): one daemon per worktree, loopback only,
a per-worktree token readable only by the user, read operations only, no browser-facing
surface, an identity check against the service's info operation before every session, and
a launcher that records the process identity, not only the PID, so a recycled PID is never
mistaken for the service. A security review of the launcher precedes the cutover.
