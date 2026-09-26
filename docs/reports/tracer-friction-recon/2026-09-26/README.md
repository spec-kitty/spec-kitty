# Tracer-file friction recon (2026-09-26)

A recon squad read the tracer files of every mission in `kitty-specs/` that keeps them and pulled out
the recurring **frictions, concerns, notes and recommendations**. Then a planner squad checked whether
open issues in `spec-kitty/spec-kitty` already describe each friction **cause** or **suggested
improvement**.

| | |
|---|---|
| Missions read | **70**: every `kitty-specs/*` dossier with tracer files (root `tracer-*.md`, `traces/`, `tracers/`, `tracer/`). ULID dates run 2026-06-30 → 2026-09-25 |
| Tracer text read | ~24,600 lines across 205 files |
| Findings extracted | **966** items (507 friction · 219 note · 166 concern · 74 recommendation), each with a `file:line` pointer that was checked |
| Friction clusters | **165** distinct fixable causes or improvements, in five groups |
| Issue coverage | **45** covered by an open issue · **72** partially covered · **24** matched only by closed issues · **24** uncovered |
| Tracker actions | #3143 reopened into 4.0.0 scope; 40 issues filed (#5060–#5100), triaged and homed under functional epics. See [§6](#6-tracker-actions-taken-2026-09-26) |
| Governance | Dispatched as Op `01M3EFYEP1QFP1F7A2Z8TYF4A7`. Recon delegates were profile-loaded as `retrospective-facilitator`; coverage delegates as `planner-priti`. All delegates were read-only; no issues were filed or edited |

Detail lives beside this file:

- [`coverage-matrix.md`](coverage-matrix.md): all 165 clusters with verdict, matching issues and draft issue titles.
- [`findings/slice-N.md`](findings/): per-mission digests (3–8 tagged bullets per mission) and cross-mission themes per slice.
  - `findings/slice-N.jsonl`: the 966 raw items.
  - `findings/slice-N-missions.txt`: the exact tracer files read.
- [`issue-coverage/group-X.md`](issue-coverage/): per-group cluster tables, draft issues, suggested order and limits.
  - `issue-coverage/second-opinion.md`: the adversarial re-check of every UNCOVERED and CLOSED-ONLY verdict.

---

## 1. Headline findings

1. **The same few seams cause most of the pain.** Mission counts overlap because one mission hits several clusters:

   | Seam | Missions |
   |---|---|
   | finalize-tasks / planning | 39 |
   | coord ↔ lane ↔ primary placement | 34 |
   | arch-gate allowlists | 34 |
   | test flakes and baseline reds | 34 |
   | lane-worktree interpreter / venv | 32 |
   | review verdicts | 28 |

   The ten biggest clusters are process- or environment-shaped rather than product bugs: stale premises, unverified plan claims, missing lane interpreters, baseline-red churn, and CI-only breaks.
2. **Tracers themselves are under-used.**
   - 25 of 70 missions seeded tracers at planning and never appended during implement or review.
   - Tracers live in two layouts: root `tracer-*.md` in 46 missions, `traces/` in 53.
   - The richest logs (ci-nightly, interpreter-matrix, golden-path) show the value when the practice is followed.
3. **Isolation looks real but isn't.**
   - Lane worktrees have no interpreter of their own. The shared editable `.pth` imports the primary checkout's `src`, so tests can pass for the wrong reason (13 missions).
   - Several `spec-kitty` installs coexist on `PATH` (7 missions).
   - Concurrent agents in one checkout revert each other's edits (8 missions).
4. **Gates that can pass while protecting nothing.**
   - No workflow runs mypy. The commit-msg and markdownlint CI steps end in `|| true`. Bandit and pip-audit are documented as blocking but are not wired.
   - Quarantined tests run nowhere.
   - Acceptance criteria and red-first tests are often passable by a no-op (11 missions).
   - Several guards key on names or substrings.
   - I confirmed the first three of these against HEAD myself.
5. **Squads earn their cost.** In 11 missions, adversarial or integration squads caught HIGH defects that per-WP review missed: wrong fix targets, inert gates, and cross-WP regressions on the merged tree. The same data also shows planning squads over-iterating on wording (4–6 rounds).
6. **Historical clusters are gone.** The "writes then hangs" family (sync store, dossier upload, layout cutover: 9 missions, Aug 22 – Sep 2) is no longer reported by missions from `01M1K*` onward. It went away with the sync-transport retirement; don't reopen it.
7. **Issue coverage is decent but lopsided.** Product bugs in the CLI are well tracked, often by `from:qa` / `catfooding` issues. **Process, doctrine and environment frictions are mostly untracked.** 15 of the 24 UNCOVERED clusters are of that kind.

---

## 2. Theme report

Each theme covers four things:

- **Friction**: what hurts.
- **Concerns**: risks, debt and residuals.
- **Notes**: learnings worth keeping.
- **Recommendations**: what the tracers propose.
- **Coverage**: what the issue tracker already holds, citing cluster IDs from the matrix.

### 2.1 Mission tracer process (34 missions)

- **Friction:**
  - Tracers are seeded at planning and left at placeholders (25 missions). Some are written only at close, from memory.
  - `/specify`, `/plan` and `/tasks` never prompt for them.
  - Concurrent appends duplicate headings.
  - Tracers kept on a lane or planning branch block `move-task`, or get clobbered by squash merge.
  - The lane `kitty-specs/` guard fires on the very tracer files the charter tells implementers to append to.
