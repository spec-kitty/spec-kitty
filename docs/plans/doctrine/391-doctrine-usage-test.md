---
title: '#391 Doctrine Usage Test (WP11 dogfood)'
description: 'The #391 doctrine-usage dogfood test (WP11) for the doctrine-glossary-architecture-consolidation mission, exercising FR-012 and success criteria SC-1/SC-6.'
doc_status: deprecated
updated: '2026-09-28'
---
# #391 Doctrine Usage Test (WP11 dogfood)

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

Mission: `doctrine-glossary-architecture-consolidation-01KTNWFC` — FR-012, SC-1/SC-6.
Date: 2026-06-11. Operator: curator-carla. Tracker: `Priivacy-ai/spec-kitty`.

This record is the usage-test of the doctrine authored in WP04/WP05 — the
[tracker-organisation-workflow procedure](../../../packs/internal/procedures/tracker-organisation-workflow.procedure.yaml),
the [planning-and-tracking styleguide](../../../packs/built-in/styleguides/planning-and-tracking.styleguide.yaml),
the [github-tracker toolguide](../../../packs/built-in/toolguides/GITHUB_TRACKER.md),
the [iterative-deepening-review](../../../packs/internal/tactics/tracker-backlog-iterative-deepening.tactic.yaml)
and [moscow-scoping-lens](../../../packs/built-in/tactics/moscow-scoping-lens.tactic.yaml) tactics,
and the planning-and-tracking glossary subset — applied to the real #391 epic
using **only** that doctrine as the method.

## Amendment note (authoritative)

The WP body on disk and spec SC-6 originally said "close #391 as superseded".
Per operator decision **2026-06-11**, this is amended: **#391 STAYS OPEN**. The
test organises #391's *current* state per the doctrine. Honest
"already-organized" findings are valid SC-1 evidence — the point of the dogfood
is whether the doctrine alone suffices to assess and act on a real epic, not to
force a destructive close.

## Headline verdict

- **SC-1 (doctrine sufficient to organise the tracker end-to-end using only the
  authored artefacts): PASS.** Every step of the procedure was executable from
  the doctrine text alone. The toolguide's gh/GraphQL mechanics and gotchas were
  not merely correct but *predictive* — two of its named traps fired exactly as
  documented during this run (see "Doctrine sufficiency"). No recourse to ad-hoc
  notes was needed.
- **SC-6 (as amended): PASS.** #391 was assessed and organised per the doctrine
  and left OPEN by operator decision. Its tree topology was already clean
  (no orphans, no closed-parent stranding, no meta-tracker-as-parent, no
  catch-all, no duplicates in the open set); the doctrine's **hygiene
  invariants** (procedure Step 8 / styleguide principle 9) surfaced real,
  actionable gaps that were fixed live.

## Inventory (procedure Step 1)

`#391 EPIC: Tech/Functional Debt Remediation` — OPEN, type `Feature`, single
priority `priority:P1`, no parent (it is a root epic). Body carries a
Purpose/Scope narrative and **no child-ticket checklist** — already compliant
with the styleguide's "epic body carries Purpose/Scope, never a list of child
numbers" principle.

76 native sub-issues total; **22 open** (54 closed). One open child, **#1797**
("Epic: 3.2.0 codebase sanitization"), is itself a functional sub-epic with 11
open leaves — a coherent `root → bucket → leaves` tier, exactly the shape the
styleguide prescribes.

Open direct children of #391 (18): 644, 454, 1231, 1347, 1149, 582, 631, 442,
572, 825, 1008, 1790, 1791, 1634, 1815, 1834, 1838, 1842, plus the sub-epic
**#1797**.

Open leaves under #1797 (11): 614, 1060, 1624, 1057, 1622, 1358, 1058, 955,
1059, 719, 1623.

## Root classification (procedure Step 2)

| Root | Class | Rationale |
|------|-------|-----------|
| #391 | **Functional epic** | Real domain of work (cross-cutting tech-debt remediation); owns tickets as native sub-issues; not a release/go-no-go gate. NOT a meta-tracker. |
| #1797 | **Functional sub-epic (bucket)** | Coherent sub-class (codebase sanitization / dead-code / LOC reduction) under #391; owns its own leaves. |

Note: #391 is part of the canonical 2026-06-09 tree and is **off-limits to
mutation except to file work into it** (per the binding brief). It was not closed, not
reparented, not retyped.

