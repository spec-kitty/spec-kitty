---
title: Identity-Boundary CI Gate
description: 'Retired record of the former drift-detector required CI check, which ran the canonical-registry recognition test on every PR until the sync transport it policed was deleted.'
doc_status: deprecated
updated: '2026-08-26T00:00:00Z'
kind: How-To
---
# Identity-Boundary CI Gate

> **Retired (2026-08-26):** the `drift-detector` workflow and its subject were
> deleted with the CLI→SaaS sync transport (spec-kitty#5); the canonical-registry
> recognition test lived in the deleted `tests/sync/test_diagnose.py`, and the
> workflow file `.github/workflows/drift-detector.yml` no longer exists. This
> page is retained only as a historical record of the #1247 gate; the Admin
> Action below is moot.

The `drift-detector` required check used to run
`tests/sync/test_diagnose.py::TestCanonicalRegistryRecognition` on every PR
against `main`. It caught drift between the canonical registries in this
repo and the consumer-recognition contract that
`spec-kitty-end-to-end-testing#41` closed over an 8-RC peeling cycle
(rc14 -> rc22). Its workflow file was
`.github/workflows/drift-detector.yml` (deleted).

This is one of three coordinated CI gates tracked under
[`#1247`](https://github.com/Priivacy-ai/spec-kitty/issues/1247):

- `drift-detector` here (this repo).
- `cross-repo-harness-tests` in [`spec-kitty-events`](https://github.com/Priivacy-ai/spec-kitty-events) - workflow `.github/workflows/cross-repo-harness-tests.yml`.
- `identity-boundary-canary` in [`spec-kitty-saas`](https://github.com/Priivacy-ai/spec-kitty-saas) - workflow `.github/workflows/canary-gate.yml`.

This repo's drift-detector pinned no external SHA. It only ran an in-repo
test. The sibling repos' workflows pinned a specific commit of
`Priivacy-ai/spec-kitty-end-to-end-testing`; each sibling's README
`Identity-Boundary CI Gate` section documented the SHA-bump procedure.

## Admin Action

Historical only — the check this section registered no longer exists. When
the gate was live, a repo admin had to register it as required on `main`:

1. Open https://github.com/Priivacy-ai/spec-kitty/settings/branches.
1. Edit the rule for `main`.
1. Under "Require status checks to pass before merging", add the exact name
   `drift-detector`.
1. Save.

Until that step is done, the workflow still runs on every PR but its red
status does not block merge.
