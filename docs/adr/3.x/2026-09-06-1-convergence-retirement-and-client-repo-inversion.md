---
title: 'ADR: Convergence Retirement and Client-Repo Inversion'
description: 'The Convergence (#3881) retired the CLI→SaaS sync/daemon/delivery stack; this repo now inverts ownership as a client of upstream spec-kitty/zeitgeist and spec-kitty/saas.'
status: Accepted
date: '2026-09-06'
supersedes:
- docs/adr/3.x/2026-06-30-1-sync-daemon-identity-and-cleanup-classification.md
- docs/adr/3.x/2026-04-11-1-saas-rollout-and-readiness.md
- docs/adr/3.x/2026-08-09-1-project-sync-store-boundary.md
- docs/adr/2.x/2026-02-27-1-cli-tracker-surface-gated-by-saas-sync-flag.md
doc_status: active
kind: ADR
updated: '2026-09-06T00:00:00Z'
---

## Context and Problem Statement

The Convergence merge (**#3881**, `converge/exp-main-20260905`, landed 2026-09-05; Convergence Event
announcement **#3824**, legacy-sync teardown holding pen **#3801**) folded ~2000 commits from the
EXPERIMENTAL line onto public `main`. It did two things this ADR records as a governed decision.

**1. It retired the in-place CLI→SaaS sync subsystem.** Removed wholesale (0 git-tracked files remain;
an architectural gate — `tests/architectural/test_no_retired_subsystems.py` — plus a `pyproject.toml`
TID251 ban block keep them from silently returning):

- the local sync transport: the `spec-kitty sync` command family (22 subcommands) + daemon +
  emitter / transport-attempts / batch / offline-queue / body-outbox;
- the delivery / event-journal **emit** stack and the `src/specify_cli/saas/` package;
- the `websockets` runtime dependency.

Mission status is now **ephemeral by design**; team artifacts render **server-side**.

**2. It inverted feature-ownership.** This core repo (`Priivacy-ai/spec-kitty`) is now merely a
**CLIENT**. The **authoritative repositories** are **`spec-kitty/zeitgeist`** (the ephemeral-status
service) and **`spec-kitty/saas`** (hosted team surface). In this repo,
`src/specify_cli/zeitgeist_client/` and `src/specify_cli/saas_client/` are **consumer code**
(`saas_client` is *generated* — PR #3589 / saas#300). The rule is: **pull + use + integrate the client
HERE; author + publish the API/client UPSTREAM.**

Four Accepted ADRs still describe the pre-Convergence world and now govern deleted subsystems, which
actively misleads any reader who trusts the decision record.

## Decision

1. **Mark the following four ADRs `Superseded`**, each pointing at this ADR:
   - `docs/adr/3.x/2026-06-30-1-sync-daemon-identity-and-cleanup-classification.md` — the sync daemon it
     governs (identity/kill authority, `owner.json`, orphan reaping) is retired.
   - `docs/adr/3.x/2026-04-11-1-saas-rollout-and-readiness.md` — the `specify_cli.saas` rollout/readiness
     package it governs is deleted; residual readiness re-homed to `tracker/saas_readiness.py`, the
     SaaS-sync flag to `core/saas_sync_config.py`.
   - `docs/adr/3.x/2026-08-09-1-project-sync-store-boundary.md` — the `ProjectSyncStore` /
     `sync/project_store.py` boundary it governs is deleted with the sync transport.
   - `docs/adr/2.x/2026-02-27-1-cli-tracker-surface-gated-by-saas-sync-flag.md` — the in-place sync
     transport is gone; the `SPEC_KITTY_ENABLE_SAAS_SYNC` gate **survives** only as an auth/hosted
     visibility gate for the surviving `tracker` group, not as a sync-transport gate. Superseded to a
     clarification, not a deletion of that env var.

2. **Record the client-repo inversion** as the standing architectural fact: core = client; the
   redesign/authoring of the SaaS/zeitgeist API lives **upstream**; `zeitgeist_client`/`saas_client` are
   consumer code integrated here.

3. **Leave `docs/adr/3.x/2026-04-25-1-shared-package-boundary.md` `Accepted`.** This inversion is not a
   reversal of it — it is the **precedent it extends**. That ADR established that `spec-kitty-events` /
   `spec-kitty-tracker` are external dependencies consumed via their public surface; the client-repo
   inversion applies the same model to `zeitgeist` and `saas`.

## Consequences

- The decision record stops asserting deleted designs; readers are routed to the retirement + inversion
  from each superseded ADR.
- No zeitgeist/SaaS **redesign or authoring** epic belongs in this repo — that work lives upstream in
  `spec-kitty/zeitgeist` + `spec-kitty/saas`. The core-repo roadmap item is narrower: consume /
  integrate / upgrade the published clients. Design-inputs from the retired surface (e.g. #3801's
  holding-pen inputs, #1800 / #3549 envelope & durability lessons) feed the **upstream** redesign.
- The surviving surfaces are unaffected and sanctioned by design: `src/specify_cli/saas_client/`,
  `tracker/saas_*` (readiness/client/service), charter sync, and the `SPEC_KITTY_SYNC_*` /
  `SPEC_KITTY_ENABLE_SAAS_SYNC` env vars.
- An ADR-hygiene gate (`tests/architectural/test_adr_hygiene_convergence_retirement.py`) enforces this
  ADR's shape: the four are `Superseded` and link here; this ADR is `Accepted` and supersedes them;
  `2026-04-25-1` remains `Accepted`.
