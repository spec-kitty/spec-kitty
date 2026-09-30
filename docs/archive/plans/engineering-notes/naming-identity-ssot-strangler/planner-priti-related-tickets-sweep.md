---
title: Naming/Identity & Read-Path SSOT — Related-Ticket Discovery Sweep (planner-priti)
description: Planner Priti's related-ticket discovery sweep for the naming/identity and read-path SSOT work, under the decision-documentation directive.
doc_status: deprecated
updated: '2026-06-16'
---
# Naming/Identity & Read-Path SSOT — Related-Ticket Discovery Sweep (planner-priti)

> **Profile-loaded.** Authored as **Planner Priti** (work-decomposition + delivery
> sequencing) under **directive 003 — Decision Documentation Requirement**: every
> classification, fold-in recommendation, and close verdict below carries its
> rationale and a hard evidence link for traceability. This is a FOCUSED
> **discovery/triage** sweep — *no claiming, no implementation, no commits/branch
> switches.* Claim (operator-assign) happens at spec time per the standing rule
> (operator 2026-06-16); cleanup closes (provable dup / provably-done) are exempt
> and listed in §4.
>
> **Baseline:** branch `research/naming-identity-ssot-strangler` @ cli 3.2.0
> (PR #2001, `fcf9be595`). **Mission SSOT surface:** A — identity/naming
> (`lanes/branch_naming.py`); B — project-root (`core/paths.py`); C — lanes-dir
> (`resolve_lanes_dir`, to extract); D — coord/primary read-path
> (`_read_path_resolver`/`surface_resolver`/`feature_dir_resolver`); E — ownership
> validation (`ownership/validation.py`). **Epics:** #1878 (coordination strangler),
> #1868 (canonical seams), #1619/#1666 (runtime/state overhaul).
>
> **Method:** went BROADER/DEEPER than the prior pass — ~30 angled `gh issue list
> --state all --search` queries across the whole surface (naming/identity, mid8,
> slug, branch/worktree name, compose, seam, ratchet, strangler, split-brain, SSOT,
> shadow-path, mirror, parallel-impl, project-root, locate_project_root, paths.py,
> lanes.json/dir, feature_dir, read-path, resolver, coordination, primary,
> topology, flatten, genesis, husk, surface, owned_files, ownership, glob,
> existence) PLUS sub-issue/body extraction on #1878/#1868/#1619/#1666 and body
> reads of every newly-surfaced candidate. De-duplicated against the §2 overview
> table and Priti's prior-pass table.

---

## 1. Headline

The prior pass + capstone already nailed the **core 4-ticket slice** (#2000, #1971, #1993, #1888) and correctly fenced #1878 write-side out. This deeper sweep surfaces
**two material upgrades to scope** and a cluster of confirm-out-of-scope items:

1. **#1900 (C-002 topology-ratchet drain) is now UNBLOCKED and should be a confirmed
   fold-in (WP04 rider), not a "fold only if trivial."** Its stated blocker —
   "coordination-merge-stabilization lands" (#1772 / epic #1796) — has **shipped**
   (#1772 CLOSED COMPLETED; #1796 epic CLOSED). Its 3 migration targets are the
   *same seams* WP04 already touches: `status_transition.py` topology predicates →
   `surface_resolver.classify_worktree_topology`; `merge.py:1114` + `preflight.py:86`
   legacy composes → `mission_branch_name_required`. Same ratchet family (C-002 here,
   C-003 in #2000), same shrink-the-allow-list idiom.
2. **#1681 (CLOSED) is the project-root/lanes-dir/feature_dir residual the SSOTs
   target** — "225 raw `kitty-specs/<slug>` path constructions across 74 files;
   FR-031 global guarantee NOT delivered." It was closed COMPLETED 2026-06-04 with
   **no resolution comment**, despite its own body stating the global guarantee
   was unmet. Recommend: **do NOT reopen blindly**, but adopt its Bucket-A/B/C
   triage as the *evidence base + allow-list seed* for WP03 (project-root) and the
   new `parents[N]` / raw-path ratchet. The capstone's `parents[N]` ratchet is the
   correct enforcement home for the still-open tail.

Everything else discovered is correctly **separate-mission / out-of-scope / dup**.

---

## 2. Full discovered-ticket table

State verified via `gh ... --state all`. **NEW?** = not in the §2 overview table
and not in Priti's prior-pass table. Relation keys to SSOTs A–E.

| id | title (short) | state | relation to SSOT surface | classification | recommended disposition |
|----|---------------|-------|--------------------------|----------------|--------------------------|
| **#2000** | Route remaining `<slug>-<mid8>` composes through seam | OPEN | A — identity compose | **FOLD-IN** (primary live work) | WP04. Confirmed (prior pass). |
| **#1971** | Consolidate 3-way `locate_project_root` split-brain | OPEN | B — project-root | **FOLD-IN** | WP03. Confirmed (prior pass). |
| **#1993** | Extract `resolve_lanes_dir()` pure seam | OPEN | C — lanes-dir | **FOLD-IN** | WP02. Confirmed (prior pass). |
| **#1888** | finalize-tasks ownership accepts non-existent `owned_files` | OPEN | E — ownership | **FOLD-IN** (verify+close+test) | WP01. Confirmed (prior pass). |
| **#1900** | Drain topology-ratchet **C-002** allow-list once coord-merge-stabilization lands | OPEN | A+D — ratchet/seam twin of #2000 | **FOLD-IN (UPGRADED)** | **WP04 rider.** Blocker (#1772/#1796) has LANDED → now actionable; 3 sites migrate to the same seams WP04 uses. |
| **#1681** | 225 raw `kitty-specs/<slug>` path constructions remain (FR-031 not delivered) | **CLOSED** (COMPLETED, no resolution comment) | B+C+D — raw-path residual | **FOLD-IN (evidence/ratchet)** | Adopt its Bucket A/B/C triage as the WP03 + `parents[N]`/raw-path ratchet allow-list seed; verify the tail, do NOT mechanically reopen. |
| #1900-adjacent: **#1791** | bulk-edit review diff-compliance: coord-topology head-ref regression test; `.jsonl` heuristic | OPEN | D — coord-topology read (adjacent) | SEPARATE (#1930 bulk-edit) / FOLLOW-UP | Out-of-scope; bulk-edit gate family. Note the `.jsonl` classifier as a known coord-read symptom. |
| **#1832** | implement claim "no workspace could be resolved" + skips prompt regen | OPEN | C/D — read-path symptom | **VERIFY-AFTER (WP02/WP04)** | Re-test after #1993; root cause is "claim's final read re-derives instead of consuming the resolved context" — exactly the SSOT framing. Likely closeable post-WP02. |
| #1890 | doctor recommends nonexistent `agent worktree repair` | OPEN | D — coordination UX | OUT-OF-SCOPE / FOLLOW-UP | Doc/UX; re-confirm prior pass. |
| #1716 | Make coordination topology coherent (create→planning) | OPEN | D — topology (write/entry) | SEPARATE-MISSION (#1878) | Broader topology; #1878 sequencing. |
| #1887 | Squash-merge duplicates planning artifacts under `.worktrees/<slug>-coord/` | OPEN | D — coord read/merge-path | SEPARATE-MISSION (#1878) | Merge-path, not naming SSOT. |
| #1827 | merge baseline-validation circular failure | OPEN | D — merge mechanics | SEPARATE-MISSION (#1878) | #1878 item 7. |
| #1357 | lock-serialize `CoordinationWorkspace.resolve()` race | OPEN | D — concurrency | SEPARATE-MISSION (#1878) | Concurrency, not naming. |
| **#1829** | DECISION: drop local-main protected-branch refusals, keep coord routing | OPEN | D — coord write/entry (the #1878 write-side core) | SEPARATE-MISSION (#1878 write-side) | The canonical #1878 write-side decision doc. Names step-1 reader-alignment as prereq (dashboard scanner coord-first). Explicitly the deferred-mission's spine. |
| **#1828** | `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` asymmetry | OPEN | D — write/entry | SEPARATE-MISSION (#1878) | Superseded-by-#1829; write-side. |
| **#1914** | Umbrella: governed/gate ops must be no-op-stable | OPEN | D — write/entry (self-writes) | SEPARATE-MISSION | Sibling umbrella to #1878 write-side; home of closed #1916. |
| #1766 | Strict `owned_files` induces workarounds (leeway policy) | OPEN | E — ownership policy | OUT-OF-SCOPE / FOLLOW-UP | Policy, distinct from #1888 existence-check. |
| **#1979** | WP changes shared contract pinned by out-of-owned test | OPEN | E — ownership policy | OUT-OF-SCOPE / FOLLOW-UP | Review-visibility policy; distinct from #1888. |
| **#1162** | tasks auto-detect cross-namespace `owned_files` | OPEN | E — ownership authoring | OUT-OF-SCOPE / FOLLOW-UP | Authoring-time ownership; not existence-check. |
| #1900-family **#1923** | DRG residual orphan curation (14 orphans) | OPEN | — (doctrine graph) | OUT-OF-SCOPE | Doctrine DRG, unrelated to path/identity SSOT. |
| **#1927** | Harden canonical-producer lint CP001 blind spots | OPEN | — (event lint) | OUT-OF-SCOPE | Event-emission lint; *ratchet-adjacent in spirit only* — different oracle. |
| #1890/#1832 already above | | | | |
| **#1057** | Retire pre-3.0 status/task readers from active runtime | OPEN | B/C/D — legacy read-path readers | SEPARATE-MISSION (legacy-cutover) | Same "one authority, no legacy hot-path" spirit, but a distinct legacy-cutover mission (lane-dir/frontmatter readers). Reference, do not fold. |
| **#1059** | Compatibility inventory + sunset policy | OPEN | cross — compat registry | OUT-OF-SCOPE | Meta-policy; the registry that #1057/#1060 feed. |
| **#1060** | Remove hidden `--feature` aliases | OPEN | A — selector vocabulary | OUT-OF-SCOPE (partly shipped #1985) | Selector-vocabulary cleanup; mission 01KV5F0B did the #1060-A slice. Not path/identity SSOT. |
| **#1058** | Split dossier queue migration from live emitter APIs | OPEN | — (sync emitter) | OUT-OF-SCOPE | Sync/dossier compat; unrelated surface. |
| #1890 | (above) | | | | |
| **#1834** | accept re-runs negative invariants vs PRE-MERGE primary tree | OPEN | D — primary-vs-lane read | SEPARATE-MISSION (#1914/#1878) | Reads wrong tree (primary pre-merge); coord/primary read symptom but an accept-gate write-side concern. |
| **#1817** | Merge gate refuses approved WP on stale rejected review artifact + override | OPEN | — (merge gate) | OUT-OF-SCOPE | Review-artifact gate; unrelated to naming/path. |
| #1185 | Claude Code statusline for active Mission/WP/step | OPEN | A — display only | OUT-OF-SCOPE | Display feature (matches every search on "mission"). |
| #1063 | Spec Kitty clutters PR files + auto-commit opt-out | OPEN | D — commit policy | OUT-OF-SCOPE / FOLLOW-UP | UX/commit-policy; #1878-adjacent at most. |
| **#1738/#1739/#1740/#1741/#1742/#1743/#1744/#1745** | Mission Clarity Layer (#1746): mission-card.json, closes_issues, EMI | OPEN | — (mission summary) | SEPARATE-MISSION (#1746) | A distinct MC-layer mission; surfaces on `meta.json`/`feature_dir` searches but is not the path/identity SSOT. |
| #1900 (above) | | | | |
| #1907 | Subagent worktrees on stale ancestors + editable-install repoint | OPEN | — (dev tooling) | OUT-OF-SCOPE | Dev-ergonomics hazard for *running* the mission, not a product seam. Operational caveat for implementers (see §5). |

### Epic / umbrella anchors (stay open, reference in spec)

| id | role | state | note |
|----|------|-------|------|
| #1878 | umbrella — coordination placement/identity strangler | OPEN | mission completes items #3/#5 only; write-side (#1829/#1828/#1716/#1827/#1357/#1887/#1834) stays. |
| #1868 | epic — canonical seams | OPEN | #2000/#1900 advance it. |
| #1619 | root epic — runtime/state overhaul | OPEN | #1971/#1993/#1681-tail advance it. |
| #1666 | epic — execution-state domain redesign | OPEN | #1993 advances; home of closed #1917. |
| #1796 | epic — safe-commit/protected-branch coherence | **CLOSED** | #1900's blocker; now landed → #1900 unblocked. |
| #1797 | epic — codebase sanitization / LOC reduction | OPEN | #1681-class raw-path drain lives here too. |

---

## 3. Newly surfaced beyond the prior pass (the callout)

The prior pass (its §1 table) covered: #1878, #1868, #1619, #1666, #1929, #1908, #1899, #1915, #1918, #1949, #1978, #1917, #1916, #2000, #1971, #1993, #1888, #1900, #1716, #1887, #1827, #1357, #1766, #1979, #1890, #1832. **NEW this sweep** (material
to the surface, absent from both prior tables):

| id | state | why it is new + material |
|----|-------|--------------------------|
| **#1681** | CLOSED | The named **225-site raw-path residual** (project-root/lanes-dir/feature_dir) — direct evidence base + allow-list seed for SSOTs B/C and the new `parents[N]`/raw-path ratchet. Capstone references the *idiom* but never cites this ticket. **Highest-value new find.** |
| **#1829** | OPEN | The canonical **#1878 write-side decision doc** (drop local-main refusals, route via `BookkeepingTransaction`). Pins the boundary of what stays OUT and names the reader-alignment prereq. Confirms the write-side is a real, scoped, separate mission — not vapor. |
| **#1828** | OPEN | Protected-branch env-var asymmetry; superseded by #1829. Confirms write-side cluster. |
| **#1914** | OPEN | "governed/gate ops no-op-stable" umbrella — the self-write/dirty-tree sibling of #1878; home of the closed #1916. Clarifies why #1916 is closed-not-orphaned. |
| **#1834** | OPEN | accept re-runs invariants against the **pre-merge primary tree** — a concrete coord/primary *read-the-wrong-tree* failure, but write-side/accept-gate. Reinforces D-surface blast radius. |
| **#1057** | OPEN | Retire pre-3.0 status/task readers — the legacy-cutover sibling of the SSOT consolidation (same "no legacy hot-path" spirit, distinct mission). |
| **#1058 / #1059 / #1060** | OPEN | Legacy-cleanup cluster (#1056 review fallout): compat inventory, dossier emitter split, `--feature` alias removal. Adjacent vocabulary/compat hygiene; out-of-scope but worth naming so they aren't re-discovered mid-mission. |
| **#1162 / #1979** | OPEN | Two more ownership-family tickets (cross-namespace auto-detect; shared-contract pin) — confirm #1888 is the *only* ownership existence-check; the rest is policy → separate. |
| **#1791** | OPEN | bulk-edit coord-topology head-ref + `.jsonl` classifier — a coord-read symptom living in the bulk-edit gate (#1930), not this slice. |
| **#1923 / #1927** | OPEN | DRG-orphan curation and CP001 lint hardening — surfaced on "ratchet"/"strangler" searches but are *different oracles* (doctrine graph / event emission). Explicitly NOT the AST path/identity ratchet. |
| **#1738/#1739/#1740–#1745 (#1746)** | OPEN | Mission Clarity Layer mission — surfaces on `meta.json`/`feature_dir`/`closes_issues`; distinct mission, not path/identity SSOT. |
| **#1185** | OPEN | Statusline feature — pure display; noise on "mission/WP" searches. |
| **#1063** | OPEN | PR-clutter / auto-commit opt-out — UX/commit-policy, #1878-adjacent. |
| **#1907** | OPEN | Subagent stale-ancestor + editable-install repoint — operational hazard for *running* this mission (see §5), not a product seam. |

**Net: ~16 newly-surfaced tickets beyond the prior pass.** Of these, exactly **one
changes the slice** (#1900 upgraded to confirmed fold-in; #1681 adopted as evidence/
ratchet seed). The rest harden the OUT-OF-SCOPE fence (the write-side cluster #1829/#1828/#1914/#1834, the legacy-cleanup cluster #1057–#1060, the ownership-policy
cluster #1162/#1979, the MC-layer mission #1746, and the different-oracle lints #1923/#1927).

---

## 4. Closes performed this sweep

**None.** (Cleanup closes are claim-exempt, but I performed none.) Rationale
(DIR-003): the seven provably-done identity tickets (#1899/#1915/#1918/#1949/#1978/#1917/#1916) were **already closed by the prior pass** with evidence comments — no
double-close needed. **#1681** is already CLOSED; I deliberately did **not** reopen it
(a reopen is a scope decision for spec time, not a discovery-sweep cleanup), but I
flag its no-resolution-comment closure as a **provenance gap** the mission should
note. No new provable duplicate or provably-done OPEN ticket was found that warrants
a cleanup close — the OPEN tickets are all either fold-ins, genuine separate-mission
work, or live follow-ups. Conservatism applied per the brief.

---

## 5. Refined 3.2.1 scope recommendation

**The 4-ticket core slice STANDS** — #2000 (WP04), #1971 (WP03), #1993 (WP02), #1888 (WP01) are confirmed correct, cohesive, and parallelizable into ≥3 lanes. The
capstone's WP decomposition (WP01 verify-and-close → WP02 lanes-dir seam → WP03
project-root → WP04 routing+ratchet capstone) holds.

**Two adjustments (DIR-003 documented):**

1. **Promote #1900 from "fold only if trivial" to a confirmed WP04 rider.**
   *Rationale + evidence:* #1900's gating condition — "after coordination-merge-
   stabilization merges" — is **satisfied**: #1772 is CLOSED COMPLETED and epic
   #1796 (safe-commit/protected-branch coherence) is CLOSED. Its 3 deferred sites
   migrate to **exactly the seams WP04 already wires** —
   `surface_resolver.classify_worktree_topology` and `mission_branch_name_required`
   — and it is the **C-002 twin of #2000's C-003 ratchet drain**. Folding it in means
   WP04 drains *both* allow-lists in one enforcement capstone (the ratchet "shrinks
   this mission" goal applies to C-002 and C-003 together). It also closes debby's
   post-merge F-2 (aggregate.py vs status_transition.py husk disagreement) by
   construction. *Risk:* the `status_transition.py` predicate migration touches a
   coordination read module — keep it a tight, golden-parity rider, not a write-side
   expansion (honour the #1878 fence).

2. **Adopt #1681's Bucket A/B/C triage as the evidence/allow-list seed for WP03 +
   the new `parents[N]`/raw-path ratchet — without mechanically reopening it.**
   *Rationale + evidence:* #1681 enumerates the 225 raw `kitty-specs/<slug>`
   constructions, the legitimate canonical definers (Bucket A: `core/paths.py`,
   `core/constants.py`, `_read_path_resolver.py`, `execution_context.py`), and the
   migration-only exemptions (Bucket B). That triage **is** the allow-list the
   capstone's new ratchet needs — reusing it prevents WP03/WP04 from re-deriving the
   exemption set from scratch (which would risk sweeping in a legitimate join, per
   Pedro's trap #4). The capstone's `parents[N]` ratchet is the correct enforcement
   home for the still-open project-root tail; the raw-`kitty-specs/<slug>` tail is the
   #1797-sanitization sibling and can be a stretch rider on WP03 if it lands trivially,
   else explicitly deferred to #1797.

**The OUT-OF-SCOPE fence is reconfirmed and hardened** with the newly-surfaced
evidence:

- **#1878 write-side is a real, scoped, separate follow-on mission** — #1829 is its
  decision spine (drop local-main refusals, route via `BookkeepingTransaction`, with
  dashboard-scanner reader-alignment as prereq), with #1828/#1914/#1834/#1716/#1827/
  #1357/#1887 as its body. Only #1878 items #3/#5 (naming-resolver slice) touch this
  mission, via #2000/#1900. **Do not pull the write-side in.**
- **Legacy-cutover (#1057) and legacy-cleanup (#1058/#1059/#1060) are a distinct
  mission family** under #1797/#1932 — same "one authority, no legacy hot-path"
  spirit, different surface. Reference, don't fold.
- **Ownership policy (#1766/#1979/#1162) stays separate** from #1888's existence-check.
- **MC-layer (#1746 / #1738–#1745)**, **bulk-edit gate (#1791/#1930)**,
  **DRG/CP001 lints (#1923/#1927)**, and **display/UX (#1185/#1063)** are unrelated
  surfaces that merely co-occur on broad search terms.
- **#1832** (implement claim "no workspace resolved") and **#1834** are **verify-after**
  candidates — re-test #1832 once WP02 (#1993) lands; it is plausibly closeable then.

**Operational caveat for implementers (not a scope item):** #1907 — subagent
worktrees landing on stale ancestors + `pip install -e .` repointing the global
editable install — is a live hazard *while running this mission* on isolated lane
worktrees. Implementers must base ops on the current branch tip and restore the
editable install to the primary checkout (matches the standing
`feedback_subagent_profile_loading` / editable-install discipline). Flag in the
mission's research/ ops notes; do not add a WP for it.

**Net verdict:** the slice is **4 core tickets + 1 confirmed rider (#1900) + 1
evidence/ratchet seed (#1681)** — still one cohesive mission of ~4 WPs, no shadow
paths, byte-identical, advancing #1868 + #1619 and completing #1878 items #3/#5.
