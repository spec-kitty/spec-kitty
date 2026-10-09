# Templates

**Templates** are output artifact scaffolds and interaction contracts deployed to
user projects. They shape how agents and humans produce consistent output across
missions.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `agent-onboarding/` | External-agent onboarding evidence, decomposition, and handoff templates |
| `architecture/` | Architectural design document templates (ADRs, stakeholder personas, user journeys) |
| `command-templates/` | Prompt files for `/spec-kitty.*` slash commands |
| `sets/` | Named bundles grouping related templates for coordinated deployment |
| `structure/` | Structural mapping templates (REPO_MAP, SURFACES) for repository orientation |
| `triage/` | Issue triage interaction templates (agent briefs, out-of-scope records) |

## Top-Level Templates

| File | Purpose |
|------|---------|
| `AGENTS.md` | Agent behavioral rules (path references, encoding, git discipline) |
| `agent-file-template.md` | CLAUDE.md-style project guidelines scaffold |
| `checklist-template.md` | Review/acceptance checklist scaffold |

Mission content templates live under `src/charter/offering/missions/<mission>/templates/`.

## Glossary Reference

See [Template Set](../../../docs/context/charter.md#template-set) in the
charter glossary context.
