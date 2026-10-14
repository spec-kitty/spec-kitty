---
title: 'Consumer census: keep CI fan-out honest'
description: What the committed consumer census is, when its CI gates go red, how to regenerate it with --write or --check, and how to fix an unrouted consumer.
doc_status: active
updated: '2026-10-14'
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

The router (`.github/workflows/ci-router.yml`) uses the census to check that a
change to shipped pack content selects the modules whose tests read it (#6166, #6173).

## When it goes red

- **Stale census.** The `architectural-fast` job runs `consumer_census.py --check` on
  every PR. It fails when a new or changed consumer is not reflected in the
  committed file.
- **Unrouted consumer.** `tests/architectural/test_consumer_census_routing.py` fails
  when the census records a pack path that no fan-out group glob matches.
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
2. Add a glob for the path to the matching filter group in `ci-router.yml` (or add a
   new group and list it in `GROUP_MODULE_FANOUT`). Keep the transcription guard in
   step if it names the group.
3. For a module-missing red, open the census `via` evidence for that module. If its
   tests assert on the shipped content, add the module to `GROUP_MODULE_FANOUT`.
   If the read is incidental (a fixture or side effect), add it to `FANOUT_ALLOWLIST`
   with a one-line reason.
4. Re-run `--write`, then the two tests above.

The census covers pack and source paths only. The `uv.lock` route to the `upgrade`
and `status` shards lives in `DEPENDENCY_MODULE_FANOUT` (`scripts/ci/gate_selection.py`),
outside the census, because a lock file has no test consumer to derive (#6238).
