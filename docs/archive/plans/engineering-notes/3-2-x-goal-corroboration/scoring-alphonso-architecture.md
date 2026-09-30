---
title: Neutral scoring — 3.2.1 lead-slice candidates (architectural lens)
description: Architect Alphonso's neutral architectural scoring of the 3.2.1 lead-slice candidates, a non-confirmatory read-only analysis pass.
doc_status: deprecated
updated: '2026-06-16'
---
# Neutral scoring — 3.2.1 lead-slice candidates (architectural lens)

**Author:** Architect Alphonso — **NEUTRAL scoping pass** (not confirmatory, not backlash).
**Branch:** `pr/tool-surface-contract-residuals` (read-only analysis; no commit/switch of the
research branches).
**Date:** 2026-06-16.
**Mandate:** score every candidate on its merits, using **both** white-team and red-team
evidence. The naming/identity work is scored **as one candidate among several** — neither
assumed-winner (white-team bias) nor punished (red-team backlash).

> **Governance.** DIR-001 (one owning authority per concern), DIR-003 (every verdict carries
> evidence at `file:line` / ticket state), DIR-031 (bounded-context boundaries — coord/primary,
> identity≠path, the C-LANES-1 triad — are the test, not a nuisance), DIR-032 (terms confirmed
> against CLAUDE.md canon). All code claims below were grep/`gh`-verified on this checkout, not
> trusted from either squad's prose.

---

## 0. Verified ground truth (the facts both squads must answer to)

Re-verified on this checkout (paths corrected — the module is `src/mission_runtime/`, **not**
`src/specify_cli/mission_runtime/`):

| Fact | Evidence | Bears on |
|---|---|---|
| `branch_naming` seam is real and load-bearing | `lanes/branch_naming.py` — `mission_branch_name_required:301`, `resolve_mid8:169`, `mid8:122`, `worktree_dir_name:484`, `worktree_path:516`, `mission_dir_name:532`, `coord_*:557-622`, `parse_mission_slug_from_branch:771` | Naming rider, #5/#6 |
| `ExecutionContext` is **mutable**; fragments frozen | `context.py:184` `@dataclass` vs `:84/:118/:134/:152/:166/:178` `frozen=True` | #5 epic slice, #1832 |
| Builder mutates 4 substrate fields **post-construction**, rebuilds no fragment | `resolution.py:793-801` (`context.wp_id/lane/branch_name/workspace_path`) | #5 — internal split-brain is real |
| Only **2** fragment reads tree-wide, both `artifact_placement` | `implement.py:552`, `agent/mission.py:727`; zero reads of `.identity/.branch_ref/.status_surface/.workspace/.prompt_source` | #5 — composite is built-and-parked |
| `resolve_action_context` 26 callsites; `resolve_mid8` 25; bare `mission_id[:8]` ~12 live sites | greps below | Naming rider scope |
| `resolve_lanes_dir` does **not** exist; inline at `implement.py:957-1130` (3 surfaces hand-juggled) | grep `def resolve_lanes_dir` → empty; `implement.py:974` `_lanes_feature_dir`, `:1018` `_status_feature_dir` | #1993, #6 |
| Dashboard uses **zero** context/`resolve_action_context` | grep in `src/specify_cli/dashboard/` → 0 | #5 — universal-SSOT claim is false |
| `merge.py` = **3341 lines** (god-module) | `wc -l` | #1827, strategic context |
| #1832 read-path uses `resolve_workspace_for_wp` (a *separate* resolver) at `implement.py:1124` | grep | #1832, #6 |
| Live ticket states (gh, 2026-06-16) | #1716 **OPEN P0+launch-blocker, no milestone**; #1832/#1827/#1891 **OPEN P1, no milestone**; #1619/#1666 **OPEN P0 epics, no milestone**; #1878 **OPEN P2 umbrella**; #1949/#1978/#1899 **CLOSED**; #2000/#1993/#1971/#1900/#1888 milestone **3.2.x** | all |

**Two facts the dialectic-synthesis flagged as genuinely unresolved — I treat them as such and do
NOT let them drive scoring:** (a) status coupling = Goodhart-relabel vs correct facade-adoption
(needs a coupling-*quality* analysis, not done); (b) whether per-authority cooling amid +115% SLOC
growth counts as "progress." Neither is load-bearing for a 3.2.1 *lead-slice* decision.

---

## 1. Per-candidate scored table (1–5; higher = stronger for *leading* 3.2.1)

