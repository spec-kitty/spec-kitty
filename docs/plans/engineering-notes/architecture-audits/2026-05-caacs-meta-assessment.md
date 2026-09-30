---
title: 'CaaCS Meta-Assessment & Input for #666 Spike'
description: 'Reflective meta-assessment of the 2026-05 ad-hoc CaaCS run on spec-kitty: synthesis for adoption stakeholders (DM-C) and input to the #666 skill-design spike.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# CaaCS Meta-Assessment & Input for #666 Spike

> **Historical (May 2026 architecture-audit snapshot, 3.2.x cycle).** Kept as a record; issue states and milestones below are as of May 2026, and any reference to a 3.3 milestone is void (3.3.x was retired on 2026-08-23). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

> Reflective synthesis of the 2026-05 ad-hoc Code-as-a-Crime-Scene (CaaCS) run on spec-kitty.
> Audiences: (1) stakeholders weighing adoption (DM-C, see §6); (2) participants in the #666 brownfield-investigation skill design spike.

**Status:** synthesis complete; adoption decision (DM-C) pending. **See 2026-05-11 update below.**
**Author:** Planner Priti (ad-hoc planning session, 2026-05).
**Companion documents:**
- `docs/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — the audit (extended 2026-05-09 with `tests/` + `kitty-specs/` scope; extended 2026-05-11 with multi-window refactor-candidate synthesis)
- `docs/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — the original #822 backlog crosscheck (2026-05-08)
- `docs/plans/engineering-notes/architecture-audits/2026-05-phase3-issue-drafts-and-triage.md` — operational follow-ups
- `docs/plans/engineering-notes/architecture-audits/2026-05-phase3-f1-knowledge-capture-plan.md` — F1 remediation plan
- `docs/architecture/assessments/code-as-a-crime-scene-overview.md` — high-level explainer of the technique (added 2026-05-09)
- `docs/plans/engineering-notes/architecture-audits/2026-05-11-findings-vs-issues-update.md` — relating findings to #645, refreshed #822, and open bug tickets (added 2026-05-11)
**Doctrine references:** `tactic:forensic-repository-audit` (updated 2026-05-11 with a multi-window refactor-candidate step), `procedure:legacy-codebase-triage`, and the provisional `paradigm:brownfield-onboarding` (added 2026-05-11).

---

