# Integrated review — issue-6693-red-main-refs-to-directive-01M66YZX

Reviewer: `reviewer-renata` (identity `claude:claude-opus-4.5:reviewer-renata`), over the
aggregate diff `main...issue-6693-red-main-refs-to-directive` (15 files outside
`kitty-specs/` and `kitty-ops/`, +187/−32).

## What the diff is

| Surface | Change |
|---|---|
| `packs/built-in.source.yaml`, `packs/internal.source.yaml` | pin `af1c370f`/`ecda7b00` → `72cb7dbc` (the open-packs#74 merge commit), with the recorded tree digests |
| `src/charter/offering/drg/migration/extractor.py` | curated `DIRECTIVE_030` edge target moves from the procedure kind to `directive:RED_MAIN_RELEASE_DISCIPLINE`; comment explains the kind move |
| five test files + `minimal_org_pack_2/drg/fragment.yaml` | assertions and the fixture edge name the directive the packs ship |
| `tests/charter_offering/test_red_main_ledger_resolution.py` | **new** fast guard: every activated id resolves, no denied id names an unprovided artifact, the red-main rule is an activated directive and not an activated procedure, plus a positive control |
| `.kittify/charter/activation.yaml` | same stem moved from `activated_procedures` to `activated_directives`; no deny residue |
| `.kittify/charter/charter.yaml`, `synthesis-manifest.yaml`, `.kittify/charter-packs/graph.yaml` | CLI regeneration output (catalog entry moved `PROCEDURE:` → `DIRECTIVE:` with the `_LIBRARY/directive-*` path; a pre-existing `PROJECT_001` label drift corrected) |
| `.kittify/charter/charter.md` | the two standing-order pointers plus one dated `Updated:` line |
| `docs/changelog/CHANGELOG.md` | one `[Unreleased] → Changed` entry (1,053 chars) |

## Verdict: APPROVE

## Evidence re-run in this review

- `charter pack vendor --check --pack built-in|internal` → both trees match `72cb7dbc`.
- `pytest tests/charter_offering/drg/migration/test_extractor_projection.py::TestDRGZeroDelta` → 5 passed.
- `pytest` over the five repointed files plus `tests/charter/test_activation_preserves_effective_4253.py` → 126 passed.
- `pytest tests/charter_offering/test_red_main_ledger_resolution.py` → 5 passed; `doctor charter-packs` → no activation-ledger finding; `charter consistency-check` → coherent; `charter context --action implement` → no catalog miss.
- `check_changelog_style` → 0 errors; `check_spelling` → 0 findings; `check_docs_freshness --ci` → errors=0 (warnings pre-existing).
- `git grep 'procedure:red-main-release-discipline'` outside `kitty-specs/`/`.kittify/evidence/` → no hits.

## Anti-pattern checklist

1. **Dead code** — N/A: no new production module; the new file is a test module with live callers (pytest).
2. **Synthetic-fixture test** — PASS: the guard calls `load_activation_ledger`, `IdentityIndex.build` and `ledger_findings`, i.e. the readers the CLI uses; deleting the ledger fix turns two of its tests red (verified by restoring the pre-repoint ledger from `39b1829058`).
3. **Silent empty return** — N/A: no new `except`/`return` path in production code.
4. **FR coverage** — PASS: FR-002 → `TestDRGZeroDelta`; FR-003 → the five repointed tests; FR-004/FR-005 → the guard and the doctor findings; FR-006 → the changelog plus `check_changelog_style`; FR-001 → the pin, verified by `charter pack vendor --check` and by CI's pin-drift gate (`tests/charter_offering/test_pack_pin.py` / `test_built_in_pin.py`).
5. **Frozen surface** — PASS: zero changes under `services/` (the ADR D-9 frozen set) and no other frozen path touched.
6. **Locked decision** — PASS: no doctrine content was authored or reworded; the rule's substance is untouched.
7. **Shared-file ownership** — PASS with a note: `src/.../extractor.py` is WP01's file and WP03 made one comment-only change to it, in its own commit with the rationale in the message (keeps the retired URN out of NFR-002's grep sweep).
8. **Production fragility** — N/A: no new `raise`.

## Criterion non-vacuity

