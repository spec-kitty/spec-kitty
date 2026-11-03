# Data Model: the pinned pack tree exemption

One derived relation, no stored state. Nothing in this mission writes a new file format; the
exemption is recomputed from committed git state plus the tree on disk on every preflight.

## `PinnedPackTree` (derived)

| Field | Type | Source | Meaning |
| --- | --- | --- | --- |
| `root` | repo-relative POSIX path | `OrgPackConfig.effective_root(repo_root)`, made relative | The fetched pack tree, e.g. `packs/internal` |
| `pin_path` | repo-relative POSIX path | `root + ".source.yaml"` | The lockfile that content-addresses the tree, e.g. `packs/internal.source.yaml` |
| `pin` | `charter.offering.packs.pack_pin.PackPin` | `load_pack_pin(pin_path)` | `repository`, `commit` (40-hex), `subtree`, `tree_digest`, `snapshot_sha256` |

**Derivation** `PinnedPackTree(root)` holds iff all of:

1. `root` exists and is a directory inside the repository;
2. `pin_path` is **tracked** (`kernel.git.tracked_paths`) — the lockfile is committed state;
3. `pin_path` is **clean** (`kernel.git.status_entries` reports nothing for it) — the on-disk pin
   *is* the committed pin, so no `HEAD`-blob reader and no second parser is needed;
4. `load_pack_pin(pin_path)` succeeds and `pin.subtree == root` — the pin names *this* tree, so a
   neighbouring pack cannot inherit the exemption;
5. `verify_pack_pin(pin, root)` is `True` — the level-aware clean-tree digest **and** the raw
   full-tree digest equal the pin's.

Only then may a material input under `root` be subtracted from the untracked-material dirty set.

## Exemption set

`pinned_pack_tree_roots(repo_root) -> tuple[str, ...]` returns the roots that satisfy the relation,
sorted, deduplicated, repo-relative. It is a *set of roots*, not a predicate answer, so a caller
cannot express "ignore all ignored paths" through it; subtracting is by component-wise prefix
(`path == root or path.startswith(root + "/")`), never by raw string prefix (`packs/intern` must not
match `packs/internal`).

## Fail-closed arms (all yield "no exemption", never an exception)

| Situation | Result |
| --- | --- |
| No `packs/<name>.source.yaml` beside the root | not exempt |
| Pin file untracked or dirty | not exempt |
| `load_pack_pin` raises (`PackPinError`, `OSError`, malformed YAML) | not exempt |
| `pin.tree_digest.algorithm` unknown, or `snapshot_sha256` absent | `verify_pack_pin` returns `False` → not exempt |
| `pin.subtree` names a different root | not exempt |
| `verify_pack_pin` raises (`OSError`, `ValueError` for a bad `pack.yaml`) | not exempt |
| Pack root resolves outside the repository, or `local_path` needs an unset env var | not exempt |
| Symlink anywhere in the tree | the digest helpers refuse → not exempt |

## Invariants

- **I-1**: A material input that is *not* under an exempt root is classified exactly as before this
  mission (index dirt, absent committed state, charter dirt, unsafe git state).
- **I-2**: The exemption never applies to a path the index tracks. A tracked file inside a pack tree
  is still reported by the ordinary dirty rules (`dirty & material_paths`), which this mission does
  not touch.
- **I-3**: No network, no remote git, no fetch during the preflight. Verification reads local files
  and the local index only.
- **I-4**: Nothing the exemption computes is persisted (no receipt, no marker, no cache), so a
  later pin bump or tree edit is observed on the next preflight.
