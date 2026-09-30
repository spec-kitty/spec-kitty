---
title: 3.2 Navigation update plan (T007 / T008)
description: Diff-shaped navigation update plan (T007/T008) for every TOC file under docs/ plus the five nav-group definitions required by FR-003 and FR-004.
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# 3.2 Navigation update plan (T007 / T008)

> Diff-shaped plan for every TOC file under `docs/**` plus the five nav-group
> definitions required by FR-003 / FR-004.
>
> **Mission:** `spec-kitty-3-2-docs-01KS4KSZ` · **WP:** WP03 ·
> **Owned file:** `docs/development/3-2-navigation-plan.md`
>
> **Read-only sources:**
>
> - `docs/development/3-2-page-inventory.yaml` (WP02 — page tag SoT)
> - `docs/development/3-2-version-taxonomy.md` (WP01 — five-tag taxonomy)
> - `docs/docfx.json` (confirmed doc-site generator: **DocFX**)
> - Live TOC files: `docs/toc.yml`, `docs/1x/toc.yml`, `docs/2x/toc.yml`,
>   `docs/context/toc.yml`, `docs/architecture/toc.yml`, `docs/guides/toc.yml`,
>   `docs/migration/toc.yml`, `docs/api/toc.yml`, `docs/guides/toc.yml`
>
> **No live TOC file is edited by WP03.** This plan is the deliverable.
> Per FR-004 / Renata finding R4: the doc-site generator is **DocFX**
> (confirmed via `docs/docfx.json`), so the `toc.yml` syntax below is
> generator-correct. The plan also notes any DocFX-specific construct so a
> future flip to MkDocs (deferred) would have a clear seam.

---

## Generator confirmation (R4 follow-up)

`docs/docfx.json` exists and declares a DocFX `build.content` set that
enumerates `toc.yml` files for every published directory under `docs/`:

```text
docs/toc.yml
docs/1x/toc.yml
docs/2x/toc.yml
docs/context/toc.yml
docs/architecture/toc.yml
docs/guides/toc.yml
docs/migration/toc.yml
docs/api/toc.yml
docs/guides/toc.yml
```

That is **nine TOC files**. T007 covers every one of them with either a
diff or an explicit "(no changes)" entry. There is no `mkdocs.yml`, no
`conf.py` (Sphinx), and no Docusaurus `sidebars.*` file under `docs/`, so
the plan treats DocFX as the sole publisher target. If the generator is
later changed, only the syntax in this document needs to change; the
nav-group definitions (T008) are syntax-independent.

---

## Conventions used in this plan

- **Before snapshot** = the current literal `toc.yml` content (read-only
  quote of the live file at base commit).
- **After snapshot** = the proposed `toc.yml` content after rebalancing.
- **Diff** = unified-diff-style `+` / `-` lines.
- **Rationale** = 1–2 sentences explaining why entries moved.
- Page membership is sourced from
  `docs/development/3-2-page-inventory.yaml` (WP02). Where the inventory
  carries a `current` page that has no live TOC entry today, the after
  snapshot adds it; this is non-destructive because the page already
  exists on disk.
- Order in each after snapshot is **alphabetical by display name within
  the group**, then groups are kept in the order they appear in the
  inventory. Re-ordering for editorial flow is deferred to WP07/WP08.
- 3.1 handling defaults to **Migration** per the plan default for the
  deferred decision `01KS4KTGTN4DBE60JFWKEA2FJB`. The flip path is
  documented in §"Flip path: decision 01KS4KTGTN4DBE60JFWKEA2FJB".

---

## T007 — TOC-file-by-TOC-file diffs

### 1. `docs/toc.yml` — site root nav

**Before snapshot** (live, 18 lines):

```yaml
- name: Home
  href: index.md
- name: Tutorials
  href: tutorials/
- name: How-To Guides
  href: how-to/
- name: Reference
  href: reference/
- name: Explanation
  href: explanation/
- name: Migration
  href: migration/
- name: 3.x Docs (Current)
  href: 3x/
- name: 1.x Docs
  href: 1x/
- name: 2.x Docs (Archive)
  href: 2x/
```