| # | Candidate | Blast radius | Unblock value | Risk (5=low) | Dep-readiness | Strategic fit (G2 SSOT) | Slice-ability | **Total /30** |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | **#1716** coord topology coherent create→planning (write-side) | 5 | 5 | 2 | 4 | 5 | 3 | **24** |
| 2 | **#1832** claim succeeds, "no workspace resolved" (read-path) | 3 | 4 | 4 | 5 | 4 | 5 | **25** |
| 3 | **#1827** merge baseline circular (unrecoverable) | 3 | 2 | 3 | 5 | 2 | 4 | **19** |
| 4 | **#1891** `agent --json` broken | 2 | 2 | 5 | 5 | 1 | 5 | **20** |
| 5 | **#1619/#1666** unify execution context (shippable slice) | 5 | 5 | 2 | 3 | 5 | 2 | **22** |
| 6 | **#1878 write-side bounded slice** (guarded, char-first) | 5 | 5 | 2 | 3 | 5 | 3 | **23** |
| 7 | **Naming routing rider** (#2000/#1993/#1971/+ratchet) | 2 | 2 | 5 | 5 | 3 | 5 | **22** |

Scores are *for the role of LEAD slice*, i.e. the first, scope-setting, momentum-and-direction
move of 3.2.1 — not a generic "should we do it" (most of these should be done; the question is
*which leads*).

---

## 2. Architectural rationale per candidate

### #1 — #1716 (write-side coord topology coherence) — **24**

The architecturally correct root. `mission create` writes `coordination_branch` into `meta.json`
(making the coord worktree the *authority signal*) while spec/setup-plan/bootstrap can still commit
through the primary checkout before that worktree exists (#1716 body, FR-003/005/019/024/030).
**This is the write-side authoring split-brain that every read-side fix is downstream of** — the
red team's R3 (alphonso) and Priti's §3 both land here: *"a read SSOT cannot be more consistent than
the write SSOT feeding it."* Blast radius 5 (every mission lifecycle transition). Unblock 5 (it is
the keystone of #1619/#1878 — fixing it makes the read-side consolidation *stable* rather than
re-divergent). Strategic fit 5 (this IS G2 "strangle core domains onto SSOT" applied to the
authoring side). Risk 2 — it touches commit/topology-activation semantics, exactly the
characterization-sensitive surface; #1716 explicitly must NOT redesign topology, only make the
activation signal and the materialized authority *coherent*. Slice-ability 3 — bounded but
semantics-heavy; needs coord/flat/primary/husk characterization tests first. Dep-readiness 4 (can
start now; benefits from the #1993 seam but does not require it).

### #2 — #1832 (claim succeeds, "no workspace could be resolved") — **25**

The highest total, and deliberately so under a neutral lens. It is a **live P1** that breaks every
orchestrator parsing claim output, *and* its own suggested fix — "the claim's final
workspace-resolution read should consume the **same resolved context the claim just used to
CREATE** the workspace (single resolution path), not re-derive it" — is the **smallest concrete,
ticket-grounded proof that the threading idea has real value**, stripped of the contested "thread
everywhere" framing. Verified: the create path and the final read (`resolve_workspace_for_wp`,
`implement.py:1124`) are *different resolvers* — a textbook re-derivation split at one callsite.
Risk 4, dep-readiness 5, slice-ability 5 (one command, one resolver unification, regression-test the
claim-output contract). Blast radius only 3 (one command path) and unblock 4 (it de-risks the #1619
thesis by proving single-resolution at a real site) — which is why it does not top blast-radius, but
it is the cleanest *bounded* win that also advances the epic narrative honestly. **It is the
candidate that both the white team (threading has value) and red team (only at sites that already
hold a context — and this is exactly one) agree on.**

### #3 — #1827 (merge baseline circular, unrecoverable) — **19**

Genuinely bad: validation of `baseline_merge_commit` ordered before the write
(`merge.py:1580-1649`), unrecoverable without a manual `meta.json` edit. Should ship in 3.2.x. But
as a **lead** slice it scores lower: it lives inside the 3341-line `merge.py` god-module (risk 3,
slice-ability 4 only because the fix itself is a small re-ordering), unblock 2 (fixes a real bug but
frees no epic chain), strategic fit 2 (it is a correctness patch, not SSOT architecture). A
high-value *rider*, not the architectural spine of the cycle.

### #4 — #1891 (`agent --json` broken) — **20**

Cheap, safe, isolated (`CommitResult` not JSON-serializable). Slice-ability 5, risk 5,
dep-readiness 5. But blast radius 2, unblock 2, strategic fit 1 — it advances no domain
consolidation. **A perfect parallel-lane filler; never the lead.** Including it costs almost nothing
and removes a CI/automation papercut.

### #5 — #1619/#1666 (unify execution context — shippable slice) — **22 (slice), epic as a whole = do-not-lead**

The epics are real and pre-existing (verified OPEN P0). **But the white-team "thread the
ExecutionContext everywhere" framing is refuted by code I re-verified:** the composite is mutable
(`context.py:184`), its builder mutates 4 substrate fields after freezing fragments
(`resolution.py:793-801`) so `branch_name`(substrate) ≠ `branch_ref.target_branch`(fragment) on one
object — **the split-brain relocated *inside* the claimed SSOT** — only 2 fragment reads exist
tree-wide, and the dashboard *structurally cannot* consume an action-scoped fail-closed context
(it must render `legacy:`/`orphan:` missions with no `mission_id`). **A shippable 3.2.1 slice DOES
exist, but it is NOT "thread it everywhere":** it is *(a)* make the builder single-phase so the
composite is genuinely immutable (un-mutate `resolution.py:793-801`, rebuild fragments at WP
resolution), and *(b)* adopt the context at the **2–3 sites that already hold one** (#1832 is one;
`implement.py:386` and `agent/mission.py:772` are the others). That slice = "fix the internal
invariant + adopt where free," which is real architecture and is **substantially the same work as
issue #1832 plus a builder hardening**. Scored 22 as a slice (blast 5, unblock 5, fit 5, but risk 2 /
slice-ability 2 because the freeze is a builder *redesign*, not a finish). **As an epic it must not
lead** — it is too big and the "everywhere" version is the wrong abstraction at current maturity.

