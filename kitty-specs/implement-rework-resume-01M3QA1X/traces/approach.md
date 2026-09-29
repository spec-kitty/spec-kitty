# Approach — implement-rework-resume

- 2026-09-29 — Red-first: re-ran #5377's 5-step real-CLI reproduction on main `5c8d24d0` in a throwaway repo. Step 5 exits 1 (`already claimed for implementation by 'codex'`, 0 events); the `--to planned` control exits 0. Script kept in the session scratchpad.
- 2026-09-29 — Fix at the shared implementation-start authority (`start_implementation_status`, `IN_PROGRESS` arm), reusing the #5196 `latest_implementer_actor` projection instead of an executor-local check.
- 2026-09-29 — Green via real CLI (lane code on `PYTHONPATH`): the implementer's step 5 exits 0 in fix mode from review-cycle-1 and adds only the resume-refresh annotation (no lane event); a third tool is refused with 0 events; the resubmit `in_progress → for_review` is unforced; the `--to planned` control is unchanged.
