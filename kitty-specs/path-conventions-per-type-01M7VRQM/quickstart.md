# Quickstart

Remap software-dev only (a content repository with no `src/`):

```yaml
# .kittify/config.yaml
project:
  path_conventions:
    software-dev:
      workspace: packs/
```

Documentation, plan and research Missions keep `docs/`, `docs/` and `research/`.

One-off: waive path conventions for one accept run, with metadata still strict:

```bash
spec-kitty accept --mission <handle> --waive-path-conventions --waive-reason "layout migration in progress"
```

Durable, per Mission (`kitty-specs/<mission>/meta.json`):

```json
{ "path_conventions": "waived", "path_conventions_rationale": "Docs-only Mission in a content repo." }
```