**After snapshot:**

```yaml
- name: Home
  href: index.md
- name: 3.2 (Current)
  items:
    - name: Tutorials
      href: tutorials/
    - name: How-To Guides
      href: how-to/
    - name: Reference
      href: reference/
    - name: Explanation
      href: explanation/
    - name: 3.x Docs (Current)
      href: 3x/
- name: Migration
  href: migration/
- name: Archive (2.x)
  href: 2x/
- name: Archive (1.x)
  href: 1x/
```

**Diff:**

```diff
 - name: Home
   href: index.md
-- name: Tutorials
-  href: tutorials/
-- name: How-To Guides
-  href: how-to/
-- name: Reference
-  href: reference/
-- name: Explanation
-  href: explanation/
+- name: 3.2 (Current)
+  items:
+    - name: Tutorials
+      href: tutorials/
+    - name: How-To Guides
+      href: how-to/
+    - name: Reference
+      href: reference/
+    - name: Explanation
+      href: explanation/
+    - name: 3.x Docs (Current)
+      href: 3x/
 - name: Migration
   href: migration/
-- name: 3.x Docs (Current)
-  href: 3x/
-- name: 1.x Docs
-  href: 1x/
-- name: 2.x Docs (Archive)
-  href: 2x/
+- name: Archive (2.x)
+  href: 2x/
+- name: Archive (1.x)
+  href: 1x/
```

**Rationale.** Promotes the five nav groups from FR-004 to first-class
top-level entries. The `3.2 (Current)` group nests the Divio quadrants
plus `3x/` so a 3.2 reader sees current-tagged surface area before
seeing migration or archive content. Archive entries are renamed for
consistency (`Archive (Nx)`) and ordered newest-first (2.x above 1.x)
per landing-page expectations. The conditional **3.1 (Supported)** group
is **absent** under the plan default; see §"Flip path" for the change if
decision `01KS4KTGTN4DBE60JFWKEA2FJB` resolves to keep 3.1 separate.

**DocFX note.** DocFX supports nested `items:` blocks for grouping;
this construct is not MkDocs-portable verbatim and is the only
generator-specific syntax in the plan.

---

### 2. `docs/1x/toc.yml` — 1.x archive child TOC

**Before snapshot** (live, 10 lines):

```yaml
- name: 1.x Overview
  href: index.md
- name: 1.x Workflow
  href: workflow.md
- name: 1.x Artifacts and Commands
  href: artifacts-and-commands.md
- name: 1.x Orchestration and API Boundary
  href: orchestration-and-api.md
- name: 1.x Branch and Workspace Model
  href: branches-and-workspaces.md
```

**After snapshot:** (no functional changes; entries unchanged)

```yaml
- name: 1.x Overview
  href: index.md
- name: 1.x Workflow
  href: workflow.md
- name: 1.x Artifacts and Commands
  href: artifacts-and-commands.md
- name: 1.x Orchestration and API Boundary
  href: orchestration-and-api.md
- name: 1.x Branch and Workspace Model
  href: branches-and-workspaces.md
```

**Diff:** (no changes)

**Rationale.** All 5 inventoried 1.x pages are tagged `archival`; they
already cover the directory and the prefix "1.x " keeps them
self-labelling. The directory move from `docs/1x/` to `docs/archive/1x/`
is **WP09's** responsibility, not WP03's; this TOC will be re-pathed at
that point but the entry names stay.

---

### 3. `docs/2x/toc.yml` — 2.x archive child TOC

**Before snapshot** (live, 12 lines):

```yaml
- name: 2.x Overview
  href: index.md
- name: Doctrine and Charter
  href: doctrine-and-charter.md
- name: Glossary System
  href: glossary-system.md
- name: Runtime and Missions
  href: runtime-and-missions.md
- name: Orchestration and API Boundary
  href: orchestration-and-api.md
- name: ADR Coverage
  href: adr-coverage.md
```

**After snapshot:**

