---
doc_status: active
updated: '2026-09-26'
---

# Recon: slice 2 — tracer-file retrospective (17 missions)

**Profile applied:** `retrospective-facilitator` (loaded via `spec-kitty agent profile show`). I followed its avoidance boundary: I read and extracted only, made no edits to the repo and applied no doctrine. Its directive refs 003, 010 and 018 shaped the method: every finding cites a `file:line` as provenance, and proposals are recorded as data, not applied. The review-action charter context was also loaded (`charter context --action review`). From it I used the Terminology Canon and the Pre-existing Failure Reporting Rule to attribute baseline reds and the "feature" wording.

**Deliverables:** `recon-slice2.jsonl` has 220 items: 122 friction, 71 note, 22 concern and 5 recommendation. By severity, 47 are high, 93 medium and 80 low. Every `evidence` line number was checked programmatically and points at a non-blank line of the real file.

Mission-local ledger IDs (SK-NN) refer to `SPEC-KITTY-LEDGER.md`. One mission recorded that this file does not exist in the checkout.

---

## Per-mission digest

### cross-os-primitive-unification-01M2T1CM (planning-only tracers)
- [FRICTION] Every `mission list --json` / `charter context` call emits `LegacyOrgPackDoctrineKeyWarning` for the legacy `doctrine.org.packs` key — `tracer-tooling-friction.md:8`
- [CONCERN] The post-spec reviewer found a critical scope miss: the `asset_preparation.py` raw msvcrt/fcntl locking, where #4703 originated, was missing from the FRs. Without it SC-003/005 could not be reached — `tracer-design-decisions.md:62`
- [CONCERN] The issue text undercounted the forks (3 safe-delete copies plus 1 frozen migration; 4 `_is_windows` sites where the issue said 2; 5 more OS-detection sites found after tasks) — `tracer-design-decisions.md:52`
- [NOTE] Faking `os.name="nt"` flips pathlib to WindowsPath and crashes pytest, so OS detection must go through the patchable `kernel.paths.is_windows` — `tracer-design-decisions.md:37`
- [REC] Scope new ban gates to `src/` only. Copying the clock-ban template's `(src,tests,scripts)` scan would flag about 92 legitimate hits as red — `tracer-design-decisions.md:84`
- [NOTE] The implementation sections of all three tracers are still `_(append as encountered)_` — `tracer-approach.md:35`

