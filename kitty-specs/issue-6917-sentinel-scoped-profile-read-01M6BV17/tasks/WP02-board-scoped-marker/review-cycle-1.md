---
affected_files: []
cycle_number: 1
mission_slug: issue-6917-sentinel-scoped-profile-read-01M6BV17
reproduction_command:
reviewed_at: '2026-11-01T18:04:41Z'
reviewer_agent: pi:glm-5.3:reviewer-renata
wp_id: WP02
---

# WP02 Review Feedback — REJECT (one mechanical defect)

Reviewer: reviewer-renata (pi:glm-5.3). Mission: issue-6917-sentinel-scoped-profile-read-01M6BV17.
Commit under review: a74fa90a9c.

## Verdict

Reject — one real defect. Everything else in the work package is correct and was verified
(see "What passed" below). The fix is a two-line deduplication; no design or test changes are needed.

## Defect (blocking)

**D1 — Duplicated `sentinels` initialization in `_st_render_human`; mypy fails on the
implementation file.**

`src/specify_cli/cli/commands/agent/tasks_status_cmd.py`, `_st_render_human`, lines 911 and 915:

```python
    sentinels: SentinelMap | None = None          # line 911
    # Lazy read (#6917): skip the lookup entirely when no rendered WP carries an
    # ``agent_profile`` -- e.g. a freshly-tasked mission where nothing has been
    # claimed yet.
    sentinels: SentinelMap | None = None          # line 915 — dead duplicate
```

Evidence (run in the repo root checkout):

```
$ uv run mypy src/specify_cli/cli/commands/agent/tasks_status_cmd.py
src/specify_cli/cli/commands/agent/tasks_status_cmd.py:915: error: Name "sentinels" already defined on line 911  [no-redef]
Found 1 error in 1 source file (checked 1 source file)
```

Why this blocks:

- The WP's own test strategy (`WP02-board-scoped-marker.md`, "Test Strategy") includes
  `uv run mypy src/specify_cli/cli/commands/agent/tasks_status_cmd.py`; it fails.
- The charter's Code Review Checklist requires "Type annotations present (mypy --strict passes)".
- The duplicate is dead code / an edit leftover — exactly the class of leftover the review
  probes for (the WP asked for rewritten comment blocks, not an extra stale annotation).

Requested fix: delete one of the two `sentinels: SentinelMap | None = None` lines (keep the
one above the comment, or fold into the comment block — implementer's choice) and confirm
`uv run mypy src/specify_cli/cli/commands/agent/tasks_status_cmd.py` is clean. Re-run the
four-file pytest set and ruff before re-submitting.

## What passed (verified, do not re-litigate)

- **One scoped read per render**: `_st_render_human` builds `sentinels` exactly once from the
  distinct non-empty `str` ids across `by_lane`, via a single
  `build_agent_profile_sentinels(_st_config_root(st), _profile_ids)` call; no read at all when
  no row names a profile (`_profile_ids` empty). No service build, no catalogue build.
- **Marker parity**: `_get_hic_marker` returns the identical `"👤 "` text; non-`str`/falsy
  `agent_profile` yields `""`; unknown ids are markerless and error-free; structural parity
  (deny/narrowing) holds — verified by `test_tasks_status_keeps_the_structural_marker_of_a_denied_sentinel`
  (self-resolving path through the scoped accessor) and
  `test_hic_marker_survives_narrowed_activation`.
- **Fail-closed contract**: only `ImportError` degrades (both the render site and the marker
  fallback); a malformed `.kittify/config.yaml` still surfaces as a non-zero structured failure
  (`test_malformed_config_still_fails_closed`).
- **Census test is genuine**: it invokes the real `agent tasks status` command through
  `CliRunner`, probes `AgentProfileRepository._parse_profile_from_file` (below the shipped-parse
  memoisation), asserts exactly the two named documents for a two-profile board and zero parses
  for empty/unknown-id boards, and carries a positive control proving the counter sees the whole
  catalogue (>20 documents) on a plain `AgentProfileRepository()` read.
- **Red-first claim holds on parent 4ccfd63ddf** (reasoned, not checked out): the parent's
  `_st_render_human` (line 966) and `_get_hic_marker` fallback (line 1114) both call
  `build_active_charter_service(...).agent_profile_repository`, which materialises the full
  catalogue; the two-profile assertion (`names == {human-in-charge.agent.yaml, python-pedro.agent.yaml}`)
  and the unknown-id assertion (`parsed == []`) would therefore fail there. The test file does
  not exist on the parent (new file).
- **Seam preserved**: `_get_hic_marker` keeps its name and its `tasks.py` re-export (lines
  661/683); `test_tasks_status_cmd_seam.py` updated to the `sentinels=None` keyword and passing.
- **No leftover `ProfileLookup` / `_needs_profile_lookup` references** anywhere in `src/` or
  `tests/`; rewritten comments accurately describe the scoped structural read and cite #6917.
- **Test results**: 39 passed in 2.79s across the four specified files.
- **Ruff**: clean on both files.

## Suggested re-submission note

Fix D1 only. No scope creep: do not touch the test files, the charter layer, or the comments
beyond the duplicated line.
