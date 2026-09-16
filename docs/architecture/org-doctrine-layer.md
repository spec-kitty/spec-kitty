---
title: Understanding the Org Doctrine Layer
description: How the three-layer doctrine model resolves built-in, org, and project artifacts, how provenance tracking works, and how org charter policy composes with the project charter.
doc_status: active
updated: '2026-07-14'
related:
- docs/architecture/charter-synthesis-drg.md
- docs/architecture/mission-type-resolution.md
- docs/migrations/doctrine-local-overlay-to-org-layer.md
---
# Understanding the Org Doctrine Layer

Spec Kitty resolves governance doctrine through three layers: a **built-in** layer shipped
with the CLI, an optional **org** layer fetched from one or more remote packs, and a
**project** layer maintained in the repository's own `.kittify/doctrine/`. This document
explains the model, the resolution rules, the provenance tags you will see in tooling
output, and the architectural boundary that keeps the three layers cleanly separated.

For step-by-step instructions on producing a pack, see [How to create an org doctrine
pack](../guides/how-to/governance/create-an-org-doctrine-pack.md). For migration guidance from a local
overlay, see [Migrating shared doctrine to the org layer](../migrations/doctrine-local-overlay-to-org-layer.md).

---

## The three-layer model

```
┌────────────────────────────────────────────────────────────┐
│  Project layer:   .kittify/doctrine/                       │  ← highest precedence
│  (project-local artifacts and exceptions)                  │
├────────────────────────────────────────────────────────────┤
│  Org layer:       configured packs (e.g. ~/.kittify/org/*) │
│  (company-wide directives, profiles, tactics)              │
├────────────────────────────────────────────────────────────┤
│  Built-in layer:  shipped with the spec-kitty package      │  ← lowest precedence
│  (sane defaults for every spec-kitty project)              │
└────────────────────────────────────────────────────────────┘
```

Each layer is a structured set of YAML artifacts — directives, tactics, styleguides,
toolguides, paradigms, procedures, agent profiles, mission step contracts, and DRG
graph extensions. Layers share the same schemas. Their only difference is **where they
live** and **how they are produced**.

| Layer | Source | Owned by | Activation |
|-------|--------|----------|------------|
| Built-in | spec-kitty package | CLI maintainers | Always active |
| Org | Remote pack(s) declared in `.kittify/config.yaml` | Org governance teams | Opt-in per project |
| Project | `.kittify/doctrine/` in the repository | Project maintainers | Always active when present |

The org layer is **purely additive**. Projects that do not declare an org pack are
unaffected by this feature — the built-in plus project model continues to work exactly
as it did before.

---

## Why the org layer exists

Before the org layer, an organisation that wanted to share governance across many
projects had two unattractive options:

1. **Fork the CLI** to embed company-specific directives into the built-in layer.
2. **Copy/paste** governance artifacts into every project's `.kittify/doctrine/`.

Both approaches drift over time. Fork maintenance is painful; copy/paste means each
project carries a stale snapshot of the policy.

The org layer solves this by giving organisations a versioned, PR-governed,
independently-released home for their doctrine that any number of projects can consume
without per-project bookkeeping. A security team can ship `security-v2.1.0`, an
architecture team can ship `architecture-v1.4.0`, and a project consumes both by
listing them in its config.

---

## Precedence and resolution

When resolution traverses the three layers, it walks them in order — built-in first,
then each configured org pack in declaration order, finally project — and applies
**full-replace semantics on ID collision**.

> **Full-replace means**: if an artifact ID exists in a higher-precedence layer, that
> artifact entirely replaces the lower-precedence one. There is no field-level merging
> across layers. The higher-layer artifact stands or falls on its own.

### Within the org layer

If you configure multiple org packs, declaration order determines precedence within
the org layer. The **last entry has the highest precedence** — the convention is
"later wins."

```yaml
doctrine:
  org:
    packs:
      - name: architecture     # lower precedence
        local_path: ~/.kittify/org/architecture/
      - name: security         # higher precedence (declared later)
        local_path: ~/.kittify/org/security/
```

If both packs define `acme-001-secret-handling`, the `security` pack's version wins.