### blocked-wp-unblock-path-01M29093 (1 tracer only)
- [FRICTION] `ensure_global_agent_commands()` raises "Global asset input changed" when a session in a sibling clone regenerates the shared `~/.kittify/cache` at the same time. Its root cause is a fail-closed check against a non-error. Suggested fix: regenerate instead of raising (#2627) — `tracer-tooling-friction.md:5`
- [FRICTION] The allocator writes `base_branch`/`base_commit` into the WP01 prompt without committing it. The next WP's allocation then refuses with "Planning artifacts not committed" — `tracer-tooling-friction.md:12`
- [FRICTION] The default `coord` topology is heavyweight for a 2-WP bug fix — `tracer-tooling-friction.md:18`
- [NOTE] The tracer set is incomplete: approach and design-decisions files are absent.

### runtime-advance-guard-topology-wp-completion-01M1W6VZ
- [FRICTION] `cd` into a lane worktree persists across harness calls. Later `spec-kitty` state commands then write silently to the worktree's frozen status copy and report OK — `tracer-tooling-friction.md:113`
- [FRICTION] Gate counts taken on the mission branch before lane consolidation looked like a regression, and no tool warns that approved lanes are unconsolidated — `tracer-tooling-friction.md:94`
- [FRICTION] `mark-status` has no `--wp` flag, and colliding subtask IDs forced `--force` on every transition (SK-135) — `tracer-tooling-friction.md:68`
- [FRICTION] `finalize-tasks` is topology-blind: its `branch_strategy` prose contradicts lanes.json (SK-133) — `tracer-tooling-friction.md:81`
- [FRICTION] `gh pr view --json files` silently truncates at 100 files and nearly hid the evidence that justified the scope narrowing (#3923) — `tracer-tooling-friction.md:29`
- [FRICTION] The file-level disjointness rule for `owned_files` forced an oversized WP with 12 subtasks and about 827 lines — `tracer-design-decisions.md:86`
- [CONCERN] Once merged, the fix newly enables the per-WP completion check on every coord mission currently in implement. Operators should spot-check them — `tracer-approach.md:61`
- [CONCERN] Draft PR #3923 degrades on `MissionSelectorAmbiguous`, while this mission hard-blocks on the same exception. The two policies contradict each other — `tracer-design-decisions.md:325`


### event-push-watch-channel-01M1K6W2
- [FRICTION] The shared workspace `.venv` editable install pointed at lane-a, so a test run from lane-b would import another lane's code without error — `tracer-tooling-friction.md:88`
- [FRICTION] `safe-commit` hard-errors on `kitty-specs/` edits from a lane unless `--to-branch <lane>` is passed. Its suggested remedy ("checkout the mission branch") is wrong for a lane worktree — `tracer-tooling-friction.md:55`
- [FRICTION] Registering a new top-level command also needs `_completion_manifest.json` regenerated. That file is not in `owned_files`, and only the integration tier catches the omission — `tracer-tooling-friction.md:111`
- [FRICTION] pytest marks stack, so a function-level `integration` mark on a module marked `fast` gets collected by the wrong CI tier. The fix is one file per marker set — `tracer-tooling-friction.md:129`
- [FRICTION] The process-global `_SEED_COUNTER` in `tests/status/conftest.py` breaks byte-identical comparisons between two seed passes — `tracer-tooling-friction.md:153`
- [FRICTION] diff-cover `--cov=<fs path>` silently collects nothing; it needs a dotted module path — `tracer-tooling-friction.md:47`
- [FRICTION] The literal-substring feature-alias guard trips on help text that says "never --feature" — `tracer-tooling-friction.md:103`

### spdd-reasons-activation-split-brain-01M1K6VN (friction tracer only)
- [FRICTION] Concurrent pytest runs across lanes evict each other's `/tmp/pytest-of-<user>/pytest-NNN` directories, causing 66 cascading errors. The fix is to pass `--basetemp` (#3283) — `tracer-tooling-friction.md:244`
- [FRICTION] tmpfs `/tmp` hit its quota (EDQUOT) under concurrent suites, and the session's Bash/Write tools were offline for 10–15 minutes — `tracer-tooling-friction.md:262`
- [FRICTION] The pre-review gate has a fixed 300s budget, but a subset of its scope alone takes about 634s. It timed out twice and needed `--skip-pre-review-gate` — `tracer-tooling-friction.md:441`
- [FRICTION] `status emit --to for_review` on a `planning_artifact` WP looks for a `lane-planning` branch that is never created (SK-152 class) — `tracer-tooling-friction.md:469`
- [FRICTION] The orchestrator dispatched three WP agents before running analyze, so all three were BLOCKED on a missing `analysis-report.md` — `tracer-tooling-friction.md:65`
- [FRICTION] `tasks.md` has no field for free-form notes, and `requirement_refs` cannot express "satisfied by omission" — `tracer-tooling-friction.md:41`, `:135`
- [FRICTION] The dispatch wrapper named `merge_target_branch` for `--to-branch`, but the flag needs the current lane branch — `tracer-tooling-friction.md:168`
- [REC] Diff "did I cause this" against the mission's true base commit, not your own earlier commit — `tracer-tooling-friction.md:435`

### dispatch-dry-run-route-only-01M1HKV2
- [FRICTION] The harness's worktree-isolation sandbox refuses git commands and Write/Edit against the shared checkout, which contradicts the dispatch instruction. The workaround was to draft in the scratchpad and `cp` into place — `tracer-tooling-friction.md:7`
- [FRICTION] `finalize-tasks` rejects `kitty-specs/` paths in `owned_files`, though plan.md's Blast Radius listed one without warning — `tracer-tooling-friction.md:48`
- [FRICTION] `record-analysis` silently persists `verdict: unknown` with exit 0 when the carrier frontmatter is missing — `tracer-tooling-friction.md:78`
- [FRICTION] The archive byte-freeze gate overruled the plan and two reviewers, so the contract doc moved to the live dossier — `tracer-design-decisions.md:54`
- [CONCERN] The SK-08 rerank changes routing mid-mission for auto-routed calls. This is accepted and not mitigated — `tracer-design-decisions.md:44`

### design-phase-orchestrator-api-01M1HE6M
- [FRICTION] WP01 never moved past `planned` despite having commits, so WP02's implement refused. Using safe-commit instead then raised `ACTIVE_WP_SCOPE_VIOLATION` on every commit — `tracer-tooling-friction.md:80`
- [FRICTION] `tests/_next_shard_map.py` is a second, undocumented marker authority. New files that are not registered are invisible to every `integration-tests-next` leg (#3241) — `tracer-tooling-friction.md:107`
- [FRICTION] The vendored `upstream_contract.json` is the enforced authority for command names and error codes. It sits outside `owned_files` and is a same-file overlap across 5 WPs — `tracer-tooling-friction.md:135`
- [FRICTION] The lane worktree has no `.venv`, and gate commands fail until `uv sync` runs there — `tracer-tooling-friction.md:203`
- [FRICTION] The `tasks` verb leaves `.kittify/sync-state.json` dirty, which trips `DIRTY_WORKTREE` in record-analysis — `tracer-tooling-friction.md:226`
- [FRICTION] The mid8 collision window is about 256ms, which made a duplicate-mission test flaky. The fix is to freeze ULID and the clock — `tracer-tooling-friction.md:181`
- [CONCERN] The plan put the shared test in a directory that the diff-coverage gate does not instrument — `tracer-design-decisions.md:115`

### custom-mission-type-second-class-citizens-01M1FQXD
- [FRICTION] `finalize-tasks` `_branch_strategy_text()` is topology-blind. A hand fix gets reverted silently by any mutating re-run (SK-133) — `tracer-tooling-friction.md:134`
- [FRICTION] The requirement-mapping gate has no notion of a descoped FR, and strikethrough is still counted — `tracer-tooling-friction.md:64`
- [FRICTION] The `requirement_refs` renderer has no per-ref status, so implemented and traceability-only refs look identical (SK-132) — `tracer-tooling-friction.md:104`
- [FRICTION] Governance overhead was high: 2 spec rulings and 4 plan fix rounds. Ruling #2 found the spec was designing the detector rather than stating the requirement — `tracer-design-decisions.md:130`
- [CONCERN] Ruling #1 contained a factual error because it reasoned from a finding summary instead of the source — `tracer-design-decisions.md:151`
- [CONCERN] There are three incompatible mission-type schemas/resolvers, so the FR-004 org-tier lookup was descoped (Refs #3831) — `tracer-design-decisions.md:217`

### next-committed-state-authority-01M1CA8W
- [FRICTION] `mark-status` run inside a lane polluted the lane with `kitty-specs/` changes and blocked for_review. Dependent-lane allocation then conflicted and was resolved with `-X ours` — `tracer-approach.md:18`
- [FRICTION] The global CLI is editable-installed from a sibling clone, and the repo's configured `primary_branch` was a stale topic branch — `tracer-tooling-friction.md:9`, `:10`
- [NOTE] Four adversarial squad reviews at spec, plan and tasks caught 5 blockers before any implementation — `tracer-approach.md:25`
- [NOTE] Deleting `primary_feature_dir_for_mission` means manual path composition trips `test_no_read_side_bypass` — `tracer-design-decisions.md:55`
- [CONCERN] Deferred work: board O(N) reductions, a redundant primary-meta read, and #3780 secondaries — `tracer-approach.md:28`

### charter-authority-flip-01M14RB3 (small, planning-heavy)
- [FRICTION] `mission create` hit a SaaS sync-store lock and had to run with sync disabled — `tracer-tooling-friction.md:3`
- [FRICTION] The glossary pack regeneration script lived in an untracked scratchpad and is gone, so the pack is hand-edited — `tracer-tooling-friction.md:5`
- [FRICTION] The exemption path in `test_no_legacy_terminology.py` is stale and points at a directory that no longer exists — `tracer-tooling-friction.md:6`
- [FRICTION] Every command needs `--mission`, because there are 433 missions in the tree — `tracer-tooling-friction.md:4`
- [CONCERN] The archived methodology.md cannot be corrected because of archive immutability — `tracer-design-decisions.md:17`

### accept-path-remediation-honesty-01M0TWZP
- [FRICTION] `agent action implement` exceeded 120s and was backgrounded with an empty output file; ENOSPC across the whole session followed — `tracer-tooling-friction.md:180`, `:225`
- [FRICTION] `mark-status` hung with no output on three attempts — `tracer-tooling-friction.md:282`
- [FRICTION] Without a lane venv, the root editable install silently tests the wrong copy of the code — `tracer-tooling-friction.md:192`
- [FRICTION] lanes.json names a phantom `kitty/mission-*` branch and predicts unrelated surfaces — `tracer-tooling-friction.md:39`
- [FRICTION] The safe-commit guard warns on the tracer files that the charter tells implementers to append to — `tracer-tooling-friction.md:211`
- [FRICTION] The scaffold commit message `Add meta for feature …` fails commitlint and violates the Terminology Canon — `tracer-tooling-friction.md:22`
- [NOTE] The enforced diff-cover floor covers only `critical_paths`, and `validators/`, `acceptance/` and `cli/` are not among them — `tracer-approach.md:43`

### custom-mission-guard-failure-blocking-inert-01M0STY0
- [FRICTION] `finalize-tasks` overwrote a stacked mission's `planning_base_branch` with target_branch, erasing the red-first anchor — `tracer-tooling-friction.md:43`
- [FRICTION] SK-93 recurred 6 times: `record-analysis` (x3), `implement` (x2) and `mark-status` hung after the real write had already landed — `tracer-tooling-friction.md:97`, `:135`, `:152`
- [FRICTION] A tracer append was committed on the lane branch's stale `kitty-specs/` copy. safe-commit only warned; move-task blocked it later — `tracer-tooling-friction.md:193`
- [FRICTION] Relative `.venv/bin/*` paths in briefs fail inside lane worktrees, and one agent borrowed `ruff` from a sibling checkout — `tracer-tooling-friction.md:217`
- [NOTE] Keeping the layering in the I/O layer made the import-boundary gate green by construction — `tracer-approach.md:16`

### charter-activate-empty-action-sequence-01M0STSX
- [FRICTION] `record-analysis` wrote host-absolute `/home/<user>/…` paths into a public artifact (SK-32, #3398) — `tracer-tooling-friction.md:81`
- [FRICTION] lanes.json has a phantom `mission_branch` and unrelated `predicted_surfaces` (SK-91) — `tracer-tooling-friction.md:36`
- [FRICTION] Generated commit messages fail commitlint (SK-64, plus 3 more type-less generated messages) — `tracer-tooling-friction.md:19`
- [NOTE] Methodological trap (SK-81): pre-seeding activations masks the bug — `tracer-design-decisions.md:5`
- [REC] Check non-goals against the diffs of open PRs, not just the issue text — `tracer-design-decisions.md:48`

### cascade-asset-silent-drop-01M0RME0
- [FRICTION] The dossier body-upload write path showed 4 different failure shapes across WP01–WP03 (hang, raise+complete, raise+hang, lock+hang), even with `SPEC_KITTY_SYNC_MINIMAL_IMPORT=1` — `tracer-tooling-friction.md:193`, `:306`
- [FRICTION] The requirement regex cannot see `FR-005a` letter-suffixed IDs, and a `finalize-tasks` re-run would silently drop the fixed ref, so the command is not idempotent — `tracer-tooling-friction.md:84`, `:111`
- [FRICTION] Allowlist entries in `test_no_dead_symbols` are keyed by body hash, so adding a dataclass field breaks CI in a way that looks like a regression — `tracer-tooling-friction.md:51`
- [FRICTION] `record-analysis` commits one artifact and leaves the dossier snapshot dirty in the same run — `tracer-tooling-friction.md:169`
- [FRICTION] `mission create` leaves its own `status.events.jsonl` untracked — `tracer-tooling-friction.md:36`
- [FRICTION] The spec phase omitted the tooling-friction tracer entirely — `tracer-tooling-friction.md:3`

### durable-concurrent-review-cycle-records-01M0QRX7 (planning-only)
- [FRICTION] The pasted `/spec-kitty.plan` prompt was older than the canonical mission-step prompt — `tracers/tooling-friction.md:11`
- [FRICTION] An inherited `SPEC_KITTY_ENABLE_SAAS_SYNC=1` caused unauthenticated sync attempts and lock warnings — `tracers/tooling-friction.md:12`
- [CONCERN] Concurrent verdict saves could lose committed review evidence (#3235). The design is a checkout-wide queue with a 10s bound — `tracers/approach.md:11`

### dossier-guard-reexport-analyze-cleanup-01M0NHRT
- [FRICTION] `finalize-tasks` writes its mutations then hangs forever in the sync retry loop. `SPEC_KITTY_SYNC_DISABLE=1` does not help, and it hung on all 4 invocations (SK-74) — `tracer-tooling-friction.md:111`
- [FRICTION] Parallel WP agents' `mark-status` calls raced the same primary `status.events.jsonl` and hung — `tracer-tooling-friction.md:334`, `:406`
- [FRICTION] `tasks.md` has no mission preamble, so baseline instructions were duplicated into every WP and one WP pointed at a preamble that never existed — `tracer-tooling-friction.md:53`, `:204`
- [FRICTION] `record-analysis` leaked absolute paths, which were rewritten by hand because the repo is public — `tracer-tooling-friction.md:231`
- [NOTE] A truncated evidence quote let a contradiction survive two review rounds — `tracer-tooling-friction.md:176`
- [NOTE] Review rejected manual BEFORE/AFTER checks; persisted red-first tests were required — `tracer-tooling-friction.md:431`

### legacy-cleanup-split-dossier-queue-migration-01M0MGHB
- [FRICTION] Coord topology on protected main hit a deadlock: safe-commit refuses main, refuses the coord branch because HEAD is not on it, and moving HEAD is forbidden — `tracer-tooling-friction.md:21`
- [FRICTION] The `spec-commit` materialize-then-retry fallback creates a coord worktree without the authored files, so the retry fails identically (SK-12 not fixed) — `tracer-tooling-friction.md:55`
- [FRICTION] `finalize-tasks` returned success with every dependency empty and all lanes parallel, because frontmatter `dependencies: []` contradicted the tasks.md prose and nothing cross-checks them — `tracer-tooling-friction.md:191`
- [FRICTION] The harness sandbox refuses git commands and Write in the shared primary checkout, which is directly at odds with `single_branch` topology — `tracer-tooling-friction.md:158`
- [FRICTION] Editing `src/` while a background baseline ran contaminated subprocess-importing arch tests — `tracer-tooling-friction.md:351`
- [CONCERN] The plan missed a `diagnose.py` `_PAYLOAD_RULES` consumer (severity 5), which was then promoted to FR-011 — `tracer-design-decisions.md:93`
- [CONCERN] Removing the de-vendored mirror dropped hash-lowercasing behaviour, and the affected test was retired — `tracer-tooling-friction.md:412`

---

## Cross-mission themes in this slice (ranked by mission count)

**1. `finalize-tasks-planning`: finalize-tasks, lanes.json, tasks.md and record-analysis (12 of 17 missions, 39 items, 11 high).** This is the densest cluster. Its sub-patterns:
- **Topology-blind generation.** `branch_strategy` prose ignores the actual topology (runtime-advance :81, custom-mission-type :134), and `planning_base_branch` is overwritten on stacked missions (guard-failure :43). lanes.json fabricates `kitty/mission-*` branches on `single_branch` missions and predicts unrelated surfaces (accept-path :39, charter-activate :36; SK-91/133). *Stated root cause:* `_branch_strategy_text()` takes only the target and merge branches and never reads the topology. *Recommendation:* make generation topology-aware and stack-aware.
- **Not idempotent / silent regression.** A re-run would undo hand fixes: FR-005a dropped (cascade :111) and `branch_strategy` reverted (custom-mission-type :134). Frontmatter `dependencies: []` silently beats contradicting tasks.md prose and returns success (legacy-cleanup :191). *Recommendation:* warn when a re-run would downgrade existing fields or when frontmatter and prose disagree.
- **Expressiveness ceilings.** `tasks.md` has no notes or preamble field (spdd :41, dossier-guard :53). There is no descoped or "satisfied by omission" status (custom-mission-type :64, spdd :135), `requirement_refs` has no per-ref status (SK-132), letter-suffixed IDs are invisible to the regex (cascade :84), and `kitty-specs/` paths cannot be owned (dispatch :48).
- **record-analysis:** it leaks host-absolute paths into a public repo (4 missions; SK-32/#3398), and a fix landed in dossier-guard FR-007. It has non-uniform commit side effects (accept-path :130, cascade :169) and silently writes `verdict: unknown` when the carrier is missing (dispatch :78; #3133). It also hangs after the commit has landed (below).

**2. Sync-store and dossier-upload hangs, "writes then hangs" (9 missions, all 01M0*–01M1H*, dated Aug 22 – Sep 2).** These items are tagged across `dead-code-legacy-residue`, `status-lanes-move-task`, `cli-ergonomics` and `finalize-tasks-planning`, so they are counted here by grep. Warnings such as `project sync store is locked` and `machine layout cutover did not publish` come with hangs in `mission create`, `plan`, `finalize-tasks` (SK-74), `record-analysis` (SK-63/93), `agent action implement` and `mark-status`. The worst cases are guard-failure :97–:173 (6 recurrences) and cascade :306 (4 distinct failure shapes). `SPEC_KITTY_SYNC_DISABLE=1` and `SPEC_KITTY_SYNC_MINIMAL_IMPORT=1` did not prevent them. *Root cause stated:* the `layout_generation._await_publish_or_loud` / `body_queue.enqueue` write-authority path, and CUTOVER_PENDING. *Universal workaround:* never trust exit codes; verify with `git log` or the event log. **The sync transport was retired in August 2026, and none of the 01M1K*+ missions report this, which suggests the cluster is historical.** It is worth confirming that no dossier body-upload remnant survives.

**3. `arch-gate-allowlists` (10 missions, 12 items).** The archive byte-freeze gate blocks corrections to archived dossiers (spdd :7, dispatch :54, charter-authority-flip :17). The safe-commit `kitty-specs/` guard contradicts the charter's instruction to append to tracers (accept-path :211). `test_no_dead_symbols` allowlist entries are keyed by body hash (cascade :51). A stale exemption path remains (charter-authority-flip :6). The feature-alias guard matches literal substrings (event-push :103). Gates copied from templates are over-scoped (cross-os :84). *Recommendation:* surface the archive-freeze rule at plan time, and carve tracer files out of the lane guard or route tracer writes to the planning surface.

**4. `test-env-venv-install`: lane worktrees have no interpreter (8 missions, 14 items).** Lane worktrees lack a `.venv`. The shared editable install points at another lane or clone, so tests silently run the wrong code (event-push :88, accept-path :192, next-committed :14, design-phase :203, guard-failure :217). *Recommendation:* provision a per-lane interpreter at `implement`, or have tooling assert `specify_cli.__file__` before any gate run. Briefs should stop using relative `.venv/bin/*` paths.

**5. `status-lanes-move-task` and `coord-branch-worktree`: lane, coordination and status-surface confusion (8+6 missions, 22 items, 13 high).** Status and `kitty-specs/` writes land on lane branches, or on a lane's stale copy (runtime-advance :113 cd-redirect, next-committed :18, guard-failure :193). `planning_artifact` WPs have no `lane-planning` branch (spdd :469). WPs with commits stay stuck in `planned` (design-phase :80). `mark-status` lacks `--wp` (SK-135) and hangs. Coord topology on protected main deadlocked, and SK-12 is unfixed (legacy-cleanup :21, :55). Approved lanes are not consolidated before gates run (runtime-advance :94). *Recommendation:* make `safe-commit` refuse `kitty-specs/` on lane branches at commit time, and route state commands to the planning surface whatever the cwd.

**6. `cli-ergonomics` (9 missions).** Users must repeat `--mission` (charter-authority-flip :4, accept-path :173). There is confusion around `safe-commit --to-branch`: the lane branch versus the merge target, plus the v3.3 deprecation (event-push :55, spdd :168, cascade :25). `mission create` and `agent mission create` are easily confused (legacy-cleanup :37). The `finalize-tasks` JSON reports only the last commit.

**7. `test-suite-speed-flakes` (9 missions).** Concurrent-agent contention appears as basetemp eviction (#3283) and a global seed counter. Baseline invocations are ambiguous: `-m "fast or unit"` versus the markers `make test-fast` uses (runtime-advance :200). Baseline figures from the orchestrator drift (accept-path :266). Editing `src/` during a subprocess-based baseline contaminates results (legacy-cleanup :351). The pre-review gate's 300s budget is miscalibrated (spdd :441). ULID/mid8 timing causes flakes (design-phase :181).

**8. `templates-prompts` (9 missions, 10 items).** The scaffold commit `Add meta for feature <slug>` fails commitlint and violates the Terminology Canon (SK-64, in 4 missions: accept-path :22, charter-activate :19, cascade :7, legacy-cleanup :122). The completion manifest is a hidden companion artifact (event-push :111). Pasted prompts go stale against the canonical source (durable :11).

**9. `review-loop-verdicts` and `governance-overhead` (8+2 missions).** Squad reviews earned their cost: they caught 5 blockers (next-committed :25), a critical scope gap (cross-os :62) and a severity-5 consumer (legacy-cleanup :93). But operator rulings were issued without checking the source (custom-mission-type :151, spdd :329). Truncated evidence quotes hid contradictions (dossier-guard :176). Over-specified specs led to 4–6 review rounds (custom-mission-type :130, charter-activate :42). *Recommendation:* verify rulings against the source, keep specs at intent level, and use full-sentence evidence.

**10. `agent-harness-sandbox` and `subagent-orchestration` (5+3 missions, 6 high).** The worktree-isolation sandbox fights `single_branch` missions that live in the primary checkout (dispatch :7, legacy-cleanup :158). Backgrounding past 120s loses transcripts. ENOSPC/EDQUOT from parallel agents took tools offline (accept-path :225, spdd :262). Subagents strand waiting on their own background work (accept-path :106, dossier-guard :111). `nohup` does not survive the tool's timeout (spdd :275). The shared global cache races between clones (blocked-wp :5, #2627).

**11. `ci-gates-routing` (7 missions).** There are hidden marker authorities: `_next_shard_map.py` (#3241) and `upstream_contract.json`. Enforced diff-cover applies only to `critical_paths`. CI job names were misremembered (legacy-cleanup dd :132, custom-mission-type :35).

**12. `tracer-process-itself` (8 missions).** Five missions left their implementation sections as placeholders (cross-os, next-committed, charter-authority-flip, durable, dispatch implementation). Two had missing tracer files (blocked-wp, spdd; cascade was seeded late). Concurrent appends duplicated and misnumbered headings (spdd :307). Tracer formats are inconsistent: free-form, the canonical prompting-question template (guard-failure), or `tracers/` with Divio frontmatter (durable).

Minor themes: `docs-drift` (the missing `SPEC-KITTY-LEDGER.md` referenced by CLAUDE.md; the Shared Package Boundary guidance not granular enough), `tracker-issue-hygiene` (open PRs overlapping scope, #3923, #3707), and `windows-cross-os`, `sonar-coverage` and `doctrine-drg-packs` with 1–2 missions each.

### Issue and PR numbers cited in this slice
#1058 #1823 #2330 #2581 #2627 #3016 #3085 #3133 #3235 #3241 #3281 #3283 #3284 #3293 #3398 #3677 #3678 #3676 #3701 #3707 #3708 #3711 #3780 #3825 #3826 #3830 #3831 #3832 #3883 #3884 #3923 #4703 #4714 #883. The ledger IDs cited most often are SK-06, SK-12, SK-32, SK-63, SK-64, SK-65, SK-74, SK-91, SK-93, SK-132, SK-133, SK-135 and SK-152.

---

## Honest limits
- The dates and some symptoms come from the tracers themselves. I did not check whether the tracked defects have since been fixed, for example SK-74/93 after the sync retirement, the SK-32 path leak (dossier-guard FR-007 fixed it), SK-133, or #3283.
- `SPEC-KITTY-LEDGER.md` is not in the checkout, so SK-NN IDs could not be resolved to their full entries.
- Several tracer sets are incomplete. blocked-wp and spdd each have only a friction file, and cross-os, durable, charter-authority-flip and next-committed have almost empty implementation sections. For these missions the friction picture reflects planning only.
- Theme assignment is a judgement call. The sync-hang cluster is spread across four slugs, so its mission count (9) comes from a grep for `sync store is locked|SK-65|SK-93|SK-74|layout cutover`, not from the theme field.
- Severity is my own assessment. Tracers rarely state severity, except for review findings that carry their own sev numbers.
- Some items record the *absence* of a known defect ("did not reproduce"). They are tagged as notes and are not counted as evidence that a defect was fixed.
