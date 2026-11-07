# Tooling friction — lane-worktree-model-hardening-01M6QY1M

Tooling the Mission touches: `spec-kitty agent mission create/finalize-tasks`, `move-task`, `consolidate`,
`doctor workspaces`, the status surface resolver, `git worktree`, `make sync-packs`/`sync-services`, the
GitHub MCP tools, the cloud-session harness.

- **[2026-11-06][setup] add_repo for spec-kitty-open-packs (push) was denied by the harness permission classifier.** S11 cannot open its upstream PR from this session; doctrine changes are drafted as a patch for the operator. Disposition: blocked, escalated in hand-off.
- **[2026-11-06][discovery] Shallow clone breaks `git diff origin/main...origin/<branch>` ("no merge base") for older in-flight PRs (#6884).** Agents fell back to per-commit `git show` and REST file lists. Disposition: workaround.
- **[2026-11-06][discovery] `gh pr view` / `gh issue view` fail (GraphQL 403 in the harness); `gh api` REST works.** Disposition: workaround.
- **[2026-11-06][discovery] The research note's "62 call sites" of `resolve_status_surface*` does not reproduce on `src/`; an AST count gives 25 direct calls in 18 files.** Grep counts docstrings/imports. Disposition: AST lister kept in the discovery scratch; the S1 gate counts by AST.
- **[2026-11-06][discovery] `_resolve_status_surface` names two different functions (`agent/status.py:139`, alias at `implement_phases.py:368`).** Misleads grep audits. Disposition: candidate tidy in S1.
- **[2026-11-06][discovery] codegraph natural-language queries returned noise (Lane enum) for status-write questions; grep/AST were faster for call-site census.** Disposition: note only.
- **[2026-11-06][discovery] No ADR file holds the #5100 explicit-only decision; it lives in an issue comment and a Mission spec FR.** Disposition: the S7 ADR supersedes it explicitly.
- **[2026-11-06][discovery] The coordination branch name equals the Mission branch name (`kitty/mission-<slug>-<mid8>`); no doc states it.** Disposition: S7 docs.
- **[2026-11-06][discovery] Five overlapping single_branch predicates (`is_planning_lane`, `is_repo_root_lane`, `lands_mission_branch`, `minted_mission_branch`, `is_single_branch_mission`); `lane_created_branch("lane-planning")` resolves to the target, a trap for gates.** Disposition: S8 tidy-first.
- **[2026-11-06][discovery] #7239/#7237/#7240 duplicate #7275's commits under different SHAs; the S4 ADR lives only on an unmerged branch.** Disposition: S5 builds a seam, binds after #7275 merges.
- **[2026-11-06][discovery] The research doctrine scan's open-packs paths/line numbers (23686fb) do not match the pinned tree (a79c3631); command skills live in core `src/charter/offering/skills/`, not in packs.** Disposition: S11 is two repos and two release paths.
- **[2026-11-06][setup] The container restarted mid-discovery; discovery files in the scratchpad survived, the primary working directory flips between /home/user and the checkout.** Disposition: always cd into the checkout.
- **[2026-11-06][specify] Discovery briefs live under a scratchpad path keyed on the old cwd (`-home-user-spec-kitty`), not the session's current scratchpad (`-home-user`).** A sub-agent must be handed the absolute path. Disposition: workaround (paths passed explicitly).
- **[2026-11-06][specify] The spec scaffold has no slots for Domain Language, Assumptions, Dependencies, Out of Scope or Rules; the specify prompt asks for them.** Added as extra sections after Success Criteria, keeping scaffold order. Disposition: note; candidate template gap for open-packs.
- **[2026-11-06][specify] spec-kitty-open-packs attached read-only at the operator's request and cloned to /home/user/spec-kitty-open-packs (22c14b2); push access is still denied by the permission classifier.** S11 pack edits can be authored on a local branch there, but the upstream PR needs push access (or the operator pushes the branch). Disposition: blocked on permission, raised with the operator.
- **[2026-11-06][plan] The orchestrator-api contract is at 1.23.0 (`envelope.py:192`), not the 1.10.0 cited in the discovery briefs and CLAUDE.md prose.** The plan uses the live value. Disposition: workaround; CLAUDE.md prose drift noted for IC-17.
- **[2026-11-06][plan] Placement of PRIMARY artifacts for coordination Missions on a protected target is not stated in one place (commit_router re-homing vs ProtectionPolicy refusal).** It took several reads and is still unresolved. Disposition: IC-14 characterization test; OQ-1.
- **[2026-11-06][plan] The plan template has no slot for an ownership map, PR rebase plan or open questions.** They were added inside the Implementation Concern Map section. Disposition: note; candidate template gap for open-packs.
- **[2026-11-06][plan] ADR 2026-06-22-1, 2026-04-03-1, 2026-07-29-1 and 2026-09-19-1 live under docs/adr/3.x, not 4.x as some briefs implied.** Paths verified by listing. Disposition: workaround.
- **[2026-11-06][plan] S11 review (open-packs PR #128) found core follow-ups.** `spec-kitty context cleanup` clears every orphaned context rather than one lane's; DESTROYED_LANE has an undocumented no-tip variant; the LANE_WORK_TIP_UNKNOWN message should suggest `--dry-run` first. Disposition: fold into IC-17 (S11 core text) if small, else file issues.
- **[2026-11-06][plan] No single doc states that the coordination branch is a configurable `meta.json` target sharing the Mission-branch grammar; corroborating it for OQ-2 took a reader census (COORDINATION_BRANCH_KEY, mission_branch_name, coord_seed/workspace reconstruct paths).** Disposition: workaround; folded into FR-059 docs (IC-17).
- **[2026-11-06][plan] Folding resolved Decision Moments back into plan artifacts is manual: the decision index has no link back to the plan sections it answers, so the OQ conditionals had to be found by grep across 9 files.** Disposition: note; candidate tooling gap (decision → artifact back-references).
- **[2026-11-06][tasks] First `finalize-tasks --validate-only` failed `LANE_DEPENDENCY_CYCLE`: every planning_artifact WP is pooled into `lane-planning`, so a planning WP that depends on a code WP (the IC-17 docs+patch WP after WP17) closes a cycle with code WPs that depend on the ADR WPs.** The canonical tasks prompt does not warn that planning-artifact WPs cannot sit downstream of code WPs. Disposition: workaround: IC-17 split into WP17 (code), WP18 (docs/changelog as `code_change`, owns only `docs/`) and WP19 (open-packs patch, planning artifact, no deps, hand-off gated in prose). Candidate gap for the tasks template.
- **[2026-11-06][tasks] The plan's shared-file ownership map (two ICs with hunks in one file) cannot be expressed in `owned_files` (no overlap allowed).** Each shared file got one owner; the other WP's hunk is a recorded out-of-map edit, listed in tasks.md "Shared-file sequencing". Disposition: workaround.
- **[2026-11-06][tasks] #6884's commits mix core code with another Mission's `kitty-specs/` files and a hand edit of `docs/changelog/CHANGELOG.md`; a plain `cherry-pick -x` would drag both in.** WP04 prescribes `cherry-pick -x -n` plus path-limited restore and a Co-authored-by trailer. Disposition: workaround.
- **[2026-11-06][tasks] WP16 owns `src/specify_cli/git/destructive_guard.py`, which exists only on #7275's branch; it is listed in `create_intent` so finalize accepts the pre-merge zero-match.** Disposition: workaround; drop it from create_intent once #7275 merges.
- **[2026-11-06][tasks] The migration file name needs the next release version (`m_4_0_0rc9_...` assumed); pyproject says 4.0.0rc8.** Disposition: WP10 told to rename consistently if the next version differs and report so owned_files can follow.
- **[2026-11-06][implement] `agent action implement` for a code lane left meta.json (`vcs_locked_at`) and the WP prompt history STAGED but uncommitted in the repository root checkout, while planning-lane agents commit in the same checkout.** Any concurrent commit there would sweep them up. Disposition: orchestrator committed them at once; candidate gap (the claim should commit its own bookkeeping or leave nothing staged).
- **[2026-11-06][implement WP02] The WP prompt prescribes `## Amendment 2026-11-06: ...` headings, while ADR 2026-10-04-5's earlier amendments are `### Amendment YYYY-MM-DD — ...` under Consequences.** Followed the prompt (the reviewer checks against it), so the new amendment sits at H2 beside H3 siblings. Disposition: cosmetic; harmonize when #7255 lands if review asks.
- **[2026-11-06][implement WP02] `pytest tests/architectural/test_no_legacy_terminology.py` (≈0.1 s per CLAUDE.md) took over two minutes in the shared repository root checkout with concurrent agents.** Disposition: noted; collection/start-up cost under contention, not the test.
- **[2026-11-06][implement WP01] ADR 2026-06-19-1 orders amendments newest first, while C-016 and the WP prompt say "append".** Disposition: the 2026-11-06 amendment is inserted above the 2026-10-01 one, following that file's own convention; no earlier text edited, frontmatter left as is (already `status: Superseded`).
- **[2026-11-06][implement WP01] ADR 2026-07-29-1 cites `tests/regression/test_issue_2993_lane_planning_ancestry.py`, which now lives in `tests/lanes/`.** Disposition: the amendment names the current path; the earlier text is not edited.
- **[2026-11-06][implement WP03] The S4 ADR (2026-11-06-1) and the S10 amendment exist only on unmerged PR branches (#7275, #7274), so the core ADRs link them by PR, and the amendment draft's relative link `../3.x/...` only resolves once pasted into `docs/adr/4.x/`.** The events ADRs 0007/0008 are on spec-kitty-events PR #215 and already link the core files by `main` URLs that 404 until this Mission merges. Disposition: cross-repo/unmerged links accepted as forward references.
- **[2026-11-06][implement WP03] `description_length_check` silently enforces a 180-char ceiling; C-3's first description was 183 chars.** Disposition: shortened; worth running before commit on every new ADR.
- **[2026-11-06][implement] `move-task WP02 --to for_review` printed a remedy `cd .worktrees/<slug>-lane-j && git rebase None`.** lane-j (WP13) has no worktree yet and the base interpolated as `None`. The command took more than 2 minutes in a checkout shared with three agents. Disposition: candidate defect (stale-lane hint with an unresolved base); file at closeout.
- **[2026-11-06][review] The issue-matrix guard refused the first per-WP approvals (WP01, WP02) on rows that belong to the whole Mission (context-only citations such as #2533 and #7255 counted as 'unknown').** Disposition: orchestrator recorded verdicts for every cited issue (S1–S11 in-mission; context and other-session issues not-applicable), then relayed the reviewers' approvals as `claude::reviewer-renata`. Candidate gap: matrix seeding from spec citations could default context-only references to not-applicable.
- **[2026-11-06][review] The generated review prompt uses `--agent claude::reviewer-renata`, while our brief said `--agent claude`; with auto-commit disabled, move-task prints "verdict written but NOT committed (--no-auto-commit)" although no such flag was passed.** Disposition: brief fixed; orchestrator commits status.
- **[2026-11-06][review] A rejection resets the WP's subtasks to `planned`, so the rework must re-mark the same subtasks done before `move-task --to for_review` runs.** Disposition: workaround; candidate gap.
- **[2026-11-06][review] Spec FR-084/C-003 still say the events ADRs are files this Mission delivers; the plan and WP03 only link spec-kitty-events PR #215.** Editing spec.md now would make the analysis report stale and block every further implement claim. Disposition: fix the two rows once the last WP is claimed, before accept, then re-run analyze.
- **[2026-11-06][review] DEFECT: the code-lane claim path (`cli/commands/implement_claim._start_wp_implementation_status`, `effective_actor: str`) records the implementer as the bare tool `claude` and drops `--profile`, while the planning-lane claim records the structured actor with the profile.** `move-task --to approved` then refuses every code WP with REVIEW_NOT_INDEPENDENT (#6715 identity rule) for a reviewer `claude::reviewer-renata`. Workaround: claim with the compact form `--agent claude::<profile>`. WP08 was re-claimed through a recorded identity-correction rejection; WP04, WP11 and WP15 were claimed bare and need the same correction at review. Disposition: file a core issue at closeout.
- **[2026-11-06][implement WP04] #6884 commit 5b6f2a8c21 (not on the carry list) holds the review-round code and the test to flip; style commit f404a0b2 does not apply without it.** Disposition: carried, path-limited to src and tests.
- **[2026-11-06][implement WP04] Integration tests in a lane worktree run very slowly (about 100 s per few tests); 47 test files plant an empty `.git` directory.** Disposition: used `-n`; an empty `.git` without HEAD counts as no repository.
- **[2026-11-06][implement WP04] WP04 handed off with the bare claim identity as well; identity correction applied before review.**
- **[2026-11-06][implement WP15] Every `done` transition clears the lane-tip ref (`lanes/claim_base.on_wp_terminal`, #5115); a killed consolidate leaves the merge lock behind, so `--resume` needs a manual unlock; shared-machine OOM killed parallel test workers twice.** Disposition: noted; candidate gaps for the lock.
- **[2026-11-06][implement WP09] `core/worktree.py` (`create_wp_workspace`, `create_feature_worktree`) and `core/vcs/git.py::create_workspace` have no production caller; the gate allowlists them.** Each fresh pytest session in a lane worktree rebuilds a test venv (session-fixture `pip install -e`), adding minutes per run. Concurrent agents push load above 10 on 4 cores. Disposition: retire the dead creators (follow-up issue); note the venv cost.
- **[2026-11-06][implement WP05] The dead-symbol gate forces a cross-module caller (or an allowlist entry) for read functions whose consumers arrive in later WPs; the read-side bypass gate blocks raw path primitives in a new module (the door's lookup helper lives in surface_resolver as `locate_status_mission`); an out-of-dir caller (wp_status_backfill) classified liveness from the legacy path and only make test-fast caught it.** Disposition: allowlist entry `read_status_events` burns down in WP06.
- **[2026-11-06][review WP09] WP09 deletes about 1,500 test lines (the dead worktree creators); `tests/architectural/test_module_length_agreement.py` may need a timings recapture.** Disposition: check in CI on the draft PR.
- **[2026-11-06][implement WP13] Each test run took 3 to 28 minutes under xdist on the shared, overloaded machine; `coord_topology_reachable` and the coord factory's `topology=None` path lost their live callers.** Disposition: dead-code check at review; WP14 wires `count_code_lanes` and `restamp_topic_branch_as_coordination`.
- **[2026-11-06][review WP13] The dead-symbol gate also flags WP15's `consolidation/lane_cleanup` exports (approved WP15, f50df2bb07). WP15's review did not run that gate serially.** Disposition: fixed in WP13's cycle-2 rework, whose lane carries WP15. Lesson: every code-WP review runs `test_no_dead_symbols.py` serially. The 17 out-of-matrix failures in `tests/specify_cli/cli/commands -k "create or specify or lifecycle"` were attributed by test name only; verify on the base before the PR.
- **[2026-11-06][implement WP13] Several lanes edit `tests/architectural/dead_symbol_allowlist.yaml` and `_baselines.yaml` in parallel (WP05 +1, WP06 -1, WP13 +2 with exits naming WP14).** Disposition: expect consolidation conflicts on both files. Resolve to the union of live entries with an honest recount; WP14 must remove the two WP13 entries. The dead-symbol gate's ~240 s run sits at its timeout under load.
- **[2026-11-06][implement WP06] `read_status_ref` returns ABSENT when the ref's tree object is missing, so a corrupt coordination branch reads as an empty history (WP04 residual, confirmed); each `uv run` pytest session rebuilds a test venv (~50 s).** Disposition: residual recorded for the ADR; venv cost noted.
- **[2026-11-06][implement WP10] An rc9-named migration is impossible while pyproject is at rc8 (the requires-git audit runs the upgrade at the installed version); upgrade-preview subprocess tests cannot run from a lane worktree with the shared venv ("Source mismatch").** Disposition: renamed to rc8; the lane tests are classified as a stale install.
- **[2026-11-06][implement] Dogfooding clash: the managed status sparse exclusion (`/*`, `!kitty-specs/<mission>/status.events.jsonl`, `!.../status.json`) was applied to all ten live lane worktrees of this Mission, most likely by WP10's new `doctor sparse-checkout --fix` run with lane source.** The installed CLI (base code, editable from the repository root checkout) predates the managed-sparse policy and refuses `implement` as legacy sparse-checkout (#588). Disposition: verified the patterns are exactly the managed exclusion with clean lane trees, then used the logged `--allow-sparse-checkout` override for claims. Consolidation will hit the same preflight: either the same override, or `git sparse-checkout disable` per lane first. Decide at consolidate time. Lesson for implementers: never run a mutating doctor `--fix` from a lane against the shared repository.
- [2026-11-06][WP07] A parallel consolidation+coordination suite run hit the container memory limit (OOM kill); the red-first check needed a separate base export because PYTHONPATH pins the lane src.
- [2026-11-06][WP07 review] `agent action review` rejects `--allow-sparse-checkout` as an unknown option; the review claim works without it.
- [2026-11-06][WP10 review] Running a broad blast-radius suite on the lane and the base at the same time timed out, so its reds could not be attributed; run lane and base comparisons one after the other.
- [2026-11-06][WP14] After a lanes_with_coord settlement the root checkout has no Mission directory, so every reader that builds the path from the root breaks.

- 2026-11-07 closeout: `spec-kitty accept` refuses only on "Acceptance matrix verdict is 'pending'": `acceptance-matrix.json` holds 63 auto-generated placeholder criteria (FR-001.. "TODO: replace with a real acceptance criterion", evidence null). Nothing earlier in the workflow prompted for them; filling them is real verification work, so closeout stopped here.
- 2026-11-07 closeout: `consolidate --dry-run` forecasts a reconciliation FAIL on two lane-to-lane dependency merge commits, 013cf94cff (lane-c into lane-k, `_baselines.yaml` conflict resolution) and d1e9235fe4 (lane-d into lane-n), reported as "belongs to NO approved WP". The remedy text points at `--dependency-ref`, but that flag refuses Mission-authored refs, so it does not fit an intra-Mission dependency merge.

## [closeout 2026-11-07] consolidate refused: legacy sparse-checkout on three lane worktrees

`accept` succeeded (acceptance commit 7c7b9e22ba, status commit 242beb5). The real
`consolidate --keep-branch --keep-worktree` then refused (exit 1) with "legacy
sparse-checkout state detected" for lanes d, g and k. Each of those worktrees has a
worktree-scoped `core.sparseCheckout=true` (`extensions.worktreeConfig` on) and an
`info/sparse-checkout` written 2026-11-06 ~19:58-19:59 excluding only this Mission's
`status.events.jsonl` and `status.json`. The repository root checkout is not sparse.
The dry run did not report this, so the sparse preflight is a real-run-only gate.
Closeout stopped: the offered remedies (`doctor sparse-checkout --fix`, a mutating
doctor, and `--allow-sparse-checkout`, an override) both need an operator ruling.

- Follow-up: `consolidate --dry-run` does not run the legacy sparse-checkout preflight at all,
  so a clean dry run (exit 0) did not predict this refusal.

## [closeout 2026-11-07] consolidate refused: lane-f stale against the mission branch

With `--allow-sparse-checkout`, consolidate merged lane-e and lane-a into
`kitty/mission-lane-worktree-model-hardening-01M6QY1M`, then refused on lane-f: "Lane lane-f is
stale: overlapping files ['src/specify_cli/lanes/for_review_gate.py'] ... Run: cd
.worktrees/*-lane-f && git merge kitty/mission-lane-worktree-model-hardening-01M6QY1M". The
rollback authority restored the mission branch (921bb30 -> a4e3426) and rebaselined the record;
the target was unchanged. The dry run did not forecast this staleness either. The suggested
remedy commits to an approved lane after approval, so closeout stopped for a ruling.

## [closeout 2026-11-07] after #7311: lane-l stale (genuine overlap)

With #7311 merged (topic 82bde0c406), consolidate passed lane-f and merged lanes e, a, f and h,
then refused on lane-l (WP15): stale, overlapping `tests/specify_cli/git/test_guarded_site_routing_misc.py`.
This overlap is real. Lane-f's WP09 review-cycle commit 4a1d8e7a1d edits that file and is not in
lane-l, and lane-l's own f50df2bb07 edits it too. The rollback restored the mission branch
(7e650a6 -> a4e3426). The new remedy text (#7311/WP17 wording) is correct. Closeout stopped:
refreshing lane-l means merging in content from another WP, not a pure dependency merge.

## [closeout 2026-11-07] all lanes merge; squash projection refuses TARGET_BRANCH_CONTENT_CONFLICT

Topic branch d1d3f99d03. Every lane (e … o) merged into the mission branch with no stale refusal;
the run built mission commit 117c4ec. The default squash onto `issue-7276-lane-worktree-hardening`
then refused with `TARGET_BRANCH_CONTENT_CONFLICT` on `src/specify_cli/lanes/stale_check.py` and
`tests/lanes/test_stale_check.py`. This is the expected #7311 (on the target) against WP17
(lane-n) overlap, but it surfaces before the squash, as a refusal, not as an editable conflict.
The remediation reads "Update the mission branch against the current target branch". Since every
failed run rolls the mission branch back to a4e3426 and rebuilds it from the lanes, the update has
to live in a lane (lane-n), so WP17 needs a refresh and a new approval. CONTRACT_VERSION did not
conflict: `git merge-tree` of target against 117c4ec reports only these two paths.
Closeout stopped, as ruled ("if anything refuses, stop and report").
