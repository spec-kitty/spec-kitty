# Tasks: Durable derived consumer census for CI fan-out (#6173)

**Mission**: `derived-consumer-census-01M4V5P5` · **Topology**: single_branch
(WPs run sequentially in the write checkout) · **Target**: `issue-6173-derived-consumer-census`

Each WP follows ATDD (C-011): a failing-first test is committed before the
implementation commit of that WP. Validation per CLAUDE.md test policy +
`NO_FULL_HEAVY_SUITES_IN_MISSION` — the SPECIFIC named architectural gate files,
never the bare `tests/architectural/` sweep.

## WP01 — Consumer census: model, static + runtime capture, committed artifact

Covers IC-1/IC-2/IC-3. Delivers `scripts/ci/consumer_census.py` and the committed
`.github/ci-consumer-census.json`.

- **T001** `tests/ci/test_consumer_census.py`: ATDD red-first — assert
  `build_census()` records the three consumers (next←prompt.md runtime,
  agent←lifecycle.py static-import, dossier←expected-artifacts.yaml static-read)
  and that `build_census() == json.load(committed artifact)` (determinism).
- **T002** `consumer_census.py`: registry-driven module universe
  (`_registry_module_names`), `test_dirs`/mirror attribution, `load_census()`,
  `build_census()`, `--write`/`--check` CLI. (FR-001, FR-004, NFR-002, NFR-003)
- **T003** static detection: AST import + `read_text`/`open`/`Path` literal scan
  over each module's `test_dirs`, resolved to repo-relative src/packs paths.
  (FR-002)
- **T004** runtime capture: bounded, offline audit-hook harness exercising the
  resolver (`resolve_command`/`resolve_template`/manifest load) per mission
  type/step, recording src/packs opens attributed to the triggering module; the
  `tests/next` prompt case is the canonical positive control. (FR-003, NFR-004)
- **T005** write + commit `.github/ci-consumer-census.json`.

## WP02 — Red-first routing gate (depends: WP01)

Covers IC-4. Delivers `tests/architectural/test_consumer_census_routing.py`.

- **T006** red-first: the gate's checker reds on a **planted** unrouted consumer
  (positive control, FR-006); and the three historical pins red against a router
  with their routing globs stripped (FR-007 red-first provenance).
- **T007** the gate: for each census `(module, path)`, assert
  `select_modules([path]) ⊇ {module}`; red naming module + unrouted path. Reads
  the committed artifact (static, battery-fast). (FR-005, NFR-001)
- **T008** enrol the gate in the architectural fast roster if it fits the budget
  (CI-config wiring verdict), else leave it in the heavy battery.

## WP03 — Derive GROUP_MODULE_FANOUT from the census (depends: WP01, WP02)

Covers IC-5.

- **T009** red-first: a unit test asserting the derived `GROUP_MODULE_FANOUT`
  equals the sets `test_group_module_fanout_is_wired` pins (cross-check).
- **T010** replace the hardcoded dict with a census-derived loader in
  `gate_selection.py` (match consumed paths against non-src group globs; exclude
  base-selected). Keep the transcription lockstep + authority gates green; add no
  scrub/registry row (C-003); leave router globs untouched (C-004). (FR-008,
  NFR-001)

## WP04 — Cost delta + charter within-module selection (depends: WP01)

Covers IC-6.

- **T011** `scripts/ci/consumer_census_cost.py` + `tests/ci/test_consumer_census_cost.py`:
  selected-shard count per recent merged PR diff and the delta vs. pre-census
  routing; record in `analysis/cost-delta.md`. (FR-009)
- **T012** charter within-module file selection
  (`tests/charter_offering/missions/*` + `test_*prompt*`) to cut the 7-shard cost
  on a `mission_pack_content` edit — land if tractable within this PR, else carve
  to a named follow-up issue and record the decision. (FR-010)

## Requirement mapping

| WP | requirement_refs |
|----|------------------|
| WP01 | FR-001, FR-002, FR-003, FR-004, NFR-002, NFR-003, NFR-004 |
| WP02 | FR-005, FR-006, FR-007, NFR-001, SC-001, SC-002 |
| WP03 | FR-008, NFR-001, SC-003 |
| WP04 | FR-009, FR-010, SC-004 |
