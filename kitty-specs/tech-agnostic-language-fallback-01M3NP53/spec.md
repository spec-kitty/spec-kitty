# Mission Specification: Tech-agnostic fallback for non-Python consumers

**Mission Branch**: `issue-5283-tech-agnostic-language-fallback`
**Created**: 2026-09-29
**Status**: Draft
**Input**: Slice 8 of umbrella #2330 — #5283, #5284, #4614 (plus operator-approved folds: #4613 minimal, and the `spec-kitty review` pytest pre-check). Operator policy (#2330 decision 2026-09-28): Spec Kitty doctrine is tech-agnostic; the default implementation profile is `implementer-ivan`; projects in a language Spec Kitty has no specialist guidance for are advised to extend their local charter with tech-specific guidelines; the fix is NOT to add languages one by one; never suggest Python layouts or files to a non-Python project.

## Intent Summary (confirmed)

- **Primary actor**: a Spec Kitty consumer whose project is implemented in a language Spec Kitty has no specialist guidance for (reproduced with Zig; also Go).
- **Triggers**: (1) running `spec-kitty review` on a merged mission whose changes contain no Python; (2) running `spec-kitty charter generate --from-interview` / `spec-kitty charter context` after declaring e.g. "Zig 0.16.0 is the primary implementation language".
- **Desired outcome**: the review reports the Python-only dead-code check as *not applicable* instead of failing; the charter context never claims Python, renders only language-neutral guidance, and tells the user to extend their local charter; a corrected interview answer takes effect on regeneration.
- **Invariant**: Spec Kitty never falsely labels a project's language, and never fabricates a clean result it could not compute ("not applicable" is a distinct, visible state — never a silent pass or a false "0 findings").
- **Boundary**: recognised languages and Python source missions behave exactly as today. One deliberate, documented change on the Python side: a Python-project mission whose change set holds no scannable source at all (only test files or docs) was previously a hard `DEAD_CODE_UNDETERMINABLE` failure and becomes *not applicable* too, since there is nothing for the gate to decide (post-spec squad MAJOR-5). The structural fix (doctrine-declared gate scope, `ScopeSource`) stays with #2535; #2330 items 2–3 (review-skill hard gates, Python-idiom recipes) are out of scope.

