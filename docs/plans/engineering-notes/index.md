---
title: Engineering notes
description: 'Internal engineering notes for Spec Kitty: field reports, design notes, architectural reviews, and the historical record of closed investigations and missions.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/architectural-review/README.md
- docs/plans/engineering-notes/finding/README.md
- docs/plans/engineering-notes/reflections/README.md
- docs/plans/engineering-notes/runtime_and_state_overhaul/README.md
- docs/plans/engineering-notes/triage/README.md
- docs/plans/index.md
---
# Engineering notes

Internal working notes for maintainers: design investigations, field reports, and the
records of closed missions. They are not end-user documentation.

These notes follow the distil-then-retire lifecycle described in the
[plans index](../index.md). A page stays under **Live** while it still guides current
work. Once its subject ships or is distilled into a canonical doc, it moves to
**Historical** and carries `doc_status: deprecated`, `superseded` or `closeout`. Historical
pages are kept as a record and are not current guidance. The active cycle is 4.0.0 — see the
[4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

## Reading these notes

- **Profile-named files** (`alphonso-*`, `debbie-*`, `paula-*`, `pedro-*`, `priti-*`,
  `randy-*`, `robbie-*`) are the per-lens outputs of an adversarial squad: several agent
  profiles (architect, debugger, patterns, Python implementer, planner, reducer, forensics)
  review the same question independently, and a `SYNTHESIS` page merges their findings.
- **CaaCS** (Code-as-a-Crime-Scene) is git-history forensics: churn, change coupling and
  complexity hot spots mined from the commit log.
- **Dialectic / red-team / white-team** passes argue for and against a design before it is
  accepted.
- **Degod / unshim** means splitting god objects into smaller modules and deleting
  compatibility shims.

## Live

### Clusters

- [Architectural review](architectural-review/README.md) — design reviews and findings.
- [Findings](finding/README.md) — recorded engineering findings.
- [Reflections](reflections/README.md) — retrospective engineering reflections.

### Field reports

Narratives of a full run under the doctrine: process, operator decisions, and where the
charter, ADRs or guides changed the outcome.

- [Doctrine-driven P0 remediation, end to end (2026-07-18)](2026-07-18-doctrine-driven-p0-remediation-field-report.md) — how the adversarial-squad cadence and the red-main, tracker-hygiene and seam docs shaped the fix for two merge-core P0 bugs (#2709, #2711) and their follow-up (#2786).
- [A migration-contract step with no owning WP (2026-07-19)](2026-07-19-migration-contract-step-ownership-field-report.md) — a staged migration passed every planning gate with a contract step no work package owned; caught only at closeout. Proposes a step-ownership lint (#2684).
- [Tactical workarounds for driving a full governed mission (2026-09-21)](2026-09-21-full-mission-driving-tactical-workarounds-field-report.md) — six workarounds found while driving one mission end to end, each with a note on whether it still applies (PR #4821).

### Design notes

- [Agent knowledge: canonical homes](agent-knowledge-canonical-homes.md) — where rules (charter), practices (doctrine), reference (Common Docs) and learned facts (`.kittify/memory/`) belong, and how to stop a per-agent memory duplicating the repo.

### Docs governance

- [Common-Docs section audit](common-docs-section-audit.md) — docs-wide baseline of which doc kind belongs in which section, the misfiled files it found, and proposed follow-up tickets (#2851, #2314, #2302).

## Historical (closed, shipped or superseded)

Kept as a record only. Each entry says what replaced it.

### Prior-cycle status and CI notes

- [3.2.6 Maintenance Brief](3.2.6-maintenance-brief.md) — status snapshot of the open 3.2.6 cycle. 3.2.6 shipped on 2026-09-03 and the 3.x line closed with 3.2.7.
- [Test-suite parallelization — CI shard topology status](testing-parallel-ci-topology-status.md) — **superseded** by the modular CI (#3995); see [CI gate mechanics](../../development/reference/ci-gate-mechanics.md).

### Mission closeouts and verification records

- [Mission closeout 01KSMG8Y — Pre-Doctrine Test Stabilization](01KSMG8Y-closeout/index.md) — baseline and retrospective for a merged mission.
- [Verification evidence — egress-refusal consolidation (01KYW895)](01KYW895-verification-evidence.md) — closeout evidence for the egress-refusal consolidation mission (#3110).
- [Docs IA & Onboarding Overhaul — terminology sweep and closing report](terminology-sweep-report.md) — closing record of mission `docs-ia-onboarding-overhaul-01KY02JB`: the terminology sweep, the frontmatter coverage check, and follow-up issues.
- [Retro-summary performance investigation](2342-retro-summary-nfr/report.md) — verdict that the 200-mission summary timing breach on CI was runner hardware variance, not a code regression (#2342); with its [oracle proof](2342-retro-summary-nfr/evidence/oracle-proof.md).

### Pre-spec research and mission scopes (missions delivered)

- [DRG completeness — pre-spec research squad](drg-completeness-2843-research.md) — relation-description parity, the activation-gate bug and anti-pattern promotion (#2843, #2847); mission `drg-relation-parity-activation-gate-01KY48PD` has completed.
- [Built-in doctrine DRG — missing links analysis](doctrine-drg-missing-links-analysis.md) — input census for ADR 2026-07-21-1, since superseded by ADR 2026-07-26-3.
- [CSF landing-pass campsite follow-ups — pre-spec research](research-notes-csf-2670.md) — root causes for the shard-map gap, an xdist flake, a sync remediation guard and mypy debt (#2670, epic #1928).
- [Coordination topology stabilization — working plan (post-3.2.0)](2026-06-12-coordination-topology-stabilization.md) — **superseded**; the planned coordination split-brain and fail-open gate work is done (#1878).
- [Coord-branch bookkeeping: read/write split-brain root cause](coord-splitbrain-rootcause.md) and [Coordination-branch trust — mission scope](coord-trust-mission-scope.md) — delivered by mission `coord-write-placement-closure-01KYCF83` (#2841).
- [Coord-trust residual + runtime-state birth cutover — mission scope](2841-residual-2917-mission-scope.md) and [runtime-state birth cutover — research](2917-runtime-state-birth-cutover-research.md) — delivered by mission `runtime-state-birth-cutover-all-paths-01KYH654` (#2917).
- [Mission #883 brief: doctrine as mission-type authority](883-mission-type-authority-brief.md) and [its research dossier](883-research-synthesis.md) — superseded by ADR 2026-07-14-2 and `docs/architecture/mission-type-resolution.md`.
- [Mission notes](mission-notes/index.md) — mission-scoped classifications whose owning missions have closed.
- [Docs consolidation — four-lens review and direction](651-docs-consolidation/index.md) — delivered by the Common Docs reconciliation (ADR 2026-06-27-1) (#2165, #651).

### Architecture audits (May 2026, 3.2.x cycle)

CaaCS audit of the repository and the issue triage that followed it. Issue states are as of May 2026.

- [spec-kitty CaaCS audit — 2026-05](architecture-audits/2026-05-spec-kitty-caacs.md)
- [CaaCS meta-assessment and input for the #666 spike](architecture-audits/2026-05-caacs-meta-assessment.md)
- [CaaCS findings ↔ #822 open sub-issues cross-check](architecture-audits/2026-05-822-crosscheck.md)
- [Findings vs issues (2026-05-11)](architecture-audits/2026-05-11-findings-vs-issues-update.md)
- [Audit relationship to #992 and #984](architecture-audits/2026-05-11-issue-992-984-audit-comments.md)
- [Phase 3 — issue drafts and triage](architecture-audits/2026-05-phase3-issue-drafts-and-triage.md)
- [F1 knowledge-capture plan](architecture-audits/2026-05-phase3-f1-knowledge-capture-plan.md)

### Retired clusters

Every page in these clusters carries `doc_status: deprecated`.

- [Runtime and state overhaul](runtime_and_state_overhaul/README.md) — design shipped as execution-context unification (#1619).
- [Triage](triage/README.md) — closeout for merged mission `test-stabilization-and-debt-pass-01KSF9HJ`.
- [Infra/logic separation](2173-infra-logic-separation/00-SYNTHESIS.md) — phase 1 shipped via mission `runtime-bridge-degod-01KX8M1C` (#2173, #2531).
- [Surface-resolution cluster](3-2-3-surface-resolution-cluster/00-SYNTHESIS.md) — shipped in the 3.2.3 release.
- [Naming/identity SSOT strangler](naming-identity-ssot-strangler/00-OVERVIEW.md) — the identity-primitive move to a lower layer shipped.
- [3.2.0 training bugs (#2007)](3-2-0-training-bugs-2007/SYNTHESIS-2007.md) — fixed in the 3.2.0 release.
- [3.2.x goal corroboration](3-2-x-goal-corroboration/DIALECTIC-SYNTHESIS.md) — folded into the 3.2.x open-core delivery plan; see also the [scoring synthesis](3-2-x-goal-corroboration/SCORING-SYNTHESIS.md).
- [Execution context factory — read/write symmetry](context-factory-readwrite-symmetry/00-SYNTHESIS.md) — read side shipped via mission `read-path-error-fidelity-adoption-01KV8NPC`.

## See also

- [Plans index](../index.md)
- [Development notes](../../development/index.md)
