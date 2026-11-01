# Design decisions

- **[2026-11-01][specify] Route form is the legacy published path.** Decision Moment `01M6BRRA8VAED9C86WVXDKSKBK`. A route reads `/a/b.html` with a leading slash, as doc-kitty's baseline format does; DocFX's map drops the slash. Both generators can read it; doc-kitty maps it to `/a/b/` (ADR D-5 rule 1).
- **[2026-11-01][plan] #3914's 124 URLs are redirected, not proven.** Their publication history cannot be proven from a shallow clone; a stub for a never-live URL is harmless, so all 124 get a redirect and join the baseline as map keys.
- **[2026-11-01][plan] Grow-on-publish is reported, not gated.** A blocking per-PR check would make every page-adding docs PR edit one shared file, the conflict pattern #6993 removed. The deploy job warns; the gate lands with the doc-kitty build gate (#6930, #6933).
- **[2026-11-01][plan] PR-time coverage mirror.** A `tests/docs/` test asserts every baseline URL is a page the docs tree publishes or a redirect key, so a deletion without a ledger entry fails at PR time, not at deploy.
- **[2026-11-01][implement] Rename gate scope narrowed to published pages.** With a route ledger, a deleted non-page file or a never-published page has no URL to break, so `rename_reconcile` checks only renames/deletions whose route is in `site/url-baseline.txt`. Its forward check now proves the committed map is current for every ledger move.
