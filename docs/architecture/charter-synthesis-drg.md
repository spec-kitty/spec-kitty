---
title: 'Understanding Charter: Synthesis, DRG, and Governed Context'
description: How charter synthesize works, what the DRG is, how governed context flows to agents, the shipped-graph orphan residual, and known limitations.
doc_status: active
updated: '2026-10-31'
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

4. **Promote artifacts**: The synthesizer writes resolved artifacts to `.kittify/charter-packs/`
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
- **Project layer**: `.kittify/charter-packs/` — promoted by `charter synthesize` and
  read alongside the built-in Charter Pack.
- **Agent-generated synthesis input**: `.kittify/charter/generated/` — written by the harness and
  validated by `charter synthesize`.

If you edit a derived file (for example, add a directive to `governance.yaml` directly), the edit
can be lost on the next `charter generate` run because those files are
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
   set (directory marker and PROVENANCE.md). The runtime falls back to the built-in Charter Pack until a
   full synthesis run with agent-generated content completes.

3. **Synthesis requires `charter.md`**: `charter synthesize` will exit non-zero if `charter.md`
   does not exist. Run `charter interview` and `charter generate` first.

---

## The shipped-graph orphan residual (current state)

An **orphan** is a DRG node with no inbound and no outbound edge. Some orphans are intentional —
a deliberately authored artifact with no single natural referent, or a structural node that is
resolved by lookup rather than by traversal. Doctrine forbids deleting such an artifact or
manufacturing an edge to zero the metric (D-C2 / C-003): every orphan is either **wired** to a real
referent or **recorded here**.

This section is the live, current-state record. It is bound to the measurement by
`test_documented_residual_matches_measured_shipped_orphans` in
`tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`: the URNs in the block below must
equal the shipped graph's orphans exactly, so an unrecorded new orphan, or a recorded one that has
since been wired, fails a test rather than passing as prose drift.

**How to recompute it** — never copy the list from prose:

```python
from charter.offering.drg.loader import load_built_in_graph

g = load_built_in_graph()
incident = {u for e in g.edges for u in (e.source, e.target)}
orphans = sorted({n.urn for n in g.nodes} - incident)
print(len(orphans))  # 25
print(*orphans, sep="\n")  # the membership the block below must equal
```

**Current state (25 orphans, 358 nodes, 1,069 edges):**

<!-- drg-orphan-residual:begin -->

- `mission_step_contract:documentation/accept`
- `mission_step_contract:documentation/audit`
- `mission_step_contract:documentation/design`
- `mission_step_contract:documentation/discover`
- `mission_step_contract:documentation/generate`
- `mission_step_contract:documentation/publish`
- `mission_step_contract:documentation/validate`
- `mission_step_contract:plan/plan`
- `mission_step_contract:plan/research`
- `mission_step_contract:plan/review`
- `mission_step_contract:plan/specify`
- `mission_step_contract:research/gathering`
- `mission_step_contract:research/methodology`
- `mission_step_contract:research/output`
- `mission_step_contract:research/scoping`
- `mission_step_contract:research/synthesis`
- `mission_step_contract:software-dev/implement`
- `mission_step_contract:software-dev/plan`
- `mission_step_contract:software-dev/review`
- `mission_step_contract:software-dev/specify`
- `mission_step_contract:software-dev/tasks`
- `glossary_pack:spec-kitty-core`
- `agent_profile:human-in-charge`
- `styleguide:deployable-skill-authoring`
- `toolguide:powershell-syntax`

<!-- drg-orphan-residual:end -->

### Why each group is residual

