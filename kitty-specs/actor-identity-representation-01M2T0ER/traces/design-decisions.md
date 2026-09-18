# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-09-18 — Scope folds #3029 as its representation half only (operator decision); alternatives (drop flag / demote accept gate) and precondition #2993 excluded. #3029's WP re-verifies the live `move-task --agent` path first and closes-with-evidence if already fixed.
- 2026-09-18 — #4673 has two roots: (a) CLI-local rejection re-stamping the reviewer as owner (fixed here) and (b) the shared `spec-kitty-events` reducer's two-pass fold ordering (PyPI-pinned 9.1.6, not editable). Operator decision: fix (a) CLI-side and file a scoped upstream follow-up for (b) only if it still contributes after the CLI fix. Do not vendor or edit the installed package.
- 2026-09-18 — Reuse the already-closed #2861 compact-`--agent` parser and resolved-actor pattern rather than inventing new projection logic.
- 2026-09-18 — Post-spec squad (code-verified) corrected the fix seam: the impl-claim identity key (`_actor_key`) is tool-scoped and ROLE-BLIND by design; reviewer-vs-implementer distinctness lives on the separate review-claim role channel (which degrades to ALLOW on a stale/None role). So #4665's fix = make the two representations of one agent compare EQUAL on a bare-STRING tool-scoped key (never a tuple/struct — the generic-actor allowance is a bare-string `in` test). Role distinctness is NOT encoded into the key. Ownership is carried by THREE authorities (transition `actor`, runtime `agent` released-on-rejection, sticky `role`), not two — captured as C-006.

### 2026-09-18 — WP04 (#3029, representation half): verified already fixed
Verify-first (T015) on lane tip a36a836da1 (WP01-WP03 landed): a real `move-task --agent <identity>` non-claim hop already persists the acting identity into the reduced ownership slot (`_mt_emit_runtime_state`, `tasks_move_task.py:2858`, combined with WP03's T012 fix in `_mt_emit_transitions`, commit 5222cf5cc7). The originally-reported "no agent key at all" symptom (#3029) is stale. Landed a GREEN characterization regression (`tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py`, commit 3feb4787bb) instead of a red-first repro, per C-004/NFR-003's #3029-specific carve-out. No code change to `tasks_move_task.py`. FR-009 satisfied; close #3029 (representation half) with this evidence.
