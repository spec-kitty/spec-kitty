---
affected_files: []
cycle_number: 1
mission_slug: issue-matrix-terminality-all-rows-01M5X1ZJ
reproduction_command:
reviewed_at: '2026-10-26T22:45:41Z'
reviewer_agent: claude-reviewer
wp_id: WP01
---

# WP01 review feedback (reviewer-renata, cycle 1)

**Verdict: changes requested. One blocking issue. Everything else passes.**

## [HIGH] src/mission_runtime/resolution.py:2263-2269 (`_raise_not_authored_if_absent`): an unreadable object is reported as ISSUE_MATRIX_NOT_AUTHORED

**Issue.** The presence check reuses `lifecycle_phase._path_present_at_rev`, which runs `git cat-file -e <ref>:<path>` and returns `False` on **any** non-zero exit. `cat-file -e` checks that the *object exists*, so it cannot tell "path absent from the tree" from "path present in the tree but its blob is missing or unreadable". Both come back as "absent". FR-004 and NFR-002 name "unreadable object" as a case that must stay fail closed. The WP DoD says the same: "Timeout, OSError, unreadable object and deleted ref keep their existing codes."

**Evidence (reproduced).**
- Plain git, valid HEAD, `issue-matrix.json` committed, loose blob removed:
  `git show HEAD:issue-matrix.json` -> exit 128 "bad object"; `git cat-file -e HEAD:issue-matrix.json` -> exit 1 (so `_path_present_at_rev` returns False); `git ls-tree HEAD -- issue-matrix.json` -> exit 0 and lists the entry.
- End to end through the reader: I used `_build_consolidated_coord_mission(..., coord_matrix_content="fixed")` and deleted the loose blob of the coord ref's `issue-matrix.json`. `read_issue_matrix_ref_content` then raised `ISSUE_MATRIX_NOT_AUTHORED` with "no issue matrix was ever committed at kitty/mission-...-coord". A matrix WAS committed. Its object is unreadable, which can happen through corruption, a partial clone (`--filter=blob:none`) used offline, or a pruned object.
- Impact once WP02 lands: a Mission with zero gating references and an authored but unreadable matrix reads as "nothing to enforce", which is a PASS. Any non-terminal rows in that matrix are hidden. NFR-002 says no code path may turn an unreadable object into a PASS.

**Recommendation.** Do not use `_path_present_at_rev` for this leg; that helper is not in WP01's owned files, so don't change it. Instead, add a private tree-only probe in `resolution.py`, for example `git ls-tree --name-only <ref> -- <path>` with `timeout=_GIT_PROBE_TIMEOUT`:
- exit 0 with empty output -> positively absent;
- exit 0 with the path listed -> present (keep PROBE_ERROR);
- non-zero exit, `TimeoutExpired` or `OSError` -> the probe could not answer (keep PROBE_ERROR).
`ls-tree` reads trees only and never the blob. It also fails (exit 128) on a ref that no longer resolves, which closes the deleted-between-checks race below at no extra cost. Add a red-first test using the missing-blob fixture above: commit `issue-matrix.json` on the coord ref, unlink its loose object, and expect `ISSUE_MATRIX_PROBE_ERROR`. Do not use `git gc` in that fixture, because it packs the object.

## [LOW] Residual: a ref deleted between `_ensure_issue_matrix_ref_exists` and the presence probe reads as NOT_AUTHORED

`cat-file -e <deleted-ref>:<path>` exits 128, which reads as "absent". The window is milliseconds, needs a concurrent branch delete such as coord teardown, and in WP02 only matters for zero-gating-reference Missions. On its own I would not block on it. The `ls-tree` fix above closes it anyway, so please confirm it in the handoff note. If the rework keeps the cat-file approach, re-validate the ref with `_rev_is_valid` after the presence probe.

## Passing items (no action needed)

- DIRECTIVE_041 re-pin of the two never-authored tests from PROBE_ERROR to NOT_AUTHORED is legitimate. FR-003/FR-004 change the contract on purpose. The tests still assert a typed refusal distinct from REF_ABSENT, and the assertion moved to the more specific code; nothing was weakened.
- Timeout and OSError on the content probe or the presence probe keep PROBE_ERROR. The `_IssueMatrixProbeExited` marker gates the leg correctly, and the `(LifecyclePhaseProbeError, OSError)` catch returns, then the caller re-raises.
- The success path is unchanged; `test_successful_read_runs_no_presence_probe` pins NFR-001.
- Red-first: with the base `resolution.py`, exactly the 3 not-authored tests fail, for the right reason (they get PROBE_ERROR). The new controls would catch a naive "md failure => NOT_AUTHORED" mutation and a bare-except presence helper.
- ruff, `ruff format --check --force-exclude` and mypy are clean; C901 is clean.
- Scope stays inside the owned files. The `ERROR_CODES.md` wording is accurate.
