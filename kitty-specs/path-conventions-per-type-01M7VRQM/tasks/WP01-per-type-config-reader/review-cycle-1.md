---
affected_files: []
cycle_number: 1
mission_slug: path-conventions-per-type-01M7VRQM
reproduction_command:
reviewed_at: '2026-11-20T07:26:30Z'
reviewer_agent: claude::generic-reviewer
wp_id: WP01
---

**Issue 1 (blocking, FR-001 / SC-001): a per-type section for the `documentation` mission type cannot be written.**

`documentation` is both a built-in mission-type id and a member of `VALID_PATH_KEYS` (`['data', 'deliverables', 'documentation', 'tests', 'workspace']`). `_split_section` treats a dict value as a per-type candidate only when `key not in VALID_PATH_KEYS`, so this config:

```yaml
project:
  path_conventions:
    workspace: apps/
    documentation:
      workspace: handbook/
```

fails with `PathConventionsConfigError: project.path_conventions.documentation must be a string directory, got dict.` (reproduced on lane-a head e6714f6e against the real layered roster, which is `['documentation', 'plan', 'research', 'software-dev']`). One of the four built-in types cannot have its own section, so FR-001 ("a mapping value keyed by a mission-type id") does not hold for it. No test covers it: test 2 only reads `documentation` through the flat fallback.

Fix: decide by value shape, not key membership. A flat value must be a string, so every mapping value is unambiguously a per-type section; `documentation: docs/` stays the flat path key and `documentation: {...}` becomes the section. A mapping under a non-type path key (for example `workspace: {a: b}`) then fails the roster check, which is still fail-closed; keep its message readable (for example, mention that a mapping value is a per-type section). Add red-first tests for:
- `documentation: {workspace: handbook/}` loads as a section, alone and beside a flat `documentation: docs/`;
- flat `documentation: docs/` alone still loads as the flat key (an existing test may already cover this);
- `workspace: {a: b}` still raises.

**Nit 1 (non-blocking):** `{"software-dev": ["src/"]}` raises `Unknown path-convention key 'software-dev'`. It fails closed as the prompt prescribes, but for a known type id the message points at the wrong mistake. Consider saying the section must be a mapping when the key is in the roster, or leave as is.

**Nit 2 (non-blocking):** `_is_artifact_routed` uses `stacklevel=4`, which is right for the flat path but points one frame short (at `load_project_path_conventions`) for the per-type path, which is one call deeper.

Verified otherwise: flat error strings are byte-identical; no existing test was edited; the roster is not read for a flat-only config; roster errors fail closed; the production default goes through `resolve_layered_roster` lazily. `pytest` on the reader, all-types and acceptance-support files: 68 passed; ruff check, ruff format and mypy are clean.
