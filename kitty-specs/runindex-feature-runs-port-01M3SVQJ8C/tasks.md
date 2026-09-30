# Tasks — RunIndex port

Mission: runindex-feature-runs-port · #5390, #5389 · refs #2624

| ID | Task | Deps | Issue |
|----|------|------|-------|
| T00 | Campsite: hoist entry-key + run-store path literals to named constants (behaviour-preserving) | — | — |
| T01 | Red-first `@pytest.mark.regression` copy repro through `next` (original cursor untouched) | — | #5390 |
| T02 | Red-first `@pytest.mark.regression` move repro through `next` (continues, no RUN_STATE_MISSING) | — | #5390 |
| T03 | Red-first `@pytest.mark.regression` two-process concurrent-start (both registrations retained) | — | #5389 |
| T04 | Red-first port test: never persists an absolute run_dir | — | #5390 |
| T05 | Implement `run_index.py` port: token serialize, read-time resolve+containment, locked RMW | T00 | #5390,#5389,#2624 |
| T06 | Rewire `runtime_bridge_io.py` funcs to delegate to the port; keep ≤15 complexity | T05 | — |
| T07 | Route `state/contract.py` filename through the port constant | T05 | — |
| T08 | Heal migration `m_*_heal_run_index_paths` (+ `describe_leaks`) | T05 | #5390 |
| T09 | `doctor run-index` self-registering sibling (`_run_index_doctor.py`) | T08 | #5390 |
| T10 | Gate: single-reader (empty allowlist) + self-mutation test | T06 | #5390 |
| T11 | Gate: port never persists absolute run_dir (behavioural) | T05 | #5390 |
| T12 | Docs + CHANGELOG (Before/After); doctor help text | T06 | — |
| T13 | Validate: make test-fast + touched module + gate files; record counts | all | — |

Green criteria: T01–T04 RED pre-fix, GREEN post-fix; all AC in spec.md met.
