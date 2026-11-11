# Data Model: Docsite cutover to doc-kitty

No data is stored. The "entities" are the deploy workflow's jobs and their contract.

| Job | Needs | Runs when | Permissions | Result contract |
|-----|-------|-----------|-------------|-----------------|
| `pages` | none | core repository, or a pull request / dispatch (fork guard) | `pages: read` | output `configured` = `true` on HTTP 200, `false` on 404; any other status fails |
| `build` | `pages` | `configured == 'true'` and `pages` succeeded | `contents: read` | calls `docs-site-build.yml` with `pages-artifact: true`; uploads the `github-pages` Pages artifact |
| `deploy` | `build` | core repository, `refs/heads/main`, `build` succeeded | `pages: write`, `id-token: write` | publishes the `github-pages` artifact; environment `github-pages` |
| `smoketest` | `deploy` | core repository, `refs/heads/main`, `deploy` succeeded | `contents: read` | `python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai`; non-zero exit fails the run |

Invariants:

- Nothing publishes unless the doc-kitty build succeeded.
- Nothing publishes or probes production from a fork or off `main`.
- A smoketest failure is never swallowed.
- The `pages` concurrency group serialises deploys and never cancels one in progress.
