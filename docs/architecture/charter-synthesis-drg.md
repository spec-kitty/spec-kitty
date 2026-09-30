---
title: 'Understanding Charter: Synthesis, DRG, and Governed Context'
description: How charter synthesize works, what the DRG is, how governed context flows to agents, and known limitations.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/architecture/mission-type-resolution.md
- docs/context/charter-overview.md
- docs/context/governance-files.md
---
# Understanding Charter: Synthesis, DRG, and Governed Context

This document explains the Charter synthesis model and the DRG-backed context system. For a
practical walkthrough, see [How Charter Works](../context/charter-overview.md). For step-by-step
how-to instructions, see [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md).

---

## What the charter bundle is

The **charter bundle** is the machine-readable synthesis of your `charter.md` governance document.
It is not a simple copy of the prose — it is a structured set of YAML artifacts that the runtime
can traverse, merge, and inject as context for specific workflow actions.

The core bundle lives in `.kittify/charter/` and consists of:

- `governance.yaml` — testing, quality, performance, branch, and doctrine-selection config
- `directives.yaml` — extracted directive list with IDs, descriptions, and severity
- `metadata.yaml` — bundle metadata: charter hash, last-sync timestamp, provenance

`references.yaml`, `context-state.json`, synthesis manifests, and provenance sidecars are also
Charter-era files, but they are outside the narrow CharterBundleManifest v1.0.0 core scope.

Why is the bundle needed rather than raw prose? Because the runtime context injection requires a
structured artifact. When `spec-kitty next` prepares a prompt for the `implement` action, it
needs to select the directives that apply specifically to `implement` (not to `specify` or
`review`). A flat prose document cannot serve that purpose efficiently. The bundle provides the
structure for action-scoped context injection.

---

## How synthesis works

The synthesis pipeline has four logical phases:

1. **Parse**: `charter synthesize` reads `charter.md` and the interview answers. It also reads any
   agent-generated YAML from `.kittify/charter/generated/` (artifacts the LLM harness has written).

2. **DRG edge computation**: The synthesizer constructs the Directive Relationship Graph (DRG) by
   resolving typed relationships between actions, directives, tactics, procedures, profiles,
   templates, and glossary terms.

3. **Directive resolution**: With the DRG computed, the synthesizer determines which artifacts
   need to be generated or updated. Artifacts whose provenance points to unchanged inputs are
   left intact (this is what makes `charter resynthesize --topic <selector>` work — only affected
   artifacts are regenerated).

4. **Promote artifacts**: The synthesizer writes resolved artifacts to `.kittify/doctrine/`
   (project-local doctrine) and records synthesis state under `.kittify/charter/`. The `--dry-run`
   flag stops after validation, before promotion.

The authoritative file throughout is always `charter.md`. The synthesizer reads it; it does not
write to it. Doctrine artifacts are outputs, not inputs.

---

## DRG edge computation

The **Directive Relationship Graph (DRG)** is a directed graph with typed nodes such as actions,
directives, tactics, procedures, profiles, templates, and glossary terms. Edges use these
relations:

- `scope`: action-to-artifact scoping
- `requires`: hard dependencies between artifacts
- `suggests`: softer recommendations traversed to a bounded depth
- `vocabulary`: links from resolved artifacts to glossary scope/term context
- `instantiates`, `replaces`, `delegates_to`: additional graph relations used by specific
  doctrine surfaces

When the runtime prepares context for a specific mission action (e.g., `implement`), it traverses
the DRG from the action's entry node. It follows `scope` edges first, then transitive `requires`
edges, bounded-depth `suggests` edges, and one-hop `vocabulary` edges from the resolved nodes.
That keeps implementation prompts focused on implementation-relevant doctrine instead of
specification-phase concerns.

The DRG is not stored as a standalone file that you can inspect directly. It is computed by the
synthesizer and manifests as the structured content of the bundle artifacts.

### Mission-type governance grains

Per-mission-type governance also resolves *through* the charter layer, keyed off the
`mission_type` recorded in a mission's `meta.json` — never inferred from
`template_set` and never defaulted to `software-dev`. It is authored at two grains
that the resolver unions and de-dupes: an **action-grain** source
(`missions/<type>/actions/<action>/index.yaml`, which generates the DRG `scope`
edges described above) and a **type-grain** source
(`missions/<type>/governance-profile.yaml`), which is also the project-override
target. A full explanation of that seam — the reserved slots for templates and
gates, the per-type override, and the leak-closure invariant — lives in
[Mission-Type Resolution](mission-type-resolution.md).

---

## Bootstrap vs compact context

The DRG traversal for a given action can produce large payloads for complex governance structures.
Two modes handle this:

**Bootstrap mode**: On the first load for an action (or after a fresh synthesis), the full
relevant DRG subgraph is injected into the governed profile invocation. The agent sees all
applicable directives, tactics, and glossary terms for its current action, plus the full doctrine
library references.

**Compact-context mode**: When the DRG context payload exceeds the size threshold for inclusion,
the runtime falls back to compact-context mode. In this mode, the agent receives only the resolved
paradigm list, directive list, and tool list — without the full doctrine library text. This is a
known limitation (see issue #787 in the project issue tracker; check that issue for current
resolution status). Do not assume full-context behavior unconditionally on large governance layers.

First-load state is tracked per action in `.kittify/charter/context-state.json`. Each action
(specify, plan, implement, review) has an independent first-load timestamp.

---

## Why the authoritative vs generated distinction matters

Charter governance is built on a strict read/write boundary:

- **Authoritative policy source**: `.kittify/charter/charter.md` — human-edited, the source of
  truth for project governance policy.
- **Derived config and runtime state**: `governance.yaml`, `directives.yaml`, `metadata.yaml`,
  `references.yaml`, `context-state.json`, synthesis manifests, and provenance sidecars — owned
  by their respective CLI commands.
- **Project-local doctrine overlay**: `.kittify/doctrine/` — promoted by `charter synthesize` and
  read alongside built-in doctrine.
- **Agent-generated synthesis input**: `.kittify/charter/generated/` — written by the harness and
  validated by `charter synthesize`.

If you edit a derived file (for example, add a directive to `governance.yaml` directly), the edit
can be lost on the next `charter sync` or `charter generate` run because those files are
re-derived from `charter.md`. There is no merge step for derived config.

`charter status` detects drift between `charter.md` and the bundle hash. `charter lint` detects
decay within the DRG (orphaned artifacts, contradictions, staleness). Both tools exist precisely
because the authoritative/generated boundary creates a risk of divergence if synthesis is not run
after charter edits.

---

## Known limitations

1. **Compact-context mode (issue #787)**: Large governance layers may trigger compact-context
   fallback, causing agents to receive summarized rather than full doctrine context. The workaround
   is to reduce governance scope or break the project into smaller governance domains.

2. **Fresh-project synthesis**: On a project where `.kittify/charter/generated/` is missing or
   empty (no agent-generated artifacts), `charter synthesize` produces only the minimal artifact
   set (directory marker and PROVENANCE.md). The runtime falls back to built-in doctrine until a
   full synthesis run with agent-generated content completes.

3. **Synthesis requires `charter.md`**: `charter synthesize` will exit non-zero if `charter.md`
   does not exist. Run `charter interview` and `charter generate` first.

---

## See Also

- [How Charter Works](../context/charter-overview.md)
- [Governance Files Reference](../context/governance-files.md)
- [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md)
- [Troubleshooting Charter Failures](../guides/how-to/governance/troubleshoot-charter.md)