1. **Same-fixture positive control** — PASS: `test_known_good_ids_resolve_through_the_same_index` probes the same index with `DIRECTIVE_034` (stem and declared id) and a procedure, so a blind probe cannot make the absence assertions pass.
2. **Half-by-half proof** — PASS: reverting the curated edge turns the zero-delta tests red; restoring the pre-repoint ledger turns the two ledger tests red. The pin half is proved directionally rather than by re-fetching the old commit: with the old pin the repointed curated edge and the repointed ledger would both dangle, which is the red state captured before either fix.
3. **Production-path non-vacuity** — PASS: the guard's assertions run through the production readers, and the ledger change was made by the CLI (`charter deactivate` / `activate`), not by hand.

## Findings raised and disposed

- **No blocking findings.** The readiness gate (`.kittify` analyze step) recorded three
  non-blocking findings: A1 (FR-005's non-vacuity note reads as two states of one test),
  A2 (WP01 prompt compresses the 345/346 node-count comparison), A3 (the spec's rename
  paragraph does not cross-reference why the map classifies only the built-in term).
  Disposition: **carried as documentation debt into the PR's `## Deferred` section**
  rather than fixed here, because editing `spec.md`/WP prompts after the readiness gate
  would invalidate the analysis report that the implementation gate consumed. The
  behaviour they describe is correct in the code and the tests; only the prose is loose.

---

## Post-merge audit (spec → code fidelity)

Ran after `consolidate` recorded `done` for all three WPs (mission number 244).

**Coverage, re-derived from the merged tree rather than from the WP claims**

| Spec | Delivered | Where |
|---|---|---|
| FR-001 pins both packs to the #74 commit | yes | `packs/*.source.yaml`; `charter pack vendor --check` matches both trees |
| FR-002 curated edge repointed | yes | `extractor.py`; `TestDRGZeroDelta` 5 passed, red when reverted |
| FR-003 five tests + fixture repointed | yes | 126 passed over the five files |
| FR-004 this repository's charter repointed | yes | `activation.yaml`, compiled catalog, `charter.md`; doctor/consistency clean |
| FR-005 ledger-resolution guard | yes | new fast module; red on the pre-repoint ledger |
| FR-006 changelog entry | yes | `[Unreleased] → Changed`, style + spelling gates 0 errors |
| NFR-001 no fetched pack edited | yes | only the two `*.source.yaml` files changed under `packs/` |
| NFR-002 no live stale reference | yes | `git grep` for the retired URN returns nothing outside preserved history |
| NFR-003 regeneration deterministic | yes | byte-identity gate green |
| C-001 upstream-first | yes | no doctrine authored here |
| C-002 history preserved | yes | the four preserved surfaces are untouched |
| C-003 single pin commit | yes | both packs at `72cb7dbc` |

**Drift.** One pre-existing project-layer drift surfaced as a regeneration side effect
(`directive:PROJECT_001`'s recorded label was "Project Intent Directive" while the
artifact's `title` has been "Mission Type Scope Directive"). The regeneration corrected
it; no behaviour depends on the label. Recorded here rather than reverted, because
hand-reverting generated output would create the drift the regeneration removed.

**Risk.** The only forward risk is consumer-side: a project whose activation ledger
lists the retired procedure keeps a `Charter catalog miss` warning until it runs the two
`charter` commands named in the changelog. Core cannot rewrite a consumer's ledger. This
is called out in the `[Unreleased]` entry and in the PR's `## Change`.

**Security.** No dependency, secret, network or permission surface changed. The new test
reads local files only and asserts on ids.

**Verdict: releasable.** No blocking finding; the three readiness-gate findings (A1–A3)
remain prose-only documentation debt, named in the PR's `## Deferred`.

### Deviation recorded after consolidation

- 2026-10-30 · review round 2 · The CI `charter` module shards were **cancelled** (not failed) behind the
  pre-existing `next`-shard red (#6798), so I ran the module locally as the shard's
  equivalent: `pytest -q -p no:randomly -m "not performance and not stress" tests/charter tests/charter_offering`
  → `3 failed, 9161 passed`. All three failures are the same one-line consequence the
  issue did not enumerate: one required *procedure* becoming one required *directive*
  moves `test_reconciler_promotion`'s required-directive histogram (28 → 29) and both
  in-force goldens. Fixed in `7b0bb69944` (histogram entry with its rationale, plus the
  documented `UPDATE_SNAPSHOT=1` regeneration whose diff is additive only). Re-ran the
  module: `9164 passed, 11 skipped, 0 failed`. The three tests pass on pristine
  `origin/main`, so they were green before this pin moved.
