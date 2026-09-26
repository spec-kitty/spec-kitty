# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-09-25 — Decision: #4889 detector keys on **WP lane state** (canonical `in_progress` via the reducer + persisted `WorkspaceContext`), not on ref existence. Alternatives: key on branch/worktree existence only (status quo — the bug), or reflog-scan for a stranded tip. Rationale: ref existence is defeated by the #4969 origin-preference path (a stale `origin/<lane>` can resurrect and disguise an empty re-cut); lane state is the honest signal.
- 2026-09-25 — Decision: #4889 fails **closed** with a diagnostic (names the missing branch + recovery ref) rather than auto-recovering the stranded commit. Alternatives: auto reflog/`fsck` recovery. Rationale: the issue's own *Regression expectation* specifies exit non-zero + diagnostic; auto-recovery is riskier and out of scope for a P0.
- 2026-09-25 — Decision: #4905 root fix is at the **claim-commit staging** (keep `tasks/WP*.md` off the coord branch via the existing `commit_to_primary_target` partition mechanism), not a new merge driver for the WP file. Alternatives: teach FR-009 `_merge_recorded_planning_commit` to auto-resolve the add/add. Rationale: keeping a PRIMARY-partition artifact off coord is the canonical-single-authority fix (same class as #3371); a merge driver would paper over a partition leak.
- 2026-09-25 — Post-tasks anti-laziness squad folds (before finalize): (a) `DestroyedLaneError` MUST subclass `StructuredError` (⊂ `RuntimeError`) so the orchestrator's existing `except (…, RuntimeError)` catches it → keeps the #4889 fix inside WP01's owned files and gives a structured envelope (NFR-004); a bare-`Exception` copy of the `DirtyWorktreeError` sibling would escape it. (b) WP01 must read status via `placement_seam(...).read_dir(STATUS_STATE)` (coord surface), never `repo_root/kitty-specs/<slug>` (sparse-excluded PRIMARY tree → silent no-op on coord). (c) Red-first repros reworded to assert the DESIRED post-fix state (RED on main), not the current bug. (d) `commit_to_primary_target` is a `BookkeepingTransaction.acquire` bool flag → WP02 runs a second acquire for primary-bound paths; path→kind via `kind_for_mission_file`. (e) Added a non-`in_progress` (blocked/for_review/in_review) trigger-arm test so a predicate keyed on `in_progress` alone can't pass green.
- 2026-09-25 — Review follow-ups (non-blocking, deferred per smallest-viable-diff on a P0): (WP01) the #4889 REACH check keys on `WorkspaceContext.base_commit` (parent SHA), not the lane's work tip — sound/fail-closed for coord (P0 closed) but a narrow false-pass window remains when the parent landed on target but work didn't; closing it needs work-tip persistence (WorkspaceContext schema + write-on-commit). No `--force` override exists to bypass a false refusal. (WP02) primary+coord commits are not atomic (harmless for the 3 covered sites since the WP file is byte-stable there) and `coordination/transaction.py::acquire`'s docstring still names only one `commit_to_primary_target` caller (now two). All recorded for the PR body / a follow-up issue rather than expanded into this P0.
- 2026-09-25 — Wrap-up step 2 (dev-assist test cleanup): all mission tests judged KEEP. test_issue_4889_*, test_issue_4905_*, and test_lane_allocation_integrity_e2e.py are genuine issue-pinned reintroduction guards in correct homes (tests/lanes, tests/orchestrator_api, tests/specify_cli), not characterization/parity/timing/__module__ scaffolding — the @pytest.mark.regression marker is the correct permanent form. Nothing retired or split.
