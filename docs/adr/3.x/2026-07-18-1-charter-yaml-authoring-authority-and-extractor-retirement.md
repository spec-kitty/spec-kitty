---
title: 'ADR: charter.yaml is the authoritative structured source; charter.md is a curated companion; retire the prose→triad extractor'
description: '`charter.yaml` becomes the authoritative structured charter owning activation state, `charter.md` becomes a curated companion, and the prose-to-triad extractor retires.'
status: Proposed
date: '2026-07-18'
---

**Status:** Proposed

**Date:** 2026-07-18

**Deciders:** Operator (Stijn Dejongh); assessment by a 4-lens grounding squad + a thesis/antithesis dialectic + a neutral empirical investigation (2026-07-18).

**Technical Story:** epic [#2519](https://github.com/Priivacy-ai/spec-kitty/issues/2519); mission [#2773](https://github.com/Priivacy-ai/spec-kitty/issues/2773) (consolidate-charter-bundle); relates [#2772](https://github.com/Priivacy-ai/spec-kitty/issues/2772); aligns with [ADR 2026-07-15-1](2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md).

---

## Context and Problem Statement

Charter state is compiled from a hand-authored `charter.md` into four separate on-disk artifacts under `.kittify/charter/`: `governance.yaml`, `directives.yaml`, `metadata.yaml` (the "derived triad", produced by `sync.py::sync()`), and `references.yaml` (produced by `compiler.py`, and also the ID-parity authority). Mission #2773 consolidates these four into one compiled `charter.yaml`.

While specifying #2773 the operator reopened a deeper question under a **deterministic-first** philosophy: should `charter.yaml` become the **authoritative structured source** and `charter.md` a **curated companion** (rationale write-up), inverting the current "charter.md is the authored source" model?

The proposal was assessed and de-risked. The key findings:

- **Three surfaces are conflated by the phrase "what is active".** (A) the *activation ledger* — `config.yaml activated_*`; (B) the *compiled resolving bundle* — the four files → `charter.yaml`; (C) *human prose* — `charter.md`. #2773 consolidates B; the inversion targets C.
- **`answers.yaml` is provenance-only** (operator-binding): a creation-time record of *why/when/who*, with **zero** runtime/behavioural impact by design. Reading `answers.yaml selected_*` for behaviour is a bug. Therefore `config.yaml activated_*` is the **sole** activation authority; the #2519 "disjoint activation ledgers" concern is largely a mislabel.
- **`charter.md` is currently dual-owned** — hand-authored prose AND regenerated from an interview template by `compiler.py:421` (`charter_path.write_text(compiled.markdown)`), reachable via `charter generate --force`. That single writer is the #2772 clobber (a 1237-line curated-prose destruction was observed live).
- **The "AI/hybrid extractor" is a phantom.** `extractor.py:807 extract_with_ai` returns `{}` and has zero callers; the prose→triad extraction is 100% deterministic regex/keyword scraping. The `extraction_mode: "hybrid"` label is cosmetic.
- **Prose is display-only for governance.** A neutral trace of every `charter.md`-content reader found all governance/directive reads flow into **agent-facing display text** (`context.py:274 _extract_policy_summary`, `context.py:1023/2754/2784 render_critical_section_bodies`, `compact.py:138`), not decisions. Runtime governance/directive loaders (`sync.py:307/356`) read the **triad YAML**, not prose. The one behavioral prose read — doctrine language-scoping (`language_scope.py:101-103`) — is orthogonal: its authoritative source is `references.yaml` (structured, from the interview), with `charter.md` only a degraded tier-3 fallback; it is not produced by the scraper and not part of the triad.

**Consequence of the findings:** seeding `charter.yaml` from the existing triad is a **deterministic, lossless yaml→yaml fold** (the same migration #2773 already commits to). The inversion's cost is therefore *not* a data-migration hazard — it is (a) a governance/authoring-UX structural change and (b) a schema-shape decision that is expensive to reverse under the bundle-manifest schema contract (a version bump + migration).

## Decision Drivers

- **Deterministic-first** — the authoritative "what is active / what governance applies" state should be structured and deterministically read, not scraped from prose.
- **Single canonical authority** (charter governing principle) — one owning source per surface; eliminate the dual-owned `charter.md`.
- **Kill the split/drift/stopgap churn** — epic #2519's purpose. Shipping a `charter.yaml` schema we already know we will re-cut for the inversion would recreate exactly that churn.
- **Cut the schema once** — the bundle-manifest schema/migration is the only expensive-to-reverse artifact; deciding its end-state shape now avoids a second bump on the same brand-new file.
- **Eliminate the #2772 clobber** at its single write site.
- **Preserve** the #2732 content-identity machinery and the C-001 layer boundary (`src/charter/` must not import `specify_cli`).

## Considered Options

- **Option X — ADR now + reshape #2773 to be authoring-ready; stage the deletion.** (chosen)
- **Option Y — ADR-first, then shape #2773 from the outcome.**
- **Option Z — keep #2773 bounded (derived-from-prose), do the inversion later as a wholly separate mission.**
- **Option (b) — charter.md becomes fully generated from rationale fields embedded in charter.yaml.** (rejected)

## Decision Outcome

**Chosen option: X**, because the only expensive-to-reverse artifact is the `charter.yaml` schema, and the empirical trace removed the "lossy migration" blocker — so we commit the full end-state in one coherent mission, delivered on a single branch and PRed as a consistent whole (sequenced tidy-first within the mission rather than split across PRs).

The end-state this ADR pins:

1. **`charter.yaml` is the project charter** — the authoritative structured source for the project's active doctrine: governance knobs, directive declarations, the resolving/artifact-ID catalog, **the project activation state and overrides**. It is pack-shaped (same **flat** `activated_kinds` / `mission_type_activations` / `activated_*` root-key vocabulary as `src/charter/packs/default.yaml`). This mission relocates a **single flat activation surface** (`default.yaml` supplies the absent-key fallback/seed); the multi-tier org⊆team⊆repo charter *accumulation* is the target model but is **forward-intent** — the current `pack_roots` overlay applies to artifact definitions, not activation tiers — and is fenced OUT with the rest of the ADR 2026-07-15-1 restructure.
2. **`charter.yaml` OWNS activation.** The project activation state (`activated_*` / `activated_kinds` / `mission_type_activations`) **relocates out of `.kittify/config.yaml` into `charter.yaml`**; the activation engine (`commit_plan`, `merge_defaults`) and `PackContext.from_config` are re-pointed to write/read `charter.yaml`; `config.yaml` retains only non-doctrine config (agents, tooling). `answers.yaml` stays provenance-only. **Fenced OUT of this mission:** the broader ADR 2026-07-15-1 restructure (runtime activation-gating; first-class DRG nodes for `mission_type`/`gate`/`asset`) — this mission advances only the activation-surface/ownership axis. Local-only/personal doctrine is assumed to activate via the same pack-shaped mechanism (the local-override mechanism itself is a separately-tracked gap).
3. **`charter.md` is a hand-authored curated companion** — the human "why". It is **never a resolving input** and **never clobbered** by any generate/compile path.
4. **The prose→triad regex extractor (`extractor.py` `SECTION_MAPPING`, `sync()` backward scrape) is retired** — governance/directive structure is authored/held structurally, not scraped from prose.
5. **Delivery is one coherent mission on a single branch, PRed as a whole**, sequenced tidy-first: (i) build `charter.yaml` with first-class *authorable* fields + fold the clobber guard; (ii) seed it deterministically from the triad and re-point resolving/parity/freshness consumers; (iii) re-point the display prose-consumers and retire the prose→triad extractor + `sync()` backward scrape; (iv) `charter.md` becomes a pure hand-authored companion the derive path never writes. No intermediate PR ships a half-inverted state.

This aligns with ADR 2026-07-15-1 ("Doctrine offers, charter activates, runtime consumes") on the activation axis (activation stays in the charter/config layer, routed via the default charter) and adds the orthogonal **authoring-direction** decision that ADR did not cover.

### Consequences

#### Positive

- One canonical structured authoring source; the dual-owned `charter.md` smell and the #2772 clobber are eliminated.
- Deterministic-first resolving/governance with no brittle prose scraper.
- The `charter.yaml` schema is cut once (no second C-004 bump), honoring #2519's anti-churn goal.
- `charter.md` becomes freely curatable rationale that no tool overwrites.

#### Negative

- The mission widens materially — it now carries the full inversion (schema design + clobber guard + C-001 flip + extractor retirement + display-consumer re-pointing) **plus relocating the activation state and re-pointing the activation engine (`commit_plan`/`merge_defaults`/`PackContext.from_config`)** in one branch/PR. Expect a large WP count and review surface; the activation-engine change is the biggest new blast radius.
- `charter.yaml` is **git-tracked** (an authoring surface); its derived `catalog` section produces honest tracked diffs when activation changes — acceptable, and detected by the freshness signal.
- The governance authoring UX shifts from prose to structured fields — a real change delivered within the mission, needing docs + operator guidance in the same PR.

#### Neutral

- The doctrine language-scoping tier-3 `charter.md` fallback (`language_scope.py:103`) is orthogonal; it is **folded into this mission** as FR-009/IC-08 (migrated off `charter.md` prose to the structured catalog `languages`), so `charter.md` is behaviorally inert by mission end.
- `#2772` is folded (the guard) / superseded (the derive path stops writing `charter.md` once the extractor retires).

#### Amendment (2026-07-19, #2800 landing pass)

The original outcome — the *compiler* (`write_compiled_charter`) never writes `charter.md` — is preserved. But "generate never writes charter.md **at all**" left a fresh project with no companion and no signal that one should exist (and stranded the FR-009 golden-path affordance). Refined: the **`charter generate` command** now seeds a minimal starter `charter.md` **only when the file is absent** (`_seed_charter_md_companion_if_absent`). This is *create-if-absent* — an existing curated `charter.md` is left byte-for-byte untouched, so the never-clobber invariant (#2772 / IC-03, pinned by `test_generate_force_preserves_curated_charter_prose_2772`) is fully preserved, and the companion is discoverable. `charter.md` remains display-only and never a resolving input.

### Confirmation

- #2773 ships `charter.yaml` with authorable governance/directive/catalog fields; its migration is a deterministic idempotent yaml→yaml fold (second run reports 0 changes).
- No `charter generate`/compile path writes `charter.md` without an explicit guard; a regression test pins that curated prose survives a refresh.
- By mission end (same PR): `extractor.py` `SECTION_MAPPING` is deleted; governance/directive loaders read `charter.yaml`; a grep shows no runtime governance decision reads `charter.md` prose.
- Activation is relocated: `.kittify/config.yaml` no longer carries `activated_*`; `commit_plan`/`merge_defaults`/`PackContext.from_config` read/write `charter.yaml`; `charter.yaml` overlays `default.yaml` (layer-0); the activation-parity/DRG-filter behavior is preserved (existing activation tests green).
- Confidence: **high** on the losslessness/determinism facts (traced to `src/` lines); **medium** on authoring-UX ergonomics, which the fast-follow will validate with real operator authoring.

## Pros and Cons of the Options

### Option X — ADR + reshape #2773 to carry the full inversion in one branch/PR

**Pros:** cuts the schema once; delivers the operator's direction as a consistent, reviewable whole (no half-inverted intermediate state ships); de-risked by the empirical trace; eliminates the clobber at its single site; fully folds #2772.
**Cons:** materially widens the mission (more WPs, larger PR); commits to the inversion direction within a single review surface.

### Option Y — ADR-first, then shape #2773

**Pros:** fullest end-state pinned before any schema is cut; safest for a structural-boundary change.
**Cons:** stalls a ready P2 consolidation; the empirical trace already de-risked the decision, so the extra gate buys little.

### Option Z — keep #2773 bounded; invert separately

**Pros:** minimal #2773 now.
**Cons:** near-certain second schema re-cut + migration on the same brand-new file — the exact split/drift/stopgap churn #2519 exists to end. Rejected as self-defeating for the epic.

### Option (b) — charter.md fully generated from charter.yaml rationale fields

**Pros:** single-source/deterministic on paper.
**Cons:** curated rationale (~30 KB, ~7× the structured extract) is not derivable from structured data; authoring rich prose inside YAML block scalars is diff-hostile and fragile; makes the #2772 clobber the *normal* path. Rejected — the viable model is a hand-authored companion, not a generated one.

## More Information

- Assessment + dialectic + empirical resolution: `kitty-specs/consolidate-charter-bundle-01KXSYB9/research/charter-authority-inversion-assessment.md`.
- Mission spec: `kitty-specs/consolidate-charter-bundle-01KXSYB9/spec.md`.
- Related: ADR 2026-07-15-1 (activation axis); #2772 (charter.md non-destructive refresh); epic #2519.

## Amendment 2026-10-19: Decision 2 is superseded for activation keys

[ADR 2026-10-19-1](../4.x/2026-10-19-1-activation-ledger-persists-deactivation.md) supersedes **Decision 2 only** ("`charter.yaml` OWNS activation"). The activation keys (`activated_kinds`, `mission_type_activations`, `activated_<plural>`) and the new `deactivated_<plural>` deny-lists now live in `.kittify/charter/activation.yaml`, not in `charter.yaml` or `.kittify/config.yaml`. A migration moves existing keys. The rest of this ADR stands: `charter.yaml` stays the authoritative structured charter for everything else, `charter.md` stays a curated companion, and the prose-to-triad extractor stays retired. `answers.yaml` is still provenance only.
