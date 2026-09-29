# Work Packages: Tech-agnostic fallback for non-Python consumers

**Inputs**: Design documents from `kitty-specs/tech-agnostic-language-fallback-01M3NP53/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-outputs.md, quickstart.md

**Tests**: Required — the charter mandates ATDD/red-first (C-011) and every FR row names its non-vacuity control. Each WP opens with a failing-first test commit through the pre-existing entry point.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtask rows are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

**⛔ HARD RULE (every implementer and reviewer):** never run full or heavy suites — no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites, no `make test-full`, no whole-repo pytest. Per WP run only the test files covering the files the WP touches, the owning module's fast tier, and the specific NAMED architectural gate files the change implicates (NO_FULL_HEAVY_SUITES_IN_MISSION).

**Lanes**: Lane A = WP01 (review gate, independent). Lane B = WP02 → WP03 → {WP04, WP05} → WP06 (WP06 also waits on WP01 and WP07). WP07 (doctrine de-scoping) is independent.

---

## Work Package WP01: Review — dead-code gate not applicable + pytest pre-check warning (Priority: P1)

**Goal**: A change set with nothing the Python-only dead-code gate can scan is recorded as a skipped gate with a non-failing, tech-agnostic not-applicable note; the missing-pytest pre-check warns instead of exiting (#5283 + fold).
**Independent Test**: Real-git CLI review of a Zig/Go-only merged mission → `pass_with_notes`, rc 0, gate `skip`, `dead_code_not_applicable` finding; Python behaviour unchanged.
**Prompt**: `tasks/WP01-review-dead-code-not-applicable.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-004, C-002, C-003
**Estimated prompt size**: ~430 lines

### Included Subtasks

T001 Red-first CLI acceptance tests: Zig/Go-only, mixed Zig+py, tests-only/docs-only, missing-pytest (WP01)
T002 Discovery outcome: `_Discovery`/`scan_dead_code` return a not-applicable outcome with unsupported extensions + excluded test paths (WP01)
T003 Not-applicable finding, diagnostic code, tech-agnostic remediation constant, report formatter (WP01)
T004 Tri-state gate recording: widen `_record_gate`, record `skip` from the scan outcome (WP01)
T005 pytest pre-check → warning (stdout JSON keeps code + `severity: warning`); re-pin `test_review.py` (WP01)
T006 Re-pin deliberately-pinned tests: `test_unsupported_non_python_change_is_undeterminable`, enum count 15→16, 2987 baseline record note (WP01)
T007 `ERROR_CODES.md`: new DEAD_CODE_NOT_APPLICABLE section; UNDETERMINABLE cause list; TEST_EXTRA_MISSING severity (WP01)
T008 Neutrality + half-by-half proof tests for the remediation text (WP01)

### Dependencies

- None (starting package, lane A).

### Risks & Mitigations

- Gate currently records `fail` whenever any finding is appended → decide `skip` from the returned scan outcome, keep plain `dead_code` → `fail`.
- `_format_finding_line` silently drops unknown types → formatter + report-content assertion.

---

## Work Package WP02: Reserved `unknown` vocabulary, validator guard, catalog-miss advice, advisory text (Priority: P1)

**Goal**: Introduce `unknown` as a reserved language value at the lowest layer with consistent admit semantics (admit no scoped artifacts; never a scope an artifact can declare), the authoring-time guard, the catalog-miss branch, and the single charter-extension advisory constant.
**Independent Test**: `applies_to_languages_match` truth table incl. `[unknown]` active/artifact sides; `doctrine validate` rejects `applies_to_languages: [unknown]` with its own message; scope-filtered catalog miss for an unknown project points at the advisory.
**Prompt**: `tasks/WP02-reserved-unknown-vocabulary.md`
**Requirement Refs**: FR-009, FR-010, C-001, C-002, C-005
**Estimated prompt size**: ~360 lines

### Included Subtasks

T009 Red-first tests: scoping truth table, validator rejection, catalog-miss suggestion, advisory neutrality (WP02)
T010 `scoping.py`: `UNKNOWN_LANGUAGE`, `RESERVED_LANGUAGE_TOKENS`, `is_unknown_language`, strip-both-sides rule (WP02)
T011 `doctrine.py` validator imports the sets from `scoping` (remove the duplicate), separate message for `unknown` (WP02)
T012 `language_advisory.py`: `CHARTER_EXTENSION_ADVISORY` constant (+ `__all__`) (WP02)
T013 `_catalog_miss.py`: unknown-language branch using `is_unknown_language` + the advisory (WP02)

