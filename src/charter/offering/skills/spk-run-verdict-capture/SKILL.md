---
name: spk-run-verdict-capture
description: "Set a Spec Kitty work-package review verdict through the deterministic event-log seam, so every agent harness records approve/reject the same way."
---

# spk-run-verdict-capture

Use this skill whenever an agent (any of the 13 slash-command harnesses or the shared
Agent-Skill harnesses) needs to **record the outcome of a WP review** — approve, reject, or
otherwise. It documents the single deterministic seam so verdicts never diverge by harness.

## The authoritative seam

The **sole** authority for a WP's review verdict is the `review_result` event in the mission's
`status.events.jsonl` (read back via `specify_cli.status.event_sourced_review_result`). The
`review-cycle-N.md` render is **non-authoritative prose** — do not hand-edit it to change a
verdict, and never treat it as the source of truth. Because the verdict is an event, it is
append-only, deterministic, and identical across every agent.

## How to set a verdict (use the CLI — do not write the event by hand)

- **Approve** a WP under review:
  ```bash
  spec-kitty agent tasks move-task <WP> --to approved --mission <slug> --note "<why>"
  ```
- **Reject** a WP (send it back with structured feedback):
  ```bash
  spec-kitty agent tasks move-task <WP> --to planned \
    --review-feedback-file <path/to/review-feedback-N.md> --mission <slug>
  ```
- **Terminal (done) with an explicit review triple** (reviewer / verdict / reference):
  ```bash
  spec-kitty agent status emit <WP> --to done --actor <name> \
    --evidence-json '{"review": {"reviewer": "<name>", "verdict": "approved", "reference": "<PR/commit>"}}'
  ```

Each command emits the `review_result` (or review-bearing transition) event; the reduced snapshot
is what `spec-kitty agent tasks status` and merge preflight read.

## Verdict vocabulary

The verdict field is validated against the canonical bridge `specify_cli.status.event_verdicts()`.
Do not invent verdict strings; an unknown verdict is rejected at the seam. Moving a WP to `done` requires a review triple with `reviewer`, `verdict`, and `reference`.

## Guardrails

- One seam, every harness: Codex, Claude, Gemini, Copilot, and the rest all record verdicts through
  these CLI verbs — never by editing `.md` renders or the event log directly.
- A rejection must carry concrete, actionable feedback (the `--review-feedback-file`); an empty
  rejection is not a review.
- Related: `spk-run-review-wp` performs the review that produces the verdict; this skill is only the
  capture step. `spk-run-implement-review` drives the loop across WPs.
