---
title: '#2007 training-bug ticket mapping & sequencing impact — planner-priti'
description: "Planner Priti's ticket mapping and sequencing-impact analysis for the #2007 training bugs, with live-verified issue states and milestones (2026-06-16)."
doc_status: deprecated
updated: '2026-06-16'
---
# #2007 training-bug ticket mapping & sequencing impact — planner-priti

**Date:** 2026-06-16 · **Author:** planner-priti (read-only research op; no tracker mutation) ·
**Source:** `gh issue view 2007` + per-candidate `gh issue view` (states/milestones verified live).
**Decision context:** `docs/release-goals/3.2.x.md`, the neutral panel
`docs/archive/plans/engineering-notes/3-2-x-goal-corroboration/SCORING-SYNTHESIS.md`, and the in-flight naming rider
`kitty-specs/naming-identity-routing-rider-01KV7SFD/` (branch `feat/naming-rider-3-2-1`).

Issue #2007 itself: **OPEN**, labels `bug` + `epic` + `3.2.0`, **milestone = none** (the `3.2.0` *label* is
a category tag, not the milestone — the epic is currently unmilestoned). Evidence = Robert's screenshots
2026-06-16 09:47–12:05 against a fresh `spec-kitty-monorepo-prep` workspace + Debugger Debbie read-only
investigations. No screenshots uploaded; the failure inventory in the body is the artifact.

---

## 1. The 16 bugs → existing-ticket-or-NEW map

Verified states/milestones (live `gh`, 2026-06-16). "Milestone" = GitHub milestone field, not the label.

