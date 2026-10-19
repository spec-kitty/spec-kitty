# Charter

The **charter** package is the governance bridge between the Human in Charge
(HiC) and the charter offering, the catalog of Charter Pack artifacts. It captures project-level governance
intent, compiles it into actionable bundles, and injects action-scoped context
at every execution boundary.

## What it does

1. **Interview** — guides the HiC through structured questions to record
   operating constraints, quality rules, and artifact selections.
2. **Compile** — resolves those selections transitively through the DRG and produces the `.kittify/charter/` output bundle.
3. **Context injection** — at each action boundary (specify / plan / implement /
   review), resolves which governance applies using
   Action Index intersection with project selections.

## Relationship to the charter offering

The activation side *consumes* the offering (`charter.offering`) but the
offering does not depend on it. The offering is a self-contained
catalog of reusable patterns (paradigms, directives, tactics, etc.) that can
ship independently. Charter is the application-layer code that reads from that
catalog and turns selections into project-specific governance.

**Dependency direction:** `charter` (facades, `charter.activation`) -> `charter.offering`. Never the reverse.

Runtime prompt generation under `src/specify_cli/next/` must resolve offering
artifacts through charter facades (`context.py`, `resolver.py`, `catalog.py`,
`scope_router.py`) so project and org governance remains scoped by the charter
trust boundary. There is no exempt subpackage: the charter pack fetch and
scaffold adapters in `src/specify_cli/charter_packs/` reach the pack model and
tooling (`charter.offering.packs`) only through the `charter.packs` and
`charter.drg` facades, and org charter composition lives in
`charter.activation.org_charter`.

## Pack descriptor model (`pack.yaml`)

**updated: 2026-10-11**

Every Charter Pack carries one authored `pack.yaml`, deserialized into the
`PackDescriptor` model (`charter.offering.packs.pack_descriptor`). The descriptor
holds a pack's stable identity, its placement among the pack levels, its lineage,
and pack-relative pointers to the charter and DRG content it ships. This section
documents that descriptor domain model so it stands on its own as the charter
module is extracted into a detached module/repository.

> This diagram shows the **target** schema — the shape after missions
> [#6048](https://github.com/spec-kitty/spec-kitty/issues/6048) (the `pack_level`
> field) and [#6046](https://github.com/spec-kitty/spec-kitty/issues/6046) (the
> `requires_core` field) land. The governing decision is
> [ADR: a Charter Pack declares its level in pack.yaml](../../docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md).
> Today's on-disk `PackDescriptor` still carries only `pack_id`, `pack_version`,
> `parent_pack` and `name`; `pack_level`, `requires_core`, `active_charter` and
> `pack_drg`, and the conditional `pack_version` rule, are the target fields this
> model draws.

![Entity-relationship diagram of the Charter Pack descriptor model. A central authored PackDescriptor entity (serialized as pack.yaml, a frozen pydantic model that forbids extra fields) carries pack_id (a required immutable 26-char ULID), pack_version (required only when pack_level is built-in, otherwise optional), name (required human handle), pack_level (required, one of built-in, org or project), requires_core (an optional core version-specifier range), parent_pack (an optional parent pack_id), and the optional pack-relative pointers active_charter and pack_drg. A self-referential parent_pack edge links a child descriptor to at most one parent descriptor as its extends/lineage edge. The pack_level field is constrained by the PackTier value vocabulary owned by kernel.pack_tiers (values built-in, org, project in precedence order). active_charter points to the Active charter file (e.g. org-charter.yaml) and pack_drg points to the DRG source, whose layout varies by level: sharded graph.yaml files plus a generated manifest for built-in, a single drg/fragment.yaml for org, and graph.yaml plus overlays for project. The authored descriptor has exactly one generated sibling, PackManifest (pack-manifest.yaml), which is machine-written and never hand-edited and holds schema_version, a provenance pack_version copy, snapshot_sha256, artifact_counts, manifest_hash, constituents, charter and presets.](diagrams/pack-descriptor-model.svg)

