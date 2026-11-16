---
title: How Charter Works
description: The Charter mental model — synthesis, DRG, governed context, and profile invocation.
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Read this for the charter mental model before you set up or change a project's governance.
- profile: external/tech-lead-evaluator
  guidance_text: Read this to see how governance reaches each agent prompt.
related:
- context/governance-files
- guides/how-to/governance/setup-governance
- architecture/charter-pack-usage-journey
---
# How Charter Works

Charter is the governance layer that turns your project's structured policy file
(`.kittify/charter/charter.yaml`) into context that every agent mission action automatically
receives. This page explains the mental model — synthesis, the DRG, governed context, and profile
invocation. For the complete, step-by-step create-your-charter flow (interview through
generation, validation, and synthesis), see
[How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md). For the guided tour connecting
setup to a full mission run, see the
[Governed Charter Workflow Tutorial](../guides/tutorials/charter-governed-workflow.md).

> **Key invariant**: `.kittify/charter/charter.yaml` is the git-tracked, authoritative,
> structured charter — `governance`, `directives`, `catalog`, and `overrides` all live inside it.
> What the project has activated lives beside it in the git-tracked activation ledger
> `.kittify/charter/activation.yaml`, written by `spec-kitty charter activate` / `deactivate`.
> `governance`, `directives`, and `overrides` are hand-authored (or interview-seeded); `catalog` and `metadata` are refreshed deterministically by
> `charter generate`. `.kittify/charter/charter.md` is a **curated companion**: a human-readable
> narrative the runtime never parses, scrapes, or resolves policy from — editing it has no
> runtime effect. A project may also keep a public constitution or governance document outside
> `.kittify/`; both `charter.md` and any external document are supporting context, not alternate
> authoritative charter paths. `.kittify/config.yaml` carries a single `charter:` pointer that
> resolves the active `charter.yaml`. Do not hand-edit `charter.yaml`'s `catalog` or `metadata`
> sections, synthesis manifests, or provenance sidecars. Agent synthesis input under
> `.kittify/charter/generated/` is produced by the harness, not by routine operator edits.

---

## What Charter Does

Charter solves a specific problem: agent prompts need consistent, project-accurate policy context,
sourced from one operator-controlled, machine-readable charter file.

The mechanism:

1. You author (directly, or via interview + `charter generate`) the `governance` and `directives`
   sections of `.kittify/charter/charter.yaml` — testing standards, quality gates, branching rules,
   directive selections — and record what you activate in `.kittify/charter/activation.yaml`
   with `spec-kitty charter activate`.
2. `charter generate` refreshes `charter.yaml`'s `catalog` and `metadata` sections (the doctrine
   reference manifest and a generation timestamp) from the active charter, merging
   the refresh back into the file without touching your authored sections.
3. When `spec-kitty next` invokes an agent profile for a mission action, the runtime reads
   `charter.yaml` directly and injects the relevant charter context into the prompt automatically.
   The agent does not invent governance; it reads and complies with what the charter says.

`charter.md` plays no role in that resolution path. Keep it as a narrative companion — a
human-facing summary of the same policy, or a pointer to a public constitution — but editing it
does not change runtime behavior.

---

## Synthesis Flow

At a high level, the Charter setup flow is: capture policy decisions via interview, generate (or
refresh) `charter.yaml`, check for graph-native decay, synthesize doctrine into
`.kittify/charter-packs/`, validate the bundle against the `CharterBundleManifest` v2.0.0 schema, and
confirm status shows no drift. For the complete command-by-command walkthrough — including flags,
what each command outputs, and how to recover from a stale bundle — follow
[How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md) rather than reproducing the
sequence here.

**`charter context`** is a separate runtime/debug command for rendering action-specific
governance context for a specific workflow action. It is not part of the generation pipeline:

```bash
# Render what governance context an agent would receive for the 'implement' action
uv run spec-kitty charter context --action implement --json
```

