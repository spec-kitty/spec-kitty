---
title: 'Activation Preset Usage Journey: Activate, Generate, and the Dispatch Safety Net'
description: Why `charter activate --preset` alone does not deliver governance on a fresh project, the `generate` follow-up, and how the dispatch fallback behaves around compilation.
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/context/charter-overview.md
- docs/context/governance-files.md
- docs/guides/how-to/governance/setup-governance.md
- docs/api/charter-commands.md
- docs/api/agent_profiles/generic-agent.md
---
# Activation Preset Usage Journey: Activate, Generate, and the Dispatch Safety Net

[How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md) documents the
**interview-driven** path to a charter (`charter interview` → `charter generate`). This page
documents the second, **preset-driven** onboarding path — `spec-kitty charter activate --preset
<name>` — which is faster to run but has a two-step shape operators can miss: activating a preset
on a fresh project does **not** deliver working governance. This page explains why, names the
exact follow-up command, and walks through how `spec-kitty dispatch`'s generic-agent safety net
behaves at each point in the journey.

An **activation preset** is a named set of activation keys that a Charter Pack ships under its
`presets/` directory (the built-in pack ships `default` and `minimal`; `spec-kitty charter pack
list` shows every pack's presets). Activating one changes the project's **active charter**.

## TL;DR

- `charter activate --preset <name>` writes activation choices. On a fresh project it does **not**
  compile them into the file the runtime actually reads.
- Until you also run `spec-kitty charter generate --no-from-interview`, the project behaves —
  correctly — as if no charter had been activated: `dispatch` keeps falling back to the generic
  agent instead of hard-failing.
- Once compiled, the compiled bundle becomes the read authority: `charter context`/`charter
  status` report the preset's governance, and `dispatch` starts running the router for real —
  `ROUTER_NO_MATCH` on an unmatched request is now the honest signal, not a bug. From then on,
  every `charter activate` (preset or single artifact) refreshes the compiled catalog by default.

## Three tiers, not two

Preset onboarding involves three distinct files, and they are not interchangeable:

| Tier | Path | Written by | Role |
|---|---|---|---|
| **Activation write store** (the active charter) | `.kittify/config.yaml` (`activated_*` keys), or the pointed-at `charter.yaml` once a `charter:` pointer exists | `charter activate` / `charter deactivate` | Records *which* artifacts your project activated. Not read directly by governance surfaces. |
| **Compiled bundle** | `.kittify/charter/charter.yaml` | The compile seam — `spec-kitty charter generate` (also exposed as `compile_charter`/`write_compiled_charter`) | The **authoritative read cache**. `charter context`, `charter status`, and the dispatch-net predicate all key on this file's presence and contents. |
| **Display companion** | `.kittify/charter/charter.md` | Seeded by `charter generate`; hand-edited afterward | Human-facing narrative. Never parsed for policy — see [How Charter Works](../context/charter-overview.md) for the full mental model of this file's role. |

`charter activate --preset` writes the first tier. Its default post-activation recompile
(`--compile`) only **refreshes** a compiled bundle that already exists; it never creates one (see
[Why activation does not bootstrap a bundle](#why-activate-does-not-bootstrap) below), which is why
activating a preset on a fresh project and then immediately checking `charter status` can look like
nothing happened.

## Step 1 — `charter activate --preset`

```bash
spec-kitty charter activate --preset minimal
```

This applies the preset with **replace semantics**: every activation key the preset lists is
written (plus any ids your org packs require), and every key it governs but leaves out is removed.
If the change would alter a key you customized by hand, the command refuses and names the key;
pass `--force` to apply the preset anyway. `--pack <name>` picks the pack whose preset applies
(default `built-in`), and `--json` prints the applied preset. The command does not touch
`.kittify/charter/charter.md` at all.

On a fresh project (no compiled bundle yet), at this point:

- `spec-kitty charter status` and `spec-kitty charter context --action <action>` still report the
  charter as unavailable — the same as an unconfigured project. This is not a bug; it is tier 2
  being genuinely absent.
- `spec-kitty dispatch` on an unmatched request still falls back to the warned generic agent (see
  [The dispatch safety net](#the-dispatch-safety-net) below) — activating a preset must never leave
  dispatch *worse* than an empty project.

## Step 2 — compile the bundle

```bash
spec-kitty charter activate --preset minimal
spec-kitty charter generate --no-from-interview
```

`charter generate` runs the compile seam and creates the compiled bundle. It needs a git working
tree. After that first compile, every `charter activate` and `charter deactivate` recompiles the
catalog through the same seam by default; `--no-compile` skips that refresh (the catalog may then
go stale until the next `charter generate`), and `--resynthesize` runs the full synthesis pipeline
instead.

<a id="why-activate-does-not-bootstrap"></a>

### Why activation does not bootstrap a bundle

Creating the bundle is a separate step because `generate` does more than the bare minimum:
it requires a git working tree, seeds `charter.md` when absent, creates `library/`, writes
`.gitignore` entries, stages files, and migrates `config.yaml` to a `charter:` pointer. Folding all
of that into `activate` would silently change its contract from a lightweight activation write into
a heavier, git-dependent operation, and minting the `charter:` pointer as a side effect would move
the activation write store off `config.yaml` in the middle of an activation. Keeping the first
compile explicit keeps both contracts predictable.

After compilation, `charter status` and `charter context --action <action>` report the preset's
activated directive/tactic set (not the full built-in catalog, and not "charter file not found").
This holds even if the display-only `charter.md` is later deleted — the read authority is
`charter.yaml`, not `charter.md`.

## The dispatch safety net

`spec-kitty dispatch` falls back to the generic agent when a request doesn't match a routable
profile — a safety net so an unmatched request never hard-fails on an unconfigured project. Whether
that fallback engages is decided by a predicate that keys on **compiled-bundle presence** plus the
direct dispatch-routability signals (an org pack, or an explicit agent-profile activation) — not on
whether *any* config activation has happened.

| Project state | Compiled bundle? | Unmatched `dispatch` result |
|---|---|---|
| Nothing configured | Absent | Falls back to the generic agent (baseline). |
| `charter activate --preset` only, no bundle | Absent | **Still** falls back to the generic agent — activating a preset never leaves dispatch worse than doing nothing. |
| `charter activate --preset` + `generate` (compiled) | Present | The router runs for real. An unmatched request now returns `ROUTER_NO_MATCH` — the *honest* signal, since the project opted into a compiled bundle. |
| Org pack or explicit agent-profile activation, no compiled bundle | Absent | The net stays disengaged and the router reaches the org profiles — no regression for projects that are routable without ever compiling a bundle. |

### What "empty" means

**"Empty" means the compiled bundle is ABSENT** — never "bundle present but its activations are
empty". Running `charter generate` on a bare project bootstraps a near-empty `charter.yaml`; that
still counts as *not* empty for dispatch purposes, because the operator explicitly opted into a
compiled bundle. `ROUTER_NO_MATCH` in that state is honest, not a regression. The predicate never
inspects bundle *contents* to decide emptiness — only bundle presence plus the org-pack/profile
routability signals — which keeps it stable against future pack additions.

### The deliberate behaviour change

Before this journey was fixed, some non-routing config-activation dimensions (directive packs,
tactic packs, toolguides, procedures, paradigms, styleguides, mission-step-contracts, and
**glossary packs**) could keep the dispatch net disengaged even with no compiled bundle and no
routable org pack or agent profile. That is no longer the case: a project that has activated
**only** dimensions like these — with no compiled bundle and nothing router-routable — now
correctly fires the generic-agent net, the same as an unconfigured project. This is a deliberate,
recorded behaviour change, not an oversight: none of those dimensions add a routable profile, so
disengaging the net for them was never actually safe. A glossary-only activation reversing back to
"net fires" is one visible instance of this broader, benign correction.

## Quick reference

```bash
# Activate a preset, then create the compiled bundle (requires a git working tree)
spec-kitty charter activate --preset minimal
spec-kitty charter generate --no-from-interview

# Confirm governance is actually live
spec-kitty charter status --json
spec-kitty charter context --action implement --json
```

If `charter status` still reports the charter as missing after `activate --preset`, that is
expected on a fresh project — go run `charter generate --no-from-interview`.

## See also

- [How Charter Works](../context/charter-overview.md) — the write-store/compiled-bundle/companion
  model in full, plus the DRG-backed context model
- [Governance Files Reference](../context/governance-files.md) — authoritative per-file table
- [How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md) — the interview-driven
  onboarding path (the alternative to activating a preset)
- [Charter CLI Reference](../api/charter-commands.md) — narrative command reference; see the
  generated [CLI Command Reference](../api/cli-commands.md#spec-kitty-charter-pack) for the full,
  `--help`-verified `charter activate` and `charter pack` flag surface
- [Generic Agent — Agent Profile](../api/agent_profiles/generic-agent.md) — the profile the
  dispatch safety net falls back to
