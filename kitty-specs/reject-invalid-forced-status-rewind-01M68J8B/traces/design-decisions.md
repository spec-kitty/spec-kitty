# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/claude-sonnet-4.5 · D-1: refuse, do not auto-fill a review_ref sentinel. move-task supplies 'force-override' as its own deliberate, named sentinel; a generic door inventing a pointer the operator never gave would record a review reference that does not exist. D-3: keep the historical non-force refusal text by returning from the structural check before the new requirement is evaluated.

2026-10-31 · pi/claude-sonnet-4.5 · D-7 (new, found while pinning the move-task ratchet): move-task's force-override sentinel was set only from the operator's --force flag, but an unforced for_review -> in_progress is auto-promoted to emit_force=True further down the plan. Measured on the pre-fix tree: exit 0, last row force=true review_ref=null — the identical invalid row the issue reports for agent status emit. Fixed by filling the existing sentinel after emit_force is final (both force routes, one vocabulary). This is not the D-1 anti-pattern: force-override is move-task's declared semantic for an operator rewind.
