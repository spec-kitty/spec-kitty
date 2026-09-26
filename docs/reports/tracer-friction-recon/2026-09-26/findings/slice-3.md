---
doc_status: active
updated: '2026-09-26'
---

# Recon: slice3 (12 missions, 33 tracer files, ~7,600 lines read in full)

**Profile applied:** `retrospective-facilitator` (builtin; role facilitator). Directives 003, 010 and 018 were resolved from the profile. `charter context --action review` was loaded in compact mode; the Terminology Canon and DIR-032 were applied to vocabulary. I applied the initialization as written: structured findings with provenance on every finding, and proposals kept as data. I also applied the avoidance boundary: I did not implement or edit anything, and I did not auto-apply doctrine, DRG or glossary changes. This was a READ-ONLY pass. The only writes were `recon-slice3.jsonl` (229 items), this file, and scratch helpers under `s3/`.

Every item in the JSONL has a `kitty-specs/<mission>/<file>:<line>` pointer. I checked each pointer against the file: the line exists and was spot-read to confirm it matches the finding.

Counts by category: friction 126, concern 59, note 29, recommendation 15.

---

## Per-mission digest

### cascade-org-inert-01M07E9P (15 items)
- [NOTE] The spec squad found 6 defects in the first draft. Two of them were sev-4 fixes that were wrong: the FR-002 swap was a no-op because the CLI truncates `org_roots[0]` upstream. See `tracer-approach.md:5`.
- [CONCERN] FR-004 was retired mid-spec because open PR #3401 already fixed the same lines. No pre-spec check for open PRs had caught this. See `tracer-approach.md:28`.
- [FRICTION] `finalize-tasks` reported the retired FR-004 as unmapped. `parse_requirement_ids_from_spec_md` regex-scans the whole spec and has no "retired" concept (SK-51). See `tracer-tooling-friction.md:8`.
- [FRICTION] `agent tasks mark-status` prints success and writes nothing. The real cause is a swallowed `RuntimeError: body outbox writes require the project_only layout`, which is sync residue in `sync/body_queue.py`. Three lanes reproduced it. See `tracer-tooling-friction.md:9` and `:11`.
- [FRICTION] WP03's `lanes.json` write_scope left out a file that its own task body required. The commit guard only warns. See `tracer-tooling-friction.md:10`.
- [FRICTION] The branch-context resolver has no notion of a stacked-PR base, so the drift is recorded only in spec prose. See `tracer-tooling-friction.md:7`.
- [REC] Prove each half of a compound fix independently red-first, so an inert partial fix cannot pass. See `tracer-design-decisions.md:29`.

### modular-per-package-ci-01M025GV (7 items)
- [FRICTION] Extracting one CI job into a reusable `uses:` workflow tripped 6 arch CI-model guards from one root cause. The guards read the caller's inline steps. See `tracers/design-decisions.md:10`.
- [CONCERN] WP01 declared 3 guard files, but 6 were affected. The planning docs also named a test file that does not exist. See `tracers/design-decisions.md:31`.
- [NOTE] Design B, a parse-time splice in `_gate_coverage.py`, turned all guards green. The WP was honestly held `in_progress` while guards were red. See `tracers/design-decisions.md:52` and `:57`.
- [FRICTION] The full `tests/architectural/` suite is policy-deferred to CI, so guard changes cannot be fully verified locally. See `tracers/design-decisions.md:47`.

