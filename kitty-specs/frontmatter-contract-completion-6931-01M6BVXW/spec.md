# Feature Specification: Frontmatter Contract Completion (#6931)

**Mission**: frontmatter-contract-completion-6931-01M6BVXW
**Mission ID**: 01M6BVXWKTRSD7WMYEY3SM65HC
**Created**: 2026-11-01
**Status**: Draft
**Target branch**: `issue-6931-frontmatter-contract`
**Issue**: spec-kitty/spec-kitty#6931 (parent epic #6100; ADR 2026-10-31-1 D-7)

## Summary

The docsite migration to doc-kitty (epic #6100) replaces a DocFX tree whose
frontmatter was authored for DocFX with a corpus that must satisfy doc-kitty's
frontmatter contract. ADR 2026-10-31-1 D-7 records the mapping in row groups.
#6929 (S-4b) owns the build-blocking rows: `audience` as a list, the excluded-tree
schema minimum, `related` as slugs, and the ADR `doc_status`/`kind` pair. This
mission owns **the rest of D-7**: `kind`, `doc_status` normalisation, and `updated`
as an instant.

The constraint that shapes the whole mission: the tool the issue names as its
gate (`dockitty-validate-frontmatter --astro-config site/astro.config.mjs`) does
not exist on `main`, and `site/` does not exist, because #6930 is unstarted. A
gate that cannot run cannot be satisfied. So the contract is made **executable in
this repository**: one module states the contract, a validator checks the corpus
against it, and the tests check both. The contract is not a guess — it mirrors
doc-kitty's own gate (`src/lib/vocabulary-core.mjs`, `src/scripts/validate-frontmatter.mjs`
at the pinned commit `494f2d87`), so the moment doc-kitty is wired up its verdict
and ours agree.

Today's corpus, measured on `main` at `287a226cfe` over the 670 published pages:

| Field | State today | Needed |
| --- | --- | --- |
| `kind` | **0** pages carry it | required on every page |
| `type` | 198 pages carry a Divio value (`how-to`, `explanation`, `reference`, `tutorial`) | `type` names the *section* in doc-kitty (ADR-0009); the Divio meaning moves to `kind` |
| `doc_status` | 227 published ADRs carry none; `point_in_time` ×2 and `proposal` ×1 are non-canonical | canonical five values only |
| `updated` | date-only (`'2026-10-26'`) on 481 pages; absent on 189 ADRs (all carry `date`) | an instant (`YYYY-MM-DDTHH:MM:SSZ`) |

ADR D-7 also constrains *how* this may be done: the bodies of ADRs, plans,
reports and changelog entries are **immutable** — "a frontmatter-only change made
by a recorded, mechanical migration is allowed", and the migration must carry a
test that proves bodies did not change.

## User Scenarios & Testing

### Primary scenario — the contract is checkable without doc-kitty (P1)

1. A maintainer asks "does the published corpus satisfy the frontmatter contract?"
2. They run the contract validator. It resolves the published page set from the
   one existing publication authority (`scripts/docs/_published_pages.py`, which
   reads `docs/docfx.json`) and reports violations against the contract module.
3. On this branch it reports **zero errors** over all published pages, and the
   count of pages checked is asserted non-vacuous.
4. The validator's rules are pinned to doc-kitty's own gate by tests that assert
   the required-field set, canonical vocabularies, and instant grammar match the
   mirrored upstream source.

### Secondary scenario — the migration is mechanical and reversible in review (P1)

1. A reviewer opens the diff and sees that every changed line is a frontmatter
   line: `kind` added, `doc_status`/`updated` normalised, Divio `type` removed.
2. No body line changed. The mission's immutability test proves it by hashing the
   body of every ADR, plan, report and changelog page against the pre-migration
   blob, and by asserting the migration function itself never alters a body.
3. Re-running the migration on the migrated tree is a no-op (idempotent), so a
   later partial re-run cannot churn the corpus.

### Tertiary scenario — the in-repo Divio readers keep working (P2)

1. `type` carried the Divio axis for `docs/development/docs-retrieval-index.yaml`
   (via `scripts/docs/docs_index.py`) and `docs/development/page-inventory.yaml`
   (via `scripts/docs/inventory_lockfile.py`).