### #6 — #1878 write-side bounded slice — **23**

Both squads converge here: the write/entry side is "the highest blast radius" (white §4) and where
the durability bugs live (red R3/Priti §3). A *guarded, characterization-first* cut is genuinely
shippable: route `is_committed`, setup-plan auto-commit, and the implement C-004 fallback through
**one** topology resolver, behind coord/flat/primary/husk characterization tests, with safe-commit
semantics frozen (the #1878 non-goal). **#1716 is in fact the cleanest, most-bounded entry-point of
this slice** — they are the same architectural surface viewed at two grains. Blast 5, unblock 5, fit
5; risk 2 and slice-ability 3 because it touches protected-branch/commit gates. Dep-readiness 3
(needs characterization scaffolding first).

### #7 — Naming routing rider (#2000/#1993/#1971 + ratchet) — **22**

Scored **fairly, neither inflated nor punished.** What survives every attack (white AND red concede
it): the static `branch_naming`/`mid8()` seam is the real SSOT; routing the ~12 bare `mission_id[:8]`
sites through `mid8()`/`resolve_mid8` is a cheap, correct, low-risk consolidation; #1993
(`resolve_lanes_dir` — verified genuinely missing) is a clean pure extraction that kills a 12-mock
test and is the *first bounded step* of the #1878 read-side convergence; #1971 is a verified-landed
behavior with only a surface (import-path) residual. What does **not** survive: that this is the
*mechanism* that makes the class "never regrow" (the ratchet is a literal-shape matcher that
**passes today with ~12 live `[:8]` sites** — verified — and is defeated by `mid[:8]`/`raw_mid[:8]`,
both already live; keep it as a **tripwire**, not an oracle), and that it should *lead* on impact.
Risk 5, slice-ability 5, dep-readiness 5 — it is the safest, most-parallelizable work in the set.
Blast 2, unblock 2 — it frees no P0/P1 and no epic gate. Strategic fit 3 — it advances #1868 as
*real* seam-generalization (project-root B, lanes-dir C), which is honest architecture, but at the
periphery, not the core domain. **It is a legitimate low-risk opener if the operator explicitly
values quick-win momentum + establishing the seam pattern over impact — a chosen trade-off, not a
data-driven conclusion.**

---

## 3. Do shippable 3.2.1-sized slices exist for the epics?

**#1619/#1666 — YES, but not the white-team version.** The shippable slice is *builder hardening +
adopt-where-free*, NOT "thread everywhere":
1. Make `ExecutionContext` genuinely immutable by un-mutating the builder (`resolution.py:793-801`
   into a single-phase build that rebuilds fragments after WP resolution). This *closes the
   internal split-brain* (`branch_name` ≠ `branch_ref.target_branch`) — a real DIR-001 integrity
   win, verifiable by a fragment↔substrate consistency test (currently absent).
2. Adopt the context at the **2–3 sites that already hold one** — #1832 being the flagship (delete
   the redundant re-derivation), plus `implement.py:386` / `agent/mission.py:772`.
