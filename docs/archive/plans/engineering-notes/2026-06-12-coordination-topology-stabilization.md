---
title: 'Working Plan — Coordination Topology Stabilization (Post-3.2.0)'
description: 'Point-in-time working plan synthesizing findings for the coordination-topology split-brain and fail-open gate issues under umbrella #1878; the planned work is now done.'
doc_status: superseded
type: explanation
updated: '2026-08-10'
---
# Working Plan: Coordination Topology Stabilization (Post-3.2.0)

Synthesized from validated findings for issues #1164, #1878 (umbrella), #1883, #1884, #1885, #1886, #1887, #1888 in Priivacy-ai/spec-kitty.

---

## 1. Executive Summary

All eight issues were investigated; **seven are valid** and **one is partially valid** (#1888 — the headline claim "never existence-checked" was refuted, but the underlying signal-routing/severity gap is real). No issue is wholly invalid.

The findings collapse into two dominant structural themes, both tracked by the umbrella **#1878 (complete the coordination placement/identity strangler)**:

1. **Coordination-topology split-brain (write/read divergence).** Write paths (status transitions, planning commits, lifecycle events) were migrated to commit on the coordination branch via the placement resolver (PRs #1850/#1879), but read/gate surfaces still treat the primary checkout's HEAD/working tree as the sole authority. Concrete instances: `is_committed()` blocking setup-plan (#1884), accept's `git_dirty` gate (#1883), the wrong-root path anchoring that leaks `.worktrees/<slug>-coord/...` artifacts into the index (#1887), and the operator-facing "ff-merge treadmill" (~10 manual `git merge --ff-only` per session, workflow-failures-log items 24-25).

2. **Gates and signals that fail open or self-defeat.** Tools write artifacts they then count as operator dirt (#1883); a mission-resolution failure renders as a successful empty query at exit 0 (#1885); validation warnings are generated but emitted into a JSON field no prompt ever reads (#1888); the always-on terminus retrospective silently does not run on the dominant completion path and finds nothing on a 28-failure mission (#1164); the stale-assertion analyzer flags intentional message-content assertions (#1886).

A third, smaller theme: **mission 131's workflow-failures-log.md is itself the regression corpus** — 28 documented failures, items 1-3, 17-20, 23-25, 28 directly map to these issues and should seed regression tests.

Two coordination notes: (a) PR #1895 draft (fork branch `stijn-dejongh/spec-kitty`, mission `name-vs-authority-remediation-01KTYGTE`) claims in-flight work on the #1884 FR-001 fix and the #1885 fail-closed query hardening — **coordinate before starting WS1/WS3 to avoid duplicate fixes**. (b) The headline #1885 mid8 symptom is already fixed on main (commit 8544012fa, PR #1850) but was absent from the v3.2.0rc42 the reporter ran — the next release tag must include it.

---

## 2. Findings Table

| Issue | Title (short) | Verdict | Severity | Root cause (one line) |
|---|---|---|---|---|
| #1878 | Umbrella: complete coordination placement/identity strangler | valid | medium (epic) | Incomplete strangler: writes migrated to coordination-branch placement authority; read/gate surfaces still anchor on primary HEAD/tree, bridged manually by the ff-merge treadmill. |
| #1883 | accept self-defeats on git_dirty | valid | high | Accept conflates reading (gates) with writing (matrix materialization) with no concept of tool-owned writes; failure/--no-commit exits leave accept-owned dirt the next run fails on — non-convergent. |
| #1884 | setup-plan is_committed coordination-blind | valid | high | `is_committed()` (_substantive.py:214-239, untouched since #898) hardcodes "tracked + present at primary HEAD"; coordination-branch commits are invisible to the gate. |
| #1885 | `next` returns silent "[QUERY — no result]" stub | valid | medium | (1) mid8 canonicalization fix (8544012fa) absent from rc42; (2) still on main: `query_current_state` catches ActionContextError and returns an "unknown" Decision at exit 0 — fail-open not-found design. |
| #1886 | stale-assertion analyzer false-positives on message-content assertions | valid | medium | Literal channel keys on bare string-value identity per changed file; no classification of the assertion's containment target (str(err)/excinfo/etc.), only exemption is `not in`. |
| #1887 | squash-merges commit `.worktrees/<coord>/kitty-specs/...` duplicates | valid | high | `_feature_dir_file_paths` relativizes coord-worktree files to the PRIMARY root; three downstream layers (write_artifact confinement, `git add --force`, backstop validating only unexpected paths) all fail open. 26 paths tracked on origin/main today. |
| #1888 | finalize-tasks accepts phantom owned_files paths | partially valid | medium | Existence check EXISTS (validate_glob_matches, since mission 065) but is uniformly soft and its warning lands in a JSON field no prompt instructs anyone to read; literal vs glob never distinguished. |
| #1164 | terminus retrospective silently absent; ran_no_findings on 28-failure mission | valid | high | (1) Capture is anchored only to the `spec-kitty next` terminal-decision path — merge-completed missions never cross it, and absence emits no event; (2) generator mines only lane-event heuristics, never mission-local artifacts (workflow-failures-log.md etc.). |

---

## 3. Cross-Cutting Root Causes

### Cluster A — Coordination read-surface blindness (#1878 umbrella; closes #1884, large part of #1883, treadmill items 24-25)
Single cause: gates define "committed"/"clean" against the primary checkout while writers target the coordination branch. Fixing it means one **coord-topology-aware read primitive** (a read-path twin of the placement resolver, mirroring `resolve_mission_read_path`) that every gate consumes: `is_committed`, accept's `git_dirty`, record-analysis preflight, check-prerequisites, map-requirements, dashboard reads. Plus rollout of `advance_branch_ref` as the standard post-write primary-ref sync to retire the manual ff-merge treadmill.

### Cluster B — Wrong-root path anchoring in writers (#1887; sibling fallbacks in #1884)
Single cause: commit-path construction anchored to the primary repo root while operating on coordination-worktree content, with `git add --force` and a requested-path-blind safe_commit backstop letting it through. The same class lives in `_planning_commit_worktree`'s silent fallbacks to `repo_root` (missing mid8 / CoordinationWorkspace.resolve failure), which re-target protected main. Fix: fail-closed `path_is_under_worktrees` rejection at all choke points + structured errors instead of silent fallbacks.

### Cluster C — Self-defeating / non-transactional gates (#1883; encoding-retry path; #1814 class)
Single cause: cleanliness gates with no ownership model for tool-written artifacts. Accept writes the matrix even in --no-commit (contradicting its help text), commits residue only on the success path, and snapshots the whole tree including daemon-materialized untracked files. Fix: write-aware baselines, true read-only modes, residue committed on all writing exit paths.

### Cluster D — Signals generated then dropped / fail-open not-found (#1885, #1888, #1164 triggering half)
Single cause: error and warning channels that exist in code but are structurally unconsumable — exit-0 "unknown" query stubs, `ownership_warnings` JSON arrays no prompt reads, retrospective absence with no skip event. Fix pattern is uniform: **fail closed with structured, named errors at the boundary, or emit a recorded event so absence is impossible to miss.**

### Cluster E — Heuristics blind to intent (#1886, #1164 content half, #1888 overlap guard)
Single cause: analyzers that match on surface shape (string identity, lane-event shapes, textual glob prefixes) without classifying semantic intent (message-content assertion vs code reference; documented friction vs event-log friction; two spellings of one file). Fixes are independent per analyzer but share the lesson: classify the target before judging.

---

## 4. Working Plan

Sequencing rationale: writer fixes before cleanup (so violations don't recur), read-surface fixes before treadmill automation (gates reading the coord view removes the blocking symptom), small independent fixes (#1886, #1885 residual, #1888) parallelizable at any time. **Check PR #1895 overlap before starting WS1 and WS3.**

### WS1 — Coordination-aware read primitive + setup-plan gate (closes #1884; core of #1878)
- **Scope:** Add a placement-aware `is_committed(file, repo_root, placement)` (or read-path twin of `_commit_to_branch`) that resolves the artifact's CommitTarget via `resolve_placement_only` and checks `git cat-file -e <placement.ref>:<rel>`, primary-HEAD as the flattened-topology case. Migrate the setup-plan #846 entry gate (mission.py:1815-1819). Convert `_planning_commit_worktree`'s silent fallbacks to repo_root (missing mid8, CoordinationWorkspace.resolve failure, ~mission.py:603-621) into structured errors or on-demand coord-worktree materialization. Ensure commit-bearing lifecycle/status emission resolves its destination via the placement authority.
- **Effort:** medium. **Severity addressed:** high.
- **Dependencies:** none upstream; unblocks WS2/WS4 conceptually; coordinate with PR #1895 draft (claims FR-001 fix in flight).
- **Verification:** integration test — coordination topology + protected main + spec committed only on coord ref → setup-plan entry gate passes. Negative test: spec committed nowhere → `SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED` with `spec_committed: false`. Structured-error test for the mid8-missing fallback. Widen the AC10 architectural lint so new primary-anchored gates cannot be introduced.

### WS2 — Stop `.worktrees` index leakage: writer fix, cleanup, ratchet (closes #1887; part of #1878)
- **Scope:** (1) Writer: make `_feature_dir_file_paths` (implement.py:441) anchor to the worktree containing feature_dir, and add fail-closed `path_is_under_worktrees` rejection (reuse merge.py:153 predicate) at implement.py files_to_commit assembly, `BookkeepingTransaction.write_artifact`, and safe_commit's requested-path validation (extend the backstop to validate requested paths, not just unexpected ones). (2) Cleanup PR: `git rm -r --cached` the 26 paths from #1825 (`do-dispatch-open-op-lifecycle-01KTSJ2H-coord`). (3) Ratchet: architectural test in `tests/architectural/` asserting `git ls-files .worktrees/` is empty (promote the doctor.py:2870 predicate into CI).
- **Effort:** medium. **Severity:** high.
- **Sequencing:** writer fix first (in-flight missions don't re-violate), then ratchet, then cleanup landing with/after the ratchet.
- **Verification:** regression test — coordination mission whose feature_dir resolves under `.worktrees/<slug>-coord/` produces commit paths NOT prefixed `.worktrees/`; safe_commit rejects a requested `.worktrees/` path; post-cleanup, `spec-kitty doctor` worktrees check and the new architectural test both pass on main. Note interaction defect: removing the 26 leaked paths changes `is_committed` behavior for that legacy mission (the two defects partially mask each other) — test both states.

### WS3 — Accept gate transactional ownership (closes #1883; depends on WS1 primitive, #1814 pattern)
- **Scope:** (1) Make `--no-commit` truly read-only: `mutate_matrix=False` (accept.py:284), honoring the help text at :224. (2) Make `git_dirty` write-aware: baseline before any accept-owned write and/or exclude accept-owned derived paths (acceptance-matrix.json, status views) — same principle as #1814. (3) Fold residual artifacts into a commit on ALL writing exit paths, including failure exits (accept.py:322-334). (4) Fix the write-target split: `_check_lane_gates` writes to the primary-anchor feature_dir while reads use the coordination-resolved dir. (5) Serialize or make event-log-authoritative the WP frontmatter agent/activity fields (unlocked read-modify-write in agent/tasks.py:3662-3688, status/emit.py:359-364) to close the lost-update race.
- **Effort:** medium. **Severity:** high.
- **Dependencies:** WS1 (shared dirty/committed primitive); #1149 for the verdict-recording CLI (below).
- **Verification:** non-convergence regression test — run accept twice on a failing mission; second run must NOT fail git_dirty on accept's own matrix write. `--no-commit` test asserting zero filesystem mutations (porcelain identical before/after). Encoding-normalization retry path (tasks_cli.py:157-191) covered too. Concurrency test for the frontmatter lost-update race.
- **Companion (overlaps #1149):** add a CLI verdict-recording surface (e.g. `spec-kitty agent mission matrix set-verdict`) so operators never hand-edit acceptance-matrix.json. Can ship separately.

### WS4 — ff-merge treadmill elimination (part of #1878; after WS1-WS3)
- **Scope:** Roll out `advance_branch_ref` (already carries the R1 untracked-collision gate) as the standard post-transition primary-ref sync everywhere the coordination branch is written; share the #1814 coord-owned-residue exclusion with it so syncs don't abort on tool-written untracked files (status.events.jsonl, status.json, tasks/.gitkeep — failure-log item 25). Retire the `_ensure_branch_checked_out` shim (#1666 per the inline comment at mission.py:2512-2515).
- **Effort:** medium-large. **Severity:** medium (operator tax, not correctness, once WS1 lands).
- **Verification:** end-to-end coordination-mission test asserting zero manual ff-merges required across specify→plan→tasks→implement→merge; collision test with coord-owned untracked residue present.

### WS5 — Fail-closed `next` query mode (closes #1885 residual; small, independent)
- **Scope:** In `runtime_bridge.query_current_state` (runtime_bridge.py:3074-3097), replace BOTH silent "unknown" branches with a structured named error (e.g. `MISSION_NOT_FOUND`) carrying the raw handle + remediation hint, exit 1 in human and `--json` modes. Tighten `next_cmd._resolve_mission_slug` (:331-357) so unresolvable handles error at the boundary (audit the StatusReadPathNotFound swallow and the advancing-mode `--result` path the same way). Release hygiene: verify the next release tag contains 8544012fa.
- **Effort:** small. **Severity:** medium.
- **Dependencies:** coordinate with PR #1895 draft, which claims exactly this hardening.
- **Verification:** CLI tests — nonexistent handle → exit 1 + named error in both output modes; valid mid8 → resolves (already verified on main); JSON consumers can distinguish not-found from real state.

### WS6 — Ownership validation severity + signal routing (closes #1888; small, independent)
- **Scope:** (1) In `validate_glob_matches`, classify literal vs glob entries; literal matching zero files → hard error (or error-by-default with override, aligning with #1766), with nearest-match suggestion (basename search). Handle the legitimate planned-new-file case (the same WP02 had a valid zero-match new-file target) via a create-intent annotation. (2) Make warnings consumable: emit `ownership_warnings` to stderr under `--json` AND update the tasks-finalize source prompt (`src/doctrine/missions/mission-steps/software-dev/tasks-finalize/prompt.md`) to require acting on them. (3) Re-validate at lane-compute time so phantoms can't enter lanes.json.
- **Effort:** small. **Severity:** medium. **Dependencies:** #1766 (strictness policy), #1162.
- **Verification:** regression test using the mission-131 shape — literal typo path with an existing near-match elsewhere → hard error with suggestion; planned-new-file annotation → passes; finalize-tasks `--json` output asserts stderr warning emission.

### WS7 — Stale-assertion analyzer message-content classification (closes #1886; small, independent)
- **Scope:** In `_literal_findings_for_assertion` (stale_assertions.py:350), classify the containment target: removed-literal-in-message-like-expression (`str(...)`, `excinfo.value`, `.message`/`.stderr`/`.stdout`/`.output`, capsys/result captures) → skip or emit a distinct info-grade finding ("message-content assertion; verify the diagnostic still names this term"), mirroring the existing absence-check exemption. Hardening: (a) repo-wide survival check (literal still present in any head production source → suppress); (b) fix the last-wins `changed_literals` dict so all removal sites report; (c) confidence threshold/grouping in the merge summary (merge.py:2570-2571).
- **Effort:** small. **Severity:** medium (advisory-only noise, but erodes trust in the release-readiness report).
- **Verification:** regression test in the mission-131 shape — literal removed from one file, asserted via `str(err)` in a test, surviving inside a longer diagnostic elsewhere → no low-confidence finding (or info-grade only).

### WS8 — Terminus retrospective: triggering + content (closes #1164; large)
- **Scope (triggering):** single shared terminus-capture entry point; merge-time (or accept-gate) postcondition — before declaring merge complete, check canonical `kitty-specs/<slug>/retrospective.yaml`; if absent, invoke the same capture path as the runtime terminal branch, or emit a recorded RetrospectiveSkipped/CaptureFailed event with reason. Consolidate `_run_retrospective_learning_capture` with the orphaned `run_terminus` lifecycle (which already has skip-event semantics but is dead code) — one implementation, not two. Fix `retrospective_terminus.py` `_record_path_str` still pointing at the gitignored `.kittify/missions/` path (stale vs FR-006/#1771 canon).
- **Scope (content):** extend `generate_retrospective` with mission-local artifact ingestors — workflow-failures-log.md numbered entries, analysis-report.md, mission-review-report.md, review-feedback files — into not_helpful/gap findings with file evidence refs. Revisit the "helped only when friction exists" rule (generator.py:684) and the ran_no_findings resolution. Fix the docstring falsely claiming mission-review-report.md/charter ingestion (generator.py:844-846).
- **Effort:** large. **Severity:** high. **Dependencies:** #1878 (path resolution), #1771 (done), #1879.
- **Verification:** (1) merge a mission via the orchestrated path (no `spec-kitty next` terminus) → retrospective.yaml exists OR a skip event is in status.events.jsonl — silent absence structurally impossible; (2) golden test: mission-131 fixture (clean lane history + 28-entry failures log) → generator returns non-empty findings with file refs, NOT ran_no_findings.

**Suggested order:** WS1 → WS2 (writer fix can parallel WS1) → WS3 → WS5/WS6/WS7 (parallel, anytime) → WS4 → WS8. WS8's triggering half can start once WS1's read primitive exists; its content half is independent.

---

## 5. Falsified / Refuted Claims (do not re-litigate)

- **#1883:** Accept does NOT mutate WP frontmatter, tasks.md checkboxes, or meta.json vcs-lock — those writers are move-task/refs paths (agent/tasks.py:3688), the phase-1 mirror (status/emit.py:335-364), and implement/init. The gate trips on them, but attribution to accept is wrong.
- **#1883:** The literal within-run ordering claim is inverted — the snapshot (:934) is taken BEFORE the matrix write (:1025→:754). The self-defeat is **cross-run** (failure/--no-commit residue fails the NEXT run), except for one true same-run path (encoding-normalization retry in tasks_cli.py:157-191).
- **#1883:** Matrix scaffolding happens at **finalize-tasks** (agent/mission.py:3298-3308), not accept time.
- **#1885:** "No change since 8544012fa" was misleading — 8544012fa **is** the fix; the reporter's rc42 simply predates it. The fix lives in `next_cmd._resolve_mission_slug`, not `mission_runtime/resolution.py`.
- **#1886:** The analyzer is advisory-only (never aborts a merge); findings are low-confidence. Citation drift (test line 566 vs 589, merge.py:440 vs :474) is the analyzer's last-wins dict, not investigator error.
- **#1887:** Commits 43fa4b6e3/9299d39ae/a5f30616e were real prior instances of the pattern but NOT the source of today's 26 paths — those came from squash 6518c852a (PR #1825); the earlier ones were cleaned by 832a394d6 (#1775).
- **#1888 (headline refuted):** Ownership existence-checking DOES exist (`validate_glob_matches`, validation.py:267-295, wired into finalize-tasks since mission 065/#449) and DOES fire on the phantom path. The defect is soft severity + an unconsumed warning channel, not a missing check.
- **#1164:** The write-path tracked-location fix was attributed to PR #1879; it actually landed in 8544012fa (#1850). Also, force transitions ARE mined by the generator — mission 131's friction simply never reached the event log.
- **#1884 sibling 1:** The primary setup-plan auto-commit bypass observed at rc42 was already fixed at HEAD by #1879 (`_safe_load_meta` re-anchoring); only the residual silent fallbacks remain.

---

## 6. Dormant Masks / Follow-Ups

**Fold into workstreams:**
- safe_commit stages ALL requested paths with `git add --force` — any gitignored path a caller requests is committed silently; backstop validates staged-vs-requested but never requested-vs-policy (→ WS2).
- `BookkeepingTransaction.write_artifact` creates a nested `.worktrees/<coord>/...` subtree **on disk inside** the coordination worktree (working-copy duplication, not just index) (→ WS2).
- Surface-anchoring inconsistencies: `agent context resolve --action tasks` anchors coord while `check-prerequisites` anchors primary; map-requirements reads coord while WP files live on primary; dashboard reads primary while transitions write coord (#1572 family) (→ WS1 migration list).
- `--no-commit` help-text contract violation; encoding-retry same-run self-defeat; primary-anchor write-target split in `_check_lane_gates` (→ WS3).
- Unlocked read-modify-write WP frontmatter — lost-update race affects ANY concurrent transition pair, not just accept (→ WS3.5).
- `advance_branch_ref` refuses on coord-owned residue but offers no cleanup — must share the #1814 exclusion before rollout (→ WS4).
- `next` JSON query mode exit-0 "unknown" document; `_resolve_mission_slug` StatusReadPathNotFound swallow; advancing-mode (`--result`) not-found path; second identical stub branch at runtime_bridge.py:3087-3097 (→ WS5).
- Entire soft-warning channel (concern_coverage, inference, audit-coverage warnings) flows into the same unread `ownership_warnings` field (→ WS6).
- Analyzer identifier channel has the same conflation at **higher** confidence (medium/high, stale_assertions.py:440-479); merge summary has no confidence threshold; FP_CEILING self-monitoring only warns, never filters (→ WS7).
- `run_terminus` dead lifecycle (retrospective.skipped events likely unreachable in production); generator docstring stale contract; "helped only by contrast" rule guarantees ran_no_findings on clean missions; merge.py:2894 stale-assumption comment (→ WS8).

**File as new issues:**
1. **mid8 canonicalization enforced once at a shared selector boundary** — currently patched surface-by-surface (merge, next, agent helpers); other `--mission`/`--feature` consumers may still accept raw mid8 and silently miss.
2. **Interaction defect:** the 26 leaked `.worktrees` index entries can make `is_committed` return TRUE for a coord-resolved spec path on the legacy mission — #1887 partially masks #1884; verify both directions after WS2 cleanup.
3. **`_globs_overlap` general false negatives** — purely textual prefix/fnmatch heuristic; two differently-spelled patterns matching the same real file are not detected as overlapping (beyond the #1888 phantom case).
4. **mission create `tasks/.gitkeep` scaffold** trips dirty-tree gates and ff-merge collisions — creation-time mechanism not yet traced (partially confirmed under #1878).
5. **Doctor `_check_tracked_worktrees_content` is error-severity but advisory-only** — origin/main has failed it since 2026-06-11 with no CI signal; WS2's architectural ratchet addresses `.worktrees` specifically, but consider promoting doctor error-severity checks to CI generally.
6. **PR #1895 coordination** — track the draft's actual coverage of #1884 FR-001 and #1885 hardening; absorb or hand off WS1/WS5 slices accordingly.
