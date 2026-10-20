# Mission Specification: Charter follow-ups tidy-up (#6539-#6543)

**Mission**: `charter-followups-tidy-01M5CCYJ`
**Source issues**: #6539, #6540, #6541, #6542, #6543. All five are follow-ups that the #6511 landing review did not fold in.
**Status**: Draft
**Decisions**: five operator Decision Moments, recorded under `decisions/`:
- `migration_repo_requirement`
- `seam_language_catalog`
- `seam_language_export_shape`
- `interview_language_write_order`
- `migration_flag_ledger_drift`

## Intent Summary

Close the five follow-ups left by the charter synthesis graph and languages Mission (#6511). Each one leaves a correctness or contract gap:

1. **Upgrade runner.** A migration that needs a git repository says so up front. Outside a repository the runner skips it before it can write anything. A migration that raises the "not inside a repository" error while applying is recorded as a failure and retried, never hidden as a clean skip (#6539).
2. **Import cycle.** The language settlement no longer hides an import cycle between the language authority and the evidence reader (#6540).
3. **Seam.** The language token list, as plain token strings, is part of the public charter offering seam, so the charter service and the conformance corpus can rely on it. The catalog's records, their family data and the family expansion (`jvm`) stay internal (#6541).
4. **Interview.** `charter interview` still proposes and asks for the project languages first. It writes them to `.kittify/config.yaml` only after the interview answers are written. An aborted or failed interview writes neither (#6542).
5. **Reconcile tests.** Synthesis reconciliation is proven to treat a table styleguide edge from a shipped but unselected directive as resolved, and an edge to a URN nothing ships as dangling (#6543).

Primary actors:
- the operator running `spec-kitty upgrade` (including outside a git repository);
- the operator running `charter interview`, interactively or not;
- downstream consumers of `charter.offering.api`, such as the charter service and the conformance corpus.

## User Scenarios & Testing *(mandatory)*

### User Story 1: An upgrade outside a git repository never hides a partial write (Priority: P1)

An operator runs `spec-kitty upgrade` in a project directory that is not inside a git repository.

- A migration that declares it needs a repository is skipped before any of its steps run. Nothing is recorded, so a later upgrade inside a repository applies it.
- A migration that does not declare the requirement, but raises the "not inside a repository" error while applying, is handled as a failed migration.

"Not inside a repository" means exactly the condition for which the canonical repository-root resolver raises its not-inside-a-repository error. A project in a subdirectory of a repository is inside one.

**Why this priority**: today a migration that writes and then raises would be reported as a clean skip, with its partial changes left on disk. That is a silent-corruption shape.

**Independent Test**: run the upgrade runner on a non-git temporary project with three migrations:
- a flagged migration whose steps would raise: skipped, no record, `detect()` never called;
- an unflagged migration that writes a file and then raises from `apply()`: recorded `failed`, with the written file visible;
- the shipped `3.2.0rc35_unified_bundle`: skipped.

**Acceptance Scenarios**:

1. **Given** a non-git project and a migration declaring that it needs a repository, **When** the upgrade runs, **Then** the migration is skipped with a "not inside a git repository" warning, its `detect()` is never called, and no ledger record is written.
2. **Given** a non-git project and an undeclared migration whose `apply()` raises the "not inside a repository" error, **When** the upgrade runs, **Then** the error is caught and handled like any other failed migration:
   - it is recorded `failed`, except a `runs_first` migration, which records no failure, as today;
   - the command reports the failure and exits non-zero, with no traceback;
   - the existing failed-migration handling of the version stamp applies.
3. **Given** a git project, **When** the upgrade runs, **Then** a migration declaring the requirement runs exactly as before.
4. **Given** a non-git project directory carrying `.kittify/metadata.yaml` at the oldest supported version and an empty ledger, **When** the full shipped registry runs with the canonical repository-root resolver instrumented, **Then**:
   - every migration that calls the resolver declares `requires_git_repository`;
   - the run reaches the last migration in the order manifest.

   This is the #6437 regression guard. It fails on today's code, where no migration declares the flag.
5. **Given** a non-git project, **When** the operator previews the upgrade (`spec-kitty upgrade --dry-run --verbose`), **Then** a migration declaring the requirement is reported as not applicable outside a repository, and the preview does not crash.

### User Story 2: Interview languages are written with the answers, never before (Priority: P1)

An operator runs `charter interview`. The detected languages are proposed, and either confirmed (interactive) or taken as detected (non-interactive, key absent). The interview then asks its questions.

- If the interview is aborted or fails before its answers are written, `.kittify/config.yaml` keeps its previous `languages:` value, or stays without the key.
- If the interview completes, the answers and the settled `languages:` are both written.

**Why this priority**: a half-finished interview must not leave project configuration behind that changes evidence, doctrine scoping and the bundle hash.

**Independent Test**: drive the interview command with (a) an abort after the language step, (b) a failure while writing answers, and (c) a completed run. Check `config.yaml` and the answers file after each.

**Acceptance Scenarios**:

1. **Given** no `languages:` key and a non-TTY interview without `--defaults`, whose stdin is empty so the prompt aborts after the language step, **When** it exits, **Then** `config.yaml` has no `languages:` key and no answers file was written.
2. **Given** no `languages:` key and an interview whose answers write fails, **When** it exits, **Then** `config.yaml` has no `languages:` key.
3. **Given** an interactive interview where the operator confirms a changed list, **When** it then stops at a later question, **Then** the previous `languages:` value is unchanged. This holds for each of these:
   - an abort;
   - a keyboard interrupt;
   - a Decision Moment error;
   - an answer-override error.
4. **Given** a completed interview, **When** it exits, **Then**:
   - the answers and the settled `languages:` are both written, in the order answers → languages → selection promotion (the promotion re-reads `config.yaml`, so it keeps the languages);
   - the JSON output still carries `languages`, `languages_source` and `languages_notice`;
   - under `--narrow-activation`, a promotion failure leaves the answers and the languages written, as the answers are today.
5. **Given** a set `languages:` key, usable or not, and a non-interactive run, **When** the interview completes, **Then** the key is never overwritten. Existing rule `DM-01M5ASPC7101YP5CQE54DC3G3Z`, unchanged.

### User Story 3: The language token list is a public offering contract (Priority: P2)

A consumer of the charter offering seam (the charter service, the conformance corpus, a UI) reads the catalog's language tokens through `charter.offering.api`, not through internal modules.

**Independent Test**: import `LANGUAGE_TOKENS` from `charter.offering.api`. It must be a tuple of plain strings equal to the catalog's tokens, in catalog order, and the public-surface and census gates must stay green.

**Acceptance Scenarios**:

1. **Given** the seam, **When** a consumer imports `LANGUAGE_TOKENS` from it, **Then** it gets a tuple of plain token strings (for example `python`, `kotlin`, `java`) equal to the catalog's tokens, in catalog order.
2. **Given** the seam, **When** a consumer looks for `LANGUAGES`, `LanguageSpec` or the family-expansion helpers, **Then** none of them is exported.

### User Story 4: The language settlement has a one-way dependency (Priority: P2)

A maintainer can see from the imports how the language modules depend on each other. No deferred import is left to break a cycle, and a test pins the direction.

**Acceptance Scenarios**:

1. **Given** the source of the language authority and the evidence reader, **When** their imports are inspected, **Then**:
   - neither imports the other inside a function body or under a type-checking guard;
   - the only edge between them is evidence reader → language authority;
   - the settlement imports both at module level.

### User Story 5: Reconcile classifies table edges like the validation gate (Priority: P3)

**Acceptance Scenarios**:

1. **Given** a project overlay carrying a table styleguide edge from a shipped directive that is not selected, **When** synthesis reconciles, **Then** no `preserved_dangling_endpoint` conflict is reported for that edge.
2. **Given** an overlay edge naming a URN that no layer ships, **When** synthesis reconciles, **Then** it is reported as `preserved_dangling_endpoint`.

### Edge Cases

- A migration's `detect()` or `can_apply()` reaches the repository root without declaring the requirement. It is still skipped: those steps run before any write, so their catches stay. The full-registry audit (US1 AC4) instruments the resolver, so such a migration is still found and gets the flag.
- The worktree upgrade loop is out of scope: a worktree is always inside a repository.
- `charter interview --defaults` with no `languages:` key used to write `config.yaml` before anything else. It now writes it only after the answers are written.
- Writing the answers succeeds but writing `config.yaml` fails:
  - the failure is surfaced (non-zero exit with a visible error), never swallowed;
  - the answers stay written, since two files cannot be written atomically;
  - the JSON output, when printed, does not claim the languages were stored.
- A `languages:` key that is set but unusable keeps its existing notice and is never overwritten.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Declared repository requirement | As an operator, I want a migration that needs a git repository to declare it, so that the runner skips it outside one, before any step and in the dry-run preview too. | High | Open | [build] | no — a flagged migration whose detect() would raise must be skipped with detect() never called |
| FR-002 | apply()-time repository error is a failure | As an operator, I want a migration whose apply() raises the not-inside-a-repository error to be handled as a failed migration (recorded failed unless runs_first, non-zero exit, no traceback), so that a partial write is never reported as a clean skip. | High | Open | [build] | no — today it is a skip with no record; paired with FR-001's skip on the same non-git fixture |
| FR-003 | Shipped migrations declare the requirement | As an operator, I want every shipped migration that calls the repository-root resolver to declare the requirement, so that upgrading outside git records no failure and #6437 stays fixed. | High | Open | [build] | no — the instrumented full-registry audit fails until the callers declare the flag |
| FR-004 | Interview writes languages with the answers | As an operator, I want charter interview to write the settled languages to config.yaml only after the answers are written and before selection promotion, so that an aborted or failed interview writes neither. The language-settlement API of charter.activation.api splits into a pure decide step and an explicit store step; activation stays in core (ADR 2026-10-16-1). | High | Open | [build] | no — an abort after the language step leaves config.yaml unchanged, and a completed run writes both |
| FR-005 | Interview contract unchanged | As a consumer of the interview JSON, I want languages, languages_source and languages_notice unchanged, and the never-overwrite rule kept, so that callers and the operator decision still hold. | High | Open | [ratchet] | yes — pinned by the existing interview-language tests; paired with FR-004 on the same fixtures |
| FR-006 | One-way language settlement dependency | As a maintainer, I want the language settlement to depend on the authority and the evidence reader one-way, with no function-level or type-checking-only import between them, so that the cycle is visible and cannot return. | Medium | Open | [build] | no — an AST test asserts there is no such import, and it fails on today's deferred import |
| FR-007 | Language tokens on the offering seam | As a seam consumer, I want a read-only LANGUAGE_TOKENS tuple of plain token strings, derived from the catalog, exported from charter.offering.api with a PUBLIC census disposition and a facade re-export, so that the token list is a stable contract. | Medium | Open | [build] | no — the import test fails until the symbol is exported |
| FR-008 | Catalog records and families stay internal | As a maintainer, I want LANGUAGES, LanguageSpec and the language-family helpers kept off the seam, so that the jvm semantics and declared-answer patterns are not frozen as a contract. | Medium | Open | [ratchet] | yes — paired with FR-007's positive import on the same seam |
| FR-009 | Reconcile table-edge classification | As a maintainer, I want reconcile tests proving that a table edge from a shipped but unselected directive is not dangling and that an unshipped URN still is, so that reconcile matches the validation gate. | Low | Open | [ratchet] | yes — non-vacuity is shown by mutating the classification (dropping the shipped-endpoint folding) and seeing the positive case go red, with the negative case on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new suppressions | Zero new `# noqa` / `# type: ignore` in the diff; ruff, `ruff format --check --force-exclude` and mypy report 0 new issues on changed files. | Maintainability | High | Open |
| NFR-002 | Complexity ceiling | Every touched function stays at cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | Red-first proof | Every FR marked `[build]` has a test that fails on the pre-change source and passes after. | Reliability | High | Open |
| NFR-004 | Single-language hashes stable | Evidence and bundle hashes of the existing charter fixtures are byte-identical before and after (no behavioural change outside the interview write timing). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Settled operator decisions | The five Decision Moments of this Mission bind the behaviour. Changing any of them needs a new operator decision. | Business | High | Open |
| C-002 | Ledger drift accepted | Declaring the flag edits shipped migration modules. The resulting audit-only `content_hash` drift is accepted and documented (changelog, PR, ADR 2026-10-17-1 note), never hidden. | Technical | High | Open |
| C-003 | Seam widening documented | Adding `LANGUAGE_TOKENS` to the frozen seam gets an amendment note in ADR 2026-10-03-1 (seam scope) and a conformance-corpus case filed against epic #6099. The corpus itself is not built here. | Technical | High | Open |
| C-004 | Detect/can_apply catches stay | The runner's `NotInsideRepositoryError` skips around `detect()` and `can_apply()` stay, because they run before any write. Only the `apply()`-level catch changes. | Technical | Medium | Open |
| C-005 | Never-overwrite rule kept | `DM-01M5ASPC7101YP5CQE54DC3G3Z` is unchanged: store the detected list non-interactively only when the key is absent, notify, and never overwrite a set key. | Business | High | Open |

### Key Entities

- **Migration repository requirement**: a declared, per-migration fact ("this migration needs a git repository"). It defaults to "no".
- **Language settlement**: the proposed or confirmed language list, its source and its notice. It is held until the interview answers are written.
- **`LANGUAGE_TOKENS`**: the catalog's ordered language tokens as plain strings, read-only, derived from the internal `LANGUAGES` records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A non-git upgrade over the full shipped registry reaches the last migration, and every migration that needs a repository declares it — [build] · no-op passable: no
- **SC-002**: A migration that writes and then raises the repository error is reported as a failure in 100% of runs, never as a skip — [build] · no-op passable: no
- **SC-003**: An interview aborted after the language step leaves the project's language setting unchanged in 100% of runs — [build] · no-op passable: no
- **SC-004**: The language token list is importable from the public offering seam as plain strings, and 0 catalog records or family-expansion helpers are — [build] · no-op passable: no
- **SC-005**: 0 function-level imports remain between the language authority and the evidence reader — [build] · no-op passable: no

## Assumptions

- The only module that raises `NotInsideRepositoryError` today is `charter.resolution.resolve_canonical_repo_root`. Shipped migrations reach it directly (rc35) or through `charter.activation.*`. An execution-based audit with the resolver instrumented, not grep, decides which migrations declare the flag.
- The answers file and `config.yaml` cannot be written atomically. The order is answers → languages → selection promotion, and a languages write failure is surfaced.
- The conformance corpus lives outside this repository (spec-kitty-charter, epic #6099).

## Out of Scope

- Exposing `LANGUAGES`, `LanguageSpec`, the family expansion or any other symbol on the seam.
- Building the conformance-corpus case itself.
- Changing what any migration does when it runs, other than declaring the flag.
- The worktree upgrade loop.
- Atomic multi-file writes.
