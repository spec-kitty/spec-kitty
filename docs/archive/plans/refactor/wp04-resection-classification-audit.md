---
title: WP04 re-section classification audit
description: 'Per-file durable-vs-ephemeral classification record for the docs/development + docs/engineering_notes re-section (Mission B, FR-012, #2054).'
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Re-section classification audit; the #2054 re-section shipped in the 3.2.3 release (tag `v3.2.3`). Content preserved as an audit-trail record.

# WP04 re-section classification audit (FR-012 / #2054)

This note is the **auditable per-file record** for WP04's re-section of the
former `docs/development/` and `docs/plans/engineering-notes/` working sets. Every
page was classified individually (not a wholesale directory move) against the
explicit decision rules in the WP04 prompt, and the **rule that fired** is
recorded per page so the reviewer audits the *reason*, not just the bucket.

## Decision rules (from the WP04 prompt)

- **E1 — Ephemeral → `plans/`**: filename or content contains any of `sprint`,
  `session`, `WP##`/`wp-`, `mission-<slug>`, an effort-tied date-stamp,
  "status update", "tracking", "handoff", "scratch", **or** it narrates a
  one-time investigation / decision-in-progress.
- **D-OPS — Durable → `operations/`**: runbook / deployment / on-call / incident
  procedure.
- **D-GUIDE — Durable → `guides/`**: how-to / tutorial / contributor workflow
  that outlives any one mission.
- **D-CONFIG — Durable → `configuration/`**: settings / env-var / toolchain /
  config reference.
- **TB — Tie-breaker**: "would this page still be correct and useful two
  missions from now?" yes → durable, no → ephemeral.

`doc_status` (draft|active, distil-then-retire) is governed at the **section
level** by `docs/plans/index.md` — matching the convention WP03 established for
the `architecture/`-rooted plans (no per-file frontmatter was added there), so
WP04 does not churn per-file frontmatter either.

## Durable pages

| Page (from `docs/development/`) | Rule fired | → Section |
|---|---|---|
| `ssh-deploy-keys.md` | D-OPS — one-time CI/CD deploy-key provisioning runbook | `operations/` |
| `identity-boundary-ci-gate.md` | D-OPS — standing `drift-detector` required check + cross-repo SHA-bump procedure | `operations/` |
| `testing-flakiness.md` | D-GUIDE — flakiness handling policy / how-to, outlives missions | `guides/` |
| `testing-parallel.md` | D-GUIDE — how-to run the suite in parallel | `guides/` |
| `contract-pinning.md` | D-GUIDE — contributor workflow (pin observable contracts) | `guides/` |
| `review-gates.md` | D-GUIDE — pre-PR / pre-review checklist workflow | `guides/` |
| `local-overrides.md` | D-GUIDE — cross-package local-dev how-to | `guides/` |
| `yaml-libraries.md` | D-CONFIG — toolchain/dependency choice reference (ruamel vs PyYAML) | `configuration/` |
| `linting-cutoff-policy.md` | D-CONFIG — commitlint/markdownlint informational-mode policy + cutoff | `configuration/` |

## Ephemeral pages → `plans/`