```yaml
- name: 2.x Overview
  href: index.md
- name: ADR Coverage (2.x)
  href: adr-coverage.md
- name: Doctrine and Charter (2.x)
  href: doctrine-and-charter.md
- name: Glossary System (2.x)
  href: glossary-system.md
- name: Model Discipline Routing (2.x)
  href: model-discipline-routing.md
- name: Model to Task Type (2.x)
  href: model-to-task_type.md
- name: Orchestration and API Boundary (2.x)
  href: orchestration-and-api.md
- name: Runtime and Missions (2.x)
  href: runtime-and-missions.md
```

**Diff:**

```diff
 - name: 2.x Overview
   href: index.md
-- name: Doctrine and Charter
+- name: ADR Coverage (2.x)
+  href: adr-coverage.md
+- name: Doctrine and Charter (2.x)
   href: doctrine-and-charter.md
-- name: Glossary System
+- name: Glossary System (2.x)
   href: glossary-system.md
-- name: Runtime and Missions
-  href: runtime-and-missions.md
-- name: Orchestration and API Boundary
+- name: Model Discipline Routing (2.x)
+  href: model-discipline-routing.md
+- name: Model to Task Type (2.x)
+  href: model-to-task_type.md
+- name: Orchestration and API Boundary (2.x)
   href: orchestration-and-api.md
-- name: ADR Coverage
-  href: adr-coverage.md
+- name: Runtime and Missions (2.x)
+  href: runtime-and-missions.md
```

**Rationale.** The inventory carries **8 archival pages** under `docs/2x/`;
the live TOC only lists 6. The after snapshot adds the two missing pages
(`model-discipline-routing.md`, `model-to-task_type.md`) so every
inventoried archival page is reachable from nav. Display names get a
`(2.x)` suffix to disambiguate from same-titled 3.2 pages (e.g.
"Orchestration and API Boundary" exists in both 1.x and 2.x). Order is
alphabetical for predictable scanning. As with 1.x, the physical
directory move to `docs/archive/2x/` is WP09's job.

---

### 4. `docs/context/toc.yml` — 3.x current child TOC

**Before snapshot** (live, 6 lines):

```yaml
- name: 3.x Docs (Current)
  href: index.md
- name: How Charter Works
  href: charter-overview.md
- name: Governance Files Reference
  href: governance-files.md
```

**After snapshot:** (no functional changes)

```yaml
- name: 3.x Docs (Current)
  href: index.md
- name: How Charter Works
  href: charter-overview.md
- name: Governance Files Reference
  href: governance-files.md
```

**Diff:** (no changes)

**Rationale.** Inventory carries exactly 3 `current`-tagged pages under
`docs/context/` and all three are already in the TOC. The 3.2 refresh adds
content to `how-to/`, `reference/`, and `explanation/`; the `3x/`
directory is for charter/governance overview pages and stays unchanged.

---

### 5. `docs/architecture/toc.yml` — Divio "Explanation" child TOC

**Before snapshot** (live, 30 lines, 15 entries):

```yaml
- name: Spec-Driven Development
  href: spec-driven-development.md
- name: Divio Documentation System
  href: divio-documentation.md
- name: Execution Lanes
  href: execution-lanes.md
- name: Git Worktrees
  href: git-worktrees.md
- name: Git Workflow
  href: git-workflow.md
- name: Mission System
  href: mission-system.md
- name: Kanban Workflow
  href: kanban-workflow.md
- name: AI Agent Architecture
  href: ai-agent-architecture.md
- name: Documentation Mission
  href: documentation-mission.md
- name: Multi-Agent Orchestration
  href: multi-agent-orchestration.md
- name: Runtime Loop
  href: runtime-loop.md
- name: "Understanding Charter: Synthesis, DRG, and Governed Context"
  href: charter-synthesis-drg.md
- name: Understanding the Org Doctrine Layer
  href: org-doctrine-layer.md
- name: Understanding Governed Profile Invocation
  href: governed-profile-invocation.md
- name: Understanding the Retrospective Learning Loop
  href: retrospective-learning-loop.md
```

