---
affected_files: []
cycle_number: 1
mission_slug: path-conventions-per-type-01M7VRQM
reproduction_command:
reviewed_at: '2026-11-20T11:51:38Z'
reviewer_agent: claude::generic-reviewer
wp_id: WP05
---

**Issue 1 (blocking, docs accuracy): the accept-and-merge guide misdescribes the failure text's remedy order.**

`docs/guides/how-to/missions/accept-and-merge.md`, "When the Project Layout Differs", says: "The strict failure text names them in this order", and then lists: per-type remap, remap for every type, waivers, last resort, followed by "Prefer all of these over `accept --lenient`".

The text WP02 renders (`PathValidationResult.format_errors`, lane-b c0126d62) is different:

1. it names only the **per-type** remap snippet. The plain every-type remap is never named in the failure text;
2. its order is: per-type remap, both waivers, `accept --lenient`, **then** the "Last resort:" copy line, then `mkdir -p` for real deliverables. The guide places the last resort before `--lenient`.

An operator following the failure text will look in the guide for an order that does not match. Fix the framing sentence; the bullets can stay as a reference list. For example:

> The strict failure text leads with the per-type remap for the failing Mission type, then names both waivers and `accept --lenient`, then the last-resort copy; `mkdir -p` is offered only for real deliverables. The levers in full:

Alternatively, reorder the bullets to match and mark the plain remap as "not named in the failure text".

Everything else matches the implementation: flag and field names (`--waive-path-conventions`, `--waive-reason`, `path_conventions_waived`, `"path_conventions": "waived"`, `path_conventions_rationale`); the precedence; the fail-closed rules; the roster rule; the orchestrator-api behaviour; and the YAML single-key note. The ADR amendment's "Remedy order" section is correct and can serve as the reference wording. The changelog fragment is accurate.
