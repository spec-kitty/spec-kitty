# Data model — doctor-body-path-containment-01M5ZD3C

## BodyPathEscape (value object, frozen)

| Field | Type | Meaning |
|---|---|---|
| `pack` | `str` | the org pack name (`OrgDRGFragment.pack_name`) |
| `node` | `str` | the authored node id |
| `kind` | `str` | the node's canonical plural kind |
| `body_path` | `str` | the `body_path` exactly as written |
| `reason` | `str` | the containment primitive's refusal message |

Derived: `message` is the D5 sentence. `as_dict()` returns the JSON record.

Invariants: produced only for authored nodes with a non-empty `body_path` that `resolve_relative_path_within_root(pack_root, body_path)` refuses. A contained path produces nothing, whether or not its target exists.

## `doctor charter-packs --json` → `org_drg` (additive)

```json
"org_drg": {
  "configured_packs": [...],
  "collision_warnings": [...],
  "dangling_endpoints": [],
  "body_path_escapes": [
    {"pack": "team-pack", "node": "team-asset", "kind": "assets",
     "body_path": "../../../../etc/hostname",
     "reason": "path '../../../../etc/hostname' must not contain '..' components"}
  ],
  "errors": ["org pack 'team-pack': node 'team-asset' (assets) body_path '../../../../etc/hostname' escapes the pack root: path '../../../../etc/hostname' must not contain '..' components"]
}
```

`body_path_escapes` is always present (`[]` when nothing escapes or when loading failed). Top-level keys are unchanged.
