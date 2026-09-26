# priti-verify: adversarial second pass on the 53 UNCOVERED / CLOSED-ONLY clusters

Profile applied: planner-priti (role planner; avoidance boundary: no implementation or architecture calls, no tracker writes; DIRECTIVE_003: every verdict change carries a written rationale, in the `note` and `searched` fields of priti-verify.jsonl).

Method: 1-2 semantic `search_issues` queries per cluster (quota shared, some 403s, retried), AND-regex over all 3,187 issue bodies (`vs.py`), and a body read of every candidate before counting it as a match. Open matches that drive a revision (#4611, #4922, #3518, #2897, #4708, #1931) were re-confirmed open through the API during this session. Other open states come from the 09:22 snapshot.

## Verdict changes (5)

| Cluster | Was | Now | Evidence |
|---|---|---|---|
| A-21 | CLOSED-ONLY | PARTIAL | #4611 (open, partial): OPEN: project-local .kittify/overrides copies of tasks-outline/tasks-packages carry stale pre-fix wording and win the 6-tier chain; 'no parity gate exists'. Same class, different file (not plan-template.md) |
| A-26 | UNCOVERED | PARTIAL | #2897 (open, partial): OPEN: durable artifacts must cite stable identifiers, optional lint gate; covers the 'committed artifacts cite workspace-local SK-xx ledger ids' facet by class. Fork-assign, gh pr view 100-file truncation and closed-issue-as-open-report facets remain uncovered |
| C-11 | CLOSED-ONLY | PARTIAL | #1931 (open, partial): OPEN epic explicitly scopes 'Test-suite state leaks — atomicity, idempotency, self-cleaning (fake missions, /tmp litter, hardcoded shared paths)'; the specific residuals (_SEED_COUNTER, reset_adapters, Path.cwd defaults) are not enumerated |
| C-17 | UNCOVERED | PARTIAL | #4708 (open, partial): OPEN: 'no test path silently out of every lane' + meta-guard ask; path/registry-based, does not name marker-deselected quarantine tests |
| D-14 | UNCOVERED | PARTIAL | #3518 (open, partial): OPEN: item 1 collapses artifact-dir enumerations incl. snapshot._ARTIFACT_BUCKETS onto ArtifactKind (covers that facet) |

All five changes go from weaker to stronger coverage, and all are PARTIAL: an open issue covers the mechanism class or one facet. None reaches COVERED.

## Flags that do not change a verdict

- **C-09, a likely mis-close.** A groom bot closed #3143 on 2026-09-24 'as delivered by PR #3144'. #3143 describes the gap that same PR left behind. `pytest.ini` addopts still has no `--timeout` at HEAD 4fb54f3f. This is a candidate for reopening, not for a new issue.
- **B-14 / C-32.** Open issues #2555 (sync-daemon hang item) and #2801 (pre-review gate reusing the sync toggles) still carry facets of retired sync behaviour. #2801 is probably stale since #3980. Both are candidates for pruning, not coverage.
- **E-08.** Closed #2447 shows that branch-derived mission detection (`_detect_from_branch`) was retired on purpose. Inferring `--mission` from the worktree needs a design decision before anyone files a bug.
- **D-22.** Open #2302 itself names `tracers/` as the convention, while the procedure says `traces/`. That is more evidence of the drift the cluster reports.
- **Regression signals (CLOSED-ONLY, tracer evidence dated after the close):** A-12, C-11, C-22, C-32, D-01, D-05, D-27, D-28, E-07 and E-30 are 'yes'. A-12, C-32 and E-07 concern mechanisms that are now retired. D-10 is unknown. Dates come from `meta.json created_at` of the evidence missions (group C's `evidence` field was truncated, so its missions were recovered from `build_priti_C.py` indices), or from the delegate's own date field.

## Confirmed UNCOVERED (24)

- **A-08**: requirement_refs have no per-ref status: descoped, retired, satisfied-by-omission and traceability-only look the same. A retired or struck-through FR is still counted as… (closest, adjacent only: #3481, #2066, #3519)
- **A-16**: wps.yaml has no mission-level or per-WP freeform notes field. finalize-tasks regenerates tasks.md mechanically, so mission-wide guidance (PR shape, chokepoints, gate tabl… (closest, adjacent only: #1676, #3944, #428)
- **A-20**: Issue and brief premises are often stale at specify time: already fixed, retired by an earlier mission, already being fixed by an open PR, or measured wrong (e.g. a '17 q… (closest, adjacent only: #2897, #3897)
- **A-24**: Generated implement guidance contradicts the charter workflow. workflow_executor.py prints raw `git commit -m "feat(WP##)…"` recipes where the repo mandates safe-commit (… (closest, adjacent only: #4625, #4632)
- **A-25**: The software-dev spec template has no optional Clarifications, Out-of-scope, Provenance or Sizing sections, and one mission got a 0-byte spec.md. The tasks-phase prompts… (closest, adjacent only: #2744, #3226, #3286)
- **A-34**: finalize-tasks warns 'missing plan_concern_refs and cross_cutting is not set' for plans that have no IC-## concerns at all. This is expected noise, and agents mark WPs cr… (closest, adjacent only: #1730)
- **B-13**: Lane identity has two uncoordinated sources: the static lanes.json WP-to-lane plan and the dynamic --base sequential allocator. The allocator minted a lane-b colliding wi… (closest, adjacent only: #3571, #3946, #4945, #2570)
- **B-15**: The mark-status surface is unscoped and dishonest. Subtask IDs restart at T001 in every WP and mark-status has no --wp flag, so it silently writes to the first WP and rep… (closest, adjacent only: #3944, #2493, #2962)
- **B-23**: safe-commit has no WP-lifecycle awareness. It accepts and pushes implementation commits for a WP still in planned (the event log and git disagree), and emits ACTIVE_WP_CO… (closest, adjacent only: #4625, #3936)
- **B-26**: Zeitgeist approval moments are dropped. `--review-result-json` records `review_result`, but StatusTransitionPayload requires `evidence` for approved/done, so every approv… (closest, adjacent only: #4327, #4214)
- **B-30**: Branch-context resolver blind spots. planning_base_branch and merge_target report the mission's own target branch rather than the real branch-off commit for stacked-PR to… (closest, adjacent only: #4857, #3874, #3124)
- **C-04**: Dev tooling is split across optional extras: a bare 'uv sync' installs neither test nor lint; mypy lives only in the lint extra; tests shell out to 'python -m ruff'/'pyth… (closest, adjacent only: #4922, #2803)
- **C-14**: Mutation evidence rots silently: mutation plugins go obsolete when patched symbols move (3 of 5 inert, TypeErrors counted as kills), the CI mutation job is disabled, and… (closest, adjacent only: #3125, #4810)
- **C-23**: Charter-mandated quality checks are absent or vacuous in live CI: no workflow invokes mypy, the commit-msg job only runs 'git log ... || true' (commitlint never runs), ma… (closest, adjacent only: #1931, #1928, #2844)
- **C-34**: Red-first anchor mechanics: characterization tests that encode the bug must be inverted, companion tests can be vacuously red/green, RED shape choice (AttributeError vs I… (closest, adjacent only: #1277, #4891)
- **D-04**: Planning does not enumerate which architectural gates, allowlists, layer ledgers, facade tables and CI shard roots a planned edit will trip; plans assert 'deletions only… (closest, adjacent only: #3487, #4227)
- **D-19**: docs/configuration/linting-cutoff-policy.md lists bandit and pip-audit as blocking checks, but no workflow in .github/workflows/ runs either (they are only dev dependenci… (closest, adjacent only: #1226, #3181)
- **D-22**: Tracer-file location never converged: the mission-tracer-files procedure says traces/, missions use traces/ (53), tracers/ (18), tracer/ (1) and root tracer-*.md (48); an… (closest, adjacent only: #3072, #2302, #4959)
- **D-34**: Fail-open patterns recur as a class (`is False` tri-state checks, truthiness on falsy values, match without default, dict.get(key, PERMISSIVE) on policy tables) and are f… (closest, adjacent only: #2992)
- **E-08**: --mission is required on nearly every verb (433 missions in-tree) even inside a lane worktree or right after next resolved it; WP prompt footers and --help examples omit… (closest, adjacent only: #4677, #4682, #2447, #2624)
- **E-19**: Acceptance criteria and red-first tests pass vacuously: 13/29 requirements passable by a no-op, refusal probes without positive controls, flag-threaded strict paths never… (closest, adjacent only: #1931, #1277, #3264)
- **E-20**: Specs, operator rulings and dispatch briefs are issued from summaries or stale citations rather than first-hand source: line citations drift within a round, truncated quo… (closest, adjacent only: #2897, #4230, #4067)
- **E-24**: A shared machine/tree is not a measurement substrate: 20+ concurrent pytest runs across agents give false reds (port band, leaked daemons, 7-min runs), fill tmpfs (EDQUOT… (closest, adjacent only: #3978, #1907, #3943)
- **E-25**: WP dispatch briefs omit load-bearing facts: whether sub-delegation is allowed (two writers committed to one WP), that dependency lanes are already merged into the lane-pl… (closest, adjacent only: #3936, #1840)

## Confirmed CLOSED-ONLY (24)

A-02, A-12, A-27, A-29, B-14, B-18, B-24, B-32, C-09, C-22, C-25, C-32, C-33, D-01, D-05, D-10, D-11, D-23, D-27, D-28, D-30, E-07, E-13, E-30

## COVERED sanity pass (45 clusters)

Every cited open issue on the 45 COVERED clusters is present in open_issues.tsv (0 misses). Details are in priti-verify-covered.txt. Soft spots: C-07, D-16 and D-24 are COVERED on partial fits only. E-21 is COVERED by doctrine (the squad-cadence standing order) and has no issue.
