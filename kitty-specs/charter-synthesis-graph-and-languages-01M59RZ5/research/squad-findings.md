# Research: squad findings (2026-10-19)

Read-only squads before specify and after the first spec draft. Full reports were relayed in the session; this file keeps the load-bearing facts.

## Graph (#6442, #6443)
- No synthesized styleguide gets `source_urns`; only tactics (`_append_selected_directives`). The `styleguide --applies-->` branch of `project_drg._derived_edge` fires only on replayed provenance.
- Styleguides are never action-bundle roots; compiled references root them only for an unconfigured project (catalog fallback) or an explicit list.
- PROJECT_001 comes from `project_intent` (scope "All project work packages"); #3052 emits `directive --requires--> mission_type:X` only when the answer names a shipped mission type; no traversal follows it.

## Languages (#6444)
- Two authorities: `code_reader._detect_language` (observed, single, knows go/rust/ruby) and `language_scope.infer_repo_languages` (declared only, list, knows swift); a third doctrine-derived vocabulary (`language_vocabulary.py`, #5284) answers "has guidance" and stays separate.
- `gradle`/`maven`/`junit` declare `java` today, so "Kotlin, Gradle" gets Java doctrine.
- Matching lives in `charter.offering.shared.scoping` (offering), which cannot import activation.

## Post-spec adversarial findings folded
FR-008 path list (generated harness input, provenance, manifest hashes, label not URN, stem tokens), the ADR-guarded request hash, the layering split for FR-009, family expansion at match time, build tokens → jvm, Kotlin hash change, FR-002 red-first case is compiled references and the new implement/review delivery, pre-existing styleguides not appended, NFR-001 golden byte-identical plus a synthesized golden, FR-015 in the runner, FR-011 declared languages, FR-016 derived ceiling.

## Local-only reds (clean env, main f16633930)
- test_doctrine_asset, packaging: green (earlier reds were stale venv/install).
- 6 upgrade tests: real red since ef23380b7 (NotInsideRepositoryError from rc35 apply; runner does not catch it); nightly #6437/#6432.
- Orphan ceiling 25 > 21: real red; four plan/* step contracts vendored by #6379.
- 4 nag tests: container SPEC_KITTY_NO_NAG leak.
- test_6155_*: #6416, out of scope.
