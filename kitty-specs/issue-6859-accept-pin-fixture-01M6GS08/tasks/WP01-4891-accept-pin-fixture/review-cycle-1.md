# Review cycle 1 — REJECT (2 findings, both fixed)

Reviewer: independent review delegate (profile `reviewer-renata`, gerrit-style), on lane head
`7f1adb1209`. Verdict: **REJECT**. No assertion, marker or production gate was found weakened;
the rejection was about fixture symmetry/documentation and malformed event ids.

## F1 (medium) — the controls differed by implementation evidence, not only by `lanes.json`

**Finding.** Only the positive control created the lane branch and its implementation commit, so
the two fixtures differed by evidence as well as by the manifest and matrix. The builder's
"accept-ready" claim and the positive control's "same fixture" docstring therefore overclaimed.

**Fix.** `_build_accept_ready_mission` now creates the lane branch and implementation commit for
BOTH controls, using the canonical `commit_lane_implementation`. Because that helper reads
`lanes.json` (as a real Mission's lanes are cut from the planning commit the manifest records),
the builder writes the manifest after committing the base fixture, cuts the lane, then removes
the manifest. The negative control therefore tests *this same Mission with its manifest absent*.
Measured effect: the negative control now reports `lanes_manifest` as its **sole** blocked check
(previously it was one of the blocked checks), which makes the pin stricter, not looser.

## F2 (medium) — seeded event ids were outside the ULID alphabet

**Finding.** Three hard-coded ids contained `I`/`L`-class characters and the claim id was 27
characters; the status store drops such lines. Not observed to drop today, but malformed.

**Fix.** All three ids are now 26-character hex (`014891ACCE000000000000000N`), inside the ULID
alphabet and of the canonical length.

## Re-verification after the fixes

- `uv run pytest tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -q` →
  **2 passed** (109 s).
- Negative control blocked checks (instrumented run): `['lanes_manifest']`.
- Half-by-half non-vacuity re-confirmed on the final structure: dropping the lane implementation
  commit → `IMPLEMENTATION_UNREADABLE`; dropping `owned_files` → `IMPLEMENTATION_MISSING`;
  approving as the implementer → `REVIEW_NOT_INDEPENDENT`.
- `ruff check` and `ruff format --check` clean; no `assert`/marker line changed
  (`git diff -U0 | grep assert` is empty).
