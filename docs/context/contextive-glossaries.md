---
title: Contextive Glossary Integration
description: How Spec Kitty generates Contextive-compatible YAML glossaries from the canonical glossary markdown, giving IDE users in-editor term hover panels without duplication.
doc_status: active
updated: '2026-09-08'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
---
# Contextive Glossary Integration

Spec Kitty generates [Contextive](https://contextive.tech)-compatible YAML glossary files from the
canonical glossary markdown so that IDE users get in-editor term hover panels without any manual
duplication.

## How it works

```
docs/context/*.md        ← canonical term definitions (edit here)
        │
        ▼
scripts/generate_contextive_glossaries.py
        │
        ├─ src/specify_cli/.contextive/<slug>.yml   (one per context)
        └─ src/specify_cli/<scope>/.contextive.yml  (imports → DRY)
```

- **Context YAMLs** (`src/specify_cli/.contextive/<slug>.yml`) contain the extracted terms for one
  glossary context domain.
- **Scope YAMLs** (`<package>/.contextive.yml`) use Contextive `imports:` to pull in only the
  contexts relevant to that package. This keeps files small and avoids copying definitions.

The mapping from source package → relevant contexts is in
`.kittify/traceability/contextive-map.yaml`.

## Running the generator

```bash
# Write / update all generated files
python scripts/generate_contextive_glossaries.py generate

# Check that generated files are up-to-date (exits 1 if stale)
python scripts/generate_contextive_glossaries.py check
```

## Where the mapping lives

`.kittify/traceability/contextive-map.yaml` — single source of truth for what gets generated where.

```yaml
context_base_dir: "src/specify_cli/.contextive"

scopes:
  - path: "src/glossary"
    description: "Core glossary subsystem"
    contexts:
      - lexical
      - system-events
```

## Adding a new scope mapping

1. Open `.kittify/traceability/contextive-map.yaml`.
2. Add a new entry under `scopes`:
   ```yaml
   - path: "src/specify_cli/my_new_package"
     description: "What this package does"
     contexts:
       - orchestration     # choose from docs/context/ filenames (without .md)
   ```
3. Run the generator:
   ```bash
   python scripts/generate_contextive_glossaries.py generate
   ```
4. Commit the updated map and the new `.contextive.yml` file together.

## Available context slugs

Each filename (without `.md`) under `docs/context/` is a valid context slug:

| Slug | Domain |
|------|--------|
| `configuration-project-structure` | Project layout and configuration artifacts |
| `charter` | Charter domain model and artifact taxonomy |
| `dossier` | Artifact inventory and drift detection |
| `execution` | CLI invocation and semantic safety gates |
| `governance` | Charter, ADR, and policy precedence |
| `identity` | Actors, roles, and Human-in-Charge |
| `lexical` | Glossary internal data model |
| `orchestration` | Mission, work package, and mission lifecycle |
| `practices-principles` | Working agreements |
| `system-events` | Event envelope and glossary evolution |
| `technology-foundations` | General tech terms (API, CLI, YAML, Git) |

## CI enforcement

The CI pipeline (`ci-quality.yml`) runs `check` mode automatically when any of the following paths
change in a PR:

- `glossary/**`
- `src/specify_cli/**`
- `.kittify/traceability/**`

If the generated files are stale, the check step fails and tells you to re-run the generator.

## Do not edit generated files

All files under `src/specify_cli/.contextive/` and any `<package>/.contextive.yml` file whose first
line reads `# GENERATED FILE` are machine-generated. Edit the canonical sources instead:

- Term definitions → `docs/context/<slug>.md`
- Scope mapping → `.kittify/traceability/contextive-map.yaml`
