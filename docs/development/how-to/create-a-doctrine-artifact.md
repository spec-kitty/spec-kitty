---
title: Create a doctrine artifact
description: A concrete, followable walkthrough for authoring a new doctrine artifact end to end — file location, schema, activation, and the loose-contract asset kind.
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/how-to/create-a-pack-skill.md
- docs/architecture/doctrine-kinds.md
- docs/architecture/doctrine-relationships.md
- docs/context/charter.md
- docs/guides/how-to/governance/synthesize-doctrine.md
- docs/guides/how-to/governance/setup-governance.md
- docs/development/how-to/review-gates.md
---
# Create a doctrine artifact

This guide walks through authoring one new doctrine artifact — from picking a kind through
verifying it is live in governed mission context. It uses a **tactic** as the worked example
because tactics have the simplest schema and the most built-in precedent to copy from, but the
same six steps apply to the doctrine artifact kinds listed on the [doctrine kinds](../../architecture/doctrine-kinds.md)
page. Two kinds need a different recipe. A **pack skill** has its own page:
[Create and activate a pack skill](create-a-pack-skill.md). The loose-contract `asset` kind (a
shipped blob, not an activatable artifact) has a short recipe at the end:
[Author an asset](#author-an-asset-a-shipped-blob).

This guide covers **project-layer** artifacts — the fast, self-serve path for one project's own
doctrine. If you are building a shareable **org pack** (doctrine distributed across multiple
projects), the file layout differs; see
[Understanding the Org Layer of the Charter Offering](../../architecture/org-doctrine-layer.md) after finishing
this guide.

## Prerequisites

- A Spec Kitty project with governance set up (`.kittify/charter/charter.md` exists — see
  [How to Set Up Project Governance](../../guides/how-to/governance/setup-governance.md) if it does not yet).
- The `spec-kitty` CLI on your `PATH`.

## Step 1: Pick a kind and its project directory

Every kind has its own directory under `.kittify/charter-packs/`, its own file suffix, and its own
schema. Project-layer directories use singular names for four kinds and plural names for the
rest — this is a real, code-verified asymmetry, not a typo. The mapping has a single canonical
home: `PROJECT_KIND_DIRS` in `src/charter/offering/artifact_kinds.py` (the charter offering package, imported
by the activation layer and the CLI — there is no second copy to drift). The table below is that
mapping:

| Kind | Project directory | File suffix | Schema | ID field |
|---|---|---|---|---|
| `directive` | `.kittify/charter-packs/directive/` | `.directive.yaml` | `directive.schema.yaml` | `id` |
| `tactic` | `.kittify/charter-packs/tactic/` | `.tactic.yaml` | `tactic.schema.yaml` | `id` |
| `styleguide` | `.kittify/charter-packs/styleguide/` | `.styleguide.yaml` | `styleguide.schema.yaml` | `id` |
| `procedure` | `.kittify/charter-packs/procedure/` | `.procedure.yaml` | `procedure.schema.yaml` | `id` |
| `toolguide` | `.kittify/charter-packs/toolguides/` | `.toolguide.yaml` | `toolguide.schema.yaml` | `id` |
| `paradigm` | `.kittify/charter-packs/paradigms/` | `.paradigm.yaml` | `paradigm.schema.yaml` | `id` |
| `agent_profile` | `.kittify/charter-packs/agent_profiles/` | `.agent.yaml` | `agent-profile.schema.yaml` | `profile-id` |
| `mission_step_contract` | `.kittify/charter-packs/mission_step_contracts/` | `.step-contract.yaml` | (Pydantic model, no standalone JSON Schema file) | `id` |
| `skill` | `.kittify/charter-packs/skills/` | `.skill.yaml` | `skill.schema.yaml` | `id` |

The `skill` kind does not follow Steps 2–6 below: it needs a `skill_namespace`, a body file, and
it projects files into each tool's skill root. Follow [Create and activate a pack
skill](create-a-pack-skill.md) for it.
Schemas live under `src/charter/offering/schemas/`. If you are working from a project that installed
`spec-kitty` as a package rather than from this source checkout, the fastest way to see a kind's
required fields is to copy a real built-in file of that kind and edit it — every built-in
artifact under `packs/built-in/<kind-plural>/` is already schema-valid.

This walkthrough creates a **tactic**, so the target directory is `.kittify/charter-packs/tactic/`.

## Step 2: Choose an ID

Doctrine artifact IDs are the config-stem — the filename with its kind suffix stripped — and for
most kinds must match `^[a-z][a-z0-9-]*$` (kebab-case, starting with a letter; see the `id`
pattern in `tactic.schema.yaml`). This ID is what you pass to `spec-kitty charter activate`, so
pick something you'll type again: `example-driven-api-design`, not `Tactic For API Design`.

## Step 3: Write the artifact file

