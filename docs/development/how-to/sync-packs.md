---
title: How to sync and bump the built-in and internal packs
description: Fetch the pinned built-in and internal pack trees into a checkout, work offline from the cache, and bump a pin after changing pack content upstream.
doc_status: active
updated: '2026-10-19'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/development/how-to/enable-the-internal-pack.md
- docs/adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md
- docs/adr/3.x/2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md
---
# How to sync and bump the built-in and internal packs

`packs/built-in/` and `packs/internal/` are not committed to this repository. Their source
is `spec-kitty-open-packs`; core holds the pin lockfiles `packs/built-in.source.yaml` and
`packs/internal.source.yaml`. This page covers fetching the trees and bumping a pin.

## Fetch the trees

Run this once in every checkout, including each lane and coordination worktree:

```bash
make sync-packs
```

The command fetches the pinned commit, verifies the clean-tree digest and places the tree.
`make dev-setup` runs it for you. `make test-fast` does not, so a fresh worktree needs it
before tests that read pack content.

## Work offline

Fetched trees are cached at `${XDG_CACHE_HOME:-~/.cache}/spec-kitty/open-packs/<sha>/<subtree>`
and shared by all worktrees. To use only the cache:

```bash
uv run --frozen python scripts/sync_packs.py --pack all --offline
```

To verify placed trees against the pins without changing anything, add `--check`.

## Change pack content

1. Author the change in `spec-kitty-open-packs` (`packs/built-in` or `packs/internal`) and
   merge it there.
2. Bump the pin in core:

   ```bash
   spec-kitty charter pack vendor --pack built-in --ref <sha>
   ```

   `--ref` accepts a commit SHA or a branch; only the resolved SHA is written. The command
   enforces the pin's `requires_core` range and rewrites only the lockfile.
3. Run `make sync-packs` to place the new tree, then commit the lockfile.
4. Verify offline with `spec-kitty charter pack vendor --pack built-in --check`.

Never edit files under `packs/built-in/` or `packs/internal/` in core: the next sync
overwrites them. Command templates under `.claude/` and the other agent directories are
generated copies and are not edited either.

## Error codes

| Code | Meaning | Fix |
|------|---------|-----|
| `PACK_PIN_INVALID` | Lockfile missing, malformed, or still the all-zero placeholder commit | Bump the pin to a real open-packs commit |
| `PACK_COMMIT_UNRESOLVABLE` | The commit or ref cannot be found upstream, or the pinned commit lacks the pack subtree | Check the SHA exists in `spec-kitty-open-packs` and contains `packs/<pack>` |
| `PACK_SYNC_UNAVAILABLE` | No network and no cache entry | Run once online, then `--offline` works |
| `PACK_DIGEST_MISMATCH` | Fetched tree does not match the pinned digest, a cached tree was tampered with, or the fetched tree contains a symlink | Clear the cache entry (`${XDG_CACHE_HOME:-~/.cache}/spec-kitty/open-packs/<sha>`) and re-run `make sync-packs`; re-bump the pin only if the upstream content changed. Do not edit the digest by hand |
| `PACK_TREE_STALE` | Placed tree differs from the pin | Run `make sync-packs` |

A source checkout whose built-in tree was never fetched raises `BuiltInPackMissing`, which
points to `make sync-packs`. An installed wheel is never affected.

## What does not change

`packs/internal/` is still excluded from the wheel and sdist, and built-in content ships
unchanged to every consumer. See ADR `2026-08-16-3`.
