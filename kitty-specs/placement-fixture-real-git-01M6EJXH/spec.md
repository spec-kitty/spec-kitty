# Mission Specification: Placement fixture must be a real git repo (#7055)

**Mission Branch**: `issue-7055-placement-fixture-real-git`
**Created**: 2026-11-02
**Status**: Draft
**Input**: GitHub issue #7055 — `tests/specify_cli/migration/test_runtime_state_cutover_placement.py::test_mismatched_feature_dir_fails_closed_without_writing`
fails on `origin/main` with `DID NOT RAISE PlacementMismatchError` and a
`TRACKED_META_UNAVAILABLE` warning.

## Summary & Framing

The file's mismatch tests build their "enclosing repo" with a **bare `.git` directory
marker** (`_init_bare_git_marker`), on the stated assumption that the only consumer is
`resolve_canonical_root`, which merely stats the marker. That assumption stopped holding
when the #6673 tracked-`meta.json` seam landed in `cutover_mission`
(`d8829074b7`): the cutover now asks git what it holds for the mission's `meta.json`
before it seeds or flips, and a `.git` anchor that git *runs and refuses* is deliberately
classified as "the tracked copy is unknown" — never as "nothing is tracked" — so the
cutover skips with `TRACKED_META_UNAVAILABLE` instead of fabricating an identity.

Consequence: in `test_mismatched_feature_dir_fails_closed_without_writing` the divergent
leg has no `meta.json`, the marker is not a repository, and the run exits through the
tracked-meta skip **before** the placement check. The test never reaches the branch it
pins, so it fails on every host regardless of git version (the issue allowed for a
host-specific cause; the reproduction shows it is deterministic).

**Evidence that this is a fixture defect, not a product defect:**

1. `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py::test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked`
   already pins the deliberate refusal for an unusable anchor (a garbled `.git` pointer).
   The bare marker is exactly that shape: git exits 128 with "not a git repository".
2. Both outcomes are fail-safe (nothing is written), so the product is not skipping a
   write it should refuse; it is refusing loudly, with a coded notice, one seam earlier.
3. In a real `git init` repo (the shape every live Mission has) the same test reaches the
   placement check and raises `PlacementMismatchError` (verified by direct probe before
   planning: bare marker → `CutoverResult(skipped_notice=...TRACKED_META_UNAVAILABLE)`;
   real repo → `PlacementMismatchError`).

So the fix is in the fixture: make the enclosing repo a real git repository, and pin the
seam interaction explicitly so the two fail-safe paths can never be confused again.

## User Scenarios & Testing

### User Story 1 — The mismatch test reaches the placement check again (Priority: P1)

A maintainer runs the migration test module on a clean checkout and sees it green, with the
mismatch case genuinely exercising `PlacementMismatchError` rather than a fixture artifact.

**Why this priority**: this is the reported red; until the fixture is real, the file's
central fail-close contract is unverified on every host.

**Independent Test**: `uv run --frozen pytest -q -p no:randomly -n0
tests/specify_cli/migration/test_runtime_state_cutover_placement.py` → all tests pass, and
the mismatch case is proven to be reaching the raise (an intentionally broken fixture makes
it fail again — see red-first below).

**Acceptance Scenarios**:

1. **Given** the fixture builds its enclosing repo with `git init`, **When** the divergent
   leg has no `meta.json` and the tracked-meta seam classifies it, **Then** the classifier
   reports nothing to refuse (a real repo that tracks nothing for the path) and the cutover
   proceeds to the placement check.
2. **Given** the same fixture, **When** `cutover_mission(divergent_dir, status_feature_dir=...)`
   runs, **Then** it raises `PlacementMismatchError` and writes no `meta.json` at either the
   divergent or the canonical location.
3. **Given** the whole module, **When** it runs, **Then** the other eight tests still pass
   unchanged (the fixture change must not rescue them into a different code path).

### User Story 2 — The refusal seam stays deliberate (Priority: P2)

A maintainer reading either seam's tests can tell which fail-safe path a given fixture is
exercising, instead of discovering it from a warning line.

**Why this priority**: the ambiguity in the issue ("fixture bug or product skip?") cost a
triage round; a seam-level pin prevents the same question recurring.