Create `.kittify/charter-packs/tactic/example-driven-api-design.tactic.yaml`. A tactic's schema
(`src/charter/offering/schemas/tactic.schema.yaml`) requires `id`, `schema_version`, `name`, and at
least one step (each step requires at least a `title`):

```yaml
schema_version: "1.0"
id: example-driven-api-design
name: Example-Driven API Design
purpose: >
  Design a new API surface by writing the concrete request/response examples first,
  then deriving the interface from what makes the examples read cleanly. Prevents
  designing an interface that is technically coherent but awkward for real callers.
steps:
  - title: Write three realistic call examples
    description: >
      Before writing any interface signature, write out three concrete example calls a
      real caller would make, including the exact request and response shape you want
      them to see.
    examples:
      - "Good: a runnable curl example with real field values, not placeholders."
  - title: Derive the interface from the examples
    description: >
      Only after the examples read naturally, write the interface (types, endpoint
      names, parameters) that would make those exact examples true.
  - title: Check for awkward callers
    description: >
      Re-read each example as if you were a caller who has never seen the design.
      If an example needs a comment to explain why a field is shaped the way it is,
      the interface needs another pass.
failure_modes:
  - "Skipping straight to the interface and retrofitting examples afterward — the examples end up justifying the design instead of shaping it."
```

Every field here maps directly onto the schema: `schema_version` must be the literal string
`"1.0"`; `steps` is a non-empty list of objects with at least a `title`; `purpose` and
`failure_modes` are optional but recommended (see the real built-in
`problem-decomposition.tactic.yaml` cited on the [doctrine kinds](../../architecture/doctrine-kinds.md#tactic) page
for a fuller example with `references` to other tactics).

For a different kind, swap the required fields per the table in Step 1 — for example an
`agent_profile` additionally requires `purpose`, `specialization`, and either `role` or `roles`
(see `src/charter/offering/schemas/agent-profile.schema.yaml`), and its ID field is `profile-id`, not
`id`.

## Step 4: Confirm the artifact is discovered

The project layer is read directly off disk — no separate "import" step. Confirm your new
file is found and parses:

```bash
spec-kitty charter list --show-available
```

Your new tactic should appear as an available-but-not-yet-activated ID under the `tactic` row.
If it does not appear, re-check the filename suffix (`.tactic.yaml`, not `.yaml`) and the
directory (`.kittify/charter-packs/tactic/`, singular).

## Step 5: Activate it

An artifact existing on disk is not the same as it being **active** — activation is what makes
an artifact eligible for context injection into governed mission actions. Activate by kind and
ID:

```bash
spec-kitty charter activate tactic example-driven-api-design
```

This is a fast, config-only write to `.kittify/config.yaml`'s `activated_tactics` list (see
`plan_activation`/`commit_plan` in `src/charter/activation/activation_engine.py`) — it does not by itself
regenerate the derived bundle. If your new tactic references other artifacts (via a `references`
field) that are not yet activated, the command warns you and suggests `--cascade`:

```bash
# Activate the tactic and everything it references, in one pass
spec-kitty charter activate tactic example-driven-api-design --cascade all

# Also eagerly refresh the derived bundle/DRG immediately (otherwise this
# happens lazily on the next synthesize)
spec-kitty charter activate tactic example-driven-api-design --resynthesize
```

> **Kinds that skip explicit activation.** `agent_profile` and `mission_step_contract` do not
> use the `activated_<kind>` list at all — all built-ins for those two kinds are available
> without an activation step (`spec-kitty charter list --all` reports them as
> "All built-ins — no explicit activation"). If you are authoring one of those two kinds, Steps
> 4–5 collapse into "confirm the file is present and well-formed"; there is no `charter activate`
> call to make.

## Step 6: Verify it took effect

```bash
# Confirm the ID now shows under "Activated" for its kind
spec-kitty charter list

# Confirm overall charter health
spec-kitty charter status

# Confirm the artifact actually surfaces in a real mission action's context —
# pick an action your tactic is relevant to
spec-kitty charter context --action specify --json
```

If `charter status` reports the bundle as stale, run `spec-kitty charter synthesize` (dry-run
first) to promote it — see
[How to Synthesize and Maintain Doctrine](../../guides/how-to/governance/synthesize-doctrine.md) for the full
synthesis workflow. If something looks wrong at any step, `spec-kitty doctor charter-packs` and
[Troubleshooting Charter Failures](../../guides/how-to/governance/troubleshoot-charter.md) are the first places to
check.

## Modeling relationships between artifacts, including tension

Every relationship between doctrine artifacts — obligation (`requires`,
`suggests`), lineage (`specializes_from`), augmentation (`enhances`,
`overrides`), and tension (`in_tension_with`, `reconciles_tension`,
`rejects`) — is an authored **DRG edge** in a `graph.yaml` fragment, never a
field on the artifact body. The full authoring reference — worked examples
for every relation, plus the URN-ordering mechanic for `in_tension_with` — is
[Doctrine relationships](../../architecture/doctrine-relationships.md); see
its ["Tension vocabulary" section](../../architecture/doctrine-relationships.md)
for how to model two co-valid artifacts that disagree (for example
DIRECTIVE_024's locality-of-change vs. DIRECTIVE_025's boy-scout rule) and
how to bridge a tension pair with a reconciler.

