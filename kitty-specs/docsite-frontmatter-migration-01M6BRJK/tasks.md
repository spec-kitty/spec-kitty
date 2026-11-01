# Tasks: Docsite build-blocking frontmatter migration

**Mission**: `docsite-frontmatter-migration-01M6BRJK` · **Topology**: `single_branch` (WPs run sequentially in the repository root checkout) · **Branch**: `issue-6929-docsite-frontmatter-migration`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Body-hash immutability test (red first) | WP01 | |
| T002 | `_dockitty_contract.py`: slug, published, excluded folders, personas, immutable set | WP01 | |
| T003 | Body-preserving frontmatter block editor | WP01 | |
| T004 | Audience rule (`[{profile, guidance_text}]`) | WP01 | |
| T005 | ADR rule (`doc_status`, `kind: ADR`) | WP01 | |
| T006 | Related rule (slugs; `external_references`; drop missing) | WP01 | |
| T007 | CLI `--check`/`--apply`/`--verify-against`, idempotency | WP01 | |
| T008 | Port `audience_resolver.py` to profile lists | WP02 | [P] |
| T009 | Port `touched_set_gates.py` audience presence and placement | WP02 | [P] |
| T010 | Rewrite audience fixtures in their tests | WP02 | |
| T011 | Corpus-shape invariant test (red on base tree) | WP03 | |
| T012 | Port `related_validator.py` to slugs + unpublished targets | WP03 | |
| T013 | Rewrite related fixtures (`test_related_validator.py`, `test_rulers_blocking.py`, `test_canonical_promotion.py`) | WP03 | |
| T014 | Apply the migration to `docs/` | WP03 | |
| T015 | Verify frontmatter-only diff and reader verdicts on the real tree | WP03 | |
| T016 | One-off doc-kitty build of `docs/` and evidence | WP04 | |
| T017 | Control build on the base tree | WP04 | |
| T018 | Record commands, page count and gaps | WP04 | |

## WP01 — Migration engine and immutable-body guard

**Goal**: one committed, idempotent, frontmatter-only migration covering audience, ADR and related, plus the body-hash test. **Priority**: P1. **Independent test**: `pytest tests/docs/test_immutable_bodies.py tests/docs/test_dockitty_contract.py tests/docs/test_dockitty_frontmatter_migration.py`.
Prompt: [tasks/WP01-migration-engine.md](tasks/WP01-migration-engine.md)

T001 Body-hash immutability test (red first) (WP01)
T002 Contract module (WP01)
T003 Frontmatter block editor (WP01)
T004 Audience rule (WP01)
T005 ADR rule (WP01)
T006 Related rule (WP01)
T007 CLI and idempotency (WP01)

Dependencies: none. Risks: YAML re-emit drift (line-level editing + key-by-key re-parse check).

## WP02 — Audience readers on profile lists

**Goal**: `audience_resolver.py` and `touched_set_gates.py` read `[{profile, guidance_text}]`. **Priority**: P1. **Independent test**: `pytest tests/docs/test_audience_resolves.py tests/docs/test_touched_set_gates.py`.
Prompt: [tasks/WP02-audience-readers.md](tasks/WP02-audience-readers.md)

T008 Port audience_resolver (WP02)
T009 Port touched_set_gates (WP02)
T010 Rewrite audience fixtures (WP02)

Dependencies: WP01 (contract module). No test reads `audience` over the real tree, so this WP is green before the cutover.

## WP03 — Cutover: related reader, corpus shape, apply

**Goal**: the related reader moves to slugs and the corpus is migrated in the same WP, so every commit stays green (`test_canonical_promotion.py` reads `related` over the real tree). **Priority**: P1. **Independent test**: `pytest tests/docs/test_dockitty_frontmatter_shape.py tests/docs/test_related_validator.py tests/docs/test_rulers_blocking.py tests/glossary/test_canonical_promotion.py`.
Prompt: [tasks/WP03-cutover.md](tasks/WP03-cutover.md)

T011 Corpus-shape invariant test (WP03)
T012 Port related_validator (WP03)
T013 Rewrite related fixtures (WP03)
T014 Apply migration to docs/ (WP03)
T015 Verify diff and reader verdicts (WP03)

Dependencies: WP01, WP02. Risks: collision with #6902/#6882 (re-run the script on rebase).

## WP04 — doc-kitty build evidence

**Goal**: the spike's one-off build passes on this branch; commands and page count recorded. **Priority**: P1.
Prompt: [tasks/WP04-build-evidence.md](tasks/WP04-build-evidence.md)

T016 One-off build (WP04)
T017 Control build (WP04)
T018 Record evidence (WP04)

Dependencies: WP03.

## MVP

WP01 (the engine) is the foundation; the mission's value lands at WP03 and is proven at WP04.
