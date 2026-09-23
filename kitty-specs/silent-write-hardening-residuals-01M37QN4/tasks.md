# Tasks — Silent-Write Hardening Residuals

**Mission**: `silent-write-hardening-residuals-01M37QN4` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Four work packages. WP01–WP03 are the three independent findings (disjoint write-scopes → parallel lanes); WP04 is the docs/tracker close-out (depends on all three so the changelog reflects landed behavior). All tests are ATDD red-first. No new dependencies.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: unregistered authoritative `event_type` row is quarantined by `--fix` | WP01 | |
| T002 | Invert `_is_preserved_non_lane_row` to preserve-by-default (EMPTY named denylist); keep `_is_legacy_typed_lane_transition` passthrough FIRST | WP01 | |
| T003 | Extend `_registry_authoritative_quarantine_violations` guard to the reader==repair invariant (no `event_type`-bearing row quarantined); preserve duplicate-`event_id` carve-out | WP01 | |
| T004 | Regression: preserved classes + duplicate-`event_id` dedupe + #3066 lane passthrough | WP01 | |
| T005 | ADR under `docs/adr/3.x/` recording inverted quarantine semantics + blast radius | WP01 | |
| T006 | Add `read_catalog_field`/`read_catalog_mission` accessor to `charter/activation/charter_yaml_io.py` | WP02 | [P] |
| T007 | Delegate `generate.py::_read_catalog_mission_from_charter_yaml` to the accessor | WP02 | [P] |
| T008 | Delegate `references_refresh.py::_read_catalog_mission_and_template_set` to the accessor | WP02 | [P] |
| T009 | Campsite: route `language_scope._read_compiled_languages` through the accessor | WP02 | [P] |
| T010 | Tests: accessor parity (normal/absent/malformed) + grep-proof single reader | WP02 | [P] |
| T011 | Red-first: `~~~`-fenced heading-like line mis-split + duplicate-heading key collision | WP03 | [P] |
| T012 | Widen `_TRACE_FENCE_MARKER` to match `~~~` fences | WP03 | [P] |
| T013 | Non-colliding base-comparison block key (section-id / occurrence-ordinal); leave `union_trace_texts` untouched | WP03 | [P] |
| T014 | Regression: diverged single-heading section still stale-drops; whole-block dedupe unchanged | WP03 | [P] |
| T015 | CHANGELOG entry (canonical `docs/changelog/CHANGELOG.md`, Fixed) | WP04 | |
| T016 | #4993 close-out notes + reader-count correction (3→2) for PR body / issue-matrix | WP04 | |
| T017 | Terminology guard + docs-freshness after prose touch | WP04 | |

---

## WP01 — Finding A: preserve-by-default mission-state repair + guard + ADR

**Priority**: P1 · **Prompt**: [tasks/WP01-repair-preserve-by-default.md](./tasks/WP01-repair-preserve-by-default.md) · **Est.**: ~430 lines
**Goal**: Invert `doctor mission-state --fix` from a registry allowlist to preserve-by-default (EMPTY denylist), so an unregistered future authoritative `event_type` is never silently quarantined; strengthen the fail-closed guard to the reader==repair invariant; record the behavioral change in an ADR.
**Independent test**: an authoritative-shaped row whose `event_type` is not in the registry survives `--fix` (red-first vs pre-inversion; SC-001).
**Included subtasks**: T001, T002, T003, T004, T005
**Dependencies**: none
**Risks**: regressing #3066 (keep lane passthrough FIRST); regressing #4938 duplicate-`event_id` carve-out. Both pinned by T004.

## WP02 — Finding B: single `catalog.mission` accessor

**Priority**: P2 · **Prompt**: [tasks/WP02-catalog-mission-accessor.md](./tasks/WP02-catalog-mission-accessor.md) · **Est.**: ~320 lines
**Goal**: One shared accessor in `charter/activation/charter_yaml_io.py`; both former readers delegate; grep proves a single reader (NFR-003 / SC-002).
**Independent test**: both callers resolve the identical value through the accessor; grep shows one reader.
**Included subtasks**: T006, T007, T008, T009, T010
**Dependencies**: none
**Risks**: import-layer edge (verified safe — both callers already reach `charter.activation` lazily).

## WP03 — Finding C: traces merge-driver hardening

**Priority**: P3 · **Prompt**: [tasks/WP03-traces-driver-hardening.md](./tasks/WP03-traces-driver-hardening.md) · **Est.**: ~300 lines
**Goal**: Recognize `~~~` fences; give blocks a non-colliding base-comparison key so duplicate headings don't collide. No `union_trace_texts` change, no contract refactor (C-002).
**Independent test**: a `~~~`-fenced heading-like line isn't a boundary; duplicate-heading sections key distinctly (red-first; SC-003).
**Included subtasks**: T011, T012, T013, T014
**Dependencies**: none
**Risks**: breaking 3-way base-awareness (do NOT use a body-sensitive key); pinned by T014.

## WP04 — Docs & tracker close-out

**Priority**: P2 · **Prompt**: [tasks/WP04-changelog-and-closeout.md](./tasks/WP04-changelog-and-closeout.md) · **Est.**: ~200 lines
**Goal**: Consumer-focused CHANGELOG entry; #4993 close-out with the 3→2 reader-count correction; run the terminology + docs-freshness gates.
**Independent test**: `check_docs_freshness --ci` errors=0; terminology guard green.
**Included subtasks**: T015, T016, T017
**Dependencies**: WP01, WP02, WP03 (changelog reflects landed behavior)
**Risks**: markdownlint over the whole CHANGELOG file (budget for the file, not just new lines).

---

**MVP**: WP01 (the active silent-loss window). WP02/WP03 are latent hardening; WP04 is close-out.