**`opposed_by` is retired, not an authoring option.** Use `in_tension_with` /
`reconciles_tension` / `rejects` instead — see the linked reference above for
the full semantics. It survives only as a legacy input an unmigrated
org/downstream pack may still carry; `spec-kitty migrate rewrite-opposed-by
--pack <path>` rewrites those legacy entries into the correct typed edges
(idempotent, safe to run repeatedly).

## Undoing this

```bash
spec-kitty charter deactivate tactic example-driven-api-design
```

Deactivating removes the ID from `activated_tactics`; it does not delete the file. Delete
`.kittify/charter-packs/tactic/example-driven-api-design.tactic.yaml` directly if you want the
artifact gone entirely.

## Author an asset (a shipped blob)

The walkthrough above covers the **activation** kinds. The `asset` kind works differently and
gets its own short recipe here — it is the canonical way to ship an image, font, template fixture,
or an executable script (a lint, a hook) to a downstream repo, instead of naming a repo-local
`scripts/…` or `.github/…` path a consumer does not have (see
[`review-gates.md`](review-gates.md)). An asset is a **blob** plus a **sidecar
manifest**; there is no schema on the blob and — unlike the activation kinds above — **no
`charter activate` step**. It is delivered when a reachable artifact points at it, not when you
activate it (see [Delivery verdicts](../../architecture/doctrine-kinds.md#delivery-verdicts-which-kinds-reach-a-mission)).

This recipe is executable against a fresh project — copy it verbatim.

### Step A: place the blob

The project-layer asset directory is `.kittify/charter-packs/assets/` (from the single canonical
`PROJECT_KIND_DIRS` mapping). Put the blob there. For a worked example, a shared release checklist:

```bash
mkdir -p .kittify/charter-packs/assets
printf '# Release checklist\n- [ ] Tests green\n' > .kittify/charter-packs/assets/team-release-checklist.md
```

### Step B: write the sidecar manifest

Alongside the blob, create a manifest named `<blob>.asset.yaml` — here
`.kittify/charter-packs/assets/team-release-checklist.md.asset.yaml`. The manifest is the validated
surface; it requires `id`, `mime`, and `path`, with an optional `title`:

```yaml
id: team-release-checklist
mime: text/markdown
path: team-release-checklist.md
title: Team release checklist
```

Field rules (`charter.offering.assets.models.AssetManifest`, enforced by the pack validator):

- `id` — a stable identifier, unique per pack per kind. This is what you resolve by.
- `mime` — `type/subtype` form (e.g. `text/markdown`, `image/png`); when the extension implies a
  type, `mime` must agree with it.
- `path` — the blob's path **relative to the `assets/` root**. It must resolve *inside* that root:
  an absolute path, a `..`-escape, or a symlink that leaves the root is rejected (NFR-006
  containment).
- `title` — optional human-facing display name.

### Step C: resolve it

Assets are not activated — they are resolved on demand, from any installation, with no charter
step. Confirm the asset is discoverable and resolves to your blob:

```bash
# List every resolvable asset and its source tier (built-in / org / project)
spec-kitty charter pack asset list

# Resolve one identifier to a filesystem path (exit 0 on success;
# an unknown id exits non-zero and names the id)
spec-kitty charter pack asset path team-release-checklist
```

The `path` command prints the absolute path to your blob and exits `0`. Downstream code (a mission
step, a hook, a shipped lint) consumes the asset by calling `spec-kitty charter pack asset path <id>`
and reading the file at the returned path — never by hard-coding a source-tree path. A more
specific tier wins: a project or org asset of the same `id` shadows the built-in, and the shadow is
reported by `asset list`.

There is nothing to undo — no activation entry was written. Delete the blob and its
`*.asset.yaml` manifest to remove the asset entirely.

## See also

- [Doctrine artifact kinds](../../architecture/doctrine-kinds.md) — what each kind is for, with a
  real example of each.
- [Create and activate a pack skill](create-a-pack-skill.md) — author a `skill` and project it
  into each configured tool.
- [Doctrine relationships](../../architecture/doctrine-relationships.md) — the full DRG relation
  reference, including the tension vocabulary (`in_tension_with`, `reconciles_tension`,
  `rejects`) that supersedes the retired `opposed_by` field.
- [Understanding the Org Layer of the Charter Offering](../../architecture/org-doctrine-layer.md) — how to package
  and share doctrine artifacts across multiple projects instead of authoring them project-local.
- [How to Synthesize and Maintain Doctrine](../../guides/how-to/governance/synthesize-doctrine.md) — the broader
  synthesis/resynthesis maintenance workflow this guide's Step 6 hands off to.
