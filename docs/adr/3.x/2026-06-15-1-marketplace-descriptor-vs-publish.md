---
title: 'ADR 2026-06-15-1: C-006 Amendment — Declarative `marketplace.json` Descriptor
  vs. Marketplace Publish'
description: 'Narrows constraint C-006 to prohibit install and publish actions only, permitting an inert `marketplace.json` descriptor and dropping the bare `marketplace` guard token.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-06-15'
---

## Context

The tool-surface-contract mission (`01KV2K2P`) established **C-006 / FR-016**: the
plugin-bundle projection and validation path must be *inert and declarative* — it
must **never auto-install a bundle** and **never publish it to a marketplace**.
The original regression test injected a `marketplace_publish` symbol and asserted
the guard fails; reverting it restored green.

That guard (`tests/specify_cli/tool_surface/providers/test_plugin_bundle.py`,
`test_no_install_or_publish_tokens_in_source`) was implemented by scanning bundle
module source for a list of forbidden tokens, which included the **bare token
`marketplace`**. This was a reasonable proxy for "no marketplace publish" at the
time, because no code legitimately needed to name a marketplace at all.

This mission (`01KV3NGS`) introduced **FR-023** (Claude) and **FR-029** (Codex):
the bundle build must generate a **`marketplace.json`** catalog *descriptor*
alongside the bundle so a user can later run, by hand:

```
claude plugin marketplace add <repo-url-or-path>
claude plugin install spec-kitty@spec-kitty-plugins
```

`marketplace.json` is a static, declarative manifest written into the output
staging tree (`dist/spec-kitty-plugins/...`). Writing it performs **no install,
no publish, no network I/O** — it is inert output, exactly like `plugin.json`.

The bare-`marketplace` token, however, cannot distinguish "writes a marketplace
*descriptor*" (`_write_marketplace_json`, the string literal `"marketplace.json"`)
from "publishes to a marketplace" (`marketplace_publish`). After WP05/WP06
landed, the guard tripped on the legitimate descriptor write — a false positive
that surfaced only once all nine lanes were merged (the per-WP review suites do
not run the `tests/specify_cli/tool_surface/providers/` guard).

## Decision

Narrow C-006 to its actual intent: **prohibit install/publish *actions*; permit
declarative descriptor *output*.**

Concretely, the bare `marketplace` token is removed from the guard's
`_FORBIDDEN_TOKENS`. The remaining tokens (`publish`, `auto_install`,
`autoinstall`, `register_plugin`, `enable_plugin`, `upload`) continue to enforce
the prohibition — in particular the original `marketplace_publish` regression is
still caught by the `publish` token, and any `*_publish` / `*upload*` /
`*auto_install*` action symbol still fails the guard.

What remains prohibited (unchanged):
- Auto-installing a generated bundle into a live agent directory.
- Publishing/uploading a bundle to a remote marketplace.
- Any networked or side-effecting distribution action inside `tool_surface/bundles/`.

What is now explicitly permitted:
- Writing a declarative `marketplace.json` catalog descriptor into the bundle's
  `dist/` staging tree (FR-023, FR-029). It is inert data the operator consumes
  manually via `marketplace add`.

## Consequences

- WP05/WP06 code is unchanged; the bundle projectors remain declarative.
- The guard still fails closed on real install/publish actions.
- The "merge-publish layer boundary" ADR
  (`2026-06-05-1-merge-publish-layer-boundary.md`) is unaffected: publishing
  remains a separate, explicit, out-of-band concern — generating a catalog
  descriptor is not publishing.
- Future tightening option (not taken now): relocate descriptor generation into a
  dedicated distribution layer so `tool_surface/bundles/` need not name a
  marketplace at all. Deferred as unnecessary given the narrowed, intent-aligned
  guard.
