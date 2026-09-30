---
title: 'Charter Pack Usage Journey: Apply, Generate, and the Dispatch Safety Net'
description: Why `charter pack apply` alone does not deliver working governance, the required `generate` follow-up, and how the dispatch fallback behaves before and after compilation.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/context/charter-overview.md
- docs/context/governance-files.md
- docs/guides/how-to/governance/setup-governance.md
- docs/api/charter-commands.md
- docs/api/agent_profiles/generic-agent.md
---
# Charter Pack Usage Journey: Apply, Generate, and the Dispatch Safety Net

[How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md) documents the
**interview-driven** path to a charter (`charter interview` → `charter generate`). This page
documents the second, **pack-driven** onboarding path — `spec-kitty charter pack apply <name>` —
which is faster to run but has a two-step shape operators can miss: applying a pack alone does
**not** deliver working governance. This page explains why, names the exact follow-up command, and
walks through how `spec-kitty dispatch`'s generic-agent safety net behaves at each point in the
journey.

## TL;DR

- `charter pack apply` writes activation choices. It does **not** compile them into the file the
  runtime actually reads.
- Until you also run `spec-kitty charter generate` (or `apply --compile`), the project behaves —
  correctly — as if no charter had been applied: `dispatch` keeps falling back to the generic
  agent instead of hard-failing.
- Once compiled, the compiled bundle becomes the read authority: `charter context`/`charter
  status` report the pack's governance, and `dispatch` starts running the router for real —
  `ROUTER_NO_MATCH` on an unmatched request is now the honest signal, not a bug.

## Three tiers, not two

Charter-pack onboarding involves three distinct files, and they are not interchangeable:

| Tier | Path | Written by | Role |
|---|---|---|---|
| **Activation write store** | `.kittify/config.yaml` (`activated_*` keys), or the pointed-at `charter.yaml` once a `charter:` pointer exists | `charter pack apply` | Records *which* doctrine your project selected. Not read directly by governance surfaces. |
| **Compiled bundle** | `.kittify/charter/charter.yaml` | The compile seam — `spec-kitty charter generate` (also exposed as `compile_charter`/`write_compiled_charter`) | The **authoritative read cache**. `charter context`, `charter status`, and the dispatch-net predicate all key on this file's presence and contents. |
| **Display companion** | `.kittify/charter/charter.md` | Seeded by `charter generate`; hand-edited afterward | Human-facing narrative. Never parsed for policy — see [How Charter Works](../context/charter-overview.md) for the full mental model of this file's role. |

`charter pack apply` only ever touches the first tier. Nothing compiles the write store into the
compiled bundle automatically — that is a deliberate, separate step (see
[Constraint C-004](#why-apply-does-not-auto-compile) below), which is why applying a pack and then
immediately checking `charter status` can look like nothing happened.

## Step 1 — `charter pack apply`

```bash
spec-kitty charter pack apply minimal
```

This is a pure, git-agnostic, additive merge: it writes the pack's declared `activated_*` keys
into `.kittify/config.yaml` (or the pointed-at `charter.yaml`), leaving any key you already
authored untouched unless you pass `--force`. It does not require a git working tree, and it does
not touch `.kittify/charter/charter.yaml` or `.kittify/charter/charter.md` at all.

Because the compiled bundle is untouched, at this point:

- `spec-kitty charter status` and `spec-kitty charter context --action <action>` still report the
  charter as unavailable — the same as an unconfigured project. This is not a bug; it is tier 2
  being genuinely absent.
- `spec-kitty dispatch` on an unmatched request still falls back to the warned generic agent (see
  [The dispatch safety net](#the-dispatch-safety-net) below) — applying a pack must never leave
  dispatch *worse* than an empty project.
- Default `apply` output names the exact next command required to deliver working governance —
  `spec-kitty charter generate` — rather than a vague "a compile may still be needed".

## Step 2 — compile the bundle

Two equivalent ways to finish the journey:

```bash
# Two-step: apply, then compile explicitly
spec-kitty charter pack apply minimal
spec-kitty charter generate --no-from-interview

# One-step: apply with the --compile flag
spec-kitty charter pack apply minimal --compile
```

`--compile` chains the **existing** compile seam (the same one `charter generate` uses) after the
config merge — it introduces no new compiler. That means `--compile` also **inherits `generate`'s
git-worktree requirement**: default `apply` stays git-agnostic, but `apply --compile` needs a git
working tree, exactly like a standalone `charter generate` call.

<a id="why-apply-does-not-auto-compile"></a>

### Why `apply` does not auto-compile

Compiling is opt-in rather than automatic because `generate` does more than the bare minimum:
it requires a git working tree, seeds `charter.md` when absent, creates `library/`, writes
`.gitignore` entries, stages files, and migrates `config.yaml` to a `charter:` pointer. Folding all
of that into default `apply` would silently change `apply`'s contract from a lightweight,
git-agnostic merge into a heavier, git-dependent operation. Keeping the two steps distinct — and
letting `--compile` opt in to the heavier one — keeps both contracts predictable.

After compilation, `charter status` and `charter context --action <action>` report the pack's
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
| `charter pack apply` only, no compile | Absent | **Still** falls back to the generic agent — applying a pack never leaves dispatch worse than doing nothing. |
| `charter pack apply` + `generate` (compiled) | Present | The router runs for real. An unmatched request now returns `ROUTER_NO_MATCH` — the *honest* signal, since the project opted into a compiled bundle. |
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
# Fast path: apply and compile in one step (requires a git working tree)
spec-kitty charter pack apply minimal --compile

# Or explicitly, two steps
spec-kitty charter pack apply minimal
spec-kitty charter generate --no-from-interview

# Confirm governance is actually live
spec-kitty charter status --json
spec-kitty charter context --action implement --json
```

If `charter status` still reports the charter as missing after `apply`, that is expected — go run
`charter generate` (or re-run `apply --compile`).

## See also

- [How Charter Works](../context/charter-overview.md) — the write-store/compiled-bundle/companion
  model in full, plus the DRG-backed context model
- [Governance Files Reference](../context/governance-files.md) — authoritative per-file table
- [How to Set Up Project Governance](../guides/how-to/governance/setup-governance.md) — the interview-driven
  onboarding path (the alternative to pack apply)
- [Charter CLI Reference](../api/charter-commands.md) — narrative command reference; see the
  generated [CLI Command Reference](../api/cli-commands.md#spec-kitty-charter-pack) for the full,
  `--help`-verified `charter pack` flag surface
- [Generic Agent — Agent Profile](../api/agent_profiles/generic-agent.md) — the profile the
  dispatch safety net falls back to