| Group | Count | Disposition |
|---|---|---|
| `mission_step_contract:<mission>/<action>` | 21 | **Edge-less by construction.** The step-contract fragment ships `edges: []`; the activation engine resolves a contract by URN lookup on the `(mission_type, action)` join, never by traversal. Deleting or edging them to shrink the metric is what D-C2 / C-003 forbid. The 21 are the 17 shipped by `doctrine-controlled-transition-gates` (7 documentation + 5 research + 5 software-dev) plus the 4 `plan/*` contracts vendored by #6379. Membership is pinned as `_EDGELESS_BY_CONSTRUCTION`. |
| `glossary_pack:spec-kitty-core` | 1 | **Awaiting references.** The pack node ships with zero outbound references; its enforcement fields stay inert until a follow-up mission gives it a real referent. Inventing one now would be a guessed edge. Pinned in `_AWAITING_REFERENCES`. |
| `agent_profile:human-in-charge` | 1 | **Runtime-assignment sentinel.** Signalled by assigning a work package to a human at runtime, never by a static doctrine edge. |
| `styleguide:deployable-skill-authoring` | 1 | **Direct-activation-only.** Reached by `charter activate styleguide deployable-skill-authoring`; no defensible source artifact exists to carry an inbound edge (a guessed one is refused, C-003). Pinned in `_DIRECT_ACTIVATION_ONLY`. |
| `toolguide:powershell-syntax` | 1 | **Runtime tooling.** Real PowerShell-authoring content consumed by agents at runtime; no built-in artifact cites it. Admitted by PR #2936. |

### Ceiling ledger

`DOCUMENTED_ORPHAN_RESIDUAL` in the test module above is the numeric regression guard. It may move
only together with this record. The history, so the number is never bare:

| Ceiling | Cause |
|---|---|
| 14 | Post-WP05 curated baseline (9 Fowler tactics wired, 12 orphans wired). |
| 18 -> 14 | A stopgap raise for 8 structural mission-type nodes, reverted once `mission-type-drg-edges` (#2677) emitted the `mission_type -> action` edges. |
| 29 | `doctrine-controlled-transition-gates` (epic #2535 half A) shipped 17 edge-less step contracts. |
| 30 | PR #2936 promoted `toolguide:powershell-syntax` from a dead file to a live, edge-less node. |
| 30 -> 21 | Ratcheted after both #3007 residuals were retired/wired and six other artifacts were wired; a ceiling cannot see a shrink, so it was ratcheted rather than left with nine points of silent slack. |
| 22 -> 21 | `charter-delivery-finish-context-degod` (#3064) relocated `asset:common-charter-scaffold-minimal` to charter-pack status, removing the node. |
| **21 -> 25** | The built-in pin bump of PR #6379 vendored the plan mission's four step contracts (#6432), which are edge-less by construction like the other 17. No edge was wired; `packs/built-in/` was untouched. Recorded by mission `charter-synthesis-graph-and-languages-01M59RZ5`, and the live record above was added under #6513 so the raise has a writable home. |

### Where the older records live

- `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md` is the
  canonical **historical** record (WP05, #1923). It sits under `kitty-specs/`, an immutable archive
  root (`tests/architectural/test_archive_root_byte_identical.py`), so it is **frozen**: cite it for
  the curation narrative of its date, never edit it, and do not read its last ceiling (29 -> 30 over
  17 step contracts) as current state.
- `_INTENTIONAL_ORPHANS` / `_SHIPPED_ORPHANS` in
  `tests/charter_offering/drg/migration/test_extractor_projection.py` are the **pure-extractor frame**
  membership pins. This page records the **shipped** frame (`load_built_in_graph()`), which is the
  frame the ceiling measures; the two differ only by `_ORPHANS_RESOLVED_BY_OVERLAY`, so neither may
  be "corrected" against the other.
- `tests/charter_offering/drg/test_reachability.py` pins the companion **reachability** measure
  (action-unreachable vs profile-delivered), which is a different question from incidence: a node
  can be edge-incident and still unreachable from any action.

---

## See Also

- [How Charter Works](../context/charter-overview.md)
- [Governance Files Reference](../context/governance-files.md)
- [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md)
- [Troubleshooting Charter Failures](../guides/how-to/governance/troubleshoot-charter.md)
