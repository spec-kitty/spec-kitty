# Research: Built-in pack sourced from open-packs

## R-1 Built-in parity
- **Finding**: open-packs `main` (21c8c33e) `built-in/` has the same clean-tree digest as core's `packs/built-in`.
- **Decision**: Keep the built-in pin at `7f063aec` (digest-equal) and add `subtree: built-in`. Bump to `packs/built-in` once open-packs#50 merges.

## R-2 Internal pack drift
- **Finding**: Three files differ between core and open-packs `packs/internal`: `pack.yaml`, `README.md` and `PROVENANCE.md` (only in open-packs). The open-packs `pack.yaml` drops `pack_level`, `active_charter` and `pack_drg`, which core requires (a pydantic `pack_level` missing error), and it adds `pack_version: 1.0.0`.
- **Decision** (operator, DM 01M59YNJWKKHG6KJVBGF56K0PQ): open a PR on open-packs that restores `pack_level: org`, `active_charter` and `pack_drg` and keeps `pack_version`. In core, relax `test_internal_pack_declares_no_pack_version` so it accepts the canonical version. The internal pin points at that open-packs commit. The README differences (core-only doc links) are accepted as upstream wording.
- **Alternative rejected**: inferring the level by convention in core, because it loosens the schema.

## R-3 Digest for internal
- **Finding**: `clean_tree_digest(level=...)` takes only `built-in|org|project`. Internal is an org-tier pack.
- **Decision**: The internal pin uses `level: org` for its digest, recorded in the pin as `tree_digest.level`.

## R-4 Hatch and gitignored trees
- **Finding**: hatch leaves VCS-ignored files out of the wheel and sdist unless they are artifacts or force-included.
- **Decision**: `hatch_build.py` (a `BuildHookInterface`) syncs or verifies the built-in pack, then sets `build_data["force_include"]["packs/built-in"] = "packs/built-in"` for the wheel. The sdist also lists `packs/built-in/**` under `artifacts`, so the gitignored tree ships in the sdist. A wheel built from the sdist only verifies the digest and needs no network.

## R-5 Fetch mechanism
- **Decision**: `git init` in the cache directory, then `git fetch --depth 1 --filter=blob:none <repo> <sha>`, a sparse checkout of `<subtree>`, and a digest check. After that the directory is copied into `packs/<pack>`: staging directory, then rename, so the swap is atomic. The cache key is the commit SHA plus the subtree path. No symlinks, so Windows works.
- **Alternatives rejected**: a submodule (subtree path, Windows symlinks, lane worktrees) and a uv git dependency (open-packs is not packaged).

## R-6 Offline behaviour (DM 01M59V55Z62T4BM8Z8KRNFKQ63)
- **Decision**: Reuse the cache if one exists. Otherwise fail with `PACK_SYNC_UNAVAILABLE` and a message that names `make sync-packs`.

## Adversarial challenge (deferred)
The fetch and integrity boundary (pin URL trust, digest bypass, cache poisoning) is reviewed by the post-tasks squad, as charter cadence requires. Planned dispositions are recorded there.
