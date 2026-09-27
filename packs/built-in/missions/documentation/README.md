# Documentation Mission

Mission type for structured documentation creation and gap-filling. Follows the
Divio 4-type documentation system (Tutorial, How-To, Reference, Explanation).

## State Machine

```
discover → audit → design → generate → validate → publish
```

Supports three iteration modes: `initial` (from scratch), `gap_filling` (audit existing
docs), and `mission_specific` (targeted documentation).

## Contents

- `mission.yaml` — State machine with documentation-specific artifacts
- `command-templates/` — Prompt files for documentation workflow steps
- `templates/divio/` — Divio-type content scaffolds (tutorial, how-to, reference, explanation)
- `templates/generators/` — Configuration templates for API doc generators (JSDoc, Sphinx)
- `templates/` — Plan, spec, tasks, and release templates