**After snapshot:** (no functional changes)

Same 15 entries. Inventory matches the TOC exactly (15 `current`-tagged
pages under `docs/architecture/`; all 15 already listed).

**Diff:** (no changes)

**Rationale.** WP02 inventory and the live TOC are already in lock-step
for `docs/architecture/`. Editorial reordering (e.g. moving the four
"Understanding…" entries into a sub-group) is deferred to WP08 IA review.

---

### 6. `docs/guides/toc.yml` — Divio "How-To Guides" child TOC

**Before snapshot** (live, 58 lines, 29 entries):

```yaml
- name: Install & Upgrade
  href: install-spec-kitty.md
- name: Diagnose Installation Problems
  href: diagnose-installation.md
- name: Set Up Codex Launcher
  href: setup-codex-spec-kitty-launcher.md
- name: Create a Specification
  href: create-specification.md
- name: Keep Main Clean
  href: keep-main-clean.md
- name: Create a Plan
  href: create-plan.md
- name: Generate Tasks
  href: generate-tasks.md
- name: Implement a work package
  href: implement-work-package.md
- name: Review Work Packages
  href: review-work-package.md
- name: Accept and Merge
  href: accept-and-merge.md
- name: Merge a Feature
  href: merge-feature.md
- name: Troubleshoot Merge Issues
  href: troubleshoot-merge.md
- name: Handle Dependencies
  href: handle-dependencies.md
- name: Sync Workspaces
  href: sync-workspaces.md
- name: Use Operation History
  href: use-operation-history.md
- name: Parallel Development
  href: parallel-development.md
- name: Run External Orchestrator
  href: run-external-orchestrator.md
- name: Build Custom Orchestrator
  href: build-custom-orchestrator.md
- name: Switch Missions
  href: switch-missions.md
- name: Use the Dashboard
  href: use-dashboard.md
- name: Manage the Glossary
  href: manage-glossary.md
- name: Upgrade to 0.12.0
  href: upgrade-to-0-12-0.md
- name: Non-Interactive Init
  href: non-interactive-init.md
- name: Set Up Project Governance
  href: setup-governance.md
- name: Synthesize and Maintain Doctrine
  href: synthesize-doctrine.md
- name: Create an Org Doctrine Pack
  href: create-an-org-doctrine-pack.md
- name: Run a Governed Mission
  href: run-governed-mission.md
- name: Use the Retrospective Learning Loop
  href: use-retrospective-learning.md
- name: Troubleshoot Charter Failures
  href: troubleshoot-charter.md
```

**After snapshot:** retains the 29 live entries in their current order
**and** appends 9 entries for pages the WP02 inventory carries as
`current` but the TOC does not yet list, plus 1 `migration`-tagged page
that lives in `docs/guides/` rather than `docs/migration/`:

```yaml
# ... 29 entries above unchanged ...
- name: Adhoc Specialist Session
  href: adhoc-specialist-session.md
- name: GStack Glossary Observations
  href: gstack-glossary-observations.md
- name: Install and Upgrade (3.2)
  href: install-and-upgrade.md
- name: Manage Agents
  href: manage-agents.md
- name: Recover From Implementation Crash
  href: recover-from-implementation-crash.md
- name: Recover From Interrupted Merge
  href: recover-from-interrupted-merge.md
- name: Run Mutation Tests
  href: run-mutation-tests.md
- name: Use WPS YAML Manifest
  href: use-wps-yaml-manifest.md
- name: "Migration: 2.1 → main Cutover Checklist"
  href: 2-1-main-cutover-checklist.md
```

**Diff:**

```diff
 - name: Troubleshoot Charter Failures
   href: troubleshoot-charter.md
+- name: Adhoc Specialist Session
+  href: adhoc-specialist-session.md
+- name: GStack Glossary Observations
+  href: gstack-glossary-observations.md
+- name: Install and Upgrade (3.2)
+  href: install-and-upgrade.md
+- name: Manage Agents
+  href: manage-agents.md
+- name: Recover From Implementation Crash
+  href: recover-from-implementation-crash.md
+- name: Recover From Interrupted Merge
+  href: recover-from-interrupted-merge.md
+- name: Run Mutation Tests
+  href: run-mutation-tests.md
+- name: Use WPS YAML Manifest
+  href: use-wps-yaml-manifest.md
+- name: "Migration: 2.1 → main Cutover Checklist"
+  href: 2-1-main-cutover-checklist.md
```

