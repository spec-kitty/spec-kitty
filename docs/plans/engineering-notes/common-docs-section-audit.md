---
title: Common-Docs section audit (docs-wide structural concern baseline)
description: 'Post-#2851 concern-bucket audit of every docs/ section: misfiled files, redistribution tally, follow-up proposals, and the durable ratchet-replacement recommendation (#2302).'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/adr/3.x/2026-06-27-1-common-docs-reconciliation.md
- docs/development/index.md
- docs/plans/engineering-notes/index.md
---
# Common-Docs section audit — docs-wide structural concern baseline

## Purpose

Issue [#2851](https://github.com/spec-kitty/spec-kitty/issues/2851) disambiguated
`docs/development/` by **concern bucket** and redistributed the misfiled subset to each
file's canonical home. That same PR (`758c2bd45`) **retired the anti-sprawl ratchet**
(`scripts/docs/anti_sprawl_ratchet.py`) — the only mechanical guard for canonical sections
and required indexes. With the ratchet gone, every other `docs/` section is unguarded against
the same "several jobs at once" accretion #2851 found in `development/`, and nothing stops the
cleaned tree from re-drifting.

This note is the **docs-wide baseline** that closes that gap: it applies #2851's method to the
rest of the tree, records the misfiled subset, proposes section-clustered follow-up tickets
under [#2314](https://github.com/spec-kitty/spec-kitty/issues/2314) bucket **C**, and
recommends the durable concern taxonomy that
[#2302](https://github.com/spec-kitty/spec-kitty/issues/2302) should codify as the ratchet's
replacement.

**Method (per #2851).** Each non-trivial file is assigned a concern bucket —
**(a)** contributor how-to · **(b)** reference/policy · **(c)** engineering-note / point-in-time
report · **(d)** generated asset / nav / tooling · **(e)** doctrine artifact (non-page) — then
judged correctly-placed vs **MISFILED** (naming the canonical home + a one-line rationale).

**Scope.** The 21 in-scope top-level sections: `adr, api, architecture, archive, assets,
changelog, configuration, context, contracts, core-concepts, doctrine, integrations, migrations,
operations, output, plans, reference, release-goals, security, templates, updates`.
**Excluded:** `docs/development/` (owned by #2851) and `docs/guides/` (owned by the in-flight
mission `docs-ia-onboarding-overhaul-01KY02JB`). **FR-003 holds: nothing may move into
`guides/`; treat `guides/` as owned by that mission.**

**Canonical redistribution homes** (Common-Docs ADR `2026-06-27-1`, D3/D4/D7):
`docs/plans/engineering-notes/` (point-in-time reports/status/synthesis/audit/closeout prose),
`docs/operations/` (operator/ops runbooks), the doctrine tree `src/doctrine/…` (doctrine
artifacts), plus intra-zone regrouping / delete-stale de-dup.

## Headline finding

`docs/` is **markedly healthier than `development/` was**: frontmatter coverage is near-total
(of ~600 in-scope `.md`, only 3 ADR `README.md` files lack frontmatter), and the point-in-time
prose is overwhelmingly **already** in its canonical home — `plans/engineering-notes/` holds
~40 dated synthesis/triage/finding/field-report files, all correctly filed. The accretion is
**concentrated in one section, `architecture/`**, plus a stale shadow tree at `plans/notes/`
and one stray closeout in `migrations/`. Six sections are index-only Common-Docs skeleton stubs
that the retired ratchet's `section_missing_index` guard used to protect.

---

## Per-section disposition

### `architecture/` — **NEEDS WORK** (the primary offender)

67 files. Durable living-design pages (`execution-lanes.md`, `git-worktrees.md`,
`mission-system.md`, `runtime-loop.md`, `multi-agent-orchestration.md`,
`spec-driven-development.md`, `mission-type-resolution.md`, `org-doctrine-layer.md`, the
`0N_*` C4 model dirs, `calibration/`, `diagrams/`) are **correctly placed**. The section is
polluted by three clusters of non-durable-design content, and its landing page is stale.

| File(s) | Current | Bucket | Proposed target | Rationale |
|---|---|---|---|---|
| `883-research-synthesis.md` | `architecture/` | (c) | **`plans/engineering-notes/`** | Self-declares "Point-in-time pre-spec research synthesis for mission #883 … **superseded by the ADR and brief where they differ**." A dated mission research dossier, not living design. **MISFILED.** |
| `883-mission-type-authority-brief.md` | `architecture/` | (c) | **`plans/engineering-notes/`** | Companion pre-spec authority brief for mission #883; superseded by ADR `2026-07-14-2`. **MISFILED.** |
| `audits/2026-05-11-findings-vs-issues-update.md`, `audits/2026-05-11-issue-992-984-audit-comments.md`, `audits/2026-05-822-crosscheck.md`, `audits/2026-05-caacs-meta-assessment.md`, `audits/2026-05-phase3-f1-knowledge-capture-plan.md`, `audits/2026-05-phase3-issue-drafts-and-triage.md`, `audits/2026-05-spec-kitty-caacs.md` | `architecture/audits/` | (c) | **`plans/engineering-notes/`** | Seven dated 2026-05 Code-as-a-Crime-Scene forensic audits / triage logs / issue-draft dumps (e.g. "spec-kitty CaaCS Audit — 2026-05", carrying a fork-local absolute path + branch `feat/caacs-doctrine`). Point-in-time reports, not architecture. **MISFILED (whole subdir).** Overlaps **#2227**. |
| `assessments/code-as-a-crime-scene-overview.md` | `architecture/assessments/` | (b)/(c) | **stays (borderline)** | Reads as a durable explainer of the CaaCS method rather than a dated finding; keep unless it is only a pointer to the 2026-05 audits, in which case fold into the audit cluster move. **VERIFY on move.** |
| `feature-detection.md`, `gap-analysis-connector-installation-model.md` | `architecture/` | (b) | **stays (canonical copy)** | Durable design notes; these are the canonical copies (`architecture/index.md` `related:` points here). But each has a **drifted duplicate under `plans/notes/`** — see the shadow-tree finding below. **STAYS; de-dup the shadow copy.** |
| `README-1.x.md`, `README-2.x.md`, `README-3.x.md`, `vision/README-1.x.md`, `vision/README-2.x.md`, `vision/README-3.x.md`, `vision/README.md` | `architecture/` | (d)/(c) | **stays as history slots; distil-then-retire** | Self-described era "history slots" — a deliberate D3 deviation (era belongs to history). Not misfiled, but they are the **#2215** distil-then-retire targets; verify they are not now empty stubs. **Defer to #2215.** |
| `index.md` | `architecture/` | (d) nav | **stays; REFRESH** | Landing page enumerates only **4** of ~60 files (connector-auth, github-app, feature-detection, gap-analysis) — drastically under-indexes the section. The retired ratchet only checked index *existence*, never *completeness*, so nothing catches this. **STAYS; must be regenerated to enumerate the section.** |
| `NAVIGATION_GUIDE.md`, `ARCHITECTURE_DOCS_GUIDE.md`, `explanation-index.md`, `explanation-toc.yml`, `adr-template.md` | `architecture/` | (d) nav/tooling | stays | Nav/meta/tooling. **STAYS PUT.** |

**Verdict:** needs work — 9 firm out-of-zone misfiles (2× `883-*`, 7× `audits/`) → engineering-notes; stale index; one borderline assessment; era READMEs deferred to #2215.

### `plans/` — **MOSTLY CLEAN** (post-#2402), one stale shadow tree

202 files. `plans/engineering-notes/` is the canonical point-in-time home and is correctly
populated; `plans/investigations/`, `plans/doctrine/`, `plans/refactor/`, `plans/reviews/`,
`plans/research/`, `plans/testing/`, `plans/user_journey/` are forward-looking decision-support
(ADR D7) and are in-zone. The defect is a stale shadow tree and a few root-level stragglers.

| File(s) | Current | Bucket | Proposed target | Rationale |
|---|---|---|---|---|
| `plans/notes/feature-detection.md`, `plans/notes/gap-analysis-connector-installation-model.md`, `plans/notes/adr-connector-auth-binding-separation.md` | `plans/notes/` | (c)/(e) | **reconcile + delete-stale (D7)** | `plans/notes/` self-titles "Architecture 1.x Notes" and its `README` only lists `feature-detection.md` — the other two are undocumented strays. All three are **drifted near-duplicates** of canonical copies (396 vs 388 / 540 vs 540 / 179 vs 177 lines) in `architecture/` and `adr/3.x/`; the canonical `architecture/index.md`/`adr` referrers point at the other copies, so these are orphaned split-brain. **MISFILED — retire after confirming the canonical copy is current.** |
| `plans/investigations/2497-external-observability-endpoints-assessment.md`, `plans/investigations/loop-friction-fastfollow-spec.md`, `plans/testing/test-change-coupling-caacs.md`, `plans/glossary-doctrine-overhaul-program.md` | `plans/` (root) | (c) | **regroup into a plans subcluster / engineering-notes** | Loose point-in-time files at `plans/` root rather than nested in a topic cluster; #2402 nested most siblings. **STAYS in zone; regroup only.** |
| everything under `plans/engineering-notes/**`, `plans/investigations/**`, `plans/doctrine/**`, `plans/refactor/**`, `plans/testing/**`, `plans/research/**`, `plans/reviews/**`, `plans/user_journey/**` | `plans/` | (c)/(b) | stays | In-zone forward-looking / point-in-time material. **STAYS.** |

**Verdict:** mostly clean; retire the `plans/notes/` shadow tree; light regroup of root stragglers. Defer structural nesting to **#2402** (done) follow-through.

### `migrations/` — **MOSTLY CLEAN**, one stray closeout

17 files. Durable migration runbooks (`shared-package-boundary-cutover.md`,
`mission-id-canonical-identity.md`, `upgrade-to-0-12-0.md`, `legacy-to-coordination.md`, the
`*-deprecation.md` set, `shim-registry.yaml`) are correctly placed.

| File | Current | Bucket | Proposed target | Rationale |
|---|---|---|---|---|
| `teamspace-mission-state-920-closeout.md` | `migrations/` | (c) | **`plans/engineering-notes/`** | "Closeout evidence for TeamSpace mission-state issue #920, generated from clean workspace `spec-kitty-20260510-…`." A dated mission closeout record, not a reusable migration runbook. **MISFILED (borderline** — carries a migration-note banner; verify it is not the sole runbook for that path before moving). |
| `teamspace-mission-state-repair.md`, `2-1-main-cutover-checklist.md`, `06_migration_and_shim_rules.md` | `migrations/` | (a)/(b) | stays | Durable repair runbook / checklist / rules. `06_`-numbered file is an odd naming residue — normalize name, keep in place. **STAYS.** |

**Verdict:** clean bar one closeout relocation.

### `context/` — **CLEAN** (with a content-consolidation note)

34 files — the glossary/doctrine narrative corpus and the D5 load-bearing glossary read-path
zone. All correctly placed (reference/policy, bucket b). **Not a placement problem**, but note
apparent topic overlap worth a separate content pass (not misfiling): `identity.md` vs
`identity-fields.md`, `governance.md` vs `governance-files.md`. Consolidation candidate only.

### Compact verdicts — remaining sections

| Section | Files | Verdict | Note |
|---|---|---|---|
| `adr/` | 138 | **CLEAN** | Era-organized by design (D3/D6). Residue only: 3 `README.md` lack frontmatter; `*-PROPOSED.md` + non-dated flat-shim names (`adr-connector-auth-binding-separation.md`, `adr-github-app-installation-authority.md`) are the **#2227** census tail — leave to that ticket. |
| `api/` | 23 | **CLEAN** | Reference (bucket b). Minor: both `README.md` and `index.md` present (nav dup). |
| `archive/` | 17 | **CLEAN** | Immutable `1x/`/`2x/` snapshots by design; do not touch. |
| `assets/` | (css/img/html+index) | **CLEAN** | Path-pinned generated/nav (bucket d). Leave pinned. |
| `changelog/` | 2 | **CLEAN placement** | `CHANGELOG.md`+`index.md`. Known dual-maintenance with root `CHANGELOG.md` is **#2302 item 6** (BOM drift); not a placement defect here. |
| `configuration/` | 3 | **CLEAN** | Reference/policy (bucket b). |
| `contracts/` | 3 | **CLEAN** | Registry YAML + index; path-pinned. |
| `core-concepts/` | 1 | **THIN STUB** | Index-only skeleton section (~22 lines). Ratchet-retirement exposure — see governance note. |
| `doctrine/` | 5 | **CLEAN** | How-to + explanation. Minor `README.md`+`index.md` dup. |
| `integrations/` | 1 | **THIN STUB** | Index-only skeleton. |
| `operations/` | 7 | **CLEAN** | Ops runbooks (bucket a/ops) — the **receiving zone** for #2851's `sync-daemon-orphan-cleanup.md` + `internal-hosted-readiness.md`, both present. Do not add contributor how-tos here. |
| `output/` | 1 | **THIN STUB** | Index-only skeleton. |
| `reference/` | 28 | **CLEAN** | Generated `agent_profiles/` + `skills/` projections (bucket d); path-pinned, do-not-hand-edit. |
| `release-goals/` | 4 | **CLEAN** | Declared 14th section (ADR amendment 2026-07-04). Minor `README.md`+`index.md` dup. |
| `security/` | 1 | **THIN STUB** | Index-only skeleton. |
| `templates/` | 1 | **THIN STUB** | Index-only skeleton. |
| `updates/` | 1 | **THIN STUB** | Index-only skeleton. |

---

## Redistribution tally

Mirroring #2851's tally, for the **in-scope** sections:

- **→ `docs/plans/engineering-notes/`:** **9 firm** (`architecture/883-research-synthesis.md`,
  `architecture/883-mission-type-authority-brief.md`, `architecture/audits/*` ×7)
  **+ 2 borderline** (`migrations/teamspace-mission-state-920-closeout.md`,
  `architecture/assessments/code-as-a-crime-scene-overview.md`).
- **→ `docs/operations/`:** **0** — operations is clean and already received #2851's runbooks.
- **→ doctrine tree (`src/doctrine/…`):** **0** in-scope (the stray tactic YAML was in
  `development/`, out of scope).
- **Reconcile + delete-stale (D7):** **3** drifted duplicates in `plans/notes/`
  (feature-detection, gap-analysis-connector-installation-model,
  adr-connector-auth-binding-separation) — de-dup against canonical `architecture/`/`adr/`.
- **Stays / regroup only:** ~15 `architecture/` living-design pages; `plans/` in-zone clusters;
  era-history READMEs (defer #2215); the 4 loose `plans/` root stragglers (regroup).
- **→ `docs/guides/`:** **0 — forbidden by FR-003.**

---

## Candidate follow-up tickets (proposals under #2314 bucket C — NOT filed)

Each inherits the #2851 IA-mechanics obligations: **redirect-map entry** per moved path
(`scripts/docs/redirect_map.yaml`), **relative-link fix** (`relative_link_fixer --check`),
**page-inventory regen** (`page-inventory.yaml` lockfile + `check_docs_freshness --ci`),
**`related:` frontmatter edges** on moved files + referrers, and the **terminology guard**
(`tests/architectural/test_no_legacy_terminology.py`).

1. **Redistribute point-in-time `architecture/` artifacts to engineering-notes** — move
   `architecture/audits/` (7) + `883-research-synthesis.md` + `883-mission-type-authority-brief.md`;
   adjudicate `assessments/code-as-a-crime-scene-overview.md`. **Size M.** **Coordinate/fold
   with #2227** (historical architecture residuals) to avoid double-moving.

2. **Refresh `architecture/index.md` to enumerate the section** — the landing page lists 4 of
   ~60 files; regenerate it to reflect the real section (and the post-move state of ticket 1).
   Nav-only, no file moves. **Size S.** (bucket C/D.)

3. **Retire the `plans/notes/` 1.x shadow tree** — reconcile the 3 drifted duplicates against
   the canonical `architecture/`/`adr/3.x/` copies, then delete-stale (D7); fix the `plans/notes/`
   README + referrers. **Size S.**

4. **Relocate mission-closeout evidence out of `migrations/`** — move
   `teamspace-mission-state-920-closeout.md` → engineering-notes; sweep `migrations/` for other
   dated closeout residue; normalize the `06_`-prefixed filename. **Size S.**

5. **Codify + guard the concern taxonomy (ratchet replacement)** — the durable #2302 deliverable
   below, filed as a bucket-C/E child so the tree cannot silently re-drift. **Size M.**

---

## #2302 recommendation — the durable ratchet replacement

The retired ratchet guarded *section existence + index presence* but never *concern placement*,
which is exactly where the tree drifts. The codified doc-standard directive (#2302) should encode
a **concern-bucket placement taxonomy** and back it with a mechanical check under `scripts/docs/`
(a toolguide + freshness-gated lint), not tribal knowledge:

- **Bucket → canonical section map** (one concern per file):
  - **(c) point-in-time** — dated / mission-scoped / superseded-by-design / audit / synthesis /
    triage / closeout / field-report prose → **only** `docs/plans/engineering-notes/`.
  - **(a) operator/ops runbook** (production-ops-shaped) → `docs/operations/`.
  - **(a/b) contributor how-to / policy** → `docs/development/` (never `guides/` — FR-003).
  - **living architecture / design explanation** → `docs/architecture/` — **no** dated audits,
    mission research dossiers, or era-READMEs beyond the sanctioned history slots.
  - **(e) doctrine artifact (non-page YAML)** → `src/doctrine/…`.
- **Mechanical guards** (the ratchet's durable replacement):
  1. every section has a **non-empty index that enumerates its files** (upgrade the old
     existence-only check to a completeness check — the `architecture/index.md` gap proves the
     need);
  2. **no dated / point-in-time filename pattern** (`^\d{4}-\d{2}`, `*-audit`, `*-report`,
     `*-synthesis`, `*-closeout`, `*-crosscheck`, `*-findings`) outside `plans/engineering-notes/`;
  3. **no two files share a basename across roots** (the `plans/notes/` shadow-tree guard);
  4. **frontmatter contract**: `doc_status` + `updated` required; `type` where the section
     declares it.
- **Thin-stub policy:** the six index-only skeleton sections (`core-concepts`, `integrations`,
  `output`, `security`, `templates`, `updates`) are legitimate Common-Docs placeholders — the
  standard should mark them explicitly `doc_status: draft` skeletons so the completeness guard
  does not false-positive, while still guarding their index presence.

This turns the concern taxonomy this audit applied by hand into the mechanical baseline the
ratchet used to provide — the single durable fix for the drift #2851 exposed section by section.

## Cross-check against tracked work (no duplication)

- **#2227** (~25 historical architecture residuals) — **overlaps ticket 1**; fold/coordinate.
- **#2215** (distil era-suffixed READMEs) — owns the `architecture/README-*.x.md` + `vision/`
  history slots; this audit **defers** to it, proposes nothing fresh there.
- **#2402** (plans restructure, done) — `plans/` is largely clean as a result; ticket 3
  (`plans/notes/` shadow tree) is the residue it did not sweep.
- **#584** (consistency audit, closed) — superseded; not re-opened.
