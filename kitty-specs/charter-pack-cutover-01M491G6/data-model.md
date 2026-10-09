# Data model: charter-pack-cutover-01M491G6

## Charter Pack (offer side)

A directory. Identity and lineage come from the authored descriptor; content hashes from the generated manifest.

| Part | File | Notes |
|---|---|---|
| Descriptor | `pack.yaml` | `pack_id`, `pack_version`, `parent_pack`, `name`. `accompanies_doctrine_pack` is **removed**; a descriptor that still carries it is rejected with a message naming the field (OD-2). |
| Manifest | `pack-manifest.yaml` | Generated; hashes constituents including `presets/*.yaml`; `generated_by: spec-kitty charter pack regenerate-graph`. |
| Artifacts | `<kind dirs>/` | Unchanged. |
| Graph | `drg/fragment.yaml` (org) / sharded graphs (built-in) | Unchanged. |
| Enforced activations | `org-charter.yaml` (org packs) | `required_<kind>`; activation entries use `charter_pack_id` (OD-1); new and scaffolded files declare `schema_version: 2`; a `schema_version: 1` file still validates as long as it carries no retired field, so third-party org packs without activations keep loading; an entry with `doctrine_pack_id` is rejected (`RETIRED_PACK_FIELD`) naming the replacement `charter_pack_id`. |
| Presets | `presets/<name>.yaml` | Optional; see Activation preset. |

The **project layer** is one flat root, `.kittify/charter-packs/`, holding the project's own components. It belongs to the offering, is listed by `charter pack list` as `project`, and ships no presets. Its `charter_pack_id` value is `project`.

## Activation preset

`presets/<name>.yaml` inside a pack (FR-019; schema in [contracts/activation-preset.schema.yaml](contracts/activation-preset.schema.yaml)).

| Field | Type | Meaning |
|---|---|---|
| `name` | string, matches file stem | Grammar: lowercase ASCII, starts with a letter, `[a-z0-9]` segments joined by single `-`, ≤ 64 chars. |
| `description` | string | One line, shown by `charter pack list`. |
| `activated_<plural>` | list of ids, optional | Absent: the preset leaves the kind unrestricted. List: allowlist (`[]` = none). Ids resolve against the whole offering. Presets govern every charter-activatable kind derived from `ArtifactKind`, `activated_anti_patterns` included (#5409); `activated_skills` and `activated_glossary_packs` are not governed by presets; templates and assets are not activatable. |
| `activated_kinds` | list of plurals, optional | Kind gate; must include every kind for which the preset lists ids. Absent: every kind. |
| `mission_type_activations` | list of mission-type ids, optional | Written as listed; when absent the preset leaves the project key untouched. |

Built-in presets:

- `default`: `mission_type_activations` only (the built-in mission types). No `activated_*`, no `activated_kinds`.
- `minimal`: curated `activated_directives` / `activated_tactics` (today's content), `mission_type_activations: [software-dev]`, **no** `activated_kinds` (the released `[directives, tactics]` gate was a defect).

Invariants: a preset never carries context-scoped activation entries; a preset is not an `ArtifactKind` and has no URN.

## Active charter (project activation state)

Lives in `.kittify/config.yaml`, or in `.kittify/charter/charter.yaml` when `config.yaml` carries the `charter:` pointer (resolved by `resolve_activation_write_target`).

| Key | Absent means | Present means |
|---|---|---|
| `activated_<plural>` (all kinds except skill) | every available artifact of the kind | allowlist |
| `activated_skills` | org `required_skills` + built-in defaults | allowlist |
| `activated_kinds` | every kind | kind gate |
| `mission_type_activations` | fail closed at use | allowlist |

### Applying a preset (FR-001) — state transition

```
read active charter (resolved target)
compute target := preset governed keys ∪ org required_<kind>
diff := governed keys whose value would change AND whose current value differs from what the built-in default preset leaves
if diff and not --force: refuse (exit 1), print diff, write nothing
write atomically: listed keys set; unrestricted keys removed; activated_skills / activated_glossary_packs untouched
optional: --compile / --resynthesize
```

## Legacy project state → canonical (FR-012)

The full inventory is the FR-012 table in [spec.md](spec.md). Classes and actions:

| Class | Action | Reported |
|---|---|---|
| Legacy config keys (`doctrine.org.*`, `organisation_packs`, `governance.doctrine.*`, tracker `doctrine`, answers `doctrine:`, `doctrine_pack_id`) | rename / rewrite | yes |
| Legacy project root `.kittify/doctrine/**` | move to `.kittify/charter-packs/**`; refuse on colliding paths with different content | yes (moved paths) |
| Path references (synthesis manifest, provenance sidecars, skills manifest `source_ref`, `.gitignore`) | rewrite path prefix | yes |
| Stale lists (snapshot match per key), stale 8-kind gate, released `minimal` kind gate, per-artifact `[]` | reset to absent, on the first application only (recorded) | yes, with file/key to restore |
| Customised lists, lists equal to `minimal` per-kind content | unchanged | yes, "kept for review" / "matches preset minimal" |
| Installed removed skills (manifested or hash-matched) | remove; new names installed | yes; edited copies kept and reported |

Invariants: idempotent (second `spec-kitty upgrade` changes 0 bytes); the migration is re-selected whenever the structural legacy predicate holds (legacy root, legacy keys, `doctrine_pack_id`), even when recorded as applied; user-chosen path values never rewritten; uncommitted content carried over by a plain filesystem move.

## Renamed identities (FR-009, OD-1)

| Before | After |
|---|---|
| `CharterPackManager` | `ActiveCharterManager` |
| `CharterPackConfigError` | `ActiveCharterConfigError` |
| `CHARTER_PACK_CONFIG_INVALID` | `ACTIVE_CHARTER_CONFIG_INVALID` |
| `doctrine_pack_id` | `charter_pack_id` |
| `ToolSurfaceKind.DOCTRINE_SKILL = "doctrine_skill"` | `ToolSurfaceKind.CHARTER_SKILL = "charter_skill"` |
| `DefaultCharterPackMissingError` | `DefaultPresetMissingError` |