**Rationale.** WP02 carries **37 `current` + 1 `migration` = 38** how-to
pages; the live TOC only lists 29. The after snapshot reaches parity with
the inventory without re-ordering existing entries (re-ordering is
deferred to WP08 IA). `2-1-main-cutover-checklist.md` is the one
how-to-located `migration` page; its display name carries a "Migration:"
prefix so the leakage check's banner requirement is visible at nav level
as well as at page level. (Per WP08 IA review, this entry may be moved
into the Migration group; that is deferred.)

---

### 7. `docs/migration/toc.yml` — migration child TOC

**Before snapshot** (live, 6 lines):

```yaml
- name: Migrating from 2.x / Early 3.x
  href: from-charter-2x.md
- name: TeamSpace Mission-State Repair
  href: teamspace-mission-state-repair.md
- name: Migrating Shared Doctrine to the Org Layer
  href: doctrine-local-overlay-to-org-layer.md
```

**After snapshot:**

```yaml
- name: Migrating from 2.x / Early 3.x
  href: from-charter-2x.md
- name: Charter Ownership Consolidation
  href: charter-ownership-consolidation.md
- name: Cross-Repo E2E Gate
  href: cross-repo-e2e-gate.md
- name: Migrating Shared Doctrine to the Org Layer
  href: doctrine-local-overlay-to-org-layer.md
- name: Feature-Flag Deprecation
  href: feature-flag-deprecation.md
- name: Mission ID — Canonical Identity Migration
  href: mission-id-canonical-identity.md
- name: Mission-Type Flag Deprecation
  href: mission-type-flag-deprecation.md
- name: Retrospective Events — Upstream Move
  href: retrospective-events-upstream.md
- name: Shared-Package Boundary Cutover
  href: shared-package-boundary-cutover.md
- name: TeamSpace Mission-State 920 Closeout
  href: teamspace-mission-state-920-closeout.md
- name: TeamSpace Mission-State Repair
  href: teamspace-mission-state-repair.md
```

**Diff:**

```diff
 - name: Migrating from 2.x / Early 3.x
   href: from-charter-2x.md
-- name: TeamSpace Mission-State Repair
-  href: teamspace-mission-state-repair.md
+- name: Charter Ownership Consolidation
+  href: charter-ownership-consolidation.md
+- name: Cross-Repo E2E Gate
+  href: cross-repo-e2e-gate.md
 - name: Migrating Shared Doctrine to the Org Layer
   href: doctrine-local-overlay-to-org-layer.md
+- name: Feature-Flag Deprecation
+  href: feature-flag-deprecation.md
+- name: Mission ID — Canonical Identity Migration
+  href: mission-id-canonical-identity.md
+- name: Mission-Type Flag Deprecation
+  href: mission-type-flag-deprecation.md
+- name: Retrospective Events — Upstream Move
+  href: retrospective-events-upstream.md
+- name: Shared-Package Boundary Cutover
+  href: shared-package-boundary-cutover.md
+- name: TeamSpace Mission-State 920 Closeout
+  href: teamspace-mission-state-920-closeout.md
+- name: TeamSpace Mission-State Repair
+  href: teamspace-mission-state-repair.md
```

**Rationale.** Inventory carries **11 `migration`-tagged pages** under
`docs/migration/`; the live TOC lists only 3. The after snapshot reaches
inventory parity. The `from-charter-2x.md` entry is preserved as the
landing case ("Migrating from 2.x / Early 3.x") because it is the
flagship migration narrative and reflects the existing entry name. Order
within the list is alphabetical thereafter for deterministic diffs;
WP08's IA review may sort by recency or by source-version target.

