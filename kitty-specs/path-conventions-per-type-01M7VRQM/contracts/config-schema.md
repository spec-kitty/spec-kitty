# Contract: `project.path_conventions` schema

```yaml
# round-trip: skip: .kittify/config.yaml shape sketch (non-Pydantic operator config); the reader is tested in tests/specify_cli/config/test_path_conventions_reader.py
project:
  path_conventions:
    workspace: apps/          # flat form: applies to every mission type that declares the key
    software-dev:             # per-type section: keyed by a mission-type id
      workspace: packs/
      tests: tests/
```

| Shape | Meaning | Error (`PathConventionsConfigError`) |
|-------|---------|--------------------------------------|
| section absent | no overrides | — |
| section not a mapping | — | raise |
| `<path-key>: <string>` | flat override | unknown key, blank, absolute or `..` → raise |
| `<path-key>: <non-string, non-mapping>` | — | raise |
| `<type-id>: <mapping>` | per-type section | `<type-id>` not in the layered roster → raise; the roster cannot be read → raise |
| `<type-id>: <non-mapping>` where `<type-id>` is not a path key | — | raise as an unknown key |
| inside a section: `<path-key>: <string>` | per-type override | the same rules as flat → raise, naming `<type-id>.<key>` |
| `deliverables` (flat or inside a section) | — | warn and ignore (C-010) |
| config file missing, unreadable or corrupt | no overrides (lenient) | — |
