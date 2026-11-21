---
affected_files: []
cycle_number: 1
mission_slug: api-claim-accept-readiness-01M7X6Q6
reproduction_command:
reviewed_at: '2026-11-20T21:04:34Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback, cycle 1 (claude::reviewer-renata)

Verdict: **changes requested**. The production code is sound and small; what blocks approval is
that a known gap is hidden by a weakened assertion, and one required test is absent.

## What holds

- `claim_policy_metadata(shell_pid | None, agent, *, extra=)` is the one claim-sidecar builder;
  claim keys win over `extra` (unit-tested, spoofed `agent`/`shell_pid` dropped). It is wired into
  API `start-implementation`, API `transition --to claimed` and `agent status emit --to claimed`.
- `status/claim_release.py` defines the planned release once; `move-task` and API
  `transition --to planned` both use it. The module imports only `status.models`, so the status
  pipeline stays git-free.
- `done_bookkeeping._lane_approved_reviewer` names the latest approver, `unknown` otherwise.
- Re-pins are honest: `test_merge_done_recording` now tells implementer (`claude-implementer`) and
  approver (`gemini-cli`) apart, which is stronger than before. `test_agent_status_emit_aggregate_wiring`
  updates the legacy emulation to the intended sidecar. Both are deliberate behaviour changes, not
  green-washing.
- ruff and `ruff format --check --force-exclude` are clean. C901 is clean. mypy shows the same 7
  pre-existing errors on the base and on HEAD, with none new.
- No orchestrator-api envelope or `CONTRACT_VERSION` change is needed, because only the stored
  event's `policy_metadata` changed.

## Blocking

**B1. The re-claim assertion was weakened in the implementation commit, and it hides a gap that
WP01 widens.** The red commit asserted `state["agent"] == "codex"` after an API rollback and
re-claim. `d63f9d82` replaced that with `state.get("agent") != "claude"`, which passes whether the
slot is empty or correct. The cause is real: `spec_kitty_events.diary.reduce_parsed` folds every
annotation after every transition, so a `release_runtime_claim` annotation also clears the
`agent`/`shell_pid` slots of any later claim. The new consequence is mine to flag. I probed it:
host claim (claude), then API `transition --to planned`, then host-shaped claim (codex, pid). The
snapshot shows `agent=None, shell_pid=None` and `implementer_of_record=codex`. Before WP01 an API
rollback emitted no release, so that host re-claim kept `agent`/`shell_pid`. Now
`core/stale_detection.py` and the `move-task` ownership guard see no live holder after any API
rollback. That is the same defect `move-task --to planned` already has, so parity holds, but
FR-004's stated outcome ("the snapshot shows an owner and the ownership guard applies") is not met
after a rollback.

Fix: file the events-package issue (C-001). Then replace the loose assertion with a **strict
`xfail`** that pins the intended result: `agent == "codex"` after an API re-claim, and
`agent`/`shell_pid` present after a host re-claim. Reference the issue in the xfail reason. Record
the residual in the mission (research.md / issue-matrix) so WP02 and the mission review see it.
Keep `implementer_of_record == "codex"` and the event-sidecar assertion as passing pins.

**B2. The host re-claim test the WP prompt requires is missing.** "A second actor then claims ...
through host `agent action implement`, with no `--force`" has no test. Add one, which also covers
the B1 consequence above.

## Non-blocking

- **L1.** `start_review` now also writes the claim sidecar. That is outside the stated scope (the
  WP names three entry points) and untested. It is inert in the reducer, which folds `agent` only
  on `planned -> claimed`. Either add a test pinning why it is there, or drop it. Say which in the
  move-task note.
- **L2.** The WP asks for the `--policy` `"agent": "spoof"` case to be driven through the Typer app.
  Today only the unit test covers it. A one-line Typer case would close it.
- **Nit.** WP item 3 says to re-export `claim_release` through `status/__init__.py`. It is imported
  from `status.claim_release` directly. Either re-export it or amend the WP text.
- **Nit.** `test_emit_event_fields_match_prior_direct_path` no longer compares against the *prior*
  path. A docstring line saying so would help.

## Anti-pattern checklist

1. Dead code: PASS. Both new helpers have production callers.
2. Synthetic fixture: PASS. The Typer tests drive real apps on a git fixture.
3. Silent empty return: PASS. The `unknown` fallback is documented.
4. FR coverage: **FAIL** for FR-004 post-rollback (B1/B2). FR-006: PASS.
5. Frozen surface: PASS.
6. Locked decision: PASS.
7. Shared-file ownership: N/A. WP02 shares the lane; no overlapping owned files seen.
8. Production fragility: PASS. No new `raise`.

## CI reach

`tests/orchestrator_api`, `tests/status` and `tests/consolidation` are in the per-PR module matrix.
The out-of-matrix `tests/specify_cli/cli/commands` (status/emit/claim) runs nightly only.