2. Removing the Divio `type` would silently degrade both to `none`. The readers
   move to `kind` in the same change, so both artifacts regenerate byte-identical
   and `spec-kitty docs query` still answers.

### Edge cases

- A page with a `kind` already present (later migrations, or a page added by
  another PR) — the migration never overwrites it, and the validator accepts it if
  it is in the canonical set.
- A page with neither a Divio `type`, nor an index role, nor a path-prefix rule —
  the migration must **fail** rather than invent a kind ("any page left
  unclassified is a migration failure", D-7).
- A `doc_status` outside the canonical set that is not in the alias table — a
  violation, not a silent pass-through.
- An `updated` value already in instant form (with or without a trailing `Z`, or
  with an offset) — only the canonical UTC instant is accepted; anything else is a
  violation naming the expected shape.
- An ADR whose `status` is not one of `Accepted`/`Proposed`/`Superseded` — a
  violation, because the mapping is total by construction and a new value means a
  human decision.
- A published page whose `doc_status` the migration would *publish* that D-8 says
  must stay unpublished (`plans/engineering-notes/`, `plans/investigations/`,
  `plans/research/` are `draft`). D-8 is the more specific rule for that subtree
  and wins over the D-7 alias table; the conflict is recorded in the contract, not
  resolved silently.
- An unpublished page (`archive/`, `reports/`, `convergence/`) carrying a
  non-canonical value — out of scope: D-8 scopes the gates to published sections.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One contract module | As a maintainer, I want the doc-kitty frontmatter contract stated once in the repository so that the corpus, the validator and the tests cannot drift apart. | High | Open | [build] | no |
| FR-002 | Canonical vocabularies mirrored from doc-kitty | As a reviewer, I want the contract's required-field set, `kind` set and `doc_status` set to match doc-kitty's pinned gate so that a green verdict here predicts a green verdict there. | High | Open | [build] | no |
| FR-003 | `kind` resolved for every published page | As a reader of the future site, I want every published page to carry a `kind` so that doc-kitty can pick its layout, and no page is left unclassified. | High | Open | [build] | no |
| FR-004 | Divio `type` folded into `kind` | As a maintainer, I want the 198 Divio `type` values replaced by their `kind` equivalents so that `type` is left free for doc-kitty's section meaning. | High | Open | [build] | no |
| FR-005 | `doc_status` normalisation | As a maintainer, I want `closeout`/`point_in_time` mapped to `durable` and `proposal` to `draft`, and ADR `status` mapped to `doc_status`, so that every page carries a canonical lifecycle value. | High | Open | [build] | no |
| FR-006 | `updated` as an instant | As a maintainer, I want every `updated` value normalised to a UTC instant, taking ADRs' value from `date`, so that doc-kitty's freshness band has one parseable input. | High | Open | [build] | no |
| FR-007 | Validator over published sections | As a maintainer, I want a runnable validator that reports contract violations for the published sections only so that the contract is checked in CI before doc-kitty exists. | High | Open | [build] | no |
| FR-008 | Body immutability proof | As a reviewer, I want a test that proves the migration changed no ADR, plan, report or changelog body, so that D-7's immutable-corpus rule is enforced rather than asserted. | High | Open | [ratchet] | no |
| FR-009 | In-repo Divio readers ported | As a maintainer, I want the retrieval index and page inventory to read the Divio axis from `kind` so that removing the Divio `type` does not silently blank both artifacts. | High | Open | [build] | no |
| FR-010 | Publish surface unchanged | As a maintainer, I want `spec-kitty docs query` to keep answering, with its index regenerated, so that the docs retrieval surface does not regress. | High | Open | [ratchet] | no |
| FR-011 | Deferred check deletion is recorded | As a maintainer, I want the `description_length_check.py` retirement recorded as blocked on doc-kitty's gate rather than performed blind, so that the corpus does not lose enforcement while the replacement is unlanded. | Medium | Open | [folded] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Validator fails closed on a collapsed page set | The validator must exit non-zero with an explicit coverage error when the resolved published set is empty or below the existing non-vacuity floor (`MINIMUM_EXPECTED_PAGES` = 500 of today's 670). | Reliability | High | Open |
| NFR-002 | Migration is idempotent and body-preserving | Re-running the migration over the migrated tree must change 0 bytes; for every file it rewrites, `body(after) == body(before)` exactly. | Correctness | High | Open |
| NFR-003 | Frontmatter-only diff | Every file the migration changes must differ from `origin/main` only inside its frontmatter block (verified line-wise by `git diff -U0`). | Correctness | High | Open |
| NFR-004 | No new dependency | The contract module, validator and migration use the standard library plus `ruamel.yaml` (already a dependency). | Portability | Medium | Open |
| NFR-005 | Whole-tree runtime is reviewable | The validator over 670 pages completes in under 10 s on the development host (it parses YAML, no network, no build). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| C-001 | Contract mirrors doc-kitty at the pinned commit | Field names, canonical `kind`/`doc_status` values and instant grammar come from doc-kitty `494f2d87` (`vocabulary-core.mjs`, `validate-frontmatter.mjs`), not from invention. Where the pinned gate only warns, this contract only warns. | Technical | High | Open |
| C-002 | One publication authority | The validator must not introduce a second answer to "which pages are published": it consumes the existing resolver, and it must not require `site/` or `docs/_meta/sections.yaml` (both unlanded). | Technical | High | Open |
| C-003 | Body immutability (ADR D-7) | ADR, plan, report and changelog bodies are byte-immutable; only frontmatter may change, and only mechanically. | Regulatory | High | Open |
| C-004 | Scope boundary against unlanded siblings | `audience`, `related`, the excluded-tree schema minimum and the `site/` scaffold belong to #6929/#6930 and are not touched. Where this mission's migration and #6929's overlap (the ADR `kind`/`doc_status` pair), the overlap is disclosed in the PR, not hidden. | Business | High | Open |
| C-005 | Never merge, never arm auto-merge, never push `main` | The PR opens as a draft with `pr:pause-ci`; the operator merges. | Business | High | Open |
| C-006 | Unrunnable gates stay red and are named | `dockitty-validate-frontmatter` cannot run without `site/`; that gate is not simulated, skipped or replaced by a green claim. It stays red in the PR body with the unblocking dependency. | Business | High | Open |

