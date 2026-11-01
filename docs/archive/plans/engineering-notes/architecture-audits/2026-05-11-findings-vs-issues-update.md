---
title: '2026-05-11 — findings vs issues (#645, #822 refresh, open bugs)'
description: '2026-05-11 refresh cross-checking the CaaCS audit findings against open issues (#645, #822) and adding two new slow-burn refactor candidates surfaced by the pass.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# 2026-05-11 — findings vs issues (#645, #822 refresh, open bugs)

> **Historical (May 2026 architecture-audit snapshot, 3.2.x cycle).** Kept as a record; issue states and milestones below are as of May 2026, and any reference to a 3.3 milestone is void (3.3.x was retired on 2026-08-23). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../../plans/4-0-0-milestone-roadmap.md).

## Inputs

- **Audit referenced**: `docs/architecture/audits/2026-05-spec-kitty-caacs.md` (commit `bc64dec6ee37dbbd6bc21a0a1aa3195f2bab1b57`, 2026-05-08).
- **Prior crosscheck**: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` (dated 2026-05-08).
- **Multi-window refresh (2026-05-11)** introduced two new slow-burn refactor candidates: `src/specify_cli/orchestrator_api/commands.py` (1097 SLOC, F#28 full-history, R#24 4-mo) and `src/specify_cli/agent_utils/status.py` (570 SLOC, F#29 full-history, R#26 4-mo, contains the `_display_status_board` F-53 renderer).
- **Provisional doctrine paradigm**: `brownfield-onboarding` (investigate before changing; document/transfer first; hierarchical reference bundles).
- **Issue tracker reads** (all via `gh` against `Priivacy-ai/spec-kitty`, 2026-05-11):
  - `gh issue view 645 --comments --json …`
  - `gh issue view 822 --comments --json …`
  - `gh api repos/Priivacy-ai/spec-kitty/issues/822/comments --paginate` (since-filter for `created_at >= 2026-05-08`)
  - `gh issue list --label bug --state open --limit 100 --json …`
  - body fetches for every open bug-labeled ticket (`#1009, #992, #988, #989, #990, #991, #983, #984, #985, #986, #987, #971, #889, #822, #662, #644, #391`)
  - searches: `orchestrator_api`, `agent_utils/status`, `glossary middleware`
  - `gh release list --limit 15` (release-tag progression)
  - `gh issue view 613` (glossary ownership)

---

## Section 1: Issue #645

**Title**: *Epic: Stable Application API Surface (UI / CLI / MCP / SDK)*
**State**: OPEN
**Labels**: `dashboard`, `epic`
**Author**: stijn-dejongh
**Created**: 2026-04-15 — Updated: 2026-05-04

### Body summary (≤200 words)

