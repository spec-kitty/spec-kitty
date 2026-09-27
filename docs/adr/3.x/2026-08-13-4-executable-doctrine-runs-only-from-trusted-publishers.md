---
title: 'ADR: Executable doctrine runs only from trusted publishers (built-in trusted by position; TOFU for the rest)'
description: 'Gate assets run only from trusted packs: built-in by install position; others via a user-home TOFU store keyed on a local executable-surface hash. Untrusted is BLOCKING.'
status: Accepted
date: '2026-08-13'
related:
- docs/architecture/mission-gates.md
- docs/adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md
- docs/adr/3.x/2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md
- docs/adr/3.x/2026-08-16-1-pack-metadata-manifest-unification.md
- docs/adr/3.x/2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md
---
# Executable doctrine runs only from trusted publishers

**Filename:** `2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md`

**Status:** Accepted (2026-09-27, amended in place)

**Date:** 2026-08-13 (proposed) · 2026-09-27 (amended and accepted)

**Deciders:** Operator (ATDD)

**Technical Story:** [ADR 2026-08-13-2](2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md)
makes gates run shipped code. Org and project packs can ship gates too — arbitrary code
executing on every Mission transition. That is a supply-chain surface and needs a trust model.
Implementation tracks the #2539 epic and the #2540 enabler; signing is deferred to #2543/#2544.

---

## Amendment note (2026-09-27)

Accepted together with [ADR 2026-08-13-2](2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md)
and [ADR 2026-08-13-6](2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md)
as one set, after the pack-trust ADR review (architect-alphonso / paula-patterns squad,
operator-approved 2026-09-27). The body is **rewritten in place**. Changes against the Proposed
text:

- "Skip + warn, transition proceeds" is gone. Untrusted, hash-mismatch and tamper outcomes are
  **BLOCKING** could-not-run outcomes (fixed by the dispatcher, ADR -6).
- Trust is no longer keyed on `pack-meta.yaml`, which does not exist: packs carry `pack.yaml` and
  `pack-manifest.yaml` ([ADR 2026-08-16-1](2026-08-16-1-pack-metadata-manifest-unification.md)).
  Trust keys on the operator-config coordinate plus a **locally computed** hash of the
  executable surface.
- The consent store lives in the **user home**. Repo-committed files may only **pin** an expected
  hash; they can never grant consent.
- Added: what the hash covers, re-hash at dispatch time (TOCTOU), the first-fetch disclosure,
  the update / re-pin flow, the CI seed, and positional built-in trust.
