---
title: 'Consumer-repo layout portability: disposition and sequencing'
description: 'Planner disposition for the consumer-repo layout blind spot (#3016/#2330): a bounded 3.2.x correctness down-payment now, broad portability deferred to mission-types-as-doctrine.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/3-2-x-milestone-roadmap.md
- docs/plans/3-2-x-open-core-delivery-plan.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/index.md
---

# Consumer-repo layout portability: disposition and sequencing

> **Status update (2026-09-30).** The bounded down-payment shipped: #3016 (accept hard-codes `src/`) closed on 2026-08-29 via PR #3790. The broader portability work, #2330, is open on the *CLI 4.x stable* milestone. The "3.3.x line" named below was retired on 2026-08-23. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

**Scope:** a draft investigation on the distil-then-retire working surface —
**not** a canonical ADR. It records a planner disposition (roadmap-line vs de-scope
vs fold vs minimal-fix) and sequencing for the consumer-repo layout blind spot. The
override-*mechanism* choice (config key vs resolver deep-merge) is a real
architectural call and is deferred to architect review; when settled it belongs in
an ADR under `docs/adr/3.x/`. This document retires once the down-payment lands and
the deferred tail has a named home. Evidence base:
`work/bug-triage-research/blindspot-consumer-layout.md` and
`categorization-findings.md` §4.

## Problem

`accept` and the path-convention gates assume a Python `src/` + `tests/` layout, so
first-party non-Python consumer repos fail the gate: **#3016** (P1, Django `apps/`)
and **#2330** (P1, Go `internal/`+`cmd/`). Supporting arbitrary consumer-repo
layouts reads as *new capability*, not stabilization.

**Corrected framing (milestone vs epic).** Both #3016 and #2330 **already carry
milestone `3.2.x`** — "no 3.2.x line owns it" is about **epic/goal-line ownership**,
not the tag. Sibling **#2329** (same defect) is **closed as duplicate**; **#1892**
(the `--lenient` ask) is **closed and shipped** — an escape hatch already exists. So
the decision is the fate of a capability that is *milestone-tagged but
epic-orphaned, with one escape-hatch increment already delivered* — again an
**ownership** question, not a scheduling one.

## Evidence

**The primary seam is shallow and already data-driven** — the load-bearing fact.

