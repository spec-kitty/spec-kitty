# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

## Seed (2026-09-27)
- `agent mission create` context-derived topology defaulted to `coord` on a non-primary CI branch (docs suggested single_branch); had to delete+recreate with explicit `--topology lanes`. #5150 notes there is no sanctioned flatten for a live coord mission — recreate-while-scaffold was the only clean path.

## finalize-tasks issue-matrix auto-classifier (2026-09-27)
The scanner mis-classified rows after finalize-tasks (friction-point: "verify the issue-matrix after finalize"):
- #4943 (a primary issue this mission *closes*) was auto-classified `context_only`/`not-applicable` — it should GATE, like #5171 (same "closes …" sentence) which was correctly gated `unknown`. Inconsistent classification of two issues cited identically.
- #5169/#5172 (cited only in the Assumptions "out of scope" sentence) were auto-classified gating (`unknown`) — corrected to `not-applicable` via issue-verdict.
Meta-irony: this mis-gating is adjacent to the very verdict-integrity class this mission fixes. Candidate catfooding issue for the classifier's "closes #N" vs context-only heuristic. Implementers must author #5171→fixed and #4943→fixed at completion (issue-verdict overwrites the not-applicable scaffold).