### Across layers

Project beats org. Org beats built-in. The project layer is always free to override
an org artifact for legitimate exceptions. When a project artifact has the same ID as
a higher layer (org or built-in), `spec-kitty charter lint` surfaces an advisory so
the team can confirm the override is intentional.

#### Field-level merge, not artifact-level full replace

When a higher layer declares an artifact ID that already exists in a lower layer,
the higher layer **takes ownership** of the resolved artifact: its `provenance`
becomes that layer. But the merge is **field-level**, not artifact-level full
replace:

- Fields **present** in the higher layer's YAML replace same-named fields in
  the lower layer.
- Fields **absent** from the higher layer fall through to the lower layer's value.

So an org override file that contains only `id`, `title`, and `enforcement`
inherits everything else (intent, scope, examples, …) from the built-in
definition. This keeps override YAML short and focused on what actually
changes. The trade-off is that operators must understand which fields are
inherited and which are overridden.

#### Collision warnings (`DoctrineLayerCollisionWarning`)

Because field-merge is silent by default, the resolver emits a
`DoctrineLayerCollisionWarning` whenever a higher layer shadows a lower-layer
artifact. The warning text records the artifact ID, the higher and lower
layers, and how many fields were replaced vs inherited:

```
Doctrine override: directive DIRECTIVE_018 from project shadowed builtin
(3 field(s) replaced; 9 field(s) inherited).
```

These warnings are categorized as `DoctrineLayerCollisionWarning` (a
`UserWarning` subclass), so operators who maintain heavy overrides can
filter them via standard Python `warnings` machinery if desired.

#### Auditing collisions via `spec-kitty doctor doctrine`

To audit the full set of override collisions across the resolved doctrine
surface without parsing warning streams, run:

```bash
spec-kitty doctor doctrine
```

The output includes a `Collisions` section that lists every shadowed
artifact (kind, ID, higher layer, lower layer, field counts), or reports
`none — every artifact resolves from a single layer.` when no overrides
are in play. The same data is available as a `collisions` array under
`--json`.

See [ADR 2026-05-16-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md)
for the rationale behind this design.

---

## Per-mission-type governance override

The same three-layer overlay stack is what carries **per-mission-type governance
customisation** — the charter "activate and customise" step for a mission type.

A project override for a mission type's governance lives at:

```
.kittify/doctrine/mission_types/<type>/governance-profile.yaml
```

Because it sits under `.kittify/doctrine/`, it is an ordinary **project-layer**
artifact resolved through the existing `doctrine/base.py` overlay loader, giving it
the same three behaviours as every other overlaid artifact:

- **Builtin → org → project ordering.** The shipped mission-type governance is the
  builtin layer; an org pack may layer on top; the project override wins last.
- **Field-level merge.** Fields present in the override replace same-named fields;
  absent fields fall through from the lower layer — so an override that adjusts a
  single selection need not restate the whole profile.
- **`DoctrineLayerCollisionWarning`.** The resolver emits the same collision
  warning when the override shadows a lower layer, and `spec-kitty doctor doctrine`
  audits it alongside every other override.

Reusing the overlay stack is deliberate — it avoids duplicating the layer-merge
contract — but it is **not zero-cost plumbing**. The `base.py` overlay loader keys
project artifacts on an `id` field and skips files that lack one, whereas
`governance-profile.yaml` keys on `mission_type`. Wiring the profile onto the stack
therefore requires an adapter: either giving `MissionTypeProfile` an `id` and a
`BaseDoctrineRepository` subclass, or a small explicit field-merge in the resolver.
That adapter is owned, tested work — not a free ride. Modulo that adapter, per-type
governance layering reuses rather than reinvents the merge contract in
[ADR 2026-05-16-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md).
Mission-type governance itself resolves through a single charter-mediated seam
keyed off `meta.json`; this override is the project-tier customisation layer of
that seam. For the whole resolution model — the two governance grains, the reserved
slots for templates and gates, and the leak-closure invariant — see
[Mission-Type Resolution](mission-type-resolution.md) and
[ADR 2026-07-14-2](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md).

## DRG composition

