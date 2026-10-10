---
title: Terminology Guard Exemption Policy
description: "Policy for the six surfaces exempt from spec-kitty terminology guards: ADRs, migrations, archived pages, archival plans, dated reports and the Unreleased-only CHANGELOG scan."
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/maintainer.md
type: reference
related: []
---

# Terminology Guard Exemption Policy

This document describes the surfaces deliberately excluded from the two active
terminology drift guards:

- `tests/contract/test_terminology_guards.py` — live-doc scan for deprecated CLI
  option names and removed command patterns
- `tests/architectural/test_no_legacy_terminology.py` — repo-wide scan for
  specific forbidden legacy terms

These exclusions are **intentional policy decisions**, not workarounds. The
rationale for each exempt surface is recorded here so future contributors can
distinguish "this surface is correctly out of scope" from "this surface was
accidentally missed."

## Background

The terminology guards enforce that active, first-party surfaces — source code,
doctrine skills, and live documentation — stay aligned with the canonical
vocabulary. They scan live surfaces only; surfaces that are historical records or
archival snapshots are deliberately out of scope.

Six categories of surfaces are currently exempt from the live-doc component of
the guards. Each is described below.

---

## Exempt Surface 1: `docs/adr/` — Immutable Architectural Decision Records

### What is excluded

All files under `docs/adr/` are excluded from:

- the live-doc scan in `_live_doc_scan_targets()` in
  `tests/contract/test_terminology_guards.py`
- the legacy-term scan `_EXCLUDED_PATH_FRAGMENTS` in
  `tests/architectural/test_no_legacy_terminology.py`

### Why it is exempt

Architectural Decision Records (ADRs) are immutable, byte-invariant snapshots by
convention (NFR-001/C-002/C-006). An ADR records the reasoning behind a decision
at a specific point in time. Once an ADR is written, its body is never modified —
even if the vocabulary it uses has since been superseded. Retroactively altering
an ADR body would corrupt the historical record and undermine the purpose of
decision documentation.

The `docs/adr/` tree was relocated from `architecture/` (which was already
outside the scan perimeter) into `docs/` during the Common Docs consolidation
(mission doc-quality-hardening). The exemption was carried over so that the
relocation did not introduce spurious guard failures on files that are
intentionally historical.

### Scope boundary

The exemption is narrow: only `docs/adr/`. All other pages under `docs/` remain
scanned. This narrowness is pinned by `test_docs_adr_exemption_is_narrow` in both
guard files, which confirms that live docs pages outside the exempt roots are
still being scanned.

---

## Exempt Surface 2: Unreleased-Only CHANGELOG Scan

### What is excluded

Both `CHANGELOG.md` (at the repository root) and `docs/changelog/CHANGELOG.md`
are scanned, but **only the unreleased section** — the portion of the file above
the first versioned heading — is checked for terminology drift. Historical version
sections are not scanned.

### Why it is exempt

A CHANGELOG is an append-at-the-top log. Each released version section records
what changed at the time of that release, using vocabulary that was canonical at
that time. Rewriting historical version sections to conform to vocabulary that
became canonical later would make the CHANGELOG historically inaccurate.

The `Unreleased` section, by contrast, describes work that has not yet shipped
and must reflect current canonical vocabulary.

### How it is implemented

The guard implements this boundary via `_extract_changelog_unreleased()`, which
returns only the content above the first `## [X.Y.Z]` heading. Both CHANGELOG
files are explicitly excluded from the `docs/**/*.md` glob and processed
separately through this extractor, ensuring only the unreleased content is
evaluated.

The `docs/changelog/index.md` index page is not a CHANGELOG file and is still
scanned as a normal live doc.

---

## Exempt Surface 3: Archived Sub-areas Under `docs/plans/`

### What is excluded

Two subdirectories under `docs/plans/` are excluded from the live-doc scan:

- `docs/plans/engineering-notes/`
- `docs/plans/initiatives/`

### Why it is exempt

These subdirectories contain archival records relocated from the previously
unscanned `architecture/` tree during the Common Docs consolidation. Their
content consists of:

- `engineering-notes/` — retained deep-dive notes from earlier development eras
- `initiatives/` — completed initiative records describing work that has already
  concluded
- `notes/` — informal engineering notes from previous development cycles

