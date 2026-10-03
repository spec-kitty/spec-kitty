# Research Consolidation

## Decision

Promote a staged charter redesign, not the earlier projection-server design.

- Python remains the production write path and the existing CLI transition
  seam initially.
- Java becomes the production read implementation and owns YAML parsing,
  validation, domain resolution, and agent-facing reads.
- Python remains a temporary conformance oracle and fallback during cut-over,
  not a permanent second read authority.
- Java writes follow later, independently, after lossless YAML evidence.
- The shared cross-language authority is a versioned contract: schemas,
  semantic rules, identifiers, and conformance fixtures.

## Rationale

The existing stable API effort (#645) already requires callers to stop importing
charter internals before charter can ship alone. The existing Python API is the
smallest cut-over seam: CLI callers remain unchanged while reads move behind it.
The separate Mission Status Read service establishes the 4.x precedent for a
detached Java read service, but it does not own charter semantics.

Hexagonal boundaries let the read service and later write service share pure
domain logic while YAML, HTTP, MCP, projection files, and future SQL remain
replaceable adapters.

## Alternatives Considered

### Java projection server over the Python compiler

Rejected as the promoted direction. It improves repeated reads but leaves
Python as the semantic engine indefinitely and does not advance the eventual
Java write path. It remains useful investigation history.

### Replace read and write together

Rejected. It combines semantic parity, API migration, and lossless authoring
into one high-risk cut-over.

### Keep Python reads as a permanent fallback

Rejected as an end state. A temporary loud fallback is useful during shadow and
primary transition stages. A permanent silent fallback hides divergence.

### Put charter routes in the Mission Status Read service

Rejected. The services may share distribution and security conventions, not a
process or domain model.

## Review Findings Incorporated

- Canonical notes previously contained two competing compiler authorities.
- The round-trip gate was fakeable without a deliberate mutation witness.
- Read cut-over and write parity require separate tracker homes.
- Unverified library versions, performance estimates, and adoption claims must
  remain outside the ADR.
- `docs/plans`, not `docs/planning`, is the canonical planning tree.
- Canonical promotion requires an ADR; plans and C4 must link rather than
  restate it.

## Open Decisions Deferred

- Final Java HTTP and MCP framework.
- Maven versus Gradle.
- Atomic document versus SQL after measured query needs.
- Exact Java/YAML libraries and versions.
- Final fallback-removal threshold.
- Quantified runtime, inference, and adoption improvements.
