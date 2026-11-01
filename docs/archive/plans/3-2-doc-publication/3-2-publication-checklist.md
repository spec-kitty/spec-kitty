---
title: Spec Kitty 3.2 Documentation Publication Checklist
description: 'The publication checklist for the Spec Kitty 3.2 documentation refresh (WP14 / FR-021): the steps the docs release engineer runs before publishing.'
doc_status: deprecated
updated: '2026-08-12'
related:
- docs/context/index.md
- docs/archive/plans/3-2-doc-publication/3-2-archive-migration-plan.md
- docs/archive/plans/3-2-doc-publication/3-2-cli-reference-audit-meta-issues.md
- docs/archive/plans/3-2-doc-publication/3-2-cli-reference-methodology.md
- docs/archive/plans/3-2-doc-publication/3-2-harness-research-method.md
- docs/archive/plans/3-2-doc-publication/3-2-information-architecture.md
- docs/archive/plans/3-2-doc-publication/3-2-navigation-plan.md
- docs/plans/3-2-doc-publication/3-2-version-taxonomy.md
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# Spec Kitty 3.2 Documentation Publication Checklist

**Mission:** `spec-kitty-3-2-docs-01KS4KSZ` (WP14 / FR-021)
**Owner:** docs release engineer
**Audience:** anyone driving the public 3.2 docs cut to `https://docs.spec-kitty.ai`

This checklist is the final gate before publishing the 3.2 docs site. It binds every
`spec.md` acceptance scenario, success criterion, and NFR to a concrete evidence
artifact (page, test, workflow, freshness rule, or meta-issue), enumerates the CI
runs that must be green, walks the release engineer through manual review, lists
the dispatch path for blocking meta-issues, and provides a concrete rollback plan.

The mission has **25 gates** (9 acceptance scenarios + 7 success criteria + 9
NFRs). Every gate appears in §1 with a citation and status. Coverage of every
workstream, every (tool × OS) install cell, and the harness support matrix is
cross-checked at the end (§6).

> **Reading this for the first time?** Start with §1 to see what must be true
> before publish, then §3 (manual review) for the walk-through, then §6
> (coverage cross-check) to confirm nothing slipped between planning and
> execution. §2, §4, and §5 are referenced as needed during the actual cut.

---

## §1. Pre-flight gates

### §1a. Acceptance scenarios (S1–S9, from spec.md §"Acceptance Scenarios")

