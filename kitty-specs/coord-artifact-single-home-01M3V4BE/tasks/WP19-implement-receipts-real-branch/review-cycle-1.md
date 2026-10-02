---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T11:50:51Z'
reviewer_agent: claude
wp_id: WP19
---

# WP19 review: changes requested (reviewer-renata, cycle 1)

Reviewed: lane-f `65b280ad1f` (red) and `03629fcfc1` (fix), against base `4f2ddb7939`.

What is already right and should stay:
- The red commit fails at base for the right reason (`sha=None`).
- The US6.2 positive control would fail an implementation that always names the coordination branch: it requires a target-branch receipt whose sha is on the target branch, plus a separate coordination receipt.
- The allowlisted `CommitTarget(ref=target_branch)` line is unchanged (workflow.py L893).
- No new `placement_seam`, `write_dir` or `CommitTarget(` call was added.
- `target_branch` already arrives as `placement.ref` (workflow_executor.py), so not re-deriving it is correct.
- ruff, mypy --strict and C901 are clean. Targeted tests: 105 passed.

## BLOCKING

### B1. `_already_present_receipt_sha` can name a commit that does not contain the change, and the new warning never fires for it

FR-013 requires a receipt to name a commit that actually holds the change. Passing `git branch --contains` is not enough on its own.

Two scenarios show the helper does not meet that today. Both were reproduced against `03629fcfc1`:

1. **Ignored or never-committed path.**
   - Setup: `kitty-specs/` is gitignored, and `status.events.jsonl` exists on disk.
   - `git status --porcelain` is clean, so the code takes the "already present" arm.
   - `git log -1 tb -- <path>` finds nothing, so the helper falls back to the tip.
   - Result: the receipt is `tb 37f66c6`, and `git cat-file -e 37f66c6:kitty-specs/m/status.events.jsonl` fails. The named commit does not contain the path.
2. **Repository-root HEAD is not the target branch.**
   - Setup: `tb` holds `s.jsonl` = `old`. HEAD is on `other`, which committed `new`.
   - The porcelain check is clean relative to HEAD.
   - `git log -1 tb -- s.jsonl` returns the old `tb` commit.
   - Result: the receipt names `tb` with a sha whose content is `old`, while the worktree holds `new`.

The executor's own debug branch says the caller's checked-out branch can differ from `placement.ref`, so scenario 2 can happen in practice.

The tip fallback only runs when no commit on the target branch touches the paths. That is exactly the case where the tip does not contain them. So the docstring claim "the tip trivially contains the already-present state by construction" is false whenever the fallback is reached.

Before this fix, both cases recorded `sha=None`: an honest absence. Now they record a plausible but wrong id, and the new `_record_receipt` warning is bypassed, so the anomaly is hidden. For a receipt-honesty requirement, that is worse than before.

`test_already_present_receipt_falls_back_to_branch_tip_when_no_history_match` asserts the wrong behaviour as correct: the path was never committed, yet the test expects the tip sha.

Required:
- **Anchor on what the porcelain check proved.** The candidate is `git log -1 --format=%H HEAD -- <paths>` in `porcelain_root`. Accept it only if both checks pass:
  - the paths are tracked at that commit (`git cat-file -e <sha>:<rel>` or `git ls-files --error-unmatch`);
  - the commit is on the named branch (`git merge-base --is-ancestor <sha> <target_branch>`).
  
  A content check (`git diff --quiet <sha> -- <paths>`) also works, provided you add the tracked-path check.
- **Remove the tip fallback.** If no verified commit exists, return `None` so the `_record_receipt` warning fires. Never name an unverified commit.
  - WP T104 step 2 ("never record sha=None", "fall back to tip") rests on a false premise. A truthful `None` with a warning beats a fabricated id.
  - Record this deviation in the activity log and as a `design-decisions` tracer entry.
- **Replace the tip-fallback test** with these tests:
  - (a) ignored or never-committed path → `sha is None`, plus exactly one warning;
  - (b) HEAD-not-on-target-branch → the receipt is not the stale target-branch commit (`None`, or a sha verified as contained and holding the content);
  - (c) keep the happy path, which already asserts the exact commit.

## NON-BLOCKING (fix in the same cycle; they are cheap)

### N1. I9 record overstates where the defect reproduces

My probe instrumented the real `agent action implement` at base, using the same `_build_mission_repo` fixture.
- **Coordination Mission:** both receipts already carry contained shas, so the non-reproduction is confirmed.
- **Lanes (coordination-less) Mission:** the legacy leaf goes through `safe_commit` and records a real sha (`f9a44d1…`). The "already present" arm is not reached. Your own `test_lanes_mission_receipts_unchanged_fields_plus_sha` passes at `65b280ad1f`.

So `sha=None` reproduces only by calling `_commit_via_legacy_safe_commit` directly with already-clean paths. It does not reproduce through implement, on either topology.

The `design-decisions` tracer entry ("The sha=None defect is real but lives on the coord-LESS (lanes/single_branch) leaf") is true about the code, but it reads as if the lanes CLI run reproduces the defect. Amend it with a new tracer entry stating these points:
- R18 is a direct-call reproduction of a latent arm. That arm is reached only when the paths are already clean, for example from the other `_commit_workflow_change` callers at workflow_executor.py L1062/L1791. It is not reached by implement's claim in this fixture.
- The grounding repro's `chore: Start WP01 implementation [ok]` line against the target branch is the correct PRIMARY-group receipt, printed without an id. The misleading part of #5440's evidence was the missing commit id in the human output, which T105 fixes. Tie this explicitly to the spec Assumption.

### N2. Fixture source is misattributed, and P-m6 is not followed

The tests import `_build_mission_repo` from `tests/characterization/test_trio_json_envelope.py`. That is the existing trio characterization helper, not WP02's factory, and it lives in a module that carries a known red (#5410). The tracer calls it "WP02's _build_mission_repo harness".

The binding P-m6 note says to use `tests._factories.coord_mission` (`make_coord_mission(..., materialized=True)`), never a hand-rolled fixture. Do one of the following:
- switch to the factory, or
- if the factory cannot produce an implement-ready Mission (charter bundle, analysis report, lanes manifest, WP file), record that gap as a `tooling-friction` tracer entry and correct the attribution.

Importing an underscore helper across test modules is fragile coupling. Note it in either case.

### N3. Docstring reference is wrong

The `_record_receipt` docstring points to `:func:_already_present_receipt`. The function is named `_already_present_receipt_sha`.

### N4. The C-008 control does not check `message`

The control says every pre-existing field is unchanged but does not assert `message`. Add `assert receipt["message"] == "chore: Start WP01 implementation [claude]"`.

### N5. WP Activity Log not updated

The WP file's Activity Log has only the initial entry. The status note covers the content, but append the red-result and decision entries as the WP asks.

## Not findings
- `ruff format --check` without `--force-exclude` flags both files, but they are equally unformatted at base and covered by the format-exclude ratchet. That is pre-existing.
- `TestImplementRecoverJson::test_coord_mission_no_crashed_sessions` is the known #5410 red.