Operator decisions recorded as Decision Moments: `unknown_language_representation` (reserved `unknown` token), `stale_languages_reset` (`--from-interview` re-derives), `dead_code_not_applicable_shape` (skip gate + not-applicable note), `scope_folds` (#4613 minimal + review pytest pre-check; the `available_tools` registry is NOT widened).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Non-Python mission gets an honest review (Priority: P1)

A Zig (or Go) consumer merges a software-dev mission that only changed `*.zig` / `*.go` files and runs `spec-kitty review` (lightweight or post-merge). Today the review fails with `MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE` ("changed source set contains no supported Python files") and exits non-zero, so a non-Python mission can never get a clean review.

**Why this priority**: it blocks every non-Python consumer's mission review outright (#5283, reproduced by samuelgoff on a Zig consumer).

**Independent Test**: build a real git repo containing a merged mission whose diff is only Zig/Go source, run `spec-kitty review` through the CLI, and inspect the console output, the exit code and the written review report.

**Acceptance Scenarios**:

1. **Given** a merged mission whose changed files are only `*.zig` / `*.go`, **When** the user runs `spec-kitty review`, **Then** the dead-code gate is reported as *not applicable* naming the unsupported extensions (e.g. `.go, .zig`), no `DEAD_CODE_UNDETERMINABLE` finding is produced, the dead-code gate is recorded with result `skip` in the review report, one finding of type `dead_code_not_applicable` is recorded, the report never states "0 unreferenced", the exit code is 0 and the verdict is exactly `pass_with_notes`.
2. **Given** the same mission, **When** the not-applicable note is shown, **Then** its remediation text is tech-agnostic: it points the user at extending their local charter with tech-specific review guidance and their own analyzer/test command, and never suggests creating Python files or layouts.
3. **Given** a mission whose change set mixes Python and non-Python files, **When** the user runs `spec-kitty review`, **Then** the Python subset is still scanned for unreferenced public symbols exactly as today (a deliberately unreferenced public symbol is still reported), and the unscanned non-Python remainder is noted as not applicable. A Python-only change set shows **no** not-applicable note (positive control).
3a. **Given** a mission whose change set contains only test-only Python files and/or docs, **When** the user runs `spec-kitty review`, **Then** the gate is not applicable; the note distinguishes excluded test-only Python paths from unsupported extensions and never names `.py` as an unsupported extension.
4. **Given** a Python mission, **When** git is unavailable, git diff fails, or a Python source file cannot be read, **Then** the gate still reports `DEAD_CODE_UNDETERMINABLE` and the verdict fails exactly as today.
5. **Given** a Python mission with a genuinely unreferenced public symbol, **When** the user runs `spec-kitty review`, **Then** the symbol is still reported exactly as today.
6. **Given** a consumer running a Spec Kitty install whose interpreter cannot import pytest, **When** they run `spec-kitty review`, **Then** the review is not blocked before any gate runs: a warning carrying `MISSION_REVIEW_TEST_EXTRA_MISSING` is shown, the gates run and the report is written (the review itself runs no Python tests). The warning is worded as a note about the Spec Kitty installation's own test extra, not as advice to the consumer's project. When pytest is importable, no warning is shown (positive control).

---

### User Story 2 - Unknown-language project gets neutral charter context (Priority: P1)

A consumer answers the charter interview with "Zig 0.16.0 is the primary implementation language" and runs `spec-kitty charter generate --from-interview`, then `spec-kitty charter context --action specify --mission-type software-dev`. Today the context either lists Python-specific guides (an unrecognised language resolves to "no signal", which admits every language-scoped artifact) or advertises `Languages: python`, and generation warns `Ignored unknown available_tools: zig` as if a toolchain were a language problem.

**Why this priority**: misleading planning and review guidance for every non-Python consumer (#5284, reproduced by samuelgoff).

**Independent Test**: in a throwaway initialised project, write the interview answer, run `charter generate --from-interview` and `charter context` through the CLI, and inspect `catalog.languages` and the rendered context.

**Acceptance Scenarios**:

1. **Given** an interview whose languages/frameworks answer declares a language Spec Kitty does not recognise (e.g. "Zig 0.16.0 is the primary implementation language"), **When** the user runs `charter generate --from-interview`, **Then** the compiled charter records the language as the explicit reserved value `unknown`, never `python`.
2. **Given** that compiled charter, **When** the user loads mission context (both the first/full render and the compact render), **Then**: there is no `Languages: python` line and no language-scoped doctrine artifact id (e.g. `python-conventions`, `python-review-checks`, `python-mutation-tools`) is listed; the language-neutral defaults (the `implementer-ivan` implementation guidance) are still rendered (context is not empty); the compact render shows `Languages: unknown`; and exactly one advisory line tells the user that no specialist guidance exists for their language and to add tech-specific guidelines to their local charter, pointing at the how-to page. Positive control: a Python-declaring sibling fixture still lists `python-conventions` and shows no advisory.
3. **Given** an interview whose `available_tools` lists a toolchain Spec Kitty does not register (e.g. `zig`), **When** the user generates the charter, **Then** the diagnostic still names `zig` but describes it as an unregistered tool id (not a language), and `zig` never appears in `catalog.languages` nor feeds language detection.
3a. **Given** the default interview (answers accepted as shipped, whose languages/frameworks answer is generic prose naming no language) or a placeholder answer (empty, "N/A", "none", "TBD", "any", "language-agnostic"), **When** the user generates the charter, **Then** `catalog.languages` stays absent (no signal), never `[unknown]`.
3b. **Given** a languages/frameworks answer naming both a recognised and an unrecognised language (e.g. "Python and Zig"), **When** languages are resolved, **Then** the result is the recognised language only (`[python]`), without `unknown`.
4. **Given** an interview that declares a recognised language (python, typescript, javascript, rust, java, swift, ruby, php), **When** the user generates the charter and loads context, **Then** the result is exactly as today.
5. **Given** an interview that declares no language at all, **When** the user generates the charter, **Then** the result is exactly as today (no language signal).

---

### User Story 3 - Corrected interview answer takes effect on regeneration (Priority: P1)

A consumer's existing charter carries a stale `catalog.languages: [python]` (from an earlier wrong inference). They correct the interview answer and run `spec-kitty charter generate --from-interview`. Today the stale value is read back as authoritative and survives every regeneration (#4614); the only escape is hand-editing a generator-owned section.

**Why this priority**: without it, User Story 2 cannot take effect on any existing charter (#5284 depends on #4614).

**Independent Test**: seed a charter with `catalog.languages: [python]`, correct the answer, regenerate through the CLI, and inspect the field.

**Acceptance Scenarios**:

1. **Given** a compiled charter with `catalog.languages: [python]` and an interview corrected to declare Zig, **When** the user runs `charter generate --from-interview`, **Then** `catalog.languages` becomes `[unknown]`.
2. **Given** the same stale charter and an interview corrected to declare a recognised language (e.g. Rust), **When** the user regenerates from the interview, **Then** `catalog.languages` reflects that language.
2a. **Given** the same stale charter and an interview corrected to a language-agnostic/default answer, **When** the user regenerates from the interview, **Then** `catalog.languages` becomes absent (no signal) — the stale value is not kept and `[unknown]` is not written.
3. **Given** a compiled charter, **When** a runtime consumer (mission context, doctrine resolution) reads the active languages, **Then** the compiled value remains authoritative over the interview transcript (the #2395 / #3292 guarantees are preserved; the existing guard tests stay green unchanged).
4. **Given** a compiled charter, **When** it is recompiled by a path that does not regenerate from the interview (charter activate / pack recompiles, or `charter generate --no-from-interview`), **Then** the recorded languages are preserved.
5. Note: `--from-interview` is the default for `charter generate`, so every plain regeneration re-derives languages from the interview and replaces a hand-edited `catalog.languages`; this is documented (FR-016).

---

### User Story 4 - Rejected technologies do not activate a language (Priority: P3)

A consumer lists rejected options in prose (e.g. "librespot-java") and Spec Kitty activates Java doctrine (#4613).

**Why this priority**: same "never falsely label a language" invariant, same detection table; deliberately minimal.

**Independent Test**: extraction over prose containing hyphenated compounds.

**Acceptance Scenarios**:

1. **Given** interview prose mentioning `librespot-java` (a language token preceded by a word and a hyphen) and no other Java signal, **When** languages are extracted, **Then** Java is not activated.
2. **Given** prose saying "Java 21 with Gradle", "Java-based backend" or "Python-based services", **When** languages are extracted, **Then** the language is still activated (a trailing `-based` style compound is unchanged).

### Edge Cases

- A change set containing only test-only Python files plus non-Python source: the Python files do not count as supported (today's filter), so the change set is not applicable — the outcome must not be `DEAD_CODE_UNDETERMINABLE`, and `.py` is never listed as unsupported.
- After FR-018 no built-in doctrine is scoped to `go`, so "Go 1.22" resolves to `[unknown]` and still receives every language-neutral tactic; a language named in the answer that a project/org pack is scoped to resolves as recognised (FR-017); "HTML with Zig" resolves to `[html]` (html is backed by the frontend profile).
- The literal "unknown" already appears elsewhere with another meaning (code-evidence `primary_language="unknown"` = nothing detected, shown by `charter status`); that usage is unchanged and is not the reserved catalog value.
- A languages/frameworks answer naming only a framework (e.g. "Django") or a typo ("Pyhton") resolves to `unknown` — accepted: C-001 forbids growing the table; the advisory covers it.
- Free-prose answers other than the languages/frameworks answer can only ever add recognised languages; they never signal `unknown`.
- Tactics scoped to several named languages (not unscoped) also stop applying to an `unknown` project — intended and documented.
- A doctrine artifact cannot declare `unknown` as a language it applies to (reserved, like the existing any/all sentinels), so no pack can become a second authority for unknown-language projects.
- A change set of only non-source files (e.g. docs/markdown/yaml): not applicable, naming the extensions; files without an extension are named as such.
- An empty change set (git diff reports no changed files): behaviour unchanged.
- A project that declares both a recognised and an unrecognised language: the recognised language resolves as today; `unknown` is not added alongside it.
- A hand-edited `catalog.languages` containing `unknown` together with real languages: runtime reads must not crash; the real languages still admit their artifacts.
- A charter compiled before this mission containing `catalog.languages: []`: meaning unchanged (admit none).
- The legacy migration that carries `references.yaml` languages into `catalog.languages` must not be broken by the new value.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Dead-code gate reports not applicable when no supported files changed | As a non-Python consumer, I want a change set with no files the dead-code gate supports to be reported as *not applicable* (naming the unsupported extensions, sorted, de-duplicated) so that my mission review is not failed by a Python-only analyzer. | High | Open | [build] | no — a Zig-only CLI review today yields `DEAD_CODE_UNDETERMINABLE` and rc=1 |
| FR-002 | Not-applicable outcome is non-failing and distinct | As a reviewer, I want the not-applicable outcome recorded as gate result `skip` (the gate record becomes tri-state pass/fail/skip), one finding of type `dead_code_not_applicable` with its own diagnostic code (`MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE`), a visible note in the console and report, verdict exactly `pass_with_notes` and exit 0 — never a pass with "0 unreferenced" and never a hard failure — so that the result is honest. | High | Open | [build] | no — asserted on the same Zig-only fixture via report gate record + finding type |
| FR-003 | Tech-agnostic remediation | As a non-Python consumer, I want the not-applicable remediation to point me at extending my local charter with tech-specific review guidance and my own analyzer/test command, with no Python file/layout suggestion, so that the advice fits my stack. | High | Open | [build] | no — asserted text on the same fixture; a negative assertion bans Python-layout advice |
| FR-004 | Mixed change sets keep scanning the Python subset | As a mixed-language consumer, I want the Python subset scanned as today and the non-Python remainder noted as not applicable, so that Python dead code is still caught. | High | Open | [ratchet] | yes — paired with FR-001 on a mixed fixture that must still report the unreferenced Python symbol |
| FR-005 | Genuine undeterminable cases unchanged | As a Python consumer, I want git-unavailable, git-diff-failure and unreadable-source cases to stay `DEAD_CODE_UNDETERMINABLE` + fail, so that real inability to decide is never hidden. | High | Open | [ratchet] | yes — paired positive control: the existing undeterminable tests must still pass unchanged |
| FR-006 | Error code documented | As an integrator, I want `ERROR_CODES.md` to document the not-applicable outcome and the undeterminable section to stop listing "no supported Python files" as a cause, so that the contract is discoverable. | Medium | Open | [build] | no — the existing documented-codes gate fails when a new enum member lacks a section |
| FR-007 | Review not blocked by a missing Python test runner | As a non-Python consumer on a Spec Kitty install without pytest, I want `spec-kitty review` to warn (not exit) with `MISSION_REVIEW_TEST_EXTRA_MISSING`, still run the gates and write the report, since no review gate runs Python tests, so that I can review at all. The code stays documented with its severity changed to warning, worded as a Spec Kitty installation note. | Medium | Open | [build] | no — today the CLI exits 1 with `MISSION_REVIEW_TEST_EXTRA_MISSING` before any gate |
| FR-008 | Unknown language is explicit, never python | As a consumer in an unrecognised language, I want a declared-but-unrecognised language to resolve to the reserved value `unknown`, so that my project is never labelled Python. "Declared but unrecognised" holds only when ALL of: no recognised language is found across the answers; the languages/frameworks answer is non-empty; it differs from the shipped default answer; and it is not a placeholder (empty, `[]`, `None`, N/A, none, TBD, any, language-agnostic, unknown, a NEEDS CLARIFICATION marker). A language named in that answer that active doctrine is scoped to counts as recognised (FR-017). The rule lives in the single language authority so pre-compile reads agree with compile. | High | Open | [build] | no — a Zig interview today compiles to an absent field (admit-all) |
| FR-009 | `unknown` admits no language-scoped artifacts | As a consumer in an unrecognised language, I want no Python (or other language-specific) styleguides/toolguides/tactics/checks to resolve for my project, so that only tech-agnostic doctrine applies. `unknown` is reserved: a doctrine artifact cannot declare it as a language it applies to (rejected at authoring time; ignored at runtime so it can never make an artifact load for unknown-language — or all — projects). Language-scoped agent profiles (e.g. python-pedro) also stop being listed/dispatched for an unknown project; `implementer-ivan` remains the default. | High | Open | [build] | no — today a Zig context lists python-conventions / python-review-checks |
| FR-010 | Neutral context with charter-extension advisory | As a consumer in an unrecognised language, I want mission context (both the full and the compact render) to show the language-neutral (`implementer-ivan`) guidance and exactly one advisory line to extend my local charter with tech-specific guidelines, and the compact render to show `Languages: unknown`, so that I know what to do. Renderers ask the language authority whether the project is unknown-language rather than testing the literal string. | High | Open | [build] | no — asserted on the rendered context of the Zig fixture |
| FR-011 | Tools validated separately from language | As a consumer, I want an unregistered `available_tools` entry reported with a tool-specific message naming it as an unregistered tool id (e.g. `available_tools: 'zig' is not a registered tool id; ignored (tool ids are validated separately from project languages)`), and tool names never used as language signals, so that a toolchain is not mistaken for a language. The tool registry is not widened; other catalog labels keep their current message. (Verified: `available_tools` values are not part of the prose scanned for languages; tool words written in free prose, e.g. "pytest", remain Python signals — out of scope, #4613 remainder.) | Medium | Open | [build] | no — the current diagnostic text `Ignored unknown available_tools: zig` is asserted to change |
| FR-012 | `--from-interview` re-derives languages | As a consumer, I want `charter generate --from-interview` (the default) to derive `catalog.languages` from the current interview instead of reading back the previously compiled list — including clearing it to absent when the corrected interview declares no language — so that a corrected answer takes effect. The bypass is an explicit precedence parameter of the single language authority, set only by the from-interview generate path; there is no second derivation function. | High | Open | [build] | no — stale `[python]` survives today |
| FR-013 | Runtime readers keep compiled-first precedence | As a maintainer, I want runtime language reads (context, doctrine resolution) and non-interview recompiles (activate/pack) to keep treating the compiled value as authoritative, so that #2395 and #3292 are not reopened. | High | Open | [ratchet] | yes — paired with FR-012 on the same stale-charter fixture: runtime read returns the compiled value |
| FR-014 | Recognised languages unchanged | As an existing consumer, I want recognised languages and language-less interviews to resolve exactly as today, so that nothing regresses. | High | Open | [ratchet] | yes — paired with FR-008 on sibling fixtures (rust / python / none) |
| FR-015 | Hyphenated compounds do not activate a language | As a consumer documenting rejected options, I want a language token preceded by a word and a hyphen (e.g. `librespot-java`) not to activate that language, so that listing a dead end does not activate its doctrine (#4613, minimal). Trailing compounds ("Java-based") are unchanged. | Low | Open | [build] | no — `librespot-java` activates java today; paired positive controls "Java 21 with Gradle", "Java-based backend", "Python-based services" still activate |
| FR-017 | Doctrine-derived language vocabulary | As a consumer in a language the built-in detector does not list but for which active doctrine carries genuinely language-specific guidance (e.g. `html`/`css` via the frontend profile, `twig` via the Drupal profile, or a language a project/org pack is scoped to), I want that language, when named as a whole word in the languages/frameworks answer, to resolve as recognised (e.g. `[twig]`) so that its scoped guidance still applies and `unknown` truly means "no specialist guidance exists". The vocabulary is derived from the scopes declared by active doctrine artifacts — never a hardcoded per-language addition (C-001). | High | Open | [build] | no — with a synthetic project-pack artifact scoped to `elixir`, an 'Elixir 1.17' answer must resolve to `[elixir]`; paired control: a Zig answer (no zig-scoped doctrine) resolves to `[unknown]` |
| FR-018 | Language-independent tactics are not language-scoped | As a consumer in any language, I want language-independent built-in tactics (catastrophic-regex backtracking, chain-of-responsibility rule pipeline, dependency hygiene) to apply to every project instead of being hidden behind a language scope, with any language-specific snippets labelled as examples and no Spec Kitty repo-internal paths, so that tech-agnostic doctrine is actually tech-agnostic (operator directive 2026-09-29). The generic-artifact language-bias gate no longer exempts an artifact merely because it declares a scope. | High | Open | [build] | no — today these tactics are excluded for an unknown-language (and any unlisted-language) project; after the change they resolve for `[unknown]` |
| FR-016 | User-facing guidance documented | As a consumer, I want a how-to page (in the published user guides, governance section, cross-linked from charter troubleshooting) explaining how to extend the local charter for an unsupported language, what `unknown` means and what stops applying, and that `--from-interview` regeneration refreshes (and replaces hand edits of) languages, so that the advisory has a destination. | Medium | Open | [build] | no — the advisory text links/points to a doc page that must exist |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No regression for Python consumers | 100% of the pre-existing targeted tests for the dead-code gate, language scope, charter compile/context and review command pass, except tests that deliberately pinned the defect being fixed, each of which is re-pinned with a dated rationale citing this mission. | Reliability | High | Open |
| NFR-002 | CLI latency | `spec-kitty review` and `spec-kitty charter context` wall time on a typical project does not grow by more than 100 ms from this change. | Performance | Medium | Open |
| NFR-003 | Code quality gates | New/changed code passes `ruff check`, `ruff format --check` and `mypy` with zero new issues; no function exceeds cyclomatic complexity 15; every new branch/helper has a focused test in the same change (≥90% diff coverage). | Maintainability | High | Open |
| NFR-004 | Red-first evidence | Each acceptance scenario of stories 1–3 has a CLI-level test that fails on the mission's planning base and passes on the final commit; every refusal/absence assertion is paired with a positive control on the same fixture; FR-001/002/003 are proven half-by-half (reverting the skip, or the remediation text, turns the test red). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No per-language additions | The fix must not add new languages to the detection table as the solution; `unknown` is the only new language value. | Business | High | Open |
| C-002 | No Python advice to non-Python projects | No output reachable by a non-Python project suggests Python files, layouts or tools. | Business | High | Open |
| C-003 | Structural fix stays with #2535 | Do not build the doctrine-declared `ScopeSource` early; do not touch #2330 items 2–3 (review-skill hard gates, Python-idiom recipes). | Technical | High | Open |
| C-004 | Sibling-owned surfaces untouched | Do not edit consolidation/*, tests/integration/**, golden/snapshot fixtures under tests/specify_cli/**, doctor/decision surfaces, review/arbiter.py or the move-task override (owned by sibling sessions); do not edit built-in software-dev guidelines owned by mission squad-doctrine-single-owner-01M3KBP7 (#5202). Non-golden review test modules under tests/specify_cli/cli/commands/ (test_review.py, review/test_dead_code_baseline*.py, review/test_diagnostic_codes_documented.py) may be edited. | Technical | High | Open |
| C-005 | Pack tiers | The consumer-facing advisory string is product code (a constant in the charter activation layer), not a built-in pack artifact; no in-house maintainer guidance is placed in built-in doctrine. If packs are touched anyway, graph regeneration is required. The advisory must pass the doctrine neutrality lint and terminology guard. | Technical | High | Open |
| C-006 | Do not regenerate the dogfood charter | The repository's own `.kittify/charter/charter.yaml` is not regenerated by this mission. | Technical | Medium | Open |
| C-007 | No heavy suites during the mission | Per NO_FULL_HEAVY_SUITES_IN_MISSION, implement/review/closeout run only targeted test files, owning-module fast tiers and named architectural gates. | Technical | High | Open |

### Key Entities

- **Active project languages**: the set of language identifiers governing which language-scoped doctrine applies. States: *absent* (no signal — admit every scoped artifact), *empty* (admit none), *list of recognised languages*, and the new *`unknown`* (declared but unrecognised — admit no language-scoped artifacts, render neutral guidance + advisory).
- **Dead-code gate outcome**: pass (scanned, maybe with unreferenced symbols as notes), undeterminable (should decide but could not — failure), and the new *not applicable* (nothing in a supported language to scan — skipped, non-failing, visible).
- **Charter-extension advisory**: the one-line consumer-facing pointer to add tech-specific guidelines to the local charter.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A mission whose diff is only Zig/Go source completes `spec-kitty review` with the dead-code gate marked not applicable and a verdict other than `fail`, in 100% of CLI runs of the acceptance fixture — [build] · no-op passable: no
- **SC-002**: A Zig-declaring interview yields a charter context with zero references to Python and exactly one charter-extension advisory line — [build] · no-op passable: no
- **SC-003**: Starting from a stale `catalog.languages: [python]`, one corrected-answer regeneration updates the field (0 hand edits required) — [build] · no-op passable: no
- **SC-004**: All recognised-language and Python-review behaviours covered by the pre-existing targeted tests are unchanged (0 unexplained regressions) — [ratchet] · no-op passable: yes — paired with SC-001..003 on sibling fixtures

## Assumptions

- "Supported files" for the dead-code gate remain exactly today's Python filter; extending analyzer support to other languages is out of scope (C-001, #2535).
- The review's pytest pre-check guards no gate that actually executes Python tests (verified during grounding: the review gates are lane check, dead-code string scan, BLE001 audit, issue matrix); downgrading it to a warning therefore loses no safety. The post-plan squad re-verifies this.
- The advisory's destination is a user-facing documentation page shipped with the product docs.

## Out of Scope / Follow-ups

- Negated-context / sentiment detection and a structured languages interview field (#4613 remainder).
- Widening the `available_tools` registry to accept arbitrary executables (operator declined).
- Doctrine-declared gate scope / `ScopeSource` (#2535); #2330 items 2–3.
- Language-filtered profile routing (#2213).
- Latent #3292-pattern bug: the charter-activation finalize migration collapses an absent languages field to `[]` (admit none) — filed as follow-up #5335, not fixed here.