- Release signing for built-in is **deferred** (#2543/#2544); it stays the to-be design for
  fetched packs.

## Context and Problem Statement

Declarative gates execute code shipped inside a doctrine pack. Built-in gates are first-party.
But the pack ecosystem (org packs, project packs) means a downstream pack could ship a gate
whose asset runs on every transition — an unreviewed code-execution surface.

What exists today: no trust store, no TOFU and no signing anywhere in `src/charter` or
`src/specify_cli`. Org-pack config carries `url`, `ref` and `source_type` only, with no expected
hash (`src/charter/offering/drg/org_pack_config.py`), and the git source checks out whatever
`ref` names without pinning a commit (`src/specify_cli/doctrine/sources/git_source.py`). Hash
machinery does exist, but only for cache reuse: the snapshot digest
(`src/specify_cli/doctrine/snapshot.py`) is self-written at fetch time, and the pack manifest's
per-constituent `content_hash` / `manifest_hash` (`src/specify_cli/doctrine/pack_manifest.py`,
LF-normalized in `builtin_manifest.py`) are authored by whoever built the pack. None of these is
a trust pin, but the LF-normalized hashing is the reusable basis for one.

Inert doctrine (directives, tactics, styleguides) is text and is never executed — so a trust
decision is only ever needed for **executing shipped code** (gate assets). The scope is narrow
by construction.

## Decision Drivers

- Never execute unreviewed third-party code silently.
- Never hang a Mission on a trust decision — gates fire in CI and (later) under a daemon, where
  no operator is present to prompt. A missing decision must fail **loudly**, not silently pass.
- The operator, not the pack author, is the authority: identity comes from the operator's
  config, and hashes are computed locally, never read from pack-authored metadata.
- A pull request must not be able to add a pack and approve it in the same change.
- Cosmetic edits to inert doctrine must not re-prompt.

## Considered Options

- **A — Trust everything** (execute any pack's gate). Rejected: supply-chain hole.
- **B — Trust nothing but built-in** (never run org/project gates). Rejected: kills the ecosystem value.
- **C — Trust-on-first-use (TOFU), SSH-`known_hosts` style**, keyed on the operator-config
  coordinate plus an observed content hash.

## Decision Outcome

**Chosen option: "C".**

### Tiers

- **Built-in is trusted by position.** A pack loaded from the installed wheel's `packs/built-in`
  root is trusted. "Built-in" means *where it was loaded from*, never a pack that merely names
  itself built-in. Only `packs/built-in/` ships in the wheel (ADR 2026-08-16-3).
- **Everything else is TOFU**: org packs (including `packs/internal`, which is consumed through
  the org tier via `local_path` — ADR 2026-08-16-3) and project packs. This also covers a
  freshly cloned hostile repository: its gates stay inert until the operator trusts them, the
  same way git hooks are not run on clone.

### Trust key and what is hashed

- A trust entry is keyed on the **operator-config coordinate** of the pack (the source as the
  operator's config names it: URL or `local_path`, plus `ref`) and the **observed hash**.
- The hash is **recomputed locally** over the pack's **executable surface only**: every gate
  constituent, every asset a gate references, and each gate's `interpreter` and `args`. It uses
  the existing LF-normalized hashing (`hash_content_bytes` over `builtin_manifest`'s
  LF-normalized bytes). The pack's own `pack-manifest.yaml` `manifest_hash` / `content_hash`
  values are **never** read as the trust hash, because the pack author controls them.
- Hashing only the executable surface means a typo fix in an inert directive does not re-prompt.

### Where consent and pins live

- **Consent lives in the user home**, in a `known_hosts`-style trust store under the spec-kitty
  home directory. Only the operator writes it, and only through the trust prompt or an explicit
  trust command.
- **Repo-committed files may only pin.** A committed file (for example an org-pack entry in
  `.kittify/config.yaml`) may declare an *expected* hash, with lockfile semantics: it is reviewed
  like code, and a mismatch between the pin and the locally computed hash is a tamper outcome.
  A pin **never records consent**; a pinned but unconsented pack is still untrusted.
- Repo-committed configuration also cannot demote trust outcomes below BLOCKING (ADR -6).

### When trust is checked

- **Prompt at activation / install time, never mid-transition.** At run time the decision is
  looked up non-interactively.
- **Re-hash at dispatch time.** A `local_path` pack is a mutable directory, so the executable
  surface is re-hashed at dispatch, not only at activation. A mismatch against the consented or
  pinned hash is a **tamper** outcome.
- The trust check completes before any asset is resolved or executed (ADR -2 ordering invariant).

### First fetch and updates

- **First-fetch disclosure.** TOFU trusts whatever the first fetch returned, so the activation
  prompt shows the source URL, the **resolved commit SHA**, the executable-surface hash, and the
  list of executable assets (the #2536 warning). A pack that ships executables from a git `ref`
  that is a branch (not a tag or commit SHA) gets a warning interactively and is refused in CI.
- **Updates re-prompt.** A hash change is handled like a changed `known_hosts` key: never
  accepted silently. An explicit `trust accept-update` step shows which executable files
  changed and records the new hash on consent.
- **Non-interactive mode never prompts.** An unknown or changed hash in CI or under a daemon is
  a BLOCKING could-not-run outcome. CI seeds trust from a CI-side configuration or environment
  source that lives **outside the pull-request diff**.

### Outcomes

- Untrusted, hash mismatch against a pin or consent, and tamper detected at dispatch are
  **BLOCKING** could-not-run outcomes, fixed by the dispatcher (ADR -6). There is no
  "skip and proceed" path for trust failures.
- Trust is not containment: a trusted pack's gate still runs under the ADR -2 refuse-unconfinable
  baseline.

### Signing (deferred)

Release signing remains the **to-be design**, recorded here and deferred to #2543/#2544. Built-in
ships in the same wheel as its verifier and any bundled key, so signing built-in adds nothing
near-term; positional trust already covers it. Signing's value is a provenance chain for
*fetched* packs, and that is where #2543/#2544 will pick it up.

### Consequences

#### Positive

- Third-party code never runs unreviewed; the operator's trust decision is explicit, persisted
  outside the repository, and cannot be forged by a pull request.
- Tampering with a mutable `local_path` pack between activation and dispatch is caught.
- CI never hangs on trust and never silently skips a gate: a missing seed blocks loudly.
- Inert doctrine edits never re-prompt.

#### Negative

- A home-directory store is per operator and per machine; teams need the CI seed and
  repository pins to get reproducible behaviour.
- Re-hashing the executable surface on every dispatch costs I/O on each gated transition.
- A strict CI refusal of branch refs forces pack consumers onto tags or SHAs.

#### Neutral

- Trust is orthogonal to gate correctness — a trusted gate can still be a bad check; an untrusted
  gate can still be a good one that simply will not run.
- Built-in positional trust needs no new machinery beyond knowing the load root.

### Resolved and open questions

1. *Resolved:* prompt at activation, never at first execution.
2. *Resolved (2026-09-27):* untrusted is not a skip; trust failures are BLOCKING (ADR -6).
3. *Resolved:* trust granularity is the operator-config coordinate plus the executable-surface hash.
4. *Deferred:* signing format and key rotation (#2543/#2544).
5. *Open:* the exact on-disk format of the home trust store and of repository pins
   (settled in #2540).
