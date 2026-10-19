# Contract: pack sync

`python scripts/sync_packs.py [--pack built-in|internal|all] [--offline] [--check]`
(`make sync-packs` runs `--pack all`)

| Situation | Exit | Code |
|---|---|---|
| Synced or already current | 0 | — |
| `--check` and the tree matches | 0 | — |
| `--check` and the tree is missing or stale | 1 | `PACK_TREE_STALE` |
| Digest mismatch after fetch | 1 | `PACK_DIGEST_MISMATCH` |
| Commit not resolvable | 1 | `PACK_COMMIT_UNRESOLVABLE` |
| No network and no cache | 1 | `PACK_SYNC_UNAVAILABLE` (message names `make sync-packs`) |

Runtime: when the built-in tree is absent, `built_in_root()` raises `BuiltInPackMissing`, and the message names `make sync-packs`.

`spec-kitty charter pack vendor [--pack <name>] [--ref <ref>] [--subtree <path>]` rewrites the pin (commit, subtree, digest) and touches no tracked tree.