*Diagram source: [`diagrams/pack-descriptor-model.puml`](diagrams/pack-descriptor-model.puml) — re-render with `java -jar plantuml.jar -tsvg src/charter/diagrams/pack-descriptor-model.puml`.*

### Entities and relationships (also stated here in prose)

- **`PackDescriptor`** — serialized as `pack.yaml`, one per Charter Pack. It is a
  pydantic `BaseModel` with `extra="forbid"` and `frozen=True`: authored,
  hand-edited, and never machine-rewritten.
  - `pack_id` — required, immutable ULID (26 chars); the sole runtime identity.
  - `pack_version` — required **only** when `pack_level == built-in`; optional for
    org and project packs (a model-validator rule). For non-built-in packs the
    version lives as generated provenance on the manifest side.
  - `name` — required human handle (display and resolved commands), not the
    identity key.
  - `pack_level` — **required**; one of `built-in`, `org` or `project`.
  - `requires_core` — optional version-specifier range declaring core
    compatibility (#6046).
  - `parent_pack` — optional parent `pack_id`; `None` for a root pack.
  - `active_charter` / `pack_drg` — optional pack-relative paths.
- **`PackTier`** (value vocabulary, `kernel.pack_tiers`) — the single authority for
  the three level tokens `built-in`, `org`, `project` (in precedence order
  built-in < org < project). `pack_level` is **constrained by** this vocabulary; no
  other module may spell the tokens independently.
- **`PackManifest`** — serialized as `pack-manifest.yaml`, the **generated** sibling
  of the descriptor. It is machine-written and must never be hand-edited (pinned by
  `tests/architectural/test_pack_manifest_no_author_edit.py`). There is exactly one
  manifest per authored descriptor, living beside it in the pack directory.
- **Active charter file** — the file `active_charter` resolves to (e.g.
  `org-charter.yaml`); the charter content the pack enforces/suggests.
- **DRG source** — the file(s) `pack_drg` resolves to. The layout differs by level:
  sharded `*.graph.yaml` plus the generated manifest for the built-in pack, a single
  `drg/fragment.yaml` for an org pack, and `graph.yaml` plus overlays for a project
  pack.

Key relationships: `parent_pack` is a **self-referential lineage/"extends" edge**
(a child descriptor references at most one parent descriptor); `pack_level` is
**constrained by** `PackTier`; `active_charter` and `pack_drg` **point to** pack
files; and the authored descriptor and the generated `PackManifest` are a
**one-to-one sibling pair** in the same pack directory. The authored-vs-generated
distinction is the model's central split and is carried by stereotype and label,
not by fill colour alone.

### Concrete example

The org-level `internal` pack illustrates a filled-in descriptor:

![Concrete pack.yaml example for the org-level internal Charter Pack, showing pack_id set to a ULID, pack_version null (optional for org packs), name internal, pack_level org (highlighted), requires_core the range greater-than-or-equal 4.0 and less-than 5.0 (highlighted), parent_pack null for a root pack, active_charter org-charter.yaml, and pack_drg drg/fragment.yaml.](diagrams/pack-descriptor-example.svg)

*Diagram source: [`diagrams/pack-descriptor-example.puml`](diagrams/pack-descriptor-example.puml).*

## Key entry points

| Entry point | Purpose |
|---|---|
| `interview.py` | `CharterInterview` — the guided Q&A flow |
| `compiler.py` | `compile_charter()` — transitive resolution producing `charter.md` + `references.yaml` |
| `context.py` | `build_charter_context()` — action-scoped governance injection |
| `resolver.py` | `resolve_project_governance()` / `resolve_governance_for_profile()` — profile-aware governance resolution |
| `catalog.py` | `OfferingCatalog` / `resolve_offering_root()` — discovers available offering artifacts |
| `defaults.yaml` | Default interview answers for `--non-interactive` and "accept defaults" paths |

## Architecture references

- Container view: `docs/architecture/diagrams/02_containers/README.md` — "Charter and Governance Engine"
- Component view: `docs/architecture/diagrams/03_components/README.md` — Governance section
- Init flow: `docs/guides/how-to/governance/init-and-project-charter.md`
- Governance ADR: `docs/adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md`
- Glossary: `docs/context/governance.md`
