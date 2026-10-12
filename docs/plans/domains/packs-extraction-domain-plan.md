---
title: 'Packs Extraction — Domain Plan'
description: 'Durable domain plan for re-extracting the doctrine layer from src/charter/offering/ and packs/built-in/ into separately released units: invariants, sub-areas, open epics.'
doc_status: durable
updated: '2026-10-12'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/index.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/domains/api-dashboard-domain-plan.md
- docs/adr/3.x/2026-08-02-1-charter-wheel-assessment.md
- docs/adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md
- docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md
---

# Packs Extraction — Domain Plan

**Audience:** maintainers deciding what to build next in the doctrine layer's
packaging.

> **Restated 2026-09-30 (#5428).** The first version of this plan (2026-08-12) was
> written against a `src/doctrine/` package that no longer exists. It described a buildable
> `spec-kitty-doctrine` wheel and a charter↔doctrine import cycle. Both are gone:
> the package was absorbed into `src/charter/offering/`, and the dormant wheel
> groundwork was deleted. This version restates the extraction as a **re-extraction** from
> today's tree. The earlier text is in git history. It is also linked from the
> [archived 3.2.x Open-Core Delivery Plan](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-x-open-core-delivery-plan.md).

This is a **standing domain throughline**. It holds the invariants the extraction must
keep, whatever release ships each step. The epics and the milestone roadmap decide
*what ships when*. Where the two disagree on what ships in a tag, the epic wins.

---

## 1. Scope

**In scope: the physical split.** This plan covers moving doctrine code and doctrine
content across a package, wheel or repository boundary:

- **Code.** The `charter.offering` subtree (or all of `src/charter/`) is released as its
  own externally-versioned unit — **its own repository**, consumed through
  `charter.offering.api` like `spec-kitty-events` / `spec-kitty-tracker` (#3101). **Direction
  update 2026-10-12: this is now GA-gating** — its precondition #645 (move the ~129
  `specify_cli → charter` imports onto the stable API) is a GA gate leg (see the
  [4.0.0 roadmap](../4-0-0-milestone-roadmap.md)). The repository extraction itself is recorded in ADR
  [2026-10-12-2](../../adr/4.x/2026-10-12-2-charter-extraction-to-its-own-repository.md); the
  extraction mechanics ride with a dedicated epic (to be filed).
- **Content.** Doctrine content for **both** pack tiers is authored in `spec-kitty-open-packs`
  and vendored into the repository at release: `packs/built-in/` (#3504) and, as of the
  2026-10-12 direction update, `packs/internal/` as well — a **source-location move only**. A
  later step may fetch built-in content at runtime (#3022). The packaging invariants are
  unchanged (§3.2).
- **Distribution integrity.** Pinned, checksummed and verifiable pack distribution
  (#2539, on 4.x Work).

**Out of scope: authoring and governance.** Pack tiers (`built-in → org → project`),
DRG merge semantics (`enhances`, `overrides`, `specializes_from`) and `component-type`
immutability belong to the
[Doctrine & Charter Domain Plan §3.2](doctrine-charter-domain-plan.md). That plan owns
*how packs are authored and layered*. This plan owns *where the code and content live and
how they ship*. When a packaging change alters an authoring guarantee, link the two plans
rather than restating either one.

---

## 2. Where things stand (checked 2026-09-30)

| Fact | Evidence |
| --- | --- |
| Doctrine code lives in `src/charter/offering/`. `src/doctrine.py` is only a deprecation shim. | `pyproject.toml` `[tool.hatch.build.targets.wheel]` |
| `charter.offering` imports nothing outside itself and `kernel`, so the import cycle the first plan called "the blocker" no longer exists. | `grep` of `src/charter/offering/**/*.py` imports |
| The enforced module chain is `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`. | `tests/architectural/test_layer_rules.py` |
| The public import surface is curated in `src/charter/offering/api.py`. That was #3179, the wheel's own precondition. | `tests/architectural/test_doctrine_public_surface.py` |
| The dormant `spec-kitty-doctrine` wheel groundwork was **deleted**, not kept. No doctrine wheel has ever been built or shipped. | mission `charter-code-topology-01M152G1`; comment in `pyproject.toml` |
| Built-in content lives at the repository root in `packs/built-in/`. The CLI wheel force-includes it. | `pyproject.toml` `force-include`; `tests/cross_cutting/packaging/test_packaging_safety.py` |
| In-house doctrine lives in `packs/internal/` and never ships (its source home moves to `spec-kitty-open-packs` — source-location only; still excluded from the wheel/sdist). | ADR `2026-08-16-3`; `test_packaging_safety.py` |
| The mission data move to `packs/built-in/missions` has landed. | #3091, closed by PR #3204 |

---

## 3. Standing concerns

Each sub-area states its **invariant** (the durable "why") and its **open work** (the
part that turns over).

### 3.1 The code boundary (#3101)

**Invariant.** `charter.offering` depends only on `kernel`. Callers outside it import
through `charter.offering.api`. The layer rules and the public-surface test stay the
mechanical guard; a function-local import never papers over an upward reach.

**Open work.** #3101 is a design spike. **As of the 2026-10-12 direction update it is
GA-gating** (via its precondition #645), and the target is the charter's **own repository**
(an independently-released external contract package), not merely a wheel built in-tree. It
must decide:

- whether the released unit is `charter.offering` alone or all of `src/charter/`;
- whether `kernel` ships as its own wheel first (`src/kernel/pyproject.toml` is dormant
  metadata for that, per ADR `2026-08-02-1`);
- whether the new package starts version-locked to the CLI, as `spec-kitty-events` and
  `spec-kitty-tracker` did (ADR `2026-04-25-1`).

The repository extraction is recorded in ADR
[2026-10-12-2](../../adr/4.x/2026-10-12-2-charter-extraction-to-its-own-repository.md); its mechanics ride with a dedicated epic (to be filed);
this plan owns the invariant and the precondition, not that epic.

### 3.2 Content provenance (#3504, then #3022)

**Invariant.** A consumer's install does not change when content provenance moves. Built-in
doctrine is always present in the wheel, byte-identical to a pinned source; the filesystem
resolver `resolve_pack_root("built-in")` stays as it is. **`packs/internal/` stays excluded
from the wheel/sdist** regardless of where its source is authored (the `packs` include stays
narrowed to `packs/built-in/`, guarded by `tests/cross_cutting/packaging/test_packaging_safety.py`).
Moving a tier's *source* changes neither its presence nor its exclusion in the consumer install.

**Design of record.** ADR `2026-08-16-2` (Accepted) chose Option B: author the content in
`spec-kitty-open-packs`, and have a release step vendor a pinned, checksummed ref before
`hatch build`. **Direction update 2026-10-12:** that open-packs source home now covers **both**
tiers — `packs/built-in/` and `packs/internal/`. This is a **source-location move only** and is
**not** a reversal of ADR `2026-08-16-3` (internal is a public org pack, not force-shipped);
it extends the already-chosen built-in provenance to name internal's source home too. No
packaging code or gate changes for it.

**Open work.**
- #3504 builds the re-vendor pipeline and a local `materialize` path for contributors.
- #3022 is the deferred Option C: fetching built-in content at runtime like an org pack.
  It raises hard questions: `PackContext.pack_roots` assumes the built-in root is at
  index 0, and a missing pack would become a failure mode for every consumer's baseline
  governance. Option C waits on #3504 and on the manifest and checksum work.

### 3.3 Strangler discipline

**Invariant.** Every step lands in place on `main` as move → shim → repoint → delete.
There is no long-lived divergent branch. A consumer-visible break rides the migration
rail (`spec-kitty upgrade`) behind a deprecation shim that names its replacement and
removal version. `src/doctrine.py` is the live example.

### 3.4 Distribution integrity (#2539)

**Invariant.** Once content or code ships from a second source, the consumer can verify
what they received: pinned refs, content hashes, and later a graduated trust signal
(built-in / org / third-party / verified).

**Open work.** #2539 (owner: Robert) is on **4.x Work**, not in 4.0.0 scope. One of its
eight sub-issues is done.

---

## 4. Known gaps

1. **No acceptance check for "transparent to consumers".** Nothing tests yet that a
   consumer pinned to `charter.offering.api` survives the wheel split, or that a vendored
   `packs/built-in/` is byte-identical to the pinned open-packs ref. #3504's confirmation
   criterion and #2539 are the natural homes for those checks.
2. **Epic facets are mixed in the tracker.** #2466 carries both authoring work (§3.2 of
   the doctrine-charter plan) and packaging work (this plan) as sub-issues. The scope
   split in §1 of this plan is the reconciling map until the tracker mirrors it.
3. **Mixed GA scope as of 2026-10-12.** The charter modular extraction (§3.1, #3101, with #645
   as its GA-gating precondition) is **now a GA gate leg** — no longer post-4.0.0. The content
   provenance move (#3504/#3022) and verified distribution (#2539) remain post-4.0.0 direction,
   not GA dependencies. None of these issues is *on milestone 11* (local integrity); the GA gate
   now spans three legs (see the roadmap), and the charter-extraction leg is tracked on #645 and
   ADR `2026-10-12-2` plus a charter-repo-extraction epic (to be filed), not on milestone 11.

---

## 5. Epics at a glance

A snapshot for orientation. Check live state with
`gh issue view <n> --repo spec-kitty/spec-kitty` before acting.

| Work | Sub-area | Epic | State (2026-09-30) |
| --- | --- | --- | --- |
| Mission data into `packs/built-in/missions` | 3.3 | #3091 | **Landed** (PR #3204) |
| Curated public surface `charter.offering.api` | 3.1 | #3179 | Largely landed |
| Doctrine/charter wheel split | 3.1 | #3101 | Open, design spike, Product backlog |
| Re-vendor open-packs into `packs/built-in/` | 3.2 | #3504 | Open, Product backlog |
| Runtime-fetched built-in pack (Option C) | 3.2 | #3022 | Open, deferred, Product backlog |
| Verified distribution | 3.4 | #2539 | Open, 4.x Work |

All six sit under the parent epic #2466.

---

## 6. Cross-references

- [Doctrine & Charter Domain Plan](doctrine-charter-domain-plan.md). Its §3.2 is the
  authoring boundary for this plan.
- [API & Dashboard Domain Plan](api-dashboard-domain-plan.md).
- ADR [2026-08-02-1 charter-wheel-assessment](../../adr/3.x/2026-08-02-1-charter-wheel-assessment.md): the wheel-split assessment.
- ADR [2026-08-16-2 open-packs is source of truth for built-in doctrine](../../adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md): Option B, the re-vendor.
- ADR [2026-05-16-1 doctrine-layer merge semantics](../../adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md): the authoring seam this plan stays out of.
- [Plans index](../index.md).