| # | Scenario | Evidence artifact | Verification command | Status |
|---|----------|-------------------|----------------------|--------|
| **S1** | Version separation at the entry page — 3.2 lands as `current`; 1.x/2.x is archive/migration. | [`docs/context/index.md`](../../../context/index.md) (3.2 landing page from WP04), [`docs/development/3-2-version-taxonomy.md`](../../../development/reference/version-taxonomy.md), [`docs/development/3-2-navigation-plan.md`](3-2-navigation-plan.md), archive-notice banners enforced by [`scripts/docs/version_leakage_check.py`](../../../../scripts/docs/version_leakage_check.py) (`LEAK-*` rules). | `SPEC_KITTY_ENABLE_SAAS_SYNC=1 SPEC_KITTY_NO_UPGRADE_CHECK=1 PYTHONPATH=. uv run python scripts/docs/check_docs_freshness.py --ci --link-check none` | TBD |
| **S2** | CLI reference parity — every visible Typer path (192 per `cli-audit-3-2.md`) is referenced or explicitly classified. | [`docs/api/cli-commands.md`](../../../api/cli-commands.md) (rebuilt in WP06/WP07), [`docs/development/3-2-cli-reference-methodology.md`](3-2-cli-reference-methodology.md), parity test [`tests/architectural/test_docs_cli_reference_parity.py`](../../../../tests/architectural/test_docs_cli_reference_parity.py). | `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run pytest tests/architectural/test_docs_cli_reference_parity.py -q` | TBD |
| **S3** | CLI help truthfulness — every help/code/test mismatch lands in `3-2-cli-reference-audit-meta-issues.md`, never silently in docs. | [`docs/development/3-2-cli-reference-audit-meta-issues.md`](3-2-cli-reference-audit-meta-issues.md) (6 seeded rows, schema enforced by [`kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md`](../../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md#metaissueentry)). | Grep the docs tree for changes that could have masked a meta-issue: `git log --oneline docs/api/ docs/guides/ docs/guides/ | head` then cross-check that every change has a row here. | TBD |
| **S4** | Divio coverage for the end-user journey — tutorial, how-to, reference, explanation for each of {install, first mission, charter, multi-harness, recovery}. | [`docs/development/3-2-information-architecture.md`](3-2-information-architecture.md) IA matrix; populated under [`docs/guides/`](../../../guides), [`docs/guides/`](../../../guides), [`docs/api/`](../../../api), [`docs/architecture/`](../../../architecture) (WP08/WP11/WP12). | `ls docs/guides docs/guides docs/api docs/architecture` and cross-reference with the IA matrix. | TBD |
| **S5** | Per-harness reachability — every first-class harness has a setup+usage page with citation to its current external docs. | [`docs/guides/harnesses/`](../../../guides/how-to/harnesses) (14 harness pages from WP11), [`docs/development/3-2-harness-research-method.md`](3-2-harness-research-method.md), harness support matrix (WP10). | Each harness page must contain at least one external doc URL: `grep -lE "^- \[.*\]\(https://" docs/guides/harnesses/*.md`. Run the freshness orchestrator with `--link-check spot` to validate URLs resolve. | TBD |
| **S6** | Cross-platform install lifecycle — pip/pipx/uv × macOS/Linux/Windows install/upgrade/uninstall, with PATH/PowerShell coverage. | [`docs/guides/install-and-upgrade.md`](../../../guides/how-to/installation/install-and-upgrade.md), [`docs/guides/install-macos.md`](../../../guides/how-to/installation/install-macos.md), [`docs/guides/install-linux.md`](../../../guides/how-to/installation/install-linux.md), [`docs/guides/install-windows.md`](../../../guides/how-to/installation/install-windows.md), [`docs/guides/upgrade-cli.md`](../../../guides/how-to/installation/upgrade-cli.md), [`docs/guides/uninstall.md`](../../../guides/how-to/installation/uninstall.md), [`docs/guides/diagnose-installation.md`](../../../guides/how-to/installation/diagnose-installation.md) (WP12). | `for f in docs/guides/install-macos.md docs/guides/install-linux.md docs/guides/install-windows.md; do grep -E "pip\|pipx\|uv" "$f" >/dev/null && echo "$f OK"; done` plus a `spec-kitty --version` smoke run on each OS surface. | TBD |
| **S7** | No mixed-version leakage in current pages — pages tagged `current` never link to `archival` without a banner. | [`docs/development/3-2-page-inventory.yaml`](../../../development/page-inventory.yaml), [`docs/development/3-2-archive-migration-plan.md`](3-2-archive-migration-plan.md), enforced by `scripts/docs/version_leakage_check.py` (`LEAK-CURRENT-TO-ARCHIVAL`, `LEAK-MISSING-BANNER`). | `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run python scripts/docs/check_docs_freshness.py --ci --link-check none` (zero `LEAK-*` findings required). | TBD |
| **S8** | Plan-only gate respected — no live docs edits during specify/plan/tasks. | Git history check: planning commits touched only `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/**`; execution commits (WP01–WP14) touched `docs/`, `scripts/docs/`, `.github/workflows/docs-freshness.yml`, `tests/architectural/test_docs_cli_reference_parity.py`. | `git log --oneline kitty/mission-spec-kitty-3-2-docs-01KS4KSZ..HEAD -- docs/ scripts/docs/ .github/workflows/docs-freshness.yml tests/architectural/test_docs_cli_reference_parity.py` | PASS (no planning commits touched live docs; gate satisfied at planning time per C-001/C-002.) |
| **S9** | Workspace operating-rule compliance — no SaaS/tracker/hosted-auth/sync flows ran during planning; later execution uses `SPEC_KITTY_ENABLE_SAAS_SYNC=1`. | Freshness workflow `.github/workflows/docs-freshness.yml` (deleted per PROGRAM.md §2 / planning#57 — this repo runs no GitHub Actions) set `SPEC_KITTY_ENABLE_SAAS_SYNC=1`; methodology note [`docs/development/3-2-cli-reference-methodology.md`](3-2-cli-reference-methodology.md) requires the flag during capture. | Historical: inspect this checklist's own record of the workflow env block. | TBD |

### §1b. Success criteria (SC1–SC7, from spec.md §"Success Criteria")

| # | Criterion | Evidence artifact | Verification command | Status |
|---|-----------|-------------------|----------------------|--------|
| **SC1** | A new adopter on macOS runs their first mission in under 30 minutes following only the new tutorials and how-tos. | [`docs/guides/getting-started.md`](../../../guides/tutorials/getting-started.md), [`docs/guides/your-first-mission.md`](../../../guides/tutorials/your-first-mission.md), [`docs/guides/install-macos.md`](../../../guides/how-to/installation/install-macos.md), [`docs/guides/harnesses/claude-code.md`](../../../guides/how-to/harnesses/claude-code.md). | Manual timed walk-through on macOS (§3 manual review item). | TBD |
| **SC2** | A user upgrading from 3.1 or 2.x reaches a green `spec-kitty verify-setup` (or current-3.2 equivalent) without consulting code. | [`docs/guides/upgrade-cli.md`](../../../guides/how-to/installation/upgrade-cli.md), [`docs/guides/upgrade-project.md`](../../../guides/how-to/installation/upgrade-project.md), [`docs/development/3-2-archive-migration-plan.md`](3-2-archive-migration-plan.md). | Run `spec-kitty verify-setup` (or `spec-kitty doctor`) following only the upgrade how-tos. | TBD |
| **SC3** | A CLI consumer can find an accurate reference entry for every command they invoke; missing reference entries count as zero in the freshness check. | [`docs/api/cli-commands.md`](../../../api/cli-commands.md) rebuild (WP07) + parity test [`tests/architectural/test_docs_cli_reference_parity.py`](../../../../tests/architectural/test_docs_cli_reference_parity.py) (WP06) + [`scripts/docs/check_cli_reference_freshness.py`](../../../../scripts/docs/check_cli_reference_freshness.py) (`REF-*`/`HELP-*` rules). | `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run python scripts/docs/check_docs_freshness.py --ci --link-check none` (zero `REF-MISSING-PATH` findings). | TBD |
| **SC4** | A docs reviewer confirms version-leakage compliance in under 10 minutes using the FR-005 validation mechanism plus this checklist. | [`scripts/docs/version_leakage_check.py`](../../../../scripts/docs/version_leakage_check.py), [`docs/development/3-2-page-inventory.yaml`](../../../development/page-inventory.yaml). | Same orchestrator command as S7; output must be a single PASS line for the reviewer. | TBD |
| **SC5** | A harness user finds documentation that cites the host's own current docs and matches the files Spec Kitty installs into the host directory. | [`docs/guides/harnesses/*.md`](../../../guides/how-to/harnesses) (14 harness pages) + the agent-directory table in repo-root `CLAUDE.md` / `AGENTS.md` reflected in the per-harness pages. | Spot-check 3 random harness pages (§3 manual review item) and confirm: (a) cited external doc URL resolves, (b) page describes the directory the harness installs into. | TBD |
| **SC6** | After publication, the only place CLI/help mismatches live is `3-2-cli-reference-audit-meta-issues.md`; no silent doc-side fixes exist. | Meta-issue file plus the test [`tests/architectural/test_docs_cli_reference_parity.py`](../../../../tests/architectural/test_docs_cli_reference_parity.py) which fails if a doc fix masks a help mismatch. | Cross-check meta-issue rows against `docs/api/cli-commands.md` revision diffs; the test should pass. | TBD |
| **SC7** | Install, upgrade, uninstall coverage is complete: at least one verified command path per (pip / pipx / uv) × (macOS / Linux / Windows) cell. | WP12 install lifecycle pages (see S6 cell), plus verification commands in each page. | Section §6c (install matrix cross-check) must show every cell pointing to a how-to page. | TBD |

### §1c. Non-functional requirements (NFR-001..NFR-009, from spec.md §"Non-Functional Requirements")

| # | NFR | Enforcement / evidence | Verification command | Status |
|---|-----|------------------------|----------------------|--------|
| **NFR-001** | CLI reference matches live tree at publication. Zero unclassified visible paths; zero reference entries for paths absent from the live tree; freshness check green in CI. | Parity test [`tests/architectural/test_docs_cli_reference_parity.py`](../../../../tests/architectural/test_docs_cli_reference_parity.py) + freshness orchestrator [`scripts/docs/check_docs_freshness.py`](../../../../scripts/docs/check_docs_freshness.py) (sub-check `check_cli_reference_freshness`). | `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run pytest tests/architectural/test_docs_cli_reference_parity.py -q` and `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run python scripts/docs/check_docs_freshness.py --ci --link-check none`. | TBD |
| **NFR-002** | Version leakage in current pages must be zero. | [`scripts/docs/version_leakage_check.py`](../../../../scripts/docs/version_leakage_check.py) (`LEAK-*` rules) inside the freshness orchestrator. | Same as NFR-001 freshness orchestrator command; require zero `LEAK-*` findings. | TBD |
| **NFR-003** | Cross-platform install instructions must be exercisable. Every (tool × OS) cell has a verifiable install command and a `spec-kitty --version` check. | WP12 pages (see S6/SC7); install matrix cross-checked in §6c. | Run `spec-kitty --version` after following each cell's install command on the matching OS. | TBD |
| **NFR-004** | Harness pages must cite current external host docs. Broken citations block publication. | WP11 harness pages cite per harness in `## References`; freshness orchestrator's `--link-check spot` or `--link-check full` HEAD-tests external URLs. | `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run python scripts/docs/check_docs_freshness.py --ci --link-check full --report freshness.json` then `jq '.findings[] | select(.code | startswith("LINK"))' freshness.json` (zero findings required). | TBD |
| **NFR-005** | Meta-issue capture must precede docs publication. Every CLI/help mismatch lands as a row before the reference page is republished. | [`docs/development/3-2-cli-reference-audit-meta-issues.md`](3-2-cli-reference-audit-meta-issues.md); §4 below gates publish on resolution of every BLOCKING row. | Read §4 dispatch path; confirm zero `blocking_status: blocking` rows remain unresolved. | TBD |
| **NFR-006** | Planning-phase artifacts must not modify live docs. | Same git-log check as S8; same path filter. | `git log --oneline main..kitty/mission-spec-kitty-3-2-docs-01KS4KSZ -- docs/ ':!docs/development/3-2-*'` (must be empty for planning commits — only execution commits touch live docs). | PASS (gate satisfied at planning per C-001/C-002.) |
| **NFR-007** | Operator readability of the harness support matrix — single page, 5 tiers, every harness from FR-014 listed. | [`docs/development/3-2-harness-research-method.md`](3-2-harness-research-method.md) + harness support matrix page (WP10). | Open the harness support matrix, count tiers (5 expected), and confirm every harness from `docs/guides/harnesses/` appears in exactly one tier. | TBD |
| **NFR-008** | Reference pages must be discoverable from the public URL — `docs/api/cli-commands.md` reachable at `https://docs.spec-kitty.ai/reference/cli-commands.html` after the docs build. | [`docs/toc.yml`](../../../toc.yml) (root nav), [`docs/api/toc.yml`](../../../api/toc.yml), DocFX build via `.github/workflows/docs-pages.yml`. | Build the docs site locally (DocFX) and visit `_site/reference/cli-commands.html`; after the publish workflow runs, visit the public URL. | TBD |
| **NFR-009** | Plan artifacts honour charter policy (typer/rich/ruamel.yaml/pytest/mypy --strict, ≥90% coverage). | Tooling proposed by the mission uses the charter stack: parity test is pytest; freshness orchestrator is stdlib Python; meta-issue file is plain markdown. | `spec-kitty charter context --action implement --json` and confirm no plan tooling violates the policy summary. | PASS (gate satisfied at planning per C-009 and verified by FR-020 freshness orchestrator design — only typer/pytest/ruamel.yaml/stdlib tooling introduced.) |

> **Status legend:** `PASS` — verified at planning time and cannot regress between planning and publish. `TBD` — must be verified by the release engineer in §3 before flipping to PASS. `BLOCKED` — depends on an unresolved meta-issue or external dependency; see §4.

---

## §2. CI checks (must be green before publish)

| Workflow / test | Trigger | What it proves | How to inspect |
|-----------------|---------|----------------|----------------|
| **`docs-freshness`** (`.github/workflows/docs-freshness.yml`, from WP13 — deleted per PROGRAM.md §2 / planning#57, this repo runs no GitHub Actions) | `pull_request`, `push` to `main` | Ran the freshness orchestrator with `SPEC_KITTY_ENABLE_SAAS_SYNC=1` and `--link-check none`; uploaded `freshness.json` as an artifact. Validated LEAK-*, REF-*, HELP-*, and inventory completeness. | Run the freshness orchestrator locally instead: `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run python scripts/docs/check_docs_freshness.py --ci --link-check none`. |
| **`tests/architectural/test_docs_cli_reference_parity.py`** (from WP06) | Part of the architectural-tests run inside `ci-quality.yml` and pre-merge `pytest` | Confirms every visible Typer path (with SaaS sync on) appears in `docs/api/cli-commands.md`, and every reference entry is either visible or classified in the meta-issue file. | `SPEC_KITTY_ENABLE_SAAS_SYNC=1 PYTHONPATH=. uv run pytest tests/architectural/test_docs_cli_reference_parity.py -q` |
| **`ci-quality.yml`** (existing) | `pull_request`, `push` | Runs ruff, mypy --strict, full pytest suite (including the parity test), clean-install verification. Assumed green at publish time. | `gh run list --workflow=ci-quality.yml --limit=5` |
| **`docs-pages.yml`** (existing publish workflow) | manual / on tag | Builds DocFX site and deploys to GitHub Pages. Must be triggered after all the above are green. | `gh workflow run docs-pages.yml` (or follow the existing manual-trigger procedure). |

Publish is **blocked** if any of the first three are red. The fourth is the action that publishes.

---

## §3. Manual review checklist (release engineer)

Walk through every item below in order. Each item maps to one or more gates in §1.
Tick items off in your release PR or release notes. If any item fails, do not
proceed to §2 step 4 (the publish workflow trigger).

1. **Archive-notice cross-link spot-check (S1, S7, NFR-002).** Open 5 random pages tagged `current` in `docs/development/3-2-page-inventory.yaml`. For each, walk every outbound link and confirm: if it points to an `archival`-tagged page, the link is wrapped in an archive/migration banner per the FR-005 validation rule. Record the 5 paths reviewed in the publish PR description.
2. **3.2 landing page link from root README (S1, S4).** Open the repo-root `README.md`. Confirm a link to the 3.2 landing page (e.g., `docs/context/index.md` or its rendered URL `https://docs.spec-kitty.ai/3x/`) appears prominently. If absent, file a doc fix before publishing.
3. **CLI reference cross-link reachable (S2, NFR-008).** From the 3.2 landing page, navigate to `docs/api/cli-commands.md` in two clicks or fewer. Then visit the rendered URL `https://docs.spec-kitty.ai/reference/cli-commands.html` after the publish workflow runs.
4. **`spec-kitty --version` in install how-tos (S6, NFR-003).** Run `spec-kitty --version` locally and confirm the output (e.g., `spec-kitty, version 3.2.0rc22`) is shown verbatim or as a placeholder pattern in `docs/guides/install-macos.md`, `install-linux.md`, and `install-windows.md`. Verify each install how-to documents the `--version` check as the post-install smoke step.
5. **`docs/archive/` navigation entry exists (S1, S7).** Confirm `docs/archive/` (or the chosen archive root per WP09's archive plan) is present and reachable from `docs/toc.yml`. Open the archive landing in a browser and confirm 1.x and 2.x pages display the archive banner.
6. **Random harness external doc URLs still resolve (S5, NFR-004).** Open 3 random files under `docs/guides/harnesses/`. For each, click every external URL in the `References` section and confirm the page loads (HTTP 200). If any URL 404s, file a meta-issue row before publishing.
7. **Meta-issue file has zero unresolved BLOCKING rows (S3, NFR-005).** Open `docs/development/3-2-cli-reference-audit-meta-issues.md` and confirm every row with `blocking_status: blocking` either has been flipped to `resolved` or has a §4 dispatch entry below explaining the accepted non-blocking deferral.
8. **Run the freshness orchestrator locally (S1, S2, S3, S5, S7, NFR-001, NFR-002, NFR-004).** Execute:
   ```
   SPEC_KITTY_ENABLE_SAAS_SYNC=1 SPEC_KITTY_NO_UPGRADE_CHECK=1 PYTHONPATH=. \
     uv run python scripts/docs/check_docs_freshness.py --ci --link-check spot --report /tmp/freshness.json
   ```
   Exit code must be `0`. Inspect `/tmp/freshness.json` for any `severity: error` findings (must be empty).
9. **Build docs site locally with DocFX and walk new 3.2 nav groups (S1, S4, NFR-008).** Run the local DocFX build (`docfx docs/docfx.json`). Walk the new 3.2 nav groups in `_site/` and confirm: (a) 3.2 current group is the top-level entry, (b) archive groups for 1.x and 2.x exist and are clearly framed, (c) every harness page is reachable from the harnesses nav group.
10. **CHANGELOG / release notes reference the docs refresh (NFR-005).** Confirm the upcoming `CHANGELOG.md` entry for the 3.2 release explicitly mentions the docs refresh and links to this mission (`spec-kitty-3-2-docs-01KS4KSZ`).

---

## §4. Meta-issue dispatch path

Every row in `docs/development/3-2-cli-reference-audit-meta-issues.md` with
`blocking_status: blocking` must be **resolved** (fix landed, row flipped to
`resolved`) or **explicitly accepted as `non_blocking`** with a named owner and a
tracker placeholder before publish.

At checklist authoring time, three rows are blocking:

| Row | Command path | Owner area | Recommended fix | Dispatch (resolve before publish) |
|-----|--------------|------------|-----------------|------------------------------------|
| 1 | `spec-kitty implement` | `core` | Drop the `Internal -` prefix from the help text (or hide the command and route users via `spec-kitty agent action implement` exclusively). Help text and docs must align. | Owner: maintainers (core CLI surface). Track as an upstream issue (`Priivacy-ai/spec-kitty` core surface tracker). Resolution: either land the help-text fix and flip this row to `resolved`, or flip to `non_blocking` with a clear deferral note pointing at the upstream issue. |
| 2 | `spec-kitty agent context update-context` | `docs` | Remove every doc reference and replace with `agent context resolve`; add a migration note for operators on older tutorials. | Owner: maintainers (docs). Track as an in-mission fix during WP07 follow-up or a fast-follow docs sweep. Resolution: confirm `docs/api/agent-subcommands.md`, `docs/guides/missions-overview.md`, and `docs/guides/claude-code-workflow.md` no longer reference `update-context`; flip to `resolved`. |
| 3 | `spec-kitty agent workflow implement` | `docs` | Rewrite affected how-tos and skill prompts to use `spec-kitty agent action implement`; optionally add a deprecation alias if external automation depends on the old name. | Owner: maintainers (docs + skills). Track as an upstream issue if the alias decision lands in code; otherwise track as a docs fast-follow. Resolution: grep `docs/` and `.claude/`, `.agents/skills/`, etc., for `agent workflow implement`; replace; flip to `resolved`. |

The three remaining `non_blocking` rows (`agent feature`/`agent workflow`,
`mission switch`/`mission-type switch`, `agent profile` vs `agent profile list`)
do not gate publish but must be retained in the file for the audit trail.

**Process to add a new BLOCKING row during release:**

1. Append a row to `3-2-cli-reference-audit-meta-issues.md` with all 9 required fields.
2. Either resolve before publish (fix lands, row becomes `resolved`) or land an accepted-non-blocking decision (with an owner and tracker URL) and flip to `non_blocking`.
3. Re-run the freshness orchestrator (§3 step 8) and confirm the new row does not produce a `REF-*` or `HELP-*` finding.

---

## §5. Rollback plan

If a regression slips into the live site after publish, follow these concrete
steps. Do not improvise — the goal is a clean revert to the last known-good
site commit, then a re-cut from a clean state.

### §5a. Identify the last-known-good site commit

```bash
# From repo root, list the most recent docs-touching commits on main:
git log --oneline -- docs/
# Note the commit SHA immediately before the regression-introducing commit.
# That is your <last-good-sha>.
```

### §5b. Revert the docs publish commit(s)

```bash
# Create a new branch from main to do the revert work:
git checkout -b kitty/docs/rollback-3-2-publish main

# Revert the range from the bad commit up to and including HEAD on main.
# Use the publish commit as <publish-sha>:
git revert <publish-sha>..HEAD

# Open a PR (gh pr create) and land it through normal review. Do NOT force-push to main.
```

If multiple commits need reverting, use `git revert --no-commit <range>` and
commit them as a single revert PR for atomic rollback.

### §5c. Force-redeploy via the publish workflow

```bash
# After the revert PR lands on main, re-run the publish workflow manually:
gh workflow run docs-pages.yml --ref main

# Monitor:
gh run list --workflow=docs-pages.yml --limit=1
gh run watch <run-id>
```

### §5d. Communicate via the release-readiness workflow

1. Comment on the regression-introducing PR with the revert SHA and a 1-line cause summary.
2. Post in the release-readiness channel (or whichever shipped-comms surface is current) referencing the revert PR, the affected pages, and the ETA for the re-cut.
3. Open a new meta-issue row in `docs/development/3-2-cli-reference-audit-meta-issues.md` (if the regression is a CLI/help mismatch) or a tracker ticket (if it's a docs-only regression) before the next publish attempt.

### §5e. Re-cut from clean state

Once the revert is live and verified:

1. Fix the regression in a new branch (`kitty/docs/3-2-publish-retry`).
2. Re-walk this entire checklist (§1 → §3) before retriggering `docs-pages.yml`.
3. Do not skip §3 step 8 (freshness orchestrator) — that is the gate that should have caught the regression the first time.

---

## §6. Coverage cross-check

This section confirms the checklist names a specific evidence artifact for
every gate, every workstream, every install cell, and the harness matrix. It is
the matrix this checklist exists to prove.

### §6a. Acceptance scenarios → owning WP

| Scenario | WP(s) | Notes |
|----------|-------|-------|
| **S1** Version separation | WP01 (taxonomy), WP02 (page inventory), WP03 (FR-003 mechanism decision), WP04 (navigation plan + 3.2 landing), WP13 (leakage check enforcement) | WP04 owns the 3.2 landing surface; WP13 enforces in CI. |
| **S2** CLI reference parity | WP05 (methodology), WP06 (audit + parity test), WP07 (rebuilt reference) | Live tree vs reference, with `SPEC_KITTY_ENABLE_SAAS_SYNC=1`. |
| **S3** CLI help truthfulness | WP06 (meta-issue capture), WP07 (does not silently fix) | Meta-issue file is the single sink for mismatches. |
| **S4** Divio coverage | WP08 (IA), WP11 (harness pages), WP12 (install lifecycle), WP10 (harness matrix) | IA matrix drives every required page. |
| **S5** Per-harness reachability | WP10 (harness research method + matrix), WP11 (14 harness pages) | Matrix is the operator-facing surface; pages are the per-harness depth. |
| **S6** Cross-platform install lifecycle | WP12 (install/upgrade/uninstall outline + pages) | See §6c install matrix. |
| **S7** No mixed-version leakage | WP02 (inventory), WP09 (archive plan), WP13 (leakage check) | Inventory + automated check. |
| **S8** Plan-only gate respected | All planning WPs (specify/plan/tasks workflow) — satisfied at planning, locked by C-001/C-002. | Audited via git-log path filter. |
| **S9** Workspace operating-rule compliance | WP13 (freshness orchestrator uses `SPEC_KITTY_ENABLE_SAAS_SYNC=1`), WP05 (methodology uses the flag) | Flag must be in effect at capture and CI time. |

### §6b. Success criteria → artifact

| Criterion | Owning artifact |
|-----------|-----------------|
| **SC1** First mission in < 30 min on macOS | [`docs/guides/getting-started.md`](../../../guides/tutorials/getting-started.md), [`docs/guides/your-first-mission.md`](../../../guides/tutorials/your-first-mission.md), [`docs/guides/install-macos.md`](../../../guides/how-to/installation/install-macos.md), claude-code harness page. |
| **SC2** Upgrader reaches green verify-setup | [`docs/guides/upgrade-cli.md`](../../../guides/how-to/installation/upgrade-cli.md), [`docs/guides/upgrade-project.md`](../../../guides/how-to/installation/upgrade-project.md). |
| **SC3** CLI consumer finds accurate reference | [`docs/api/cli-commands.md`](../../../api/cli-commands.md) + parity test. |
| **SC4** Docs reviewer confirms leakage compliance < 10 min | This checklist + [`scripts/docs/version_leakage_check.py`](../../../../scripts/docs/version_leakage_check.py). |
| **SC5** Harness user finds host-matching docs | [`docs/guides/harnesses/*.md`](../../../guides/how-to/harnesses). |
| **SC6** No silent doc-side CLI/help fixes | [`docs/development/3-2-cli-reference-audit-meta-issues.md`](3-2-cli-reference-audit-meta-issues.md) + parity test. |
| **SC7** Full install matrix coverage | WP12 install pages — see §6c. |

### §6c. Install matrix (pip / pipx / uv × macOS / Linux / Windows)

Every cell must point to at least one how-to page (named in §3 step 4).

|         | **macOS**                                                                                 | **Linux**                                                                                 | **Windows**                                                                                  |
|---------|-------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| **pip** | [`docs/guides/install-macos.md`](../../../guides/how-to/installation/install-macos.md) §pip                          | [`docs/guides/install-linux.md`](../../../guides/how-to/installation/install-linux.md) §pip                          | [`docs/guides/install-windows.md`](../../../guides/how-to/installation/install-windows.md) §pip (PowerShell + PATH)     |
| **pipx**| [`docs/guides/install-macos.md`](../../../guides/how-to/installation/install-macos.md) §pipx                         | [`docs/guides/install-linux.md`](../../../guides/how-to/installation/install-linux.md) §pipx                         | [`docs/guides/install-windows.md`](../../../guides/how-to/installation/install-windows.md) §pipx (PowerShell + PATH)    |
| **uv**  | [`docs/guides/install-macos.md`](../../../guides/how-to/installation/install-macos.md) §uv                           | [`docs/guides/install-linux.md`](../../../guides/how-to/installation/install-linux.md) §uv                           | [`docs/guides/install-windows.md`](../../../guides/how-to/installation/install-windows.md) §uv (PowerShell + py-launcher)|

Cross-cutting: [`docs/guides/install-and-upgrade.md`](../../../guides/how-to/installation/install-and-upgrade.md), [`docs/guides/upgrade-cli.md`](../../../guides/how-to/installation/upgrade-cli.md), [`docs/guides/uninstall.md`](../../../guides/how-to/installation/uninstall.md), [`docs/guides/diagnose-installation.md`](../../../guides/how-to/installation/diagnose-installation.md). Each cell must have a `spec-kitty --version` verification step (NFR-003). Manual review step §3.4 enforces this.

### §6d. Harness support matrix (WP10)

The harness support matrix from WP10 lists every harness in `docs/guides/harnesses/`:
amazon-q, augment, claude-code, codex, copilot, cursor, gemini, kilocode, kiro,
opencode, pi-tui, qwen, roo, windsurf (14 pages). Manual review step §3.6 spot-checks
3 random pages; NFR-007 confirms the matrix renders 5 tiers on a single page.
This checklist references the matrix via S5 (gate), SC5 (criterion), and NFR-007
(rendering). Coverage confirmed.

### §6e. NFR enforcement

| NFR | Enforcement |
|-----|-------------|
| NFR-001 | Parity test + freshness orchestrator (`REF-*`/`HELP-*`). |
| NFR-002 | Freshness orchestrator (`LEAK-*`). |
| NFR-003 | Install matrix §6c + §3.4 manual review. |
| NFR-004 | Freshness orchestrator `--link-check` + §3.6 manual review. |
| NFR-005 | Meta-issue file + §4 dispatch path. |
| NFR-006 | git-log path filter (planning vs execution). |
| NFR-007 | Harness support matrix single-page render. |
| NFR-008 | DocFX local build (§3.9) + public URL check (§3.3). |
| NFR-009 | Charter context policy summary (`spec-kitty charter context --action implement --json`). |

### §6f. Workstream cross-check (A–F)

The mission spans six workstreams. Each must be represented by at least one
checklist item.

| Workstream | Scope | Checklist coverage |
|------------|-------|--------------------|
| **A. Version taxonomy + inventory** | FR-001, FR-002, FR-005, FR-013 | §1 S1, S7; §3 step 1, 5; §6a S1, S7. |
| **B. CLI reference rebuild** | FR-006, FR-007, FR-008, FR-009, FR-010 | §1 S2, S3, SC3; §2 parity test row; §3 step 7; §6a S2, S3. |
| **C. Information architecture + Divio** | FR-011, FR-012 | §1 S4; §3 step 9; §6a S4. |
| **D. Harness research + per-harness pages** | FR-014, FR-015, FR-016 | §1 S5, SC5, NFR-007; §3 step 6; §6d harness matrix. |
| **E. Install / upgrade / uninstall lifecycle** | FR-017, FR-018, FR-019 | §1 S6, SC7, NFR-003; §3 step 4; §6c install matrix. |
| **F. Validation + publication** | FR-020, FR-021 | §1 NFR-001, NFR-002, NFR-004; §2 docs-freshness workflow; §3 steps 7, 8, 10; §4 dispatch path; §5 rollback; this entire checklist. |

### §6g. Harness page coverage (WP11)

For NFR-007 (single-page support matrix) and SC5 (host-matching docs), confirm
each harness from FR-014 has both a tier in the matrix and a setup+usage page.
The 14 pages under `docs/guides/harnesses/` cover: Claude Code, Codex, OpenCode,
Cursor, Gemini, Pi TUI, Qwen Code, Amazon Q (Kiro retains legacy `amazon-q.md`
plus dedicated `kiro.md`), GitHub Copilot, Augment, Roo, Kilo Code, Windsurf.
Google Antigravity, Mistral Vibe, and Letta Code are tracked in the support
matrix (WP10) per the spec's deferred-decision resolution; if they are first-class
at publish, a corresponding page must be added before flipping S5 to PASS.

---

## §7. Sign-off

When every row in §1 reads `PASS`, every item in §3 is ticked, every BLOCKING
meta-issue is `resolved` or accepted as `non_blocking` (§4), and CI is green
(§2), the release engineer signs off here in the publish PR description:

```
[ ] §1 pre-flight gates (25/25 PASS)
[ ] §2 CI checks green (docs-freshness, parity test, ci-quality)
[ ] §3 manual review complete (10/10 ticked)
[ ] §4 meta-issue dispatch resolved (0 blocking rows unresolved)
[ ] §5 rollback plan understood (no rollback required, plan ready if needed)
[ ] §6 coverage cross-check verified (no uncovered gates, workstreams, install cells, or harness pages)

Release engineer: <name>
Publish date: <ISO timestamp>
Publish PR: <gh pr URL>
Publish workflow run: <gh run URL>
```

After sign-off, trigger `docs-pages.yml`. The publish is live when the workflow
completes green and §3.3 (public URL reachability check) returns 200 for both
the 3.2 landing page and `https://docs.spec-kitty.ai/reference/cli-commands.html`.
