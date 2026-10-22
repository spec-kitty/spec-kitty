---
affected_files: []
cycle_number: 1
mission_slug: event-write-hygiene-01M5HS55
reproduction_command:
reviewed_at: '2026-10-22T16:08:11Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (cycle 1): reviewer-renata

All the substantive checks pass:
- Red first: at 78730d04 the gate fails with only `lifecycle_events.py:368 -> spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL`, and it is green at HEAD.
- The gate is sound against bypass probes:
  - Reported: private module, private name, `_internal`, `_q as Q`, a nested or function-local import, and `import ..._m as m`.
  - Not reported: public-as-private alias, docstring or comment, `__version__`, `__init__`, a relative import, and the `spec_kitty_eventsx` prefix.
- The gate reuses `_PRODUCTION_ROOTS`, has a non-empty corpus floor and has no allowlist.
- The deletions are complete. `_repo_root_for_lifecycle_log` survives and `fanout_lifecycle_event_hosted` is not renamed.
- Every removed test covered only deleted code. The two retargeted tests keep their intent.
- Tests: 1739 passed, 6 skipped. ruff, `ruff format --check --force-exclude` and mypy are clean.

One required change:

**Issue 1: the stale docstring named in T011 step 2 was not fixed.** The WP prompt explicitly asks to fix `lifecycle_events.py:827`. At HEAD that text is lines 700-702, in the `emit_artifact_phase` docstring. It still says "``artifact_path`` is local lifecycle metadata for Started events; the SaaS fan-out path strips it before strict canonical validation." The code that stripped `artifact_path` (`_canonical_lifecycle_payload_for_saas`) and the strict validation (`_validate_lifecycle_payload`) were deleted in 0a53cdd1, so the sentence now describes behaviour that no longer exists. WP04's occurrence map only renames identifiers, so it will not fix this. To fix it, keep the first clause (`artifact_path` is local lifecycle metadata on Started events) and drop the fan-out stripping and strict-validation claim, or state that no canonical-model validation happens on this path.

Same class (optional; fix it in the same edit if you agree): lines 954-955 say `MissionReopened` "is intentionally kept off the SaaS strict-validation model map". That map was `_EVENT_TYPE_TO_MODEL`, which core no longer reads. Events 6.1.0 also added these types to the map (see `tests/specify_cli/status/test_post_mission_lifecycle_events.py:371-378`). Rephrase it to say that the event is local-only through `_POST_MISSION_EVENT_TYPES`.

This is a docstring-only fix in an owned file, so no new tests are needed. Re-run ruff check, `ruff format --check --force-exclude` and mypy on `lifecycle_events.py`.
