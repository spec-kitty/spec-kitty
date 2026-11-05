# Discovery — #7198 late-window accounting

Mission: `fix-7198-late-window-accounting-01M6P3DS`
Issue: [#7198](https://github.com/spec-kitty/spec-kitty/issues/7198) — `consolidate`: a late
coordination commit touching only `status.events.jsonl` or `meta.json` is approved at exit 0 without
being landed.

## Grounding on current main

Checked before any planning artifact was written (main at `b4d1e918e2`):

- `git log --all --grep=7198` returns no fix commit; no branch or open PR claims the issue
  (`gh issue view 7198` — unassigned, `state: OPEN`, labels `reliability`, `priority:P2`,
  `domain:consolidation`, `type:bug`).
- The defect is present in the merged code:
  `src/specify_cli/consolidation/bookkeeping_projection.py#assert_late_window_landed` skips a changed
  path when `_classify_status_bookkeeping_filename(...) is MissionArtifactKind.STATUS_STATE`
  (`status.events.jsonl`, `status.json`) and when `is_coordination_kind_file(relpath)` is false
  (`meta.json` and every other primary/unclassified artifact). Everything the assertion skips is
  approved by the tip advance PR #7124 (#6871) added in
  `phase_teardown._land_late_coordination_commits`.
- PR #7124 is the mechanism to extend, and it is merged (`bcd2afa038`), so the extension is a
  delta on shipped behaviour rather than a redesign. Its late-window test suite
  (`tests/coordination/test_projection_teardown.py`, `tests/consolidation/test_late_teardown_projection.py`,
  `tests/terminus/test_coord_teardown_cas_branch_delete.py`) is the regression surface.
- Not superseded: no ADR or changelog entry claims this behaviour as intended. The only related
  open issues are #7121 (no-anchor first run), #7199 (resume anchor advance) and #7209
  (`--skip-lanes` evidence window) — all named as out of scope.

## Decision 1 — Extend `assert_late_window_landed`; no second mechanism

Evidence: `_land_late_coordination_commits` already calls the assertion on **both** run kinds, after
the projection, before the approved-tip advance and before the projection teardown gate
(`src/specify_cli/consolidation/phase_teardown.py:531`). A parallel "window completeness" check
elsewhere would have to repeat the window base, the failure wrapping and the remedy envelope, and
would risk being called in a different order relative to the tip advance.

Decision: the assertion's per-path verdict widens; nothing else in the ordering changes. This also
makes "both run kinds" fall out of the code instead of being asserted twice.

## Decision 2 — `status.events.jsonl` is proved by event containment, not exempted

Evidence: the union stage (`_project_status_bookkeeping_to_target`) reads
`run.feature_dir / status.events.jsonl` — the coordination **worktree's working tree** — and unions
it into the target. A branch commit made anywhere else is not in that working tree, so the union
cannot carry it. Byte equality with the target's blob is therefore the wrong proof (the union's
output is a superset, keyed by `event_id` in `specify_cli.status.event_log_merge.merge_event_payloads`).

Decision: every `event_id` present in the coordination branch's committed log must be present in the
target branch's committed log. That is exactly "the union carried it", degrades to byte equality for
an unmoved log, and is bounded by the two blobs the assertion already reads.

## Decision 3 — `status.json` stays excluded, as a stated derived-snapshot rule

Evidence: `status.json` is rematerialized by `_rematerialize_status_snapshot` from the unioned events
after every projection; its own bytes are never an authority (`FR-005` of #4981/#4970/#4973). A
`status.json`-only change on the coordination branch therefore carries no record the log does not
already carry.

Decision: keep excluding it, but as an explicit named rule in the same disposition table, with a test
that a `status.json`-only window still tears down. This keeps the escalation shape ("only `status.json`
changed") from becoming a refusal, while the event log itself is now proved.

## Decision 4 — A primary document is "landed" when the target's copy contains it

Evidence: `meta.json` is re-authored on the target during the merge (mission-number bake,
`baseline_merge_commit` stamp, coordination-marker flatten — `phase_bookkeeping.py:196`,
`phase_teardown` marker handling), and `_post_checkpoint_mission_paths` excludes it from projection
on purpose (#5460: the driver replay runs base-aware while the real squash runs the meta driver
two-way, so a projected `meta.json` would not match). So the coordination copy can legitimately be
stale-but-contained: the target's document is the coordination document plus the merge's own keys.

Decision: for a non-coordination document, "landed" means recursive JSON object containment of the
coordination copy in the target's committed copy — every key present, nested objects recursed,
everything else equal. A changed or removed field is *not* contained and refuses. Non-JSON
non-coordination paths cannot be proved carried and therefore refuse.

Rejected alternative: exempting primary artifacts whenever the target's copy differs from the
checkpoint copy ("the merge authored it"). That is unfalsifiable — it exempts exactly the lost late
edit the issue reports.

## Decision 5 — Two new refusal kinds, one remedy each

Evidence: #6791 established the invariant `len(set(remedies.values())) == len(LateProjectionRefusalKind)`
(`tests/consolidation/test_late_teardown_projection.py::test_no_two_refusal_kinds_share_a_remedy`).
The repairs differ in kind: a missing status event is cleared by making the coordination worktree's
log match the branch (the union's source) or by landing the event on the target; a non-coordination
document is cleared by landing it on the target (or reverting it on the branch) — the projection
cannot carry it either way.

Decision: add `STATUS_EVENTS_NOT_LANDED` and `NON_COORDINATION_RECORD_NOT_LANDED`, both inside the
existing `COORD_LATE_PROJECTION_REFUSED` envelope and the existing exit-1 teardown error. No new CLI
flag, exit code or error code.

## Shared-code note for the batch

`src/specify_cli/consolidation/phase_teardown.py` is shared with **#7199** (same function,
`_land_late_coordination_commits`: it removes `not run.is_resume` from the anchor advance). This
Mission does not touch the anchor-advance condition; expected conflict surface is the docstring block
above it and the assertion call site. **#7209** (`entry_preflight.py`, `wp_evidence.py`) does not
overlap this Mission's files. This is called out in the PR body for the lander.

## Open questions

- None blocking. Two judgement calls are recorded as decisions 3 and 4 above and are re-stated in the
  PR's `## Change` so a reviewer can disagree with either without re-deriving the rest.
