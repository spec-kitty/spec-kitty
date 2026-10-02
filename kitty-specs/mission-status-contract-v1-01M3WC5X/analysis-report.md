---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: mission-status-contract-v1-01M3WC5X
mission_id: 01M3WC5XGBJ0DZ91CP66BWB7PS
generated_at: '2026-10-02T10:49:07.073922+00:00'
analyzer_agent: claude:sonnet
input_artifacts:
  spec.md:
    path: kitty-specs/mission-status-contract-v1-01M3WC5X/spec.md
    sha256: aec77c3284640ff5fe2fe5812c23454b3acbcb5fec84b2a3d2a5b954b2b4fb81
  plan.md:
    path: kitty-specs/mission-status-contract-v1-01M3WC5X/plan.md
    sha256: ff43cc2a2f3a0fed8879a4fa224487d8e38ea04d0e69fa194068c0a2d1967a43
  tasks.md:
    path: kitty-specs/mission-status-contract-v1-01M3WC5X/tasks.md
    sha256: dc1e3f22b2d097a85402fe90350c1796e6add73448aab7cb94141cf6deaaaf1c
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 69c63e91ae27a02b0c07b48939f72198b0d2654ed5bee42e3d6bc1d5d4e71a6e
verdict: blocked
issue_counts:
  low: 2
  critical: 0
  high: 2
  medium: 5
  info: 0
findings:
- id: A1
  severity: high
  category: inconsistency
  summary: Normative text still says ONE PR (spec.md CL-1, C-001, SC-010; plan.md summary, section 445, branch contract 571; tracer-approach.md; WP01 PR-shape bullet; WP02 pre-step; WP12 PR bullets), contradicting the binding six-stacked-PR ruling of 2026-10-02.
- id: A2
  severity: high
  category: inconsistency
  summary: contracts.yml is specified with pull_request branches [main] (contracts/tools-and-workflows.md, WP02, DD-7, plan), so it never runs on stacked PRs 2 to 6 whose base is the previous PR branch; the CI-only JVM feedback, P1 and the SC-003/SC-006 evidence cannot be produced there.
- id: A3
  severity: medium
  category: underspecification
  summary: History-rewriting steps (rebase, compact-history, tag re-publication) are written for one branch; no per-seam branch cut, bottom-up compaction or rebase-onto rule for six stacked branches.
- id: A4
  severity: medium
  category: underspecification
  summary: PR-body evidence (SC-010 five-section body, known-red baseline, DEV-1/DEV-2 confirmation, SC-008 diff assertions, NFR-001, SC-006, quickstart paste items, WP12 close-out.md as the PR body backer) is not assigned per PR.
- id: A5
  severity: medium
  category: inconsistency
  summary: Preview points p0/p1/p2 are defined against "the draft PR" and commits, not seam heads; they happen to align with PR2 end, PR4 and PR5 but this is unstated, and partial points and re-publication causes are not mapped to the stack.
- id: A6
  severity: medium
  category: underspecification
  summary: Draft-until-ack gating, merge order, base retargeting and the ready-for-squad label rules are not stated for a stack of six (CL-1, C-001 require onto main; operator/maintainer merges, orchestrator never merges is unrecorded).
- id: A7
  severity: medium
  category: coverage
  summary: tracer-design-decisions.md has no decision record (next is DD-21) for the six-stacked-PR ruling; tracer-approach.md Log and WP12 tracer assessment also do not mention it.
- id: A8
  severity: low
  category: inconsistency
  summary: plan.md "eleven work packages" (line 445) vs 12 WPs in wps.yaml/tasks.md (IC-10 split into WP11 and WP12); ten concerns, eleven with IC-07 split.
- id: A9
  severity: low
  category: underspecification
  summary: Orchestrator-written planning records (research.md R-3/R-9 record step, baseline) are committed on the planning surface before WP03/WP06/WP08 and thus land in an early seam PR; WP12 owns research.md and close-out.md in the last PR. Which PR carries which kitty-specs records is unstated.
---

## Specification Analysis Report

Mission: mission-status-contract-v1-01M3WC5X. Artifacts read: charter, spec.md, plan.md, tasks.md (generated from wps.yaml), wps.yaml, tasks/WP01..WP12, data-model.md, contracts/tools-and-workflows.md, research.md, quickstart.md, tracer-*.md. Read-only analysis; no state-writing command run.

### Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | HIGH | spec.md CL-1 ("The single Mission PR"), C-001 ("One PR for the Mission ... onto main"), SC-010 ("The PR is a draft"), Out-of-scope/Assumptions line 594, spec.md header para line 32; plan.md line 12 ("through one pull request"), line 124 item 6, line 388 E-3, line 445 ("One PR for the whole Mission"), line 571; tracer-approach.md line 58 ("One PR") and "UI early-start point"; tasks/WP01 "PR shape" bullet (recommends single PR, split "on these six seams" as optional); tasks/WP02 "Orchestrator pre-step" ("opens the DRAFT pull request ... if the orchestrator decided to split"); tasks/WP08 line 92 ("the draft PR at this WP's own push"); tasks/WP09 lines 222 and 239; tasks/WP12 "One PR for the Mission" and "PR size and reviewability" bullets, T075 | The binding ruling is six stacked seam PRs (WP01+02; WP03-05; WP06+07; WP08+09; WP10; WP11+12), all draft until ack on #5528, orchestrator never merges. Text states one PR and treats the split as an optional recommendation. | Reword CL-1/C-001/SC-010 (note supersession by the 2026-10-02 ruling, citing DD-21), plan summary/branch contract, WP01 and WP12 bullets (make the six seams binding, delete "recommendation only"), WP02 pre-step (opens PR 1; PR 2..6 opened at their seam end), WP08/WP09 "the draft PR" -> "this seam's draft PR". Keep wps.yaml unchanged (seams already follow WP boundaries). |
| A2 | Inconsistency | HIGH | contracts/tools-and-workflows.md line 52; tasks/WP02 line 99 ("`pull_request` and `push` with `branches: [main]`"); tracer-design-decisions.md DD-7; plan.md workflow-shape text; tasks/WP09 guard test (asserts triggers); tasks/WP08 line 92; plan.md P1 definition | contracts.yml `pull_request` has `branches: [main]`, so on stacked PRs 2-6 (base = previous PR head branch) it does not run. ci-router.yml has no branches filter on pull_request, so only contracts.yml is affected. Evidence for PR 4 (lint, breaking-change, release-dry-run, negative-tests, P1 green, SC-003 class A, SC-006) and WP09 guard test depend on that run; workflow_dispatch resolves from the default branch and cannot substitute. | Decide and record: drop `branches` from the `pull_request` trigger (keep `branches: [main]` on `push`), update the DD-7 text, tools-and-workflows.md, WP02 shape bullet and the WP09 trigger guard; OR require each stacked PR to target `main` (cumulative diff), which defeats the stack. Also check the fork guard/fleet-verdict inventory expectations still hold. |
| A3 | Underspecification | MEDIUM | plan.md line 124 item 6 and E-3; WP01 "Orchestrator pre-step"; WP12 F-3 pre-PR step; tracer-approach UI point | Rebase onto main and the compact-history step are written once for one branch. With six stacked branches a rewrite of a lower seam orphans every upper PR; no rule for bottom-up compaction then `rebase --onto`, nor which seam head is the branch name each PR uses. WP01 says the split is "cheapest to decide before WP03" but it is now decided. | Add a stack-maintenance paragraph (plan + WP01 pre-step): cut seam branches at WP02, WP05, WP07, WP09, WP10, WP12 heads; compact lowest first, rebase upper seams onto the rewritten head, force-with-lease only; each rewrite triggers `compact history` re-publication of any published preview tag at or below that seam. |
| A4 | Underspecification | MEDIUM | spec.md SC-010, SC-008, SC-006, NFR-001/NFR-007 evidence note (line 659), FR-023; quickstart.md line 108; tasks/WP12 T075 (close-out.md "backs the PR body"), T076; research.md R-3/R-9 | Evidence items are written as one PR body. Not assigned per PR: five-section body (each of six), known-red baseline (PR1 and referenced after), DEV-1/DEV-2 confirmation requests (PR1 plus #5528), CODEOWNERS advisory statement (PR3, WP07), release dry-run artifact SC-006 (PR4), NFR-001 timing and the SC-002 reality check (PR5), NFR-007 coverage paste (PR5), `src/`-untouched and "exactly one glob line" SC-008 diff assertions (per-PR base vs whole-stack base), WP12's `git log origin/main..HEAD`/stray-missing diff check (stack base differs per PR). | Add a per-PR evidence table to WP12 T075 and plan (PR 1..6 -> the SC/NFR/DEV items it carries and the base each diff assertion uses); make the WP12 stray/missing check run against `origin/main` for the whole stack and against the previous seam head for per-PR claims. |
| A5 | Inconsistency | MEDIUM | plan.md "UI early-start point" and D-P13, E-3, P-11; tracer-approach.md UI section; WP05 line 151, WP09 line 222, WP10 line 156, WP12 T077 | p0 = last commit of IC-04 = head of PR 2 (aligned); p1 = "first commit whose contracts-workflow run is green on the draft PR" falls inside PR 4 and requires A2; p2 = last commit of IC-09 = PR 5 head. Alignment is correct but unstated; partial points (IC-02, IC-03) lie inside PR 2; "the draft PR" wording is singular. | State in plan, tracer-approach and WP05/WP09/WP10: each preview tag is cut at the stated seam head and cites the seam PR number; p1 recorded with that PR's run id; p0 is the UI early-start unit (PR 2). |
| A6 | Underspecification | MEDIUM | spec.md CL-1 ("not labelled ready-for-squad"), C-001, SC-010; plan.md E-2/E-3 | No rule for the stack as a whole: all six remain draft until the single ack on #5528 (ruling); merge order is bottom-up by the operator/maintainer; the orchestrator never merges and never marks ready; retargeting after a lower merge is a maintainer act; "ready-for-squad" label applies to none until ack. | Add to C-001 and plan process section; reference DD-21. |
| A7 | Coverage | MEDIUM | tracer-design-decisions.md (last record DD-20, then "Assess at close"); tracer-approach.md Log | The ruling has no decision record, as expected. Charter Standing Order 3 requires tracer files to carry rationale. | Add DD-21: ruling date 2026-10-02, six seams, why (reviewability, per-reviewer skill sets, p0 as UI unit), the A2 consequence on `branches: [main]`, supersession of "one PR" in CL-1/C-001. Add a Log line to tracer-approach.md. |
| A8 | Inconsistency | LOW | plan.md line 445 ("eleven work packages") vs wps.yaml/tasks.md (12 WPs) and plan.md Implementation Concern Map | Count drift: concerns are IC-01..IC-10 with IC-07 split (eleven concerns); WPs are twelve because IC-10 is split. | Reword to "eleven concerns delivered as twelve work packages". |
| A9 | Underspecification | LOW | tasks/WP02 record step (research.md R-3/R-9 committed before WP03), WP01 baseline record; WP12 owns research.md/close-out.md | Orchestrator-written planning records land in whichever seam is current; WP12 (PR 6) owns the final state. | State in WP12 which PR carries planning records and that PR 6 only finalises them. |
| A10 | Info | INFO | tasks/WP09 line 218 | T061 retired, intentional gap documented. | None. |

### Coverage Summary

Every FR-001..FR-025, NFR-001..NFR-007, C-001..C-011 and SC-001..SC-010 named in spec.md appears in at least one WP `requirement_refs` in wps.yaml (mechanical check: zero unmapped). T001..T079 are present except retired T061. No orphan WPs.

### Other passes

- Duplication: none material; WP09 `contracts/mission-status/**` and fixture globs overlap WP03-WP05 and WP10 ownership, but WPs are strictly serial (single lane chain), so write-scope overlap is sequential, not concurrent.
- Ambiguity/underspecification: only the stack items above.
- Charter alignment: Standing Order 7 (PRs only, merge agent merges) is consistent with the ruling; Standing Order 3 (tracer files) is why A7 matters; no charter conflict found.
- Terminology: Mission/work package canon used consistently; no "feature" drift found in normative text.
- Dependency/write-scope sanity: dependency graph acyclic (WP09 depends on WP05..WP08, WP10 on WP06, WP09). `contracts.yml` single-writer order WP02, WP08, WP09 holds. Seam boundaries coincide with WP boundaries, so no WP straddles two PRs.
