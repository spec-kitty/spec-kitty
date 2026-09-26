# Planner-Priti coverage check — Group A

Themes: finalize-tasks-planning (110), templates-prompts (28), plan-premise-errors (4), tracker-issue-hygiene (22), governance-overhead (14), tracer-process-itself (37). That is 215 tracer items from 70 missions, grouped into 34 clusters.

**Profile applied:** planner-priti, loaded via `spec-kitty agent profile show planner-priti` with plan-action charter context. I applied DIRECTIVE_003 (decision documentation: each verdict records its evidence and what was searched), the eisenhower-prioritisation and problem-decomposition tactics (one cluster = one fixable thing, P0-P3 by impact × recurrence), premortem-risk-identification (dependencies are noted on the drafts), 028 search-tool-discipline, and 045 read-intent: read-only on GitHub and the repo, and nothing was filed.

**Verdicts:** COVERED 10 · PARTIAL 12 · CLOSED-ONLY 5 · UNCOVERED 7

## Clusters → verdict → issues

| ID | Kind | Cluster | Missions/items | Max sev | Verdict | Issues (state, fit) |
|---|---|---|---|---|---|---|
| A-01 | both | finalize-tasks bundles every planning_artifact WP into one lane-planning node, so a planning WP that is both upstream and downstream of code lanes (or a pure scheduling constraint encoded as `dependencies:`) yields a false LANE… | 3/6 | high | **PARTIAL** | #428 (open, adjacent); #3431 (closed, adjacent) |
| A-02 | cause | Write-scope-overlap collapse in compute_lanes produced a cyclic depends_on_lanes graph from an acyclic WP graph, and finalize-tasks still reported success. | 3/3 | high | **CLOSED-ONLY** | #3431 (closed, exact) |
| A-03 | cause | A code-free planning_artifact or verification WP cannot declare ownership. build_wp_manifests drops `owned_files: []` because of a truthiness check, so compute_lanes raises 'Executable WP has no ownership manifest'. Paths under… | 4/5 | high | **COVERED** | #2742 (open, exact); #3683 (open, partial); #2643 (closed, partial) |
| A-04 | cause | WP dependency authority is split between wps.yaml, WP frontmatter and tasks.md prose. Frontmatter drifts from the prose chain, and _detect_dependency_conflicts refuses a real new edge when frontmatter already holds a different … | 3/4 | high | **PARTIAL** | #4152 (open, adjacent); #4135 (closed, partial); #4890 (closed, adjacent) |
| A-05 | both | requirement_refs live in three unsynced copies (wps.yaml, WP frontmatter, tasks.md). When wps.yaml is present, finalize-tasks reads only frontmatter, so it reports every FR unmapped until map-requirements runs. The tasks.md fal… | 4/6 | high | **PARTIAL** | #428 (open, partial); #2066 (open, adjacent); #3221 (closed, adjacent) |
| A-06 | cause | The requirement-ID grammar accepts only FR\|NFR\|C-\d+. SC-### and letter-suffixed ids (FR-005a) are dropped from WP frontmatter with a clean success, and a re-run can silently downgrade existing refs. | 3/5 | high | **COVERED** | #3519 (open, exact); #2991 (open, exact); #3874 (open, partial) |
| A-07 | cause | The spec.md requirement scan counts foreign FR ids (cited ADR sentences, other missions' FRs) as this mission's own, which forces fabricated mappings or elided citations. Headings for C-XXX bare prose are left out of blocking s… | 3/3 | high | **COVERED** | #3394 (open, exact); #3170 (open, exact); #3519 (open, exact); #2742 (open, partial) |
| A-08 | improvement | requirement_refs have no per-ref status: descoped, retired, satisfied-by-omission and traceability-only look the same. A retired or struck-through FR is still counted as unmapped, and descoping means rewording every mention of … | 5/7 | high | **UNCOVERED** | #2066 (open, adjacent); #3519 (open, adjacent) |
| A-09 | cause | finalize-tasks is not transactional. A failing run has already written WP frontmatter, tasks.md, lanes.json, issue-matrix and lifecycle events; the success commit can miss events appended after staging; and re-finalizing after … | 4/5 | high | **PARTIAL** | #4075 (open, partial); #2644 (open, partial) |
| A-10 | cause | finalize-tasks is topology-blind and non-idempotent. It writes lanes.json with a phantom mission_branch for single_branch missions and keyword-matched predicted_surfaces, renders generic branch_strategy text, overwrites a stack… | 8/10 | high | **COVERED** | #3874 (open, exact); #3553 (open, partial); #3477 (open, partial) |
| A-11 | cause | record-analysis persists `verdict: unknown` with exit 0 when the analysis-findings/v1 carrier is missing or malformed (intermittent). | 3/3 | medium | **COVERED** | #3133 (open, exact) |
| A-12 | cause | record-analysis and finalize-tasks hang or stall (exit 124) after their commit has already landed, through the unbounded dossier-sync / layout-cutover tail (SK-63/SK-74/SK-93). | 5/7 | high | **CLOSED-ONLY** | #3680 (closed, partial) |
| A-13 | cause | record-analysis writes host-absolute /home/<user>/ paths into analysis-report.md input_artifacts, leaking local layout into a public repo. | 4/4 | high | **COVERED** | #3398 (open, exact) |
| A-14 | cause | CLI writers leave their own generated artifacts uncommitted: mission create (status.events.jsonl, tasks/), finalize (sync-state.json), record-analysis (dossier snapshot), implement claim (base_commit metadata). The next guard t… | 5/6 | medium | **COVERED** | #3933 (open, partial); #3471 (open, exact); #4228 (open, exact) |
| A-15 | cause | Churn around analysis-report freshness and the planning pin. mark-status checkbox flips, tracer/issue-matrix edits and spec edits all make analysis-report.md stale, and record-analysis is idempotent with no --force. Post-finali… | 8/10 | high | **COVERED** | #2493 (open, exact); #2582 (open, exact); #4827 (closed, partial) |
| A-16 | improvement | wps.yaml has no mission-level or per-WP freeform notes field. finalize-tasks regenerates tasks.md mechanically, so mission-wide guidance (PR shape, chokepoints, gate tables) is copied into every WP prompt, and one WP pointed to… | 3/4 | medium | **UNCOVERED** | #428 (open, adjacent); #3944 (open, adjacent) |
| A-17 | both | owned_files authoring is validated too late and too narrowly. Globs that match zero files (singular vs plural dirs) pass; a WP body edits files its write_scope omits; test files and generated files (_completion_manifest.json, g… | 6/7 | high | **PARTIAL** | #3468 (open, partial); #1979 (open, partial); #2742 (open, partial); #2249 (closed, partial) |
| A-18 | cause | Ownership and dependency granularity is too coarse. File-level disjointness forces separate planned WPs into one oversized WP, the dependency gate works per WP so a dependent waits for the whole absorbing WP, and the chokepoint… | 3/4 | medium | **PARTIAL** | #2742 (open, partial); #2088 (closed, partial) |
| A-19 | both | Plan-phase claims are not checked against the code. Census counts undershoot (they are floors, not measurements), named files or tests do not exist, WPs own the wrong file or miss a gate, unowned tests pin the old bug, and PR-s… | 14/17 | high | **PARTIAL** | — |
| A-20 | improvement | Issue and brief premises are often stale at specify time: already fixed, retired by an earlier mission, already being fixed by an open PR, or measured wrong (e.g. a '17 quarantines' count that was actually 1). Missions shrank b… | 13/13 | high | **UNCOVERED** | — |
| A-21 | cause | A git-tracked project override (.kittify/overrides/missions/software-dev/templates/plan-template.md) outranks the canonical built-in template. It still says 'Constitution Check' and points at the retired src/doctrine path, so e… | 5/7 | high | **CLOSED-ONLY** | #3182 (closed, partial); #760 (closed, partial) |
| A-22 | cause | Shipped packs/built-in templates still use the prohibited 'Feature' term (plan-template.md:4 'Feature specification from', the specify checklist, and others), so every consumer mission's plan starts with a Terminology Canon vio… | 3/5 | medium | **PARTIAL** | #2964 (open, partial) |
| A-23 | cause | CLI-generated auto-commit subjects fail commitlint and use the prohibited term: 'Add meta for feature <slug>', 'Add tasks for feature', 'Add plan for feature', 'Add analysis report for mission'. | 4/4 | medium | **PARTIAL** | #4837 (open, adjacent); #2964 (open, adjacent) |
| A-24 | cause | Generated implement guidance contradicts the charter workflow. workflow_executor.py prints raw `git commit -m "feat(WP##)…"` recipes where the repo mandates safe-commit (with FILES/--to-branch), and the WP template gives PR cre… | 2/2 | high | **UNCOVERED** | — |
| A-25 | improvement | The software-dev spec template has no optional Clarifications, Out-of-scope, Provenance or Sizing sections, and one mission got a 0-byte spec.md. The tasks-phase prompts name template stages (tasks-outline/tasks-packages) witho… | 3/4 | medium | **UNCOVERED** | #2744 (open, adjacent); #4926 (closed, adjacent) |
| A-26 | improvement | Tracker-hygiene limits in the operating procedure: a fork cannot assign the HiC on upstream issues (DIR-003/012 unsatisfiable); `gh pr view --json files` silently truncates at 100 files; a closed issue cannot serve as the open … | 6/6 | medium | **UNCOVERED** | — |
| A-27 | cause | LocalTrackerService.sync_publish was missing, so `tracker sync publish` on beads/fp raised an uncaught AttributeError. Tracers also asked for the out-of-scope egress follow-ups to be filed. | 2/3 | medium | **CLOSED-ONLY** | #3168 (closed, exact) |
| A-28 | both | Spec and plan review squads over-iterate. They run 4-6 fresh-sweep rounds with HALTs on wording, attribution and line-range precision; the spec designs mechanism instead of stating intent; specs grow 3x with duplicated facts th… | 6/7 | high | **PARTIAL** | #3925 (open, adjacent) |
| A-29 | improvement | Planning point-cut squads (post-plan brownfield, post-tasks anti-laziness, architecture-alignment/SSOT) repeatedly caught wrong owned files, missed gates, SSOT bypasses, fakeable DoDs and lane cycles before implementation, at h… | 4/4 | high | **CLOSED-ONLY** | #2094 (closed, exact) |
| A-30 | improvement | Ratchet, parity and literal-presence architectural tests added per mission are mostly friction. The operator ruled for keeping only behavioural/negative invariants and retiring mission-scoped ratchets with their mission. Deferr… | 4/4 | medium | **COVERED** | #2631 (open, exact); #1931 (open, partial) |
| A-31 | both | Mission tracer files are seeded at planning and almost never filled during implement or review (25 of 70 missions have placeholder-only implement sections). They are seeded late or retroactively because specify/plan/tasks do no… | 25/27 | medium | **PARTIAL** | #3072 (open, adjacent); #2095 (closed, partial) |
| A-32 | cause | The tracer write surface is split. The canonical tracer-append CLI writes traces/<cat>.md, but 46 missions keep root-level tracer-*.md files (18 use tracers/, 53 use traces/). Concurrent agents append to stale lane-worktree cop… | 10/10 | high | **PARTIAL** | #4959 (closed, adjacent); #3072 (open, adjacent) |
| A-33 | cause | The post-plan point-cut hook fires as soon as setup-plan scaffolds the template plan.md, before any plan is written. | 1/1 | medium | **COVERED** | #2746 (open, exact) |
| A-34 | cause | finalize-tasks warns 'missing plan_concern_refs and cross_cutting is not set' for plans that have no IC-## concerns at all. This is expected noise, and agents mark WPs cross_cutting just to silence it. | 2/2 | low | **UNCOVERED** | — |

## Gaps and notes per cluster

- **A-01 (PARTIAL)**: Nothing covers the single lane-planning node that causes the cycle, the WP-level remedy (fold the baseline WP, or move the ordering into prose), or a validate-only early warning. Three missions on 2026-09-22 hit it after #3696 landed.
- **A-02 (CLOSED-ONLY)**: No residual. All tracer evidence predates the close (latest 2026-08-14), and the check is on main.
- **A-04 (PARTIAL)**: _detect_dependency_conflicts still blocks adding a genuine edge when the frontmatter holds a different non-empty set (interpreter-matrix, 2026-09-22). No issue makes wps.yaml the authority for dependencies.
- **A-05 (PARTIAL)**: Near-term defect, verified on main at mission_finalize.py:1047-1060: with wps.yaml present, the requirement_refs in wps.yaml are never read. The tasks.md parser (mission_parsing.py ~l.102-108) has no citation-vs-declaration scoping and no multi-line capture.
- **A-08 (UNCOVERED)**: No open or closed issue proposes a status marker for requirements (descoped/retired/omission). Searched 'descoped requirement', 'retired FR', 'strikethrough', 'satisfied-by-omission'. Tracer ledger SK-51 was never filed.
- **A-09 (PARTIAL)**: Missing: artifact writes (frontmatter/tasks.md/lanes.json/issue-matrix) before a failed commit, which then blocks a clean re-run; the commit-ordering bug where files_committed lists status.events.jsonl but the commit lacks the appended events; and no write-without-commit mode.
- **A-12 (CLOSED-ONLY)**: One sighting post-dates the close (design-phase-orchestrator-api, 2026-09-02: trigger_feature_dossier_sync_if_enabled). That function is gone from src/ on main and the sync transport was deleted in Aug 2026, so this is likely resolved. Re-confirm before filing anything.
- **A-14 (COVERED)**: Sub-gap: mission create's untracked status.events.jsonl and record-analysis's uncommitted dossier snapshot are not named in these issues. Worth a comment on #3933 rather than a new issue.
- **A-15 (COVERED)**: Mostly resolved on main. analysis_report.py now hashes only spec/plan/tasks (+charter) and _normalize_tasks_md (l.194) removes checkbox churn, so #2493 item 1 looks fixed; confirm and close that item. Tracers and issue-matrix are not hash inputs. The tracer evidence for them (2026-06-27) predates this. The planning-pin repin was fixed by #4827 (closed 2026-09-21). Residual: no record-analysis --force for a fresh commit, which is low value.
- **A-16 (UNCOVERED)**: No issue asks for a notes/preamble field on WpsManifest. Searched 'wps.yaml notes', 'preamble', 'freeform', 'tasks.md regenerated overwrites prose'.
- **A-17 (PARTIAL)**: Missing: a finalize-time cross-check of each WP body's named files against its owned_files/write_scope, zero-match glob rejection for non-create_intent globs, a git check-ignore warning for generated/ignored targets, and preserving hand ownership amendments across regeneration.
- **A-18 (PARTIAL)**: Not covered: dependency-ordered same-file ownership, subtask-level dependency edges, and doctrine wording for chokepoint serialization.
- **A-19 (PARTIAL)**: No open issue. The adversarial-squad-cadence styleguide (post-plan brownfield, post-tasks anti-laziness) addresses this as optional advice. Missing is a deterministic check: plan- or finalize-time existence checks for named paths/tests, and a 'grep tests exercising changed symbols' step in the plan prompt.
- **A-20 (UNCOVERED)**: No open or closed issue. The post-spec 'scope and prior-art check' squad in adversarial-squad-cadence is optional, and the specify prompt has no premise re-grounding step (checked packs/built-in/.../specify/prompt.md). Searched 're-ground premise', 'already fixed', 'open PR already fixes', 'stale issue scope'.
- **A-21 (CLOSED-ONLY)**: Residual or regression: tracer evidence runs to 2026-09-22, and I confirmed the override is still stale on main today (line 6 cites src/doctrine; line 35 'Constitution Check'). No staleness check exists for overrides.
- **A-22 (PARTIAL)**: User-facing template prose in packs/built-in (9 files contain 'Feature', verified) is not in #2964's identifier-focused scope.
- **A-23 (PARTIAL)**: Still live on main: mission_creation.py:266, mission_setup_plan.py:229/794/848 and mission_finalize.py:2367 build 'Add … for feature <slug>' subjects with no conventional-commit type.
- **A-24 (UNCOVERED)**: No issue. Searched 'raw git commit safe-commit footer', 'WP template PR creation orchestrator'. Verified raw `git commit` recipes at workflow_executor.py:1361/1438/1497 and implement.py:423. Decide first whether safe-commit is consumer doctrine or in-house only (tier question).
- **A-25 (UNCOVERED)**: Low value. mission_creation.py:1035-1037 now copies the spec template, so the 0-byte case looks resolved. What remains is template content and prompt clarity.
- **A-26 (UNCOVERED)**: No issue found for any of the four. Searched 'assign from fork', 'gh pr view truncate', 'ledger ids'. These are doctrine/procedure notes (packs/internal), not product defects.
- **A-27 (CLOSED-ONLY)**: No residual. The fix is on main.
- **A-28 (PARTIAL)**: No issue covers planning-phase squads: delta-scoped re-sweeps, a severity floor for wording nits, 'spec at intent level, mechanism in plan', one canonical home per fact, and marking unreviewed post-cap text in the handoff.
- **A-29 (CLOSED-ONLY)**: Already doctrine and working as intended. Optional follow-up: add the 'architecture-alignment/SSOT' lens to the post-tasks pattern's example profiles.
- **A-30 (COVERED)**: Small sub-gap: a deferred invariant should state at assignment that 'the loop will not verify this' (lifecycle-gate mission). Not covered, low value.
- **A-31 (PARTIAL)**: No open issue on the fill rate. Tracer evidence (to 2026-09-25) post-dates the closes. The procedure (mission-tracer-files.procedure.yaml:69) says absence 'does not block acceptance' and still references the deleted src/doctrine/templates path.
- **A-32 (PARTIAL)**: No issue on the location/name split: the CLI (traces/) disagrees with the orchestrator briefs and most missions (root tracer-*.md). Also missing: a rule that tracers are coordination-level state, so they should be written only via tracer-append to the coord/primary surface and never from lane worktrees.
- **A-34 (UNCOVERED)**: No issue. Verified still live at core/wps_manifest.py:195-221: the check does not look at whether plan.md defines any IC-## headings. Searched open titles for plan_concern/IC-##.

## Draft issues (not filed)

### A-01 [P1] finalize-tasks: planning_artifact WPs bundled into one lane-planning node produce false LANE_DEPENDENCY_CYCLE; refusal gives no WP-level remedy
- Scope: Either let a planning-artifact WP gate code lanes without single-lane bundling, or have `finalize-tasks --validate-only` detect the bidirectional planning-lane shape and name the WP edges to fold or drop. Document in the tasks-packages prompt that `dependencies:` is for real data dependencies, not scheduling order.
- Labels: workflow, reliability, catfooding, priority:P1
- Relates to / depends on: #428, #3431

### A-05 [P1] finalize-tasks ignores wps.yaml requirement_refs (frontmatter-only) and its tasks.md fallback miscredits prose citations / truncates wrapped ref lines
- Scope: Read requirement_refs from wps.yaml when present and generate the frontmatter from it (one write path). Until then, fail fast when wps.yaml and frontmatter disagree. Port #3395's declared-shape scoping and multi-line capture to mission_parsing.py.
- Labels: workflow, reliability, priority:P1
- Relates to / depends on: #428, #2066, #3221

### A-09 [P1] finalize-tasks is mutate-before-fail: validate fully, then write+commit atomically (frontmatter, tasks.md, lanes.json, issue-matrix, events)
- Scope: Stage every finalize write in a pending set, validate, then write and commit in one transaction; roll back on failure. Emit status events before staging so the reported files_committed matches the commit. Add a --no-commit write mode for iterative fixes. Pair with #4075/#2644.
- Labels: workflow, reliability, priority:P1
- Relates to / depends on: #4075, #2644

### A-04 [P2] finalize-tasks: _detect_dependency_conflicts refuses a manifest-driven dependency edge addition (only narrowing to [] passes); make wps.yaml authoritative
- Scope: When wps.yaml is present, treat its dependencies as the authority and rewrite WP frontmatter from it, or report the diff and apply it under an explicit flag. Add a regression test: add an edge in wps.yaml over a non-empty frontmatter set.
- Labels: workflow, reliability, priority:P2
- Relates to / depends on: #4152, #4135, #4890

### A-08 [P2] Requirement lifecycle status: let spec.md/wps.yaml mark an FR descoped/retired/satisfied-by-omission so the unmapped-FR gate and tasks.md render honour it
- Scope: Add a structured status to requirement rows (spec.md table) and to requirement_refs entries in wps.yaml. The coverage gate should exempt descoped/retired ids, and generate_tasks_md_from_manifest should show per-ref status. Design this alongside #428 so it becomes part of the JSON-owned state, not a new Markdown convention.
- Labels: enhancement, workflow, priority:P2
- Relates to / depends on: #2066, #3519

### A-17 [P2] finalize-tasks ownership lint: cross-check WP body file mentions vs owned_files, reject zero-match globs, warn on gitignored/generated targets
- Scope: At --validate-only, extract the paths each WP prompt names and flag any not covered by owned_files/create_intent. Reject globs that match zero files and are not in create_intent. Warn when an owned path is gitignored or a known generated artifact, naming its tracked source. Keep manual owned_files amendments across re-finalize.
- Labels: workflow, reliability, priority:P2
- Relates to / depends on: #3468, #1979, #2742, #2249

### A-19 [P2] plan/tasks prompts: require live re-measurement of census counts and existence check of every named file/test before WP sizing
- Scope: Add a plan-prompt step: re-grep counts at authoring time, record them as measured, and list tests that exercise the changed symbols. Add a finalize --validate-only check that every non-create_intent path named in plan.md's Blast Radius or in WP prompts exists.
- Labels: workflow, enhancement, priority:P2
- Relates to / depends on: none

### A-20 [P2] specify: add a premise re-grounding step — verify each cited issue's claim against current code, open PRs touching the same seam, and cited SHAs before scoping
- Scope: Add a short, required checklist to the specify mission-step prompt. For each cited #issue: reproduce or verify the claim at HEAD, run `gh pr list --search` for open PRs on the seam, and `git cat-file -e` any cited SHA. Record the results in spec.md 'Premise verification'. This is advisory doctrine, not a gate.
- Labels: workflow, enhancement, catfooding, priority:P2
- Relates to / depends on: none

### A-21 [P2] Stale .kittify/overrides content templates shadow canonical packs/built-in templates (plan-template: 'Constitution Check', retired src/doctrine path) — delete/resync + add override-staleness doctor check
- Scope: Delete or resync the repo's overrides/missions/software-dev/templates/*. Add a `doctor` check that flags an override whose canonical counterpart has changed since the override was last synced (hash or version stamp).
- Labels: workflow, tech-debt, priority:P2
- Relates to / depends on: #3182, #760

### A-24 [P2] Implement prompt/footer and WP template contradict commit & PR doctrine (raw `git commit` vs safe-commit; WP agent vs orchestrator opens PR)
- Scope: Decide whether safe-commit belongs to consumers (packs/built-in) or only in-house (packs/internal). Then align the workflow_executor footer and the WP template with that decision, and give PR creation to the orchestrator step.
- Labels: workflow, documentation, priority:P2
- Relates to / depends on: none

### A-28 [P2] Planning-squad calibration: delta-scoped re-sweeps, nit severity floor, intent-level spec guidance, and flag unreviewed post-cap/operator-amended text
- Scope: Extend the adversarial-squad-deployment procedure and the specify/plan prompts: cycle N reviews only the delta; wording/line-range nits never trigger a HALT; specs state intent while plan owns mechanism; any text amended after the last squad round is marked unreviewed in the handoff.
- Labels: workflow, doctrine, priority:P2
- Relates to / depends on: #3925

### A-16 [P3] WpsManifest: add optional mission-level `notes`/preamble (and per-WP notes) rendered into tasks.md so finalize-tasks regeneration preserves cross-WP guidance
- Scope: Add an optional `notes` markdown field at manifest and WP level. generate_tasks_md_from_manifest renders it verbatim, and finalize never drops it. Update the tasks-outline/tasks-packages prompts to use it instead of duplicating guidance into each WP prompt.
- Labels: enhancement, workflow, priority:P3
- Relates to / depends on: #428, #3944

### A-22 [P3] Terminology: remove 'Feature' from shipped packs/built-in templates/prompts (plan-template.md:4 et al.) + scoped guard
- Scope: Replace Mission-domain 'Feature' wording in packs/built-in/missions/**/templates and mission-steps prompts. Extend test_no_legacy_terminology with a scoped template-prose check. This is a small, safe bulk edit (occurrence map), and the prose half of #2964.
- Labels: documentation, tech-debt, good first issue, priority:P3
- Relates to / depends on: #2964

### A-23 [P3] CLI auto-commit subjects: conventional-commit form + Mission terminology ('Add … for feature <slug>' in mission create/setup-plan/finalize)
- Scope: Replace the f-string subjects with `chore(mission): add <artifact> for <slug>`-style messages. Add a unit test asserting that every CLI-generated subject matches the repo commitlint pattern.
- Labels: tech-debt, good first issue, domain:git, priority:P3
- Relates to / depends on: #4837, #2964

### A-25 [P3] software-dev spec template: optional Clarifications/Out-of-scope/Sizing sections; tasks prompts name the backing CLI verbs; blast-radius read vs edit
- Scope: Add optional sections to packs/built-in/missions/software-dev/templates/spec-template.md. In tasks-outline/tasks-packages prompts, list the CLI verbs each stage runs. Split Blast Radius into 'edited' and 'read-only' columns in plan-template.
- Labels: documentation, enhancement, priority:P3
- Relates to / depends on: #2744, #4926

### A-26 [P3] packs/internal procedure notes: fork-safe HiC assignment fallback, paginate PR file lists (gh api) beyond 100, cite upstream #issues not SK-xx in committed artifacts
- Scope: Update the in-house tracker/landing procedures (packs/internal) with: a fork fallback for DIR-012 (mention the HiC in a comment), the gh file-list pagination recipe, and the rule that committed artifacts cite upstream issue numbers.
- Labels: documentation, priority:P3
- Relates to / depends on: none

### A-31 [P3] Mission tracers: auto-seed at mission create, prompt per-WP append at implement/review handoff, non-blocking non-empty check at accept (+ fix stale template path in procedure)
- Scope: mission create scaffolds the canonical tracer trio. The implement/review prompts end with a one-line `agent tracer-append` nudge. accept reports placeholder-only tracers as a non-blocking warning. Fix the src/doctrine path in the procedure. Depends on #3072 so entries are actually consumed.
- Labels: workflow, doctrine, catfooding, priority:P3
- Relates to / depends on: #3072, #2095

### A-32 [P3] One canonical tracer location: tracer-append (traces/<cat>.md via placement seam) is the only writer; migrate/recognise root tracer-*.md; forbid lane-worktree appends
- Scope: Declare traces/<category>.md, routed by the placement seam, as the single tracer surface. Have the retrospective and review read legacy root tracer-*.md as a fallback. Update the orchestrator/brief templates to call `agent tracer-append` and never edit tracer files inside lane worktrees.
- Labels: workflow, tech-debt, priority:P3
- Relates to / depends on: #4959, #3072

### A-34 [P3] finalize-tasks: suppress plan_concern_refs coverage warning when plan.md declares no IC-## concerns
- Scope: Pass the parsed plan concern set into check_concern_refs_coverage and return [] when it is empty. Add a unit test for both branches.
- Labels: usability, good first issue, priority:P3
- Relates to / depends on: none

### Sequencing (planner view)
- **Do first (P1, same seam, one mission):** A-09 (transactional finalize), A-05 (one write path for requirement_refs), A-01 (planning-lane false cycle). All three live in `mission_finalize.py` / `lanes/compute.py` and share the tests. Land them next to the open #3874 (topology-blind finalize), because A-09's transaction is the natural place to add #3874's no-silent-overwrite rule.
- **Then, together with the #1676 / #428 JSON-owned planning epic:** A-08 (requirement lifecycle status) and A-16 (notes field). Both are schema additions to WpsManifest and should not become new Markdown conventions.
- **Doctrine or prompt batch (parallel, no code-risk):** A-20 (premise re-grounding), A-19 (live census and existence checks), A-28 (planning-squad calibration), A-24 (commit/PR doctrine alignment, after the built-in vs internal tier decision), A-25, A-26 (packs/internal).
- **Good-first-issue batch:** A-22, A-23, A-34, plus A-21's override delete/resync. The A-21 doctor check is the only non-trivial part.
- **Tracer lifecycle:** A-32 (one location) before A-31 (fill-rate prompts). A-31 depends on open #3072 so that entries are actually consumed.

## Close-candidates noticed (for the orchestrator, not acted on)
- #2493 item 1 (mark-status re-stales analysis-report) appears fixed on main: `_normalize_tasks_md` in analysis_report.py:194.
- #3394 may be stale-open. Its sibling #3396 says #3395 already scoped the parser to declaring positions. Recent tracer sightings (2026-08-13) predate or coincide with that change.
- #3398: the forward fix (`_relativize_or_raise`) is on main. What remains is the historical backfill of 171 files.

## Honest limits
- GitHub semantic search was heavily rate-limited because sibling delegates share the same user quota. I ran about 20 successful searches. For clusters with no search hit, I relied on the full open-title index grep (818 issues) plus reading issue bodies (`issue_read`, about 30 issues). Closed-issue coverage is therefore thinner than open coverage, and a CLOSED-ONLY or UNCOVERED verdict could hide a closed issue I did not surface. I did not page all 2,367 closed titles.
- The mission creation date (meta.json `created_at`) stands in for the date of each tracer item when comparing against issue close dates. Items can be logged days after a mission was created.
- 'Still live on main' claims (A-05, A-21, A-22, A-23, A-24, A-32, A-34) were checked by grepping or reading the current checkout, not by running the CLI. 'Fixed on main' claims (A-02, A-12, A-15, A-27) rest on code inspection only; no regression tests were run.
- Clustering is a judgment call. A-10 and A-06 overlap on the non-idempotent FR-005a drop (#3874), and A-17 and A-03 overlap on ownership. Each tracer item is assigned to exactly one cluster (215/215).
- A-24's premise (safe-commit is mandatory) is this repo's charter rule. Whether it should bind consumers is a pack-tier decision, and I did not make it.