To change runtime policy by hand, edit `charter.yaml`'s `governance:` or `directives:` sections
directly. There is no separate sync step: the next `charter context` call reads the file as-is.
The `charter sync` command was removed (#5828); nothing replaces it.

A directive you add under the `directives:` section is **additive**: it is unioned onto the
directive set the project already resolves (the built-in catalog default, charter-activated
directives, or an explicit `governance.charter.selected_directives` selection), never a
replacement of it. If you set `governance.charter.selected_directives`, that list defines the
authoritative *base* set; the `directives:` section then layers on top of it additively. The
resolution branch is now visible: `spec-kitty charter context --action plan --json` exposes a
top-level `directives_source` (for example `catalog_fallback+project_local` when a project-local
directive is merged onto the catalog default, or `catalog_fallback` for a bare project), and the
human-readable `charter context` output prints a diagnostic when project-local directives are
merged or when the catalog-default fallback is used.

For partial regeneration of a specific directive or tactic without touching unrelated artifacts:

```bash
uv run spec-kitty charter resynthesize --topic directive:PROJECT_001
```

---

## The DRG-Backed Context Model

The charter bundle is not a flat file — it is backed by the **Doctrine Reference Graph (DRG)**.
The DRG is a directed graph whose nodes are doctrine artifacts (directives, tactics, paradigms,
styleguides, toolguides, procedures, agent profiles and the other kinds), mission actions and
glossary scopes (`NodeKind`, `src/charter/offering/drg/models.py`), and whose edges use typed
relations such as `scope`, `requires`, `suggests`, `vocabulary`, `instantiates`, `replaces`, and
`delegates_to`.

When `spec-kitty next` prepares a prompt for a mission action (for example, `implement`), the
runtime traverses the DRG from the entry point for that action and collects the relevant subgraph.
This is **governed profile invocation**: the agent receives a `(profile, action, governance-context)`
triple, where the governance context is the DRG-derived subgraph rendered as structured text.

The agent cannot see or modify the DRG directly. It receives the rendered context and acts in
accordance with the directives it finds there.

## External Governance Documents

Projects that already publish governance outside `.kittify/`, for example
`spec/constitution.md`, should keep that public document in place and reference it from
`.kittify/charter/charter.yaml`. Spec Kitty does not require the public document, `charter.yaml`,
and `charter.md` to be byte-for-byte equal — `charter.yaml` is the only one the runtime resolves.

Declare supporting docs under `governance.charter.governance_references` in `charter.yaml`
(the interview's equivalent answer writes into this same section):

```yaml
governance:
  charter:
    governance_references:
      - spec/constitution.md
```

`spec-kitty charter context --action ...` renders these paths as required governance reading.
`spec-kitty charter status` reports missing or unsafe references so operators can fix stale paths.
All referenced paths must be repository-relative and stay inside the repo root.

---

## Bootstrap vs Compact Context

`spec-kitty charter context --action <action> --json` reports which of two modes it rendered in
its `mode` field. The mode depends on the action and on whether this is its first load, not on the
size of the payload (`src/charter/activation/context.py`, `context_state.py`):

- **Bootstrap mode**: the first time an action loads context (recorded in
  `.kittify/charter/context-state.json`), or whenever a caller asks for a depth of 2 or more, the runtime
  renders the governance it resolved for that action from the DRG. This applies to `specify`,
  `plan`, `implement` and `review` (`BOOTSTRAP_ACTIONS`) and to any other action whose node is
  declared in the DRG.
- **Compact mode**: later loads of the same action get a compact view that keeps every directive,
  tactic and section id but collapses the long-form text. An action with no declared DRG node
  always gets the compact view.

Issue #787 (closed) recorded that compact mode left out free-form rules written only in
`charter.md`. The runtime resolves policy from `charter.yaml` only (see the key invariant above), so
a rule belongs there, not in `charter.md`.

---

## Key Governance Files

| File | Written by | Purpose |
|---|---|---|
| `.kittify/charter/charter.yaml` | **Human** (`governance`/`directives`/`overrides`); `charter generate` (`catalog`/`metadata` only) | The single git-tracked, authoritative structured charter |
| `.kittify/charter/activation.yaml` | `spec-kitty charter activate` / `deactivate`, `init`, presets | Activation ledger: what the project has activated and deactivated |
| `.kittify/charter/charter.md` | **Human** | Curated narrative companion; never parsed by the runtime |
| `.kittify/config.yaml` | **Human**; `charter:` pointer minted once at bootstrap | Points to the active `charter.yaml`; also declares org packs under `charter_packs.org.packs` |
| `.kittify/charter/generated/` | Agent harness | Candidate doctrine YAML consumed by `charter synthesize` |
| `.kittify/charter/synthesis-manifest.yaml` | Auto-generated (`charter synthesize`) | Manifest for promoted project-local doctrine artifacts |
| `.kittify/charter/provenance/*.yaml` | Auto-generated (`charter synthesize`) | Provenance sidecars for synthesized doctrine artifacts |
| `.kittify/charter-packs/` | Auto-generated (synthesize) | Project-local doctrine promoted by synthesizer |

See [Governance Files Reference](governance-files.md) for the full table.

---

## See Also

- [Governance Files Reference](governance-files.md) — authoritative file table
- [How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md) — initial setup walkthrough
- [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md) — day-to-day synthesis
- [Understanding Charter: Synthesis, DRG, and Governed Context](../architecture/charter-synthesis-drg.md) — deeper explanation
- [Activation Preset Usage Journey](../architecture/charter-pack-usage-journey.md) — the
  preset-driven onboarding path (`charter activate --preset` → `charter generate`) and the dispatch safety net
