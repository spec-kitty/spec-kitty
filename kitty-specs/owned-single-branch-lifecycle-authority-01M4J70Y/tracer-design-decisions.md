# Tracer: Design decisions — owned single-branch lifecycle authority

Seeded at planning (2026-10-10). Full provenance in research.md.

## Decisions (operator-ruled 2026-10-10)
- D1 One-resolver seam; `owned=` threading; NO `core/paths.py` edit.
- D2 WP01 extends to `orchestrator_api/decision_verbs.py` (branch omitted it).
- D3 #5893 includes BOTH halves (recording + material/charter authority); guard relaxation limited to the reviewed package-identical GLOBAL mirror.
- D4 #5947 verify-green + defensive owned hardening; no fabricated red, no test-expectation edits.

## Adopted-vs-rewrote (per issue)
- #5877, #5878, #5893-recording: adopt-as-is. #5874, #5880, #5892, #5893-authority: adopt-with-rebase. #5874-orchestrator-api, #5947: new/extend.

## Running notes
- (append during implement)