| # | Bug (short) | Existing ticket | Ticket state | In 3.2.x milestone? | Disposition |
|---|-------------|-----------------|--------------|---------------------|-------------|
| 1 | `doctrine list` command drift; skills/prompts imply nonexistent surface | **NEW** | — | — | net-new (command-surface class) |
| 2 | Charter stale/status loop; `status --json` traceback; `sync` noop-while-stale; `entity_pages` DRG warning | **NEW** (related: #1336 *charter --json on error*, **CLOSED**) | #1336 CLOSED | no | net-new; #1336 is a prior partial in the same family, not a dup |
| 3 | Specify `NO_BRIEF`/`NO_TICKET` bootstrap ambiguity | **NEW** | — | — | net-new (UX/typed-state) |
| 4 | `setup-plan` requires `--mission` while prompt/docs say no-flag | **NEW** | — | — | net-new (resolver/contract) |
| 5 | `agent context resolve` requires `--action` (undocumented) | **NEW** | — | — | net-new (resolver/contract + doc drift) |
| 6 | Submodule/`.git`-file root misresolution → `SPEC_KITTY_REPO_NOT_INITIALIZED` | **NEW** | — | — | net-new (root detection) |
| 7 | `spec_committed:false` while committed — checks wrong branch authority; `SpecifyCompleted` gated wrong | **NEW** | — | — | net-new (read-path authority) |
| 8 | `decision open` rejects valid mission handle (`path would escape kitty-specs/`) | **NEW** | — | — | net-new (read-path authority) |
| 9 | Raw `python -c "from specify_cli.core.templates"` fails (out-of-venv + wrong import path) | **NEW** | — | — | net-new (prompt-hygiene/guard) |
| 10 | `finalize-tasks --validate-only` exit 1 on zero-match globs; future-file vs glob semantics unclear | **NEW** (adjacent: #1888 ownership existence-check, in rider) | #1888 OPEN | yes | net-new; *distinct* from #1888 (this is glob/warn-vs-error semantics, not phantom-path existence) |
| 11 | `finalize-tasks` from coord worktree reads planning inputs from wrong surface (`meta.json`/`spec.md` not found) | **NEW** | — | — | net-new (read-path authority) |
| 12 | Explicit `--mission` error flattened into generic "pass --mission" remediation | **NEW** | — | — | net-new (error-fidelity) |
| 13 | Broken coord worktree recovery; docs reference nonexistent `agent worktree repair` | **#1890** | **OPEN** | **no** | **existing** — exact match |
| 14 | `STATUS_READ_PATH_NOT_FOUND` for valid mission; coord topology exists, no primary fallback | **NEW** (zone of #1832/#1716/#1619) | #1832 OPEN / #1716 OPEN | #1832 no / #1716 no | net-new symptom of the read-path/coord-topology class |
| 15 | `next` hides real failure — query mode discards preflight, reclassifies read-path miss as `MISSION_NOT_FOUND` | **NEW** | — | — | net-new (read-path/error-fidelity) |
| 16 | `implement` command surface mismatch — `--json` on internal allocator, rejected by `agent action implement` | **#1891** (residual: "action implement rejects --json") | **OPEN** | **no** | **existing** — #1891 already names this exact residual |

### Net-new vs existing count

- **Existing tickets:** **2** of 16 — **#1890** (bug 13) and **#1891** (bug 16, the documented residual).
- **Adjacent-but-distinct existing tickets** (same family, do NOT collapse): **#1888** (bug 10 is a
  *different* finalize defect than #1888's phantom-path existence check); **#1832/#1716/#1619**
  (bug 14 is a *symptom* of that read-path/coord class, not a 1:1 dup); **#1336** (CLOSED — prior
  charter-`--json`-on-error partial, related to bug 2).
- **Net-new (no ticket exists):** **14** of 16 — bugs 1–12 (minus the #1890/#1891/#1888/#1832 overlaps
  noted), 14, 15. Concretely the genuinely-uncovered ones needing new sub-issues: **1, 2, 3, 4, 5, 6,
  7, 8, 9, 10, 11, 12, 14, 15**.

---

## 2. The 16 → 6 suggested sub-issue clusters

The epic body proposes 6 sub-issues. Mapping each bug to its cluster:

| Cluster | Bugs | Net-new? | Existing-ticket touchpoints |
|---------|------|----------|------------------------------|
| **C1 — Command-surface validation & docs/prompt drift** | 1, 5, 9, 16 | mostly new | bug 16 = **#1891** residual |
| **C2 — Charter status/sync/preflight consistency** | 2 | new | related CLOSED **#1336** |
| **C3 — Mission context / read-path resolver unification** | 4, 7, 8, 11, 12, 14, 15 (+ bug 5 has a resolver tail) | new | zone of **#1832 / #1716 / #1619** (unmilestoned) |
| **C4 — Coordination worktree repair surface** | 13 | existing | **#1890** (exact) |
| **C5 — Implement/review action JSON contract** | 16 | existing | **#1891** (exact residual) |
| **C6 — Submodule / root detection hardening** | 6 | new | — |
| *(loose)* **Specify bootstrap UX** | 3 | new | — fits C1 (prompt/typed-state) or stands alone |
| *(loose)* **Ownership/finalize glob semantics** | 10 | new | distinct from **#1888**; fits C3 or stands alone |

**C3 is the centre of mass** — 7 of 16 bugs (4, 7, 8, 11, 12, 14, 15) are the *same* "wrong mission-state
authority resolved, then typed failure flattened" defect the epic's Architectural Diagnosis #2 names. This
is precisely the read-path/single-resolution surface the neutral panel ranked **first** for 3.2.1
(`#1832 → #1716`), now corroborated by live training evidence.

### Overlaps with the naming rider (`feat/naming-rider-3-2-1`)

The rider's spec (read directly) addresses **#2000, #1971-tail, #1888** and *explicitly defers* the
read-path/coord class to 3.2.2. Cross-referencing #2007:

- **#1888** — bug 10 is *adjacent* to the rider's #1888 work but is a **different finalize defect**
  (zero-match-glob warn-vs-error semantics vs the rider's phantom-path *existence check*, FR-007). The
  rider's #1888 fix does **not** close bug 10. **One overlap, partial.**
- **#1832 / #1716 / #1619** — the rider **lists these out-of-scope (C-005), deferred to 3.2.2.** Bug 14
  (and the C3 cluster) lands squarely in that deferred zone. **Overlap = by-deferral, not by-coverage.**
- **#1891** — the rider lists #1891 residual as out-of-scope (C-005). Bug 16 = that residual. **Overlap
  by-deferral.**
- **#1890** — **not** in the rider at all. Net-new to the rider's scope.

Net: the naming rider **touches #2007 only at the #1888 surface (and that only partially)**. Everything
else in #2007 is either net-new or sits in the zone the rider deliberately pushed to 3.2.2. **The rider
does not close #2007; #2007 does not block the rider.**

---

## 3. The decision question — does #2007 change the 3.2.1 lead?

### What the prior decision was

The neutral panel (all three scorers) leaned **impact-first**: open the write-side/single-resolution
surface via **#1832 → #1716**, demote naming to a parallel rider. The **operator overrode** to
**safety-first** — naming rider as the 3.2.1 opener — recorded explicitly as a *values choice, not a data
verdict*, trading "lowest-risk momentum + establish the ratchet/routing pattern" against "frees no P0/P1,
parks the highest-blast-radius surface."

### What #2007 adds

Issue #2007 is **live training evidence** (a real operator workflow run) that the **command-drift + read-path
authority class** — the exact surface the panel wanted to lead with — is **causing observable workflow
failures right now**, including at least one **launch-blocker-class** symptom (see §4). 7 of 16 bugs are
the C3 read-path/resolver-flattening defect; 4 more are command-surface drift. This is no longer a
predicted ROI; it is reproduced field failure on a fresh workspace.

Critically, #2007 evidence arrived **after** the safety-first call. The panel's de-bias note already
conceded "leading with naming forfeits impact, the safety is available *inside* the impact plan (because #1832 is the safest first WP)." Issue #2007 strengthens the impact side of that exact trade-off with empirical weight the panel did not have.

### Options assessed

| Option | What it means | Trade-off |
|--------|---------------|-----------|
| **(i)** Rider as-is, #2007 → 3.2.2 | No change; #2007 becomes the 3.2.2 headline | Cleanest, preserves the in-flight rider's momentum. **Cost:** ships a stabilization patch (3.2.1) that does *not* touch the class actively breaking the operator's own training run; the launch-blocker-class bug 14/13 waits a full patch. |
| **(ii)** Rider stays, bounded #2007 slice joins 3.2.1 | Rider proceeds; carve a small, safe #2007 sub-slice (e.g. C4 #1890 repair-command + C1 command-surface CI guard + bug-12 error-fidelity) into the same patch | Keeps the safe opener AND lands the cheapest, highest-confidence #2007 wins. **Cost:** modest scope-creep on 3.2.1; needs a clean WP boundary so it doesn't entangle with the rider's byte-parity work. C4/#1890 and the command-snippet CI guard are genuinely independent of the rider's seam routing. |
| **(iii)** #2007 becomes the 3.2.1 lead; rider yields/parallels | Promote the C3 read-path resolver unification (= the panel's #1832→#1716 lead) to the headline; rider runs parallel or slips | Aligns 3.2.1 with both the neutral panel's original lean AND the new field evidence. **Cost:** higher characterization-test cost + semantics risk (exactly what safety-first was avoiding); discards in-flight rider momentum; re-opens a decision the operator already made deliberately. |

### Recommendation — **(ii), trending toward (iii) for 3.2.2**

**Keep the naming rider as the 3.2.1 opener (honor the operator's deliberate safety-first call — it is
already in flight, severable, and the panel confirmed its safety is real), BUT fold a bounded, low-risk #2007 slice into 3.2.1: #1890 (C4 worktree-repair command — net-new, independent, fixes a recovery dead
end Robert hit) and the C1 command-surface CI guard (bug 1/5/9 — a regression *tripwire*, the same
pattern-establishing move the rider's ratchet already embodies, so it fits the safety-first thesis
perfectly). Then make #2007's C3 read-path resolver unification the explicit 3.2.2 headline — which is
also the panel's original #1832 → #1716 lead, now field-proven.**

Rationale, tracker-grounded:
- The C3 resolver class (7/16 bugs) **is** the deferred 3.2.2 zone the rider already names (#1832/#1716/
  #1619, C-005). #2007 does not create new sequencing — it **raises the priority and evidence weight of
  the work already slated for 3.2.2**, and supplies the characterization corpus (Robert's reproduced
  paths) that 3.2.2 needed anyway.
- #2007 does **not** change the 3.2.1 *lead* (naming rider stays) because reversing an in-flight,
  deliberate, severable values-call on fresh-but-not-emergency evidence costs more momentum than it
  buys — and #2007's safe subset (C4 #1890 + the C1 guard) can ride along *without* reversing anything.
- It **does** change 3.2.2: #2007 should become the **named headline** of 3.2.2, absorbing the panel's
  #1832→#1716 lead, with the 6 sub-issues opened as its children and milestoned onto 3.2.x.

### Tracker hygiene this surfaces (do regardless)

Both the panel and this analysis confirm the **milestone inversion persists**: #1716, #1832, #1827, #1891, #1619/#1666, **and #1890** are all **unmilestoned**, while only #2000/#1971/#1993/#1900/#1888 sit
on 3.2.x. #2007 itself is unmilestoned. Milestone #2007 + its read-path children onto 3.2.x so the
burndown reflects the real cycle. (Recommendation only — this op is read-only.)

---

## 4. Launch-blocker flags

The epic body does **not** carry the `launch-blocker` label itself, but the framing ("3.2.0 training
bugs that Robert witnessed", fresh-workspace evidence, "Proposed Epic Acceptance Criteria" gating a
training run) is launch-readiness evidence. Bug-level blocker assessment:

- **Bug 6 (submodule/root misresolution → `SPEC_KITTY_REPO_NOT_INITIALIZED`)** — **launch-blocker-class.**
  In a submodule-style checkout (a real consumer topology, e.g. `econcept-next` monorepo prep) Spec Kitty
  is *unusable* — it resolves to the parent repo and refuses to initialize. Hard stop, no workaround
  short of restructuring the consumer repo.
- **Bug 14 (`STATUS_READ_PATH_NOT_FOUND` + `agent action implement` same miss)** — **launch-blocker-class
  by association.** It is the read-path symptom of **#1716**, which carries the explicit
  **`launch-blocker`** label (verified). The implement path failing closed with no fallback blocks the
  core implement loop on coord topologies.
- **Bug 13 (#1890 broken coord-worktree recovery, points at nonexistent command)** — **high-severity, not
  strictly blocking:** there is a real (if undocumented) recovery via `doctor workspaces --fix`; the
  defect is that agents are steered into manual recursive deletion. Recovery-surface trap, not a hard
  stop.
- **#1716 itself** carries `launch-blocker` (verified label). The C3 cluster is its read-side
  manifestation, so the **whole C3 read-path class inherits launch-blocker weight** — reinforcing the
  §3 recommendation to headline it in 3.2.2 rather than let it drift.

Everything else (charter loops, doc drift, error-fidelity, JSON contract) is workflow-friction /
confidence-eroding but has agent-survivable workarounds — important for a clean training run, not a
hard launch gate.
