# Implementation Plan: Context docs refresh (audience profiles first)

**Branch**: `kitty/mission-context-docs-refresh-01M7AN3N` (lands on `issue-7522-context-refresh`) | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/context-docs-refresh-01M7AN3N/spec.md`; gap analysis in [gap-analysis.md](gap-analysis.md).

## Summary

A `gap_filling` refresh of the 40 published pages under `docs/context/` for #7522. No page is
added or removed. Each page is checked claim by claim against the current CLI and source, names
its reader in `audience:` frontmatter, follows the #3891 writing guidance, and loses any retired
surface the docs gate tracks. The audience profiles go first because every other page names one
of them as its reader.

## Technical Context

**Documentation Framework**: doc-kitty docsite (`site/`, Astro), per ADR `2026-10-31-1`. Pages are Markdown under `docs/`.
**Languages Detected**: Python (the CLI the pages describe). The `jsdoc`/`sphinx` generators that `spec-kitty plan` auto-detected do not apply: no page here is generated reference.
**Output Format**: HTML (built site); diagrams render at build time to static SVG (#6936).
**Hosting Platform**: the docsite pipeline (`docs-site` CI job). Not changed by this mission.
**Theme**: unchanged.

## Project Structure

### Documentation (this mission)

```
kitty-specs/context-docs-refresh-01M7AN3N/
├── spec.md, plan.md, gap-analysis.md, tasks.md, tasks/
├── corrections-log.md      # every factual correction with its evidence (FR-004)
├── operator-flags.md       # unverifiable facts and profile-change proposals (FR-005, C-002)
├── decisions/              # Decision Moments from discovery
└── traces/                 # mission tracer files
```

### Documentation Files (repository root)

Only existing files under `docs/context/` change, plus the retired-surface burn-down pair:
`scripts/docs/retired_surface_burndown.yaml` and `tests/architectural/_baselines.yaml`
(`test_retired_surface_gate.burn_down`). `scripts/docs/retired_surface_landing.yaml` is frozen (C-004).

## Phase 0: Research

Done in the `audit` step: [gap-analysis.md](gap-analysis.md) holds the inventory, coverage matrix
and drift findings D1 to D12. No separate `research.md`.

## Phase 1: Design

### Decision 1: the reader is named in `audience:` frontmatter

- **Choice.** Each page gets an `audience:` list of `{profile, guidance_text}` entries naming
  profiles under `docs/context/audience/`. One primary reader per page; a second entry only when
  the page genuinely serves two readers (as directive 047 allows).
- **Alternatives.** A prose "Who this is for" line (not machine-checkable); a path list as
  DIRECTIVE_047's text describes (contradicted by the shipped schema, #6929).
- **Rationale.** `scripts/docs/audience_resolver.py` and `scripts/docs/staleness_audit.py` read
  this field; it is the existing convention on 285 entries.

### Decision 2: who reads the audience profiles themselves

- **Choice.** The ten profile pages and three hubs name `internal/maintainer` (owns the docs and
  their governance) and `internal/ai-collaboration-agent` (the writing agents, `comms-cleo`
  among them, that pick a reader before drafting).
- **Rationale.** The profiles exist so authors can choose a reader (directive 047,
  `writing-audience-catalog`); those authors are maintainers and agents.

### Decision 3: profiles keep the canonical persona template

- **Choice.** Keep the section shape of `src/charter/offering/templates/architecture/stakeholder-persona-template.md`.
  "Goals" are checked in Primary Goal and Core Motivations; "vocabulary" across every section;
  "the questions a reader brings" in Desiderata (Information, Interaction) and Behavioral Cues.
  The audience hub gains short guidance on which profile to name for which kind of page.
- **Alternatives.** Add "Vocabulary" and "Questions" sections to each profile. Rejected: it changes
  the canonical template's shape in ten copies (DIRECTIVE_044). Raised as a proposal for the
  operator instead (`operator-flags.md`).

### Decision 4: per-page reader allocation (WP02, WP03)

The default reader by page family, applied in WP02 and WP03 unless the page's content says otherwise
(each deviation is recorded in the WP's self-review):

| Page family | Primary reader | Second reader (only if served) |
|---|---|---|
| Footgun glossaries: `orchestration`, `execution`, `topology` | `internal/ai-collaboration-agent` | `internal/lead-developer` |
| `team-kitty`, `product-lines` | `internal/system-architect` | `external/architect-evaluator` |
| Governance and charter pages | `internal/maintainer` | `internal/lead-developer` |
| Identity (`identity`, `identity-fields`), configuration, dossier, system events | `internal/lead-developer` | `internal/ai-collaboration-agent` |
| Glossary tooling and conventions | `internal/lead-developer` (pages that already name one keep it) | none |
| Method pages: `spec-driven`, `practices-principles`, `ops-vs-missions`, `mission-types` | `external/tech-lead-evaluator` | `internal/lead-developer` |
| `testing-taxonomy`, `technology-foundations` | `internal/lead-developer` | none |
| `context/README.md` | keeps `internal/system-architect` | none |

### Decision 5: anchors are frozen

Headings that carry a linked anchor keep their exact text. Before each WP02/WP03 commit, the set of
heading slugs on each page is compared with `origin/main`; any slug that disappears must have no
inbound link (checked with `git grep`) or a redirect. The strict link check is the backstop.

### Decision 6: retired surfaces are drained, not explained away

Each `context/` burn-down pair is removed with its page fix, and
`test_retired_surface_gate.burn_down` drops by the number of pairs removed in the same commit
(the gate's own hint). A page may still describe a retirement in prose where the gate's patterns
allow it (for example "Zeitgeist" as a product name rather than an identifier).

### Decision 7: diagrams

The one text-drawn diagram (`contextive-glossaries.md`) becomes Mermaid with `%% title:` and
`%% description:` lines, per the `mermaid-diagramming` toolguide.

### Decision 8: the `updated` date

`updated` becomes `'2026-11-13T00:00:00Z'` (the date of the check) only on pages whose claims
were checked in this mission. The persona table's `Created / Updated` field records the same date.

### Documentation Structure

Unchanged. Navigation stays: `docs/context/README.md` → section pages; `docs/context/audience/README.md`
→ `internal/README.md`, `external/README.md` → the ten profiles.

### Generator Configurations

None. The auto-detected `jsdoc` and `sphinx` entries in `meta.json` are corrected to an empty list.

### Content Outline

The three work packages, in #7522's order:

- **WP01, audience profiles** (13 pages): D1 to D6; readers per Decision 2.
- **WP02, footgun and concept pages** (`orchestration`, `execution`, `topology`, `team-kitty`,
  `identity`): claim check of every definition, command and path; anchors frozen; D7, D8 (all 11
  burn-down pairs). `identity.md` joins WP02 because it holds the remaining 3 `context/` pairs: one
  work package then owns the burn-down and the baseline, so WP02 and WP03 never edit the same two
  lines and can run in parallel after WP01.
- **WP03, the remaining 22 pages**: claim check; D9 to D12; mixed Divio types resolved.

### Work Breakdown Preview

1. **WP01: Audience profiles** — `docs/context/audience/**`.
2. **WP02: Footgun and concept pages, plus `identity.md`** — depends on WP01; owns the burn-down and its baseline.
3. **WP03: Remaining context pages** — depends on WP01.

## Phase 2: Implementation

Handled by `/spec-kitty.tasks`. Each WP is written under the `comms-cleo` profile, keeps a
corrections log entry per factual change, and stops at `for_review` for an independent reviewer.

### Per-WP checks

- `make docs-lint` (spelling, changelog style, retired-surface gate).
- `uv run python -m scripts.docs.site_link_gates check-links -- pnpm --dir site exec dockitty-check-links ../docs --strict --astro-config astro.config.mjs`.
- Frontmatter: `tests/docs/test_dockitty_frontmatter_shape.py`, `tests/docs/test_audience_resolves.py`, `tests/docs/test_related_validator.py`.
- Section tests: `tests/docs/test_retired_surface_gate.py`, `tests/docs/test_context_glossary_contract_scenario_and_pack_level.py`, `tests/docs/test_glossary_residue_entry.py`, `tests/docs/test_section_index_basename.py`, `tests/docs/test_one_index_per_folder.py`.
- Terminology: `tests/architectural/test_no_legacy_terminology.py`.
- Site build when feasible; with no Docker daemon the PlantUML server cannot run, which is reported.

## Success Criteria Validation

- **SC-001**: regenerate the per-page audit for `context/`; reader column has no `**none**`.
- **SC-002**: `grep -c "page: context/" scripts/docs/retired_surface_burndown.yaml` is 0; baseline is 81 − 11 = 70.
- **SC-003**: audit `text_diagrams` is 0 for every `context/` page.
- **SC-004**: `corrections-log.md` has an evidence entry per change; `operator-flags.md` lists the rest.
- **SC-005**: the strict link check passes, with the positive control that it checks anchors in the same tree.

## Charter Check

- Writing doctrine (charter "Writing, Communication & Diagramming Doctrine"): directive 047, 042;
  styleguides `plain-language`, `professional-communications`, `common-docs`,
  `divio-type-discipline`, `docs-accessibility`, `docs-freshness-sla`, `publication-authority`;
  internal `report-writing` anti-AI-prose patterns; `mermaid-diagramming` toolguide.
- Canonical sources (DIRECTIVE_044): persona template kept; mission artifacts from the canonical commands.
- Terminology Canon: Mission, never Feature; overloaded terms always carry their sense.
- Tests and gates (Standing Order #4): any new gate is written red-first in its own commit; none is planned.
- `NO_FULL_HEAVY_SUITES_IN_MISSION`: only the targeted files above.

## Risks & Dependencies

**Risks**:
- An anchor rename breaks `CLAUDE.md` / `AGENTS.md` links (mitigated by Decision 5).
- A rewrite changes a factual claim beyond what the code proves (mitigated by the corrections log and operator flags).
- The persona pages change shape across ten copies (mitigated by Decision 3).

**Dependencies**:
- `make sync-packs` done in this checkout (the built-in tree feeds the docs gates).
- The docsite toolchain (`pnpm`, node 22) for the link check; Docker for diagram rendering (not available here).