All three are archival: they document decisions, investigations, and completed
work. Their content uses vocabulary that was current at the time of writing and
is not maintained going forward. Scanning them would produce false positives that
cannot be remediated without rewriting historical context — the same reasoning
that exempts `docs/adr/`.

### Scope boundary

Only the three named subdirectories are exempt. The `docs/plans/` root and all
non-archival pages at the top level of `docs/plans/` remain live surfaces that
are fully scanned.

---

## Exempt Surface 4: `docs/migrations/` — Migration Runbooks

### What is excluded

All files under `docs/migrations/` are excluded from the live-doc scan.

### Why it is exempt

Migration runbooks must *name* the deprecated flags, commands, and workflows they
help users move away from — `--feature`, the pre-3.0 main-centric workflow, legacy
env vars, and so on. The whole purpose of a migration doc is to reference the old
vocabulary verbatim so a reader can find-and-replace it. Scanning these pages
would flag the very terms they exist to document, producing false positives that
cannot be remediated without defeating the doc's purpose. Same reasoning as
`docs/adr/`: the content legitimately carries era-correct vocabulary.

### Scope boundary

Only `docs/migrations/` is exempt. All other live `docs/` pages remain fully
scanned.

---

## Exempt Surface 5: `docs/reports/` — Dated Point-in-Time Report Snapshots

### What is excluded

All files under `docs/reports/` are excluded from:

- the live-doc scan in `_live_doc_scan_targets()` in
  `tests/contract/test_terminology_guards.py` (`FORBIDDEN_SCAN_ROOTS`)
- the non-canonical decision-command-shape scan in
  `tests/specify_cli/cli/test_decision_command_shape_consistency.py`
  (`REPORT_SNAPSHOT_PREFIX`)
