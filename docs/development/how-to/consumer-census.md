---
title: 'Consumer census: keep CI fan-out honest'
description: What the committed consumer census is, when its CI gates go red, how to regenerate it with --write or --check, and how to fix an unrouted consumer.
doc_status: active
updated: '2026-10-19'
audience: docs/context/audience/internal/maintainer.md
type: how-to
---
# Consumer census: keep CI fan-out honest

The consumer census, `.github/ci-consumer-census.json`, records which test module
consumes which `src/**` or `packs/**` path. It is built by
`scripts/ci/consumer_census.py` from two sources: a static scan of test imports and
path literals, and a replay of a fixed set of resolver surfaces under an audit hook
(so reads a grep cannot see, such as a mission-step prompt resolved through the CLI,
are attributed too). A reader that resolves pack content outside those surfaces is
not seen (tracked in #6214).

The census checks that a change to shipped pack content selects the modules whose
tests read it (#6166, #6173). `packs/built-in/` is fetched from a pinned commit and is
not tracked (#6451), so pack content changes in a pull request only through the pin
lockfile `packs/built-in.source.yaml`. Each pack fan-out group in
`.github/workflows/ci-router.yml` is triggered by that pin alone. The pack sub-trees each
group answers for are listed in `PACK_CONTENT_SCOPES` (`scripts/ci/gate_selection.py`),
which the census uses to assign a consumed path to its group (#6480).

The census build and its tests read the synced tree, so run `make sync-packs` first.

## When it goes red

- **Stale census.** The `architectural-fast` job runs `consumer_census.py --check` on
  every PR. It fails when a new or changed consumer is not reflected in the
  committed file.
- **Unrouted consumer.** `tests/architectural/test_consumer_census_routing.py` fails
  when the census records a pack path that no fan-out group glob or `PACK_CONTENT_SCOPES`
  entry matches. The same file fails when a pack group's router filter is anything but
  the pin, or when a `PACK_CONTENT_SCOPES` glob matches no file of the synced tree.
- **Module missing from its fan-out group.** `tests/ci/test_fanout_derivation.py`
  fails when the census derives a module for a group but the module is in neither
  `GROUP_MODULE_FANOUT` nor `FANOUT_ALLOWLIST` (`scripts/ci/gate_selection.py`).

## Regenerate

```bash
python scripts/ci/consumer_census.py --write   # rebuild and write the artifact (about 25 s)
python scripts/ci/consumer_census.py --check   # exit 1 if the committed file is stale
```

Commit the regenerated file with the change that caused it.

## Fix an unrouted-consumer red

1. Read the failure: it names the pack path and the consuming module.
2. Add a glob for the path to the matching group in `PACK_CONTENT_SCOPES`
   (`scripts/ci/gate_selection.py`), not to `ci-router.yml`: a `packs/built-in/**` glob
   in the router matches no tracked file. For a new group, list it in
   `GROUP_MODULE_FANOUT` and `PACK_CONTENT_SCOPES`, and give its router filter the pin
   `packs/built-in.source.yaml` as its only glob.
3. For a module-missing red, open the census `via` evidence for that module. If its
   tests assert on the shipped content, add the module to `GROUP_MODULE_FANOUT`.
   If the read is incidental (a fixture or side effect), add it to `FANOUT_ALLOWLIST`
   with a one-line reason.
4. Re-run `--write`, then the two tests above.

The census covers pack and source paths only. The `uv.lock` route to the `upgrade`
and `status` shards lives in `DEPENDENCY_MODULE_FANOUT` (`scripts/ci/gate_selection.py`),
outside the census, because a lock file has no test consumer to derive (#6238).
