# Decision Moment `01M2NRXNA9Y4P8QVTRMHP0D5KH`

- **Mission:** `cli-boundary-robustness-01M2NQCB`
- **Origin flow:** `specify`
- **Slot key:** `specify.json-gate.closure-scope`
- **Input key:** `json_gate_closure_scope`
- **Status:** `resolved`
- **Created:** `2026-09-16T18:50:59.785343+00:00`
- **Resolved:** `2026-09-16T18:51:21.622133+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How wide does the --json envelope-SHAPE convergence reach (post-spec squad finding B1: >=24 files, >=8 divergent shapes all pass a parse-only gate)?

## Options

- Shape-gate on in-scope adopted surfaces + universal parse-ability + converge divergent shapes inside touched files; file a follow-up for full cross-repo convergence; downgrade SC-005/NFR-004 to in-scope (RECOMMENDED, squad consensus, bounded MVP)
- Full shape convergence now across all ~24+ --json error surfaces (strongest closure, ~24-file blast radius, touches files no issue filed against)
- Parse-only gate as originally specced (smallest, leaves 8 divergent shapes, weak closure, re-report risk)

## Final answer

Shape-gate on in-scope adopted surfaces + universal parse-ability. The enumeration gate asserts the canonical error envelope SHAPE ({ok:false,error:{code,message}}) on the error paths of every command this mission ADOPTS, plus json.loads-parseability on ALL --json-capable commands (discovered by structural Typer introspection over the 4 flag vocabularies: json_output, --json, json:bool, output_json), plus an explicit+extensible empty-path case list. Converge divergent envelope shapes inside touched files (e.g. cli/helpers.py:474 exit_git_resolution_failure) onto the canonical shape. Downgrade SC-005/NFR-004 to in-scope surfaces. File a follow-up issue for full cross-repo envelope convergence of the remaining ~12 divergent shapes (charter_bundle.py, implement.py, _mission_state_doctor.py, etc.) as a deferred DIRECTIVE_040 architecture item. Rationale: honors expand+close-the-class for what the mission touches, keeps the 4.0.0 MVP blast radius bounded (~10-12 files), keeps the closure claim honest, and gives the residual a tracked home. Squad consensus (paula-patterns + reviewer-renata).

## Rationale

_(none)_

## Change log

- `2026-09-16T18:50:59.785343+00:00` — opened
- `2026-09-16T18:51:21.622133+00:00` — resolved (final_answer="Shape-gate on in-scope adopted surfaces + universal parse-ability. The enumeration gate asserts the canonical error envelope SHAPE ({ok:false,error:{code,message}}) on the error paths of every command this mission ADOPTS, plus json.loads-parseability on ALL --json-capable commands (discovered by structural Typer introspection over the 4 flag vocabularies: json_output, --json, json:bool, output_json), plus an explicit+extensible empty-path case list. Converge divergent envelope shapes inside touched files (e.g. cli/helpers.py:474 exit_git_resolution_failure) onto the canonical shape. Downgrade SC-005/NFR-004 to in-scope surfaces. File a follow-up issue for full cross-repo envelope convergence of the remaining ~12 divergent shapes (charter_bundle.py, implement.py, _mission_state_doctor.py, etc.) as a deferred DIRECTIVE_040 architecture item. Rationale: honors expand+close-the-class for what the mission touches, keeps the 4.0.0 MVP blast radius bounded (~10-12 files), keeps the closure claim honest, and gives the residual a tracked home. Squad consensus (paula-patterns + reviewer-renata).")
