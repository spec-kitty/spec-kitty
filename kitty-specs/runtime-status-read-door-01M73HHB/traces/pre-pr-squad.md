# Pre-PR adversarial squad: dispositions

Point-cut: pre-PR, branch `refactor/7310-status-read-door-s5` rebuilt on `origin/main`. The question: is the branch safe to open as a PR, judged by design coherence, correctness and regression, and failure modes?

Lenses (profile-loaded, read-only, run in parallel): `architect-alphonso`, `reviewer-renata`, `debugger-debbie`. All three returned **ship-with-fixes**.

| # | Finding | Lens(es) | Severity | Disposition |
|---|---|---|---|---|
| 1 | Board path: `StatusSurfaceRefUnreadable` at read time escapes as a traceback (default-topology Mission, branch ref unreadable). Reproduced. | debugger | MAJOR | **Fixed** red-first: `42f472d1` (red), `91434cb3` (fix) |
| 2 | ADR 2026-11-06-2 amendment says an owned dispatch refuses on an "empty or unmaterialized" workspace; shipped behaviour refuses only when empty | architect | MAJOR | **Fixed** `504a81ea` |
| 3 | No `fixed` changelog fragment for #7507 or the two lanes crashes | reviewer | MAJOR | **Fixed** `55a19f69` |
| 4 | No test for a landed Mission with a retained, materialized coordination worktree | architect, reviewer | MINOR | **Fixed** `3b610ca2` (passes as written) |
| 5 | `recovery.py` `no-any-return` when changed files are type-checked together | reviewer | MINOR | **Fixed** `ce435f51` |
| 6 | Lifecycle row dropped by a bare `except` with no log line | reviewer, debugger | NIT | **Fixed** `70e65576` (debug log) |
| 7 | Re-pin comment narrower than the field docstring; lane-mates advisory docstring claims "never crashes" (also false on main) | reviewer, debugger | NIT | **Fixed** `14ee97da` |
| 8 | Advancing `next` reads the door 3 times per decision (query: once); NFR-002 holds per helper, not per decision | architect, debugger | MINOR | **Deferred**: follow-up issue (carry one `BoardStatus` on `DecideNextContext`) |
| 9 | `recovery._get_wp_lane_from_events` re-reads the log per WP and turns a ref failure into `planned` | debugger | MINOR | **Deferred**: follow-up issue (mitigated: `implement --recover` materializes first) |
| 10 | Non-owned bootstrap progress falls back to a path read on a ref or registry failure, so it can be stale with only a debug log | architect, debugger | MINOR | **Deferred**: follow-up issue (decision stays safe; the board blocks) |
| 11 | Landed routing in `next_invocation_lifecycle` is a second derivation of the door's `CONSOLIDATED_TARGET` | architect | MINOR | **Deferred**: follow-up issue (they agree today; tests pin it) |
| 12 | `board_status_from_dir` and the `status_dir=` path forms are not scanned by the single-door gate | architect | MINOR | **Deferred**: follow-up issue (add them to the gate's allowlist so the ratchet tracks them) |
| 13 | Status directory derived before the wrap (non-owned) and after it (owned) | architect | MINOR | **Deferred**: with #8 |
| 14 | With `owned` set, the door ignores the handle; a strict slug check would refuse a valid mid8 or ULID | reviewer | MINOR | **Deferred**: document in the follow-up issue |
| 15 | `_dispatch_via_composition` takes `owned` beside `seam`, and `seam.owned` is the same object | reviewer | NIT | **Deferred**: with #8 |
| 16 | Commit subject of `572c8d8a` says "42 entries"; final count is 33 | reviewer | NIT | **Accepted as is**: historical, and the trail is in `_baselines.yaml` |

Checked clean: layer rules (107 passed), gate numbers consistent (33/33/33), re-pins assert behaviour, no new skip or xfail (one sparse-checkout skip), error codes unchanged outside the named cells, no read-path side effects, and nothing in this diff creates the stale `decisions/index.json.lock`.