### Key Entities

- **Contract rule set**: required fields, canonical `kind` values, canonical
  `doc_status` values, `doc_status` alias table, Divio `type` → `kind` map,
  path-prefix `kind` table, instant grammar, description band.
- **Page violation**: a `(path, field, reason, detail)` row the validator emits;
  a hard error or an advisory warning, matching the pinned gate's severity.
- **Migration plan entry**: a `(path, kind, doc_status, updated, remove_type)`
  tuple the migration computes before writing, so the diff is inspectable without
  running it.

## Success Criteria

- **SC-001**: The contract validator reports 0 errors and 0 warnings over all 670 published pages on this branch. — [build] · no-op passable: no
- **SC-002**: The validator's required-field set, canonical `kind` set and canonical `doc_status` set are asserted equal to doc-kitty's pinned sets by a test. — [build] · no-op passable: no
- **SC-003**: The immutability test covers every ADR, plan, report and changelog page (364 files measured) and fails if any body byte changes. — [ratchet] · no-op passable: no
- **SC-004**: `uv run python -m scripts.docs.frontmatter_contract --strict` exits 0, and a mutated fixture page makes it exit 1 (the gate can fail). — [build] · no-op passable: no
- **SC-005**: `spec-kitty docs query` answers, and the retrieval index and page inventory regenerate with zero drift **after regeneration** (measured: generated=917, committed=917, drift=False, both). The regenerated files themselves are reverted because `scripts/ci/check_generated_docs_untouched.py` refuses a PR that edits them; the bot PR carries them post-merge. — [ratchet] · no-op passable: no
- **SC-006**: `dockitty-validate-frontmatter` is recorded as **not run** in the PR body with its unlanded dependency, and no claim of a doc-kitty green is made. — [folded] · no-op passable: no
