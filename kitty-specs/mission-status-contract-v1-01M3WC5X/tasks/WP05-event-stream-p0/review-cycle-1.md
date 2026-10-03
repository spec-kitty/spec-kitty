---
affected_files: []
cycle_number: 1
mission_slug: mission-status-contract-v1-01M3WC5X
reproduction_command:
reviewed_at: '2026-10-02T14:26:40Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback 1 (reviewer-renata)

Everything verified green and grounded (see report). Three provisional-marking gaps must be fixed before p0, because p0 is what a UI team generates a client against. One remedy each.

1. (sev 3) `cursor_without_mission` is contract-owned (no tail-reader counterpart, no HTTP mapping) but is not x-provisional and not in the CHANGELOG Provisional section. StreamRefusal.code carries only x-source ResumeRefused, which implies all five values come from the tail reader. Remedy: add x-provisional + open_decision to that enum value's property (or the code property) naming cursor_without_mission as contract-owned, and list it in CHANGELOG Provisional.
2. (sev 3) Framing (event:/id:/data: lines), 30s heartbeat, and the "streamCursor wins over Last-Event-ID" rule: the precedence is x-provisional on LastEventId only; framing and heartbeat are only prose "Provisional." in paths/events.yaml, with no x-provisional/open_decision in the operation, and EventsStreamCursor has none. Remedy: add x-provisional with open_decision on the get operation (framing, heartbeat interval, 400/409 mapping) and on EventsStreamCursor (precedence), matching the CHANGELOG lines.
3. (sev 3) The code's validate_resume_cursor accepts an offset without an invariant (structural checks only; the CLI's --from-invariant is optional) while the contract's StreamCursorString requires both. This divergence is documented nowhere. Remedy: state it in StreamCursorString (or the streamCursor parameter) as a deliberate stricter contract rule, x-provisional with open_decision, and list it in the CHANGELOG Provisional section.

Non-blocking (sev 2): test_the_stream_cursor_string_never_reaches_the_page_cursor checks only StreamCursorString and StatusTransitionEvent closures; add LogTruncatedEvent, MissionLifecycleEvent, StreamRefusal and the three events parameter files. Sev 1: the 400/409 status maps are only in the StreamRefusal description; fine.
