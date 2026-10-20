# Data Model

## Command skill identity

| Field | Form | Invariant |
|-------|------|-----------|
| command | `[a-z][a-z0-9-]*`, member of `CANONICAL_COMMANDS` | explicit set, never a prefix match |
| skill name | `spec-kitty-<command>` | ≤64 chars; equals folder; not a charter-skill or retired name |
| rel path | `.agents/skills/spec-kitty-<command>/SKILL.md` | POSIX separators in manifests |
| legacy rel path | `.agents/skills/spec-kitty.<command>/SKILL.md` | read-only: migration + doctor only |

## Command-skill manifest entry (unchanged shape)

`{path, content_hash, agents[], installed_at, spec_kitty_version}`; schema `path` pattern accepts
the canonical and the legacy form so a pre-migration manifest still loads.

## State transitions (rename migration, per legacy entry)

```
legacy entry + file hash == entry hash  -> delete SKILL.md (+ empty folder) -> drop entry
legacy entry + file hash != entry hash  -> keep file, warn "no longer managed" -> drop entry
legacy entry + file missing             -> drop entry
legacy folder without entry             -> untouched (reported by doctor skills)
```

## Frontmatter projection

`shared root` → keys ∈ ALLOWED; other top-level keys → `metadata.<key>: "<str(value)>"`.
`native root` → unchanged.