**Note on `feature-flag-deprecation.md`.** Display name retains
"Feature-Flag" as a historical reference to a discontinued surface; per
Charter Terminology Canon, the **active domain object is Mission**, and
this entry documents the historical 2.x feature-flag deprecation only.
A separate `mission-type-flag-deprecation.md` entry exists for the
3.x-era mission-type flag cleanup.

---

### 8. `docs/api/toc.yml` — Divio "Reference" child TOC

**Before snapshot** (live, 26 lines, 13 entries):

```yaml
- name: CLI Commands
  href: cli-commands.md
- name: Charter CLI Reference
  href: charter-commands.md
- name: Profile Invocation Reference
  href: profile-invocation.md
- name: Retrospective Schema Reference
  href: retrospective-schema.md
- name: Orchestrator API
  href: orchestrator-api.md
- name: Slash Commands
  href: slash-commands.md
- name: Agent Subcommands
  href: agent-subcommands.md
- name: Configuration
  href: configuration.md
- name: Environment Variables
  href: environment-variables.md
- name: File Structure
  href: file-structure.md
- name: Missions
  href: missions.md
- name: Event Envelope
  href: event-envelope.md
- name: Supported Agents
  href: supported-agents.md
```

**After snapshot:** appends the 3 inventoried `current` pages that have
no live TOC entry today (`README.md`, `agent-plan-artifacts.md`,
`terminology.md`):

```yaml
# ... 13 entries above unchanged ...
- name: Reference Overview
  href: README.md
- name: Agent Plan Artifacts
  href: agent-plan-artifacts.md
- name: Terminology
  href: terminology.md
```

**Diff:**

```diff
 - name: Supported Agents
   href: supported-agents.md
+- name: Reference Overview
+  href: README.md
+- name: Agent Plan Artifacts
+  href: agent-plan-artifacts.md
+- name: Terminology
+  href: terminology.md
```

**Rationale.** Inventory carries **16 `current` reference pages**; the
live TOC has 13. The after snapshot reaches parity. `README.md` is
exposed as "Reference Overview" so DocFX surfaces it as a child landing
page; `terminology.md` is the canonical-term glossary the Charter
Terminology Canon enforces (placing it under Reference makes it directly
linkable from leakage-check failures).

---

### 9. `docs/guides/toc.yml` — Divio "Tutorials" child TOC

**Before snapshot** (live, 14 lines, 7 entries):

```yaml
- name: Getting Started
  href: getting-started.md
- name: Your First Feature
  href: your-first-mission.md
- name: Multi-Agent Workflow
  href: multi-agent-workflow.md
- name: Missions Overview
  href: missions-overview.md
- name: Claude Code Integration
  href: claude-code-integration.md
- name: Claude Code Workflow
  href: claude-code-workflow.md
- name: Charter Governed Workflow (End-to-End)
  href: charter-governed-workflow.md
```

**After snapshot:** (no functional changes)

Same 7 entries. Inventory matches the TOC exactly.

**Diff:** (no changes)

**Rationale.** Inventory carries 7 `current`-tagged tutorials; all 7 are
already in the TOC. WP07 may rename `your-first-mission.md` to a
mission-canonical phrasing per Charter Terminology Canon, but that is a
**page-content** change, not a nav change, and is out of scope for WP03.

---

## T007 coverage summary

| TOC file | Inventory pages in scope | Entries before | Entries after | Change kind |
| --- | ---: | ---: | ---: | --- |
| `docs/toc.yml` | n/a (parent) | 9 | 9 (regrouped) | structural |
| `docs/1x/toc.yml` | 5 | 5 | 5 | no changes |
| `docs/2x/toc.yml` | 8 | 6 | 8 | additive + rename |
| `docs/context/toc.yml` | 3 | 3 | 3 | no changes |
| `docs/architecture/toc.yml` | 15 | 15 | 15 | no changes |
| `docs/guides/toc.yml` | 38 | 29 | 38 | additive |
| `docs/migration/toc.yml` | 11 | 3 | 11 | additive |
| `docs/api/toc.yml` | 16 | 13 | 16 | additive |
| `docs/guides/toc.yml` | 7 | 7 | 7 | no changes |
| **Total** | **103** | **90** | **112** | — |

