---
title: 'ADR: Local, No-Egress PlantUML Rendering for Code-Grounded Doctrine Schema Diagrams — a New Genre Beside the Hand-Authored C4 Lane'
description: 'Why doctrine schema diagrams render locally at build time from a pinned, network-isolated PlantUML — a genre distinct from C4 progressive-zoom, carving R-04 accordingly.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-08-12'
updated: '2026-08-12'
type: explanation
---

## Context and Problem Statement

The doctrine artefact model — agent profiles, mission-type/step contracts, the DRG
(`DRGNode`/`DRGEdge`/`NodeKind`/`Relation`), and the `ArtifactKind` vocabulary — is
documented **in prose** across `doctrine-kinds.md`, `mission-type-resolution.md`, and
`doctrine-relationships.md`. It has **no schema diagrams**: a reader cannot see the shape
of a bound model at a glance, and prose alone does not make a closed field set legible.

Two facts constrain any fix.

1. **The docsite renders Mermaid but not PlantUML.** The DocFX pipeline runs an ordered
   `scripts/docs/` HTML post-processing chain over `docs/_site` (`glossary_linker.py` is
   the established pattern). Mermaid renders client-side; a ` ```plantuml `-fenced
   `@startyaml` block does not render at all. So the diagram genre best suited to typed
   schema depiction — PlantUML `@startyaml` — has no rendering path today.
2. **These diagrams must not drift from the code**, and they must not send doctrine
   content off-machine to be drawn. A schema diagram that is hand-copied, or rendered by a
   remote PlantUML server, fails one or the other: it drifts, or it egresses.

This ADR records the rendering decision (Scope B, mission `doctrine-schema-diagrams`,
FR-001/FR-002), the reasoning that positions these schema diagrams as a **new genre**
rather than an extension of the existing C4 model, and the reconciliation with R-04 in
[`docs/architecture/diagrams/README.md`](../../architecture/diagrams/README.md) so the two
governance surfaces do not contradict.

The governing toolguide for the mechanism is the active **`plantuml-diagramming`**
toolguide (`packs/built-in/toolguides/plantuml-diagramming.toolguide.yaml`), activated in
the charter's *Writing, Communication & Diagramming Doctrine* (2026-08-08) alongside
`USE_C4_MODEL_TECHNIQUES` and the `mermaid-diagramming` toolguide. That activation is
**charter-prose active** — a governing directive read from the charter document — not a
runtime-resolved artefact loaded through the doctrine chain; this ADR cites it by name as
the source of the how-to, and does not depend on runtime resolution of it.

## Decision Drivers

* **Zero doctrine-content egress (C-001, NFR-002).** The content being drawn is the
  project's own doctrine model. It must be rendered on-machine, and the renderer must be
  provably unable to reach the network — proven behaviourally, not by a flag.
* **Generated fidelity over source-view convenience (C-002).** A diagram that is generated
  from the frozen code model and guarded against drift is worth more than one that renders
  on github.com's raw source view. We accept docsite-only rendering to get fidelity.
* **Reproducibility (NFR-003).** The rendering binary must be pinned by version **and**
  sha256, and the diagrams must be CI-generated, not committed as SVGs that can rot.
* **Slot into the existing chain, disturb nothing.** The step must run inside the
  established `scripts/docs/` post-processing order and leave the existing Mermaid/C4
  diagrams (R-04) rendering unchanged (NFR-004).
* **Keep the genre boundary honest.** These diagrams depict *code models*, not
  architecture zoom levels. Conflating them with the C4 lane would misdirect both authors
  and the drift guard.

## Decision

**Render `@startyaml` doctrine schema diagrams at docs-build time, locally, with a pinned
binary inside a network-denied container, as a post-processor after `glossary_linker`.**

1. **Pinned binary, sandboxed engine.** A single `plantuml.jar`, pinned by **version and
   sha256**, is verified before use (a sha256 mismatch fails the build before any render
   from an unverified binary). It is invoked with
   `-DPLANTUML_SECURITY_PROFILE=SANDBOX`, and SANDBOX is proven behaviourally: a diagram
   carrying an egress directive (`!include`/`!includeurl`) must fail-closed under it.
2. **Rendering runs only inside a digest-pinned JRE container under
   `docker run --network=none`.** The jar never runs host-native. The container image is
   pinned by digest; `--network=none` denies the render process any network namespace, so
   even a hypothetical SANDBOX bypass cannot reach the wire. This is the portable, hard
   egress gate on CI-Linux (the runners have Docker); `unshare -rn` is not reliable on
   Ubuntu-24.04 runners (`apparmor_restrict_unprivileged_userns=1`) and is therefore not
   the primary mechanism.
3. **Python orchestration is host-native and stdlib-only.** The orchestrator
   (`scripts/docs/plantuml_render.py`) recovers ` ```plantuml `-fenced `@start*` blocks
   from the built `docs/_site` HTML (HTML-unescaping the payload; asserting the emitted
   `language-plantuml` class), shells out to the pinned container to render each block to
   SVG, and injects the SVG with descriptive alt/aria text. The orchestrator itself does
   no network I/O and pulls in no third-party dependency; only the isolated container does
   the drawing.
4. **Positioned after `glossary_linker` in both docs workflows.** The step runs after
   `glossary_linker` in the PR gate (`docs-build-pr.yml`) and in the deploy pipeline
   (`docs-pages.yml`, including its `paths:` allowlist), so glossary linking has already
   run over the HTML before diagrams are injected.
