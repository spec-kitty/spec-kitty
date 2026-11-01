---
title: F1 Knowledge-Capture Plan
description: 'Proposed knowledge-capture plan anchored in CaaCS Finding F1 (bus factor of 1 across src/ hotspots), honoring DM-D: document and transfer before refactoring.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# F1 Knowledge-Capture Plan

> **Historical (May 2026 architecture-audit snapshot, 3.2.x cycle).** Kept as a record; issue states and milestones below are as of May 2026, and any reference to a 3.3 milestone is void (3.3.x was retired on 2026-08-23). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../../plans/4-0-0-milestone-roadmap.md).

> Anchored in the CaaCS audit's Finding F1 (bus factor = 1 across 14/15 src/ hotspots).
> Honors decision moment **DM-D**: *document/transfer first, then refactor*.

**Status:** proposed plan, no work scheduled yet.
**Author:** Planner Priti (ad-hoc planning session, 2026-05).
**Doctrine references:**
- `directive:DIRECTIVE_003` (decision documentation)
- `tactic:forensic-repository-audit` (the audit that surfaced F1)
- `procedure:legacy-codebase-triage` (the workflow this plan extends)
**Issue references:** future issue tracking F1 (drafted in companion document); pre-emptive bridge to #665/#666 brownfield-investigation skill.

---

## 1. Problem statement

The 2026-05 CaaCS audit measured 1001 commits to `src/` over the last year. **89.5% are single-author.** Of the top-15 hotspots, 14 are >90% single-author. The concentration is most acute in:

| File | Last-year commits (src/-touched) | Single-author share | Architect DDD |
|---|---|---|---|
| `src/specify_cli/cli/commands/agent/tasks.py` | top of churn list | ≥90% | core (per architect ratification) |
| `src/specify_cli/cli/commands/agent/workflow.py` | top of churn list | ≥90% | core |
| `src/specify_cli/cli/commands/agent/mission.py` | top of churn list | ≥90% | core |

These three files also hold five of the seven worst-complexity functions in the project (`finalize_tasks` CC=160, `move_task` CC=139, `status` CC=87, `review` CC=84, `map_requirements` CC=74). They are the unambiguous structural-remediation target. **Refactoring them blind would risk breaking implicit invariants that exist only in the SME's head.**

