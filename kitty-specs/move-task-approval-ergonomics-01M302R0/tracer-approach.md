# Tracer — Approach

Mission: move-task / approval-gate ergonomics (#3469)

## Seed (planning)

- **Strategy:** two levers on one root (over-collection + under-provision of honest verdicts),
  fixed coherently: (a) classify discovered `#NNNN` references so only implementation-targets
  gate; (b) add a truthful non-gating `not-applicable` verdict for the residual/recorded rows.
  Single source of truth for "is this reference gating?" must be pinned (avoid a
  parallel-authority split between the discovery lever and the verdict lever).
- **Reuse, don't reinvent:** extend the existing discovery/scan (`tasks/issue_reference_discovery.py`
  + `tasks/issue_matrix.py detect_issue_references`) with classification rather than a second
  scanner; extend `IssueMatrixVerdict` (`review/_issue_matrix.py ~L50`) additively; thread the
  new value through `issue_verdict.py` help/validation and the approval blocker
  (`tasks_parsing_validation.py ~L283-302`).
- **Sequencing:** WP01 classification (foundation) → WP02 verdict enum + ADR (consumes
  classification) → WP03 gate/CLI ergonomics + docs. move-task flag aliases are independent and
  parallelizable.
- **ATDD:** each in-scope defect gets a red-first `@pytest.mark.regression` repro through the
  pre-existing entry point, RED on the planning base, GREEN on the fix.
- **Do NOT:** re-fix #4330 (error string, batched surfacing) or regress #2816 (event-sourced
  subtasks — checkbox fix is docs-only).

## Appended during implement

_(to be filled per WP)_