| Page (from `docs/development/`) | Rule fired |
|---|---|
| `3-2-archive-migration-plan.md` | E1 — 3.2 docs-refresh effort-scoped plan |
| `3-2-cli-reference-audit-meta-issues.md` | E1 — audit log / meta-issue tracking |
| `3-2-cli-reference-methodology.md` | E1 — mission `spec-kitty-3-2-docs` WP05 evidence record |
| `3-2-coord-merge-issue-hygiene-log.md` | E1 — issue-hygiene "log" (tracking) |
| `3-2-harness-research-method.md` | E1 — 3.2 harness research method (effort-tied) |
| `3-2-information-architecture.md` | E1 — 3.2 docs-refresh IA (one effort) |
| `3-2-navigation-plan.md` | E1 — T007/T008 task-tied navigation plan |
| `3-2-publication-checklist.md` | E1 — 3.2 publication checklist (effort-tied) |
| `3-2-version-taxonomy.md` | E1 + TB — mission `spec-kitty-3-2-docs` taxonomy; durable-leaning but mission-tied → ephemeral |
| `391-doctrine-usage-test.md` | E1 — `#391` WP11 dogfood |
| `charter-path-resolution-gaps.md` | E1 — gap-analysis investigation |
| `ci-coverage-gate-tuning.md` | E1 + TB — Mission 062 WP07 tuning notes, branch-tied → ephemeral |
| `code-review-2026-03-25.md` | E1 — date-stamped one-time review |
| `doctrine-artifact-selection-preflight.md` | E1 — pre-flight investigation |
| `doctrine-inclusion-assessment.md` | E1 — assessment investigation |
| `doctrine-migration-architecture-review.md` | E1 — architecture alignment review |
| `epic-1111-slice-landing-plan.md` | E1 — epic landing plan |
| `issue-1040-scope-assessment.md` | E1 — issue scope assessment |
| `issue-1111-analysis.md` | E1 — issue analysis report |
| `layered-doctrine-resolution-design.md` | E1 — design-in-progress blueprint |
| `mission-b-proposed-scope.md` | E1 — mission-tied proposed scope |
| `mission-next-compatibility.md` | E1 — explicitly marked HISTORICAL / superseded |
| `model-first-schema-generation.md` | E1 + TB — dated, PR-branch-tied writeup → ephemeral |
| `mutation-testing-findings.md` | E1 — WP05 findings |
| `org-doctrine-layer-architecture-review.md` | E1 — post-implementation review |
| `pr305-review-resolution-plan.md` | E1 — PR-tied resolution plan |
| `quality_check_structure.md` | E1 + TB — narrates one-time CI-workflow change → ephemeral |
| `runtime-charter-doctrine-boundary.md` | E1 — boundary audit + recommendations |
| `slice-f-gap-analysis.md` | E1 — slice gap analysis |
| `slice-f-mission-debrief.md` | E1 — mission debrief |
| `test-execution-report-pr305.md` | E1 — PR test-execution report |
| `test-plan-pr305.md` | E1 — PR test plan |
| `test-suite-friction-audit.md` | E1 — friction audit |
| `wp-prompt-governance-atdd-findings.md` | E1 — ATDD findings |
| `tracking/next-mission-mappings/*` (3 files) | E1 — "tracking" in path → `plans/next-mission-mappings/` |

## `docs/plans/engineering-notes/` → `plans/engineering-notes/`

The whole `engineering_notes/` tree is investigations / traces / reflections /
triage (E1 by the occurrence-map `moves:` `docs/plans/engineering-notes → docs/plans`).
Moved as a **subtree** (`plans/engineering-notes/`) to stay fully disjoint from
WP03's `architecture/`-rooted plans content (avoids the `index.md` collision).

## Stays put (operator directive)

- `docs/development/3-2-page-inventory.yaml` — page-inventory tooling artifact;
  the 4 lockfile modules read it at this exact path. Guarded by
  `tests/docs/test_inventory_path_stable.py`.
- `docs/development/mutation-testing-tactic.yaml` — doctrine tactic artifact
  (non-page `.yaml`, outside WP04's `*.md` ownership).

## IC-01 — borderline pages (tie-breaker resolved, no hard gap)

No page fit *no* rule. Four pages had durable-leaning content but
effort/mission/date/branch-tied framing tipped them ephemeral via the
tie-breaker; flagged here for reviewer attention:
`3-2-version-taxonomy.md`, `ci-coverage-gate-tuning.md`,
`model-first-schema-generation.md`, `quality_check_structure.md`. Each can be
distilled into a durable reference later under the plans distil-then-retire
lifecycle if the durable kernel is confirmed reusable.

## #2054 resolution note (issue-matrix)

`#2054` (the `docs/development/` durable-vs-ephemeral mixing drift) is resolved:
`docs/development/` no longer mixes durable references with one-off tracking
notes — durable pages are split across `operations/`, `guides/`,
`configuration/`; ephemeral notes are consolidated under `plans/`. The
page-inventory tooling artifact stays put (no freshness-gate self-block).
Mission B should carry `Closes #2054` on the PR (FR-012).