- **Concerns:**
  - The `mission-tracer-files` procedure says absence "does not block acceptance". It still references the deleted `src/doctrine/` path.
  - The location never converged: the CLI `tracer-append` writes `traces/<cat>.md`, while briefs and most missions use root `tracer-*.md`.
- **Notes:** the logs that were kept append-only and self-correcting were the most useful input to this recon.
- **Recommendations:**
  - Auto-seed at `mission create`.
  - Prompt a per-WP append at implement/review handoff.
  - Add a non-blocking non-empty check at accept.
  - Make `tracer-append`, routed through the placement seam, the only writer.
- **Coverage:**
  - A-31 fill rate: PARTIAL (#3072).
  - A-32 split write surface: PARTIAL (#3072; #4959 closed).
  - D-22 layout convergence: **UNCOVERED**.
  - B-07, no lane-side seam for tracer writes: PARTIAL (#3931).

### 2.2 Planning, finalize-tasks and requirement mapping (39 missions, the densest cluster)

- **Friction:**
  - **False `LANE_DEPENDENCY_CYCLE`.** Every `planning_artifact` WP is bundled into one `lane-planning` node, which creates cycles when a planning WP sits both before and after code lanes. It hit 3 missions on 2026-09-22 alone.
  - **Topology-blind, non-idempotent generation.** `lanes.json` names a phantom `mission_branch` for `single_branch` missions, and a re-run undoes hand fixes. Frontmatter `dependencies: []` silently beats tasks.md prose.
  - **Refs dropped.** The regex drops letter-suffixed ids (`FR-005a`) and `SC-###`. `requirement_refs` lives in three unsynced copies (wps.yaml, frontmatter, tasks.md). When `wps.yaml` exists, `finalize-tasks` doesn't read its refs (`mission_finalize.py:1047-1060`).
  - **Analysis-staleness dance.** `mark-status` checkbox flips and tracer or issue-matrix edits re-stale `analysis-report.md` before each claim.
  - **`finalize-tasks` is not transactional.** A failing run has already written frontmatter, tasks.md and lanes.json.
- **Concerns:**
  - Plan-time claims are not checked against the code (14 missions). Census counts undershoot 2–3×, and named files or tests don't exist.
  - There is no way to mark a requirement descoped, retired or satisfied-by-omission, so it stays "unmapped".
  - `owned_files` is validated too late and too loosely: zero-match globs pass.
- **Notes:** `record-analysis` host-absolute path leakage (#3398) is fixed forward on main. Only the backfill of old dossiers remains.
- **Recommendations:**
  - Topology- and stack-aware generation.
  - Warn when a re-run would downgrade fields.
  - A single write path for refs.
  - Per-ref status.
  - A `notes`/preamble field in `wps.yaml`.
  - Detect the lane-cycle shape early and suggest a fold.
- **Coverage:**
  - A-10 topology-blind finalize: COVERED (#3874, #3553, #3477).
  - A-15 analysis churn: COVERED (#2493, #2582).
  - A-06/A-07 id grammar and foreign FRs: COVERED (#3519, #3394).
  - A-03 `owned_files: []`: COVERED (#2742).
  - A-01 false lane cycle: PARTIAL (only #428; #3431 closed).
  - A-05 refs copies: PARTIAL (#428, #2066).
  - A-09 transactional: PARTIAL (#4075).
  - A-17 ownership lint: PARTIAL.
  - A-19 plan claims unverified: PARTIAL.
  - **UNCOVERED:** A-08 per-ref status, A-16 notes field, A-34 IC-## warning noise.

### 2.3 Coordination, lanes and status placement (34 + 24 missions)

- **Friction:**
  - Implement's bootstrap commits `kitty-specs/` content onto the lane branch, and the review gate then refuses it. The gate's suggested directory-wide `git restore` would delete matrix files.
  - Status commands run from a lane cwd read the lane's frozen status copy.
  - `single_branch` missions still get lane worktrees, and commits strand on undeclared lanes.
  - `meta.json` `target_branch`, frozen at specify time, beats the checked-out branch, causing "protected main" refusals.
  - `mark-status` has no `--wp` flag, and subtask ids restart at T001 in every WP. Marking WP02 wrote to WP01 and reported success.
  - `safe-commit` accepted and pushed code for a WP still in `planned`.
- **Concerns:**
  - Coord-husk reads fall through to an empty primary (#4966, epic #5002).
  - Lane identity has two uncoordinated sources: static `lanes.json` and dynamic `--base` allocation.
  - Approved lanes are not consolidated before gates run.
- **Notes:** the universal workaround everywhere is `safe-commit --to-branch`. Two missions pivoted to implementing directly on the mission branch.
- **Recommendations:**
  - Resolve every guard against the resolved write branch.
  - Skip lane machinery for lane-less topologies.
  - Route state commands to the planning surface regardless of cwd.
  - Scope remediation text to single files.
- **Coverage:**
  - B-06: COVERED (#3931, #4905, #2570).
  - B-08: COVERED (#2570, #2160).
  - B-09 coord/primary split-brain: COVERED (#2160, #2334, #5025).
  - B-10 coord husk: COVERED (#5002, #4979).
  - B-01/B-02 frozen `target_branch` and protected main: PARTIAL (#3477, #4632).
  - B-11 `single_branch` ignored: PARTIAL, **P1** (#4828).
  - B-05 stale lanes: PARTIAL (#3945, #4889).
  - **UNCOVERED:**
    - B-15 `mark-status --wp` and honest no-ops.
    - B-23 `safe-commit` ignores WP state.
    - B-13 lane identity.
    - B-30 branch-context fork point.

### 2.4 Test environment and interpreters (32 missions)

- **Friction:**
  - Lane worktrees have no `.venv`. Prompts and fixtures hard-code `<worktree>/.venv/bin/*`.
  - The shared editable `.pth` imports primary or foreign `src`.
  - The shared `.venv` drifts from `uv.lock`, and nested `uv run` calls re-sync or downgrade it mid-run.
  - Several `spec-kitty` installs coexist, and `PATH` picks the wrong one.
  - A bare `uv sync` installs neither test nor lint tools. radon is never installed, yet WP validation calls it.
- **Concerns:** tests pass against unfixed source, so "isolation" is an illusion. Stale-venv false reds cost one mission three design phases.
- **Recommendations:**
  - Provision a lane-scoped interpreter at `implement`, or fail loud when `specify_cli.__file__` is foreign.
  - Add a pytest session preflight against `uv.lock`.
  - Use `--no-sync` for nested `uv run`.
  - One documented sync command that yields every tool the gates call.
- **Coverage:**
  - C-05 nested `uv run`: COVERED (#4922, #3950).
  - C-06 slow `test_venv`: COVERED (#3959).
  - C-01 lane interpreter: PARTIAL, **P1**. #2803 frames it as "lane venv missing pytest" when most lanes have no venv at all.
  - C-02 PATH skew: PARTIAL (#3123).
  - C-03 venv drift: PARTIAL (#3123, #4922).
  - **UNCOVERED:** C-04 dev tooling split across extras.

### 2.5 Test-suite reliability and baseline-red churn (34 missions)

- **Friction:**
  - Every mission re-measures pre-existing reds, with 100–1700 s runs, off-by-one narratives and ambiguous "fast/unit" selectors.
  - Concurrent pytest sessions evict each other's `/tmp/pytest-of-<user>` basetemp.
  - Process-global fixture state leaks between suites.
  - Tests that mock the gated seam pass without reaching it.
  - From-import rebinding makes patches inert after moves.
  - Rich/ANSI output breaks `--json` tests.
- **Concerns:**
  - There is no default per-test timeout: loop-driving tests hang. #3143 was closed 2026-09-24 as delivered, but `pytest.ini` still has no `--timeout`, so the close looks wrong.
  - Mutation plugins go obsolete silently.
- **Recommendations:**
  - A machine-readable known-red ledger from the nightly run, plus one canonical baseline selector.
  - A default timeout.
  - An autouse-fixture audit.
  - Injected seams instead of module-attribute patching.
- **Coverage:**
  - C-16 baseline churn: PARTIAL (#4916, #4787, #5044).
  - C-10 concurrent pytest: PARTIAL (#2927, #3978).
  - C-12 vacuous greens: PARTIAL (#2935, #4708).
  - C-13 patch coupling: PARTIAL (#2561).
  - C-11 isolation leaks: PARTIAL, raised by the second opinion (#1931).
  - C-09 timeout: CLOSED-ONLY (reopen #3143).
  - **UNCOVERED:** C-14 mutation evidence rot, C-34 red-first anchor mechanics.

### 2.6 CI gates and quality-gate honesty (26 missions)

- **Friction:**
  - Breaks surface only on CI (11 missions): blast-radius tests outside the `make test-fast` dirs, golden or contract fixtures, and doc-freshness gates. It takes one ~15-minute round per discovery.
  - Routing blind spots produce false greens.
  - `workflow_run` workflows cannot validate their own PR.
  - Auto-generated commit subjects fail commitlint:
    - `Add meta for feature <slug>`, which also uses the prohibited term.
    - `Add scaffold for mission <slug>`.
- **Concerns (verified at HEAD):**
  - No workflow invokes mypy.
  - `ci-router.yml:399` (commit-msg) and `:407` (markdownlint) end in `|| true`.
  - No workflow runs `-m quarantine`.
  - No bandit or pip-audit job, although `docs/configuration/linting-cutoff-policy.md` lists them as blocking.
  - Shard-duration weights fall back to uniform silently.
- **Recommendations:**
  - `make ci-parity --run`, to execute the CI selection for a diff locally.
  - Wire the charter-mandated gates for real.
  - Derive the commitlint ignore list from the generators.
- **Coverage:**
  - C-21 routing blind spots: COVERED (#4708, #3265).
  - C-28 mypy scope: COVERED (#2844, #4188).
  - C-20 CI-only breaks: PARTIAL (#1979, #3943).
  - C-24 `workflow_run`: PARTIAL (#1271).
  - C-17 quarantine: PARTIAL, raised by the second opinion (#4708 doesn't mention quarantine).
  - C-22 scaffold commitlint: CLOSED-ONLY, a residual of #3844.
  - A-23 "feature" commit subjects: PARTIAL (#4837, #2964).
  - **UNCOVERED:** C-23 absent or vacuous mypy/commitlint/security gates (**P1**), D-19 bandit/pip-audit doc claim.

### 2.7 Architectural gates and allowlists (34 missions)

- **Friction:**
  - Allowlists and census rows pinned by `file:line` go red on unrelated drift.
  - Every new test file needs manual registry or baseline rows.
  - Dead-symbol gates impose a sequencing tax: seam-first WPs stay red until a consumer lands, and body-hash keys invalidate on legitimate edits.
  - The archive byte-freeze gate blocks corrections to archived dossiers, although live contracts are still stored in them.
  - The ruff-format-exclude ratchet goes red when a WP incidentally cleans a file it doesn't own.
- **Concerns:**
  - Guards shaped as text or name checks pass while the protected behaviour is gone.
  - The positional-anchor ban only covers files that import the ratchet helpers. `_KNOWN_JOIN_ALLOWLIST` is still pinned by `(Path, int)`.
- **Notes:** hand-written allowlists were repeatedly wrong. Baselines should come from a live census.
- **Recommendations:**
  - A plan-time **gate-impact census**: which gates, allowlists, layer ledgers and shard roots the planned files will trip.
  - A "pending consumer" marker for dead-symbol gates.
  - A canonical home for durable contracts, plus an errata protocol for archived dossiers.
- **Coverage:**
  - D-03 arch suite never run per WP: COVERED (#3943).
  - D-06: COVERED (#4506).
  - D-02: PARTIAL (#2913).
  - D-07: PARTIAL (#4956, #3100).
  - D-08: PARTIAL (#3663).
  - D-09: PARTIAL (#3088).
  - D-01: CLOSED-ONLY, recurred after #2077.
  - D-05: CLOSED-ONLY, recurred after #4315.
  - **UNCOVERED:** D-04 plan-time gate-impact census.

### 2.8 Review loop, acceptance criteria and squads (28 missions)

- **Friction:**
  - Per-WP approval is gated by the mission-wide issue matrix. Every cited `#NNN` needs a terminal verdict, including context-only references.
  - After a reject → fix → approve cycle, stale review artifacts block the next transition.
  - Review-cycle records are thin, for example "Approved by claude" with empty `affected_files`.
  - The CLI says `changes_requested` while doctrine says `rejected`.
  - The pre-review gate's fixed 300 s budget times out on ~2-minute suites.
- **Concerns:**
  - **Vacuous criteria.** In one mission 13 of 29 requirements were passable by a no-op. There were refusal probes without positive controls, and compound fixes proven only as a whole.
  - Specs, rulings and briefs are issued from summaries or stale citations rather than first-hand source (11 missions).
- **Notes:** squads repeatedly paid for themselves (§1.5). Integration or aggregate review on the consolidated tree caught cross-WP defects that per-WP review structurally cannot see.
- **Recommendations:**
  - Label criteria `[build]` or `[ratchet]`.
  - Require positive controls for refusal and absence criteria.
  - Always run the integration gate on the consolidated tree.
  - Re-verify rulings against source.
  - Calibrate planning squads: delta-scoped re-sweeps and a severity floor for nits.
- **Coverage:**
  - E-15/B-17 issue-matrix gate: COVERED (#5007, #5011).
  - E-22 cross-WP escapes: COVERED (#3943).
  - E-21 squad value: COVERED by the charter squad-cadence rule.
  - E-18 thin review evidence: PARTIAL (#3044).
  - E-16 verdict vocabulary: PARTIAL (#3578).
  - E-17/C-19 300 s gate: COVERED or PARTIAL (#3046).
  - A-28 squad over-iteration: PARTIAL (#3925).
  - **UNCOVERED:** E-19 vacuous criteria, E-20 first-hand-source discipline.

### 2.9 Multi-agent orchestration and harness (20 + 17 missions)

- **Friction:**
  - Concurrent agents share one working tree: parallel operations revert edits, and `git add -A` swallows another agent's work.
  - 20+ concurrent pytest runs produce false reds and exhaust disk or tmp quota (ENOSPC/EDQUOT).
  - The harness backgrounds foreground calls at ~600 s whatever `timeout` says; `nohup`/`&` doesn't survive, and subagents strand waiting on their own background work.
  - Worktree isolation fights `single_branch` missions that live in the primary checkout.
  - Implementers were dispatched on the wrong model tier.
- **Concerns:**
  - Dispatch briefs omit load-bearing facts: whether sub-delegation is allowed (two writers committed to one WP), lane-merge state, and venv constraints.
  - Implementers sometimes bypass `agent action implement`, so no lane transition is recorded.
- **Recommendations:**
  - **One writer per checkout.** Concurrent implementers and reviewers each get their own worktree, and `git add -A`/`git stash` are forbidden in shared checkouts.
  - A measurement-discipline tactic: serialized sweeps and mission-base attribution.
  - Required fields in the dispatch-brief template.
  - `run_in_background` plus an in-turn `kill -0` loop.
- **Coverage:**
  - E-23 one writer per checkout: PARTIAL, **P1** (#3129 shadow-workspace design only).
  - E-26 model routing: PARTIAL (#2364 closed; #1049, #4205).
  - E-27 long-run handling: PARTIAL (#2555).
  - E-28 sandbox vs dispatch: PARTIAL (#4122).
  - E-30 bypass: CLOSED-ONLY (#571).
  - **UNCOVERED:** E-24 measurement discipline, E-25 dispatch-brief fields.

### 2.10 CLI ergonomics and honest outcomes (33 missions)

- **Friction:**
  - A "Global asset input changed" RuntimeError race in global asset sync crashes arbitrary verbs as an unenveloped traceback. It appeared in 4 missions, and a retry clears it.
  - `--mission` is required on nearly every verb, even inside a lane worktree.
  - `--json` output is Rich-wrapped on `finalize-tasks` and `record-analysis`.
  - Verbs are slow: 20–60 s repository scans and doctrine loads.
  - There are two `mission create` commands.
- **Concerns:** outcome reporting is dishonest around side effects. `implement --base` exits 1 after creating the workspace. Mutating verbs block for minutes after their useful work lands.
- **Recommendations:**
  - Print and flush the outcome before slow tail work.
  - Infer `--mission` when unambiguous.
  - Emit pure JSON under `--json`.
- **Coverage:**
  - E-01 asset race: COVERED (#4885, #3998, #2627).
  - E-14 slowness: COVERED (#4514, #4620).
  - C-07 fixed CLI cost: COVERED (#4517).
  - E-05 dishonest outcomes: PARTIAL (#4722, #3930).
  - E-06 `--json`: PARTIAL (#2605).
  - E-10 naming: PARTIAL.
  - E-07 slow tails: CLOSED-ONLY (#3680).
  - **UNCOVERED:** E-08 `--mission` inference.

### 2.11 Merge, accept and Zeitgeist (17 missions)

- **Friction:**
  - Merge was refused on stale rejected review artifacts after approval.
  - Acceptance was measured before lane consolidation.
  - `AcceptanceSummary.ok` ignores skipped and blocked checks, the mechanism behind #4891.
- **Concern: Zeitgeist approval moments are dropped.**
  - `spec_kitty_events` `StatusTransitionPayload` raises when `to_lane ∈ {approved, done}` and `evidence is None`.
  - `status/zeitgeist_bridge.py::_normalise_evidence(None)` returns `None`, so an approval recorded only via `--review-result-json` fails validation. It is logged as a warning and never published.
  - Confirmed by reading the code, not reproduced live.
- **Coverage:**
  - B-19 acceptance-matrix lifecycle: COVERED (#4162).
  - B-22 unserialised writers: COVERED (#4887, #4974).
  - B-20 accept/merge fail-open: PARTIAL (#4891, #4934).
  - B-21 gates before consolidation: PARTIAL (#3966).
  - **UNCOVERED:** B-26 Zeitgeist approval drop (**P1**).

### 2.12 Premises, docs, doctrine and charter drift (25 + 19 missions)

- **Friction:**
  - **Stale premises (13 missions).** The issue being worked was already fixed, already retired, or already had an open PR, so scope shrank 50–60% mid-spec.
  - Citations (`file:line`, counts, command names) drift before the mission runs.
  - A git-tracked `.kittify/overrides` plan template outranks the canonical one. It still says "Constitution Check" and cites the deleted `src/doctrine/` path.
  - Shipped `packs/built-in` templates still use "Feature" (`plan-template.md:4`).
  - Generated implement guidance tells agents to run raw `git commit` and to open PRs, which contradicts the charter.
  - `charter context` emits warning noise on every call.
  - The synthesis manifest restamps its version on content-identical runs: the committed manifest says 3.2.6 on a 3.2.7rc1 repo.
  - `implement` preflight reports charter prerequisites one at a time.
- **Recommendations:**
  - A premise re-grounding step in `/specify`.
  - Symbol-anchored citations, plus a citation check in `/analyze`.
  - A parity gate for project overrides.
  - An aggregated preflight.
- **Coverage:**
  - D-17 citation drift: PARTIAL (#2897, #4067).
  - A-21 overrides: PARTIAL, raised by the second opinion (#4611, #4441).
  - A-22 "Feature" in templates: PARTIAL (#2964).
  - D-32 charter noise: COVERED (#4573).
  - D-27 manifest churn: CLOSED-ONLY, recurred after #1912/#1914.
  - D-28 preflight: CLOSED-ONLY, recurred after #2157.
  - **UNCOVERED:**
    - A-20 premise re-grounding.
    - A-24 implement guidance vs. charter.
    - A-25 spec-template sections.
    - D-34 class-level fail-open audit.

### 2.13 Historical: sync-era hangs and residue (≈16 missions, resolved)

- Warnings such as `project sync store is locked` and `layout cutover did not publish` came with hangs (exit 124) in `mission create`, `finalize-tasks`, `record-analysis`, `implement` and `mark-status`. Agents learned never to trust exit codes.
- Clusters A-12, B-14, D-10, D-11 and C-32 are all CLOSED-ONLY, with the code removed. **No action**, apart from confirming that no dossier body-upload remnant survives (per CLAUDE.md, "sync" is dead).

---

## 3. Issue-coverage summary

| Verdict | Clusters | Meaning |
|---|---|---|
| COVERED | 45 | An open issue describes the cause or the improvement. E-21 is covered by the charter rather than an issue |
| PARTIAL | 72 | An open issue covers part of it or something adjacent; the gap is recorded per cluster |
| CLOSED-ONLY | 24 | Only closed issues match. 10 have tracer evidence dated after the close; 3 of those have since been removed from the code |
| UNCOVERED | 24 | Nothing found after title grep, full-text search over all 3,187 issues, and semantic search |

### 3.1 Uncovered gaps, ranked (draft issues are in `coverage-matrix.md`; none were filed)

| ID | Missions | Proposed issue | Pri | Pack tier |
|---|---|---|---|---|
| B-26 | 2 | Zeitgeist: approval moments dropped. `review_result` is not mapped onto the `evidence` the payload requires for approved/done | P1 | product |
| C-23 | 3 | Wire the charter's zero-mypy, commitlint and security-audit gates into live CI (now absent or `\|\| true`) | P1 | in-house |
| A-20 | 13 | `/specify`: premise re-grounding step. Check the cited issue's claim against current code, open PRs and prior missions | P2 | built-in |
| E-19 | 11 | Spec template and review doctrine: `[build]`/`[ratchet]` criterion labels; positive controls for refusal/absence criteria | P2 | built-in |
| D-04 | 8 | Plan phase: gate-impact census for the files a mission will touch | P2 | built-in |
| A-08 | 5 | Requirement lifecycle status (descoped, retired, satisfied-by-omission) honoured by the unmapped-FR gate | P2 | built-in |
| B-15 | 5 | `mark-status`: `--wp` scoping, honest no-ops, terminal `skipped` status | P2 | product |
| B-23 | 4 | `safe-commit` refuses implementation commits for an unclaimed WP | P2 | product |
| E-25 | 4 | Dispatch-brief template: required sub-delegation, lane-merge-state and env fields | P2 | built-in |
| A-24 | 2 | Implement prompt and WP template contradict commit/PR doctrine (raw `git commit`; the WP agent opens the PR) | P2 | built-in |
| B-13 | 2 | Lane identity: `--base` allocation must reuse the WP's `lanes.json` lane | P2 | product |
| E-24 | 2 | Tactic: measurement discipline for multi-agent missions | P2 | internal |
| D-19 | 1 | `linting-cutoff-policy.md` claims bandit and pip-audit block; nothing runs them | P2 | in-house |
| E-20 | 11 | Rulings and briefs re-verify claims against live source before issue | P3 | internal |
| C-04 | 6 | One documented sync command yields every tool the tests and WP gates invoke | P3 | in-house |
| C-34 | 5 | ATDD tactic: prove a red-first anchor is red for the intended reason | P3 | built-in |
| E-08 | 4 | Infer `--mission` from a lane/coord worktree or mission branch | P3 | product |
| A-16, A-25, B-30, C-14, D-22, A-34, D-34 | 1–3 | Notes field in wps.yaml; spec-template sections; fork-point context; mutation-plugin self-proof; tracer layout; IC-## warning; fail-open lint | P3 | mixed |

The pack tier follows the CLAUDE.md rule on who the doctrine governs. **built-in** means it governs every consumer; **internal** means it covers only how the core team works. The planners flagged A-24 in particular as a tier decision for the operator.

### 3.2 The biggest PARTIAL gaps (existing issue is too narrow)

| ID | Missions | Existing | What is missing |
|---|---|---|---|
| A-31 | 25 | #3072 | Tracer fill-rate: seed at create, prompt at handoff, non-blocking check at accept |
| A-19 | 14 | — (squad advice only) | Deterministic existence and re-measurement check for named files, tests and counts at plan/finalize |
| D-17 | 13 | #2897, #4067 | Symbol-anchored citations plus an `/analyze` citation check |
| C-01 | 13 | #2803 | Most lanes have **no** venv; fail loud on a foreign-`src` import; stop hard-coding `<worktree>/.venv` (P1) |
| C-16 | 12 | #4916, #5044 | Nightly-published machine-readable known-red ledger and a canonical baseline selector |
| C-20 | 11 | #1979, #3943 | `make ci-parity --run` to execute the CI selection locally |
| E-23 | 8 | #3129 | "One writer per checkout" orchestration rule and guard (P1) |
| B-11 | 6 | #4828 | `single_branch` topology must never allocate or require lanes (P1) |

### 3.3 Regressions and residuals after close (new issues or reopen)

- **#3143, reopen:** closed 2026-09-24 as delivered, but `pytest.ini` still has no per-test `--timeout` (C-09).
- **#2077 → D-01:** the positional-anchor ban has a scope hole (`_KNOWN_JOIN_ALLOWLIST`).
- **#4315 → D-05:** gate-registration toil still recurs (tracer evidence to 2026-09-22).
- **#3844 → C-22:** the `Add scaffold for mission <slug>` auto-commit still fails commitlint.
- **#1912 / #1914 → D-27:** synthesis-manifest version churn.
- **#2157 → D-28:** one-at-a-time preflight.
- **#4864 → C-25:** silent uniform fallback for shard weights.
- **#571 → E-30:** no orchestrator-side check that a dispatched WP drove the implement transitions.

### 3.4 Close candidates (acted on in §6)

- **#2493:** items 1–3 are fixed or superseded. One residual remains live: `plan.md` NEEDS-CLARIFICATION removal re-stales the analysis. Set to `triage:needs-revision` for the owner to re-scope or split.
- **#3394:** fixed on main (declared-id scoping plus `TestDeclaredVsCitedRequirements`). **Closed as completed.**
- **#3398:** the forward fix is on main. 192 historical reports still leak absolute paths, and sweeping them collides with the archive byte-freeze gate. Routed to a human.

---

## 4. Suggested sequencing (planner view)

1. **Quick, high-value fixes.** Each is a single-surface change:
   - B-26: Zeitgeist evidence mapping.
   - C-09: reopen #3143 and add a default timeout.
   - C-22 and A-23: generator-derived commitlint ignore list, and drop "feature" from commit subjects.
   - B-15: `mark-status --wp`.
   - B-23: `safe-commit` WP-state check.
2. **Make gates honest.** C-23 and D-19 (mypy, commitlint, security or amend the doc), then C-17 (quarantine lane) and C-14 (mutation lane).
3. **Environment isolation, which unblocks trust in every test result:**
   - C-01: lane interpreter or fail-loud check.
   - C-03: `uv.lock` preflight.
   - C-02: PATH skew guard.
   - E-23: one writer per checkout.
   - After those, C-16's known-red ledger becomes cheap and ends the per-mission baseline churn.
4. **Planning doctrine and templates** (`packs/built-in`; regenerate the pack graph after editing):
   - A-20: premise re-grounding.
   - A-19 and D-17: verify plan claims and citations.
   - D-04: gate-impact census.
   - E-19: criterion labels and positive controls.
   - A-08 and A-16: requirement status and notes.
   - A-24: prompt/charter contradiction.
5. **Topology correctness** (with epics #5001/#5002): B-11 `single_branch`, B-13 lane identity, B-01/B-02 frozen `target_branch`, A-01 false lane cycle.
6. **Tracer practice:**
   - A-31, A-32 and D-22: one location, one writer, prompted appends.
   - Once fixed, re-run this recon; §5 of this report explains why the sample is uneven.

---

## 5. Method and honest limits

- **Pipeline:**
  1. `spec-kitty dispatch` opened the Op.
  2. Four recon delegates (`retrospective-facilitator`) each read a chronological slice of tracers and emitted structured items with checked `file:line` evidence.
  3. Five `planner-priti` delegates each clustered one theme group and searched issues: a title grep over all 818 open issues, a local full-text search over all 3,187 issues, semantic search, and reading candidate issue bodies.
  4. One second-opinion `planner-priti` delegate adversarially re-checked every UNCOVERED and CLOSED-ONLY verdict. It raised 5 of them to PARTIAL and lowered none.
- **Rate limits.** GitHub semantic search was heavily rate-limited while the five coverage delegates ran concurrently. The local full-text corpus and the second-opinion pass compensate, but a paraphrased duplicate could still hide behind an UNCOVERED verdict.
- **Liveness.** Most "still live at HEAD" claims were checked by reading code or grepping, not by running the CLI. I personally re-verified:
  - C-23: no mypy in any workflow; `|| true` on commit-msg and markdownlint.
  - C-17: no quarantine run.
  - C-09: no `--timeout` in `pytest.ini`.
  - B-26: the validator/normaliser mismatch.
- **Uneven sample.** 25 missions have thin tracers, so implement-phase friction is under-captured for them. Some themes were spread by inherited "watch-lists" between briefs, so mission counts overstate independent recurrence for coord and venv themes.
- **Unresolvable references.** `SK-NN` ids point to a workspace-local ledger that isn't in this repository.
- **Dates.** Mission dates come from ULID or `meta.json` `created_at`. Individual tracer entries can be days later, which affects the "post-dates the close" regression judgements.
- **Judgement calls.** Clustering and severity are judgement calls. Each item sits in at most one cluster. Groups B and D set aside about 44 design-only or already-resolved notes that need no action; groups A, C and E clustered every item. The per-group JSONL and `.md` files record the mapping so it can be audited.

---

## 6. Tracker actions taken (2026-09-26)

The operator asked for the report's recommendations to be actioned and for the repository's issue-triage approach to be run on the result. The work ran under Op `01M3EP3N34E82WGTBXBN656Y9H` and followed the `issue-triage-state-machine` and `tracker-organisation-workflow` procedures and `docs/development/how-to/manage-issue-tracker.md`.

**Reopened.** #3143 (default per-test timeout). The 2026-09-24 grooming close cited #3144, the PR that created the gap. Since `ci-quality.yml` was retired, no per-test `--timeout` runs anywhere: not locally, not in the Linux module shards, not on Windows. It is now in milestone **4.0.0 release scope** at the operator's request. Triage moved it to `status:ready`, because moving the default into `pytest.ini` is now the only option that covers every surface.

**Filed.** 40 issues, #5060–#5100 (#5066 is an unrelated PR): all 24 UNCOVERED clusters, the 8 recurrences found after a close, and the 8 largest PARTIAL gaps. Every issue carries its tracer evidence, the coverage check, the gap and a proposed scope. The cluster-to-issue mapping is in the **Tracker action** column of [`coverage-matrix.md`](coverage-matrix.md).

**Triaged.** Four profile-loaded planner-priti delegates handled the issues. For each one they read the whole issue, set one native type and one state, and bounded the claim against `origin/main` (`43520a31`). Each issue then got either a durable agent brief (current and desired behaviour, contracts, acceptance criteria, out of scope; no file paths) or a "Triage: ready-for-human" note listing the decision options. They also checked priority against the P0 calibration, fixed domain labels, and removed the retired `enhancement` label.

| State | Issues |
|---|---|
| `status:ready` (agent brief posted) | 25 |
| ready-for-human (`status:triage` + options comment) | 12 |
| needs-info (`status:triage` + `triage:repro-needed`) | 3 |

Several premises were narrowed during triage, where part of the claim was already fixed at HEAD: #5064, #5068, #5071, #5073, #5075, #5077, #5086 and #5094. Two severities were adjusted:

- **#5081** (Zeitgeist approval drop): lowered to P2. The drop is real on `agent status emit --review-result-json` and the orchestrator-api transition. `move-task` always attaches evidence, and the local log stays correct.
- **#3143**: kept at P1.

**Homed.** The tracker guide treats a source-based grouping as a catch-all root, so the temporary epic #5059 did not stay the parent. Each issue was re-parented under an existing functional epic, 21 in all, listed below. #1931 was at GitHub's 100-sub-issue cap, so #5082 went under #1795 and #5086 under #3260, which is itself a child of #1931. #5059 was then turned into a closed, reference-only meta-tracker.

**Close candidates and duplicates.**

- #3394 was closed as completed.
- #2493 was set to `triage:needs-revision`; see §3.4.
- #3398 was routed to a human.
- #2803 and #5096 were judged related but not duplicates. #5096 owns the lane-interpreter root cause; #2803 keeps the pre-review `no_coverage` diagnostic, whose second cause is a hard-coded `tests.architectural` import in consumer repos. Both were cross-linked.

**Open for the operator.**

- **P0 candidates** (escalation is an operator decision):
  - #5100: `single_branch` missions still get lane worktrees; code lands on undeclared lanes.
  - #5099: the shipped implement-review skill tells agents to `git add -A` in shared checkouts.
  - #5096: lane tests import the primary checkout's `src`.
- **Ready-for-human decisions**, 12 of them: #5062, #5063, #5065, #5069, #5070, #5074, #5075, #5076, #5078, #5096, #5097, #5100.
- **A label-vocabulary conflict.** The retired `type:*` family still carries `type:decision`, which the fleet dispatcher reads as "skip". The triage procedure's *ready-for-human* state therefore has no sanctioned label. These issues are held back from the fleet only by staying in `status:triage`.

| Issue | Cluster | Type | Pri | Triage state | Functional parent |
|---|---|---|---|---|---|
| #5060 | A-20 | Task | P2 | status:ready | #1799 |
| #5061 | E-19 | Task | P2 | status:ready | #1931 |
| #5062 | E-20 | Task | P3 | ready-for-human | #1799 |
| #5063 | D-04 | Feature | P2 | ready-for-human | #3448 |
| #5064 | C-04 | Task | P3 | status:ready | #1932 |
| #5065 | A-08 | Feature | P2 | ready-for-human | #1676 |
| #5067 | B-15 | Bug | P2 | status:ready | #2017 |
| #5068 | C-34 | Task | P3 | status:ready | #1931 |
| #5069 | B-23 | Bug | P2 | ready-for-human | #1619 |
| #5070 | E-08 | Feature | P3 | ready-for-human | #1801 |
| #5071 | E-25 | Feature | P2 | status:ready | #3809 |
| #5072 | A-16 | Feature | P3 | status:ready | #1676 |
| #5073 | A-25 | Feature | P3 | status:ready | #1676 |
| #5074 | B-30 | Feature | P3 | ready-for-human | #1619 |
| #5075 | C-14 | Task | P3 | ready-for-human | #1931 |
| #5076 | C-23 | Bug | P1 | ready-for-human | #1928 |
| #5077 | D-22 | Task | P3 | status:ready | #1799 |
| #5078 | A-24 | Bug | P2 | ready-for-human | #4441 |
| #5079 | A-34 | Bug | P3 | status:ready | #1676 |
| #5080 | B-13 | Bug | P2 | needs-info | #1795 |
| #5081 | B-26 | Bug | P2 | status:ready | #3890 |
| #5082 | E-24 | Task | P2 | status:ready | #1795 |
| #5083 | D-19 | Bug | P2 | status:ready | #3891 |
| #5084 | D-34 | Task | P3 | status:ready | #1928 |
| #5085 | D-01 | Bug | P3 | status:ready | #1931 |
| #5086 | D-05 | Task | P3 | status:ready | #3260 |
| #5087 | E-07 | Bug | P3 | needs-info | #4514 |
| #5088 | C-22 | Bug | P3 | status:ready | #1932 |
| #5089 | D-27 | Bug | P2 | status:ready | #2519 |
| #5090 | E-30 | Task | P3 | status:ready | #1619 |
| #5091 | D-28 | Bug | P2 | needs-info | #3897 |
| #5092 | C-25 | Bug | P2 | status:ready | #4437 |
| #5093 | A-31 | Feature | P3 | status:ready | #1799 |
| #5094 | A-19 | Task | P2 | status:ready | #1676 |
| #5095 | D-17 | Task | P2 | status:ready | #849 |
| #5096 | C-01 | Bug | P1 | ready-for-human | #2624 |
| #5097 | C-16 | Feature | P2 | ready-for-human | #3260 |
| #5098 | C-20 | Feature | P2 | status:ready | #1932 |
| #5099 | E-23 | Task | P1 | status:ready | #1795 |
| #5100 | B-11 | Bug | P1 | ready-for-human | #1619 |
