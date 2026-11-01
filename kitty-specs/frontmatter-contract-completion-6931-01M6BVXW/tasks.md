# Tasks: Frontmatter Contract Completion (#6931)

**Mission**: frontmatter-contract-completion-6931-01M6BVXW
**Branch**: `issue-6931-frontmatter-contract`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md)

State doc-kitty's frontmatter contract once, check it with a runnable gate, migrate
the published corpus mechanically (frontmatter-only, body-immutable), and port the
in-repo Divio readers to `kind` in the same change. The contract mirrors doc-kitty at
`494f2d87` rather than inventing one, because the issue's own gate
(`dockitty-validate-frontmatter`) cannot run without `site/` (#6930 unstarted).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `scripts/docs/frontmatter_contract.py`: contract constants mirrored from doc-kitty `494f2d87` | WP01 | — |
| T002 | Pure resolvers: `resolve_kind`, `normalise_doc_status`, `normalise_updated`, `remove_divio_type` | WP01 | — |
| T003 | Unit + upstream-parity tests | WP01 | — |
| T004 | Validator CLI on the one publication authority, exit contract 0/1/2 | WP02 | — |
| T005 | Corpus gate test: ≥ 500 pages, 0 errors after WP04 | WP02 | — |
| T006 | Gate-can-fail + coverage-failure tests (no green over an empty set) | WP02 | — |
| T007 | `inventory_lockfile.entry_for_page`: `divio_type` from `kind` | WP03 | — |
| T008 | `docs_index`: Divio axis from `kind` | WP03 | — |
| T009 | `frontmatter_backfill`: write `kind`, never the Divio `type` | WP03 | — |
| T010 | Migration `--check` / `--write`, line surgery inside the fence only | WP04 | — |
| T011 | Apply to the 670 published pages; re-run gate to 0/0; idempotence check | WP04 | — |
| T012 | Body-hash baseline + immutability and body-preserving property tests | WP04 | — |
| T013 | Changelog `[Unreleased]` entry + gate reference page | WP05 | — |
| T014 | Record the `description_length_check` deferral and the #6929 overlap | WP05 | — |

## WP01 — Frontmatter contract module + upstream parity

**Prompt**: [tasks/WP01-contract-module.md](tasks/WP01-contract-module.md)

**Summary**
- **Goal**: one module stating the contract (required fields, canonical `kind`/`doc_status`, alias tables, instant grammar) plus the pure resolvers the gate and the migration share.
- **Priority**: P0 — everything imports it.
- **Independent test**: `pytest tests/docs/test_frontmatter_contract.py tests/docs/test_frontmatter_contract_upstream_parity.py -q`.

**Tracking**
- [ ] T001 Contract constants, cited to the upstream file and commit (WP01)
- [ ] T002 Pure resolvers with the documented precedence (WP01)
- [ ] T003 Unit + parity tests (WP01)

**Implementation sketch**
- `CANONICAL_REQUIRED`/`KINDS`/`DOC_STATUSES`/`DOC_TYPES` mirrored from `vocabulary-core.mjs`; `UPDATED_INSTANT_RE`; description band moved here (WP03's `description_length_check` imports it later).
- `KIND_BY_PATH_PREFIX` ordered, longest match; `DRAFT_SECTIONS` (D-8) documented as beating the D-7 alias table for those subtrees.

**Dependencies**: none. **Estimated prompt size**: ~180 lines.

---

## WP02 — Contract validator gate

**Prompt**: [tasks/WP02-validator-gate.md](tasks/WP02-validator-gate.md)

**Summary**
- **Goal**: `python -m scripts.docs.frontmatter_contract --strict` validates the published sections, fails closed, and mirrors doc-kitty's severity split.
- **Priority**: P0 — it is the verdict this mission is judged by.
- **Independent test**: red over the pre-migration tree (exit 1 with a JSON report); green after WP04; exit 2 on a collapsed page set.

**Tracking**
- [ ] T004 CLI, one publication authority, exit contract (WP02)
- [ ] T005 Corpus gate (WP02)
- [ ] T006 Gate-can-fail + coverage failure (WP02)

**Dependencies**: WP01. **Estimated prompt size**: ~150 lines.

---

## WP03 — Port the in-repo Divio readers to `kind`

**Prompt**: [tasks/WP03-divio-readers.md](tasks/WP03-divio-readers.md)

**Summary**
- **Goal**: removing the Divio `type` must not blank the retrieval index or the page inventory; three readers move to `kind` before WP04 rewrites the corpus.
- **Priority**: P1 — a prerequisite for WP04, not an afterthought.
- **Independent test**: inventory lockfile and retrieval index regenerate with no drift; `spec-kitty docs query` answers.

**Tracking**
- [ ] T007 Inventory lockfile (WP03)
- [ ] T008 Retrieval index (WP03)
- [ ] T009 Backfill writer (WP03)

**Dependencies**: WP01. **Estimated prompt size**: ~120 lines.

---

## WP04 — Corpus migration + body immutability proof

**Prompt**: [tasks/WP04-corpus-migration.md](tasks/WP04-corpus-migration.md)

**Summary**
- **Goal**: apply the mapping to 670 published pages with line surgery; prove no body moved; prove idempotence.
- **Priority**: P0 — it is the corpus outcome the issue asks for.
- **Independent test**: second `--write` changes 0 bytes; `git diff -U0` shows frontmatter lines only; gate 0 errors / 0 warnings.

**Tracking**
- [ ] T010 Migration implementation (WP04)
- [ ] T011 Apply + verify (WP04)
- [ ] T012 Immutability baseline and property tests (WP04)

**Dependencies**: WP01, WP03. **Estimated prompt size**: ~200 lines.

---

## WP05 — Changelog, gate docs, recorded deferral

**Prompt**: [tasks/WP05-changelog-docs-deferred.md](tasks/WP05-changelog-docs-deferred.md)

**Summary**
- **Goal**: a changelog entry, a gate reference page that does not pretend to be doc-kitty, and the recorded deferral of the `description_length_check` deletion with its unblocking dependency.
- **Priority**: P2 — process fidelity; required by the delivery procedure.
- **Independent test**: `make docs-lint` passes; the changelog entry names `(#6931)`.

**Tracking**
- [ ] T013 Changelog + gate page (WP05)
- [ ] T014 Deferral + overlap recorded (WP05)

**Dependencies**: WP02, WP04. **Estimated prompt size**: ~90 lines.
