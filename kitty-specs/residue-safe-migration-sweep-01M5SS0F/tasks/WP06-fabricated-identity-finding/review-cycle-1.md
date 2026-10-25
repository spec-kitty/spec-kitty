---
affected_files: []
cycle_number: 1
mission_slug: residue-safe-migration-sweep-01M5SS0F
reproduction_command:
reviewed_at: '2026-10-25T17:21:45Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback (reviewer-renata, cycle 1)

The design is sound and most of the work is approved in substance: signal 3 uses `mid8_from_slug`, signal 1 uses the precomputed `tracked` set with an exact allow-list, the blank/number equivalences are right, the finding is WARNING with `artifact_path="meta.json"` and outside `TEAMSPACE_BLOCKER_CODES`, the builder output is unchanged, the classifier is wired from `_scan_missions` and the CLI test proves it, and the import closure grows by exactly one module (the classifier) against origin/main. Two items block approval.

**Issue 1 (blocking, regression this WP introduced): the load_meta census gate is red.**
`tests/architectural/test_lifted_root_meta_fail_closed_census.py` fails on this branch and passes on the parent of 81b9206c (12 passed there):

    NEW unaccounted `load_meta` call site(s) detected (FR-007 / NFR-003 / D10):
        src/specify_cli/audit/classifiers/fabricated_identity.py::fabricated_identity_finding  x1

The cause is the new `load_meta(folder, on_malformed="none")` in `src/specify_cli/audit/classifiers/fabricated_identity.py` (`fabricated_identity_finding`). Fix: the silent arm is correct here, because a malformed `meta.json` is already reported by `classify_meta_json` in the same scan and this classifier must decline rather than double-report. Add a `silent-by-contract` row for `("src/specify_cli/audit/classifiers/fabricated_identity.py", "fabricated_identity_finding"): (1, "silent-by-contract")` to `ACCOUNTED_SITES` in `tests/architectural/_load_meta_census.py`, with that rationale in a comment. That file is outside `owned_files`, so record it as an out-of-map edit in the history note. Re-run `tests/architectural/test_lifted_root_meta_fail_closed_census.py`.

**Issue 2 (blocking, FR-010 negative not isolated): the "meta.json is git-tracked" clause of signal 1 is untested.**
`test_untracked_meta_json_is_a_negative` (`tests/audit/test_fabricated_identity_finding.py`) also writes and commits a `spec.md`. `spec.md` is not on the allow-list, so the folder fails signal 1 whether or not `meta.json` is tracked. I checked with a mutant that deletes

    if prefix + _META not in tracked:
        return False

from `_signal_tracked_allowlist`. The test as written still passes. In an isolated scenario (only `status.json` committed, `meta.json` on disk with a `mission_id` but untracked, so `is_mission_dir` still treats it as a Mission) the original returns no match and the mutant returns a match. Fix: make the negative commit only an allow-listed file (for example `status.json`) and leave `meta.json` untracked, with no `spec.md`. It then fails only on the tracked-meta clause. Drive it through the CLI (`_audit`) like the other negatives.

**Non-blocking (take or leave):**
- 3. No fixture exercises the `*.lock` arm of the allow-list. A positive with a stray `foo.lock` would pin it. A negative with a `tasks/WP01.md`, the #6669 residue shape, would document the intended non-match.
- 4. The corpus test is marked `slow`, so it is deselected from the per-PR fast tier. pytest.ini defines `slow` as more than 30 s, and it measured 6.2 s here. The WP prompt allowed the marker, so this is not a defect, but NFR-002 then runs only in the nightly. Consider dropping the marker.

**Pre-existing reds, not this WP's** (the same counts on the parent commit): `tests/architectural/test_dead_port_snapshot_recovery.py` (37 errors, `git archive` of commits absent from this clone), `tests/contract/test_mission_status_reality.py` (9; this mission's own status snapshot), `tests/upgrade/test_mission_corpus_recovery.py` (9). The `PinningInventoryDriftWarning` in `tests/release/test_pinning_inventory_fresh.py` is byte-identical on the parent commit, so it predates this WP.
