# Tasks HALT ruling — orchestrator, 2026-09-28

**Findings ruled on:** TASKS-FRESH2-001 (severity 4) and TASKS-FRESH2-002 (severity 3), both in
`tasks-fresh-2.yaml`, surfaced by the round-2 fresh sweep after fix commit `ac925fffc`.

**Why this is a HALT under the protocol, not a routine continuation:** the R6 gate's early-stop
rule triggers here — the severity-≥3 finding count did not fall between the round-1 fresh sweep
(2 findings ≥3: TASKS-FRESH-001, TASKS-FRESH-002, both now resolved) and the round-2 fresh sweep
(2 findings ≥3: TASKS-FRESH2-001 at severity 4, TASKS-FRESH2-002 at severity 3). A flat count
across a round, per `review-protocol.md` §R6, means stop rather than spend the remaining round
budget. Because TASKS-FRESH2-001 is severity 4 (`> 3`), the plain gate rule is HALT.

**Applying the plan-phase standing rule (carried forward to tasks/analyze per
`reviews/plan.ruling.md`'s own text):** "A HALT where every surviving finding has one concrete
remedy and none touches an operator decision/ruling gets one extra bounded fix + verify round
without a new operator question." This is the **first** HALT-triggering event in the tasks phase
(no prior `tasks.ruling.md` entry exists), so the one-extra-round allowance is available.

## Classification of the two surviving findings

**TASKS-FRESH2-001** (severity 4): `plan.md` (PASSED at HEAD `a117695b5`, ground truth for this
phase) still shows the old, buggy `gh pr list ... --json number` sample in two places — the
"Open-PR check (verbatim)" bullet (plan.md item (b)) and the TOCTOU re-verification paragraph's
restatement of it — even though `tasks/WP02-recapture-decision-script.md`'s own T011 subtask was
corrected this round to `--json number,headRefName`. WP02.md tells the implementer to treat
plan.md's bullet as "verbatim," so an implementer who trusts that label over WP02.md's corrected
text would silently reintroduce the exact bug the round-2 fix just closed (`pr.get("headRefName")`
always `None`, so `find_open_recapture_pr` never matches, so FR-007's skip-if-open guarantee never
fires in production).
- **(a) One concrete remedy? YES.** Do **not** hand-edit the PASSED `plan.md` artifact (reopening a
  closed phase's content is exactly the kind of silent artifact mutation this mission's own
  doctrine avoids elsewhere — see plan.md's own NFR-002 "interim projection, revisit post-dispatch"
  pattern for the precedent of flagging drift via a note rather than rewriting settled text).
  Instead: add an explicit note to `tasks/WP02-recapture-decision-script.md`'s T011 section (and,
  if useful, a one-line pointer in `tasks.md`'s traceability row) stating plainly that plan.md's
  item (b) "Open-PR check (verbatim)" bullet and its TOCTOU paragraph's restatement of the same
  command predate this fix and are **superseded** by T011's corrected `--json number,headRefName`
  command; WP02.md's own text is authoritative for implementation, not plan.md's now-stale sample.
- **(b) Touches an operator decision/ruling? NO.** Neither `spec.ruling.md` nor `plan.ruling.md`
  addresses the `gh pr list --json` field list; this is a technical correction, not a design
  choice. (The choice of *how* to remedy it — a superseding note vs. editing plan.md — is an
  orchestrator judgment call, not an operator ruling matter, and is recorded here for that reason.)

**TASKS-FRESH2-002** (severity 3): WP01's new "reconciled against `guidelines.md`" paragraph
(added this round to mirror WP02's rigor) applies the "200-500 lines per WP prompt" guideline to
WP01's pre-existing "~350-450 estimated lines" (implementation-size) figure, without also citing
WP01's own actual prompt-file line count via `wc -l` the way WP02's parallel paragraph does for
itself. Both numbers currently fall inside the guideline's range, so the conclusion is unaffected,
but the stated reasoning is inconsistent with the sibling paragraph it was written to match.
- **(a) One concrete remedy? YES.** Add WP01's own actual prompt-file line count (via `wc -l`,
  measured fresh, not copied) to the paragraph, alongside the existing implementation-estimate
  figure, mirroring WP02's denominator clarification.
- **(b) Touches an operator decision/ruling? NO.** Pure internal-consistency/wording fix.

**Ruling: both findings get one more bounded R4 fix + full R5 (anchored verify + fresh sweep)
round, per the standing rule, before this counts as a second consecutive HALT.** If the next fresh
sweep returns any new finding at severity ≥3, that is a second consecutive HALT under the standing
rule's own terms and goes to the operator without a further self-granted round.

This ruling REPLACES the acceptance bar for TASKS-FRESH2-001 and TASKS-FRESH2-002: a verifier
judges each resolved iff the fix implements the point above (a superseding note for -001, an
own-file line count for -002) — not some independently-invented remedy.

---

# Orchestrator ruling (operator standing rule, `plan.ruling.md`) — 2026-09-28

**Finding:** AMENDMENT-FRESH-001 (severity 4), raised by the design-amendment fresh sweep and
carried out of that phase as out of its delta-only scope. WP03 Subtask T016's recapture job
invokes bare `python3 scripts/ci/recapture_charter_shard_timings.py` with no uv install or
environment sync; `capture_shard_timings.py` needs pytest and this repository's own installed
packages, so the scheduled job would fail with `ModuleNotFoundError` on its first run. Orchestrator
verified the T016 text directly.

**Classification:** (a) one concrete remedy — yes; (b) touches an operator decision or ruling —
no. The operator's standing rule therefore applies: one bounded fix + verify round, recorded here.
This ruling is issued by the orchestrator, not by a phase agent.

**Ruling:** T016's job gains the same environment steps the repository's existing jobs use and
that T020 already specifies — `actions/checkout`, `astral-sh/setup-uv` at the SHA-pinned ref
`ci-nightly.yml` uses, `uv sync --frozen --all-extras` — and the invocation becomes
`uv run --frozen python scripts/ci/recapture_charter_shard_timings.py` (or the equivalent the
plan's secret/checkout ordering requires; the secret check still runs before any recapture work,
per plan ruling 2). Any other bare-interpreter invocation in WP03 is fixed the same way. Nothing
else changes. A verifier judges the finding resolved iff every Python invocation in WP03 runs in
the synced environment and the job's step order still honours the fail-early secret check.
