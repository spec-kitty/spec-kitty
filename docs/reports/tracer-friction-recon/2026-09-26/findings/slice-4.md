---
doc_status: active
updated: '2026-09-26'
---

# Recon — slice4 (24 older missions, 2026-06-27 → 2026-07-31)

**Profile applied:** `retrospective-facilitator` (builtin; directives 003, 010, 018). I worked in its capture/propose mode: every finding has provenance (`file:line`), proposals are recorded as data and nothing is auto-applied, and the work was read-only. I also loaded the `review` charter context (Terminology Canon, Regression Vigilance, Pre-existing Failure Reporting). The profile's boundary says it runs only at mission terminus. All 24 missions here are closed or historical, so this pass fits that boundary.

**Deliverable:** `recon-slice4.jsonl` has 274 items: 155 friction, 54 note, 50 concern, 15 recommendation. It covers all 24 missions. Every `evidence` path and line number was machine-checked against the file (0 bad).

---

## Per-mission digest

### doctrine-built-in-seam-consolidation-01KYW3TX
- [CONCERN] The three topic tracers are 4-line seeds and hold no findings: `tracers/arch-ratchet.md:3`, `tracers/seam-authority.md:1`.

### doctrine-delivery-activation-01KYQVQK
- [FRICTION] `bare python`/`pytest` inside a lane imports the PRIMARY checkout's src. The workaround is `uv run`: `tracer-tooling-friction.md:19`
- [FRICTION] A full `tests/architectural/` run breaks the agent session, so only targeted node-ids are possible: `tracer-tooling-friction.md:18`
- [FRICTION] `test_every_load_delivery` goes false-red from ambient `context-state.json`. Fixed in-mission as FR-009: `tracer-tooling-friction.md:17`
- [FRICTION] The org monthly spend limit terminated subagent dispatches: `tracer-tooling-friction.md:20`
- [NOTE] The plan named the wrong channel (`resolve_context`). There the check is vacuously green or permanently red; the post-plan squad moved the assertion to the profile channel: `tracer-design-decisions.md:31`
- [NOTE] A WP marked "parallel" collided at hunk level with the core walk and was split into IC-06a/06b (#3075): `tracer-design-decisions.md:36`

### write-side-seam-matrix-tracer-01KYP3MH
(The only tracer-related file is the WP10 prompt that builds a tracer writer. It is not a tracer log.)
- [FRICTION] An agent that appends tracers from a lane commits `kitty-specs/` on the lane branch, and that blocks `move-task` (#2980/#2549). WP10 adds a routed `tracer-append`: `tasks/WP10-tracer-writer.md:58`
- [CONCERN] `agent:""` silently blanks attribution because the reducer only guards `is not None` (#2960): `tasks/WP10-tracer-writer.md:61`
- [FRICTION] The baseline capture recorded "no JUnit XML artifact produced by the scoped run" as a failure: `tasks/WP10-tracer-writer/baseline-tests.json:14`

### journal-project-consent-3030-01KYKWQS (the richest set: 1421 lines)
- [FRICTION] A lane was cut from a stale base that predates the mission's own acceptance pins. The result is a false 0-failure baseline: `tracer-tooling-friction.md:3`
- [FRICTION] The `--to done` gate needs every issue-matrix verdict to be terminal. So no WP can reach `done`, and neither `--force` nor `--done-override-reason` bypasses it: `tracer-tooling-friction.md:12`
- [FRICTION] WPs added after planning have no `lanes.json` entry. The staleness gate then advises rebasing a different WP's lane. The pre-review gate prints "no_coverage … skipping the gate cheaply", so two confidentiality WPs got no gate coverage while the output read like a pass: `tracer-tooling-friction.md:139`, `:153`
- [FRICTION] The editable-install `.pth` hard-codes the main checkout path. Worktree isolation "looks performed" but imports the live tree: `tracer-tooling-friction.md:437`
- [FRICTION] Shared-tree multi-agent hazards:
  - `git add -A` swallowed another agent's edits (`:47`).
  - 20+ concurrent pytest runs gave false reds from port bands and leaked daemons (`:315`).
  - A `reset_adapters()` teardown broke later suites' positive controls (`:730`).
- [CONCERN] The filename-token conftest guard can neutralise pins, and three tests depend on that gap. Fixing the guard would tempt reverting T028: `tracer-tooling-friction.md:104`, `:665`
- [REC] Five mutation-plugin "rot modes"; plugins must assert they took effect: `tracer-tooling-friction.md:203`, `:586`. Also: "a shared working tree is not a measurement substrate" (`:359`).
- [NOTE] #3030 and saas#585 pinned the root cause to the wrong file. The real drain was `delivery/dispatcher.py`: `tracer-design-decisions.md:6`

### lifecycle-gate-execution-context-01KY72GQ
- [NOTE] Three of the four P0s in the brief (#2160, #2367, #1834, #2573) were already delivered, and scope was rewritten to about half: `tracers/approach.md:20`
- [FRICTION] #2795: the claim writes the VCS lock into PRIMARY `meta.json`, and the ref-advance dirty scan then refuses. The reported cause was refuted: `tracers/design-decisions.md:35`
- [FRICTION] An implementer confined to a lane cannot commit tracer or baseline artifacts. The files were left uncommitted for the operator to migrate: `tracers/tooling-friction.md:20`
- [FRICTION] `mission create` never materialised the coord worktree. `status.events.jsonl` sat untracked on primary for a whole planning cycle, and `doctor coordination` would have caught it but is never run automatically: `tracers/tooling-friction.md:66`
- [FRICTION] The procedure says `traces/` but the missions use `tracers/`: `:48`. Also, `test_tid251_enforcement` needs `python -m ruff` inside `.venv`: `:53`
- [FRICTION] The ADR README invocation drifted: bare scripts need `PYTHONPATH=.`, and the freshen step does not refresh the docs index (#2887): `:60`

### synthesized-drg-stale-refresh-01KXN8KZ
- [FRICTION] The `synthesized_drg: stale` deadlock came from comparing mtimes. It was fixed with a content hash (#2681): `tracer-approach.md:10`
- [FRICTION] `finalize-tasks` rejects any `kitty-specs/` path in `owned_files`, and empty ownership fails `compute_lanes`. A WP whose deliverable is a doc therefore cannot declare it: `tracer-tooling-friction.md:10`
- [FRICTION] A `single_branch` mission still got four materialised lane worktrees, which were left orphaned: `tracer-tooling-friction.md:63`
- [FRICTION] A shared test fixture encoded a pre-fix schema and broke three CI shards after merge; the local sweeps missed it (#2732): `tracer-tooling-friction.md:140`
- [FRICTION] Single-file and full-package `mypy --strict` runs disagree about casts: `tracer-tooling-friction.md:109`. Tests without `repo_root=` polluted `.kittify/`: `:87`
- [CONCERN] Activation changes are invisible to the content hash until a recompile: `tracer-approach.md:85`

### test-suite-friction-remediation-01KXDKBX
- [FRICTION] F12: `move-task` run from a lane commits status onto the lane branch while printing "Using planning repo". The next call then hard-blocks on its own guard: `tracer-tooling-friction.md:43`
- [FRICTION] The mirror case: a transactional status read from a lane sees a stale event log and rejects "planned -> for_review": `tracer-tooling-friction.md:45`
- [FRICTION] Every new test file triggers two gate-coverage baseline refreezes (#2616; gc2b re-scoped to orphans). New arch files also need a shard-map row: `tracer-tooling-friction.md:7-8`, `:24`
- [FRICTION] Fresh lane venvs lack pytest/ruff/mypy (`uv sync` prints "Audited 54 packages"). Arch gates are vacuous under `.worktrees/`: `tracer-tooling-friction.md:10-11`, `:51`
- [FRICTION] F13: about 81 pre-existing failures from Rich ANSI splitting and `--json` output that won't decode: `tracer-tooling-friction.md:46`
- [CONCERN] Static grep cannot see list-driven identity assertions: 0 of 45 delegates were deletable, and 34 remain deferred behind the frozen #2531 guard: `tracer-design-decisions.md:56`, `tracer-tooling-friction.md:50`
- [NOTE] The operator's hypothesis that ratchet and parity suites are net friction is catalogued with keep/retire verdicts (#2071): `tracer-design-decisions.md:14`

### coord-shadows-arm-closeout-01KXAST2
- [CONCERN] All three tracers have empty implementation and close-out sections: `tracers/claim-liveness.md:17`
- [CONCERN] `_infer_subtasks_complete` fails open at 4 callers. The #2511 door patch must only be removed after `status_transition.py:444` is fixed: `tracers/emit-class-closure.md:3`
- [CONCERN] Two divergent subtask-row walkers exist (break vs continue): `tracers/subtask-row-canon.md:7`

### relocation-hardened-dead-code-scanners-01KX958P
- [CONCERN] The tracers are seed-only: `tracers/relocation-key.md:12`
- [CONCERN] The location-keyed dead-symbol allowlist is not tolerant of relocation, and a frozen collision set re-blinds the gate: `tracers/live-collision-classifier.md:8`
- [FRICTION] About 40 intentional `warnings.warn` diagnostics pollute the suite output. The built-in `terminology-guard.toolguide.yaml` fails the schema and is silently skipped: `tracers/warning-remediation.md:7`, `:17`

### content-address-ratchet-allowlists-01KX8M4D
- [CONCERN] The tracers are unchecked watch-lists: `tracers/descriptor-mechanism.md:8`
- [CONCERN] Positional `file:line` anchors in arch allowlists need a standing ban meta-guard (#2077): `tracers/standing-metaguard.md:5`
- [REC] Use one shared content-descriptor resolver for all gates: `tracers/descriptor-mechanism.md:5`

### coord-authority-trio-degod-01KX7094
- [FRICTION] Module-attribute monkeypatches (about 14) blocked moving `collect_feature_summary`. Its free variables resolve through the defining module's globals: `tracers/acceptance.md:14`
- [FRICTION] Source-inspection tests pin exact literal text and `except X:` substrings inside `implement()`: `tracers/implement.md:77`
- [FRICTION] A line-pinned arch seed (`implement.py:88`) had to be re-pinned after drift. This recurred; see #2450: `tracers/implement.md:91`
- [FRICTION] A monkeypatch target went inert after an extraction: `tracers/implement.md:98`. A lane-branch tracer commit blocked `move-task`: `:116`

### doctrine-template-asset-kinds-01KX2YQ7
- [CONCERN] A new ArtifactKind or NodeKind silently misses switch/map/comprehension sites, so a totality guard is needed: `tracer-tooling-friction.md:6`, `tracer-design-decisions.md:66`
- [CONCERN] ASSET paths had no containment (`../../etc/passwd`), and the containment helper already exists in at least 5 copies: `tracer-design-decisions.md:38`
- [FRICTION] Doctrine changes trip CI-only shards: `tracer-tooling-friction.md:9`
- [NOTE] The post-spec and post-plan squads reversed several decisions and caught the wrong validator file: `tracer-design-decisions.md:50`

### mission-resolver-port-01KX1C05
- [FRICTION] Duplicated floor constants across gate files, and a single drain drops two counters: `tracer-tooling-friction.md:12-15`
- [FRICTION] The layer ledger is keyed by subpackage, not by direction: `tracer-tooling-friction.md:31`
- [FRICTION] Plan censuses undershot about 2-3x, and many cited line numbers had drifted: `tracer-tooling-friction.md:35`, `:64`
- [CONCERN] The S1192 stamp literal appears 18 times with 4 redundant constants; about 18 isoformat copies remain in non-owned files: `tracer-tooling-friction.md:41`

### coord-primary-partition-lock-01KWZ46V
- [FRICTION] Tracers were seeded late because /specify, /plan and /tasks never prompt for them: `tracer-tooling-friction.md:5`
- [FRICTION] The dispatch surface has no default for implementer/reviewer model routing. Implementers were sent to opus, the operator had to correct it twice, and the `--agent` model string is cosmetic: `tracer-tooling-friction.md:9`
- [FRICTION] A claim silently failed to write the WP prompt but still took the lease: `:19`. Re-claiming under a different identity is a silent no-op: `:24`

### census-freshness-loc-insensitive-01KWVD6Y
- [FRICTION] `uv run python -m pytest` rebuilds the editable install on every call (~75s vs ~44s): `tracer-tooling-friction.md:10`
- [FRICTION] The setup-plan post-plan hook fires on the scaffold before the plan is written: `:13`. The harness passes workflow `args` as a JSON string: `:5`
- [FRICTION] `record-analysis`/`merge` refuse on unrelated dirty state, and the squash-merge reverted `issue-matrix.md` to its template: `:16`, `:21`

### relocate-saas-sync-flag-to-core-01KWQ3RV
- [FRICTION] Churn in the charter synthesis-manifest trips the `move-task` guards: `tracers/tooling-friction.md:16`
- [CONCERN] A live stability contract lives in an archived mission folder, which conflicts with immutability: `tracers/tooling-friction.md:16`
- [REC] Ratchet an emptied allowlist to `== 0`: `tracers/design-decisions.md:20`

### refactor-stable-gate-substrate-01KWK3FY
- [FRICTION] `git checkout <branch> -- kitty-specs/<mission>/` into the coord worktree clobbered `status.events.jsonl`: `tracers/tooling-friction.md:8`
- [FRICTION] All 31 quarantined tests fail on CI while 16 pass locally: `tracers/design-decisions.md:56`
- [NOTE] Seed/line-derived gate identity is content-following and fails both halves of NFR-001, so the gate moved to a frozen content key: `tracers/design-decisions.md:25`

### tasks-py-degod-wave2-01KWH9EQ
- [FRICTION] Targeted per-WP suites let 4 mission-introduced arch REDs accumulate unseen until the closure sweep: `tracers/approach.md:33`
- [FRICTION] mypy's per-module quarantine makes relocated bodies fail `--strict`: `tracers/tooling-friction.md:21`. The census treats `dumps` as a write token, so it silently re-classifies writes: `:25`
- [FRICTION] A quarantined literal-pin test rotted while dark: `tracers/tooling-friction.md:33`
- [REC] Operator ruling: remove the LOC-ceiling gate, delete positive literal scans, and prefer negative/behavioural invariants: `tracers/design-decisions.md:118`, `:127`

### tasks-py-degod-01KWF08S
- [FRICTION] The merge review-artifact gate blocks when the latest review-cycle file is still `rejected`, because approvals are recorded as status transitions and not as artifacts: `tracers/tooling-friction.md:44`
- [FRICTION] The coord worktree holds the authoritative acceptance/issue/review artifacts, so editing the primary copy does nothing: `:46`
- [FRICTION] Typer drift in the shared venv (0.26.8 vs the locked 0.24.2) broke the golden harness: `:18`. The FR scanner tokenizes prose: `:22`
- [FRICTION] Tracers were written retroactively at close: `tracers/approach.md:4`

### doctrine-catfooding-2196-01KWE16N
(The only tracer-related file is WP04, which authors the tracer procedure itself.)
- [NOTE] The `mission-tracer-files` procedure and templates were created, turning #2095 into doctrine: `tasks/WP04-mission-tracer-files.md:84`
- [CONCERN] The procedure makes tracers optional, "absence does not block acceptance", which explains the stubs: `:143`. It prescribes `traces/`, while missions use `tracers/`: `:140`

### reliability-papercut-sweep-01KWD0V5
- [FRICTION] The mission reproduced its own target bugs live: DIRTY_WORKTREE on bookkeeping (#2251), gate reads split between coord and primary, and REJECTED_REVIEW_ARTIFACT_CONFLICT (#2275): `tracers/tooling-friction.md:37-48`
- [FRICTION] Removing a fallback left stale sibling tests that surfaced one per ~15-min CI round, costing about 1 hour: `tracers/tooling-friction.md:59`
- [FRICTION] `branch-context` reported a stale per-clone `primary_branch`: `:16`
- [NOTE] The squad cadence, especially the SSOT/architecture lens, caught wrong owned files, a missed 4th gate and a fakeable DoD. The tracer rates it high ROI: `tracers/approach.md:37`

### sync-strict-json-auth-01KWA6KN
- [FRICTION] The catch-all `classify_sync_error` reported a benign "no Private Teamspace" skip as `server_auth_failure`: `tracers/approach.md:9`
- [FRICTION] DIR-012 assignee cannot be set from a fork (#2254): `tracers/tooling-friction.md:5`

### common-docs-structural-move-01KW3SBK
- [FRICTION] The "analysis-staleness dance": `mark-status` checkboxes change the `tasks.md` hash, which forces a re-record and commit before every WP claim: `tracers/tooling-friction.md:91`
- [FRICTION] A rejected WP's lane collects `kitty-specs/` status chores. That creates a Catch-22 between the `move-task` pre-flight, the pre-commit guard and diff-compliance, and it needed `--no-verify` (#2160/#1862): `:66`
- [FRICTION] Flat missions still need `lanes.json`, and finalize collapses lanes into cycles: `:33`. Flattening lost the status bootstrap, and no flatten command exists: `:43`
- [FRICTION] The occurrence map pointed at a gitignored generated file: `:10`. The diff-compliance gate classifies at file granularity: `:23`

### common-docs-consolidation-01KW3Q6M
- [FRICTION] A concurrent mission's loop ran `git checkout` on the shared primary checkout mid-task: `tracers/tooling-friction.md:7`
- [FRICTION] Any artifact change stales the analysis, and an idempotent `record-analysis` cannot mint a fresh commit: `:17`
- [FRICTION] Tracers kept on the planning branch fight the WP and analysis guards and were squash-clobbered at merge. Their home should follow coord authority (#2095/#2160): `:18-19`
- [FRICTION] `--json` output is Rich-wrapped: `:11`. `spec-kitty next` reports not_started for a fully tasked mission: `:13`. `create_intent` is not prompted: `:9`

---

## Cross-mission themes in this slice

Ranked by how many missions hit each theme; item counts are from the JSONL.

1. **tracer-process-itself: 18 missions, 21 items.**
   - Many tracers were seeded and never back-filled, or written only at close. Examples: coord-shadows, relocation-hardened, content-address, doctrine-template-asset, mission-resolver, refactor-stable, reliability, doctrine-built-in, and the `workflow.md` tracer in coord-authority.
   - Root causes stated in the tracers:
     - The procedure marks tracers optional (`doctrine-catfooding…/WP04:143`).
     - /specify, /plan and /tasks never prompt for them (`coord-primary-partition-lock/tracer-tooling-friction.md:5`).
     - The file location never converged: `traces/` vs `tracers/` vs root `tracer-*.md` (`lifecycle-gate/tracers/tooling-friction.md:48`).
     - Tracers placed on the planning branch or in lanes collide with the guards (`common-docs-consolidation/tracers/tooling-friction.md:18`).
   - Recommendations:
     - A routed `tracer-append` command (#2980/#2549/#2960; `write-side…/WP10:69`).
     - A topology-dependent tracer home (#2095/#2160).
     - A light non-empty check at accept.

2. **Lane/coord/primary split-brain (coord-branch-worktree + status-lanes-move-task): 12 and 7 missions, 34 items combined. This is the highest-severity cluster, with 17 items rated high.**
   - `move-task` run from a lane reads a stale event log and rejects legal transitions (`test-suite-friction…:45`, `common-docs-structural…:53`).
   - Writes land on the wrong branch (F12, `test-suite-friction…:43`).
   - `kitty-specs/` changes committed on a lane block `move-task` (at least 6 missions).
   - Gates read coord while tools write primary (`reliability…:40`, `tasks-py-degod…:46`).
   - The coord worktree was never materialised (`lifecycle-gate…:66`).
   - Stated root cause: status and lifecycle artifacts are not routed unconditionally through the coordination/primary partition, and lane worktrees carry a `kitty-specs/` copy. Cited: #2160, #2275, #2980, #2549, #1862, #2795.

3. **test-suite-speed-flakes: 14 missions, 31 items.**
   - Shared-tree contention and port/daemon false reds (`journal…:315`).
   - Fixtures that change global state (`journal…:730`).
   - Source-inspection and monkeypatch-location tests that block refactors (`coord-authority…/implement.md:77`, `acceptance.md:14`).
   - Rich/ANSI `--json` output breaking about 81 tests (`test-suite-friction…:46`).
   - A shared fixture encoding a schema broke three CI shards (`synthesized-drg…:140`).
   - Quarantined tests rotting while dark (`tasks-py-degod-wave2…:33`).
   - Suites that hang with no default timeout (`journal…:394`).
   - Recommendations: fan out coding but serialise sweeps; measure in pinned worktrees; use behavioural invariants instead of source-text pins; restore global state rather than reset it.

4. **finalize-tasks-planning: 13 missions, 24 items.**
   - The analysis-report staleness dance: hashes include checkbox and tracer changes, and an idempotent `record-analysis` cannot refresh (`common-docs-structural…:91`, `common-docs-consolidation…:17`, `tasks-py-degod…:27`).
   - `owned_files` rules: test files are omitted, `kitty-specs/` paths are forbidden, and `create_intent` is not prompted.
   - Lane cycles on flat missions.
   - Plan censuses undershoot 2-3x.
   - The FR scanner tokenizes prose.
   - Recommendations: hash only task definitions; `record-analysis --force`; validate owned-file globs; add a `finalize --no-commit` mode.

5. **arch-gate-allowlists: 12 missions, 31 items.**
   - Line-anchored allowlist seeds drift (`coord-authority…/implement.md:91`, `tasks-py-degod…:14`).
   - Gate-coverage baselines refreeze on every test add (#2616).
   - Coupled or duplicated ratchet floors.
   - Name-shaped guards miss new shapes (`journal…/design-decisions.md:308`).
   - Mission-introduced arch REDs pile up under targeted-only runs.
   - Recommendations: content-addressed keys (#2077, #2546); re-scope to genuine orphans; operator ruling (`tasks-py-degod-wave2…/design-decisions.md:118`) that ratchets tied to code shape are friction.

6. **test-env-venv-install: 10 missions, 14 items.**
   - Stated root cause: the editable-install `.pth` points at the primary checkout, so lanes and worktrees silently import PRIMARY src (`journal…:437`, `test-suite-friction…:11`, `refactor-stable…:10`).
   - Test and lint tooling sit in extras, so a fresh lane venv lacks them.
   - The venv drifted from `uv.lock` (typer/click, Rich).
   - `uv run` rebuilds the package on every call (~75s).
   - Recommendations: `PYTHONPATH=$WT/src` or a per-worktree venv; put test/lint in the default dev group.

7. **docs-drift (10 missions)** and **tracker-issue-hygiene (6 missions).**
   - Issues or briefs had stale premises that the code had already delivered or mis-pinned (#1716, #2160/#2367/#1834/#2573, #2295, #3030).
   - The ADR README and CLAUDE.md fallback notes were stale.
   - Recommendation: re-ground every brownfield brief against the code before specifying.

8. **ci-gates-routing: 9 missions, 10 items.**
   - Shards that only run on CI (terminology, docs-freshness, functional merge/lanes shards) bite after push, one CI round at a time (`reliability…:59`).
   - Local and CI quarantine outcomes diverge (`refactor-stable…:56`).
   - Recommendation: run the CI-only functional shards locally before opening the PR.

9. **merge-accept-pipeline: 8 missions, 11 items.**
   - Rejected review-cycle artifacts block merge after approval (`tasks-py-degod…:44`, `reliability…:44`, #2275).
   - Squash-merge reverts `issue-matrix.md` and tracers.
   - Dirty-tree refusals on the tool's own bookkeeping (#2251).
   - A textually clean merge still regressed at runtime.

10. **subagent-orchestration: 7 missions, 11 items.**
    - Shared-checkout clobbering (`git add -A`, concurrent `git checkout`).
    - No default for model routing (`coord-primary-partition-lock…:9`).
    - The spend cap killed dispatches.
    - Recommendation: one worktree or clone per concurrent agent.

11. **Smaller themes:**
    - doctrine-drg-packs: 6 missions. Kind-totality, containment and schema-skip.
    - cli-ergonomics: 6. `--json` output is not pure JSON, `next` state is disconnected, misleading hints.
    - governance-overhead: 6. This theme is mostly positive: squads are rated high ROI.
    - dead-code-legacy-residue: 8.
    - review-loop-verdicts: 5.
    - ruff-mypy-format: 4. Scope-dependent `--strict` results, per-module quarantine.

## Honest limits

- Four "missions" have little or nothing to extract:
  - doctrine-built-in-seam-consolidation has only 4-line stubs.
  - write-side-seam-matrix-tracer and doctrine-catfooding-2196 have WP prompts about building tracer tooling, not tracer logs.
  - coord-shadows, relocation-hardened and content-address have planning-seed hypotheses only.
  - For all of these, what I extracted is planning-time concerns, not observed friction.
- I did not open spec.md or retrospective.yaml files, and I did not verify whether cited issues (#2160, #2275, #2616, #2887 and others) are now closed or fixed. Friction from July 2026 may already be resolved, for example F12 `move-task` or the analysis-staleness dance.
- Theme assignment is my judgement. Coord-branch-worktree and status-lanes-move-task overlap heavily, which is why I report them combined in theme 2.
- Severity is inferred from each tracer's own emphasis and impact, not from a shared rubric.
- Several friction items repeat across missions as "inherited watch-lists", for example F5 (bare python imports primary) and F6 (lane `kitty-specs/`). Counting missions per theme therefore partly measures how widely a known issue was propagated, not how often it independently recurred.
