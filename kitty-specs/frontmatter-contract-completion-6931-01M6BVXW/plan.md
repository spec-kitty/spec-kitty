# Implementation Plan: Frontmatter Contract Completion (#6931)

**Branch**: `issue-6931-frontmatter-contract` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/frontmatter-contract-completion-6931-01M6BVXW/spec.md`
**Issue**: spec-kitty/spec-kitty#6931 | **Parent**: #6100 | **ADR**: 2026-10-31-1 D-7

## Summary

State doc-kitty's frontmatter contract once, in `scripts/docs/frontmatter_contract.py`;
validate the published corpus against it with a runnable gate
(`python -m scripts.docs.frontmatter_contract --strict`); migrate the corpus
mechanically (`--write`), body-preserving and idempotent; prove the corpus bodies
did not move; and port the two in-repo Divio readers to `kind` so removing the
Divio `type` does not blank the retrieval index or the page inventory.

The contract is **not invented**. Its field set, canonical vocabularies, severity
split (error vs advisory) and instant grammar are mirrored from doc-kitty at the
pinned commit the spike recorded (`494f2d87`), so this gate and
`dockitty-validate-frontmatter` give the same verdict when the site lands.

### Upstream source of truth (mirrored, cited in the module)

| doc-kitty symbol | Value | Used here for |
| --- | --- | --- |
| `CANONICAL_REQUIRED` | `title, description, doc_status, updated, kind` | required fields (error when absent) |
| `REQUIRED_FIELD_FLOOR` | `title` | never relaxable |
| `KINDS` (15) | `Tutorial, How-To, Reference, Explanation, Hub, ADR, Changelog, Glossary, Presentation, Persona, Planning, Feature, User-Journey, Specification, Schematic` | `kind` value set (advisory warning outside it, error when absent) |
| `STATUSES` (5) | `draft, active, deprecated, superseded, durable` | `doc_status` value set (advisory warning outside it) |
| `DOC_TYPES` (18) | `Context … Specification` | `type` canonical set (advisory only — `type` is optional upstream since #38) |
| `instantDate` / `normaliseInstant` | RFC3339 UTC instant | `updated` grammar |
| `DESCRIPTION_MAX` | 180 | description upper bound |

Upstream severity is preserved deliberately: `kind`/`doc_status` **unknown value**
warns; **absent required field** is an error; `kind: Presentation` outside
`presentations/` is an error; `kind: Persona` without `role`/`goals`/
`responsibilities` is an error. Making any of these stricter would invent a gate
doc-kitty does not have; making any looser would fake green.

## Technical Context

**Language/Version**: Python 3.11 (`requires-python` in `pyproject.toml`)
**Primary Dependencies**: standard library + `ruamel.yaml` (already used by
`scripts/docs/_inventory.py`); no new dependency (NFR-004)
**Storage**: the `docs/` tree itself; the contract is code, not a new data file
**Testing**: `pytest` under `tests/docs/`; `pytest.mark.architectural` for the
whole-corpus assertions, matching the sibling docs gates
**Target Platform**: developer host and CI (PR-time), no build, no network
**Project Type**: single repository, `scripts/docs/` build tooling + `docs/` corpus
**Performance Goals**: validator over 670 pages < 10 s (NFR-005); measured, not assumed
**Constraints**: no `site/`, no `docs/_meta/sections.yaml`, no doc-kitty binary on
`main` (C-002, C-006); bodies immutable (C-003)
**Scale/Scope**: 670 published pages (of 931 files); 670 files touched by the
migration, every one of them frontmatter-only

## Charter Check

- **One authority per question** (directive 044 / the `_published_pages` precedent):
  the published page set comes from the existing resolver; the Divio axis gets one
  reader after the port; the contract module is the only place a vocabulary is
  retyped.
- **No fake green**: the unrunnable doc-kitty gate is named, never simulated. The
  local gate is a *different, honest* check ("does the corpus satisfy the contract"),
  not a stand-in verdict for doc-kitty.
- **Red-first**: the validator is written and run *before* the migration; its red
  output over the current corpus is the reproduction. The migration then turns it
  green.
- **Documented deviations** must be recorded where the code lives: the D-8 vs D-7
  `doc_status` precedence for `plans/engineering-notes/` is a comment + test, not a
  silent choice.

## Phase 0 — Research (done, evidence recorded)

1. **Is the issue coherent without `site/`?** Yes for 3 of its 4 deliverables
   (contract, validator, migration). The fourth — deleting
   `description_length_check.py` "once `dockitty-validate-frontmatter` covers them"
   — is conditioned on a tool that does not exist, so it is *deferred by the
   issue's own wording*, not by a judgement call (FR-011).
2. **What exactly does doc-kitty require?** Read at `494f2d87`:
   `src/lib/vocabulary-core.mjs`, `src/scripts/validate-frontmatter.mjs`,
   `src/lib/schema.ts`, `docs/adr/0009-finalize-metadata-contract.md`. Findings in
   the table above; the decisive one is ADR-0009: "`type` names the section; `kind`
   names how to read the page", which is what licenses folding the Divio `type`
   into `kind` (FR-004) instead of leaving 198 pages carrying a value doc-kitty
   reads as a wrong section name.
3. **What is the current corpus state?** Measured (not quoted from the ADR's
   spike, which was taken at a different base): 670 published; 0 `kind`; 198 Divio
   `type`; 227 ADRs without `doc_status`; 3 non-canonical `doc_status` values in
   published sections; 189 ADRs without `updated` (all with `date`); 481 date-only
   `updated`.
4. **What does `kind` resolution need for the 201 pages with no Divio `type`, no
   index role and no ADR role?** A path-prefix table, because their sections have
   unambiguous doc-kitty kinds: `plans/` → `Planning`, `changelog/` → `Changelog`,
   `api/` → `Reference`, `architecture/` → `Explanation`, `context/` → `Explanation`,
   `configuration/` → `Reference`, `development/reference/` → `Reference`,
   `migrations/` and `operations/` → `How-To`. Every row is a documented decision in
   one table; a page the table cannot classify is a hard error (D-7's "migration
   failure").
5. **Why not `kind: Persona` for `docs/context/audience/**`?** doc-kitty *errors*
   on a `Persona` page without `role`/`goals`/`responsibilities`, and those 20+
   pages carry their persona attributes in a body table (they are md-authored, not
   frontmatter-authored). Classifying them `Persona` would ship a red gate. They
   get `Explanation`, and the upstream gap is recorded in the PR's `## Deferred`.
6. **Why does D-8 override the D-7 alias table for two pages?** D-7 maps
   `point_in_time` → `durable`; D-8 says `plans/engineering-notes/` pages are
   `draft` and unpublished. Both live in the same merged ADR; for that subtree D-8
   is the specific rule. Applying D-7 literally would *publish* two
   engineering-note pages the operator decided not to publish.

## Phase 1 — Design

### Module: `scripts/docs/frontmatter_contract.py` (new)

Single module, three roles, no new data files.

```text
Contract data (constants)
  REQUIRED_FIELDS            <- CANONICAL_REQUIRED
  FIELD_FLOOR                = ('title',)
  KINDS / DOC_STATUSES / DOC_TYPES          (canonical sets, mirrored)
  DOC_STATUS_ALIASES         {closeout: durable, point_in_time: durable, proposal: draft}
  ADR_STATUS_TO_DOC_STATUS   {Accepted: active, Proposed: active, Superseded: superseded}
  DIVIO_TYPE_TO_KIND         {tutorial: Tutorial, how-to: How-To, reference: Reference,
                              explanation: Explanation}
  KIND_BY_PATH_PREFIX        ordered (prefix, kind) rows, longest match wins
  DRAFT_SECTIONS             plans/engineering-notes|investigations|research  (D-8)
  INDEX_BASENAMES            {'index.md', 'README.md'}
  UPDATED_INSTANT_RE         ^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$
  MIN/MAX_DESCRIPTION_LENGTH (moved here; description_length_check imports them)

Pure resolution (testable without a filesystem)
  resolve_kind(path, frontmatter) -> str | None            # ordered rules, None = unclassified
  normalise_doc_status(path, frontmatter) -> str | None    # alias table, D-8 override, ADR status
  normalise_updated(path, frontmatter) -> str | None       # keeps an explicit value, ADR date fallback

Validation (pure)
  validate_page(rel_path, frontmatter) -> PageVerdict(errors, warnings)
      error  : absent required field; unclassified kind; unparseable/absent updated;
               unknown ADR status; Presentation outside presentations/
      warning: kind/doc_status/type outside the canonical set; description over 180
               (doc-kitty's own severities)

Corpus gate
  validate_tree(docs_root, repo_root, page_set=None) -> ContractReport
      default page set = scripts.docs._published_pages.resolve_published_pages
      (one authority; no site/, no sections.yaml)

Migration (mechanical, idempotent, frontmatter-only)
  plan_page(text, rel_path) -> PageEdit | None      # computes kind/doc_status/updated/type-drop
  apply_page(text, edit) -> str                     # line surgery inside the fence only
  main(--write | --check | --json | --strict)
```

Line surgery, not re-serialisation: the migration rewrites only the frontmatter
lines it owns (in place where the key exists, appended at the end of the block
where it does not) and removes a Divio-only `type` line. Re-serialising through
`ruamel` would reformat all 670 frontmatter blocks and destroy reviewability
(NFR-003). Everything outside the closing `---` is copied verbatim, which is also
why the body invariant holds by construction *and* is asserted (NFR-002).

### Severity and exit contract (mirrors `description_length_check`)

`0` clean; `1` `--strict` and at least one error; `2` coverage failure (the
resolver refused, or the set collapsed below `MINIMUM_EXPECTED_PAGES`). Warnings
never fail `--strict`, exactly as doc-kitty's warnings do not fail its gate.

### Readers ported (FR-009)

| Reader | Today | After |
| --- | --- | --- |
| `scripts/docs/inventory_lockfile.py` | `divio_type` from frontmatter `type` | from `kind` via `KIND -> DivioType` (same values → lockfile regenerates identical) |
| `scripts/docs/docs_index.py` | Divio axis from frontmatter `type` | from `kind`; `docs/development/docs-retrieval-index.yaml` regenerated (no drift) |
| `scripts/docs/frontmatter_backfill.py` | writes `type` from `divio_type` | writes `kind` (its `type` writer would re-introduce the Divio value) |

`DivioType` stays as the retrieval axis enum: it is the *reading* of a page, which
is precisely what `kind` now carries. The mapping is total over the Divio kinds and
`NONE` otherwise.

### Tests

| File | Covers |
| --- | --- |
| `tests/docs/test_frontmatter_contract.py` | resolution order, alias table, D-8 override, ADR status totality, instant grammar, severity split, non-vacuity/coverage failure, gate-can-fail (mutated fixture) |
| `tests/docs/test_frontmatter_contract_upstream_parity.py` | required fields and both vocabulary sets equal to the doc-kitty constants recorded above (the parity anchor) |
| `tests/docs/test_frontmatter_contract_corpus.py` | the real tree: 0 errors, 0 warnings, ≥ 500 pages checked, every published page has a canonical `kind` |
| `tests/docs/test_frontmatter_body_immutability.py` | every ADR/plan/report/changelog body matches the committed body-hash baseline; the migration function is body-preserving over every file and over adversarial synthetic input |

### Risks

| Risk | Mitigation |
| --- | --- |
| A wrong `kind` classification is a content judgement | one reviewable table + per-page override wins; counts per row in the PR body |
| The 670-file diff is unreviewable | frontmatter-only proof (line-wise `git diff -U0`); one line per file mostly; `--check` prints the plan |
| Overlap with #6929 on ADR `kind`/`doc_status` (227 files) | disclosed in the PR body with merge-order advice; both derive from the same D-7 table, so values are identical |
| Body-hash baseline freezes ADR/plan/changelog bodies | that is the ADR's rule; the test's failure message names the deliberate-update path |
| `docs_index` drift after the reader port | the index is regenerated in the same commit and `check_docs_freshness --ci` is run |

## Phase 2 — Execution order

1. Contract module + unit and parity tests (red over the corpus).
2. Validator CLI + gate-can-fail test.
3. Reader ports (`inventory_lockfile`, `docs_index`, `frontmatter_backfill`).
4. Migration `--check`, then `--write`; regenerate the retrieval index and the
   inventory lockfile; re-run the corpus gate to green.
5. Immutability baseline + tests.
6. Changelog entry, docs page for the gate, `## Deferred` for the doc-kitty gate
   and #6929 overlap.