This plan exists to make those invariants legible *before* anyone touches the code structurally. It is the prerequisite knowledge-transfer workstream for any future agent/* refactor.

## 2. Constraints (DM-D applied)

| Constraint | Source | Implication |
|---|---|---|
| Document/transfer **first** | DM-D resolution | No structural-refactor work begins until KC-WP1–3 land |
| Knowledge-capture artifacts must be durable | DIRECTIVE_003 | Markdown in `architecture/`, committed, reviewed, refresh model declared |
| Out of scope: the refactor itself | This plan's boundary | A separate plan owns refactor sequencing once KC artifacts exist |
| Out of scope: replacement of #665/#666 | Phase 1 doctrine out-of-scope clause | This plan is *bridge work* for what #665 will eventually automate |

## 3. Sequenced work packages

### KC-WP1 — Living architecture brief for `src/specify_cli/cli/commands/agent/`

| Field | Value |
|---|---|
| **Goal** | A non-author can read the brief and predict each public function's behavior within ±20% |
| **Inputs** | `agent/tasks.py`, `agent/workflow.py`, `agent/mission.py`, the audit hotspot table, recent fix commits referencing each file |
| **Output** | `architecture/agent-commands/README.md` (top-level map) + one module brief per file (`tasks.md`, `workflow.md`, `mission.md`) — each containing: purpose · public surface · invariants · common bugs (from git history) · testing notes · "do not refactor without understanding X" warnings |
| **Owner** | SME (robertDouglass) drafts; one second-eye reviewer ratifies |
| **Effort** | 2–3 days SME + 1 day reviewer |
| **Exit criteria** | Reviewer can independently lead a code-review session on each file using only the brief; no critical invariant flagged as missing |
| **Risks** | SME bandwidth; brief-decay if no refresh cadence declared |

### KC-WP2 — Pair sessions on top-5 worst-complexity functions

| Field | Value |
|---|---|
| **Goal** | Distribute mental model of the highest-risk functions to ≥1 navigator per function |
| **Targets** | `finalize_tasks` (CC=160), `move_task` (CC=139), `status` (CC=87), `review` (CC=84), `map_requirements` (CC=74) |
| **Format** | 1–2h pair session per function, recorded as a brief in `architecture/agent-commands/pairing-notes/<function-name>.md`. Driver = SME, navigator rotates |
| **Owner** | SME (driver) + 1–2 navigators rotating |
| **Effort** | 5 sessions × 2h × 2 people ≈ 20 person-hours |
| **Exit criteria** | Each navigator can independently walk through one function in a future review without SME present |
| **Dependencies** | KC-WP1 should be drafted first so sessions reference the brief, not improvise |

### KC-WP3 — Test-gap audit for agent/* hotspots

| Field | Value |
|---|---|
| **Goal** | Surface invariants encoded only in implementation, not in tests |
| **Inputs** | Existing tests for the three files; complexity overlay from the audit; KC-WP2 pairing notes |
| **Output** | `architecture/agent-commands/test-gaps.md` — gap list: which CC>30 functions lack adequate coverage, which invariants are tribal, which tests are missing edge cases identified during pairing |
| **Owner** | A navigator from KC-WP2 |
| **Effort** | 1–2 days |
| **Exit criteria** | Every CC>30 function in agent/* either has a test or has a documented "untested invariant" entry with rationale |
| **Dependencies** | KC-WP2 partially complete (pairing notes inform the gap audit) |

### KC-WP4 — F6 duplicate-template investigation

| Field | Value |
|---|---|
| **Goal** | Resolve the 15-co-edits/year duplicate-template smell |
| **Inputs** | `missions/software-dev/templates/task-prompt-template.md` and `templates/task-prompt-template.md` history |
| **Output** | A short investigation note answering: are these intentionally divergent or accidental drift? If drift, a remediation plan |
| **Owner** | Anyone with a few hours |
| **Effort** | 0.5 day |
| **Exit criteria** | Question answered. If "drift," a follow-up issue tracking remediation; if "intentional," a comment in both files explaining why |
| **Dependencies** | None |

### Out of scope for this plan

- **The agent/* refactor itself.** A separate "Refactor readiness" plan picks up after KC-WP1–3 land.
- **Replacing #665/#666.** This plan is the manual version of what the brownfield-investigation skill is meant to automate. Treat the artifacts produced here as a ground-truth reference set for evaluating that future skill (see meta-assessment companion doc).
- **Documenting all of `src/`.** Scope is bounded to agent/* hotspots. Doctrine and charter packages are stable per the audit and don't need this treatment.

## 4. Eisenhower matrix

| Quadrant | Items |
|---|---|
| Q1 (urgent + important) | *none* — nothing here gates 3.2.0 rc1 |
| Q2 (important not urgent) | KC-WP1, KC-WP2, KC-WP3 |
| Q3 (urgent not important) | KC-WP4 (small, fits in slack time) |
| Q4 (delete) | — |

## 5. Risk register

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| KR-1 | SME has no bandwidth → plan stalls | HIGH | Cap each WP at the smallest useful slice; KC-WP1 alone is valuable even without WP2/3 |
| KR-2 | Pair sessions produce thin notes (drive-by capture) | MED | Exit criterion for KC-WP2 is "navigator can lead review independently" — forces depth |
| KR-3 | Brief-decay (artifacts go stale silently) | MED | Declare ownership + refresh cadence in KC-WP1's README front-matter (e.g., re-review every minor release) |
| KR-4 | Knowledge capture used as procrastination instead of refactor | LOW | Time-box the whole plan to ≤1 week elapsed (≤25 person-hours); refactor plan starts as soon as exit criteria are met |

## 6. Connection to #665 / #666

This plan is the **manual prototype** of the brownfield-investigation workflow that #665 proposes and #666 will design.

- KC-WP1's brief format is exactly the kind of artifact the skill should produce automatically once it exists.
- KC-WP2's pairing-notes format is the qualitative interview output #665 envisions.
- KC-WP3's test-gap audit overlay is what an integrated skill could compute by combining forensic data with conversation transcripts.

Recommendation: when #666 design spike begins, reference these artifacts (once produced) as the **ground-truth reference set**. The proposed skill design should be evaluated against the question: *would this skill, run against `src/specify_cli/cli/commands/agent/`, produce artifacts comparable to what KC-WP1–3 produce manually?*

If yes, the design is on track. If not, identify what the skill is missing.

## 7. Open follow-ups

- Decide ownership and refresh cadence for the brief artifacts (proposed: monthly review during 3.2.x stabilization, quarterly thereafter).
- Decide whether KC-WP4 graduates to a #822 sub-issue or stays in this plan as a self-contained chore.
- Decide whether the refactor-readiness plan (post this plan) is a spec-kitty mission or stays ad-hoc.
- Re-evaluate after KC-WP1 lands: did the manual brief reveal anything that should change the audit's findings? If yes, amend the audit.