| Layer | File:line | Role |
|---|---|---|
| DATA (root) | `missions/software-dev/mission.yaml:152-153` (`workspace:"src/"`, `tests:"tests/"`; `:110` deliverable `src/`) | the *only* place the shape is asserted for the gate |
| Model | `mission.py:166-176,183` (`valid_path_keys`) | keys hardcoded, **values free** |
| Validator (**language-neutral**) | `validators/paths.py:133-215` `validate_mission_paths` | data-driven; reads `mission.config.paths`; **no language literal**; `mkdir -p` remedy at `:81-105` |
| Gate | `acceptance/summary_core.py:110-148` `evaluate_path_conventions` (wired `acceptance/__init__.py:1013`) | `strict_metadata=True` → hard block; `--lenient` → advisory (the #1892 hatch, `:120-128`) |

**The missing override is the actual gap.** `mission.yaml` is overlayable, but
resolution is **whole-file precedence, not deep-merge**
(`src/doctrine/resolver.py:303-361`). To change only `paths:` a project must copy the
**entire** `mission.yaml` into `.kittify/overrides/` — brittle and drifts on
`upgrade`. There is no granular `paths` / `path_conventions` knob in
`.kittify/config.yaml`. **That missing capability is the root ask** — a
*shallow-seam-plus-missing-override*, not a language assumption buried in the
validator.

**The correctness wart (independent of portability).** The `mkdir -p src/` remedy
still prints for a layout where `src/` is inapplicable, converting an inapplicable
gate check into a **falsely-passing** one — it makes a gate *lie*. That violates the
charter's *trace-don't-work-around* guidance on its own merits, regardless of the
roadmap verdict.

**The blast tail.** Beyond the one hard-blocking surface sit **~7** *secondary,
mostly-non-blocking* hardcodes (the count is **approximate and illustrative** — the
list below is representative, not an exhaustively re-counted census): `ownership/validation.py:77`
(`_CODE_PREFIXES=("src/","tests/")`), `policy/risk_scorer.py:190`,
`lanes/compute.py:76,88`, `review/_dead_code.py:104,133,135`,
`review/scope_source.py:266`, `post_merge/stale_assertions.py:262,747`,
`missions/documentation/doc_generators.py:164` + `gap_analysis.py:723`. (Explicitly
**excluded**: `template/manager.py`, `skills/registry.py`, `compat/doctor.py`, `m_*`
migrations — those are spec-kitty locating its *own* tree, not consumer layout.)
Depth verdict: **1 hard-blocking surface (already softened by `--lenient`) + a long,
shallow, non-blocking tail.**

**Demand + open-core relevance.** Demand is **real but internal/dogfooding-only** —
two first-party repos (`spec-kitty-saas` Django, `spec-kitty-analyzer` Go); no
`customer-feedback` label, no external ticket. And this is **orthogonal** to the
open-core thesis: the open-core "consumer" is a *doctrine-pack consumer*
(`3-2-x-open-core-delivery-plan.md` §2.2/§3), whereas #3016/#2330's "consumer repo"
is the *project spec-kitty runs against*. The natural architectural neighbor is
**mission-types-as-doctrine (#2468/#2721)** — they make `mission.yaml`/`paths:`
overlayable doctrine — but **neither epic today commits to language-neutral path
conventions or a granular `paths` override**, and #2721 needs resolver **deep-merge**
that is not in its scope.

## Options considered

- **(a) New 3.3.x portability line.** — *Reject for now.* Honestly names the
  capability and keeps 3.2.x pure, but demand is internal-only, `--lenient` already
  softens urgency, and a standalone epic is net-new scope with no external pull.
  Revisit only if an external (non-dogfooding) ticket appears.
- **(b) Fold into mission-types-as-doctrine (#2468/#2721).** — *Accept, but deferred
  and only for the tail.* Architecturally the correct long-term home (`paths:` is
  already overlayable doctrine there), but those epics are scoped to
  ArtifactKind/step-model, and the real fix needs resolver deep-merge not in either
  epic today. Forcing deep-merge onto a load-bearing G1 epic *now* is scope-creep on
  a load-bearing epic. Fold **when they mature the granular overlay**, not before.
- **(c) De-scope as non-goal (Python-first).** — *Reject.* Hard to justify while
  Priivacy-ai dogfoods its own Go + Django repos, and — decisively — the `mkdir -p
  src/` wart is a **correctness** bug independent of portability. A Python-first
  product still must not prescribe an action that makes a gate lie.
- **(d) Minimal fix: config-driven layout for accept/gates.** — *Accept as the
  immediate down-payment.* Smallest diff; the validator is already data-driven, so it
  needs only a granular `paths` override + softening the misleading remedy. Kills the
  hard-block and the falsely-passing remedy. Its limitation — the ~7 (approximate,
  illustrative) secondary heuristics stay Python-shaped — is exactly what the deferred
  (b) tail covers.

## Decision

**Decouple correctness from portability; ship a bounded 3.2.x down-payment now, defer
broad portability to a matured mission-types-as-doctrine.** Concretely, two tracks:

- **Track 1 — correctness + hard-block down-payment (keep on 3.2.x): option (d).**
  (i) Soften the `mkdir -p src/` remedy so it does not print an inapplicable action
  when a convention is *absent* (vs *violated*) — a standalone correctness fix,
  **dependency-free as a diff**. Its user-visible payoff is **latent** until the
  granular `paths` override (ii) exists: absent an override, `src/`/`tests/` are
  always *declared* for every consumer (from the default `mission.yaml`), so the
  "absent" branch never fires — and for a plain Python repo a missing `src/` is a
  legitimate *violation* where `mkdir` is the correct remedy. The fix still lands
  alone, because it closes the trace-don't-work-around violation in the remedy
  generator regardless of when its payoff becomes observable.
  (ii) Add a **granular `paths` / `path_conventions` override** so a non-Python
  project can retarget layout without copying the whole `mission.yaml`. Together these
  remove the hard-block for Django/Go and stop the gate lying. Bounded to ~2–3
  surfaces (the validator is already neutral).
- **Track 2 — broad portability (defer, 3.3.x-shaped): option (b), not (a).** The
  ~7 secondary heuristics land later as a **language-neutral extension of
  mission-types-as-doctrine (#2468/#2721)**, once those epics adopt the granular
  overlay / deep-merge. **Not** a standalone 3.3.x epic (no external demand), **not**
  a fold *today* (the epics are not scoped for it yet).

**Architectural justification (for architect review).** The portability problem is
*already* factored the right way: the gate is data-driven and language-neutral
(`validators/paths.py:133-215`), so the fix is not "de-Python the validator" — it is
"make the data overridable granularly." That surfaces **one genuine architectural
choice: a `path_conventions` key in `.kittify/config.yaml` *versus* resolver
deep-merge (`resolver.py:303-361`).** The config-key is the bounded, 3.2.x-shaped
down-payment; **deep-merge is the more general change and is the one that naturally
belongs with mission-types-as-doctrine.** The disposition does **not** pick the
mechanism — that is the architect's call — but the choice has a roadmap consequence:
pick deep-merge and Track 1 partially pre-builds Track 2's home; pick the config-key
and Track 2 stays a clean separate fold. The `mkdir` remedy fix is orthogonal to both
and should not wait on the mechanism decision.

## Architect recommendation

> **Operator-accepted (2026-08-16).** The recommendation below is adopted as the
> decision; the ratifying ADR records it rather than re-opening it.

The override-mechanism choice this disposition deferred to architect review has been
made (architect-alphonso, 2026-08-15):

**Prefer resolver deep-merge over a `config.yaml` `path_conventions` key — but scope
the 3.2.x down-payment to a *bounded* merge of the `paths:` subtree only, not a
general deep-merge and not a config side-channel.**

Path conventions are mission-config data — they already live in
`mission.config.paths`, and the validator reads them there. The override therefore
belongs in the **same resolution layer**: one source of truth. A `config.yaml`
`path_conventions` key introduces a **second competing authority** plus a new
precedence question (config `apps/` vs `overrides/mission.yaml` `src/` — who wins?),
and it becomes throwaway once deep-merge lands (a double migration).

A **full, general** deep-merge on `resolve_mission` is a broad, load-bearing change
that needs its own ADR (list-vs-scalar-vs-null semantics) and belongs with #2721, not
a G1 epic now. The resolution: for 3.2.x, let the override tier supply a **partial
that deep-merges over the package default for the `paths:` key specifically** (e.g.
`.kittify/overrides/missions/<name>/paths.yaml`, or a `paths:`-only partial
`mission.yaml`). The merge semantics are trivial (flat `str→str`, shallow-merge) — no
general-deep-merge ADR required — yet forward-compatible: when #2721 generalises
deep-merge, `paths` is already the right shape.

**Trade-off:** the config key is the smallest diff and ships fastest, but leaves a
durable second source of truth, precedence ambiguity, and double-migration debt. The
bounded `paths:`-subtree merge is a slightly larger diff, keeps `mission.yaml` the
single authority, avoids upgrade drift, and matches the shape #2721 will later
generalise. **If forced to an either/or: choose deep-merge (bounded to `paths:`), not
the config key.**

## Recommended tracker actions

- **Keep #3016 and #2330 on 3.2.x** as the Track 1 down-payment (they are
  stabilization-shaped: unblock the gate + stop it lying, not net-new capability).
- **File the `mkdir -p src/` remedy fix as its own bounded item** (correctness;
  ship-alone, no mechanism dependency). Cross-link to #3016 (which explicitly flags
  the misleading remedy).
- **Do not mint a standalone 3.3.x portability epic (option a) now.** Instead add a
  **deferred fold-target note** on #2468/#2721: "language-neutral path conventions +
  granular `paths` overlay — the ~7 secondary heuristics land here when the overlay
  matures." Keep it as a **loose 3.3.x line/annotation**, not an active epic.
- **Close-check** #2329 (dup, already closed) and #1892 (`--lenient`, shipped) so
  they are not re-triaged.
- **Do not "fix" portability by widening `--lenient`** — #3016 already rejects it as
  blunt (it drops other strict checks).

## Sequencing

1. **Now, independent, smallest:** soften the `mkdir -p src/` remedy (absent-vs-
   violated). Ships alone with no dependency and closes the trace-don't-work-around
   violation in the remedy generator; its **user-visible payoff is realised once the
   granular `paths` override (step 2) lets a convention be *absent*** — absent an
   override, `src/`/`tests/` are always declared, so the "absent" branch never
   triggers.
2. **Track 1 core — granular `paths` override.** Depends only on the architect's
   mechanism ruling (config-key vs deep-merge). Unblocks #3016/#2330's hard-block on
   3.2.x. Add regression coverage for a non-`src/` layout (Django `apps/`, Go
   `internal/`) in the same change.
3. **Track 2 tail (deferred, 3.3.x).** The ~7 secondary heuristics, folded into a
   language-neutral extension of #2468/#2721 **after** those epics adopt the overlay.
   Independent of each other; sequence by consumer pain (dogfooding signal), not all
   at once.

Dependency note: step 1 has **no** dependency and should not be gated behind the
mechanism decision; steps 2 and 3 both wait on the mechanism ruling, and step 3
additionally waits on #2468/#2721 maturing.

## Open questions for the operator

- **Keep #3016/#2330 on 3.2.x, or bump to 3.3.x?** *Recommended default: keep on
  3.2.x* framed as the (d) correctness/hard-block down-payment; the **broad
  portability capability** (the tail) is what carries the 3.3.x framing, as a fold
  into #2468/#2721 — not these two tickets. Flagging rather than resolving: keep-vs-
  bump is an operator call because it reframes what "3.2.x done" means.
- **Any external (non-dogfooding) demand?** *Recommended default: treat as
  internal-only* until a `customer-feedback` ticket appears. If external demand
  surfaces, Track 2 escalates from a deferred fold to a real 3.3.x line (option a).
- **Override mechanism — answered.** The config `path_conventions` key vs resolver
  deep-merge question is the architect's decision, and it has been made: prefer
  resolver deep-merge **bounded to the `paths:` subtree** for 3.2.x — not a general
  deep-merge, not a `config.yaml` side-channel (see
  [Architect recommendation](#architect-recommendation)). Retained here only for its
  roadmap consequence: the bounded `paths:` merge already pre-builds the shape #2721
  will generalise, so Track 1 lands forward-compatible with Track 2's home rather
  than throwaway.
