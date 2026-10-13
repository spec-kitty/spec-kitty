# Implementation plan — charter module entry-point seams (#6188)

## Architecture

Two independent module entry-point seams, kept split (ADR `2026-10-06-1` §1), so each layer's
internals are swappable/extractable behind a stable import surface:

```
external consumers (specify_cli, runtime, glossary, mission_runtime)
        │                                   │
        ▼ offering seam                     ▼ activation seam
  charter.offering.api            charter.activation.api      (NEW)
  + charter.* offering facades            │
        │                                 │
        ▼                                 ▼
  charter.offering.*  (internals)   charter.activation.*  (internals)
```

Each seam is a **pure identity re-export** surface (explicit `X as X`, `__all__`) so consumers
bind the real object and the internals behind the seam can be rewritten/extracted without
touching a consumer. Each seam is guarded by:
- an **identity gate** (the re-export is the same object; the activation seam never fronts an
  offering symbol — the split invariant), and
- a **boundary gate** (no external consumer imports past the seam into the layer internals),
  shrink-only where a brownfield baseline exists.

## Approach (why these choices)

- **Offering seam already exists** (`charter.offering.api` + facades, C-001). This mission only
  *widens its enforcement reach*: the boundary gate scanned only `specify_cli` + `runtime`, so
  `glossary` reached `charter.offering.drg.models` unguarded. Fix: repoint glossary onto the
  `charter.drg` facade (identity-preserved) and add `glossary` + `mission_runtime` to the scan.
- **Activation seam is new.** Activation was built "no eager re-exports — import submodules
  directly", which is exactly what blocks extraction. Introduce `charter.activation.api` as the
  single seam; because 253 pre-existing internal reaches exist, enforce with a **shrink-only
  baseline ratchet** (new reaches FAIL, drained WARN) governed through `_baselines.yaml`, and
  drain tranche by tranche (owner #6099). First tranche: the mission-type-key access cluster.
- **Do NOT widen `charter.offering.api`** — the charter-blessed design prefers facade doors over
  api widening (DISPOSITION manifest; `scope-c-public-contract-delta.md`). The seam pattern is
  identity re-export through a dedicated entry module, not a swollen public manifest.

## Rebase cadence

Branch off latest `main`; rebase after spec/plan/tasks (pre-implement) and only on a staleness
notice thereafter. Collision watch: sibling run #6164 (hosted/sync removal) deletes some
`cli/commands/*` — none overlap the files this PR touches (charter/glossary, not hosted).

## Risk controls

- mypy-strict `Any`-leak (#4188): seam uses explicit `X as X` re-exports; mypy verified clean on
  the seam + repointed consumers.
- Gate baseline correctness: the activation baseline is generated from the gate's own predicate,
  so gate and baseline match by construction; growth-fails/shrink-warns tolerates over-inclusion.