3. **Explicit non-goal:** the dashboard and the ~10 context-free bulk sites take the *static*
   `mid8()` seam — they correctly do not thread (R4). The bounded-context boundary (action-context
   for action callers, static seam for bulk) is the *correct* architecture and must be written into
   the slice's scope as a guardrail.
This slice is real, bounded, and advances the epic without gold-plating a parked abstraction.

**#1878 — YES.** A guarded write-side cut led by **#1716** (the coherence of the
topology-activation signal vs materialized authority), routing the write/entry gates through one
resolver, behind characterization tests, safe-commit semantics frozen. #1993 is its in-scope
read-side first step; #1827 is an adjacent ref-advance/durability rider in the same `merge.py`
surface. The slice exists; the discipline is *characterize-then-route*, never *redesign topology*.

**The crucial architectural observation:** #1716, the #1619 builder-hardening slice, the #1878
write-side slice, and #1832 are **not four candidates — they are one architectural surface at four
grains.** #1832 is the smallest concrete instance (one re-derivation at one callsite); #1716 is the
authoring root; the #1619 slice is the value-object hardening that makes single-resolution durable;
issue #1878 is the umbrella. A coherent 3.2.1 lead picks the **entry-grain that is both high-impact and
characterizable now**, then pulls the others in dependency order.

---

## 4. Ranked recommendation for the 3.2.1 LEAD slice

**Recommended lead: a paired "write-side coherence + single-resolution" slice — #1716 as the
architectural spine, opened by #1832 as the concrete, low-risk, momentum-setting first WP.**

Ranked:

1. **#1716 + #1832 paired (LEAD).** #1716 is the root authority bug (highest blast radius, keystone
   of #1619/#1878, pure G2 SSOT). #1832 is its smallest verifiable instance and the safest possible
   *first* WP — it lands a real P1 fix, proves single-resolution at one site, and establishes the
   "consume the resolved context, don't re-derive" pattern the whole slice generalizes. Leading with
   #1832 gives the safety the white team wanted *without* the priority inversion the red team
   correctly identified.
2. **#1619 builder-hardening slice (immediate follow-WP).** Un-mutate the builder; adopt at the 2–3
   context-holding sites; write the action-vs-bulk boundary as a guardrail. This is the honest,
   bounded version of the epic — and it is mostly the same surface as #1.
3. **Naming routing rider (#2000/#1993/#1971 + ratchet-as-tripwire) in parallel lanes.** Genuinely
   good, safe, parallelizable work that advances #1868 as real seam-generalization and supplies
   #1993 (`resolve_lanes_dir`) as the read-side first step #1716/#1878 will consume. Ship it
   *alongside*, scoped honestly (tripwire, not oracle), but do **not** let it be the headline.

Riders to fold into open lanes regardless of lead: **#1891** (free CI/automation win) and **#1827**
(unrecoverable durability bug — ship it, it lives in the same `merge.py` write-side surface as
issues #1716/#1878).

### The single trade-off the operator must decide, stated plainly

**Lead with IMPACT (the write-side coord/topology authority + single-resolution: #1716/#1832,
spine of #1619/#1878) at higher characterization-test cost and semantics risk — OR lead with SAFETY
(the naming routing rider: byte-identical, parallel, zero-semantics-risk) accepting that it frees no
P0/P1 and leaves the highest-blast-radius surface and the live unrecoverable bugs for a later
cycle.**

My neutral architectural read: the evidence (verified write-side split-brain at #1716, the #1832
suggested-fix being literally "single resolution path," the read-SSOT-can't-exceed-write-SSOT
constraint conceded by both squads) points to **leading with impact, opened by the low-risk #1832
WP** — which captures most of the safety argument without the priority inversion. The naming rider
is a legitimate *parallel* track and a legitimate *alternative lead only if the operator explicitly
prefers momentum/pattern-establishment over impact* — but that is a values choice, not what the
data dictates.
