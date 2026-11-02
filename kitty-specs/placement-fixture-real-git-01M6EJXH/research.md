# Discovery findings — #7055 placement fixture

## D1 — The red is deterministic, not host-specific (decision)

**Decision:** treat #7055 as a deterministic fixture defect; do not chase a git-version
difference.

**Evidence:**
- Reproduced on current `origin/main` (`9aed3a8012`, worktree clean) with the issue's own
  command: `uv run --frozen pytest -q -p no:randomly -n0
  tests/specify_cli/migration/test_runtime_state_cutover_placement.py` → `1 failed,
  8 passed`, failing applet
  `test_mismatched_feature_dir_fails_closed_without_writing`.
- The warning is `TRACKED_META_UNAVAILABLE`, emitted by
  `specify_cli/upgrade/tracked_meta_notice.py` through
  `cutover_mission` → `_tracked_meta_notice(feature_dir)`.
- `cutover_mission` consults that seam **before** the seed phase
  (`src/specify_cli/migration/runtime_state_cutover.py`, the
  `notice = _tracked_meta_notice(feature_dir)` block), and returns
  `CutoverResult(flipped=False, skipped_notice=...)` on a refusal. The placement check lives in
  `_flip_phase`, reached only after seed + verify, so a refusal short-circuits it.

## D2 — The fixture, not the product, is wrong (decision)

**Decision:** fix the fixture to build a real git repository; leave the seam ordering and the
tracked-meta classifier untouched.

**Evidence:**
- The helper `_init_bare_git_marker` creates only `(repo_root / ".git").mkdir()`. Its
  docstring justifies that with `resolve_canonical_root`, which only stats the marker — true,
  but the cutover path since `d8829074b7` (2026-11-01, "keep the shipped 3.2.6rc1 cutover
  migration byte-identical; skip the tracked-absent Mission in cutover_mission") also shells
  out to git via `classify_missing_tracked_meta`.
- With a bare marker, git *runs and refuses* (`fatal: not a git repository`). `read_tracked_meta`
  → `_meta_checkout_prefix` → `_has_no_git_anchor` sees the `.git` anchor and raises
  `_GitRefuses`, so the answer is `TrackedMeta(None, unavailable=True)` — "the tracked copy is
  unknown" — by design.
- That design is already pinned:
  `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py::test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked`
  ("a refusing git was read as 'nothing tracked' (the fabricating branch)" fails the test).
  Refusing is the fail-safe: it never writes a fabricated `meta.json` over an unknown identity.
- Direct probe, both branches, same fixture contents except the marker
  (`/tmp/probe7055.py` in the run log):
  - bare marker → `CutoverResult(flipped=False, skipped_notice='... [TRACKED_META_UNAVAILABLE]')`, no raise, nothing written;
  - `git init` repo → `PlacementMismatchError` raised, matching the test's assertion.
  A real repository with an unborn HEAD classifies as "nothing tracked" (`TrackedMeta(None,
  unavailable=False)`), so the fixture needs no commit.
- Neither outcome writes, so no real-world safety property is lost by the skip; the test is
  simply pinning the wrong seam for its fixture shape.

## D3 — Blast radius of the helper (decision)

**Decision:** rename the helper to `_init_git_repo` (real `git init`) and keep every call site;
add one seam-level regression test.

**Evidence:**
- `grep -rn "_init_bare_git_marker" tests/` → defined and used only in
  `tests/specify_cli/migration/test_runtime_state_cutover_placement.py` (5 call sites: mismatch,
  direct `_flip_phase` mismatch, genuine-primary flip, symlinked root, two action-context tests).
- Call sites that already have a `meta.json` on disk (`test_genuine_primary_dir_still_flips`,
  `test_placement_home_and_canonicalize_agree_through_symlinked_root`) short-circuit the
  classifier (`meta.json` exists → `None`), so the change is inert for them.
- The direct `_flip_phase` call sites never consult the classifier; a real repo keeps them
  meaningful (and they keep passing).
- A regression test for the marker shape (`flipped=False`, `TRACKED_META_UNAVAILABLE` notice,
  nothing written, no raise) makes the FR-001/FR-003 distinction explicit and prevents a future
  "fix" from moving the fixture back onto the fabricating branch.

## D4 — CI matrix status (decision)

**Decision:** evidence is a targeted local run, cited in the PR; do not expect a matrix job.

**Evidence:** `tests/specify_cli/migration` is out-of-matrix in
`.github/ci-module-registry.yml` (nightly only). The PR will still run the full workflow set
under the fleet's `pr:pause-ci` throttle.

## Open questions

- Q1: the unusable-anchor notice reads "tracked meta.json is missing ... git could not produce
  its content", which implies a tracked path where git actually refused to answer at all. The
  wording is a pre-existing #6673 message concern, out of this mission's scope; propose it as a
  separate issue if a reviewer agrees it is worth changing.
- Q2: whether `_init_git_repo` should also `git commit` to mimic a live checkout. Not needed
  (D2: unborn HEAD is a supported shape), and a commit would add runtime for no coverage.