**Independent Test**: the new regression test fails if `cutover_mission` starts raising
`PlacementMismatchError` (or writing) on a mission whose enclosing `.git` is unusable, and
fails if the skip notice loses its `TRACKED_META_UNAVAILABLE` code.

**Acceptance Scenarios**:

1. **Given** a mission dir under a bare `.git` marker (git runs and refuses), **When**
   `cutover_mission` runs, **Then** it returns a `CutoverResult` with `skipped_notice`
   carrying `TRACKED_META_UNAVAILABLE`, `flipped=False`, and no `meta.json` on disk.
2. **Given** the same shape, **When** the caller inspects the result, **Then** no exception
   escapes — the refusal is a skip with an operator notice, not a crash.

### Edge Cases

- A real repo with an **unborn HEAD** (no commit) and no tracked `meta.json`: must classify as
  "nothing tracked" and reach the placement check — so the fixture does not need a commit,
  but must not depend on one either.
- The `GIT_CEILING_DIRECTORIES` hermetic fixture stays: the repo root is under `tmp_path`, and
  a stray real repo above `tmp_path` must never satisfy the probe.
- The tests that only need a repo root for `resolve_canonical_root` (symlinked-root, action
  context degrade) must keep working against a real repo, not just the marker.

## Requirements

### Functional Requirements

- **FR-001**: The module's repo fixture helper creates a real git repository (`git init`)
  instead of a bare `.git` directory marker, and its name/docstring say so.
- **FR-002**: `test_mismatched_feature_dir_fails_closed_without_writing` keeps its existing
  strength: `pytest.raises(PlacementMismatchError)` through the pre-existing public entry
  point `cutover_mission(feature_dir, status_feature_dir=...)`, plus the "nothing written"
  assertions. No `xfail`, no `skip`, no relaxed assertion.
- **FR-003**: A regression test pins the seam interaction: with an unusable `.git` anchor
  (bare marker), `cutover_mission` returns `flipped=False` with a `TRACKED_META_UNAVAILABLE`
  `skipped_notice`, raises nothing, and writes no `meta.json`. This is the deliberate
  counterpart to FR-001 and explains why the mismatch fixture cannot use the marker.
- **FR-004**: Every other test in the module keeps passing without weakening its assertions
  after the fixture change.
- **FR-005**: No change to `src/` behaviour is required or made; if implementation proves a
  product defect instead, stop and report rather than widening the diff (see
  `## Out of Scope`).

### Non-Functional Requirements

- **NFR-001**: The module's runtime must not grow materially (a `git init` per repo-building
  test is acceptable; no network, no commits required on the hot path).
- **NFR-002**: The change must hold with `GIT_CEILING_DIRECTORIES` set to the test's
  `tmp_path` and with the repo at an unborn `HEAD`.
- **NFR-003**: The new regression test must be a `fast`-marked unit test (module `pytestmark`).

### Constraints

- **C-001**: `tests/specify_cli/migration` is out-of-matrix in
  `.github/ci-module-registry.yml` (nightly only), so the PR's evidence is a targeted local
  run of the module plus the neighbouring `test_read_tracked_meta_6673.py` suite it leans on,
  not a matrix job.
- **C-002**: Do not edit `packs/built-in/**` (generated) or agent copies.
- **C-003**: Keep the file's `pytestmark = [pytest.mark.fast]` and `-p no:randomly -n0`
  compatibility.

## Out of Scope

- Changing `cutover_mission`'s seam ordering or the tracked-meta classifier. The refusal for
  an unusable git anchor is intentional and already pinned by #6673's own tests.
- The `TRACKED_META_UNAVAILABLE` notice's *wording* for the unusable-anchor case (it reads as
  if the path were tracked). Worth a separate issue; message-only, and it would change a
  string other tests pin. Recorded in `## Deferred` if a reviewer agrees it stands.
- Any other test file that builds a bare `.git` marker (none found in this module's blast
  radius; a `grep` for the helper shows it is local to this file).

## Success Criteria

- **SC-001**: `test_runtime_state_cutover_placement.py` is 10/10 green locally (9 existing +
  1 new), including the previously failing mismatch test.
- **SC-002**: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` stays green (the
  product contract the fixture leans on is unchanged).
- **SC-003**: A reviewer can map each test's fixture to the seam it exercises from the helper
  name and docstring alone.