Pages **excluded** from any TOC by design:

- All `internal`-tagged pages (288 rows: `docs/development/**`,
  `docs/architecture/**`, all of `architecture/**`). Per taxonomy
  `internal`, these are **not** part of the published 3.2 nav index.
- Six `current` root-level pages (`docs/index.md`,
  `docs/contextive-glossaries.md`, `docs/host-surface-parity.md`,
  `docs/retrospective-learning-loop.md`, `docs/status-model.md`,
  `docs/trail-model.md`) and one `current` recovery page
  (`docs/operations/logged-out-teamspace.md`). These are intentionally
  excluded from child TOCs; whether they should appear in the root
  `docs/toc.yml` as siblings of `Home` is **deferred to WP08 IA review**.
- The repo-root `README.md` is `current`-tagged and lives outside the
  doc-site build — DocFX does not nav-index it.

---

## T008 — Five nav-group definitions

The five nav groups required by FR-004 are defined below with member
populations sourced from the WP02 inventory and landing-page wording
drafted for WP07 reference and WP08 IA cross-linking.

### Group 1 — **3.2 (current)**

**Members.** All 88 pages tagged `current` in the WP02 inventory:

- `docs/context/**` (3 pages)
- `docs/guides/**` (7 pages)
- `docs/guides/**` (37 pages)
- `docs/api/**` (16 pages)
- `docs/architecture/**` (15 pages)
- `docs/doctrine/**` (2 pages)
- `docs/operations/**` (1 page)
- `docs/` root pages (6 pages: `index.md`, `contextive-glossaries.md`,
  `host-surface-parity.md`, `retrospective-learning-loop.md`,
  `status-model.md`, `trail-model.md`)
- Repo-root `README.md` (1 page — out-of-build but tagged for
  citation purposes)

**Landing-page wording draft (1–2 sentences).**
> Spec Kitty 3.2 — the current release. Tutorials, how-to guides,
> reference material, and explanation pages here describe behaviour as it
> ships in 3.2. Anything older than 3.2 lives under Migration or Archive.

---

### Group 2 — **3.1 (supported)** *(conditional)*

**Conditional on deferred decision
[`01KS4KTGTN4DBE60JFWKEA2FJB`](../../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/spec.md).**