Issue 645 is a multi-step architectural epic (rescoped 2026-05-03 from "Frontend Decoupling and Application API Platform" to "Stable Application API Surface") aimed at giving Spec Kitty a single, documented, stable retrieval surface that the dashboard UI, CLI, future MCP adapter, and future external SDKs all consume — instead of each independently walking the filesystem under `kitty-specs/*/`. The current proof points cited as the problem are stdlib server bootstrap, hand-rolled routing, dashboard-local TypedDict response contracts, and monolithic frontend controller logic — all dashboard-package internal. The epic sequences nine steps: (0) codify single-entry-point doctrine + architectural tests, (1–4) terminology, handler-to-service extraction, contract hardening, transport migration (all now DONE on `feature/650-dashboard-ui-ux-overhaul`), (5) stable retrieval surface via MissionRegistry+cache (#956, DONE), (6) resource-oriented endpoints + `WorkPackageAssignment` schema (#957/#958, DONE in mission `01KQQRF2`), (7) glossary/lint service-extraction follow-ups (#954/#955), (8) async update transport (WebSocket/SSE), (9) generated clients and new consumer slices. HATEOAS-LITE `_links` convention is in scope. Out of scope: visual redesign (#650), public docs site (#651), DRG/doctrine refactors not tied to access layers.

### Linked work

| Reference | State (2026-05-11) | Role in epic |
|---|---|---|
| #459 .d.ts codegen | CLOSED | Folded into FastAPI mission |
| #460 FastAPI/OpenAPI migration | CLOSED | Done — mission `frontend-api-fastapi-openapi-migration-01KQN2JA` |
| #447 weighted progress | CLOSED | Done |
| #537 WPState/Lane consumer migration | CLOSED | Done — mission 080 |
| #538 status emission / dirty worktree | OPEN | Partial; Mode B hardening + dirty-worktree recovery remain |
| #391 cross-cutting remediation umbrella | OPEN | Parent debt epic |
| #956 MissionRegistry + cache | DONE (in mission `01KQPDBB`) |
| #957 resource-oriented endpoints + `WorkPackageAssignment` | DONE (mission `01KQQRF2`) |
| #958 OpenAPI tag grouping | DONE (folded into 957's mission) |
| #954 / #955 glossary & lint service extraction | OPEN follow-ups |
| #650 UI/UX shared design system | OPEN sibling epic |
| #361 historical predecessor | CLOSED |

### Specific code paths referenced

- `src/specify_cli/dashboard/server.py:61` (legacy stdlib server, retained for rollback)
- `src/specify_cli/dashboard/handlers/router.py:14` (hand-rolled router)
- `src/specify_cli/dashboard/api_types.py:1` (TypedDicts — Phase 1)
- `src/specify_cli/dashboard/static/dashboard/dashboard.js:1` (monolithic frontend)
- `src/dashboard/` (new canonical service package: `services/mission_scan.py`, `services/project_state.py`, `services/sync.py`, `file_reader.py`)
- `src/dashboard/api/` (FastAPI subpackage with 12 routers)
- `src/charter/context.py`, `src/charter/sync.py` (charter chokepoint, upstream dependency of #460)
- `tests/architectural/test_dashboard_boundary.py` (FR-010 invariant guard)
- `tests/architectural/test_fastapi_handler_purity.py` (≤6-LOC handler bodies)

### Relationship to findings

| Finding | Strength | Reason |
|---|---|---|
| F1 (Bus factor=1) | **NONE** | The epic is purely architectural; it does not address single-author concentration. |
| F2 (`cli/commands/agent/{tasks,workflow,mission}.py`) | **NONE** | The epic is dashboard/application-API-shaped. The F2 hotspot is the orchestration command layer, untouched by #645. |
| F15 (test-update lag on F2 hotspots) | **NONE** | Same scope mismatch as F2. |
| F16 (`glossary/middleware.py` under-tested) | **WEAK** | Step 7 (#954) extracts glossary handler from dashboard transport; this could surface but does not target `middleware.py`. |
| F17 (mission↔src/ co-change limited) | **NONE** | Structural pipeline observation, not addressed. |
| F18 (`agent_utils/status.py` under-tested) | **PARTIAL** | The epic's MissionRegistry (#956) and `WorkPackageAssignment` schema (#957) create a canonical materialization layer that `agent_utils/status.py` should eventually consume; if executed, it would naturally reduce that file's filesystem-walking footprint and make its renderer thinner. Not a direct target, but in the structural path. |
| orchestrator_api/commands.py slow-burn | **WEAK** | The epic explicitly says "do not overload the orchestrator API with product/application concerns" — orthogonal-by-design. |
| Brownfield-onboarding paradigm | **PARTIAL** | The epic's Step 0 explicitly "codifies doctrine + architectural tests" before refactoring further, which is the brownfield "document first, refactor second" pattern. Also: `docs/architecture/05_ownership_map.md` updates are part of each merged mission. The doctrine layer is exactly where brownfield-onboarding would land. |

**Overall**: #645 is a strong-execution architectural epic, but its scope only weakly overlaps the audit's structural-remediation findings. It is also visibly close to **done** — Steps 1–6 have shipped, Steps 7–9 are the remainder.

---

## Section 2: Issue #822 — delta since 2026-05-08 crosscheck

**Title**: *Epic: 3.2.0 stabilization and release readiness*
**State**: OPEN (unchanged)
**Labels**: `bug`, `workflow`, `release`, `epic` (unchanged)

### New comments since 2026-05-08

**Zero new comments on the epic body itself.** The last visible comment is dated 2026-05-05 (the final-gate rerun + mission hygiene comment from robertDouglass). Both `gh issue view 822 --comments` and the paginated `gh api .../issues/822/comments` query produced no entries with `created_at >= 2026-05-08`.

### Sub-issue state changes since 2026-05-08

Comparing the prior crosscheck's table against the current open-bug list:

| # | Prior state (2026-05-08) | Current state (2026-05-11) | Delta |
|---|---|---|---|
| #967 | CLOSED | CLOSED | — |
| #966 | CLOSED | CLOSED | — |
| #964 | CLOSED | CLOSED | — |
| #968 | CLOSED | CLOSED | — |
| #904 | CLOSED | CLOSED | — |
| #848 | CLOSED | CLOSED | — |
| #971 mypy strict | OPEN | OPEN | — |
| #889 sync misclassification | OPEN | OPEN | — |
| #952 SaaS sync leak | reopened then closed at read | not in current open list | confirmed closed |
| #662, #825, #595, #771, #631, #630, #726, #728, #729, #629, #644, #740, #323, #306, #260, #253, #303, #317 | all OPEN | #662 and #644 confirmed still OPEN in current bug query; the rest are still OPEN (no closure event seen) | no change |
| **NEW since prior crosscheck**: #983, #984, #985, #986, #987, #988, #989, #990, #991, #992, #1009 | not present | all OPEN | **+11 new open bug tickets** |

The largest delta is the **opening of 11 new bug-labeled issues** between 2026-05-05 and 2026-05-07, most of them surfaced during mission `auth-local-trust-and-multi-process-hardening-01KQW587` and `stable-320-release-blocker-cleanup-01KQW4DF`. Notably, **#992 ("Epic: drain the bug queue by repairing domain boundaries")** was opened 2026-05-05 and is itself an architectural meta-epic — it diagnoses the same kind of structural seam problem the audit identified (commands independently inferring/mutating the same truth), though from a different angle (lifecycle invariants rather than file-level complexity).

### Release-tag progression

| Tag | Date | Type |
|---|---|---|
| v3.2.0a10 | 2026-05-04 | prerelease |
| **v3.2.0rc1** | **2026-05-05** | prerelease |
| **v3.2.0rc2** | **2026-05-06** | prerelease |
| **v3.2.0rc3** | **2026-05-06** | prerelease |
| **v3.2.0rc4** | **2026-05-10** | prerelease |
| v3.1.8 | 2026-04-29 | Latest stable |

**rc1, rc2, rc3, and rc4 have all cut since 2026-05-05.** The epic narrative has not been updated to reflect the rc progression — the epic body still anchors on "3.2.0a10" status. rc4 is the most recent and is dated yesterday (2026-05-10). Stable 3.2.0 has not been tagged. The fact that four rc tags have shipped in ~5 days while the epic body has not been updated is itself a signal: either the rc bar is moving (each rc triggered by newly-discovered blockers from the 11 newly-opened bugs) or the epic is no longer the live coordination surface for the release.

### Does the prior picture still hold?

Mostly yes, with one important shift:

- The audit's framing — that #822's blocker tranche maps to mission-flow correctness issues and not to the structural F2 hotspot — remains correct.
- **However**, #992 (opened 2026-05-05) materially changes the picture. It is an explicit epic to repair domain boundaries across the same command surfaces the audit identified as F2 (`spec-kitty next`, `agent action implement/review`, `agent tasks move-task`, `agent tasks status`, `review`, `merge --dry-run`, `merge`, dashboard materializers, SaaS sync). It is the first issue-tracker artifact that names the F2 structural concern as the root cause of a bug cluster rather than as individual bugs. The audit's F2 finding now has an issue-tracker analog, just not one that's filed under #822.

---

## Section 3: Open "bug"-labeled issues — relating table

Open bug-labeled issues as of 2026-05-11 (17 total, including the two epics that carry the `bug` label):

| # | Title (short) | Age (days) | F1 | F2 | F15 | F16 | F18 | orch_api | Brownfield | Strongest match |
|---|---|---:|---|---|---|---|---|---|---|---|
| 1009 | profile-invocation lifecycle records do not match issued step id | 4 | NONE | PARTIAL | NONE | NONE | NONE | NONE | NONE | **F2 PARTIAL** |
| 992 | Epic: drain bug queue by repairing domain boundaries | 6 | WEAK | **STRONG** | PARTIAL | NONE | PARTIAL | PARTIAL | **STRONG** | **F2 STRONG + Brownfield STRONG** |
| 991 | merge dry-run misses review artifact consistency failures | 6 | NONE | PARTIAL | NONE | NONE | NONE | NONE | NONE | **F2 PARTIAL** |
| 990 | review-cycle artifact generation can wrap prior cycle frontmatter/body | 6 | NONE | PARTIAL | NONE | NONE | NONE | NONE | NONE | **F2 PARTIAL** |
| 989 | new missions without baseline_merge_commit skip dead-code review | 6 | NONE | PARTIAL | NONE | NONE | NONE | NONE | NONE | **F2 PARTIAL** |
| 988 | `spec-kitty next --json` can miss claimable WPs | 6 | NONE | PARTIAL | NONE | NONE | NONE | PARTIAL | NONE | **F2 PARTIAL** |
| 987 | mission-review gate commands can fall through to global pytest in fresh clones | 6 | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| 986 | contract and architectural gates race on shared pytest cache venv | 6 | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| 985 | `spec-kitty review` does not enforce mission-review hard-gate artifacts | 6 | NONE | PARTIAL | NONE | NONE | NONE | NONE | NONE | **F2 PARTIAL** |
| 984 | `agent tasks status` can resolve wrong checkout from detached worktree | 6 | NONE | **PARTIAL** | NONE | NONE | **STRONG** | NONE | NONE | **F18 STRONG** |
| 983 | merge is not idempotent after partial mission-number assignment | 6 | NONE | PARTIAL | NONE | NONE | NONE | NONE | NONE | **F2 PARTIAL** |
| 971 | mypy strict gate fails on current baseline | 7 | NONE | WEAK | NONE | NONE | NONE | NONE | NONE | NONE |
| 889 | sync misclassifies teamspace ingress rejection as server_error | 11 | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| 822 | Epic: 3.2.0 stabilization (carries `bug` label) | 14 | NONE | WEAK | NONE | NONE | NONE | NONE | WEAK | WEAK |
| 662 | CI workflow duplication | 25 | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| 644 | Encoding mixups: stop assuming UTF-8 | 26 | NONE | NONE | NONE | NONE | NONE | NONE | WEAK | WEAK |
| 391 | EPIC: 3.x tech/functional debt remediation (carries `bug` label) | 36 | WEAK | PARTIAL | NONE | PARTIAL | NONE | NONE | **PARTIAL** | **Brownfield PARTIAL** |

### Per-issue notes for PARTIAL/STRONG matches

- **#1009** — Lifecycle record write keyed off wrong identifier. Likely sits in or around `src/specify_cli/next/runtime_bridge.py` / lifecycle persistence (probably the `next` action emission seam). Adjacent to the F2 hotspot via the `next`/action-dispatch wiring.
- **#992** — Direct topical hit on F2. The body enumerates exactly the command surfaces the audit named (`tasks`, `workflow`, `mission`, `review`, `merge`, dashboard, sync) and proposes the same remedy (centralize invariants, route every surface through them). Also resonates with brownfield-onboarding: its "North Star Invariants" section is the kind of doctrine artifact the new paradigm would prescribe.
- **#991** — Merge dry-run/real-merge parity failure. Sits on the `merge` command surface, part of F2's `cli/commands/agent/` cluster.
- **#990** — Review-cycle artifact generation bug. Lives in review command path; F2-adjacent.
- **#989** — Review command skip-path bug (missing `baseline_merge_commit`). F2-adjacent.
- **#988** — `next --json` claimability parity with `agent action implement`. Two surfaces independently inferring claimability — classic F2 symptom.
- **#985** — `spec-kitty review` not enforcing mission-review artifacts. F2-adjacent (review command surface).
- **#984** — `agent tasks status` reads from wrong checkout. **STRONG match on F18** — this is the under-tested `agent_utils/status.py` (570 SLOC, F#29) failing precisely on a status-board reading invariant. Also PARTIAL on F2 (the bug surface is `cli/commands/agent/tasks.py`).
- **#983** — `merge` non-idempotent after partial mission-number assignment. F2-adjacent (merge command).
- **#391** — Generic tech-debt umbrella epic. Has a partial match on the orchestrator_api / domain-boundary work via its child #613 ("Establish glossary as a clearly owned functional module") and #645's chain of dashboard service extractions. Brownfield-onboarding resonates with #391's intent.
- **#644** — Encoding policy. Brownfield-adjacent only in the sense that it asks for explicit contracts at lifecycle boundaries (a brownfield-onboarding hallmark).

### Notes on the WEAK/NONE rows

- **#987, #986** — Test infrastructure / fresh-clone hygiene. Orthogonal to the audit's structural findings.
- **#971** — mypy strict. Crosses many files but does not target any specific F-finding.
- **#889** — SaaS sync error classification. Cross-repo concern (SaaS service), orthogonal.
- **#662** — CI duplication, infrastructural.

---

## Section 4: Gap analysis

### Open bug tickets that STRONGLY match the new audit findings

- **#992** (STRONG on F2 + Brownfield): The team has already filed an architectural epic that names the F2 structural concern as the root cause of a bug cluster. The audit's F2 finding and #992 converge on the same diagnosis: **multiple command surfaces independently owning the same truth**. #992's proposed remedy (centralize invariants, single-execution per domain) is the issue-tracker form of an F2 refactor. This is a strong confirmation that the audit is in agreement with the team's own structural read of the codebase. Importantly, #992 is **not listed in #822's linked-work table** — it is a sibling/successor epic, opened after the prior crosscheck.
- **#984** (STRONG on F18): The audit's F18 (`agent_utils/status.py` under-tested at 19.0% ratio) has a concrete bug repro at `#984` — the very file the audit flagged as under-tested is producing wrong-checkout reads from detached worktrees. This is direct forensic backing for F18.

### The two new slow-burn candidates — issue-tracker status

| Slow-burn candidate | Direct open bug tickets | Architectural tickets |
|---|---|---|
| `src/specify_cli/orchestrator_api/commands.py` (1097 SLOC, F#28) | **None.** No open issue names this file. | Historical: #177 (CLOSED, "read commands mutate status.json; JSON-envelope contract inconsistencies") — closed but the file remains a slow-burn refactor candidate per the multi-window analysis. #391 (OPEN umbrella) touches orchestrator API concerns indirectly. |
| `src/specify_cli/agent_utils/status.py` (570 SLOC, F#29, contains F-53 `_display_status_board`) | **#984** (STRONG, see above). | None named directly. |

**Net-new vs filed:**

- `orchestrator_api/commands.py` is **net-new**. No live issue tracks it; the only historical reference (#177) is closed.
- `agent_utils/status.py` has **partial issue-tracker backing** via #984, but only on one symptom (wrong-checkout reads). The full slow-burn picture (complexity, churn, the F-53 renderer that's hard to test) is not filed.

### Bug tickets without forensic backing

The audit did **not** examine the following bug clusters, and they appear legitimate as orthogonal scope:

- **#987, #986** — pytest/venv infrastructure hygiene. Test-infra concerns the audit explicitly did not have a `tests/` overlay for.
- **#971** — mypy strict gate. Tooling/quality gate work, separate from forensics.
- **#889** — SaaS sync error classification. Cross-repo concern; the audit is single-repo.
- **#662** — CI workflow duplication. Infrastructural.
- **#644** — Encoding policy. Cross-cutting product correctness; audit is structural.

These are not contradicted by the audit; they are simply outside the scope of the file-level / churn-based forensic lens.

### Newly-opened bug cluster (post-prior-crosscheck) and its shape

The 11 new open bugs (#983–#992, #1009) split into two clusters:

1. **F2 cluster** (8 of 11): #983, #984, #985, #988, #989, #990, #991, #992, #1009 — all touch the `cli/commands/agent/{tasks,workflow,mission}.py` complex or its lifecycle dependencies (`next`, `review`, `merge`). This is a strong post-hoc validation of F2 and F15. The "test-update lag" claim from F15 is consistent with so many lifecycle-correctness bugs shipping in the rc-cycle window.
2. **Test-infra cluster** (2 of 11): #986, #987 — orthogonal to the audit.

---

## Section 5: Methodology / caveats

### Issues fetched successfully

- #645 (full body + comments)
- #822 (full body + comments, plus paginated comment API)
- All 17 open bug-labeled issues (bodies for the 16 relevant + the two epics that carry the `bug` label)
- #613 (glossary ownership, referenced from F16)

### Issues NOT fetched

- Sub-issues of #822 explicitly closed in earlier crosscheck (#967, #966, #964, #968, #904, #848) — relying on the prior crosscheck's record that they were closed; no re-verification done here.
- Historical orchestrator_api ticket #177 — closed, body not deep-read (title alone was sufficient signal).
- Older deferred items in #822 (#306, #303, #317, #260, #253, etc.) — relying on prior crosscheck's per-issue scoring; no rescoring done here as the prior crosscheck remains canonical.

### State changes during the read

None observed. `gh` returned consistent state across the read window (a few minutes on 2026-05-11). One minor note: the `gh issue list --label bug --state open` count of 17 includes both the #822 and #391 epics (because they carry the `bug` label); these are excluded from per-issue forensic scoring but included in the table for completeness.

### Limits

- **The `bug` label filter is not exhaustive.** Issues like #538 (status emission), #954, #955 (service extraction follow-ups), #771 (auto-rebase), and #613 (glossary ownership) carry other labels and would not surface via the bug filter — but they are visible inside #645 and #822 linkage and are referenced in this document.
- **No PR-level scan** was performed for in-flight work that might already address some of these. The audit references are file-level structural; the issue-tracker view is symptom-level. Where these two views agree (e.g., #992 ↔ F2; #984 ↔ F18), the agreement is high-confidence.
- **The four rc tags (rc1-rc4) in 5 days** suggest the release coordination surface for 3.2.0 stable may have moved off #822 and onto release-PR conversations. This research did not enumerate those PRs.
- **No subjective product-priority judgment** was applied: STRONG/PARTIAL/WEAK ratings reflect topical/structural overlap with the audit findings, not whether the team should prioritize the matched ticket.
