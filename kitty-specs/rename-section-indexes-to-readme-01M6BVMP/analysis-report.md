---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: rename-section-indexes-to-readme-01M6BVMP
mission_id: 01M6BVMP0WAWX55EP1136GQ4HT
generated_at: '2026-11-01T15:45:00+00:00'
analyzer_agent: python-pedro
input_artifacts:
  spec.md:
    path: kitty-specs/rename-section-indexes-to-readme-01M6BVMP/spec.md
    sha256: 3cdbd3c4864c77ace945408b9bc8ad6c24e8b6520a6dd667943e215c7362ad40
  plan.md:
    path: kitty-specs/rename-section-indexes-to-readme-01M6BVMP/plan.md
    sha256: 2f368ea62c15613bea0eb1324bc22ec5a6c3116aaeafa495e6cc11795cf6d81f
  tasks.md:
    path: kitty-specs/rename-section-indexes-to-readme-01M6BVMP/tasks.md
    sha256: cde3b9e7cb562cdee391300050b6deb755d43c78a0ec4777d380a2c935bffe0d
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  low: 2
  medium: 1
  high: 0
  info: 0
findings:
- id: X1
  severity: medium
  category: coverage
  summary: The docs-structural-lint asset (external pack) keys index_completeness on
    architecture/index.md and exempts every **/README.md from the frontmatter contract;
    after the rename both behave differently and cannot be fixed in this repository.
- id: G1
  severity: low
  category: risk
  summary: The committed docs-retrieval-index.yaml and page-inventory.yaml go stale with
    the rename by design (the regen bot owns them) and the PR must not refresh them.
- id: R1
  severity: low
  category: risk
  summary: DocFX is still the live deployer, so the renamed pages' rendered URLs change
    from dir/index.html to the README-derived URL until the doc-kitty chain lands.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| X1 | Coverage | MEDIUM | spec.md C-003, plan.md IC-03, WP02 DoD | `packs/built-in/assets/docs_structural_lint.py` implements `index_completeness` as `section_dir / "index.md"` and `check_one_index_per_dir` treats `index.md` as the canonical keeper; the Spec Kitty config (`packs/internal/styleguides/spec-kitty-docs-lint-config.styleguide.yaml`) exempts `**/README.md` from the frontmatter contract and names `architecture` as curated-complete. After the rename, `index_completeness` finds no index and silently skips, and all 60 pages become frontmatter-exempt nav basenames. Both live in the external pack (`packs/*` are gitignored, fetched from pinned commits), so this PR cannot change them. | Accept and report: it is a coverage change, not a red gate (no live-tree zero-violation assertion exists for these rules; `tests/docs/test_docs_structural_lint.py` asserts per-rule and per-cohort behaviour). It must be named in the PR `## Deferred` section as an open-packs change gated on the doc-kitty chain. Do not patch `packs/` (C-003). |
| G1 | Risk | LOW | spec.md NFR-003, WP01/02/03 DoD | The PR renames 60 pages; the committed retrieval index and page inventory enumerate them by path and will therefore lag. `check_docs_freshness` reports that staleness as `warning` and `tests/docs/test_docs_index_regenerates_cleanly.py` checks the generators' CONTENT, not equality with the committed copy — so this is by design and must not be "fixed" in the PR. | Accept: `scripts/ci/check_generated_docs_untouched.py` must be clean; note the post-merge regen in the PR body. |
| R1 | Risk | LOW | spec.md Scope boundary, C-004 | With DocFX still live, `docs/adr/<era>/README.md` and the other renamed pages deploy under a different output URL than `dir/index.html`; `docs-pages.yml` runs only on push to `main`/`2.x`, so no PR check can exercise it. | Accept: the PR opens as a draft, states the deploy gap and that the chain (`#6927`–`#6930`, `#6937`, `#6938`, `#6943`, `#6926`/`#7007`) unblocks it. Do not weaken a gate to simulate green. |

## Requirement coverage check

Every FR-001…FR-009, NFR-001…NFR-003, C-001…C-004 and SC-001…SC-006 is referenced by
at least one work package (WP01: FR-001…FR-005, FR-008, NFR-001…NFR-003, C-001,
SC-001…SC-002; WP02: FR-006, FR-007, SC-004, C-003; WP03: FR-009, SC-003, SC-005,
SC-006, C-002, C-004). No requirement is unmapped.

## Ambiguity check

Two terms are fixed before scoping, per the grounding rule: "section index" means a
page named `index.md` at a section directory root (60 of them, not every `index.md` name
in the repository); "link target" means a Markdown link/image destination, a `toc.yml`
`href`, or a frontmatter `related:` entry — never a prose or code-block mention
(ADR 2026-10-31-1 D-7).
