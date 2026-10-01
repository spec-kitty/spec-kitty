---
title: Governance Files Reference
description: Authoritative reference for every file under .kittify/charter/ — who writes it, what it contains, and whether you can edit it.
doc_status: active
updated: '2026-07-18'
related:
- docs/context/charter-overview.md
- docs/architecture/charter-pack-usage-journey.md
---
# Governance Files Reference

The Charter governance layer lives primarily in `.kittify/charter/`, with promoted project-local
doctrine under `.kittify/doctrine/`. Most files are runtime-managed or agent-generated inputs and
must not be hand-edited. This page describes the common Charter-era files and the commands that
own them.

> **Key rule**: edit `.kittify/charter/charter.yaml` for Spec Kitty runtime policy changes —
> specifically its `governance:`, `directives:`, activation, and `overrides:` sections.
> `.kittify/charter/charter.md` is a curated narrative companion; the runtime never reads it for
> policy. External governance docs such as `spec/constitution.md` are supporting context
> referenced from `charter.yaml`, not alternate authoritative charter paths. Re-run
> `charter generate` to refresh `charter.yaml`'s `catalog`/`metadata` sections, and
> `charter synthesize` to promote doctrine artifacts — do not patch those sections, runtime state,
> or synthesis outputs by hand.

---

## File Table

| File path | Who writes it | Contains | Edit directly? |
|---|---|---|---|
| `.kittify/charter/charter.yaml` | **Human** (`governance`/`directives`/activation/`overrides`); `charter generate` (`catalog`/`metadata` sections only) | The single structured charter: hand-authored policy plus a generator-refreshed doctrine catalog | `governance`/`directives`/activation/`overrides`: yes. `catalog`/`metadata`: no |
| `.kittify/charter/charter.md` | **Human**, or an agent during `/spec-kitty.charter`'s chat flow — never `charter generate` | Narrative summary of policy; may reference or summarize an external constitution | Yes — but edits have no runtime effect |
| `.kittify/config.yaml` (`charter:` key) | Minted once by `charter generate` on first bootstrap; human-editable afterward | The single pointer resolving to the active `charter.yaml` | Yes, to redirect to a different charter file |
| `.kittify/charter/interview/answers.yaml` | `charter interview` | Captured answers used by `charter generate` | Prefer re-running `charter interview` |
| `.kittify/charter/context-state.json` | Runtime context loader | Per-action first-load state for compact/bootstrap context | No |
| `.kittify/charter/generated/{directives,tactics,styleguides}/` | Agent harness | Candidate YAML artifacts consumed by `charter synthesize` | No routine hand edits |
| `.kittify/charter/synthesis-manifest.yaml` | `charter synthesize` / `charter resynthesize` | Manifest of promoted synthesized artifacts and content hashes | No |
| `.kittify/charter/provenance/*.yaml` | `charter synthesize` / `charter resynthesize` | Provenance sidecars for project-local doctrine artifacts | No |
| `.kittify/charter/.staging/` | Synthesizer | Temporary validation/promote workspace; `.failed` dirs may remain for diagnosis | No |
| `.kittify/doctrine/` | `charter synthesize` / `charter resynthesize` | Project-local doctrine overlay used with built-in doctrine | No |
| `.kittify/doctrine/PROVENANCE.md` | `charter synthesize` fresh-project path | Human-readable provenance for the minimal fresh-project doctrine seed | No |

`charter generate` refreshes `charter.yaml`'s `catalog` (doctrine reference manifest) and
`metadata` (generation timestamp) sections deterministically; it never writes `charter.md`. It no
longer materializes doctrine library pages as authoritative `library/*.md` files; doctrine content
is resolved through `charter.yaml`'s `catalog` section and the built-in/project doctrine service.

Normal hand-authored `.kittify/charter/charter.md` is the supported default. `charter generate`
refuses to overwrite a symlinked `charter.md`, including with `--force`; replace the symlink with
a normal file before generation. This guard protects the companion file from an accidental
clobber — it has no bearing on runtime policy, which never reads `charter.md`.

---

## External Governance Documents