> ### 2026-05-11 update — the "zero STRONG matches" headline is no longer current
>
> Three days after this document was first written, two STRONG matches exist between the audit findings and the open issue backlog:
>
> | Audit finding | Matched ticket | What changed |
> |---|---|---|
> | **F2** (`cli/commands/agent/*` refactor target) + the new `brownfield-onboarding` paradigm | **#992** (new epic, opened 2026-05-05) — "centralize domain invariants" | The team has filed exactly the architectural epic F2 implies |
> | **F18** (`agent_utils/status.py` under-tested) | **#984** | One symptom (wrong-checkout reads from detached worktrees) is now filed |
>
> Eleven new bug tickets opened against `Priivacy-ai/spec-kitty` between 2026-05-05 and 2026-05-07 (#983–#992, #1009), most touching the F2 cluster. Release cuts `v3.2.0rc1` through `v3.2.0rc4` shipped in the same window; no stable tag yet. The 2026-05-11 multi-window refactor-candidate step surfaced two new slow-burn candidates: `orchestrator_api/commands.py` (no live issue — net-new forensic signal) and `agent_utils/status.py` (partially backed by #984 but no whole-scope ticket).
>
> **Implication for §6 (DM-C):** the shift from zero to two STRONG matches in three days *strengthens* — does not weaken — the adoption argument. The audit surfaced structural concerns the team independently filed within days. Where CaaCS looked first, the tracker followed. The case for CaaCS as an opt-in pre-investigation step (per §6) is empirically reinforced.
>
> Full detail: `docs/plans/engineering-notes/architecture-audits/2026-05-11-findings-vs-issues-update.md`. A companion document reading #992 and #984 in full with proposed audit-evidence comment text lives at `docs/plans/engineering-notes/architecture-audits/2026-05-11-issue-992-984-audit-comments.md`.
>
> The original §1 executive summary below is preserved as the time-of-writing record (2026-05-08). Read this update note as the live state.

---

## 1. Executive summary

This work was an ad-hoc Code-as-a-Crime-Scene (CaaCS) audit of spec-kitty, adapted from two Piechowski blog posts and rooted in Adam Tornhill's broader body of work. It was conducted as a **series of agent-orchestrated invocations** — explicitly *not* a spec-kitty mission — across four phases:

| Phase | What | Output |
|---|---|---|
| **0** Priming | Parallel research: CaaCS technique, issues #822 / #665 / #666, repo shape | Briefing into the planning conversation |
| **1** Doctrine extraction | PR-able doctrine artifacts | `forensic-repository-audit.tactic.yaml`, `legacy-codebase-triage.procedure.yaml`, DRG updates (commit `bc64dec6e`) |
| **2** Discovery run | Vanity-filtered forensic audit of all of `src/` (~757 files, 1y window) | `docs/architecture/audits/2026-05-spec-kitty-caacs.md` (commit `cd0052e97`); architect-ratified DDD column (`af2bbd0ee`) |
| **3** Synthesis | Crosscheck vs #822 + issue drafts + triage + F1 plan + this meta | `docs/architecture/audits/2026-05-822-crosscheck.md` (commit `e9610c964`) and the Phase 3 commit that adds this document |

**Top finding:** bus factor = 1; 89.5% of `src/` commits in the last year are single-author; 14 of 15 hotspots are >90% single-author. Pipeline trust is healthy (~0.3% reverts/hotfixes); velocity is accelerating. The unambiguous structural-remediation target is `cli/commands/agent/{tasks,workflow,mission}.py` — top of churn, top of bug-grep, top of complexity, densest temporal-coupling cluster.

**Most strategic finding:** **zero STRONG matches** between the audit's 14 catalogued findings (F1–F14) and the 16 currently-open sub-issues under #822. The audit and the issue tracker see *different worlds* — structural-forensic vs operational-release-readiness. Both legitimate; neither subsumes the other.

That zero-STRONG outcome is the answer to the latent question behind #665/#666: *does forensic auditing add value the issue tracker doesn't already capture?* Empirically, yes.

## 2. Methodology — phase-by-phase reflection

### Phase 0 — Priming

**What we did:** four parallel research subagents (CaaCS technique synthesis · #822 deep-dive · #665/#666 deep-dive · repo shape survey).

**What worked:** parallel dispatch was fast and produced independent ground truth. The repo-shape survey caught the eventual hotspots (agent/*, sync/*) before any forensic work began.

**What didn't:** the user's stated goal at session start ("primary goal is to progress on #822") was already mostly achieved before we started — most P0 blockers under #822 are closed, and the maintainer had already recommended cutting `3.2.0rc1`. Phase 0 caught this and corrected the priority calculus. **Lesson:** never start a remediation initiative without first confirming the target ticket is still active.

### Phase 1 — Doctrine extraction

**What we did:** architect (DM-A) decided artifact shape (tactic + procedure, reuse strategic-domain-classification for DDD overlay); curator authored the YAMLs and DRG updates.

**What worked:** the architect-then-curator handoff produced clean schema-compliant artifacts in one pass. The architect's discovery that `strategic-domain-classification` already existed reduced authoring scope by ~⅓. All eight proposed cross-link IDs verified to exist before authoring — zero dropped.

**What didn't:** minor — the architect proposed cross-links that the curator had to re-verify (low cost; expected pattern). The "limits-to-encode" requirement (six known biases) had to be wedged into different schema fields in tactic vs procedure (`failure_modes` vs `anti_patterns`); the curator handled this cleanly, but a unified schema field would be cleaner long-term.

### Phase 2 — Discovery run

**What we did:** scope = all of `src/` (per user DM-B); vanity filter spec; five core CaaCS recipes plus temporal coupling, bus factor, complexity overlay (radon), tentative DDD classification.

**What worked:** vanity filter caught the right things (lockfiles, `__pycache__/`, CHANGELOG). Bug-grep regex spot-checked at 4/5 true-positive rate — usable. Findings were concrete, prioritised, and actionable in one pass.

**What didn't:**
- The scope=`src/`-only constraint (a deliberate user call) limited temporal-coupling visibility into `kitty-specs/` ↔ `src/` couplings. A two-pass scope (focused for hotspots, broad for coupling) would have caught more.
- `cloc` was unavailable; SLOC came from `wc -l`. Slight over-count vs cloc but didn't change rankings.
- DDD classification was researcher-tentative until architect ratification (handled in Phase 3).

### Phase 3 — Synthesis

**What we did:** parallel architect-ratify + mapper-crosscheck; planner synthesis (issue drafts, backlog triage, F1 plan, this meta).

**What worked:** parallel dispatch again. Architect ratified 25/30 DDD rows unchanged; revised 5 with rationale (most notably elevating mission-templates from supporting to **core** — they *are* the SDD methodology contract). Mapper produced clean STRONG/PARTIAL/WEAK match counts that made the "two different worlds" conclusion impossible to miss.

**What didn't:** no structural failures. The 0-STRONG match finding required the most planner judgment — surfacing it as a strength of CaaCS rather than a failure of either CaaCS or #822 was the synthesis call.

## 3. Findings recap (compact)

| Finding | Severity | Backed by open issue? |
|---|---|---|
| F1 Bus factor = 1 across hotspots | 🔴 Critical | No |
| F2 `cli/commands/agent/{tasks,workflow,mission}.py` refactor target | 🔴 High | No |
| F3 Pipeline trust healthy | 🟢 Good news | n/a |
| F4 Project alive and accelerating | 🟢 Good news | n/a |
| F5 Three empty `src/` leftover dirs | 🟡 Hygiene | No |
| F6 Duplicate task-prompt-template smell | 🟡 Smell | No |
| F7–F14 | various | mostly No (3 PARTIAL, 7 WEAK matches in total) |

Full table and prose: `docs/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md`. Mapping detail: `docs/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md`.

## 4. Reflections on the approach

**The technique held up across the language gap.** The Piechowski posts are Rails-centric; spec-kitty is Python. The five core git recipes are language-agnostic and worked unchanged. Only the complexity overlay needed adapting (radon for Python instead of rubycritic for Ruby).

**The DDD overlay was a planner-extension to CaaCS, not native to it.** Doing it as a separate step (architect ratification post-hoc) preserved its independence. If we had baked it into the recipe, an architect's classification call would have been entangled with the researcher's quantitative data. Keeping them separate paid off.

**CaaCS's value is in what it surfaces that the issue tracker doesn't.** If every finding had STRONG matches with open issues, the audit would have been a redundant overlay. The 0-STRONG outcome is precisely what justifies the technique. This is worth restating because it inverts a naive interpretation: zero matches looks like "the audit failed to align with the backlog" but actually means "the audit caught what the backlog was missing."

**Bus factor was the dominant finding — and the kind of thing that hides in plain sight.** A long-running solo or near-solo project produces a knowledge-concentration risk that no operational ticket captures. Forensic methods make it visible. Spec-kitty's velocity has been *increasing* in 2026; that masks the bus-factor risk because nothing has gone wrong yet. CaaCS surfaces risk before it materializes.

**A limitation we hit:** CaaCS measures what *was* committed, not what *should have been*. Critical files with no churn and no bug fixes look healthy by every CaaCS metric — but their stability might be the calm before a storm, or true mature stability, and CaaCS can't tell. This is a known limitation of forensic-only methods and is a primary reason the qualitative #665 layer matters.

**Cost-of-run.** Roughly five subagent dispatches (priming research × 4, audit × 1, ratify × 1, crosscheck × 1, drafts × 1) plus planner synthesis. Total wall time across the session: ~half a day; total agent time: a few hours of compute. **For a project the size of spec-kitty, the signal-to-effort ratio is favorable.** A team-led version (without agents) would take 1–2 days; the agent-orchestrated version compressed it to a focused planning session.

## 5. Recommendations for further enhancement

When this technique is institutionalized (whether as a default workflow or as the foundation of #665/#666), consider these enhancements:

| # | Enhancement | Why |
|---|---|---|
| 1 | **Test-coverage overlay.** Layer test-coverage data on top of the complexity overlay so high-CC + low-coverage shows up as a distinct red flag. Radon can't see this; pytest-cov can. | F2 hotspots may or may not be tested; the audit can't currently say |
| 2 | **Two-pass scope affordance.** `--scope-hotspots <path>` plus `--scope-coupling <path>` so coupling can range broader than hotspots without diluting either signal. | Phase 2 hit this limit when scope=`src/` cut off `kitty-specs/`↔`src/` coupling |
| 3 | **Knowledge half-life.** Bus-factor without time-on-project normalization is biased toward earlier contributors. Add a "knowledge half-life" metric (decay-weighted authorship) | Single-author findings can mask "they wrote it 5 years ago and have moved on" vs "they wrote it 2 months ago" |
| 4 | **Fan-in coupling.** Hot AND high-fan-in is worse than hot AND low-fan-in. CaaCS doesn't measure fan-in natively — add it via import-graph analysis | Some F2-class hotspots might be self-contained; others ripple |
| 5 | **Commit-message hygiene preflight.** The bug-grep recipe is only as good as commit messages. A preflight check ("are commit messages structured enough that the recipe will work?") would prevent silent under-counting | Spec-kitty is fine here (Conventional Commits); other repos won't be |
| 6 | **Vanity-filter heuristic** beyond explicit excludes. Flag candidate vanity files automatically by insertions:deletions ratio and file-extension class | Manual exclusion list won't scale across many repos |

These all live in the future of `forensic-repository-audit.tactic.yaml`. Treat them as backlog for the doctrine artifact, not blockers for adoption.

## 6. Direct input for the #666 design spike

The brownfield-investigation skill (#665, designed in #666) and CaaCS (the doctrine just landed on this branch) should be **complementary, not competitive**. Here is what the #666 design spike should explicitly decide based on what this CaaCS run did and didn't accomplish.

### What the #666 skill SHOULD include

- **Phase 0: forensic-repository-audit as a primitive step.** Before the interview-driven investigation begins, the skill runs the forensic audit (or accepts an existing one as input). The hotspot list, bus-factor table, and temporal-coupling pairs become *targets* for the interview phase.
- **Hotspot-prioritized interview ordering.** Top-N hotspots get interviewed first. Bus-factor concentration is a priority signal: high single-author share means the SME interview is more time-critical.
- **Combined output structure.** Forensic table + interview narrative side-by-side, where interview answers explain forensic anomalies. *Why is this file high-churn but low-complexity?* *Why does this pair always change together?* *Why is this CC=160 function not refactored — what invariants does it carry?*
- **Inferred-vs-validated marking** (already in #665's acceptance criteria) extended to forensic findings: "the audit measured X; SME interview confirmed/contradicted X; resolved interpretation is Y."
- **Knowledge-capture artifact format** matching what the F1 knowledge-capture plan (companion document) will produce manually. Treat that plan's outputs (`agent-commands/README.md` and the per-module briefs) as a reference set the skill should be able to reproduce automatically.

### What the #666 skill SHOULD NOT do

- **Do not replace `forensic-repository-audit`.** That tactic is a primitive; the skill is a workflow. Keep them composable. A reviewer should be able to run the tactic alone for a quick read; the skill is for full-depth investigations.
- **Do not interview-derive what git data already shows.** Don't ask the SME "which files change most?" when `git log` answers that in 50ms.
- **Do not conflate "what the code does" with "what the team thinks it should do."** Both are needed; both should remain distinct in the output bundle. The audit measures the former; interviews measure the latter; the gap between them is where most strategic insight lives.
- **Do not pre-empt structural decisions.** The skill produces a *reference bundle*; it does not propose refactors. Refactor recommendations come from a downstream planner step (the F1 knowledge-capture plan demonstrates this separation manually).

### A concrete test for the design spike

When the future skill runs against spec-kitty's `feat/caacs-doctrine` branch (or its successor on main), it should produce:

- A hotspot table that subsumes F1–F14
- Interview-derived insight on each hotspot (what F1–F14 *don't* answer: why the code is shaped this way, what implicit invariants exist, what should and shouldn't be refactored)
- A combined output that a non-author can read and understand the codebase from

If the skill's output is a strict superset of what this CaaCS run + the F1 knowledge-capture plan produce manually, the design is on track. If it produces less, the spike has identified a missing capability.

### What this run did NOT prove about #665/#666

This run is a **single data point**, on one Python codebase, by one organization. It does not prove the technique generalizes to:

- Polyglot repos (multiple-language complexity overlays would need work)
- Repos with weak commit-message hygiene (bug-grep would underperform)
- Repos with squash-merge as default (bus-factor would distort)
- Brand-new repos (no history to mine)

The #666 spike should consider these axes when deciding whether the skill ships as a default workflow vs an opt-in surface.

## 7. Decision Moments — open and resolved

| ID | Question | Status | Resolution |
|---|---|---|---|
| **DM-A** | CaaCS doctrine artifact shape | Resolved (2026-05-08) | Tactic + procedure + reuse `strategic-domain-classification`. Architect Alphonso |
| **DM-B** | Forensic-run scope | Resolved | All of `src/`. User decision |
| **DM-D** | Structural-remediation priority given bus factor = 1 | Resolved | Document/transfer first, then refactor. User decision; constrains F1 knowledge-capture plan |
| **DM-C** | Adopt CaaCS as default · opt-in skill · merged into #666 | **Open** | Recommendation pending Phase 4 |

DM-C is what the next step of this engagement should resolve. The recommendation forming based on this run: **do not adopt as a default gate; do adopt as an opt-in skill** that is the **first phase** of the #665/#666 workflow when that workflow lands. Until #665 lands, the doctrine artifacts (tactic + procedure) plus this run's audit-template format are sufficient guidance for any contributor who wants to do this manually.

That recommendation is for Phase 4 to ratify; this document only frames the question.

## 8. Provenance

- Branch: `feat/caacs-doctrine`
- Commits this work introduced (in order):
  - `bc64dec6e` doctrine artifacts
  - `cd0052e97` audit findings
  - `af2bbd0ee` architect DDD ratification
  - `e9610c964` #822 crosscheck
  - (this commit) Phase 3 synthesis
- Subagents dispatched: 7 (4 priming · 1 architect DM-A · 1 curator · 1 researcher discovery · 1 architect ratify · 1 mapper · 1 issue-drafts)
- Time-on-task (planner-perceived): one focused planning session, half-day equivalent.
