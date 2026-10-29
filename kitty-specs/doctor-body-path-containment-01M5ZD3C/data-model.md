# Data model — doctor-body-path-containment-01M5ZD3C

## BodyPathEscape (value object, frozen)

Home: `charter.offering.drg.org_pack_loader`.

| Field | Type | Meaning |
|---|---|---|
| `code` | `ClassVar[str]` | always `ORG_FRAGMENT_BODY_PATH_ESCAPE` (D7) |
| `pack` | `str` | the org pack name (`OrgDRGFragment.pack_name`) |
| `node` | `str` | the authored node id |
| `kind` | `str` | the node's canonical plural kind |
| `body_path` | `str` | the `body_path` exactly as written |
| `reason` | `str` | the containment primitive's refusal message, or the resolve error's text |

Derived: `message` is `org pack '<pack>': node '<node>' (<kind>) body_path '<body_path>' is not contained in the pack root: <reason>`. `as_dict()` returns the JSON record `{code, pack, node, kind, body_path, reason}`.

Invariants: produced only for authored nodes with a non-empty `body_path` that `resolve_relative_path_within_root(pack_root, body_path)` refuses, or whose resolution raises `ValueError` / `OSError` (a NUL byte, for example; recorded for that node only). A contained path produces nothing, whether or not its target exists.

## AssetPathEscape (value object, frozen) — FR-007

Home: `charter.offering.assets.repository` (exported from `charter.offering.assets`). Produced by `find_asset_path_escapes(pack, pack_root)`; the registry-aware wrapper is `charter.activation.drg_activation.find_org_asset_path_escapes`.

| Field | Type | Meaning |
|---|---|---|
| `code` | `ClassVar[str]` | always `ORG_ASSET_PATH_ESCAPE` (D7) |
| `pack` | `str` | the org pack name |
| `asset` | `str` | the sidecar's asset id |
| `path` | `str` | the sidecar's `path` exactly as written |
| `reason` | `str` | the containment primitive's refusal message (the cause of `AssetPathEscapeError`), or the resolve error's text |

Derived: `message` is `org pack '<pack>': asset '<asset>' path '<path>' is not contained in the pack's assets/ root: <reason>`. `as_dict()` returns `{code, pack, asset, path, reason}`.

Invariants: produced only for org-provenance items of `AssetRepository(org_dirs=[pack_root / "assets"])` whose `resolve_path` raises `AssetPathEscapeError`, `ValueError` or `OSError`. Built-in items are never reported. One repository per pack, so no pack shadows another. No blob is opened or read (NFR-001).

## `doctor charter-packs --json` → `org_drg` (additive)

```json
"org_drg": {
  "configured_packs": [...],
  "collision_warnings": [...],
  "dangling_endpoints": [],
  "body_path_escapes": [
    {"code": "ORG_FRAGMENT_BODY_PATH_ESCAPE", "pack": "team-pack", "node": "team-asset", "kind": "assets",
     "body_path": "../../../../etc/hostname",
     "reason": "path '../../../../etc/hostname' must not contain '..' components"}
  ],
  "asset_path_escapes": [
    {"code": "ORG_ASSET_PATH_ESCAPE", "pack": "team-pack", "asset": "team-logo",
     "path": "../../../../etc/hostname",
     "reason": "path '../../../../etc/hostname' must not contain '..' components"}
  ],
  "errors": [
    "org pack 'team-pack': node 'team-asset' (assets) body_path '../../../../etc/hostname' is not contained in the pack root: path '../../../../etc/hostname' must not contain '..' components",
    "org pack 'team-pack': asset 'team-logo' path '../../../../etc/hostname' is not contained in the pack's assets/ root: path '../../../../etc/hostname' must not contain '..' components"
  ]
}
```

`body_path_escapes` and `asset_path_escapes` are always present (`[]` when nothing escapes or when loading failed). A check that could not run adds `org-layer body_path check failed: …` or `org-layer asset path check failed: …` to `errors` and leaves its list empty. Top-level keys are unchanged.
