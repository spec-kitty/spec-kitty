---
title: Naming / Identity SSOT Strangler — Capstone Overview (3.2.1)
description: "Capstone overview (3.2.1) of the naming/identity SSOT strangler: Architect Alphonso's aggregation of the research squad's findings, read-only at 3.2.0."
doc_status: deprecated
updated: '2026-06-16'
---
# Naming / Identity SSOT Strangler — Capstone Overview (3.2.1)

> **Retired (deprecated).** Design shipped/superseded via the open-core delivery plan §1.2 "G2 — strangle the core domains onto SSOTs" (identity primitive moved to the lower layer; naming/identity derive once) — see `docs/archive/plans/3-2-x-open-core-delivery-plan.md`. Preserved as a historical record.

**Author:** Architect Alphonso (squad aggregation — capstone deliverable)
**Branch:** `research/naming-identity-ssot-strangler` @ spec-kitty 3.2.0 (read-only; no commit/switch)
**Date:** 2026-06-16
**Squad inputs (this directory):** `randy-reducer-split-brain-map.md`,
`paula-patterns-duplication-shapes.md`, `python-pedro-implementation-feasibility.md`,
`architect-alphonso-intended-design.md`, `planner-priti-tracker-landscape.md`.

> **Governance (architect-alphonso).** Directives applied: **DIR-001** (Architectural
> Integrity — one owning module per concern; duplicates are seams to strangle, not features
> to keep), **DIR-003** (Decision Documentation — every reconciliation verdict below carries
> authority/contract/rationale + evidence link), **DIR-031** (Context-Aware Design —
> bounded-context boundaries are preserved through explicit translation layers, never
> collapsed), **DIR-032** (Conceptual Alignment — terms confirmed against CLAUDE.md canon:
> Mission Identity Model, C-LANES-1, the #1619 consolidated domain model). Tactics:
> *translation-layer-over-fork*, *strangler-completion*, *test-scaffolding-as-design-smell*.

---

## 1. Executive summary (the one-screen takeaway)

**The "confusing naming" / split-brain surface is mostly already fixed by 3.2.0 (PR #2001)
and prior work. The live 3.2.1 slice is small — ~3–4 work packages of mechanical routing,
one pure-seam extraction, and one shim retirement. The single deep remaining item — the
coordination-vs-primary *write/entry* strangler (#1878) — is a separate, larger mission and
must NOT be pulled into this slice.**

The whole squad converged on one headline, grep-verified against the actual code on this
branch (not trusted from issue prose):

> **3 of the 7 seed issues are already shipped** — **#1888** (ownership existence-check,
> landed as #1886), **#1915** (dep-merge atomicity, snapshot+`reset --hard`), and **#1971**
> (project-root behavior split-brain, `project_resolver` now *delegates* to
> `core/paths.py`). Planner Priti has already **closed #1899/#1915/#1918/#1949/#1978/#1917/#1916**
> against PR #2001 with evidence. The correct disposition for the shipped class is
> **verify-and-close (+ carry the missing regression test)**, *not* re-implement.

**Why re-implementing would be the anti-pattern.** Re-deriving a fix that already ships
creates a *parallel implementation of an existing authority* — a brand-new shadow path —
which is the precise failure class this mission exists to eliminate. Carrying issue prose
verbatim into a spec sizes the mission for 7 problems when it is really ~2 substantive
(#2000+#1899-tail, #1993) + 1 cleanup (#1971-tail) + verification. Sizing for 7 would also
*re-open* a fix and risk regressing it. The mission's value is therefore (a) finishing the
identity seam's migration tail, (b) extracting one more pure resolver, (c) retiring thin
shims, and (d) **tightening the ratchet so the closed classes can never regrow** — all as one
coherent step of #1868 (canonical seams) + #1619 (runtime/state SSOT), with **no new shadow
paths**.

---

## 2. The issue surface (status · concern · disposition)

Reconciled against Priti's tracker actions (§3 of her note) and the squad-discovered extras.
**Concern** keys to the five SSOTs in §3. Status is **grep-verified on this branch**, not
issue-prose-trusted.

| Issue / item | Status | Concern (SSOT) | Disposition |
|---|---|---|---|
| **#1888** finalize-tasks existence-check | **shipped** (as #1886; `validate_glob_matches`, `validation.py:319`, wired `mission.py:3348`) | E — Ownership | **verify + carry test → close.** Confirm it is a stale duplicate of #1886; file the exact-typo regression test if absent. |
| **#1915** dep-lane merge atomicity | **shipped** (`worktree_allocator.py:289–345` snapshot+`reset --hard`; ≥2-dep tests exist) — **CLOSED by Priti** | (atomicity — adjacent to D) | **closed.** Carry only the ≥2-dep regression test into the dep-merge suite. NOT a naming concern. |
| **#1971** project-root 3-way split-brain | **residual** (behavior closed: `project_resolver`→`paths` delegation, `1a21d6157`/`8431dd931`) | B — Project-root | **mission-WP.** Collapse the `__init__`→`project_resolver`→`paths` double-hop; redirect 4 callers; delete the re-export shim (keep deferred import). |
| **#1993** extract `resolve_lanes_dir()` seam | **open** (inline at `implement.py:974–982`) | C — Lanes-dir | **mission-WP.** Pure topology-aware extraction; kills the 12-mock test. High test-ROI. |
| **#1899** worktree dir-name grammar + 4th ratchet | **~85% shipped** (`worktree_dir_name`/`worktree_path`/ratchet exist) — **CLOSED by Priti**, residual → #2000 | A — Identity | **mission-WP (tail).** 3 allow-listed sites + the `surface_resolver` R2 classifier dedupe rider. |
| **#2000** route 3 `<slug>-<mid8>` composes | **open** (allow-listed `test_no_worktree_name_guess.py:113–115`) | A — Identity | **mission-WP (primary live work).** Mechanical, byte-identical; shrink the allow-list. |
| **#1878** coord/primary strangler (umbrella) | **open / partial** (READ side largely consolidated; WRITE side scattered) | D — Coord/primary | **separate mission (follow-on).** Only items #3 (allocator naming) + #5 (lint expansion) touch this seam; the rest is a distinct bounded context. |
| **#1918 / #1949 / #1978 / #1917 / #1916** | **shipped — CLOSED by Priti** vs PR #2001 | A / D (identity + ref) | **closed.** Evidence comments posted; no action. |
| *extra:* **bare `mission_id[:8]` mid8 derivation** (randy 2c) — ~10 sites (`implement.py:386`, `agent/workflow.py:292`, `agent/mission.py:772`, `git/sparse_checkout.py:286`, …) | **open, ratchet-blind** | A — Identity | **mission-WP rider + new guard.** Route through `mid8()`; **extend the ratchet idiom to flag bare `<…>_id[:8]` mid8 derivation** (closes the completeness gap). |
| *extra:* **`Path(__file__)…parents[N]` re-derivation** (paula Shape D) — `dashboard/server.py:95`, `doctor.py:1842`, `bulk_edit/occurrence_map.py:55`, `sync/owner.py:314`, … | **open** | B — Project-root | **mission-WP rider + new ratchet** — *but distinguish project-root vs installed-package-root intent first* (paula's premature-merge caveat). |
| *extra:* **`surface_resolver` R2 inline `.worktrees`-segment test** (alphonso Q1 / paula Shape F) — `surface_resolver.py:480` vs `is_under_worktrees_segment` `:199` | **open** | D — Coord/primary | **rider on #1899-tail WP.** Replace hand-roll with the classifier call. |
| *extra:* **`mission_dir_name` strip vs `coord_*` verbatim** twins (paula Shape B) | **by-design (do NOT merge)** | A — Identity | **new directional-usage guard.** Lint that the wrong twin is used in coord vs create paths. |
| #1900 C-002 allow-list drain | open | A — Identity | follow-up; pairs with #2000, fold in only if WP1 lands trivially. |
| #1827 / #1357 / #1716 / #1887 | open | D — Coord/primary | out-of-scope (merge/concurrency/topology mechanics) → #1878 sequencing. |
| #1766 / #1979 | open | E — Ownership | separate ownership-policy follow-ups; distinct from #1888. |
| #1890 / #1832 | open | C/D | UX/doc + a likely-fixed read-path symptom (re-test #1832 after #1993). |

---

## 3. The intended design — five canonical SSOTs (target architecture)

Each concern is one bounded sub-context of the **Shared Kernel** (#1619 model §2:
"path · identity · status resolvers"). The Shared Kernel is a *code module that builds
Contexts* — these resolvers are **OHS (Open-Host-Service) facades**, not domain logic.

The **branch_naming seam (3.2.0, PR #2001) is the repeating template** every concern
generalizes to:

> **compose+parse SSOT · emit-don't-guess · canonical-first / legacy-failover-warned ·
> declared-identity-keyed ("name proposes, authority disposes") · fail-closed on ambiguity ·
> ratchet-enforced (AST literal-ban with a *shrinking* allow-list as completeness oracle).**

Evidence: `lanes/branch_naming.py` — `mission_branch_name_required` (fail-closed, `:301`),
`resolve_mid8` (`:169`), `resolve_branch_name` (canonical-first + one-shot legacy warn, `:675`),
`worktree_dir_name`/`worktree_path` (emit-don't-guess, `:484`/`:516`),
`parse_mission_slug_from_branch` (dual-era parser, `:771`); enforced by
`tests/architectural/test_no_worktree_name_guess.py`.

| # | SSOT (single authority) | Public contract (seam) | Bounded context | State |
|---|---|---|---|---|
| **A — Identity / naming** | `lanes/branch_naming.py` | `mission_branch_name_required`, `mission_dir_name`, `worktree_dir_name`/`worktree_path`, `coord_*`, `resolve_mid8`, `parse_mission_slug_from_branch` (compose **and** parse together) | *Identity* — "who is this mission?" Names propose; declared `mission_id` from `meta.json` disposes. | **established** — 3 inline composes + ~10 bare-`[:8]` sites un-routed |
| **B — Project-root** | `core/paths.py::locate_project_root` | `locate_project_root(start=None)`; 3-tier order: `SPECIFY_REPO_ROOT` (Tier 1, #1965) → worktree `.git`-pointer → `.kittify` walk | *Infra/path* — "where is the project root?" One answer, identical from worktree or primary. | **behavior landed** (#1971) — surface/import duplication + `parents[N]` tail remain |
| **C — Lanes-dir / workspace** | `missions/_read_path_resolver.py::resolve_lanes_dir` (the #1993 ask), modeled on `resolve_status_surface_with_anchor` | one pure `resolve_lanes_dir(repo_root, mission_slug)`, **zero-mock** `tmp_path`-testable; coord-preferred, primary-fallback | *Path/topology*, lanes family — the THIRD artifact surface (C-LANES-1) | **gap** — inline in `implement.py:974` |
| **D — Coord-vs-primary read surface** | `missions/_read_path_resolver.py::resolve_mission_read_path` (the C-005 read primitive); status via `coordination/surface_resolver.resolve_status_surface_with_anchor` | `resolve_mission_read_path(repo_root, slug, mid8, *, require_exists)`; `primary_feature_dir_for_mission` (topology-BLIND, meta.json); ambiguous → `MissionSelectorAmbiguous`; stale-primary-under-coord → `StatusReadPathNotFound` | *Coordination topology* — the explicit **translation layer** (DIR-031) between operator-CWD/slug and the authoritative surface per artifact family | **read side consolidated; write/entry side scattered** (#1878) |
| **E — Ownership / path validation** | `ownership/validation.py` — `validate_no_overlap` + `validate_glob_matches` | literal zero-match → hard error + nearest-match; glob zero-match → soft warn; `create_intent` suppresses planned-new | *Mission-management planning* invariant (consumes `repo_root`, adjacent to the Kernel) | **landed** (#1886) — verify #1888 dup + carry test |

**Hard guardrails (boundaries that must NOT collapse — DIR-031):**

- **Identity ≠ Path.** `branch_naming` (identity) and `_read_path_resolver` (path) are distinct
  authorities. Names propose; declared identity disposes. Never let a path heuristic mint identity.
- **meta/primary ≠ status/coord ≠ lanes/coord (C-LANES-1 / DIR-031).** Three artifact families,
  three surfaces. Collapsing them into one resolver "for simplicity" re-creates the
  planning→implement *genesis* bug (`implement.py:1009–1018`: a slug-derived empty mid8 read
  landed on a different surface than the meta-anchored write and saw "WP not finalized").
- **Strip-vs-verbatim twins must stay two functions (Shape B).** `mission_dir_name` (strips
  `NNN-`, for *create*) vs `coord_*` verbatim (for *reconstruct-existing*) is a genuine semantic
  fork, not duplication. Merging behind a `strip: bool` flag re-creates the #1589 orphaned-coord
  class. Guard the *choice*, don't erase it.
- **Coord/primary topology stays a translation layer, never a fork** (#1878 non-goal: no topology
  redesign, no safe-commit semantics change).

---

## 4. Impact of the discrepancies (the cost of NOT consolidating)

Each split-brain has a concrete, *historically realized* failure mode — these are not
hypotheticals:

| Discrepancy | Real failure it caused / risks | Blast radius |
|---|---|---|
| **Coord/primary read scatter (D, #1878)** | The 3.2.0 mission itself bled here — #1718 (stale-primary-under-coord `StatusReadPathNotFound`), #1772, #1991 (`require_lanes_json` read the wrong surface). High-traffic commands (`implement`/`finalize`/`accept`) hand-juggle 3 surfaces in ~30 lines of fallback ladders, *duplicated per command* (`implement.py:957–985`). | **Highest.** Load-bearing topology; every mission lifecycle transition. |
| **NNN-strip drift (Shape B, #1589/#1821)** | A legacy `NNN-`-prefixed slug composed by the *stripping* composer drifts to a name **never created on disk** → orphaned coord worktree, broken status reads. | Status reads + coord worktree resolution for any legacy mission. |
| **mid8 double-append (#1949/#1860 class)** | `mission_branch_name` appended `-{mid8}` to a slug that already embedded it → `<slug>-<mid8>-<mid8>` → path never resolves. (Shipped fix: `_idempotent_legacy_body`.) | Branch/worktree resolution; was a **P1 merge-blocker** in the #1978 sibling. |
| **mid8 NNN-/preflight strip (#1978)** | Merge preflight dropped `-{mid8}` → preflight looked for a branch that doesn't exist (**P1 merge-blocker**). | Merge gate for every mid8-embedded mission. |
| **Bare `mission_id[:8]` (randy 2c)** | ~10 sites slice mid8 by hand; the ratchet's idiom-3 keys on `endswith(f"-{mid8}")` and **does not catch a bare `[:8]`** → the class silently escapes enforcement and can regrow even after #2000 lands. | Enforcement completeness — the gap that lets the closed class return. |
| **Teardown / compose name-guess (#2000/#1899)** | 3 allow-listed inline composes are 3 more places the grammar can drift (the #1860/#1949/#1978 class re-entry points). | Every mission-dir and mission-worktree creation. |
| **Project-root `parents[N]` (Shape D)** | Hard-codes a module's on-disk depth; a module move silently mis-locates root, and none honour `SPECIFY_REPO_ROOT`/worktree topology — the same authority split #1971 named, different idiom. | Dashboard, doctor, bulk-edit, sync — anything resolving root by depth. |
| **Ownership phantom path (#1888)** | A typo'd literal `owned_files` validated against a *phantom* path → silently weakened the parallel-WP collision guard (a name that passes a grammar check but names nothing real). | Parallel-lane ownership safety. (Now fixed; guard must not regress.) |
| **Non-atomic dep-merge (#1915)** | An earlier clean dep-merge commit survived a later dep's conflict despite a contract promising "never half-merged." | Cross-lane dependency propagation. (Now fixed; carry the test.) |

**The tangible cost of not consolidating:** the same defect *class* recurs at each un-routed
site, and each new fix that doesn't route through the seam adds another site to police. The
3.2.0 mission spent most of its remediation budget on the coord/primary surface (D) precisely
because it was three authorities, not one — consolidation is what stops the whack-a-mole.

---

## 5. Reconciling the squad's divergences (architect's binding verdicts)

Per DIR-003, I document each divergence and the resolved position:

**(a) Coord/primary — "still 3 scattered authorities" (Randy) vs "read side largely
consolidated" (my design note).**
*Both are correct about different sides of the surface.* Randy is right that the **READ side
still presents three resolver *entry points*** — `resolve_mission_read_path` (read primitive),
`resolve_status_surface` (status surface), and `resolve_feature_dir_for_mission →
resolve_action_context` (action-context) — and the high-traffic commands hand-juggle all three
*inline*. My design note is right that the **underlying read authority is consolidated** (C-004/
C-005 strangler: `feature_dir_resolver` is a thin re-export of the one read primitive).
**Resolved position:** the *authority* is single, but the *projection/entry* is scattered — three
families derive their surface ad-hoc at the callsite instead of consuming **one resolved
`MissionSurfaces` context object** projected from `resolve_action_context`. So the live disease
is on the **entry/projection side (and the entire WRITE side)**, not the read authority. That
makes the action-context-as-single-topology-authority the correct target, with the read primitive
and status surface as *projections* of it. **This is #1878 (separate mission) — not the 3.2.1
slice.** #1993 (extract `resolve_lanes_dir`) is the *first, bounded* step of this convergence
that is safely in-scope now.

**(b) #1915 disposition — Priti CLOSED it; Randy called it "a separate atomicity concern."**
*Not a conflict — they agree on substance.* Both say #1915 is **not a naming/identity split-brain**;
it is a git-transaction atomicity bug. Pedro and Paula confirm it is **already shipped** (snapshot+
`reset --hard`, with ≥2-dep tests). **Resolved position:** #1915 is **closed** (Priti's verdict
stands); the only residual is ensuring the ≥2-dep regression test lives in the dep-merge suite. It
**does not get a WP in this naming mission** and must not be folded in.

**(c) #1899 vs #2000 — "closed" (Priti) vs "residual" (Randy/Pedro).**
*Both correct, correctly split.* Priti **closed #1899** because the *seam + ratchet infrastructure*
shipped in #2001 (`worktree_dir_name`/`worktree_path` + the 4th ratchet). Randy/Pedro flag the
**migration tail** — the 3 allow-listed sites + the `surface_resolver` R2 dedupe — which Priti
explicitly **re-homed under #2000** (not orphaned). **Resolved position:** #1899 = closed (infra);
issue #2000 = the live residual WP carrying the tail. No double-counting.

**(d) #1888 disposition — "shipped/dup" (Pedro/Paula) vs "tagged 3.2.1 mission" (Priti).**
**Resolved position:** the *code* is shipped (as #1886). Priti tagged #1888 into 3.2.1 to carry the
**verification + missing regression test**, not a re-implementation. The WP is "confirm dup of #1886,
add the exact-typo regression test, close" — a **verify-and-close**, not a build. Honour that framing;
do not re-derive `validate_glob_matches`.

---

## 6. Recommended 3.2.1 mission shape

**Theme:** *Naming/Identity & Read-Path SSOT — strangler completion.* One cohesive mission,
advancing **#1868** (canonical seams) + **#1619** (runtime/state SSOT), completing **#1878**
items #3/#5 only.

**Sequencing principle (DIR-001 + strangler):** foundation seams → routing → enforcement; never
widen a divergence without a ratchet that **shrinks** the allow-list. Tighten each existing oracle
*before* adding code, so no consolidation introduces a parallel path a later step must re-strangle.

### WP decomposition (dependency order)

```
WP01  Verify-and-close the shipped class                         [foundation / hygiene]
      - #1888: confirm dup of #1886; add the exact-typo regression test for
        validate_glob_matches; close.
      - #1915: confirm ≥2-dep test home; close.
      - Establishes scope-truth so no later WP re-implements a working authority.
      - deps: none.

WP02  #1993 — extract resolve_lanes_dir() pure seam              [foundation seam]
      - Into missions/_read_path_resolver.py (the blessed KITTY_SPECS constructor module).
      - PRESERVE the two-variable dance (lanes-dir stays COORD-aware while feature_dir
        falls back to PRIMARY for meta) — return a small dataclass, not one path.
      - Zero-mock tmp_path test, written RED first; kills the 12-mock scaffold.
      - deps: none.

WP03  #1971 — collapse project-root hops + migrate parents[N]    [SSOT consolidation]
      - Repoint the 4 project_resolver callers + __init__ wrapper at core/paths;
        KEEP the deferred import (cycle-safe); delete the re-export shim.
      - Migrate the parents[N] tail — BUT first distinguish project-root vs
        installed-package-root intent (some dashboard/asset sites want package root).
      - SPECIFY_REPO_ROOT regression test on lint/helpers.
      - NOTE: __init__.py change → pyproject version bump + CHANGELOG entry (CLAUDE.md rule).
      - deps: none.

WP04  #2000 + #1899-tail + 2c — route composes & mid8; shrink+extend ratchet  [routing + enforcement]
      - Route mission_creation.py:321 + worktree.py:367/370 through mission_dir_name()
        (canonical/stripping twin — NOT the coord verbatim twin).
      - Route the ~10 bare mission_id[:8] sites through mid8().
      - surface_resolver R2: replace inline ".worktrees"-segment test with
        is_under_worktrees_segment().
      - REMOVE the 3 allow-list entries; EXTEND the ratchet idiom to flag bare
        <...>_id[:8] mid8 derivation; ADD the parents[N] sibling ratchet; ADD the
        directional strip-twin usage assertion.
      - Byte-identical golden-parity tests (legacy 057-foo AND embedded foo-<mid8>).
      - deps: none on others; SEQUENCE LAST — enforcement capstone reads cleanest
        after routing lands.
```

**Dependency DAG:** WP01 / WP02 / WP03 are independent foundations; WP04 is independent but
sequenced last (enforcement capstone). All four parallelize into ≥3 lanes.

### What stays OUT (explicit non-goals)

- **#1878 write-side strangler** — `is_committed` primary-HEAD check, setup-plan auto-commit
  fallback, lifecycle emission to protected main, the implement C-004 fallback, single
  ref-advance helper rollout, `_ensure_branch_checked_out` retirement. **Separate follow-on
  mission** (coordination/merge-durability bounded context). Only its *naming-resolver* slice
  (items #3/#5) touches this seam.
- **#1915 / #1918 / #1949 / #1978 / #1917 / #1916** — already closed; no WP.
- **#1827, #1357, #1716, #1887** — merge/concurrency/topology mechanics → #1878.
- **#1766, #1979** — ownership-*policy* follow-ups, distinct from #1888's existence-check.
- **Merging the strip-vs-verbatim twins** — by-design boundary; guard, don't erase.

### Byte-identical / no-shadow-path traps to honour (Pedro's two load-bearing traps + riders)

1. **#2000 canonical-vs-coord grammar.** `mission_dir_name` STRIPS `NNN-`; `coord_mission_dir_name`
   does NOT. The 3 creation sites already `strip_numeric_prefix` → route to the **canonical**
   twin. Routing to the coord variant silently changes on-disk names. Golden-parity test must
   cover legacy (`057-foo`) AND embedded (`foo-<mid8>`) inputs.
2. **#1993 two-surface seam.** The inline code keeps `_lanes_feature_dir` on the COORD surface
   while reassigning `feature_dir` to PRIMARY for meta. A naive one-path extraction collapses the
   surfaces → `require_lanes_json` reads the wrong dir (silent C-LANES-1 regression). The seam
   MUST preserve both outputs.
3. *(rider)* **#1971 deferred import is load-bearing** (`project_resolver.py:14–21`) — keep it;
   reverting to a module-level import re-introduces the package-init cycle.
4. *(rider)* **`.worktrees/` join vs name compose** — only the `<slug>-<mid8>` NAME composition
   routes; legit `dir / ".worktrees" / already_composed_name` joins (manifest, 30+ migrations)
   are allowed and must NOT be swept in.

### New guards / ratchets to add (Paula's enforcement deliverable)

- **Extend** `test_no_worktree_name_guess.py` to flag bare `mission_id[:8]` / `<…>_id[:8]` mid8
  derivation outside the seam (`mission_id`/`mid`-scoped, to exclude unrelated `[:8]` hash/state
  truncation). *Closes the completeness gap that lets the class regrow.*
- **Add** a sibling AST ratchet banning `Path(__file__).resolve().parents[N]` /
  `Path(<pkg>.__file__)…parents[N]` outside `core/paths.py` (with a small justified allow-list).
- **Add** a directional usage assertion: `mission_dir_name(` is not used inside `coordination/`
  read/transaction modules, and `coord_*` verbatim is not used on create paths (Shape B).
- **Shrink** the existing allow-list by removing the 3 #2000 entries after routing (the ratchet
  must *shrink* this mission, never grow).

### Tie to the epics (one coherent step)

Issue #1868 says "bind authority to type/owner for canonical seams"; #1619 says "the Shared Kernel
resolvers (path · identity · status) build the per-domain Contexts." This slice **generalizes the
proven branch_naming seam shape** from identity-naming (done) to project-root (B) and lanes-dir (C),
retires the duplicate surfaces, and ratchets the closed classes shut — assembling the runtime/state
SSOT one resolver at a time, exactly as the consolidated domain model prescribes
(`docs/archive/plans/engineering-notes/runtime_and_state_overhaul/17-consolidated-domain-model.md` §6: "harden
ExecutionContext + enforce the Status boundary first, Strangler"). The deep coord/primary write-side
work (#1878) is the *next* increment, deliberately deferred so this slice stays small, byte-identical,
and shadow-path-free.
