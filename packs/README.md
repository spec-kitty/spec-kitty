# packs/

Pack tiers for Spec Kitty doctrine. The content of both tiers is authored in the
`spec-kitty-open-packs` repository; this directory holds pins and the fetched trees.

| Path | Tracked in core | Ships in the wheel |
|------|-----------------|--------------------|
| `built-in.source.yaml` | yes (pin lockfile) | n/a |
| `internal.source.yaml` | yes (pin lockfile) | n/a |
| `built-in/` | no (fetched) | yes, for every consumer |
| `internal/` | no (fetched) | never |

Do not edit `built-in/` or `internal/`: `make sync-packs` regenerates them from the pins.

To change pack content, author it upstream in `spec-kitty-open-packs`, then bump the pin:

```bash
spec-kitty charter pack vendor --pack built-in --ref <sha>
make sync-packs
```

See [`docs/development/how-to/sync-packs.md`](../docs/development/how-to/sync-packs.md) and
ADR `2026-08-16-2` (Amendment 2026-10-19). The packaging invariant of ADR `2026-08-16-3` is
unchanged. Internal pack usage: [`internal/README.md`](internal/README.md).