### Dependencies

- None within lane B (first package). Can start in parallel with WP01.

### Risks & Mitigations

- Do NOT add `unknown` to `_SENTINEL_TOKENS` (sentinels load everywhere).
- Dead-symbol gate: every new `__all__` name needs a `src/` caller inside this WP.

---

## Work Package WP03: Language authority — `unknown` detection, hyphen rule, precedence parameter (Priority: P1)

**Goal**: A memoized doctrine-derived language vocabulary provider (languages genuinely language-specific doctrine is scoped to, e.g. twig/html, or a project-pack language — operator decision, FR-017) and `infer_repo_languages` resolving a declared-but-unrecognised language to `[unknown]` (only from the languages/frameworks answer, defaults/placeholders excluded, doctrine vocabulary consulted first), hyphen-prefixed compounds stop matching, and a `prefer_interview` parameter enables the regenerate-only bypass (#5284 core, #4613 minimal, #4614 authority half).
**Independent Test**: Unit + characterization tests over `infer_repo_languages`/`extract_declared_languages`: Zig → `[unknown]`; defaults/N/A/`[]` → None; "Python and Zig" → `[python]`; synthetic `elixir`-scoped overlay + "Elixir 1.17" → `[elixir]`; `librespot-java` → nothing; "Java-based" → java; compiled-first guards unchanged; `prefer_interview=True` skips tier 1.
**Prompt**: `tasks/WP03-language-authority-unknown.md`
**Requirement Refs**: FR-008, FR-012, FR-013, FR-014, FR-015, FR-017, NFR-001, NFR-002, C-001
**Estimated prompt size**: ~560 lines

### Included Subtasks

T014 Campsite (behaviour-preserving, own commit): `ruff format` fix, characterization tests pinning today's tier semantics (WP03)
T015 Red-first tests: detection, placeholders, vocabulary, hyphen rule, precedence parameter (WP03)
T016 Doctrine-derived vocabulary provider `charter.activation.language_vocabulary` (unfiltered load, lazy imports, cache, timing) (WP03)
T017 Hyphen-prefix guard `(?<!\w-)` on every `_LANGUAGE_PATTERNS` entry (WP03)
T018 Unknown detection rule in tier 2 (languages/frameworks answer; default text; placeholders; list-repr; vocabulary hook) (WP03)
T019 `prefer_interview` keyword; re-export `UNKNOWN_LANGUAGE`/`is_unknown_language`; docstring rewrite (WP03)
T020 Synthesizer placeholder filter in `interview_mapping.py` (no "Unknown Style Guide") (WP03)

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- Import cycle (`doctrine_service_builder` → `language_scope` → vocabulary provider → service): lazy imports inside the provider; never call `infer_repo_languages` from it.
- #3292 trap: default interview must stay None — mandatory positive control.
- Keep `test_language_scope.py:49` and `test_active_languages_idempotency.py:185/:196` unchanged (FR-013 guards).

---

## Work Package WP04: Compile wiring — `--from-interview` re-derives; tool diagnostics (Priority: P1)

**Goal**: `charter generate --from-interview` (the default) re-derives `catalog.languages` and resolves references under the re-derived languages (no split-brain); activate/pack/`--no-from-interview` preserve the recorded value; `available_tools` diagnostics name unregistered tool ids, not languages (#4614, FR-011).
**Independent Test**: CLI regenerate trio from a stale `[python]` seed (Zig → `[unknown]`, Rust → `[rust]`, default → absent), `--no-from-interview` preserves, no `python-*` reference ids after the Zig regenerate, new tool message.
**Prompt**: `tasks/WP04-compile-rederive-languages.md`
**Requirement Refs**: FR-011, FR-012, FR-013, NFR-004
**Estimated prompt size**: ~400 lines

### Included Subtasks

T021 Campsite (own commit): mypy no-any-return at `charter_yaml_io.py:468` (WP04)
T022 Red-first CLI tests: stale-seed regenerate trio, `--no-from-interview`, reference parity, activate/pack preserve (WP04)
T023 `compile_charter(rederive_languages=...)` → `infer_repo_languages(..., prefer_interview=...)` (WP04)
T024 Builder kwargs on `build_activation_aware_doctrine_service` + `_build_doctrine_service_with_org_layer`; `generate` passes them (WP04)
T025 `available_tools` per-label diagnostic message (WP04)

### Dependencies

- Depends on WP03.

### Risks & Mitigations

- `--no-from-interview` passes the shipped `default_interview`, not None — must keep compiled precedence.

---

## Work Package WP05: Neutral mission context + charter-extension advisory (Priority: P1)

**Goal**: For an unknown-language project, compact and bootstrap context render language-neutral guidance, `Languages: unknown` (compact), and exactly one advisory line; no `python-*` artifact ids (#5284 rendering, FR-010).
**Independent Test**: CLI `charter context` on a Zig fixture (both renders) + Python sibling positive control; token-budget tests still green.
**Prompt**: `tasks/WP05-neutral-context-advisory.md`
**Requirement Refs**: FR-009, FR-010, C-002, NFR-002
**Estimated prompt size**: ~360 lines

### Included Subtasks

T026 Campsite (own commit): narrow the two broad `except Exception: pass` blocks in `compact.py` with characterization tests (WP05)
T027 Red-first CLI context tests (Zig bootstrap + compact; Python sibling control; defaults control) (WP05)
T028 Compact render: `Languages: unknown` via `is_unknown_language` + advisory once (WP05)
T029 Bootstrap render: advisory once, outside what `_enforce_token_budget` can drop (WP05)
T030 Token-budget / marker test ripple limited to the unknown fixture (WP05)

### Dependencies

- Depends on WP03 (parallel with WP04; no shared files).

### Risks & Mitigations

- Budget truncation could drop the advisory → append after budget enforcement or reserve space.

---

## Work Package WP06: Consumer docs, ADR, reserved-token reference (Priority: P2)

**Goal**: A consumer how-to for unsupported languages (extend the local charter; what `unknown` means and what stops applying; regenerate behaviour), an ADR for catalog.languages states, and reserved-token notes (FR-016).
**Independent Test**: Docs index/freshness scripts pass; terminology guard passes; advisory constant names the page title that exists.
**Prompt**: `tasks/WP06-docs-adr-unsupported-language.md`
**Requirement Refs**: FR-016, C-005
**Estimated prompt size**: ~260 lines

### Included Subtasks

T031 How-to `docs/guides/how-to/governance/extend-charter-for-unsupported-language.md` (+ index/toc) (WP06)
T032 Cross-link from `troubleshoot-charter.md` (regenerate replaces hand edits; unknown; review not-applicable) (WP06)
T033 ADR `docs/adr/3.x/2026-09-29-1-catalog-languages-states-and-reserved-unknown.md` (+ ADR index) (WP06)
T034 `docs/architecture/doctrine-kinds.md` reserved tokens (`any`, `all`, `unknown`) (WP06)

### Dependencies

- Depends on WP01, WP04, WP05, WP07.

### Risks & Mitigations

- Docs must mirror shipped behaviour — write after WP01/WP04/WP05 land; verify strings against code.

---

## Work Package WP07: De-scope language-independent built-in tactics; close the bias-gate scope loophole (Priority: P1)

**Goal**: Operator directive (2026-09-29): tactics are language-independent. Remove `applies_to_languages` from `secure-regex-catastrophic-backtracking`, `chain-of-responsibility-rule-pipeline` and `dependency-hygiene`, neutralize their wording (examples labelled, no in-house repo paths / Sonar python ids), close the bias-test loophole that exempted any scoped artifact, drop the stale neutrality-allowlist entry, regenerate the pack manifest (FR-018).
**Independent Test**: The three tactics resolve for `["zig"]`/`["unknown"]`; bias test rejects a scope-only exemption; `regenerate-graph --check` green.
**Prompt**: `tasks/WP07-descope-language-independent-tactics.md`
**Requirement Refs**: FR-018, C-001, C-005
**Estimated prompt size**: ~180 lines

### Included Subtasks

T035 Red-first tests: tactics unscoped + resolve for unlisted languages; bias-test loophole closed (WP07)
T036 secure-regex rewrite (unscoped, engine list fixed, examples labelled, no in-house paths) (WP07)
T037 chain-of-responsibility rewrite (unscoped, Python illustration labelled) (WP07)
T038 dependency-hygiene rewrite (unscoped, Java/Maven example labelled) (WP07)
T039 Bias-gate loophole, neutrality allowlist entry, provenance baseline (shrink-only) (WP07)
T040 `spec-kitty doctrine regenerate-graph` + `--check` (WP07)

### Dependencies

- None (independent lane).

### Risks & Mitigations

- Rebase overlap with open PR #5324 (dependency-hygiene, graph files) — accepted by the operator; resolved at closeout.
- Closing the loophole may surface other artifacts that relied on it — classify; never re-open the loophole.
