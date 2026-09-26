# Tracer: Design Decisions
## D1 — "Red-first" for a guard = demonstrate vacuity first
Plant the broken input the guard should catch, show it currently PASSES (vacuous), then tighten so it FAILS on that input while still passing on the real tree. The demonstration becomes the guard's permanent non-vacuity test (C-001/C-002).
## D2 — Real-tree basis, not planted-only text
Where a guard parses planted text only (#4210, #4536), re-base it on the actual artifact (test tree / pytest.ini / workflow) with a bounded, deterministic walk + explicit exemption list — never an unbounded/flaky scan.
## D3 — Test-infra only (C-003)
No src/ production change. #4536's dynamic-import coverage stays in the test layer.
## D4 — (append during implement/review)

## D4 — RESOLVED (post-spec/brownfield scout, paula-patterns): two spec BLOCKERS folded
- **#4105**: vacuity is in `test_no_dead_src_path_literals.py` (`is_retired_doc`/`_DOC_STATUS_RE` whole-file `finditer`), NOT `_dead_path_scan.py` (a different helper with 4 sibling importers — dropped from scope). Fix = frontmatter-scope `is_retired_doc` + drop `kitty-specs/` prefix + fix comment.
- **#4210**: (a) e2e-double-run is a GHOST (already removed by #4865) → re-scoped to "assert SPEC_KITTY_RUN_PERFORMANCE stays scoped to the performance job"; (b) the pure `find_functional_assertions_under_performance_marker(source)` is imported by `test_timing_coverage_invariant.py:51/525` — the tree walk must be ADDITIVE (new walker), never a signature change; bound the walk (rglob test_*.py + SyntaxError catch + exemption list).
- **#4036**: RED-first must prove a REAL cross-window straddle is caught (easiest to fake); guard already has an e2e firing proof, so fix is narrow discrimination.
- **#4408/#4536/#4388**: confirmed clean, disjoint, C-003-safe (no src/ dynamic jsonschema import; pytest.ini has no python_files override).
## D5 — WP-ownership: six disjoint EDIT sets (once #4105 corrected). Caveat: #4210 edits pytest.ini(desc)+ci-nightly.yml; #4388 only READS pytest.ini → sequence/coordinate. #4210's ci-nightly.yml edit must keep sibling workflow assertions green.