The doctrine reference graph (DRG) is the typed graph that the runtime traverses to
select context for a given action. Each layer can contribute graph **fragments**, and
they merge additively:

- Built-in DRG nodes and edges are always present.
- Org packs contribute additional nodes and edges via `drg/*.graph.yaml` fragments.
- Project DRG fragments compose on top.

DRG fragments from the org layer are **additive only** — they may add new nodes and
new edges, but they must not remove or modify nodes from a lower layer. `spec-kitty
doctrine pack validate` enforces this and rejects packs whose DRG references dangle
or whose extensions try to delete built-in graph state.

This rule is what keeps the three-layer composition safe: org packs cannot
silently weaken the built-in graph, and projects cannot accidentally weaken org
graph state without a visible override.

---

## Source attribution (provenance)

Every artifact and DRG node carries a `source` tag once it is resolved:

| Tag | Meaning |
|-----|---------|
| `builtin` | Shipped with the CLI |
| `org` | Loaded from a configured org pack |
| `project` | Loaded from `.kittify/doctrine/` in the repository |

Provenance shows up in two places you can inspect directly:

```bash
# Per-action charter context (shows which artifacts apply)
uv run spec-kitty charter context --action implement --json
```

```bash
# Pack inventory (shows what is installed and where it came from)
uv run spec-kitty doctor doctrine --json
```

When you see an artifact tagged `source: org`, it tells you the artifact resolved
from one of the packs in your `doctrine.org.packs` config — not from the project
overlay or the built-in defaults. That signal is what lets a team lead audit "is our
security directive actually live in this project?" without having to grep file trees.

---

## Org charter composition

In addition to artifacts and DRG fragments, an org pack may include an
`org-charter.yaml` at its root. This is a small, structured policy document that
composes with the project charter at interview time.

The `org-charter.yaml` schema has three meaningful fields:

| Field | Purpose |
|-------|---------|
| `interview_defaults` | Pre-fill answers for the project charter interview. The user can still override during the interview. |
| `required_directives` | Directive IDs that the project charter is expected to honour. Surfaced as advisories during lint. |
| `governance_policies` | Free-form policy entries (e.g. minimum test coverage). Advisory-only in this release. |

The merge across multiple packs follows the same "later wins" rule as artifacts:

- `interview_defaults`: dict update; later packs overwrite earlier values.
- `required_directives`: union, preserving first-seen order.
- `governance_policies`: concatenated and deduplicated by `(field, value)`, keeping
  the last occurrence.

Empty packs (no `org-charter.yaml`) contribute no policy — they are doctrine-only.

> **Enforcement note**: In this release, `enforcement` values on
> `governance_policies` are read but treated uniformly as advisory. Only the literal
> string `"advisory"` is honoured today; other values parse and surface as advisories.
> Future releases may add stronger enforcement modes; pack authors should write
> `enforcement: advisory` explicitly to remain forward-compatible.

---

## The fetch model

Org packs are not resolved over the network at runtime. The `doctrine fetch` command
downloads or refreshes a **local snapshot** under each pack's configured `local_path`,
and every subsequent resolution reads from that snapshot.

This shape was chosen deliberately:

- **CI/CD safety**: pipelines do not depend on remote availability or auth.
- **Determinism**: a project produces the same context on every machine that has
  fetched the same ref.
- **Auditability**: the on-disk snapshot is the record of "what governance ran here."

`doctrine fetch` is an explicit install/update step, not a background operation. If
your org publishes a new ref, you re-run `doctrine fetch` (or your IT system does)
to pick it up. This is the same shape as `npm install` or `pip install` — fetch is
the install step; resolution is offline.

For git-managed packs, the local path is a normal working tree of the git clone
(`.git/` present). For HTTPS bundles and HTTP APIs, the snapshot is an atomic
replace of the directory with a `pack-manifest.yaml` recording the fetched version.

---

## Architectural boundary

The org layer respects a strict layer rule:

```
kernel  ←  doctrine  ←  charter  ←  specify_cli
```