- the retired doctrine-profile-directory path scan in
  `tests/audit/test_no_legacy_agent_profiles_path.py`
  (`_SNAPSHOT_EXCLUDED_DIRS`; #5474)

### Why it is exempt

`docs/reports/` holds dated, point-in-time report snapshots — for example
`docs/reports/tracer-friction-recon/2026-09-26/`, a recon report generated on
2026-09-26 that describes, as part of its findings, retired command/flag
shapes (the removed `--feature` alias; non-canonical decision-subcommand
phrasing) exactly as they existed in the surfaces it was investigating.
Rewording those quotations to match current vocabulary would falsify the
report: the whole value of a dated snapshot is that it records what was true
on the date it was taken, not what is true today. This is the same rationale
as the `docs/adr/` exemption above.

`docs/reports/` is already classified as an immutable-historical-snapshot
prefix by `ARCHIVE_PATH_PREFIXES` in
`tests/architectural/test_no_dead_src_path_literals.py`; this exemption
mirrors that existing classification rather than inventing a third,
divergent list of "which report/archive paths are historical."

Authority: spec.md R6 / #5187 (mission `nightly-drift-reds-01M3M14S`).

### Scope boundary

Only `docs/reports/` is exempt. All other live `docs/` pages remain fully
scanned. This narrowness is pinned by `test_docs_adr_exemption_is_narrow` in
`tests/contract/test_terminology_guards.py`, which asserts both that
`docs/reports/` is excluded and that live `docs/` pages outside every exempt
root are still being scanned.

Because a "point-in-time snapshot" exemption is only safe as long as those
snapshots are never *published* as live docs, every guard file listed under
"What is excluded" also carries a
`test_docs_reports_exemption_is_not_published_as_live_docs` guard. Each one
calls the shared `assert_docfx_does_not_publish_reports` in
`tests/_support/docfx_reports_guard.py`, which fails when any
`docs/docfx.json` `build.content` or `build.resource` entry would publish a
`docs/reports/` path. If that guard ever fails, `docs/reports/` has started being
published as live documentation and this exemption must be reconsidered, not
silently kept.

---

## Exempt Surface 6: `docs/archive/` — Retired Pages Relocated Out of the Live Tree

### What is excluded

All files under `docs/archive/` are excluded from the live-doc scan in
`_live_doc_scan_targets()` in `tests/contract/test_terminology_guards.py`
(`FORBIDDEN_SCAN_ROOTS`).

### Why it is exempt

`docs/archive/` holds retired pages that #5428 ("archive retired pages and
neutralize 3.x-anchored names") relocated out of the live tree. They are
immutable historical snapshots that legitimately retain era-correct wording
(the removed `--feature` alias, the pre-3.0 main-centric workflow, "Merge to
main"), exactly like `docs/adr/`. The Terminology Canon permits legacy wording
in explicitly archived artifacts, and rewording these pages would falsify the
record they exist to preserve. #5428 moved the pages but did not exempt the new
root, so the scan began flagging them (for example
`docs/archive/plans/initiatives/test_improvement/IMPLEMENTATION_COMPLETE.md`);
the exemption restores the archival carve-out (#5488).

### Scope boundary

Only `docs/archive/` is exempt. A retired page is exempt only because it lives
under this root: moving a page out of `docs/archive/` back into the live tree
puts it back in scope. All other live `docs/` pages remain fully scanned.

---

## Shared Exempt-Root List and the Operator-Surface Gates

The exempt roots above are one list, `FORBIDDEN_SCAN_ROOTS` in
`tests/_support/terminology_scope.py`. The live-doc guard
(`tests/contract/test_terminology_guards.py`) and the two operator-surface
gates added for #4836 read it, so a root exempted for one scan is exempted
for all:

- `tests/architectural/test_no_config_key_spelled_as_module_path.py` — no
  charter config key written as a `charter.offering.*` module path.
- `tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py` —
  the removed-command gate: the `doctrine` command group was removed in
  #3732, so no living surface invokes it (the CLI name followed by
  `doctrine`) or names a backticked `doctrine <former command>`. It scans the shipped skills, both
  packs, the living docs, the CI workflows, `Makefile`, `AGENTS.md`,
  `CLAUDE.md`, `README.md` and the full text of every Python file under `src/`
  and `scripts/` (docstrings and comments included). It has no allowlist.

Those two gates add the following exemptions on top of the shared list, each
for the reason given:

| Exemption | Gate | Reason |
|---|---|---|
| `docs/changelog/` (both gates) | both | A changelog entry's **Before** quotes the old key or command. The live-doc guard's Unreleased-only scan does not fit here, because the Unreleased section is exactly where those Before quotes live. |
| `docs/plans/` | removed-command gate | Plans and design reviews record how past work was planned and delivered (for example a work-package row recording that it added a subcommand to the `doctrine` group). Rewriting a delivered work package's command would falsify the record. |
| `docs/development/docs-retrieval-index.yaml` | removed-command gate | Generated output: it indexes every docs page, including the exempt historical roots. `docs/api/cli-commands.md` is scanned: it regenerates from the CLI's help text, which no longer has the group. |
| Glob `m_*charter_pack_cutover*.py` under `src/specify_cli/upgrade/migrations/` (today `m_4_0_0rc6_charter_pack_cutover.py`) | removed-command gate | The cutover migration must spell the retired literals it rewrites. |

## Invariant: Exemptions Must Stay Narrow

Each exemption above is explicitly bounded. The guards include non-vacuity and
narrowness checks:

- `test_docs_adr_exemption_is_narrow` (in both guard files) confirms that live
  `docs/` pages outside the exempt roots are still being scanned; in
  `tests/contract/test_terminology_guards.py` it additionally confirms
  `docs/reports/` is excluded.
- The CHANGELOG handling must remain via `_extract_changelog_unreleased()` rather
  than a raw glob that would skip the file entirely.
- `test_grep_guards_do_not_scan_historical_artifacts` confirms that no glob
  pattern in the guards directly targets any `FORBIDDEN_SCAN_ROOTS` root.
- `test_docs_reports_exemption_is_not_published_as_live_docs` (in both the
  live-doc guard and the decision-command-shape guard) confirms
  `docs/docfx.json` never publishes `docs/reports/` as live docs, so the
  point-in-time-snapshot rationale for that exemption stays true.

If a future change widens an exemption beyond its stated boundary — for example,
by exempting all of `docs/plans/` instead of only the three archival
subdirectories, or by treating all of `docs/` as historical — that is a
regression, not maintenance.

---

## Updating This Policy

If a new surface requires an exemption:

1. Update `FORBIDDEN_SCAN_ROOTS` in
   `tests/_support/terminology_scope.py` (shared by every terminology scan).
2. Update `_EXCLUDED_PATH_FRAGMENTS` in
   `tests/architectural/test_no_legacy_terminology.py` if the legacy-term scan
   is also affected.
3. Update this document to record the rationale and scope boundary for the new
   exemption.
4. Add or update a narrowness test that pins both the exempt surface and the
   non-exempt remainder, so a future glob change cannot silently widen the
   carve-out.