Some repositories already have a public constitution, governance policy, or engineering handbook
outside `.kittify/` (for example `spec/constitution.md`). Do not treat `.kittify/charter/charter.md`
or `.kittify/charter/charter.yaml` as a second full copy that must stay byte-for-byte equal to that
document.

Use this ownership model instead:

| Document | Role |
|---|---|
| Public governance document outside `.kittify/` | Human-facing policy, historical record, or public project constitution. |
| `.kittify/charter/charter.yaml` | Runtime charter consumed by Spec Kitty. Its `governance`/`directives` sections should contain the operative policy agents need, plus `governance.charter.governance_references` pointers to external authority when useful. |
| `.kittify/charter/charter.md` | Human-facing narrative companion. Useful for onboarding and review; not consumed by the runtime. |

Recommended pattern:

1. Keep the external constitution as the public source for long-form governance.
2. Keep `.kittify/charter/charter.yaml`'s `governance`/`directives` sections concise and
   runtime-oriented: encode the binding directives, and reference the public constitution through
   `governance.charter.governance_references`.
3. If agents should inspect a directory of supporting policy, declare that directory under
   `governance.charter.authority_paths`:

```yaml
governance:
  charter:
    authority_paths:
      - spec/
    governance_references:
      - spec/constitution.md
```

Current Spec Kitty does not support a configured external charter path that replaces
`.kittify/charter/charter.yaml` itself — the `.kittify/config.yaml` `charter:` pointer is the one
supported redirection mechanism, and it points at a `charter.yaml` file, not at `charter.md`.

### Sync Behavior

`spec-kitty charter sync` is retained for its canonical-root resolution and the internal
`ensure_charter_bundle_fresh()` staleness check that other charter-layer modules still call — the
`charter sync` CLI command itself and the bundle-migration upgrader both depend on
its signature. It performs **no extraction** any more: it always reports `synced=False` and
`files_written=[]`, because there is nothing left to derive from `charter.md`. Running
`spec-kitty charter sync` after a hand edit to `charter.yaml` is a harmless no-op, not a required
step.

---

## Git Policy

Fresh checkouts must contain human-owned policy and must not require operators
to commit local build products. Use this policy for Spec Kitty-governed
projects:

| Path | Git policy | Refresh command |
|---|---|---|
| `.kittify/charter/charter.yaml` | Commit. This is the Spec Kitty runtime policy source. | Edit `governance:`/`directives:`/activation/`overrides:` directly; run `spec-kitty charter generate` to refresh `catalog`/`metadata`. |
| `.kittify/charter/charter.md` | Commit. Curated narrative companion, not a runtime source. | Edit directly, whenever convenient. |
| `.kittify/config.yaml` | Commit. Holds the `charter:` pointer plus agent/pack config. | Edit directly to redirect the pointer. |
| `.kittify/charter/provenance/*` | Do not commit. Synthesis provenance is regenerated with the promoted doctrine overlay. | `spec-kitty charter synthesize` |
| `.kittify/charter/synthesis-manifest.yaml` | Do not commit. Generated synthesis manifest. | `spec-kitty charter synthesize` |
| `.kittify/doctrine/graph.yaml` | Do not commit. Project-local DRG overlay synthesized locally when needed. | `spec-kitty charter synthesize` |
| `.kittify/doctrine/{directive,tactic,procedure,overlays}/` | Commit only when the project intentionally carries a durable project-local doctrine overlay. | `spec-kitty charter synthesize` or `spec-kitty charter resynthesize` |

If a project has a public governance document, keep it in that public location and reference it
from `charter.yaml`:

```yaml
governance:
  charter:
    governance_references:
      - spec/constitution.md
```

Do not enforce markdown equality between the public document and `.kittify/charter/charter.md` or
`.kittify/charter/charter.yaml` unless the project deliberately adopts a mirror policy outside
Spec Kitty's defaults.

Spec Kitty's own repository follows this split: `charter.yaml`, `charter.md`, and selected
project-local doctrine overlays are tracked, while synthesis provenance and `graph.yaml` remain
local.

When a required local generated file is missing, do not hand-create it. Run:

```bash
spec-kitty charter status
spec-kitty charter synthesize
spec-kitty charter bundle validate
```