The `charter` package implements DRG composition (`load_validated_graph`) and accepts
an explicit `org_root` argument when present. It must not import from
`specify_cli`. The actual config-aware resolution — reading `.kittify/config.yaml`
and turning it into a list of pack paths — lives one layer up in
`specify_cli.doctrine.config.resolve_org_roots`.

To preserve the boundary, `charter._drg_helpers._resolve_org_root()` is an **inert
stub** that always returns `None`. Real callers in `specify_cli` resolve the path
themselves and pass it explicitly. This pattern is documented in the source and
enforced by `tests/architectural/test_layer_rules.py` so that no future change can
silently introduce a circular dependency.

If you encounter `_resolve_org_root` in the codebase and wonder why it is empty:
that is the intentional design. The real logic is one layer up.

---

## Breaking change (mission B): missing packs hard-fail

Prior to mission `charter-mediated-doctrine-selection-01KRTZCA`, a doctrine pack
configured in `.kittify/config.yaml` whose `local_path` did not exist on disk was
silently skipped — resolution would degrade to the built-in + project layers
without surfacing the misconfiguration. This made stale pack entries and typoed
paths invisible until a missing artifact tripped a downstream lookup.

As of this mission (FR-015), missing packs cause `spec-kitty charter context` and
every downstream command (including `spec-kitty next`) to fail loudly with a
message naming the pack and the missing path:

```
Doctrine pack `very-serious-developers` configured at
`/home/alice/.kittify/org/very-serious-developers` does not exist on disk. Run
`spec-kitty doctrine fetch --pack very-serious-developers` to populate it, or
remove the pack from .kittify/config.yaml.
```

The diagnostic is intentionally actionable — operators are given two concrete
remediation steps, and the error is raised by `MissingDoctrinePackError`
(`src/specify_cli/doctrine/org_charter.py`) so callers can catch and report it
in their own UIs.

**Migration**

1. Run `spec-kitty doctor doctrine` to enumerate configured packs and their
   on-disk status.
2. For each missing pack, either:
   - `spec-kitty doctrine fetch --pack <name>` to populate the snapshot, or
   - Remove the entry from `.kittify/config.yaml` under `doctrine.org.packs`.
3. Re-run `spec-kitty doctor doctrine` to confirm a clean state before the next
   `charter context` build.

This behaviour is non-negotiable: silent fallback risked teams unknowingly
running without the governance their charter assumed. There is no opt-out flag.

---

## Frequently asked questions

**Can I have multiple org layers?**
Yes — list any number of packs in `doctrine.org.packs`. Within the org layer,
declaration order determines precedence (later wins).

**Can a project override an org artifact?**
Yes. The project layer always wins. Use the override when you have a genuine
project-level exception; `charter lint` will surface an advisory so the
override remains visible.

**What if the org snapshot is missing on disk?**
As of mission `charter-mediated-doctrine-selection-01KRTZCA` (FR-015), this is a
**hard error**. Earlier releases silently fell back to built-in + project; that
behaviour was hiding misconfigured packs and stale paths. See the breaking-change
section below for the migration path. `spec-kitty doctor doctrine` reports every
configured pack and flags any that are missing.

**Is it safe to gitignore the snapshot directory?**
Yes — and that is the recommended pattern. `doctrine fetch` is the install step;
treating the snapshot as cache rather than source-controlled artifacts keeps the
repository small and ensures all consumers pull the same way.

**Does the org layer change how built-in doctrine is loaded?**
No. The built-in layer is unchanged. The org layer composes on top.

**Where do I see which layer an artifact came from?**
`uv run spec-kitty charter context --action <action> --json` lists every resolved
artifact with its `source` tag. `uv run spec-kitty doctor doctrine --json` lists
installed pack contents.

---

## See also

- [How to create an org doctrine pack](../guides/how-to/governance/create-an-org-doctrine-pack.md)
- [Migrating shared doctrine to the org layer](../migrations/doctrine-local-overlay-to-org-layer.md)
- [How to set up project governance](../guides/how-to/governance/setup-governance.md)
- [Understanding Charter: Synthesis, DRG, and Governed Context](charter-synthesis-drg.md)
- [Mission-Type Resolution](mission-type-resolution.md)
