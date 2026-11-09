# Data model: Docsite shared build definition

No persisted data. The one interface is the reusable workflow's call contract.

| Element | Value |
|---|---|
| Trigger | `on: workflow_call` only (no automated trigger, so no fork guard needed) |
| Input `pages-artifact` | boolean, default `false` |
| Secrets | none |
| Permissions | `contents: read` |
| Job | `build` (`name: build`), `ubuntu-24.04`, `timeout-minutes: 20` |
| Output artifact (`pages-artifact: false`) | `docs-site-<run_attempt>` containing `site/dist`, 7-day retention |
| Output artifact (`pages-artifact: true`) | `github-pages` (Pages artifact of `site/dist`) |

Invariant: the steps before the upload are identical for every caller.