Use `charter status` to detect missing or stale local synthesis state such as
a missing synthesized DRG. Use `charter synthesize` to regenerate that local
state. `charter bundle validate` validates the committed charter-bundle
manifest and reports missing tracked policy, missing `.gitignore` entries (if any project-local
entries are required), and invalid synthesis state when synthesis artifacts are present; it does
not require a project-local DRG to exist in fresh checkouts that intentionally rely on built-in
doctrine.

---

## What Happens If You Edit a Generated Section

`charter generate` can overwrite `charter.yaml`'s `catalog` and `metadata` sections on every run —
that refresh is a merge that leaves `governance`, `directives`, activation, and `overrides` alone,
but any hand edit made directly inside `catalog` or `metadata` will be lost the next time
`charter generate` runs. `governance` and `directives` are never touched by `generate` — edit them
freely.

Use these commands to check the state of the bundle before relying on it:

```bash
# Detect orphaned artifacts, contradictions, and staleness in the graph
uv run spec-kitty charter lint

# Validate the bundle against the canonical schema
uv run spec-kitty charter bundle validate

# Inspect current bundle state
uv run spec-kitty charter status
```

If `charter lint` reports decay, run `charter synthesize` if project-local doctrine needs to be
re-promoted, or edit `charter.yaml` directly to fix the underlying policy.

## Migrating Constitution-Era Files

Projects upgraded from early Spec Kitty layouts may still have stale governance files:

| Legacy path | Current action |
|---|---|
| `.kittify/memory/constitution.md` | Move current runtime policy into `.kittify/charter/charter.yaml`'s `governance`/`directives` sections, or keep the old file only as archived project history. |
| `.kittify/constitution/constitution.md` | Move current runtime policy into `.kittify/charter/charter.yaml`; do not keep it as an alternate runtime source. |
| `.kittify/charter/{governance,directives,metadata,references}.yaml` | Legacy pre-inversion derived files. The upgrade migration folds their content into `.kittify/charter/charter.yaml` and removes them; do not hand-recreate them. |
| `.kittify/constitution/{governance,directives,metadata}.yaml` | Delete or archive after confirming the upgrade migration has folded any remaining content into `.kittify/charter/charter.yaml`. |

If the old constitution file is still useful as public or organizational context, put it in a
normal project path such as `spec/constitution.md` and list that path under
`governance.charter.governance_references` in `charter.yaml`.

---

## Bundle Validation

The core charter bundle is validated against the **CharterBundleManifest v2.0.0** schema by:

```bash
uv run spec-kitty charter bundle validate
```

The v2.0.0 manifest tracks two files — `charter.md` and `charter.yaml` — and derives nothing:
`derived_files` is empty. `charter.yaml` is also the sole entry in `content_hash_files`, the
content-identity input set used for the bundle's freshness hash. `charter.md` is tracked (git
must contain it) but contributes nothing to that hash, since it is a companion, not an input.

`charter lint` performs graph-native decay checks — it detects orphaned directives (directives
that appear in the DRG but have no referencing tactic), contradictions (two directives with
conflicting instructions), and staleness (a directive whose provenance references a deleted or
superseded built-in directive).

---

## Generate vs Synthesize

These two operations are different:

| Command | What it does |
|---|---|
| `charter generate` | Refreshes `charter.yaml`'s `catalog` and `metadata` sections from interview answers + doctrine references. Bootstraps `governance`/`directives` from a legacy triad only on first creation of `charter.yaml`; on every later run it leaves them untouched. Never writes `charter.md`. |
| `charter sync` | Retained for canonical-root resolution and back-compat call sites. Performs no extraction — always a no-op (`synced=False`, `files_written=[]`). |
| `charter synthesize` | Validates and promotes agent-generated project-local doctrine artifacts from `.kittify/charter/generated/` to `.kittify/doctrine/`. |

Edit `charter.yaml`'s `governance`/`directives` sections directly for policy changes; run
`charter synthesize` when the doctrine overlay needs to be refreshed.

---

## See Also

- [How Charter Works](charter-overview.md) — mental model and synthesis flow
- [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md) — day-to-day synthesis workflow
- [Charter Pack Usage Journey](../architecture/charter-pack-usage-journey.md) — why `charter pack
  apply` alone leaves the compiled bundle absent, and the `generate` follow-up that produces it
