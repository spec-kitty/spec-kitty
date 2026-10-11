---
title: 'ADR: Open-packs Is the Source of Truth for Built-in Doctrine; CI Re-vendors It Into the Core Release'
description: 'Inverts built-in doctrine ownership: content is authored in spec-kitty-open-packs, and CI re-vendors it into the core wheel at release so consumers see no change.'
status: Accepted
date: '2026-08-16'
related:
- docs/adr/3.x/2026-04-25-1-shared-package-boundary.md
- docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md
- docs/adr/3.x/2026-08-16-1-pack-metadata-manifest-unification.md
- docs/adr/3.x/2026-05-24-3-shipped-to-built-in-cutover.md
---

# Open-packs Is the Source of Truth for Built-in Doctrine; CI Re-vendors It Into the Core Release

**Filename:** `2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md`

**Status:** Accepted

**Date:** 2026-08-16

**Deciders:** Maintainer

**Technical Story:** Internal doctrine-pack initiative; grounds on core #2196 (catfooding) and the open-packs catalog. Depends on the open-packs distribution umbrella (#2466) and the pack manifest schema / validator / checksum work (#2467, #2471, #2539/#2543). Supersedes the "built-in is authored in core" assumption carried by mission `relocate-builtin-doctrine-packs-01KYT87F`.

---

## Amendment (2026-10-11 — pre-spec grounding for #3504)

**This amendment refines Option B. It does not replace it.** The decision text below is
unchanged history. Where the two disagree, this amendment binds.

### Why it was needed