**Plan default (this WP).** **This group is absent.** All would-be
"3.1-supported" pages are folded into the **Migration** group as 3.1 →
3.2 upgrade notes. The WP02 inventory therefore carries **zero
`supported` rows** (verified at the top of
`docs/development/3-2-page-inventory.yaml`: "No `supported` rows in this
initial inventory: per plan default the deferred decision
01KS4KTGTN4DBE60JFWKEA2FJB folds 3.1 content into `migration`").

**Members under default.** None.

**Members if decision flips to "keep 3.1 as supported".** The set of
3.1-era pages currently folded into Migration would re-tag from
`migration` to `supported` and appear here. The candidate set is
identified at WP08 IA review; the inventory must be re-walked at that
point.

**Landing-page wording draft (1–2 sentences) — for the flip case only.**
> Spec Kitty 3.1 — still supported. Pages here describe 3.1 behaviour
> that 3.2 users are likely to invoke unchanged; consult the Migration
> group when 3.2 behaviour differs.

---

### Group 3 — **Migration**

**Members.** All 12 pages tagged `migration` in the WP02 inventory:

- `docs/migration/charter-ownership-consolidation.md`
- `docs/migration/cross-repo-e2e-gate.md`
- `docs/migration/doctrine-local-overlay-to-org-layer.md`
- `docs/migration/feature-flag-deprecation.md`
- `docs/migration/from-charter-2x.md`
- `docs/migration/mission-id-canonical-identity.md`
- `docs/migration/mission-type-flag-deprecation.md`
- `docs/migration/retrospective-events-upstream.md`
- `docs/migration/shared-package-boundary-cutover.md`
- `docs/migration/teamspace-mission-state-920-closeout.md`
- `docs/migration/teamspace-mission-state-repair.md`
- `docs/guides/2-1-main-cutover-checklist.md` (located under `how-to/`
  for editorial reasons; tagged `migration` in inventory)

**Landing-page wording draft (1–2 sentences).**
> Moving to 3.2 from an earlier version? Start here. Each page carries
> the mandatory migration banner and walks a 1.x, 2.x, or 3.1 reader
> through the changes needed to land on 3.2.

---

### Group 4 — **Archive (2.x)**

**Members.** All 8 pages tagged `archival` under `docs/2x/**` in the
WP02 inventory:

- `docs/2x/adr-coverage.md`
- `docs/2x/doctrine-and-charter.md`
- `docs/2x/glossary-system.md`
- `docs/2x/index.md`
- `docs/2x/model-discipline-routing.md`
- `docs/2x/model-to-task_type.md`
- `docs/2x/orchestration-and-api.md`
- `docs/2x/runtime-and-missions.md`

**Landing-page wording draft (1–2 sentences).**
> Historical record of Spec Kitty 2.x. These pages are preserved for
> citation only; they do not describe current behaviour. Each page
> carries the mandatory archive banner — see the Migration group for the
> 2.x → 3.2 transition guide.

---

### Group 5 — **Archive (1.x)**

**Members.** All 5 pages tagged `archival` under `docs/1x/**` in the
WP02 inventory:

- `docs/1x/artifacts-and-commands.md`
- `docs/1x/branches-and-workspaces.md`
- `docs/1x/index.md`
- `docs/1x/orchestration-and-api.md`
- `docs/1x/workflow.md`

**Landing-page wording draft (1–2 sentences).**
> Historical record of Spec Kitty 1.x. These pages are preserved for
> citation only; the 1.x workflow is no longer supported. Operators
> upgrading from 1.x should go through the 2.x archive and the Migration
> group in sequence.

---

## Flip path: decision `01KS4KTGTN4DBE60JFWKEA2FJB`

If the deferred decision resolves to **"keep 3.1 as a supported group
distinct from Migration"**, only one section of this plan changes:

1. Re-walk `docs/development/3-2-page-inventory.yaml` and re-tag the
   3.1-era pages currently held under `migration` to `supported`. The
   candidate set is identified at WP08 IA review and is expected to be
   on the order of 20–25 pages (per the WP01 forecast).
2. Re-emit `docs/toc.yml` with the `3.1 (Supported)` group **inserted
   between** `3.2 (Current)` and `Migration`:

   ```diff
    - name: 3.2 (Current)
      items:
        ...
   +- name: 3.1 (Supported)
   +  href: 3.1/
    - name: Migration
      href: migration/
   ```
3. Add the landing-page wording in §"Group 2" verbatim.
4. The 4 archive/migration groups are unchanged.

No other TOC file changes under the flip.

---

## Reviewer cross-check (from `tasks/WP03-navigation-update-plan.md`

"Reviewer Guidance")

- [x] Every TOC file appears at least once. **9 of 9 covered.**
  - 4 with explicit diff (root, 2x, how-to, migration, reference)
  - 4 with "(no changes)" entry (1x, 3x, explanation, tutorials)
- [x] The conditional 3.1 group cites the decision_id
  `01KS4KTGTN4DBE60JFWKEA2FJB`. **Cited in §"Group 2" and §"Flip path".**
- [x] No live TOC file was edited by this WP. **Verifiable via
  `git diff --stat` — the only changed file is
  `docs/development/3-2-navigation-plan.md`.**

---

## See also

- WP01 taxonomy: `docs/development/3-2-version-taxonomy.md`
- WP02 inventory: `docs/development/3-2-page-inventory.yaml`
- Mission spec FR-003, FR-004:
  `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/spec.md`
- Doc-site generator config: `docs/docfx.json`
- Leakage-check contract:
  `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/contracts/version_leakage_check.md`