### bare-prose-requirements-uncounted-01KZYV3C (30 items; the densest tooling-defect record in the slice)
- [FRICTION] `_parse_requirement_refs_from_tasks_md` treats citations as declarations and has no DOTALL multi-line capture. It was never patched with #3395's fix. As a result, `finalize-tasks` writes miscredits by default. See `tracer-tooling-friction.md:9` and `:14`.
- [FRICTION] No `owned_files` value can satisfy both validators for a code-free planning WP: the `kitty-specs/` path is banned, and `[]` means no manifest, so `compute_lanes` raises. See `tracer-tooling-friction.md:10`.
- [FRICTION] Mutate-before-fail showed up three ways: `finalize-tasks` wrote frontmatter and false events on a failed run; its auto-commit missed events because of an ordering bug; and `implement` wrote `meta.json` vcs fields before failing. See `tracer-tooling-friction.md:10`, `:15` and `:17`.
- [FRICTION] `compute_lanes` produced a **cyclic** `depends_on_lanes` graph from an acyclic WP graph, and `finalize-tasks` still reported success. See `tracer-tooling-friction.md:16`.
- [FRICTION] Diverged coord and lane lineages blocked `implement`. No CLI can flatten a `coordination_branch` (SK-01, #900/#903). A stale lane *branch*, not only its worktree, must be deleted, and `--base` does not override it. Every mission-branch status write makes open lanes stale. See `tracer-tooling-friction.md:17`, `:19`, `:21` and `:25`.
- [FRICTION] A shadowing global `~/.local/bin/spec-kitty` (rc1) hid the `.venv` rc2 install. The shipped `plan-template.md` contains the prohibited term "Feature". See `tracer-tooling-friction.md:8` and `:11`.
- [FRICTION] The issue-matrix guard blocks every WP approval and has no `--force`. A `deferred` row needs a `#NNN` or `Follow-up:` token. See `tracer-tooling-friction.md:24`.
- [CONCERN] WP frontmatter `dependencies` drifted from `tasks.md` prose in several WPs, so the gate would not have blocked early claims. See `tracer-design-decisions.md:22`.

### org-pack-authoring-diagnostics-01KZY463 (21 items)
- [FRICTION] `spec-commit`, `plan --json` and `tasks --json` all refused with "protected branch main" while HEAD was a feature branch. The root cause is `_resolve_mission_target_branch` reading a stale `meta.json` (SK-12/13); its own docstring names the bug. See `tracer-tooling-friction.md:7` and `:74`.
- [FRICTION] `finalize_tasks` silently dropped every `SC-00x` requirement ref. See `tracer-tooling-friction.md:116`.
- [FRICTION] The `--base` lane allocator minted `lane-b` for WP01, which collided with the static `lanes.json` `lane-b`. A live concurrent WP02 session ended up sharing the same worktree. See `tracer-tooling-friction.md:204`.
- [FRICTION] The `analysis_report_required` gate gave a false positive: the charter content hash was unchanged, but a metadata timestamp bump made it look stale. Three corroborations. See `tracer-tooling-friction.md:290`.
- [FRICTION] `tracer-append` writes to a split-brain `traces/` file instead of the mission's `tracer-tooling-friction.md`. See `tracer-tooling-friction.md:340`.
- [FRICTION] `move-task` and `status emit` return `PROTECTED_BRANCH_REFUSED` (SK-21). The narrowed blast radius is the `to_lane` commit. See `tracer-tooling-friction.md:384` and `:460`.
- [FRICTION] SK-14: the `charter synthesize` detector misfires and downgrades versions. It was resolved only by a concurrent sibling run mutating shared `.kittify/charter`. See `tracer-tooling-friction.md:493`.
- [CONCERN] There were 15+ cumulative sightings of the SK-12/14/21 family across 4 WPs. See `tracer-tooling-friction.md:442`.

### mission-type-guard-registry-01KZY2FG (25 items)
- [FRICTION] SK-09: `specify` mints no branch. SK-11: `safe-commit` demands HEAD be `main` while `spec-commit` refuses `main`. The two refusals contradict each other. See `tracer-tooling-friction.md:7` and `:22`.
- [FRICTION] On LANES topology, `commit_router.py` routes bookkeeping to `main`, and `policy.py` refuses protected branches unconditionally. This blocked `finalize-tasks` and every WP02 claim. See `tracer-tooling-friction.md:114` and `:607`.
- [FRICTION] The `record-analysis` DIRTY_WORKTREE preflight blocks on any dirty path anywhere in the repo, with no escape hatch. The stash/pop workaround was used three times. See `tracer-tooling-friction.md:190`.
- [FRICTION] SK-20: CLI version skew (PATH 3.2.5 vs `.venv` 3.2.6rc2) hashed `charter.md` vs `charter.yaml`, which produced a false stale-analysis result. See `tracer-tooling-friction.md:469`.
- [FRICTION] The implement preflight chains gates one at a time. `charter synthesize` downgraded the manifest version. See `tracer-tooling-friction.md:357`.
- [FRICTION] A citation-only rebase refresh re-staled the byte-hash analyze gate. See `tracer-tooling-friction.md:233`.
- [FRICTION] Harness limits: one subagent never returned, and several agents hit the org monthly spend limit. See `tracer-tooling-friction.md:41`.
- [FRICTION] A tracer entry was drafted from a stale lane-worktree copy of the tracer file. See `tracer-tooling-friction.md:654`.

### org-activation-scan-dirs-01KZY1PT (18 items)
- [NOTE] `_org_scan_dirs` scanned a `built-in/` layout that no org pack uses. The fix was additive and non-recursive, to keep parity with the live loader. See `tracer-approach.md:5`.
- [FRICTION] With `single_branch` topology, `target_branch` was the protected `main`. There was also no git identity, and `safe_commit` said only "git commit failed". See `tracer-tooling-friction.md:31` and `:42`.
- [FRICTION] `software-dev` specify scaffolds an empty 0-byte `spec.md` with no template. See `tracer-tooling-friction.md:17`.
- [FRICTION] A foreign `FR-021` in prose was flagged unmapped (#3394). The operator authorized a spec edit forced by the tool. See `tracer-tooling-friction.md:113`.
- [FRICTION] `finalize-tasks --target-branch` does not move the commit, but it does mutate WP frontmatter and `lanes.json` before failing. See `tracer-tooling-friction.md:224`.
- [FRICTION] A line-pinned `_KNOWN_JOIN_ALLOWLIST` would have red-flagged the fix. No planning artifact listed it. See `tracer-tooling-friction.md:392`.
- [CONCERN] A reviewer subagent ran concurrently in the same `single_branch` checkout, and a `git stash` caught the reviewer's edits. See `tracer-tooling-friction.md:372` and `:406`.
- [FRICTION] `analysis-report.md` records absolute machine paths (#3398). See `tracer-tooling-friction.md:423`.

### up-mission-type-seam-01KZY1JB (27 items)
- [FRICTION] `spec-commit --help` still promises coord "materialize-then-retry" for spec-kind artifacts, but that path is gone. The refusal ignores live HEAD (SK-12). See `tracer-tooling-friction.md:38` and `:86`.
- [FRICTION] When `wps.yaml` is present, `finalize-tasks` ignores its `requirement_refs`, so all 13 FRs showed as unmapped. See `tracer-tooling-friction.md:174`.
- [FRICTION] The `lanes.json` generated by `finalize-tasks` is cyclic (lane-a↔lane-b and lane-a↔lane-c). `compute_lanes` never validates cycles; its docstring calls this "best-effort". See `tracer-tooling-friction.md:217`.
- [FRICTION] The `diff-cover --include 'src/doctrine/*'` filter is a filesystem glob. It silently excludes nested files, so the "critical-path, enforced" 90% gate gives almost no signal for `src/doctrine` and `src/charter`. See `tracer-tooling-friction.md:502`.
- [FRICTION] Arch gates tripped on "safe" deletions: `test_no_dead_symbols` failed on a facade re-export and `test_golden_count_ban` also fired. The plan had asserted deletions could only help. See `tracer-tooling-friction.md:380`.
- [FRICTION] An unowned test pinned the pre-fix bug as correct behavior. Tests coupled to `sys.modules` mocks broke on a correct refactor. See `tracer-tooling-friction.md:410` and `:566`.
- [FRICTION] Host contention from parallel missions: coverage runs took 26-27 min (2.5-3x normal) and a timing test flaked. Per-file and batch mypy disagree. See `tracer-tooling-friction.md:649` and `:688`.
- [CONCERN] A tracer and a WP prompt had authorized hand-building a workspace. Adversarial review caught it. See `tracer-tooling-friction.md:249`.

### ci-scoping-gate-reliability-01KZP80D (12 items)
- [FRICTION] CI silently skipped the corpus suites on data-only PRs (#3008). This was a two-gate structure that could not be found without a trace. See `tracer-tooling-friction.md:7` and `:9`.
- [FRICTION] Arch-invariant gates run only in CI's integration-core-misc job, so local runs miss them. See `tracer-tooling-friction.md:12`.
- [CONCERN] GitHub `on.paths` does not support brace expansion, so the brace-form fix would have been inert (squad blocker B1). See `tracer-squad-findings.md:7`.
- [REC] Use a `@pytest.mark.corpus` marker so suites don't run twice. Diff-scoped docs checks should fail closed from `base.sha`, and a corpus completeness invariant should be added (#3147, #3265 fold candidate). See `tracer-squad-findings.md:17`, `:28`, `:35` and `:53`.

### assertive-test-suite-sanitation-01KZME3P (12 items)
- [FRICTION] Parallel pytest workers deadlock on `.pytest_cache/spec-kitty-test-venv.lock` during the editable install (#3283). See `tracer-tooling-friction.md:5`.
- [FRICTION] Collecting 37,444 nodes takes 94-110s. CLI commands take 20-60s. The mutation CI job is disabled. See `tracer-tooling-friction.md:6`, `:7` and `:8`.
- [CONCERN] Healthy baseline: 24 failed and 2 errors (#3284, #2782). See `tracer-tooling-friction.md:10`.
- [FRICTION] PRIMARY vs COORD split-brain: review cycles were duplicated on both, and `cutover-guard` disagreed with where cutover placed seeds. See `tracer-tooling-friction.md:11` and `:12`.

### verdict-seam-boundary-hardening-01KZG179 (11 items)
- [FRICTION] `spec-commit` returned "unchanged" on a real diff. The `safe_commit` stash dance mangled the index. The pre-commit hook pinned a dead agent-worktree venv interpreter. See `tracers/tooling-friction.md:7` and `:8`.
- [FRICTION] Rebasing the mission branch stranded the coord branch on its old base; the fix was `rebase --onto` plus a merge. See `tracers/tooling-friction.md:12`.
- [FRICTION] The pre-review gate has a hardcoded 300s timeout. The tracer says it was skipped with the sync-residue `SPEC_KITTY_SYNC_DISABLE`, but per CLAUDE.md that variable was retired from this gate in #3980, so the tracer's workaround is now stale. See `tracers/tooling-friction.md:14`.
- [FRICTION] The issue-matrix gate runs on every WP approval, and finalize clobbers the matrix. Implementers hit their turn limit on the slow `move-task`. See `tracers/tooling-friction.md:13` and `:16`.
- [CONCERN] Census-fixture staleness appeared only on the consolidated tree (closure-cascade demotion). Per-lane runs cannot see it. See `tracers/design-decisions.md:36`.

### tracker-egress-refusal-3108-01KYWF1R (19 items; sync-era, now largely residue)
- [CONCERN] The issue premise (#3108, #3030 E20) was measured false. The mission was reframed on evidence gathered with positive controls. See `tracer-evidence-base.md:10`.
- [CONCERN] The squad measured three vacuous-green traps. The house test pattern patches out `_build_engine`, the gated seam, so the gate's bind count was 0 while 519 tests passed. The default `external_authoritative` mode never pushes. The arming gate turned every refusal test green. See `tracer-squad-findings.md:31`, `:50` and `:72`.
- [CONCERN] `tracker bind` and `unbind` erase a committed refusal key, which silently fails open. See `tracer-squad-findings.md:169`.
- [REC] File the incidental `sync_publish` AttributeError bug. Patch mocks at the deciding module, because imports rebind by value. See `tracer-evidence-base.md:452` and `:468`.

### egress-refusal-consolidation-3110-01KYW895 (32 items; sync-era)
- [FRICTION] A user-site editable `.pth` made bare imports load a *different* checkout that another mission was editing. The machine has only Python 3.14 while CI runs 3.11/3.12, and `Path.exists()` EACCES behavior diverges between them. One trivial test cost 69s. See `tracer-evidence-base.md:9`, `:61` and `:66`.
- [FRICTION] CI routing gaps: a tracker-only PR does not run the tracker guard. The 4 SaasClient construction sites sit in `cli/`, so a `cli`-only diff skips the SaaS guard. Joining `core_misc` alone would be worse than `run_all`. See `tracer-squad-findings.md:737` and `:2243`.
- [CONCERN] The seam-allowance gate only checks that the name appears as a substring. The integration-boundary gate is not transitive: 9 CORE modules already reach sync. Autouse conftests fabricate consent. See `tracer-squad-findings.md:825`, `:805` and `:687`.
- [CONCERN] The spec grew 526→1571 lines with four copies of the same content across 3 review rounds. The escalation gate tripped, and the operator accepted the fixes without review. See `tracer-squad-findings.md:1691` and `:1851`.
- [CONCERN] By-value import binding (rot-mode 5) and guard predicates that live inline in tests made mutations inert or unkillable. See `tracer-squad-findings.md:2087` and `:2141`.
- [NOTE] Undeclared no-op criteria fell from 45% to 18% to 6% across rounds once the `[build]`/`[ratchet]` labels were introduced. See `tracer-squad-findings.md:1612`.

---

## Cross-mission themes in this slice (ranked by mission count, then item count)

### 1. review-loop-verdicts: 9 missions, 20 items. Squads catch inert or vacuous fixes and criteria.
- Evidence: cascade `tracer-approach.md:5` (the drafted fix was a no-op). bare-prose `tracer-approach.md:5` (the arbiter found a sev-5 inert gate that the squad missed). egress-3110 `tracer-squad-findings.md:482` (SC-001 was passable with zero production change). tracker-3108 `tracer-squad-findings.md:50` (the gate was never entered).
- Stated root causes: specs are written from plausible code reading without positive controls, and acceptance criteria assert absences that already hold.
- Recommendations: prove each half of a compound fix independently; bind a positive control to the same fixture; use `[build]`/`[ratchet]` labels; persist squad verdicts as files (assertive `:14`); don't use flag-threaded strict/tolerant functions (guard-registry DD-2).

### 2. coord-branch-worktree: 8 missions, 27 items. The stale `meta.json.target_branch` family dominates.
- Evidence: org-pack `tracer-tooling-friction.md:7` and `:74`; guard-registry `:22` and `:114`; up-seam `:86`; scan-dirs `:224`; assertive `:9`; bare-prose `:17`, `:19`, `:21` and `:25`; verdict-seam `:12`.
- Stated root causes:
  - `_resolve_mission_target_branch` (`core/paths.py:717`) and the `commit_router` placement read `meta.json` instead of live HEAD (SK-09/11/12/13).
  - `policy.py` refuses protected branches regardless of topology, even for LANES.
  - `specify` mints no primary branch.
  - The dynamic lane-slot allocator is not coordinated with the static `lanes.json`.
  - Lane branches go stale after mission-branch status writes.
  - No CLI exists to flatten or re-strand the coord branch.
- Recommendations: fix target resolution to honor live branch context. Make the protection policy topology-aware. Have `specify` mint the mission branch. Have `--base` reuse the lane_id assigned in `lanes.json`. Add a sanctioned flatten/re-strand command. Merge the mission tip into lanes so they keep it as an ancestor. Until then, `safe-commit --to-branch` is the de-facto universal workaround (used in 6+ missions).

### 3. finalize-tasks-planning: 8 missions, 25 items.
- Evidence:
  - The whole-document `FR-\d+` regex (#3394, SK-51) broke 4 missions: cascade `:8`, scan-dirs `:113`, up-seam `:103`, and bare-prose's sibling parser `:9`.
  - Cyclic lane graphs: bare-prose `:16`, up-seam `:217`.
  - Silent ref loss: org-pack `:116` (dropped `SC-*`), up-seam `:174` (`wps.yaml` refs ignored).
  - Mutate-before-fail or commit-ordering bugs in 4 missions: bare-prose `:10` and `:15`, org-pack `:116`, guard-registry `:100`, scan-dirs `:224`.
  - Planning-artifact `owned_files` gap: bare-prose `:10`.
  - Frontmatter deps drifting from prose: bare-prose DD `:22`.
- Recommendations: scope requirement parsing to the requirements table and add a retired/citation convention; validate cycles after lane collapse; make finalize-tasks transactional; read `requirement_refs` from `wps.yaml`; warn on unknown prefixes; validate deps against prose; cross-check write_scope against the file list in each task body.

### 4. test-suite-speed-flakes: 7 missions, 18 items.
- Evidence: assertive `:6` (37k nodes, 94-110s collection); egress-3110 `tracer-evidence-base.md:61` (69s for one test) and `:87` (no global `--timeout`); up-seam `:649` (host contention, 2.5-3x slower); verdict-seam `:14` (300s pre-review gate); tracker-3108 `:50` (mocked chokepoint, vacuous green); egress-3110 `:2087` (by-value import rebinding).
- Recommendations: add `--timeout` to addopts; make the gate timeout env-tunable; test contracts rather than mock shapes; hoist guard predicates so mutation plugins can reach them; patch every name a symbol is bound to.

### 5. docs-drift: 6 missions, 13 items.
- Evidence: stale `spec-commit --help` (up-seam `:38`); line-number drift after rebases (guard-registry DD `:149`, egress-3110 `:1521`); absolute paths in `analysis-report.md` (#3398, scan-dirs `:423`, up-seam `:362`); a P0 boundary with no ADR (egress-3110 `:101`); "engagement" missing from the glossary (`:420`).
- Recommendations: use citations anchored to symbols; write ADRs for structural boundaries; emit repo-relative paths.

### 6. arch-gate-allowlists: 6 missions, 13 items.
- Evidence: a line-pinned `_KNOWN_JOIN_ALLOWLIST` (scan-dirs `:392`); `test_no_dead_symbols` hit on facade re-exports and seam-first WPs (up-seam `:380` and `:541`); census staleness visible only on the consolidated tree (verdict-seam DD `:36`); a substring-only seam gate (egress-3110 `:825`); the non-transitive integration boundary (`:805`); arch gates missing from the local fast tier (ci-scoping `:12`).
- Recommendations: during planning, grep `tests/architectural` for line-pinned allowlists covering files being moved; run arch gates before claiming a deletion is safe; run the live census on the consolidated tree before merge.

### 7. cli-ergonomics: 6 missions, 11 items.
- Evidence: misleading exit-1 after the side effect had already succeeded (org-pack `:183`); `next --json` shows clear while `implement` refuses (guard-registry `:457`); the `record-analysis` DIRTY_WORKTREE scope is too broad (3 missions); CLI invocations take 20-60s (assertive `:7`).

### 8. test-env-venv-install: 6 missions, 8 items.
- Evidence: a shadowing global `spec-kitty` binary (bare-prose `:8`); CLI version skew corrupting hashes (SK-20, guard-registry `:469`); a user-site editable `.pth` leaking across checkouts (egress-3110 `:9`); `uv sync` banned because it destroys hand-built venvs (bare-prose `:22`); an empty fresh-worktree venv (up-seam `:344`); the `.pytest_cache` venv lock (#3283).

### 9. subagent-orchestration and tracker-issue-hygiene: 6 missions each.
- Subagent orchestration: shared-checkout concurrency among lane implementers and reviewers (org-pack `:535`, scan-dirs `:372`); briefs that declared blockers resolved without reproducing them (guard-registry `:615`); implementers hitting the turn limit on slow `move-task` (verdict-seam `:16`).
- Issue hygiene: issue premises measured false (#3108, #3387, #3396 bad SHA, #3216 already resolved). Recommendation: verify fold and issue premises against live code before scoping.

### 10. status-lanes-move-task: 5 missions, 10 items.
- Evidence: `mark-status` reports success but performs no write (cascade `:9` and `:11`); SK-21 `PROTECTED_BRANCH_REFUSED` on `move-task` and `status emit` (org-pack `:384`); the issue-matrix gate on every WP approval with no force option, clobbered by finalize (bare-prose `:24`, verdict-seam `:13`); failed allocation leaving a WP `blocked` that needs `--force` to recover (bare-prose `:21`).

### 11. ci-gates-routing: 4 missions, 17 items (concentrated in the CI and egress missions).
- Evidence: reusable-workflow extraction blinding the guards (modular-ci `:10`); corpus suites skipped on data-only PRs (#3008); guards routed by package name rather than by where construction sites live (egress-3110 `:737`); single-glob membership turning half the routing blind (`:2243`); routing that cannot be verified before merge (`:2382`).

### 12. charter-context-activation: 3 missions, 9 items.
- Evidence: analyze freshness gated on a metadata timestamp or byte-hash (org-pack `:290`, guard-registry `:233`); chained `charter sync`→`synthesize` preflight (guard-registry `:357`); SK-14 synthesize version downgrade.

### Smaller themes
- doctrine-drg-packs: 4 missions.
- dead-code-legacy-residue: 4 missions. The two sync-era egress missions are now themselves residue; sync body_queue still sits on the `mark-status` path.
- templates-prompts: 3 missions. Empty software-dev spec scaffold; "Feature" in `plan-template.md`; missing `create_intent` in the schema.
- governance-overhead: 3 missions.
- agent-harness-sandbox: 3 missions. Spend limit; dead hook interpreter; no git identity.
- tracer-process-itself: 2 missions. `tracer-append` split-brain; stale lane copies of tracer files.
- One mission each: sonar-coverage (`diff-cover` glob), windows-cross-os (3.14 vs 3.11), merge-accept-pipeline (stale acceptance row after descoping).

---

## Honest limits
- **Ledger IDs are not resolvable here.** SK-01…SK-51 live in a workspace-local `SPEC-KITTY-LEDGER.md` that is not in this repo. I recorded them in `cited_issues` as given; they are not GitHub issue numbers. The tracers themselves say to cite upstream #-numbers such as #3394 and #3398 instead.
- **I did not check whether any cited defect has since been fixed on main.** Examples: the `_resolve_mission_target_branch` fix, the #3394 parser scoping, `compute_lanes` cycle validation, the #3398 absolute paths. Severity reflects impact at the time the tracer was written.
- **Two missions are about the sync transport, which has since been deleted:** tracker-egress-refusal-3108 and egress-refusal-consolidation-3110. Most of their consent-chain findings are probably moot now. I tagged them `dead-code-legacy-residue` where relevant, but did not re-verify them against current code. The same applies to verdict-seam's `SPEC_KITTY_SYNC_DISABLE` workaround, which is now stale per #3980.
- **Two tracers are atypical.** modular-per-package-ci has only a design-decisions tracer, with no friction or approach tracer. egress-3110's "evidence-base" file calls itself orchestrator scratch notes, not a deliverable.
- **Item granularity is a judgment call.** Recurring defect families, such as the stale-target_branch refusals, are split per mission and per surface rather than deduplicated, so the per-theme item counts overweight missions with verbose tracers. Mission counts are the more reliable ranking signal.
- **Some root causes are the tracer author's inference, not a traced fact.** Examples are the analyze-gate timestamp theory at org-pack `:311` and the sync-store lock warnings in cascade. I recorded them as stated.