5. **Fidelity is enforced by the drift guard, not by hand.** Each diagram is bound to its
   source model by an explicit `file:class` table and checked by the FR-004 drift guard,
   which introspects the live model (Pydantic `model_fields` with `FieldInfo.alias or
   name` normalization and transitive nested recursion; frozen-dataclass `fields()`;
   StrEnum members via `list(...)` — never a hand-copied count) and fails on any field-set
   mismatch. The guard is the control that lets us treat a generated diagram as
   authoritative.

### Schema diagrams are a new genre, distinct from C4 progressive-zoom

The charter's `USE_C4_MODEL_TECHNIQUES` directive governs **architecture** diagrams via
the C4 model's progressive zoom — System Context → Container → Component → Code — where
each level serves one audience at one altitude. Those diagrams are **hand-authored** and
live under [`docs/architecture/diagrams/`](../../architecture/diagrams/README.md) as the
living C4 model (R-04).

The doctrine **schema diagrams** introduced here are a **different genre**. They depict the
**shape of a code model** — the fields, types, and enum members of a frozen artefact
schema — not an architecture zoom level. They are not a fifth C4 tier and they are not a
finer-grained "Code" level of the architecture C4 set; they answer "what does this model's
field set look like?", a question C4 never asks. They are **generated** from the frozen
models (not hand-authored), **drift-guarded** (not narrative), and **docsite-only** (not
source-view). Treating them as their own genre keeps the C4 lane's hand-authored,
GitHub-renderable convention intact while giving schema depiction its own rules.

### Accessibility carve-out (NFR-005)

The `docs-accessibility` styleguide requires that a diagram's facts be **restated in
prose** so the page is legible without seeing the image. For these schema diagrams that
duty is **discharged by the surrounding doctrine-kinds prose** — the kind descriptions and
model explanations already on the page — **not** by re-listing every field beside the
diagram. Re-listing the fields would recreate exactly the hand-maintained field inventory
that **C-005 forbids**: a second copy of the schema that drifts from both the code and the
generated diagram. Each injected SVG still carries descriptive, non-trivial alt/aria text
derived from the diagram's `@startyaml` title/caption (asserted by the render pipeline), so
the *identity and purpose* of each diagram is available to assistive technology; the
*exhaustive field facts* live once, in the code model, surfaced through the generated
diagram and narrated by the existing prose.

## Consequences

**Positive**

- Doctrine schema shape becomes legible on the docsite, generated from the single source of
  truth (the frozen models) and unable to drift past the FR-004 guard.
- No doctrine content leaves the machine: the render runs in a `--network=none` container
  with a SANDBOX engine, both proven behaviourally.
- The rendering binary is reproducible (version + sha256; digest-pinned image), and SVGs
  are CI-generated rather than committed and left to rot.
- The existing hand-authored C4 lane (R-04) and its Mermaid/C4 diagrams are untouched
  (NFR-004); the genre boundary is explicit, so authors know which lane a new diagram
  belongs to.

**Negative / accepted trade-offs**

- **Docsite-only rendering (C-002).** Pre-rendered SVGs appear only on the *built* docsite,
  not on github.com's source view of the Markdown. A reader browsing the raw doctrine
  pages on GitHub sees the ` ```plantuml ` fence, not a picture. We accept this: the value
  is generated fidelity, and the fidelity control (the drift guard) only exists on the
  build path. This is the deliberate inverse of the C4 lane's R-04 convention, which
  chooses GitHub-source rendering (Mermaid, no build tooling) over generation.
- **Build-time and Docker dependency.** The docs build now shells out to Docker and adds
  render time (target ≤ 60s, a **monitored budget/warning**, not a hard per-PR gate, per
  the flakiness policy). A runner without Docker cannot render these diagrams — acceptable
  because CI-Linux (which has Docker) is the hard gate.
- **A new lane to govern.** There are now two diagram lanes with different conventions
  (hand-authored/source-rendered C4 vs generated/docsite-only schema). The R-04 amendment
  and this ADR cross-link so the boundary is stated once and identically in both places.

**Reconciliation with R-04 (and #1839)**

R-04 in [`docs/architecture/diagrams/README.md`](../../architecture/diagrams/README.md)
records that deterministic diagram **generation** (Structurizr/PlantUML) is out of scope
for the living C4 model, which stays hand-authored so it renders on GitHub. That line is
**unchanged for hand-authored C4 architecture diagrams** — the C4 lane keeps its
convention. This ADR opens a **separate, narrowly-scoped lane**: **generated,
docsite-only schema diagrams of code models**, governed here and by the
`plantuml-diagramming` toolguide. The two do not contradict because they cover different
genres: R-04's "generation out of scope" applies to the C4 architecture model; the new
lane applies only to drift-guarded schema depictions of frozen doctrine models. The R-04
entry is amended to state this carve-out and cross-link this ADR.

## References

- Mission spec: `kitty-specs/doctrine-schema-diagrams-01KZTQTH/spec.md` — FR-001, FR-002,
  NFR-002, NFR-003, NFR-005, C-001, C-002, C-004, C-005, C-006.
- Research: `kitty-specs/doctrine-schema-diagrams-01KZTQTH/research.md` — D1 (rendering),
  D2 (drift guard), D4 (ADR / R-04 reconciliation).
- Toolguide (charter-prose active): `plantuml-diagramming`
  (`packs/built-in/toolguides/plantuml-diagramming.toolguide.yaml`).
- Charter: `.kittify/charter/charter.md` § *Writing, Communication & Diagramming Doctrine*
  — `USE_C4_MODEL_TECHNIQUES`, `mermaid-diagramming` + `plantuml-diagramming` toolguides,
  `docs-accessibility`.
- Amended R-04 entry: [`docs/architecture/diagrams/README.md`](../../architecture/diagrams/README.md).
- Upstream generation-scope issue this carve-out refines: `#1839` (deduped vs `#1812`).