## Steps 3–7 (drain / re-slice / sweep / orphan-clusters / dedup)

- **Step 3 (drain closed epics, collapse passthroughs, relabel meta-trackers):**
  No open child sits under a closed/superseded parent — every open ticket
  resolves directly to #391 or to the live #1797. No one-child passthrough tier.
  No meta-tracker among the parents (#391 and #1797 are both functional).
  **No action required** — honest already-clean finding.
- **Step 4 (re-slice catch-all roots):** #391 is not a flat catch-all — it has a
  Purpose/Scope body and one functional sub-epic bucket (#1797). The open direct
  children are a coherent tech-debt set (intake bugs, bulk-edit gate gaps,
  CI/test hygiene, orchestration hardening). No re-slice required. **No action.**
- **Step 5 (keyword + scope-read sweep, backfill links, flag overlaps):** All
  parent links are native sub-issues (verified via GraphQL `parent`, not body
  checklists). No invisible-checklist-only children to backfill. No
  cross-epic overlap requiring a single-owner decision in the open set. **No action.**
- **Step 6 (orphan clusters → reuse/create epics):** Zero genuine orphans in the
  open set — every open ticket has a functional parent. No ≥4-orphan cluster to
  home. **No new epic created** (correctly avoids the "fork a near-duplicate
  epic" anti-pattern). **No action.**
- **Step 7 (duplicate resolution with community-precedence):** No duplicate
  pairs in the open set. Author-association was sampled via the toolguide's REST
  `.author_association` path (the field is rejected by `gh issue view --json`,
  confirming the toolguide note). **No close performed; no community ticket touched.**

## Step 8 — hygiene invariants (where the real work was)

The topology was clean; the doctrine's **per-ticket hygiene invariants** are
where #391 had drifted. Audited every open leaf for: resolves-to-functional-epic
(all pass), single canonical priority, an issue type, and `bug label ↔ type Bug`.

### Mutations executed (issue numbers)

Issue type derived **objectively** from the conventional-commit prefix and
existing labels (procedure Step 8 / styleguide "Issue type mirrors the bug label"):

| Issue | Was | Set to | Objective signal |
|-------|-----|--------|------------------|
| #719  | (none) | **Task** | `test(intake):` conv-commit prefix |
| #1622 | (none) | **Task** | `[DIRECTIVE_013]` dead-symbol cleanup (refactor) |
| #1623 | (none) | **Task** | `[DIRECTIVE_013]` doctor.py helper extraction (refactor) |
| #1624 | (none) | **Task** | `[DIRECTIVE_013]` provenance-sidecar typing (refactor) |
| #582  | (none) | **Feature** | `enhancement` label → capability work |
| #631  | (none) | **Task** | documentation workaround task |

Priority (triage judgement) — the procedure prescribes "assign a provisional
default and flag it rather than silently guessing". Provisional `priority:P2`
applied and flagged for triage on the priority-missing leaves:

| Issue | Action |
|-------|--------|
| #1815 | added provisional `priority:P2` (flag for triage) |
| #1834 | added provisional `priority:P2` (flag for triage) |
| #1838 | added provisional `priority:P2` (flag for triage) |
| #1842 | added provisional `priority:P2` (flag for triage) |
| #1791 | added provisional `priority:P2` (flag for triage) |

`bug label ↔ type Bug`: all bug-labelled open tickets (644, 1149, 1790, 1634,
1058, 1842) are already typed Bug, and no Bug-typed ticket lacks the label.
**No mutation needed** — invariant already held.

### Proposals deferred (not executed)

- **#1797 mistyped `Task` but carries the `epic` label** → styleguide says
  "epics are typed Feature". A retype to Feature is the correct fix, but #1797 is
  a **canonical-tree node** the brief forbids mutating. **Proposal:** retype
  #1797 `Task → Feature` and add a `priority:P*` label (it currently has none) —
  to be actioned by whoever owns the canonical tree, not in this WP.
- **#1791 left type-missing.** Title ("add regression test for coord-topology
  fix; path heuristic misses .jsonl") is genuinely ambiguous between **Bug**
  (the path heuristic is a defect) and **Task** (adding a regression test). The
  procedure says derive type *objectively*; with no conventional-commit prefix
  and no kind label, an objective call cannot be made. **Proposal:** owner to
  confirm Bug vs Task. Recorded rather than guessed (anti-pattern avoidance).

## Step 9 — clean-bill re-walk

Post-mutation re-walk of all 29 open leaves (18 direct + 11 under #1797):

- Orphans: **0**. Meta-rooted: **0**. Under-closed-parent: **0**.
- Priority anomalies (missing / dual / legacy `Px-description`): **0** among
  the leaves actioned. (Legacy `Px-description` labels were not present on the
  open set; the residual `p1:verified` / `p1-decision:*` labels are a separate
  triage-snapshot scheme — see doctrine sufficiency below.)
- Type-missing: **1** — only **#1791**, deliberately left as a flagged proposal.

The only deliberately-unresolved item carries a named decision (owner confirms
type), satisfying Step 9's "remaining items should be only roots plus a
deliberately-parked item with a named owner".

## Doctrine sufficiency assessment (SC-1)

**The doctrine was sufficient.** Every procedure step mapped cleanly onto the
live epic and was executable from the artefact text with no improvisation. Two
specific strengths and three concrete gaps:

### Validated as predictive (strengths)

1. **zsh word-splitting trap (toolguide "bash heredocs for loops").** The first
   batched parent-lookup loop, written in the default zsh shell, passed the
   entire `$OPEN` id-string as a single GraphQL `Int!` value and errored
   (`Could not coerce value … to Int`). Re-running the identical loop inside a
   `bash <<'EOF'` heredoc fixed it immediately. The toolguide predicted this
   exactly.
2. **`author_association` field rejection (toolguide "Handy one-call queries").**
   `gh issue view --json authorAssociation` was rejected with "Unknown JSON
   field"; the toolguide's prescribed REST `.author_association` path worked.
   The toolguide saved the dedup step from a dead end.

The `--paginate` mandate (76 children, well over the 30-item default page) and
the GraphQL-`parent`-vs-REST-`parent` distinction were both load-bearing and
correct on this epic.

### Concrete gaps (fed back to WP04/WP05)

1. **No guidance for a residual / legacy *triage-snapshot* label scheme.** #391's
   children carry `p1:verified`, `p1-decision:keep|close-if-stale|split|defer` —
   a prior triage pass's bespoke labels. The styleguide retires the legacy
   `Px-description` labels and defines the canonical `priority:Px` + `triage:*`
   namespaces, but is **silent on what to do with a *different* legacy decision
   namespace** like `p1-decision:*`. Are these to be migrated into `triage:*`,
   kept as an audit snapshot, or deleted? **Suggestion:** add a styleguide
   pattern "Reconcile or retire bespoke triage-snapshot labels" — either map
   `p1-decision:close-if-stale` → `triage:stale`, `p1-decision:defer` →
   `future`, and drop `p1:verified`; or explicitly bless them as an immutable
   audit snapshot. Without this, a reviewer cannot answer the styleguide's own
   quality-test cleanly for these tickets.
2. **No "do not mutate protected / canonical-tree nodes" carve-out.** The
   procedure's hygiene-invariant step (Step 8) would have me retype #1797
   `Task → Feature`, but #1797 is a governed canonical-tree node that this WP is
   forbidden to touch. The doctrine has no concept of a node that is *correctly
   classified-as-off-limits* — the agent must import that boundary externally.
   **Suggestion:** add an entry/exit note to the procedure: "Some roots/buckets
   may be under change-control; record the prescribed fix as a proposal for the
   tree owner rather than executing it." (This is exactly what happened here.)
3. **Provisional-priority default value is unspecified.** Step 8 says "assign a
   provisional default and flag it" but never names the default. I chose
   `priority:P2` (mid-scale) as the least-surprising default and flagged each.
   **Suggestion:** the styleguide should name the canonical provisional default
   (e.g. `priority:P2` + a `triage:*` marker) so two operators converge instead
   of each picking their own mid-value.

None of these gaps blocked the run; all were absorbable by recording a proposal,
which is itself the doctrine working as designed (procedure: "Where the doctrine
is insufficient, that is a finding for the record, not something to silently
patch around").

## Summary of live mutations

- Type set (objective): #719, #1622, #1623, #1624 → Task; #582 → Feature; #631 → Task.
- Provisional priority `priority:P2` (flagged): #1815, #1834, #1838, #1842, #1791.
- **#391 not closed, not reparented, not retyped** (operator decision + canonical-tree protection).
- Deferred proposals: #1797 retype/priority (canonical-tree owner); #1791 type (owner confirms Bug vs Task).
