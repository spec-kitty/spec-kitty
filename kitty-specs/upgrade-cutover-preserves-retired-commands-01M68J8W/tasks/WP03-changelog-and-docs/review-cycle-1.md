---
affected_files: []
cycle_number: 1
mission_slug: upgrade-cutover-preserves-retired-commands-01M68J8W
reproduction_command:
reviewed_at: '2026-10-31T09:59:23Z'
reviewer_agent: reviewer-renata
wp_id: WP03
---

# WP03 review — changes requested

One finding, docs clarity (the only blocking one):

**D1 — the new subsection's first sentence is ungrammatical and loses the second removal condition.**
`docs/api/upgrade-lifecycle.md`, "Project-local command files stay retired":

> which delete only a file proven generated (it carries a `<!-- spec-kitty-command-version: … -->`
> marker) and replaced globally; a file without the marker is yours and is left alone.

`3.1.2_globalize_commands` removes a file only when **both** hold: it is proven generated (the
marker), *and* an exact global replacement exists. The sentence as written makes the second
condition a dangling participle ("a file proven generated … and replaced globally"), so a reader
cannot tell that a marked file with no global equivalent is kept. Please reword to state both
conditions, e.g. "which delete only a file that is proven generated (it carries a `…` marker) and
that has an exact global replacement; a file without the marker is yours and is left alone."

Everything else passes:

- Changelog entry: impact-first lead, `(#6547)`, before/after, 945 characters, "what to do" present.
- `check_docs_freshness --ci`: errors=0; the only index change is the one anchor row for the new
  heading (the shared-file note is recorded in the move-task reason).
- `tests/architectural/test_no_legacy_terminology.py`: 98 passed after `make sync-packs`.
- Anti-pattern checklist: dead code N/A; no fixture change; silent returns N/A; FR-007 covered;
  no frozen file touched; no locked decision contradicted; shared-file ownership noted; no new raise.
