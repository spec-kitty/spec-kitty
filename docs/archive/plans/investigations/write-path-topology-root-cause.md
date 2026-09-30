---
title: 'Write-path topology: ambient-location root cause and remediation options'
description: 'Root-cause analysis of the ambient-location write-target defect class (#3129, 14 issues), squad-corroborated, with a scoped remediation seed for a future mission.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/plans/3-2-x-milestone-roadmap.md
- docs/changelog/3.2.x.md
- docs/architecture/execution-lanes.md
- docs/architecture/git-worktrees.md
- docs/operations/how-to-maintain.md
---

# Write-path topology: ambient-location root cause and remediation options

> **Historical (delivered in 3.2.6).** The remediation this note scoped shipped in the 3.2.6 line: a checkout-identity guard now refuses foreign-checkout writes (#3128) across the #3129 command family, via mission `write-path-integrity-01KZZD69` and the 3.2.6rc2 fixes (see `CHANGELOG.md`). References below to "the current 3.2.x milestone" are prior-cycle. Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

**Scope:** pre-spec research. Corroborate or disprove GH issue
[#3129](https://github.com/Priivacy-ai/spec-kitty/issues/3129)'s diagnosis before any mission is
opened against it. READ-ONLY analysis; no product code changed by this document. Tracker
housekeeping (parenting, labels) that followed from this research is recorded in
[§6](#6-tracker-actions-already-taken) — not a substitute for a mission.

**Method:** an independent dialectic squad (architecture-verifier, governance-verifier, skeptic,
advocate lenses + synthesis) investigated the claim from primary sources — code, docs, and the live
tracker — rather than accepting the filer's synthesis at face value. Full lens outputs are preserved
in this doc's [§3](#3-the-four-lenses).

**Origin:** a maintainer observation — *"the read vs write paths topology issues keep rearing their
heads, and we're chopping them off as they spawn"* — prompted LynnColeArt's investigation, filed as
#3129.

---

## 0. The one-paragraph answer

**Root cause confirmed:** lane worktrees, the coordination worktree, and the primary checkout share
one git object store and one ref namespace (standard git-worktree semantics, not a spec-kitty
defect — confirmed against `docs/architecture/git-worktrees.md`). **No code path in the runtime
compares the invoking checkout against a mission's declared workspace before allowing a write.**
The nearest existing safeguard, `commit_guard.py`, only gates whether a *ref* is protected (e.g.
`main`); it takes no cwd/workspace-identity input. The nearest routing logic,
`mission_runtime/artifacts.py`'s coord/primary placement resolver, decides *which partition* a
write should target — but presupposes the write already originates inside a valid mission
workspace. Sanctioned 3.2.x work (epic #1878, milestone goal G2: placement-routing +
commit/protected-branch durability) inherits that same precondition gap and would not have caught
the 2026-07-31 `spec-kitty-saas` incident (a compacted Codex agent resumed in the wrong checkout and
wrote artifacts into it, undetected, next to a second agent's uncommitted edits).

**What is NOT corroborated to the same degree:** that the fix requires a ThickTicket/SugarFang-style
shadow-workspace topology redesign. A cheap, additive, already-designed check — GH #3128, "fail
closed when a mission-mutating command is invoked from a checkout the mission does not own" —
would independently have caught the actual incident with zero topology change. Its own author
ranks it "the cheap first mitigation regardless" of any later shadow-workspace decision.

**What was explicitly rejected as a process move:** creating a new P0 "Topology / Isolation
breaches" epic and reparenting all 14 issues #3129 names into it. 11 of the 14 already have working
homes under active functional epics (#2624, #2160, #1619, #1795, #2017); the closest existing
umbrella (#1878) carries an on-record maintainer non-goal ("No topology redesign — the
coordination-branch/worktree topology stays as-is"); and #3129 itself states "Not urgent relative to
MVP," which contradicts a P0 (release-blocker) label under this repo's own priority definitions
(`HOW_TO_MAINTAIN.md`).

---

## 1. The defect class

A command's write target is derived from **ambient invoking location** rather than from the
mission's **declared** target. Symptom recurs verbatim across issues filed by different authors —
`#3051` and `#2613` both use the phrase "locate_project_root() collapses to PRIMARY" in their own,
independently-written reproductions (`#3051` self-identifies as "the third confirmed command family
hitting this exact mechanism, after #3049 and #2613").

| # | Symptom | Existing epic parent |
|---|---|---|
| #3124 | `setup-plan` reports the primary checkout's branch as the mission's target, `branch_matches_target: true` | *(unparented before this investigation — now #1878, see §6)* |
| #3051 | `doctor mission-state --audit/--fix` worktree-unaware; `locate_project_root()` collapses to PRIMARY | #2624 |
| #3049 | `migrate backfill-runtime-state` writes outside a linked worktree; guard reads the same redirected path | *(unparented before this investigation — now #1878, see §6)* |
| #2613 | `doctor tool-surfaces --fix` from a lane silently mutates the primary's manifest | #2624 |
| #2549 | `move-task --force` from a lane commits placement-partition status to the lane branch | #2160 |
| #2702 | `record-analysis` reports a primary path while committing the coordination copy | #2160 |
| #2334 | `kitty-specs` state lives in N copies across primary/coord/lanes, hand-synced | #1619 |
| #2367 | merge blocked by an uncommitted VCS-lock in the coordination worktree | #1795 |
| #2797 | git-revert transport authority and coord-worktree cleanliness | #1795 |
| #2274 | lane-hygiene guard compares `kitty-specs` by commit history, not content | #2017 |
| #2570 | multi-lane allocator serialized behind its own uncommitted frontmatter write | #2017 |
| #2745 | terminus gaps when a WP was implemented directly on the target branch | #1795 |
| #1914 | umbrella: governed operations dirty the working tree with their own writes | #1619 |
| #3128 | nothing refuses when a command is invoked from a checkout the mission does not own | *(unparented before this investigation — now #1878, see §6)* |

**Two additional candidates surfaced during triage, not yet confirmed members** (flagged, deferred —
see the triage note in `docs/plans/3-2-x-milestone-roadmap.md` § Addendum 2026-08-01):
- `#3131` — `spec-kitty merge` ignores mission retention constraints and deletes lane
  branches/worktrees (target derived from default flags, not the mission's declared retention
  contract)
- `#3133` — `record-analysis` silently writes `verdict: unknown` for an explicitly ready report
  (content derived from a fallback path, not the mission's actual declared conclusion — same shape
  as sibling #2702, already in the class)

---

## 2. The missing seam

There is no enforced invariant that a mission-mutating command's invoking checkout matches the
mission's declared workspace. The pieces that exist today operate on adjacent, insufficient axes:

- `commit_guard.py` — the single commit-protection decision point. Gates whether a **ref** is
  protected. Takes no cwd/workspace-identity input. Cannot distinguish "the right agent, wrong
  checkout" from "the right agent, right checkout."
- `mission_runtime/artifacts.py` (coord/primary placement resolver, referenced in this repo's
  `CLAUDE.md` "Execution Workspace Strategy") — decides which **partition** (coord vs. primary) an
  artifact kind should target, *given that a commit is already happening*. It is a routing layer on
  top of the shared object store, not a boundary around it.
- `locate_project_root()` (`src/specify_cli/core/paths.py`) — deliberately walks up from a worktree
  to resolve a canonical project root. Useful for config discovery; the same mechanism means a
  command invoked from an unexpected directory silently resolves to *some* project root rather than
  refusing.

No code path was found (grepped for `invoking checkout`, `expected_workspace`, `fail closed` +
location-related terms) that compares actual cwd against the mission's *declared* workspace and
refuses on mismatch. `#3128`'s own proposed fix is explicitly the missing comparison-and-refuse
check — additive, not a topology change: *"the mission already knows enough to answer this... so the
check is a comparison against something already computed, not new bookkeeping."*

**The genuine open architectural question** (not resolved by this research, correctly gated as a
separate design-spike): is a comparison-and-refuse check sufficient long-term, or does the "every
mutating call site must remember to call it" shape of that fix risk being bug #16 in the same
disease class it's meant to close? The skeptic lens raised this against its own recommendation (see
§3) — `#1878`'s own deferred-item list already names "an is-a-worktree type invariant... instead of
ad-hoc path checks" as the direction the team wants to graduate toward, which is closer to the
structural-guarantee end of the spectrum than a single check.

---

## 3. The four lenses

Full independent investigations, preserved for traceability (each lens fetched primary sources
itself rather than trusting the others' summaries).

### Architecture-verifier — CORROBORATED (high confidence)

- Confirmed `docs/architecture/git-worktrees.md` states plainly (its own words): "All worktrees
  share: Commit history... Branch definitions... Configuration... Remote references" — a worktree's
  `.git` is a pointer file back to one real object database. Standard git semantics, not
  spec-kitty-specific.
- The same doc's "Full Checkouts" section concedes isolation is behavioral, not structural:
  "Isolation is enforced by lane computation, ownership metadata, workspace context, and merge
  guards rather than by hiding files from the working directory."
- Inspected `commit_guard.py`, `mission_runtime/artifacts.py`, `locate_project_root()` directly (see
  §2) and found no structural boundary against ambient-location writes for the command class #3129
  names.
- `#3128` (filed one day before #3129, still open, zero commits referencing it) is precisely the
  missing check, independently confirming the gap from the tracker side.
- **Strongest counter-evidence acknowledged:** `commit_guard.py` + the placement resolver are real,
  working, tested infrastructure — they correctly block unauthorized commits to protected branches.
  They operate on a different axis (branch-protection vs. workspace-identity) and do not defeat the
  "wrong location, undetected write" failure mode, but the investment is real and should not be
  discounted.

### Governance-verifier — DISPROVEN *(on the requested tracker action, not the technical claim)*, high confidence

- 11 of 14 issues already have functional-epic homes; HOW_TO_MAINTAIN.md's own triage rule prefers
  parenting under an existing epic over inventing a new one, when an existing epic already covers
  the area.
- `#1878`'s non-goal ("No topology redesign") is a direct, on-record conflict with a new
  topology-remediation epic, unless explicitly reconciled.
- `#2392` (closed precedent: consolidated 4 bugs into one canonical seam) shows this repo's own
  successful playbook is narrow-scope-after-confirmed-mechanism, not broad-scope-on-a-design-spike.
- `#3129` states "Not urgent relative to MVP" — directly undercuts a P0 label.
- **Strongest counter-evidence acknowledged:** the current 3.2.x milestone doc already scopes G2 as
  "the full #1878 coord/primary write-side strangler" — an operator decision already pulling
  write-path/topology-adjacent work onto the active roadmap. This weakens (does not eliminate) the
  P0/non-goal objections — it is evidence to hand the operator for an explicit decision, not license
  for an agent to infer and batch-apply that decision unilaterally.
- **Recommended scope (adopted, see §6):** no new epic; leave the 11 in place; park only the
  currently-homeless items under the existing `#1878` umbrella with an explicit flag on the non-goal
  tension; provisional priority, not P0, pending operator confirmation.

### Skeptic — PARTIALLY_CORROBORATED (medium confidence)

Argued the already-sanctioned `#1878`/G2 work (placement-routing + commit-durability, both landing
in 3.2.x per `docs/release-goals/3.2.x.md`) should be sufficient — and found, honestly, that it
isn't:

- **Critical counter-finding (against its own position):** placement-routing presupposes a valid
  mission workspace and only decides which partition to target once a write is already happening
  there. It has no mechanism to catch a checkout that is not part of the mission's declared topology
  in the first place — exactly the shape of the 2026-07-31 incident.
- `#3128`'s proposed fix is explicitly *not* a topology redesign — a cheap comparison-and-refuse
  check against data the mission already computes — and Lynn's own comment ranks it "the cheap first
  mitigation regardless" of any topology decision.
- **Self-undercutting counter-evidence, disclosed honestly:** 14 separate issues for one diagnostic
  root is itself evidence that "add a targeted check" has a poor track record in this codebase —
  several of the 14 occurred in paths that already had *some* routing/guard logic. `#1878`'s own
  deferred-item list frames "ad-hoc path checks" as the weaker pattern the team wants to graduate
  away from, toward type-level invariants. A physically separate object store (ThickTicket-style)
  makes the class impossible by construction; a check-based fix is a weaker guarantee that must be
  called at every site. The skeptic concluded its own recommended scope "buys time... but does not
  resolve the deeper architectural argument — it just kicks it one incident down the road."

### Advocate — CORROBORATED (high confidence)

- `#3051`/`#2613` reproduce the identical mechanism in their own words, filed by a different author
  than Lynn — cross-author corroboration, not just one investigator's framing.
- `#3124` (Lynn) is explicitly the "read-side analogue" of `#3051`/`#2613` in its own body.
- The 2026-07-31 incident is narrated consistently, with matching specifics, across two independent
  issues (`#3129`, `#3128`).
- `#2392` is direct successful precedent for unifying a scattered bug cluster into one seam before
  implementation — while disciplined about excluding adjacent-but-different-mechanism issues.
- **Counter-evidence disclosed:** `#1878`'s non-goal is real and dated, though `#3129` explicitly
  disclaims rewriting the execution model and defers the topology-compatibility question to the
  maintainer rather than asserting the answer. Also: 2 of the 14 (`#2334`, `#1914`) are
  adjacent-but-distinct mechanisms rather than literal instances — the "one class" framing is
  somewhat looser than the summary table implies, a looseness Lynn's own wording ("reachable from the
  same fact") anticipates.

### Synthesis — PARTIALLY_CORROBORATED overall, high confidence

Reconciled rather than averaged: the technical-diagnosis axis (real gap, no structural boundary
exists) and the process/remedy axis (wrong to batch-reparent into a new P0 epic) are independent
questions that can both resolve differently, which is exactly what happened. Full reasoning
preserved in `docs/plans/3-2-x-milestone-roadmap.md` § Addendum 2026-08-01.

---

## 4. Remediation options (for a future mission to select from)

| Option | Shape | Status |
|---|---|---|
| **A — fail-closed checkout-identity check** (`#3128`) | Additive comparison against already-computed mission/lane metadata; refuse mission-mutating commands invoked from a checkout the mission doesn't own | **Recommended as the near-term mission scope.** Cheap, closes the actual dated incident, no topology change, independently endorsed by the issue's own author as first-priority regardless of the larger decision. |
| **B — ThickTicket-style scoped shadow workspace** | Agent gets a workspace created from a recorded source HEAD, living outside the repo; a handle scoped to that shadow makes the canonical tree *unreachable*, not merely off-limits; explicit `ApplyShadowMerge` crossing point | Structural guarantee (collision impossible by construction), but unproven for this codebase and explicitly gated — pursue only if incidents of the same shape recur after Option A + the `#1878` strangler land. |
| **C — SugarFang-style mirrored shadow** | Every mutation path mirrors the workspace into a shadow git repo with stamped `[mission:<id>] [session:<id>]` commits; does not prevent drift, makes it attributable/reversible | Addresses a different property (provenance/recoverability of *all* mutations, including planned ones) than B (collision prevention). Lynn's own comment on #3129 frames B and C as complementary, not exclusive — open question for the operator (§5). |
| **D — new P0 "Topology / Isolation breaches" epic, full reparent of 14 issues** | — | **Rejected.** See §3 governance-verifier and `docs/plans/3-2-x-milestone-roadmap.md` § Addendum 2026-08-01. |

If a mission is opened, **Option A is the concrete, scoped, low-risk candidate**: single check,
single call site pattern (mission-mutating commands), acceptance criterion is exactly the
2026-07-31 incident shape (agent resumes in an unrelated checkout → command refuses rather than
serving normally). Options B/C are design-spike material for a later mission, contingent on Option A
proving insufficient.

---

## 5. Open questions for the operator

Carried forward from the governance/synthesis lenses — these are calls this research deliberately
did not resolve unilaterally:

1. Should `#1878`'s non-goal ("No topology redesign") be formally amended given this finding, or
   should `#3129` be treated as strictly out-of-scope for `#1878` (needing some other future home if
   a redesign is eventually warranted)? This reverses an on-record maintainer ruling.
2. Should `#3128` (Option A) be added to the already-committed 3.2.x/G2 milestone scope now, or
   deferred to the next cycle? The milestone doc is operator-owned.
3. Is there an actual maintainer mandate for P0 urgency on this class, or does `#3129`'s own "not
   urgent relative to MVP" framing stand?
4. If a future design-spike concludes redesign is warranted: pursue ThickTicket (B) and SugarFang
   (C) as complementary, or choose one exclusively? This is an architecture decision outside a
   planning lens's authority.
5. Are `#3131` and `#3133` (§1, unconfirmed candidates) actually members of this class? Deferred
   pending a closer read; would extend the table in §1 if confirmed.

---

## 6. Tracker actions already taken

Applied 2026-08-01, scoped narrowly per the governance-verifier's recommendation (not a mission, not
a batch reparent):

- `#3128`, `#3124`, `#3049` parented under `#1878` as strangler-completion work (consistent with its
  non-goal — they fix ambient-location bugs within the current topology, they do not redesign it).
- `#3129` parented under `#1878` for **tracking/reference only** — explicitly flagged in a comment on
  `#1878` as falling inside that epic's own non-goal, not an implementation mandate.
- The other 11 issues in the class left exactly where they were (no reparenting).
- No new epic created. No P0 label applied anywhere in this class.
- Full comment trail: `#1878` issue comments, 2026-08-01.
- Companion roadmap addenda: `docs/plans/3-2-x-milestone-roadmap.md` § Addendum 2026-08-01,
  `docs/release-goals/3.2.x.md` G2 section (2026-08-01 scoping-gap note).

---

## See also

- [3.2.x Milestone — Roadmap](../../../plans/3-2-x-milestone-roadmap.md) — § Addendum 2026-08-01
- [3.2.x — Release Goals](../../../changelog/3.2.x.md) — G2, 2026-08-01 scoping-gap note
- [Investigations index](../../../plans/investigations/index.md)
