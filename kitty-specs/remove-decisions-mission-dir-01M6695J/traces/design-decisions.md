# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude · Design decision: the two orphaned leniency tests are DELETED, not re-pointed — they pin the deleted helper's own behaviour; the fail-loud coordination contract survives through the write-side pre-resolution suites. Design decision: the guard test (FR-004) is a standing-invariant pin per DIRECTIVE_041 — it prevents reintroducing a divergent read path for the decisions event log.

2026-10-30 · claude · Spec-squad (kimi-k3, reviewer-renata profile) verdict: spec sound, no blockers. Accepted findings folded: (1) the WP06 ledger row for decisions/service.py in docs/development/reference/read-side-seam-classification.md:793 documents the deleted site and now records its removal per the ledger's own '(removed, #NNNN)' convention (FR-003/T003 extended); (2) test_read_seam_leniency.py's module docstring cites a wrong ledger path — corrected in the same FR-002/T004 edit. Rejected: none. Squad also verified the no-src-caller claim, the _PRE_SPLIT_QUALNAMES risk assessment, and that the FR-004 guard is a real non-vacuous invariant.

2026-10-30 · claude · Red-first T006 surfaced two additional anchor callers of the deleted helper: tests/decisions/test_decisions_reconciler.py::test_service_and_doctor_resolve_ledger_dir_in_lockstep (+ its _under_coord_topology variant) call _service_mod._mission_dir to obtain the COORD events dir for comparison. These are live lockstep pins (ledger-dir agreement between service and doctor), not orphaned helper pins, so they stay and are re-pointed to resolve placement_seam(...).read_dir(STATUS_STATE) directly in the test. The literal grep 'service._mission_dir' missed them because they alias the module as _service_mod; a full '_mission_dir' sweep confirmed no other callers. tasks.md T004 and WP01 owned_files amended accordingly.

2026-10-30 · claude · Consolidation stale-assertion findings adjudicated — all 4 HIGH flags are false positives: test_retrospective_terminus_recovery.py:50, test_service_idempotency.py:255, test_service_open_repair.py:225 and test_service_terminal.py:529 each call a LOCAL fixture helper 'def _mission_dir(repo_root)' defined in the same file (flat kitty-specs/<slug> path constructor), not the deleted specify_cli.decisions.service._mission_dir. The checker is name-based. All tests/specify_cli/decisions/ suites green in T006; renaming unrelated local fixtures would be scope creep (DIRECTIVE_024).