The pre-spec research squad for [#3504](https://github.com/spec-kitty/spec-kitty/issues/3504)
found that the original text left the deciding questions open and had gone stale:

* As of 2026-10-11, `spec-kitty-open-packs` holds **no** built-in content and has **no**
  tags. There is nothing to pin. Moving the content is a prerequisite, tracked in
  [open-packs#31](https://github.com/spec-kitty/spec-kitty-open-packs/issues/31).
* Option C cites `src/doctrine/hatch_build.py` and the nested-doctrine-wheel groundwork.
  Both were deleted when doctrine was absorbed into `src/charter/offering/`
  (mission `charter-code-topology-01M152G1`). Option C now needs a fresh wheel design (#3101).
* The release builds with `python -m build`, not a bare `hatch build`. "Before `hatch build`"
  below means "before the distribution build", in `release.yml` and the manual pre-tag
  build in `RELEASE_CHECKLIST.md` alike.

### Amended decisions

1. **The vendored tree stays committed.** `packs/built-in/` remains tracked in core, but it
   is read-only there: it changes only through a pin bump, and a CI drift gate fails any PR
   whose tree does not match the pin. Materializing it at build time is rejected because it
   would make every checkout, worktree, lane worktree and CI shard fetch before any test ran,
   would break offline development, and would leave the nightly gate (which checks the exact
   release SHA) testing a tree the release never ships. The "local materialize path" in
   Consequences is therefore optional tooling, not a requirement.
2. **Pin format.** A committed lockfile records the open-packs repository URL, a **commit
   SHA** (a tag is metadata, never the pin) and a tree digest computed with the existing
   `charter.offering.packs` hashing (`snapshot_sha256` and the manifest hash). It is
   verified on every PR and again at release, never at consumer runtime: the wheel is
   immutable, and `pack-manifest.yaml` already carries a `content_hash` for every file.
   A plain SHA-256 pin is enough to start. #2539, #2543, #2467 and #2471 strengthen it
   later and do not block it.
3. **One producer for the manifest.** Open-packs generates `pack-manifest.yaml` with the
   core validator at the core version it declares. Core verifies it and never regenerates
   vendored content.
4. **Compatibility is declared.** Mission-step prompts name CLI commands and flags, and
   step contracts bind to runtime action indices, so the content cannot be versioned
   independently of core. The authored `pack.yaml` gains a core-compatibility range
   (`requires_core`), checked at vendor time. A change that touches a CLI command or a
   contract lands as a pair: the open-packs PR first, then a core PR that bumps the pin.
5. **Scope of the inversion.** Only the consumer `built-in` tier moves. `packs/internal/`
   (ADR `2026-08-16-3`) stays authored in core. Pack skills (ADR `2026-09-27-1`) that ship
   in `packs/built-in/` move with the rest of its content.
6. **The authoring flip is a separate, later step.** Until it is ruled on by the operator,
   contributors keep editing `packs/built-in/` in core, as CLAUDE.md says. Moving authorship
   to open-packs, and with it CLAUDE.md, the charter and the template-source guidance, is
   its own slice after the pin and drift gate are live.

### Sequence

open-packs#31 (seed the content, map the layout, first tag, `requires_core`) → amend core
(this ADR) → #3504 (lockfile, `spec-kitty charter pack vendor`, drift gate, release
re-verification) → the authoring flip → Option C (#3022), unchanged as the north star.

## Context and Problem Statement

Built-in doctrine content today is authored **inside** the core repository at
`packs/built-in/` and shipped to consumers by force-inclusion in the PyPI wheel
(mission `relocate-builtin-doctrine-packs-01KYT87F` relocated it there from
`src/doctrine/**` and drew the shared `resolve_pack_root(tier)` seam). The
`spec-kitty-open-packs` repository was created to be the **canonical, curated,
community-friendly publishing home** for doctrine packs — its own vision statement
frames the monolithic built-in bundle as *the problem* open-packs answers, yet its
"division of responsibility" table still keeps built-in authored in core while
open-packs only carves *additive* slices from it.

That leaves the ownership of built-in content ambiguous and split: the place that
is meant to be the curation home (open-packs) is not the source, and the place that
is not meant to own content (core) is. We want a single, unambiguous source of truth
for doctrine **content**, without changing anything a consumer experiences (built-in
must still arrive, transparently, with a normal `pip install`).

The mechanics of doctrine — the resolver, DRG merge, charter activation, and the
validator — are deliberately **out of scope**: they stay in core (per the open-packs
vision and the doctrine-layer-merge-semantics ADR). This decision is only about where
the built-in **content** is authored and how it reaches the shipped artifact.

## Decision Drivers

* One unambiguous source of truth for doctrine content — the curation home, not core.
* Consumer experience unchanged: built-in still ships in the core wheel, transparently.
* Reuse the already-built resolution seam (`resolve_pack_root("built-in")` is a
  filesystem ancestor-walk); do not force a runtime resolver rewrite.
* Keep doctrine *mechanics* in core; move only *content*.
* Honour the graduated-trust direction (checksum-verifiable packs) rather than an
  opaque copy.

## Considered Options

* **A — Status quo:** built-in authored in core; open-packs adds only additive org slices.
* **B — Invert with CI re-vendor (chosen):** built-in content authored in open-packs;
  a release-time CI step vendors it into `packs/built-in/` before `hatch build`, so the
  wheel still force-includes it. Resolution is unchanged because it is filesystem-based.
* **C — Published data dependency:** built-in ships as a separate PyPI data package
  (e.g. `spec-kitty-doctrine`) that core depends on and resolves at runtime from the
  installed dependency.

## Decision Outcome

**Chosen option: "B — Invert with CI re-vendor",** because it makes open-packs the
single source of truth for content while leaving the consumer install, the runtime
resolver, and the core mechanics untouched. Built-in remains present on disk at build
time (satisfying the parity and corpus gates) and in the wheel (satisfying consumers),
but its **canonical origin** becomes the open-packs catalog. Option C is the eventual
"north star" but requires the dormant nested-doctrine-wheel groundwork
(`src/doctrine/hatch_build.py`, guarded dormant by `test_doctrine_wheel_closure.py`) to
become a real published package plus a resolver that finds packs inside an installed
dependency — a larger lift deferred until the manifest/checksum work (#2467/#2539) lands.
Option A is rejected because it permanently contradicts the open-packs vision and leaves
content ownership split.

### Consequences

#### Positive

* Single curation home; contributors and SK Inc. maintain built-in where the catalog,
  docsite, and validator already live.
* Consumers see no change — same `pip install`, same force-included `packs/built-in/`.
* The runtime resolver, DRG merge, and charter activation are untouched.

#### Negative

* Core's release now has a **build-time dependency** on open-packs (a checkout/copy step
  before `hatch build`); a broken or unpinned open-packs breaks the core release.
* Release reproducibility now depends on a **pinned open-packs ref** (tag or SHA), which
  must be recorded and verified (ideally by checksum) at build time.
* Parity/corpus gates (`test_packaging_parity.py`, the `packs`-triggered CI jobs) assume
  `packs/built-in/` is present in-tree; the vendor step must complete before they run,
  and contributor checkouts need a documented way to materialize built-in locally.
* Runs against the direction of the shared-package-boundary ADR (which retired vendored
  *code* in favour of a published dependency). Packs are **data, not code**, so that ADR
  does not bind — but the tension is real and Option C remains the longer-term resolution.

#### Neutral

* `packs/built-in/` continues to exist in the core tree; only its provenance changes.

### Confirmation

Success = (1) built-in content has exactly one authoritative copy (open-packs), pinned by
ref/checksum in the core release; (2) a released wheel's `packs/built-in/` is byte-identical
to the pinned open-packs content; (3) `test_packaging_parity.py` and the corpus jobs stay
green against the vendored tree; (4) consumers observe no behavioural change. **Not yet
built** — this ADR ratifies direction; the implementation is a separate epic gated on
open-packs CI scaffolding (none exists today) and the manifest/checksum dependencies above.

## Pros and Cons of the Options

### A — Status quo (built-in in core)

**Pros:** No build-time coupling; simplest release; reproducible from one repo.
**Cons:** Content ownership stays split; contradicts the open-packs vision; two curation
surfaces for the same corpus.

### B — Invert with CI re-vendor

**Pros:** Single source of truth; unchanged consumer + runtime; reuses the filesystem seam.
**Cons:** Build-time dependency on open-packs; release must pin + verify a ref; local
checkouts need a materialize step.

### C — Published data dependency

**Pros:** Cleanest boundary; aligns with the shared-package-boundary philosophy; no vendoring.
**Cons:** Largest lift — needs the dormant doctrine wheel productionized and a resolver that
reads packs from an installed dependency; blocked on manifest/checksum work.

## More Information

* Open-packs vision: `spec-kitty-open-packs/docs/architecture/vision.md` (division-of-responsibility
  table is amended by this ADR: built-in *content* now originates in open-packs).
* Blockers: `spec-kitty-open-packs/docs/research/blockers-and-core-dependencies.md` (#2466/#2467/#2471/#2539).
* Companion decision: `2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md`.
