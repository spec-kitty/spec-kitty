# Design decisions — implement-degod-01M44488

Running log of design choices and their rationale (1-3 sentences per dated entry). Seeded at
planning; the authoritative table is research/code-grounding.md §2 (D1–D10).

- 2026-10-04 — D4: the existing tasks patch-liveness gate is widened to the implement family. No new
  gate is added (operator ruling: no new size or ratchet gates; a liveness gate is a correctness
  check, and widening reuses the #5684 precedent).
- 2026-10-04 — D5 / DM 01M4455PBFDASHQ7R9DN5ZQRMW: #5232 is delivered through the write-shaped
  placement seam (option B), following the `mission_record_analysis` precedent. It does not fail
  closed on every context error (option A), which would newly refuse flat missions (INV-7) and the
  unmaterialized-coordination window. Escalation guard: spec C-007.
- 2026-10-04 — D6: #5673 is shaped (pure claim-commit path bundle) but not fixed, because changing
  the claim commit's content is a behaviour change. #5676 lives in `mission_creation.py` and is owned
  by the sibling mission #5634.
- 2026-10-04 — R-1: #5232 is delivered as B2\*, a seam-owned typed placement whose degrade arms
  are keyed on a "context unresolved" flag. A 64-state real-git characterization showed it
  byte-identical to today. The literal single-path shape (B1) changes four reachable outcomes, so
  it becomes an operator follow-up and is not taken here (C-001/C-007).
- 2026-10-04 — R-1: #5232 is delivered as B2\*, a seam-owned typed placement whose degrade arms
  are keyed on a "context unresolved" flag. A 64-state real-git characterization showed it
  byte-identical to today. The literal single-path shape (B1) changes four reachable outcomes, so
  it becomes an operator follow-up and is not taken here (C-001/C-007).
- 2026-10-05 — WP06: no seam or topology helper answers "is a coordination branch declared", so the
  identifier cascade's `coordination_branch` is used as a boolean predicate only. The ref value
  always comes from the placement seam (`write_target(DECISION_LOG)`). The full-outcome diff over
  the 18 FR-015 rows gave 0 diffs.
- 2026-10-05 — R-1b / DM 01M44THPFVJSWH7FEE8X5JKSZV: the WP06 review found 4 reachable
  double-fault divergences under B2\*. The degrade source is now the declared coordination-branch
  value, owned by the coordination seam and computed lazily after the structural check (B2\*\*).
  It is identical by construction, so no operator escalation is needed. Lesson: a 64-state matrix is
  evidence, not proof; equivalence by construction beats equivalence by sampling.
- 2026-10-05 — WP07: `BaseRefUnresolved` is a typed seam error, caught **inline inside the
  create-step try**. A plant proved the inline catch is load-bearing: letting the error reach
  `except Exception` changes the tracker text to "workspace allocation failed: …".
  `_validate_base_ref` and `_raise_base_ref_unresolved` stay CLI-side as translators, because their
  tests pin `typer.Exit`.
- 2026-10-05 — WP09: the phase-order test observes the real phase calls through a
  `sys.setprofile` hook rather than patched spies, so it adds no patch site to the SC-002 counter.
  `implement.py` leaves the mypy `ignore_errors` quarantine; an override with
  `follow_imports = "normal"` for `core.context_validation` types its decorator, while that
  module's own body stays quarantined.
